#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/4-下午10:50
import pytest

from registry_client.client import DEFAULT_REGISTRY_HOST


class TestRegistry:
    @pytest.skip("not done")
    def test_catalog(self, docker_registry):
        catalog = docker_registry.get_repositories()
        assert catalog

    @pytest.skip("not done")
    def test_catalog_pagination(self, docker_registry):
        full_catalog = docker_registry.get_repositories()

        n_catalog = docker_registry.get_repositories(count=1)
        assert n_catalog != full_catalog

    @pytest.mark.parametrize(
        "host, username, custom, expect",
        (
                (DEFAULT_REGISTRY_HOST, "", "", f"{DEFAULT_REGISTRY_HOST}-"),
                ("", "", "", f"{DEFAULT_REGISTRY_HOST}-"),
                (DEFAULT_REGISTRY_HOST, "username", "", f"{DEFAULT_REGISTRY_HOST}-username"),
                (DEFAULT_REGISTRY_HOST, "username", "custom", "custom"),
                (DEFAULT_REGISTRY_HOST, "", "custom", "custom"),
                ("", "", "custom", "custom"),
        ),
    )
    def test_name(self, docker_registry_client, host, username, custom, expect):
        registry = docker_registry_client.registry(host=host, username=username, name=custom)
        assert registry.name == expect
