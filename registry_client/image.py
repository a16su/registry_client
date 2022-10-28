#!/usr/bin/env python3
# encoding: utf-8
import json
import pathlib
import sys
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Union

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

import httpx
import requests
from loguru import logger

from registry_client.auth import AuthClient
from registry_client.digest import Digest
from registry_client.errors import ImageNotFoundError
from registry_client.export import TarImageDir
from registry_client.manifest import ManifestClient, ManifestIndex, ManifestList
from registry_client.media_types import ImageMediaType
from registry_client.platforms import Platform
from registry_client.reference import (
    DigestReference,
    Reference,
    Repository,
)
from registry_client.scope import RepositoryScope
from registry_client.utlis import DEFAULT_REGISTRY_HOST, DEFAULT_REPO

MAX_MANIFEST_SIZE = 4 * 1048 * 1048


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


class BlobClient:
    def __init__(self, client: AuthClient):
        self.client = client

    def _send_req(
        self,
        method: Literal["GET", "STREAM", "DELETE", "HEAD", "POST"],
        ref: DigestReference,
        actions: List[str],
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
    ) -> Union[Iterable[httpx.Response], httpx.Response]:
        if not ref.is_named_digested:
            raise Exception("reference must be a digest")
        scope = RepositoryScope(ref.path, actions=actions)
        url = f"/v2/{ref.path}/blobs/{ref.digest}"
        if method == "STREAM":
            return self.client.stream("GET", url=url, auth=scope, params=params)
        return self.client.request(method, url=url, auth=scope, params=params, json=body)

    def get(self, ref: DigestReference, stream=False) -> Union[Iterable[httpx.Response], httpx.Response]:
        method = "STREAM" if stream else "GET"
        return self._send_req(method=method, ref=ref, actions=["pull"])

    def delete(self, ref: DigestReference) -> httpx.Response:
        return self._send_req("DELETE", ref=ref, actions=["pull"])

    def head(self, ref: DigestReference) -> httpx.Response:
        return self._send_req(method="HEAD", ref=ref, actions=["pull"])


class ImageClient:
    def __init__(self, client: AuthClient):
        self.client = client
        self._blob_client = BlobClient(client)
        self._manifest_client = ManifestClient(client)

    def repo_tag(self, reference: Reference):
        assert reference != ""
        if isinstance(reference, DigestReference):
            return None
        target = reference.tag
        result = reference.repository.path.split("/", 1)
        if self.client.base_url.netloc.decode() == DEFAULT_REGISTRY_HOST:
            if len(result) == 2 and result[0] == DEFAULT_REPO:
                return f"{result[-1]}:{target}"
            return f"{reference.path}:{target}"
        return str(reference)

    def list_tag(self, ref: Repository, limit: Optional[int] = None, last: Optional[str] = None) -> httpx.Response:
        name = ref.path
        scope = RepositoryScope(repo_name=name, actions=["pull"])
        params = {}
        if limit:
            params["n"] = limit
        if last:
            params["last"] = last
        return self.client.get(f"/v2/{name}/tags/list", auth=scope, params=params)

    def _tar_layers(
        self,
        reference: Reference,
        image_config: requests.Response,
        layers_file_list: List[pathlib.Path],
        layers_dir: pathlib.Path,
        options: ImagePullOptions,
    ):
        target = reference.tag or reference.digest.short
        assert layers_dir.exists() and layers_dir.is_dir()
        image_config_digest = Digest.from_bytes(image_config.content)
        with layers_dir.joinpath(f"{image_config_digest.hex}.json").open("w", encoding="utf-8") as f:
            json.dump(image_config.json(), f)

        if options.image_format == ImageFormat.V2:
            with open(layers_dir.joinpath("manifest.json"), "w", encoding="utf-8") as f:
                repo_tag = self.repo_tag(reference)
                repo_tags = [repo_tag] if repo_tag else []
                data = {
                    "Config": f"{image_config_digest.hex}.json",
                    "RepoTags": repo_tags,
                    "Layers": [path.name for path in layers_file_list],
                }
                json.dump([data], f)
            image_save_path = options.save_dir.joinpath(f"{reference.repository.name().replace('/', '_')}_{target}.tar")
            TarImageDir(src_dir=layers_dir, target_path=image_save_path).do()
            return image_save_path

    def _get_manifest(self, resp: httpx.Response, ref: DigestReference, platform: Platform = None) -> ManifestIndex:
        if resp.status_code == 404:
            raise ImageNotFoundError(ref)
        resp.raise_for_status()
        media_type = resp.headers.get("Content-Type")
        if media_type == ImageMediaType.MediaTypeDockerSchema2Manifest.value:
            return ManifestIndex(**resp.json())
        elif media_type == ImageMediaType.MediaTypeDockerSchema2ManifestList.value:
            manifest_list = ManifestList(**resp.json())
            digest = manifest_list.filter_by_platform(platform)
            new_ref = DigestReference(ref.repository, digest=digest)
            resp = self._manifest_client.get(new_ref)
            return self._get_manifest(resp, ref, platform)
        else:
            raise Exception("no match handler")

    def pull(self, ref: Reference, options: ImagePullOptions) -> pathlib.Path:
        if not options.save_dir.exists():
            options.save_dir.mkdir(parents=True)
        tmp_dir = tempfile.TemporaryDirectory(prefix="image_download_")
        if ref.digest:
            manifest_digest = ref.digest
        else:
            manifest_content_digest_resp: httpx.Response = self._manifest_client.head(ref)
            if manifest_content_digest_resp.status_code != 200:
                raise ImageNotFoundError(ref)
            manifest_digest = manifest_content_digest_resp.headers.get("docker-content-digest")
            if manifest_digest is None:
                manifest_digest = Digest.from_bytes(manifest_content_digest_resp.content)
        r = DigestReference(ref.repository, digest=manifest_digest)
        manifest_content_resp = self._manifest_client.get(r)
        manifest = self._get_manifest(manifest_content_resp, r, options.platform)
        image_digest = DigestReference(r.repository, digest=manifest.config.digest)
        image_config = self.get_image_config(image_digest)
        logger.info(image_config.text)
        logger.info(manifest)
        layers_file_list = []
        for one_layer in manifest.layers:
            layer_path = pathlib.Path(tmp_dir.name).joinpath(f"{one_layer.digest.hex}.tar")
            is_gzip = one_layer.media_type == ImageMediaType.MediaTypeDockerSchema2LayerGzip
            with open(layer_path, "wb") as f:
                with self._blob_client.get(
                    DigestReference(image_digest.repository, digest=one_layer.digest), stream=True
                ) as resp:
                    if is_gzip:
                        if resp.headers.get("Content-Encoding") is None:
                            resp.headers["content-encoding"] = "gzip"  # let httpx decode gzip
                    for content in resp.iter_bytes():
                        f.write(content)
            layers_file_list.append(layer_path)
        image_path = self._tar_layers(
            ref,
            image_config=image_config,
            layers_file_list=layers_file_list,
            layers_dir=pathlib.Path(tmp_dir.name),
            options=options,
        )
        # logger.info(f"image save to {image_path}")
        # return image_path
        return image_path

    @classmethod
    def push(cls, image_path: pathlib.Path, force=False):
        assert image_path.exists() and image_path.is_file()

    def exist(self, ref: Reference) -> bool:
        resp = self._manifest_client.head(ref)
        return resp.status_code == 200

    def put_manifest(self):
        pass

    def delete_manifest(self):
        pass

    def get_image_config(self, ref: DigestReference):
        resp = self._blob_client.get(ref)
        return resp
