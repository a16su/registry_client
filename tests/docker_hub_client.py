#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/28-下午5:58
from typing import Optional
import requests


class DockerHubClient:
    def __init__(self, username: str = "", password: str = ""):
        self.host = "https://hub.docker.com"
        self.username = username
        self.password = password
        self.client = requests.Session()
        self._token = None

    def list_tags(self, image, page_size: int = 10, page: int = 1, name: Optional[str] = None):
        if "/" not in image:
            image = f"library/{image}"
        uri = f"/v2/repositories/{image}/tags/"
        params = {"page_size": page_size, "page": page}
        if name:
            params["name"] = name
        resp = self.client.get(f"{self.host}{uri}", params=params)
        return [one["name"] for one in resp.json()["results"]]

    def list_repository(self, username, page_size: int = 10):
        url = f"{self.host}/repositories/library"
        params = {"page_size": page_size}
        return self.client.get(url).text

    def login(self):
        url = f"{self.host}/v2/users/login/"
        body = {"username": self.username, "password": self.password}
        resp = self.client.post(url, data=body)
        resp.raise_for_status()
        self.client.headers["Authorization"] = f"JWT {resp.json()['token']}"

    def users(self):
        return self.client.get(f"{self.host}/v2/user/").json()
