#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/19-下午6:18
from typing import Dict, Optional

import httpx

from registry_client.auth import AuthClient

HeaderType = Dict[str, str]


class RepoClient:
    def __init__(self, client: AuthClient):
        self.client = client

    def list(self, count: Optional[int] = None, last: Optional[str] = None) -> httpx.Response:
        params = {
            "n": count or "",
        }
        if last:
            params["last"] = str(last)
        resp = self.client.get(url="/v2/_catalog", params=params, auth=(self.client._username, self.client._password))
        return resp
