#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/28-下午5:58
import requests


class DockerHubClient:
    def __init__(self):
        self.host = "https://hub.docker.com"

    def list_tags(self, image, page_size: int = 10, page: int = 1, name: str = None):
        if "/" not in image:
            image = f"library/{image}"
        uri = f"/v2/repositories/{image}/tags/"
        params = {"page_size": page_size, "page": page}
        if name:
            params["name"] = name
        resp = requests.get(f"{self.host}{uri}", params=params)
        return [one["name"] for one in resp.json()["results"]]

    def login(self):
        # TODO
        pass


if __name__ == "__main__":
    client = DockerHubClient()
    print(client.list_tags("hello-world"))
