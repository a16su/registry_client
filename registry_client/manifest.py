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

from registry_client.auth import AuthClient
from registry_client.media_types import ImageMediaType, OCIImageMediaType
from registry_client.reference import Reference
from registry_client.scope import RepositoryScope


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
