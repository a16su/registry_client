#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/19-下午6:18
import urllib.parse
from typing import List, Optional, Dict

import requests
from loguru import logger

from registry_client.auth import Auther, Token, EmptyToken
from registry_client.image import Image
from registry_client.scope import Scope

HeaderType = Dict[str, str]


class Registry:
    def __init__(
        self, client: "RegistryClient", host: str, username: str = "", password: str = "", name: Optional[str] = None
    ):
        self.name = name or f"{host}-{username}"
        host = urllib.parse.urlparse(host)
        self._scheme = host.scheme
        self._host = host.netloc
        self._username = username
        self._password = password
        self.client = client
        self._auth_config: Optional[Auther] = None
        self._auth_cache: Dict[str, Token] = {}

    @property
    def _base_url(self):
        return f"{self._scheme}://{self._host}"

    def build_url(self, url_path: str):
        if not url_path.startswith("/"):
            url_path = f"/{url_path}"
        return f"{self._base_url}{url_path}"

    @property
    def auth_config(self) -> Optional[Auther]:
        if self._auth_config is None:
            ping_resp = self.ping()
            auth_config_header = ping_resp.headers.get("WWW-Authenticate")
            self._auth_config = Auther(auth_config_header=auth_config_header)
        return self._auth_config

    def ping(self) -> requests.Response:
        url = f"{self._base_url}/v2/"
        resp = self.client._get(url)
        return resp

    def auth_with_scope(self, scope: Scope) -> Token:
        token_exists = self._auth_cache.get(str(scope))
        if token_exists and not token_exists.expired:
            logger.info("use cache")
            return token_exists
        auth_config = self.auth_config
        if not auth_config.need_auth:
            return EmptyToken()
        token = auth_config.auth_with_scope(self._username, self._password, scope)
        self._auth_cache[str(scope)] = token
        return token

    def image(self, repo: str, image: str) -> Image:
        return Image(f"{repo}/{image}", self)

    def get_repositories(self):
        pass

    def pull_image(self):
        pass

    def push_image(self):
        pass

    def list_image(self) -> List[Image]:
        pass
