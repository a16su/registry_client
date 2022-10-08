#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/4-下午10:50
import pytest

from registry_client.client import DEFAULT_REGISTRY_HOST
from registry_client.scope import EmptyScope, RegistryScope, RepositoryScope
from registry_client.auth import Auther, EmptyToken


class TestRegistry:
    @pytest.mark.skipif("not config.option.registry_username")
    def test_catalog(self, docker_registry):
        catalog = docker_registry.get_repositories()
        assert catalog

    @pytest.mark.skipif("not config.option.registry_username")
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
        another_registry = docker_registry_client.registry(name=expect)
        assert registry.name == expect
        assert not registry != another_registry

    def test_auth_cache_get(self, docker_registry, monkeypatch):
        token = EmptyToken()
        scope = RepositoryScope("library", actions=["pull"])
        monkeypatch.setattr(docker_registry, "_auth_cache", {str(scope): token})
        assert docker_registry.auth_with_scope(scope) is token

    def test_auth_with_scope_empty_token(self, docker_registry, monkeypatch):
        no_need_auther = Auther()
        monkeypatch.setattr(docker_registry, "_auth_config", no_need_auther)
        scope = RepositoryScope("libraray", actions=["*"])
        auth = docker_registry.auth_with_scope(scope)
        assert isinstance(auth, EmptyToken)

    @pytest.mark.parametrize("path", ("path", "/path"))
    def test_build_url(self, docker_registry, path: str):
        get = docker_registry.build_url(path)
        assert get == f"{docker_registry._base_url}/path"
