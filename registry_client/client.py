#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午4:06
import urllib.parse
from typing import Optional

from loguru import logger

from registry_client.auth import AuthClient
from registry_client.image import ImageClient
from registry_client.reference import Repository
from registry_client.repo import RepoClient
from registry_client.utlis import parse_normalized_named


class RegistryClient:
    def __init__(self, host="https://registry-1.docker.io", username: str = "", password: str = "", skip_verify=False):
        self._username = username
        self._password = password
        self.client = AuthClient(base_url=host, auth=(username, password), verify=not skip_verify)
        domain = urllib.parse.urlparse(host).netloc
        self._repo_info = Repository(domain, path="")
        self._registry_client = RepoClient(self.client)

    def catalog(self, count: int = None, last: str = None):
        resp = self._registry_client.list(count, last)
        resp.raise_for_status()
        return resp.json().get("repositories", [])

    def list_tags(self, image_name: str, limit: Optional[int] = None, last: Optional[str] = None):
        ref = parse_normalized_named(image_name)
        assert ref.is_named_only, Exception("No tag or digest allowed in reference")
        resp = ImageClient(self.client).list_tag(ref.repository, limit, last)
        if resp.status_code in [401, 404]:  # docker hub status_code is 401, harbor is 404, registry mirror is 200
            logger.warning("image may be dont exist, return empty list")
            return []
        resp.raise_for_status()
        tags = resp.json().get("tags", None)
        return tags if tags is not None else []
