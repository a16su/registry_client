import base64
import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TypeAlias, Union, Dict, List

import requests
from loguru import logger

IMAGE_DEFAULT_TAG: str = "latest"
DEFAULT_REPO: str = "library"
DEFAULT_REGISTRY_HOST: str = "index.docker.io"
DEFAULT_CLIENT_ID = "registry-python-client"

ScopeType: TypeAlias = Union["RegistryScope", "RepositoryScope"]


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
    digest: Digest

    def __post_init__(self):
        self.digest = Digest(self.digest)


@dataclass
class ManifestsResp:
    schemaVersion: int
    mediaType: str
    config: LayerResp
    layers: List[LayerResp]

    def __post_init__(self):
        self.config = LayerResp(**self.config)
        self.layers = [LayerResp(**one) for one in self.layers]

