#!/usr/bin/env python3
# encoding: utf-8
import json
import pathlib
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union

import requests
from loguru import logger
from tqdm import tqdm

from registry_client.digest import Digest
from registry_client.errors import ImageManifestCheckError, ImageNotFoundError
from registry_client.export import GZIP_MAGIC, GZipDeCompress, TarImageDir
from registry_client.manifest import ManifestsHandler, ManifestsListHandler
from registry_client.media_types import ImageMediaType
from registry_client.platforms import Platform
from registry_client.scope import RepositoryScope, Scope
from registry_client.utlis import DEFAULT_REGISTRY_HOST, DEFAULT_REPO


class ImageFormat(Enum):
    V1 = "v1"
    V2 = "v2"
    OCI = "oci"


@dataclass
class ImagePullOptions:
    save_dir: pathlib.Path
    reference: str = "latest"
    image_format: ImageFormat = field(default=ImageFormat.V2)
    platform: Platform = field(default_factory=Platform)
    compression: bool = False


class Layer:
    def __init__(self, digest: Digest, image: "Image", save_dir: pathlib.Path):
        self.digest = digest
        self.image = image
        self.client = image.client
        self.save_dir = save_dir

    def get_blob(self) -> pathlib.Path:
        save_file = self.save_dir.joinpath(f"{self.digest.hex}.layer").absolute()
        url = self.image._build_url(f"blobs/{self.digest}")
        with requests.get(url, headers=self.client.headers, stream=True) as resp, open(save_file, "wb") as f:
            for chunk in resp.iter_content(5120):
                if chunk:
                    data_size = f.write(chunk)
        logger.info(f"download layer {self.digest} to {save_file.absolute()}")
        return save_file.absolute()

    def export_to_tar(self):
        save_file = self.get_blob()
        target = save_file.with_suffix(".tar")
        with save_file.open("rb") as f:
            head = f.read(10)
            if head.startswith(GZIP_MAGIC):
                GZipDeCompress(save_file, target).do()
                save_file.unlink()
                return target
        save_file.rename(target)
        return target

    def delete(self):
        url = self.image._build_url(f"blobs/{self.digest}")
        resp = requests.delete(url, headers=self.client.headers)

    def push_blob(self):
        pass

    def head(self) -> bool:
        url = self.image._build_url(f"blobs/{self.digest}")
        resp = requests.head(url, headers=self.client.headers)
        return resp.status_code == 200


