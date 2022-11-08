#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/27-下午6:40
import sys
from typing import List, Optional, Union

from registry_client.utlis import CustomModel

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

import httpx
from pydantic import Field

from registry_client.auth import AuthClient
from registry_client.digest import Digest
from registry_client.media_types import ImageMediaType, OCIImageMediaType
from registry_client.platforms import Platform
from registry_client.reference import Reference
from registry_client.scope import RepositoryScope


class LayerInfo(CustomModel):
    media_type: Union[ImageMediaType, OCIImageMediaType] = Field(alias="mediaType")
    size: int
    digest: Digest
    platform: Optional[Platform] = Field(default_factory=Platform)


class ManifestIndex(CustomModel):
    schema_version: str = Field(alias="schemaVersion")
    media_type: Union[ImageMediaType, OCIImageMediaType] = Field(alias="mediaType")
    config: LayerInfo
    layers: List[LayerInfo]


class ManifestList(CustomModel):
    manifests: List[LayerInfo]
    schema_version: str = Field(alias="schemaVersion")
    media_type: Union[ImageMediaType, OCIImageMediaType] = Field(alias="mediaType")

    def filter_by_platform(self, platform: Platform) -> Digest:
        if platform is None:
            return self.manifests[0].digest
        for manifest in self.manifests:
            if manifest.platform == platform:
                return manifest.digest
        else:
            raise Exception("Not Found Matching image")


class ManifestClient:
    def __init__(self, client: AuthClient):
        self.client = client
        self.client.headers.update(
            {
                "accept": ", ".join(
                    (
                        ImageMediaType.MediaTypeDockerSchema2Manifest.value,
                        ImageMediaType.MediaTypeDockerSchema2ManifestList.value,
                        OCIImageMediaType.MediaTypeImageManifest.value,
                        OCIImageMediaType.MediaTypeImageIndex.value,
                        "*/*",
                    )
                )
            }
        )

    def _send_request(self, method: Literal["GET", "HEAD"], ref: Reference) -> httpx.Response:
        scope = RepositoryScope(ref.path, actions=["pull"])
        target = ref.target
        url = f"/v2/{ref.path}/manifests/{target}"
        return self.client.request(method, url, auth=self.client.new_auth(auth_by=scope))

    def head(self, ref: Reference) -> httpx.Response:
        return self._send_request("HEAD", ref)

    def get(self, ref: Reference) -> httpx.Response:
        return self._send_request("GET", ref)
