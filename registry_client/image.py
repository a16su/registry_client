#!/usr/bin/env python3
# encoding: utf-8
from dataclasses import field, dataclass
from enum import Enum

from registry_client.platforms import Platform


class Reference:
    pass


class TagReference(Reference):
    pass


class Digest(Reference):
    pass


class ImageFormat(Enum):
    V1 = "v1"
    V2 = "v2"
    OCI = "oci"


@dataclass
class ImagePullOptions:
    repo: str
    name: str
    reference: Reference
    image_format: ImageFormat = field(default=ImageFormat.V2)
    platform: Platform = field(default_factory=Platform)
    compression: bool = False


class Layer:
    def get_blob(self):
        pass

    def push_blob(self):
        pass


class Image:

    def pull(self):
        pass

    def push(self):
        pass

    def get_tags(self):
        pass

    def get_manifest(self):
        pass

    def put_manifest(self):
        pass

    def delete_manifest(self):
        pass


