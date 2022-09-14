import base64
import datetime
import hashlib
import platform
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union, Dict, List

import requests
from loguru import logger

IMAGE_DEFAULT_TAG: str = "latest"
DEFAULT_REPO: str = "library"
DEFAULT_REGISTRY_HOST: str = "registry.docker.io"
DEFAULT_CLIENT_ID = "registry-python-client"
DEFAULT_SYSTEM = platform.system()
DEFAULT_MACHINE = platform.machine()


ScopeType = Union["RegistryScope", "RepositoryScope"]

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
    config = {
        "created": "1970-01-01T08:00:00+08:00",
        "layer_id": layer_id
    }
    if parent != "":
        config["parent"] = parent
    return f"sha256:{hashlib.sha256(str(config).encode()).hexdigest()}"


class System(Enum):
    Windows = "Windows"
    Linux = "Linux"
    Mac = "Darwin"


class Machine(Enum):
    INTEL_386 = "386"
    ARM = "ARM"
    AMD_64 = "AMD64"
    MIPS_64le = "MIPS64LE"
    ARM_64 = "ARM64"
    S390X = "S390X"
    PPC_64LE = "PPC64LE"
    RISCV_64 = "RISCV64"


@dataclass
class Platform:
    os_name: System = System(DEFAULT_SYSTEM)
    arch: Machine = Machine(DEFAULT_MACHINE)


@dataclass
class V1Image:
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


@dataclass
class RepositoryScope:
    repo_name: str
    actions: list[str]
    class_name: str = ""

    def __str__(self) -> str:
        repo_type = "repository"
        if self.class_name != "" and self.class_name != "image":
            repo_type = f"{repo_type}({self.class_name})"
        return f"{repo_type}:{self.repo_name}:{','.join(self.actions)}"


@dataclass
class RegistryScope:
    rs_name: str
    actions: list[str]

    def __str__(self) -> str:
        return f"registry:{self.rs_name}:{','.join(self.actions)}"


@dataclass
class TokenResp:
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


class ChallengeScheme(Enum):
    Bearer = "Bearer"
    Basic = "Basic"


class PingResp:
    def __init__(self, headers: str):
        scheme, params = headers.split(" ")
        param_dict = dict(param.split("=") for param in params.split(","))
        self.scheme = ChallengeScheme(scheme)
        self.realm = param_dict.get("realm").strip('"')
        self.service = param_dict.get("service").strip('"')

    def __str__(self):
        return f"{self.scheme=}, {self.realm=}, {self.service=}"


@dataclass
class ChallengeHandler:
    ping_resp: PingResp
    username: str
    password: str
    scope: ScopeType
    client_id: str = DEFAULT_CLIENT_ID
    scheme: ChallengeScheme = field(init=False)

    def __post_init__(self):
        assert self.ping_resp.scheme == self.scheme

    def get_auth_header(self) -> Dict[str, str]:
        raise NotImplementedError


@dataclass
class BearerChallengeHandler(ChallengeHandler):
    scheme = ChallengeScheme.Bearer

    def _encode_basic_auth(self):
        base_str = f"{self.username}:{self.password}"
        return base64.b64encode(base_str.encode()).decode()

    def get_auth_header(self):
        params = {
            "scope": str(self.scope),
            "service": self.ping_resp.service,
            "client_id": self.client_id,
            "account": self.username,
        }
        if "docker.io" in self.ping_resp.realm:
            headers = None
        else:
            headers = {"Authorization": f"Basic {self._encode_basic_auth()}"}
        resp = requests.get(
            self.ping_resp.realm, params=params, verify=False, headers=headers
        )
        logger.debug(f"{resp.text=}, {resp.headers=} {resp.status_code=}")
        token_resp = TokenResp(**resp.json())
        return {"Authorization": f"Bearer {token_resp.registry_token}"}


class Digest:
    def __init__(self, value: str):
        self.scheme, self.value = value.split(":")

    def __str__(self):
        return f"{self.scheme}:{self.value}"


@dataclass
class LayerResp:
    mediaType: str
    size: int
    digest: str


@dataclass
class ManifestsResp:
    schemaVersion: int
    mediaType: str
    config: LayerResp
    layers: List[LayerResp]

    def __post_init__(self):
        self.config = LayerResp(**self.config)
        self.layers = [LayerResp(**one) for one in self.layers]
