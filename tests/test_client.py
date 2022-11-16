#!/usr/bin/env python3
# encoding: utf-8
import time
import typing

import httpx
import pytest

from registry_client.client import RegistryClient
from registry_client.image import ImageClient
from registry_client.platforms import OS, Arch, Platform
from registry_client.reference import parse_normalized_named
from registry_client.utlis import DEFAULT_REGISTRY_HOST, DEFAULT_REPO
from tests.test_image import DEFAULT_IMAGE_NAME


class TestRegistryClient:
    @staticmethod
    def _check_pull_image(client: RegistryClient, image_name: str, options: typing.Dict[str, typing.Any]):
        image_path = client.pull_image(image_name=image_name, **options)
        assert image_path.exists() and image_path.is_file()
        save_dir = options.get("save_dir")
        assert image_path.parent == save_dir

    @pytest.mark.parametrize(
        "image_name, options",
        (
            (DEFAULT_IMAGE_NAME, {}),
            (
                DEFAULT_IMAGE_NAME + ":latest",
                {"platform": Platform(os=OS.Linux, architecture=Arch.ARM_64)},
            ),
            (f"{DEFAULT_IMAGE_NAME}:linux", {}),
            (
                f"{DEFAULT_IMAGE_NAME}@sha256:f54a58bc1aac5ea1a25d796ae155dc228b3f0e11d046ae276b39c4bf2f13d8c4",
                {},
            ),
        ),
    )
    def test_pull(self, docker_registry_client, image_save_dir, image_name, options):
        options.update(save_dir=image_save_dir)
        self._check_pull_image(docker_registry_client, image_name=image_name, options=options)

    @pytest.mark.parametrize(
        "params, want",
        (
            ({"image_name": "hello-world:latest"}, AssertionError),
            ({"image_name": f"hello-world@sha256:{'f' * 64}"}, AssertionError),
            ({"image_name": "foo/bar"}, ["latest", "linux"]),
            ({"image_name": "foo/bar", "limit": 1}, ["latest"]),
            ({"image_name": "foo/bar", "last": "latest"}, ["linux"]),
            ({"image_name": "foo/bar", "limit": 1, "last": "latest"}, ["linux"]),
        ),
    )
    def test_list_tags(self, docker_registry_client, registry_tags, params, want):
        if want == AssertionError:
            with pytest.raises(AssertionError):
                docker_registry_client.list_tags(**params)
        else:
            registry_tags.respond(json={"tags": want})
            assert docker_registry_client.list_tags(**params) == want

    def test_list_tags_with_unauthorized(self, docker_registry_client, monkeypatch):
        for code in (401, 404):
            resp = httpx.Response(status_code=code)
            monkeypatch.setattr(ImageClient, "list_tag", lambda *args, **kwargs: resp)
            assert docker_registry_client.list_tags("foo/bar") == []

    @pytest.mark.parametrize(
        "host, image_name, target, want",
        (
            (DEFAULT_REGISTRY_HOST, "foo", "latest", "foo:latest"),
            (DEFAULT_REGISTRY_HOST, f"{DEFAULT_REPO}/foo", "latest", "foo:latest"),
            (
                DEFAULT_REGISTRY_HOST,
                f"{DEFAULT_REPO}1/foo",
                "latest",
                f"{DEFAULT_REPO}1/foo:latest",
            ),
            ("a.com", "foo", "latest", "a.com/foo:latest"),
            ("a.com", "library/foo", "latest", "a.com/library/foo:latest"),
            ("a.com", "a/b/c/d/foo", "latest", "a.com/a/b/c/d/foo:latest"),
            (DEFAULT_REGISTRY_HOST, "foo", "digest1", None),
            (DEFAULT_REGISTRY_HOST, "library/foo", "digest2", None),
            (DEFAULT_REGISTRY_HOST, "a/b/c/foo", "digest3", None),
            ("a.com", "a/b/c/foo", "digest3", None),
        ),
    )
    def test_image_repo_tag(self, docker_registry_client, monkeypatch, random_digest, host, image_name, target, want):
        monkeypatch.setattr(docker_registry_client.client, "base_url", httpx.URL(f"https://{host}"))
        if target.startswith("digest"):
            target = f"@{random_digest.value}"
        else:
            target = f":{target}"
        ref_str = f"{host}/{image_name}{target}"
        ref = parse_normalized_named(ref_str)
        assert docker_registry_client.repo_tag(ref) == want