class Image:
    def __init__(self, name: str, registry: "Registry"):
        if "/" in name:
            repo, name = name.rsplit("/", 1)
        else:
            repo = DEFAULT_REPO
        self.repo = repo
        self.name = name
        self._name_with_repo = f"{self.repo}/{self.name}"
        self.registry = registry
        self.client = registry.client

    def repo_tag(self, reference: str):
        assert reference != ""
        if Digest.is_digest(reference):
            return None
        if self.registry._host == DEFAULT_REGISTRY_HOST:
            if self.repo == DEFAULT_REPO:
                return f"{self.name}:{reference}"
            return f"{self.repo}/{self.name}:{reference}"
        return f"{self.registry._host}/{self.repo}/{self.name}:{reference}"

    def __str__(self):
        return self._name_with_repo

    def __eq__(self, other: "Image"):
        return self.registry == other.registry and self._name_with_repo == other._name_with_repo

    def __ne__(self, other):
        return not self.__eq__(other)

    __repr__ = __str__

    def _set_auth_header(self, scope: Scope):
        self._update_header(**self.registry.auth_with_scope(scope).token)

    def _update_header(self, **kwargs):
        self.client.headers.update(kwargs)

    def _build_url(self, url_suffix):
        return self.registry.build_url(f"/v2/{self._name_with_repo}/{url_suffix}")

    def _send_req_with_scope(self, url_suffix: str, scope: Scope, method: str, **kwargs) -> requests.Response:
        self._set_auth_header(scope)
        url = self._build_url(url_suffix)
        func = getattr(self.client, f"_{method.lower()}")
        return func(url, **kwargs)

    def _download_layer_and_save(self, save_dir: pathlib.Path, digest: Digest) -> pathlib.Path:
        layer = Layer(digest, self, save_dir=save_dir)
        tar_file = layer.export_to_tar()
        return tar_file

    def _tar_layers(
        self,
        image_config: requests.Response,
        layers_file_list: List[pathlib.Path],
        layers_dir: pathlib.Path,
        options: ImagePullOptions,
    ):
        assert layers_dir.exists() and layers_dir.is_dir()
        image_config_digest = Digest.from_bytes(image_config.content)
        with layers_dir.joinpath(f"{image_config_digest.hex}.json").open("w", encoding="utf-8") as f:
            json.dump(image_config.json(), f)

        if options.image_format == ImageFormat.V2:
            with open(layers_dir.joinpath("manifest.json"), "w", encoding="utf-8") as f:
                repo_tag = self.repo_tag(options.reference)
                repo_tags = [repo_tag] if repo_tag else []
                data = {
                    "Config": f"{image_config_digest.hex}.json",
                    "RepoTags": repo_tags,
                    "Layers": [path.name for path in layers_file_list],
                }
                json.dump([data], f)
            image_save_path = options.save_dir.joinpath(f"{self.repo}_{self.name}.tar")
            TarImageDir(src_dir=layers_dir, target_path=image_save_path).do()
            return image_save_path

    def pull(self, options: ImagePullOptions) -> pathlib.Path:
        if not options.save_dir.exists():
            options.save_dir.mkdir(parents=True)
        tmp_dir = tempfile.TemporaryDirectory(prefix="image_download_")
        scope = RepositoryScope(self._name_with_repo, actions=["pull"])
        self._set_auth_header(scope)
        image_manifest: Digest = self.exist(options.reference)
        if not image_manifest:
            raise ImageNotFoundError(self._name_with_repo, options.reference)
        manifest = self.get_manifest(options.reference, platform=options.platform)
        image_config = self.get_image_config(manifest.config.digest)
        layers_file_list = []
        with tqdm(total=len(manifest.layers)) as progress:
            for one_layer in manifest.layers:
                tar_file = self._download_layer_and_save(save_dir=pathlib.Path(tmp_dir.name), digest=one_layer.digest)
                layers_file_list.append(tar_file)
                progress.update(1)
        image_path = self._tar_layers(
            image_config=image_config,
            layers_file_list=layers_file_list,
            layers_dir=pathlib.Path(tmp_dir.name),
            options=options,
        )
        logger.info(f"image save to {image_path}")
        return image_path

    @classmethod
    def push(cls, image_path: pathlib.Path, force=False):
        assert image_path.exists() and image_path.is_file()

    def get_tags(self, limit: Optional[int] = None, last: Optional[str] = None) -> List[str]:
        scope = RepositoryScope(repo_name=self._name_with_repo, actions=["pull"])
        params = {}
        if limit:
            params["n"] = limit
        if last:
            params["last"] = last
        resp = self._send_req_with_scope("tags/list", scope, "GET", params=params)
        if resp.status_code in [401, 404]:  # docker hub status_code is 401, harbor is 404, registry mirror is 200
            logger.warning("image may be dont exist, return empty list")
            return []
        resp.raise_for_status()
        tags = resp.json().get("tags", None)
        return tags if tags is not None else []

    def exist(self, ref: str) -> Union[bool, Digest]:
        scope = RepositoryScope(repo_name=self._name_with_repo, actions=["pull"])
        resp = self._send_req_with_scope(f"manifests/{ref}", scope, "HEAD")
        if resp.status_code != 200:
            return False
        logger.debug(resp.headers)
        dcg = resp.headers.get("Docker-Content-Digest") or resp.headers.get("Etag")
        return Digest(dcg)

    def get_manifest(self, ref: Union[str, Digest], platform: Platform = None) -> ManifestsHandler:
        scope = RepositoryScope(repo_name=self._name_with_repo, actions=["pull"])
        resp = self._send_req_with_scope(f"manifests/{ref}", scope, "GET")
        if Digest.is_digest(ref):
            digest = Digest(ref) if isinstance(ref, str) else ref
            logger.info("Check image manifest digest")
            assert digest == Digest.from_bytes(resp.content), ImageManifestCheckError()
        if resp.json().get("mediaType") == ImageMediaType.MediaTypeDockerSchema2ManifestList.value:
            target_digest = ManifestsListHandler(resp).filter(platform)
            return self.get_manifest(target_digest)
        return ManifestsHandler(resp)

    def put_manifest(self):
        pass

    def delete_manifest(self):
        pass

    def get_image_config(self, digest: Digest):
        scope = RepositoryScope(repo_name=self._name_with_repo, actions=["pull"])
        resp = self._send_req_with_scope(f"blobs/{digest}", scope=scope, method="GET")
        logger.info(resp.json())
        return resp
