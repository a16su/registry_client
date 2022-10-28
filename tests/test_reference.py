#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/28-下午7:57
import pytest

from registry_client.digest import Digest
from registry_client.reference import (
    DigestReference,
    Reference,
    Repository,
    TagReference,
)
from registry_client.utlis import parse_normalized_named


@pytest.mark.parametrize(
    "name, want",
    (
        ("hello-world", Reference(repository=Repository("registry-1.docker.io", path="library/hello-world"))),
        ("repo/hello-world", Reference(repository=Repository("registry-1.docker.io", path="repo/hello-world"))),
        ("a.com/repo/hello-world", Reference(repository=Repository("a.com", path="repo/hello-world"))),
        ("a.com:8080/repo/hello-world", Reference(repository=Repository("a.com:8080", path="repo/hello-world"))),
        ("19.1.41.1/repo/hello-world", Reference(repository=Repository("19.1.41.1", path="repo/hello-world"))),
        (
            "19.1.41.1:8080/repo/hello-world",
            Reference(repository=Repository("19.1.41.1:8080", path="repo/hello-world")),
        ),
        (
            "19.1.41.1/repo/hello-world:latest",
            TagReference(repository=Repository("19.1.41.1", path="repo/hello-world"), tag="latest"),
        ),
        (
            f"registry-1.docker.io/repo/hello-world@sha256:f54a58bc1aac5ea1a25d796ae155dc228b3f0e11d046ae276b39c4bf2f13d8c4",
            DigestReference(
                repository=Repository("registry-1.docker.io", path="repo/hello-world"),
                digest=Digest(f"sha256:f54a58bc1aac5ea1a25d796ae155dc228b3f0e11d046ae276b39c4bf2f13d8c4"),
            ),
        ),
    ),
)
def test_parse_normalized_named(name: str, want):
    ref = parse_normalized_named(name)
    assert type(ref) == type(want)
    assert ref.repository.name() == want.repository.name()
    if isinstance(want, (TagReference, DigestReference)):
        assert str(ref) == str(want)
