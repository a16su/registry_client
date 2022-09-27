#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午2:52
from typing import Any


class TaggedReference:
    name: str
    tag: str

    def __str__(self):
        return f"{self.name}:{self.tag}"
