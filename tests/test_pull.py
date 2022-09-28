import pathlib
import uuid

import pytest

from registry_client.image import ImagePullOptions
from registry_client.errors import ImageNotFoundError, ImageManifestCheckError


class TestImage:
    def test_pull(self, docker_registry, tmp_path):
        image = docker_registry.image("hello-world")
        option = ImagePullOptions(save_dir=tmp_path, reference="latest")
        image_path = image.pull(option)
        assert image_path.exists() and image_path.is_file()
        image_path.unlink()

    def test_pull_dont_exists_image(self, docker_image):
        image = docker_image(uuid.uuid1().hex[:8])
        with pytest.raises(ImageNotFoundError):
            image.pull(ImagePullOptions(pathlib.Path(".")))

    def test_pull_dont_exists_tag(self, docker_image):
        image = docker_image("hello-world")
        with pytest.raises(ImageNotFoundError):
            image.pull(ImagePullOptions(pathlib.Path("."), reference="error-tag"))

    def test_image_right_tag(self, docker_image):
        image = docker_image("library/hello-world")
        assert image.exist("latest")

    def test_image_error_tag(self, docker_image):
        image = docker_image("library/hello-world")
        assert not image.exist("error-tag")

    def test_get_tags(self, docker_registry, docker_hub_client):
        image_name = "library/hello-world"
        image = docker_registry.image(image_name)
        tags_by_api = image.get_tags()
        tags_by_http = docker_hub_client.list_tags(image_name)
        assert not set(tags_by_api) - set(tags_by_http)

    def test_tags_paginated_last(self, docker_image):
        image = docker_image("library/python")
        tags = image.get_tags(limit=1)
        assert len(tags) == 1
        next_tags = image.get_tags(limit=1, last=tags[-1])
        assert next_tags and next_tags != tags

    def test_get_dont_exists_image_tags(self, docker_image):
        image = docker_image(f"library/hello-world1")
        with pytest.raises(ImageNotFoundError):
            print(image.get_tags())
