#!/usr/bin/env python3
# encoding: utf-8
import pathlib
import sys
from enum import Enum
from typing import Dict, Iterable, List, Optional, Union

from registry_client import spec
from registry_client.media_types import ImageMediaType

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

import httpx

from registry_client.auth import AuthClient
from registry_client.digest import Digest
from registry_client.errors import ImageNotFoundError
from registry_client.manifest import ManifestClient
from registry_client.platforms import Platform, filter_by_platform
from registry_client.reference import (
    CanonicalReference,
    DigestReference,
    NamedReference,
    Reference,
)
from registry_client.scope import RepositoryScope

MAX_MANIFEST_SIZE = 4 * 1048 * 1048


class ImageFormat(Enum):
    V1 = "v1"
    V2 = "v2"
    OCI = "oci"


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

    def get_manifest_digest(self, ref: Reference) -> Digest:
        if isinstance(ref, (DigestReference, CanonicalReference)):
            return ref.digest
        manifest_content_digest_resp = self._manifest_client.head(ref)
        if manifest_content_digest_resp.status_code != 200:
            raise ImageNotFoundError(ref)
        manifest_digest_in_header = manifest_content_digest_resp.headers.get("docker-content-digest")
        if manifest_digest_in_header is None:
            return Digest.from_bytes(manifest_content_digest_resp.content)
        return Digest(manifest_digest_in_header)

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

    def get_manifest(self, ref: CanonicalReference) -> httpx.Response:
        return self._manifest_client.get(ref)

    def put_manifest(self):
        pass

    def delete_manifest(self):
        pass

    def get_config(self, ref: CanonicalReference) -> httpx.Response:
        return self._blob_client.get(ref)

    def _handle_manifest(
        self, resp: httpx.Response, ref: CanonicalReference, platform: Platform = None
    ) -> spec.Manifest:
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
            return self._handle_manifest(resp, ref, platform)
        else:
            raise Exception("no match handler")
