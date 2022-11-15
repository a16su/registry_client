#!/usr/bin/env python3
# encoding: utf-8
import json
import pathlib
import re
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

from registry_client import spec
from registry_client.auth import AuthClient
from registry_client.digest import Digest
from registry_client.errors import ImageNotFoundError
from registry_client.export import ImageFileSort, ImageV2Tar, OCIImageTar
from registry_client.manifest import ManifestClient
from registry_client.media_types import ImageMediaType
from registry_client.platforms import Platform, filter_by_platform
from registry_client.reference import (
    CanonicalReference,
    DigestReference,
    NamedReference,
    Reference,
    TaggedReference,
)
from registry_client.scope import RepositoryScope
from registry_client.utlis import (
    DEFAULT_REGISTRY_HOST,
    DEFAULT_REPO,
    diff_ids_to_chain_ids,
)

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
        ref: CanonicalReference,
        actions: List[str],
        method: str = Literal["GET", "STREAM", "DELETE", "HEAD", "POST"],
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
    ) -> Union[Iterable[httpx.Response], httpx.Response]:
        if not isinstance(ref, CanonicalReference):
            raise Exception("reference must be a digest")
        scope = RepositoryScope(ref.path, actions=actions)
        url = f"/v2/{ref.path}/blobs/{ref.digest}"
        if method == "STREAM":
            return self.client.stream("GET", url=url, auth=self.client.new_auth(auth_by=scope), params=params)
        return self.client.request(
            method,
            url=url,
            auth=self.client.new_auth(auth_by=scope),
            params=params,
            json=body,
        )

    def get(self, ref: CanonicalReference, stream=False) -> Union[Iterable[httpx.Response], httpx.Response]:
        method = "STREAM" if stream else "GET"
        return self._send_req(method=method, ref=ref, actions=["pull"])

    def delete(self, ref: CanonicalReference) -> httpx.Response:
        return self._send_req(method="DELETE", ref=ref, actions=["pull"])

    def head(self, ref: CanonicalReference) -> httpx.Response:
        return self._send_req(method="HEAD", ref=ref, actions=["pull"])


