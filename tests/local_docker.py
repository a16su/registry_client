#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/5-下午5:36
import pathlib
from typing import Optional

import docker
from docker.models.images import Image

from registry_client.digest import Digest
from registry_client.platforms import Platform


class LocalDockerChecker:
    def __init__(self):
        self.client = docker.from_env()
        self.client.images.list()
        self.image: Image = None

    def check_load(self, image_path: pathlib.Path) -> "LocalDockerChecker":
        with image_path.open("rb") as f:
            images = self.client.images.load(f)
            self.image = images[0]
            return self

    def check_exists(self, image_name: str):
        pass

    def check_platform(self, platform: Platform) -> "LocalDockerChecker":
        attr = self.image.attrs
        assert attr["Architecture"] == platform.architecture.value and attr["Os"] == platform.os.value
        return self

    def check_tag(self, tag_name: Optional[str] = None) -> "LocalDockerChecker":
        if tag_name is None:
            assert self.image.tags == []
            return self
        tags = self.image.tags
        assert tag_name in tags
        return self

    def check_id(self, digest: Digest) -> "LocalDockerChecker":
        assert self.image.id == digest.value
        return self
