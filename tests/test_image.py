import pathlib
import uuid
from typing import Any, Dict

import pytest

from registry_client.errors import ImageNotFoundError
from registry_client.image import Image, ImagePullOptions
from registry_client.platforms import OS, Arch, Platform
from tests.local_docker import LocalDockerChecker

DEFAULT_IMAGE_NAME = "library/hello-world"


class TestImage:
    @staticmethod
    def _check_pull_image(checker: LocalDockerChecker, image: Image, options: ImagePullOptions):
        image_path = image.pull(options)
        assert image_path.exists() and image_path.is_file()
        save_dir = options.save_dir
        assert image_path.parent == save_dir
        checker.check_load(image_path).check_tag(image.repo_tag(options.reference)).check_platform(options.platform)

    @pytest.mark.parametrize(
        "image_name, options",
        (
            (DEFAULT_IMAGE_NAME, {}),
            pytest.param(
                DEFAULT_IMAGE_NAME,
                {"platform": Platform(os=OS.Linux, architecture=Arch.ARM_64)},
                marks=pytest.mark.skip,
            ),
            (DEFAULT_IMAGE_NAME, {"reference": "linux"}),
            (
                DEFAULT_IMAGE_NAME,
                {"reference": "sha256:f54a58bc1aac5ea1a25d796ae155dc228b3f0e11d046ae276b39c4bf2f13d8c4"},
            ),
        ),
    )
    def test_pull(self, docker_image, image_save_dir, image_name, options: Dict[str, Any], image_checker):
        options.update(save_dir=image_save_dir)
        pull_options = ImagePullOptions(**options)
        image = docker_image(image_name)
        self._check_pull_image(image_checker, image, pull_options)

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

    @pytest.mark.parametrize(
        ("registry_name", "name", "result"),
        (
            ("docker-official", "library/hello-world", True),
            ("docker-official", "hello-world", True),
            ("docker-official", "hello-wold", False),
            ("docker-official", "1ibrary/hello-wo-rld", False),
            ("docker-officia", "hello-world", False),
            ("docker-officia", "library/hello-world", False),
            ("docker-officia", "librar-y/hello-wo-rld", False),
        ),
    )
    def test_eq(self, docker_registry_client, registry_name: str, name: str, result: bool):
        default_registry = docker_registry_client.registry(name="docker-official")
        default_image = default_registry.image("library/hello-world")
        new_registry = docker_registry_client.registry(name=registry_name)
        new_image = new_registry.image(name)
        assert (default_image == new_image) == result