class ImageClient:
    def __init__(self, client: AuthClient):
        self.client = client
        self._blob_client = BlobClient(client)
        self._manifest_client = ManifestClient(client)

    def repo_tag(self, reference: TaggedReference):
        assert reference != ""
        if isinstance(reference, (CanonicalReference, DigestReference)):
            return None
        if isinstance(reference, NamedReference):
            reference = TaggedReference(reference.domain, reference.path, "latest")
        target = reference.target
        result = reference.path.split("/", 1)
        if self.client.base_url.netloc.decode() == DEFAULT_REGISTRY_HOST:
            if len(result) == 2 and result[0] == DEFAULT_REPO:
                return f"{result[-1]}:{target}"
            return f"{reference.path}:{target}"
        return str(reference)

    def list_tag(
        self,
        ref: NamedReference,
        limit: Optional[int] = None,
        last: Optional[str] = None,
    ) -> httpx.Response:
        name = ref.path
        scope = RepositoryScope(repo_name=name, actions=["pull"])
        params = {}
        if limit:
            params["n"] = limit
        if last:
            params["last"] = last
        return self.client.get(
            f"/v2/{name}/tags/list",
            auth=self.client.new_auth(auth_by=scope),
            params=params,
        )

    def _tar_layers(
        self,
        reference: Union[TaggedReference, CanonicalReference, DigestReference],
        layers_dir: pathlib.Path,
        options: ImagePullOptions,
    ) -> pathlib.Path:
        """
        |- layer_id1/layer.tar
        |- layer_id2/layer.tar
        |- image_config.json
        Args:
            reference:
            layers_dir:
            options:

        Returns:

        """
        target = reference.target
        image_save_path = options.save_dir.joinpath(f"{re.sub(r'[.:/]', '_', reference.name)}_{target}.tar")
        assert layers_dir.exists() and layers_dir.is_dir()
        image_name = self.repo_tag(reference=reference)
        sort_tool = ImageFileSort(
            image_name=image_name,
            target_dir=layers_dir,
        )
        if options.image_format == ImageFormat.V2:
            sort_tool.to_docker_v2()
            final_path = ImageV2Tar(
                src_dir=layers_dir,
                target_path=image_save_path,
                compress=options.compression,
            ).do()
            return final_path
        elif options.image_format == ImageFormat.OCI:
            sort_tool.to_oci()
            return OCIImageTar(
                src_dir=layers_dir,
                target_path=image_save_path,
                compress=options.compression,
            ).do()
        else:
            raise Exception("invalid image format")

    def _get_manifest(self, resp: httpx.Response, ref: CanonicalReference, platform: Platform = None) -> spec.Manifest:
        if resp.status_code == 404:
            raise ImageNotFoundError(ref)
        resp.raise_for_status()
        media_type = resp.headers.get("Content-Type")
        if media_type == ImageMediaType.MediaTypeDockerSchema2Manifest.value:
            return spec.Manifest(**resp.json())
        elif media_type == ImageMediaType.MediaTypeDockerSchema2ManifestList.value:
            manifest_list = spec.Index(**resp.json())
            digest = filter_by_platform(manifest_list.manifests, target_platform=platform)
            new_ref = CanonicalReference(ref.domain, ref.path, digest=digest)
            resp = self._manifest_client.get(new_ref)
            return self._get_manifest(resp, ref, platform)
        else:
            raise Exception("no match handler")

    def pull(self, ref: Reference, options: ImagePullOptions) -> pathlib.Path:
        if not options.save_dir.exists():
            options.save_dir.mkdir(parents=True)
        tmp_dir = tempfile.TemporaryDirectory(prefix="image_download_")
        temp_dir_path = pathlib.Path(tmp_dir.name)
        temp_dir_path.mkdir(exist_ok=True)
        if isinstance(ref, (DigestReference, CanonicalReference)):
            manifest_digest = ref.digest
        else:
            manifest_content_digest_resp: httpx.Response = self._manifest_client.head(ref)
            if manifest_content_digest_resp.status_code != 200:
                raise ImageNotFoundError(ref)
            manifest_digest = Digest(manifest_content_digest_resp.headers.get("docker-content-digest"))
            if manifest_digest is None:
                manifest_digest = Digest.from_bytes(manifest_content_digest_resp.content)
        r = CanonicalReference(ref.domain, ref.path, digest=manifest_digest)
        manifest_content_resp = self._manifest_client.get(r)
        manifest = self._get_manifest(manifest_content_resp, r, options.platform)
        image_digest_ref = CanonicalReference(ref.domain, ref.path, digest=manifest.config.digest)
        image_config_resp = self.get_image_config(image_digest_ref)
        image_config = spec.Image(**image_config_resp.json())
        assert len(image_config.rootfs.diff_ids) == len(manifest.layers), Exception("Invalid Manifest And ImageConfig")

        with open(temp_dir_path.joinpath("image_config.json"), "wb") as f:
            f.write(image_config_resp.content)

        layer_id_generator = diff_ids_to_chain_ids(image_config.rootfs.diff_ids)

        index = 0
        for layer_id in layer_id_generator:
            layer_path = temp_dir_path.joinpath(Digest(layer_id).hex)
            layer_path.mkdir()
            layer_desc = manifest.layers[index]
            is_gzip = layer_desc.media_type == ImageMediaType.MediaTypeDockerSchema2LayerGzip
            with open(layer_path.joinpath("layer.tar"), "wb") as f:
                with self._blob_client.get(
                    CanonicalReference(
                        image_digest_ref.domain,
                        image_digest_ref.path,
                        digest=layer_desc.digest,
                    ),
                    stream=True,
                ) as resp:
                    if is_gzip and options.image_format != ImageFormat.OCI:  # oci image use gzip layer
                        if resp.headers.get("Content-Encoding") is None:
                            resp.headers["content-encoding"] = "gzip"  # let httpx decode gzip
                    for content in resp.iter_bytes():
                        f.write(content)
            index += 1
        image_path = self._tar_layers(
            ref,
            layers_dir=temp_dir_path,
            options=options,
        )
        return image_path

    @classmethod
    def push(cls, image_path: pathlib.Path, force=False):
        assert image_path.exists() and image_path.is_file()

    def delete(self, ref: CanonicalReference) -> httpx.Response:
        name = ref.path
        target = ref.target
        scope = RepositoryScope(repo_name=name, actions=["delete"])
        resp = self.client.delete(f"/v2/{name}/manifests/{target}", auth=self.client.new_auth(scope))
        return resp

    def exist(self, ref: Reference) -> bool:
        resp = self._manifest_client.head(ref)
        return resp.status_code == 200

    def put_manifest(self):
        pass

    def delete_manifest(self):
        pass

    def get_image_config(self, ref: CanonicalReference):
        resp = self._blob_client.get(ref)
        return resp
