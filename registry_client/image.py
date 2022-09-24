#!/usr/bin/env python3
# encoding: utf-8
import pathlib
from dataclasses import field, dataclass
from enum import Enum

import requests

from registry_client.digest import Digest
from registry_client.platforms import Platform
from registry_client.reference import TaggedReference
from registry_client.scope import Scope, RepositoryScope, RegistryScope


class ImageFormat(Enum):
    V1 = "v1"
    V2 = "v2"
    OCI = "oci"


@dataclass
class ImagePullOptions:
    image_format: ImageFormat = field(default=ImageFormat.V2)
    platform: Platform = field(default_factory=Platform)
    compression: bool = False


class Layer:

    def __init__(self, digest: Digest, save_dir: pathlib.Path, image: "Image"):
        self.digest = digest
        self.save_dir = save_dir
        self.image = image
        self.client = image.client

    def get_blob(self):
        pass

    def push_blob(self):
        pass


class Image:

    def __init__(self, name: str, reference: TaggedReference, registry: "Registry"):
        self.name = name
        self.reference = reference
        self.registry = registry
        self.client = registry.client

    def _set_auth_header(self, scope: Scope):
        self.client.headers.update(
            self.registry.auth_with_scope(scope).token
        )

    def pull(self, options: ImagePullOptions):
        pass

    @classmethod
    def push(cls, image_path: pathlib.Path):
        assert image_path.exists() and image_path.is_file()

    def get_tags(self) -> requests.Response:
        scope = RepositoryScope(repo_name=self.name, actions=["pull"])
        self._set_auth_header(scope)
        url_path = f"/v2/{self.name}/tags/list"
        url = self.registry.build_url(url_path)
        return self.client._get(url)

    def get_manifest(self):
        pass

    def put_manifest(self):
        pass

    def delete_manifest(self):
        pass
