import base64
import datetime
import hashlib

from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
from enum import Enum
from typing import Optional, Union, Dict, List

from registry_client.digest import Digest
from registry_client.media_types import ImageMediaType
from registry_client.platforms import Platform

IMAGE_DEFAULT_TAG: str = "latest"
DEFAULT_REPO: str = "library"
DEFAULT_REGISTRY_HOST: str = "registry-1.docker.io"
DEFAULT_CLIENT_ID = "registry-python-client"
INDEX_NAME = "docker.io"

BZIP_MAGIC = b"\x42\x5A\x68"
GZIP_MAGIC = b"\x1F\x8B\x8B"
XZ_MAGIC = b"\xFD\x37\x7A\x58\x5A\x00"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def get_chain_id(parent: str, ids: List[str]) -> str:
    if not ids:
        return parent
    if parent == "":
        return get_chain_id(ids[0], ids[1:])
    value = hashlib.sha256(f"{parent} {ids[0]}".encode()).hexdigest()
    value = f"sha256:{value}"
    return get_chain_id(value, ids[1:])


def diff_ids_to_chain_ids(diff_ids: List[str]) -> List[str]:
    assert diff_ids
    result = [diff_ids[0]]
    parent = ""
    for diff_id in diff_ids[1:]:
        result.append(get_chain_id(result[-1], [diff_id]))
    return result


def v1_image_id(layer_id: str, parent: str, v1image: "V1Image" = None) -> str:
    config = {"created": "1970-01-01T08:00:00+08:00", "layer_id": layer_id}
    if parent != "":
        config["parent"] = parent
    return f"sha256:{hashlib.sha256(str(config).encode()).hexdigest()}"


class V1Image(BaseModel):
    id: Optional[str]
    parent: Optional[str]
    comment: Optional[str]
    created: Optional[str]
    container: Optional[str]
    container_config: Optional[str]
    docker_version: Optional[str]
    author: Optional[str]
    config: Optional[str]
    architecture: Optional[str]
    variant: Optional[str]
    os: Optional[str]
    size: Optional[float]


class TokenResp(BaseModel):
    token: str
    expires_in: float
    issued_at: str
    access_token: Optional[str] = ""

    @property
    def registry_token(self) -> str:
        return self.access_token or self.token

    @property
    def expiration(self) -> datetime.datetime:
        issued_at = datetime.datetime.strptime(self.issued_at, "%Y-%m-%dT%H:%M:%SZ")
        return datetime.timedelta(seconds=self.expires_in) + issued_at


@dataclass
class LayerResp:
    mediaType: ImageMediaType
    size: int
    digest: Digest
    platform: Optional[Platform] = None

    def __post_init__(self):
        self.digest = Digest(self.digest)


class ManifestsResp(BaseModel):
    schemaVersion: int
    mediaType: ImageMediaType
    config: LayerResp
    layers: List[LayerResp]

    class Config:
        arbitrary_types_allowed = True


class ManifestsListResp(BaseModel):
    manifests: List[LayerResp]
    mediaType: ImageMediaType
    schemaVersion: str

    def filter(self, target_platform: Platform) -> Digest:
        """sample filter"""
        for manifest in self.manifests:
            if manifest.platform == target_platform:
                target_manifest = manifest
                break
        else:
            raise Exception("Not Found Matching image")
        return target_manifest.digest
