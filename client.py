#!/usr/bin/python3
# encoding: utf-8
import base64
from dataclasses import dataclass
import datetime
from typing import Dict, Optional, Tuple, Union, TypeAlias

import requests
from loguru import logger

from utlis import RegistryScope, RepositoryScope, IMAGE_DEFAULT_TAG, DEFAULT_REPO

logger.add("./client.log", level="INFO")
ScopeType: TypeAlias = Union[RegistryScope, RepositoryScope]


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


class ImageClient:
    def __init__(self, host: str, username: str, password: str, schema: str = "https"):
        self._host: str = host
        self._username: str = username
        self._password: str = password
        self._schema: str = schema
        self._base_url = f"{schema}://{host}"
        self._realm: Optional[str] = None
        self._service: Optional[str] = None
        self._basic_auth = self._encode_basic_auth()

    def __post_init__(self):
        self._base_url = f"{self._schema}://{self._host}"

    def _parse_ping_resp(self, resp: requests.Response) -> Tuple[str, Dict]:
        logger.debug(
            f"{resp.headers=}, {resp.text=}, {resp.status_code=}"
        )
        auth_header = resp.headers.get("WWW-Authenticate", None)
        if auth_header is None:
            raise Exception(f"Get Auth Server Error: {resp.headers}")
        scheme, params = auth_header.split(" ")
        param_dict = dict(param.split("=") for param in params.split(","))
        return scheme, param_dict

    def ping(self) -> Tuple[str, Dict]:
        resp = requests.get(f"{self._base_url}/v2/")
        return self._parse_ping_resp(resp)

    def _encode_basic_auth(self):
        base_str = f"{self._username}:{self._password}"
        return base64.b64encode(base_str.encode()).decode()

    def auth_header(self, scope: Union[str, RegistryScope, RepositoryScope] = ""):
        token = self.get_token(scope=scope)
        return {"Authorization": f"Bearer {token.registry_token}"}

    def get_token(
        self, scope: Union[str, RegistryScope, RepositoryScope] = ""
    ) -> TokenResp:
        if self._realm is None:
            _, param = self.ping()
            self._realm = param["realm"].strip('"')
            self._service = param["service"].strip('"')

        params = {
            "scope": str(scope),
            "service": self._service,
            "client_id": "registry-client",
            "account": self._username,
        }
        headers = {"Authorization": f"Basic {self._basic_auth}"}
        resp = requests.get(self._realm, params=params, verify=False, headers=headers)
        logger.debug(f"{resp.text=}, {resp.headers=} {resp.status_code=}")
        return TokenResp(**resp.json())

    def _request(
        self, suffix: str, scope: ScopeType, method: str, **kwargs
    ) -> requests.Response:
        if not suffix.startswith("/"):
            suffix = f"/{suffix}"
        url = f"{self._base_url}{suffix}"
        headers = self.auth_header(scope)
        headers_in_param = kwargs.get("headers", None)
        if headers_in_param is not None:
            headers.update(headers_in_param)
        logger.debug(f"{suffix=}, {scope=}, {method=}, {kwargs=}, {headers=}")
        return requests.request(method=method, url=url, headers=headers, **kwargs)

    def list_registry(self) -> Dict:
        suffix = "/v2/_catalog"
        scope = RegistryScope("catalog", ["*"])
        return self._request(suffix=suffix, scope=scope, method="GET").json()

    def head_image_with_tag(
        self,
        image_name: str,
        repo_name: str = DEFAULT_REPO,
        tag: str = IMAGE_DEFAULT_TAG,
    ):
        suffix = f"/v2/{repo_name}/{image_name}/manifests/{tag}"
        scope = RepositoryScope(f"{repo_name}/{image_name}", ["pull"])
        return self._request(suffix=suffix, scope=scope, method="HEAD")


if __name__ == "__main__":
    harbor_ip = ""
    username = ""
    password = ""

    c = ImageClient(harbor_ip, username, password, "http")
    a = c.head_image_with_tag("image_name", repo_name="library", tag="latest")
    logger.info(a.headers.get("Etag"))
