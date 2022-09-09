#!/usr/bin/python3
# encoding: utf-8
from typing import Dict, Optional, Union, Type

import requests
from loguru import logger

from utlis import (
    RegistryScope,
    RepositoryScope,
    IMAGE_DEFAULT_TAG,
    DEFAULT_REPO,
    DEFAULT_REGISTRY_HOST,
    ScopeType,
    PingResp,
    BearerChallengeHandler,
    ChallengeScheme,
    ChallengeHandler,
)

logger.add("./client.log", level="INFO")


class ImageClient:
    def __init__(
            self,
            host: str,
            username: Optional[str] = None,
            password: Optional[str] = None,
            scheme: str = "https",
    ):
        self._host: str = host
        self._username: str = username
        self._password: str = password
        self._schema: str = scheme
        self._base_url = f"{scheme}://{host}"
        self._realm: Optional[str] = None
        self._service: Optional[str] = None

    def ping(self) -> Optional[PingResp]:
        resp = requests.get(f"{self._base_url}/v2/")
        logger.debug(f"{resp.headers=}, {resp.text=}, {resp.status_code=}")
        auth_header = resp.headers.get("WWW-Authenticate", None)
        if auth_header is None:
            return None
        return PingResp(auth_header)

    def auth_header(self, scope: Union[str, RegistryScope, RepositoryScope] = ""):
        ping_resp = self.ping()
        if ping_resp is None:
            return {}
        return self._handle_challenges(ping_resp, scope)

    def _handle_challenges(self, challenge: PingResp, scope: ScopeType) -> Dict:
        scheme_dict: Dict[ChallengeScheme, Type[ChallengeHandler]] = {
            ChallengeScheme.Bearer: BearerChallengeHandler
        }
        handler = scheme_dict.get(challenge.scheme, None)
        if handler is None:
            return {}
        return handler(
            challenge, self._username, self._password, scope
        ).get_auth_header()

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
    from tomlkit import parse

    with open("./registry_info.toml", "r", encoding="utf-8") as f:
        info = parse(f.read())
    c = ImageClient(**info.get("docker-mirror"))
    a = c.head_image_with_tag("python", repo_name="library")
    logger.info(a.headers.get("Etag"))
