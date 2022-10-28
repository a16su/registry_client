#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/4-下午10:50
import pytest


class TestRegistry:
    @pytest.mark.skipif("not config.option.registry_username")
    def test_catalog(self, repo_client):
        catalog = repo_client.list().json()
        assert catalog

    @pytest.mark.skipif("not config.option.registry_username")
    def test_param_n(self, repo_client):
        n_catalog = repo_client.list(count=1).json().get("repositories")
        assert len(n_catalog) == 1

    @pytest.mark.skipif("not config.option.registry_username")
    def test_param_last(self, repo_client):
        n_catalog = repo_client.list(count=2).json().get("repositories")
        first = repo_client.list(count=1).json().get("repositories")
        second = repo_client.list(count=1, last=first[-1]).json().get("repositories")
        assert first + second == n_catalog
