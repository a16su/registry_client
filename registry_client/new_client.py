#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午4:06
from typing import Dict, Optional, Any

import requests
from registry_client.registry import Registry


class RegistryClient(requests.Session):
    def __init__(self, verify=True, proxy: Optional[Dict] = None):
        super(RegistryClient, self).__init__()
        self.verify = verify
        self.proxies = proxy or {}
        self._registries = {}

    def _get(self, url: str, params: Dict[str, Any] = None, **kwargs) -> requests.Response:
        return self.get(url, params=params, **kwargs)

    def _post(self, url: str, body: Dict, **kwargs):
        return self.post(url, json=body, **kwargs)

    def _delete(self, url: str, **kwargs):
        return self.delete(url=url, **kwargs)

    def registry(self, host: str, username: str = "", password: str = "", name: Optional[str] = None) -> Registry:
        reg = Registry(client=self, host=host, username=username, password=password, name=name)
        self._registries[reg.name] = reg
        return reg