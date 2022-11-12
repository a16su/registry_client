#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/4-下午10:50
import pytest

DEFAULT_RESPONSE_DATA = [
    "repo1/image1",
    "repo2/image2",
    "repo3/image3",
]


class TestRegistry:
    @pytest.mark.parametrize(
        "params, want",
        (
            ({}, DEFAULT_RESPONSE_DATA),
            ({"count": 1}, DEFAULT_RESPONSE_DATA[:1]),
            ({"count": 1, "last": DEFAULT_RESPONSE_DATA[1]}, DEFAULT_RESPONSE_DATA[1:]),
            ({}, []),
            ({"count": 1}, []),
            ({"count": 1, "last": "asda"}, []),
            # ({}, Exception),
            # ({"count": 1}, Exception),
            # ({"count": 2, "last": "test"}, Exception),
        ),
    )
    def test_catalog(self, repo_client, registry_catalog, params, want):
        if want is Exception:
            registry_catalog.respond(status_code=500)
        else:
            data = {"repositories": want}
            registry_catalog.respond(200, json=data)
        catalog = repo_client.list(**params).json()
        assert catalog.get("repositories") == want
