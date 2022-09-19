#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/19-下午6:18
from typing import List

from registry_client.image import Image


class Registry:
    def get_repositories(self):
        pass

    def pull_image(self):
        pass

    def push_image(self):
        pass

    def list_image(self) -> List[Image]:
        pass
