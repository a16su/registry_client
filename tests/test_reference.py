#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/28-下午7:57
import re
from typing import Dict, List, Optional

import pytest

from registry_client import errors, reference
from registry_client.reference import NamedReference, TaggedReference


def check_regexp(reg, value: str, match: bool, result: Optional[List[str]] = None):
    match_results = reg.findall(value)
    if match and match_results:
        if result:
            match_results = match_results[0]
            assert len(match_results) == len(result)
            for index, v in enumerate(result):
                assert match_results[index] == v
    elif match:
        raise Exception(f"Expected match for {value}")
    elif result:
        raise Exception(f"Unexpected match for {value}")


@pytest.mark.parametrize(
    "value, match",
    (
        (
            ("test.com", True),
            ("test.com:10304", True),
            ("test.com:http", False),
            ("localhost", True),
            ("localhost:8080", True),
            ("a", True),
            ("a.b", True),
            ("ab.cd.com", True),
            ("a-b.com", True),
            ("-ab.com", False),
            ("ab-.com", False),
            ("ab.c-om", True),
            ("ab.-com", False),
            ("ab.com-", False),
            ("0101.com", True),
            ("001a.com", True),
            ("b.gbc.io:443", True),
            ("b.gbc.io", True),
            ("xn--n3h.com", True),
            ("Asdf.com", True),
            ("192.168.1.1:75050", True),
            ("192.168.1.1:750050", True),
            ("[fd00:1:2::3]:75050", True),
            ("[fd00:1:2::3]75050", False),
            ("[fd00:1:2::3]::75050", False),
            ("[fd00:1:2::3%eth0]:75050", False),
            ("[fd00123123123]:75050", True),
            ("[2001:0db8:85a3:0000:0000:8a2e:0370:7334]:75050", True),
            ("[2001:0db8:85a3:0000:0000:8a2e:0370:7334]:750505", True),
            ("fd00:1:2::3:75050", False),
        )
    ),
)
def test_domain_regexp(value: str, match: bool):
    reg = re.compile(f"^{reference.DOMAIN_REGEXP.pattern}$")
    check_regexp(reg, value, match)


@pytest.mark.parametrize(
    "value, match, result",
    (
        ("", False, []),
        ("short", True, ["", "short"]),
        ("simple/name", True, ["simple", "name"]),
        ("library/ubuntu", True, ["library", "ubuntu"]),
        ("docker/stevvooe/app", True, ["docker", "stevvooe/app"]),
        (
            "aa/aa/aa/aa/aa/aa/aa/aa/aa/bb/bb/bb/bb/bb/bb",
            True,
            ["aa", "aa/aa/aa/aa/aa/aa/aa/aa/bb/bb/bb/bb/bb/bb"],
        ),
        ("aa/aa/bb/bb/bb", True, ["aa", "aa/bb/bb/bb"]),
        ("a/a/a/a", True, ["a", "a/a/a"]),
        ("a/a/a/a/", False, []),
        ("a//a/a", False, []),
        ("a", True, ["", "a"]),
        ("a/aa", True, ["a", "aa"]),
        ("a/aa/a", True, ["a", "aa/a"]),
        ("foo.com", True, ["", "foo.com"]),
        ("foo.com/", False, []),
        ("foo.com:8080/bar", True, ["foo.com:8080", "bar"]),
        ("foo.com:http/bar", False, []),
        ("foo.com/bar", True, ["foo.com", "bar"]),
        ("foo.com/bar/baz", True, ["foo.com", "bar/baz"]),
        ("localhost:8080/bar", True, ["localhost:8080", "bar"]),
        ("sub-dom1.foo.com/bar/baz/quux", True, ["sub-dom1.foo.com", "bar/baz/quux"]),
        ("blog.foo.com/bar/baz", True, ["blog.foo.com", "bar/baz"]),
        ("a^a", False, []),
        ("aa/asdf$$^/aa", False, []),
        ("asdf$$^/aa", False, []),
        ("aa-a/a", True, ["aa-a", "a"]),
        ("/".join("a" * 129), True, ["a", "/".join("a" * 128)]),
        ("a-/a/a/a", False, []),
        ("foo.com/a-/a/a", False, []),
        ("-foo/bar", False, []),
        ("foo/bar-", False, []),
        ("foo-/bar", False, []),
        ("foo/-bar", False, []),
        ("_foo/bar", False, []),
        ("foo_bar", True, ["", "foo_bar"]),
        ("foo_bar.com", True, ["", "foo_bar.com"]),
        ("foo_bar.com:8080", False, []),
        ("foo_bar.com:8080/app", False, []),
        ("foo.com/foo_bar", True, ["foo.com", "foo_bar"]),
        ("____/____", False, []),
        ("_docker/_docker", False, []),
        ("docker_/docker_", False, []),
        (
            "b.gcr.io/test.example.com/my-app",
            True,
            ["b.gcr.io", "test.example.com/my-app"],
        ),
        ("xn--n3h.com/myimage", True, ["xn--n3h.com", "myimage"]),
        ("xn--7o8h.com/myimage", True, ["xn--7o8h.com", "myimage"]),
        (
            "example.com/xn--7o8h.com/myimage",
            True,
            ["example.com", "xn--7o8h.com/myimage"],
        ),
        (
            "example.com/some_separator__underscore/myimage",
            True,
            ["example.com", "some_separator__underscore/myimage"],
        ),
        ("example.com/__underscore/myimage", False, []),
        ("example.com/..dots/myimage", False, []),
        ("example.com/.dots/myimage", False, []),
        ("example.com/nodouble..dots/myimage", False, []),
        ("example.com/nodouble..dots/myimage", False, []),
        ("docker./docker", False, []),
        (".docker/docker", False, []),
        ("docker-/docker", False, []),
        ("-docker/docker", False, []),
        ("do..cker/docker", False, []),
        ("do__cker:8080/docker", False, []),
        ("do__cker/docker", True, ["", "do__cker/docker"]),
        (
            "b.gcr.io/test.example.com/my-app",
            True,
            ["b.gcr.io", "test.example.com/my-app"],
        ),
        (
            "registry.io/foo/project--id.module--name.ver---sion--name",
            True,
            ["registry.io", "foo/project--id.module--name.ver---sion--name"],
        ),
        ("Asdf.com/foo/bar", True, []),
        ("Foo/FarB", False, []),
    ),
)
def test_full_name_regexp(value, match, result):
    check_regexp(reference.ANCHORED_NAME_REGEXP, value, match, result)


@pytest.mark.parametrize(
    "value, match, result",
    (
        ("registry.com:8080/myapp:tag", True, ["registry.com:8080/myapp", "tag", ""]),
        (
            "registry.com:8080/myapp@sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            True,
            [
                "registry.com:8080/myapp",
                "",
                "sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            ],
        ),
        (
            "registry.com:8080/myapp:tag2@sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            True,
            [
                "registry.com:8080/myapp",
                "tag2",
                "sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            ],
        ),
        ("registry.com:8080/myapp@sha256:badbadbadbad", False, []),
        ("registry.com:8080/myapp:invalid~tag", False, []),
        ("bad_hostname.com:8080/myapp:tag", False, []),
        (
            "localhost:8080@sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            True,
            [
                "localhost",
                "8080",
                "sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            ],
        ),
        (
            "localhost:8080/name@sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            True,
            [
                "localhost:8080/name",
                "",
                "sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            ],
        ),
        (
            "localhost:http/name@sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            False,
            [],
        ),
        (
            "localhost@sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            True,
            [
                "localhost",
                "",
                "sha256:be178c0543eb17f5f3043021c9e5fcf30285e557a4fc309cce97ff9ca6182912",
            ],
        ),
        ("registry.com:8080/myapp@bad", False, []),
        ("registry.com:8080/myapp@2bad", False, []),
    ),
)
def test_reference_regexp(value, match, result):
    check_regexp(reference.REFERENCE_REGEXP, value, match, result)


@pytest.mark.parametrize(
    "value, match, result",
    (
        ("da304e823d8ca2b9d863a3c897baeb852ba21ea9a9f1414736394ae7fcaf9821", True, []),
        ("7EC43B381E5AEFE6E04EFB0B3F0693FF2A4A50652D64AEC573905F2DB5889A1C", False, []),
        ("da304e823d8ca2b9d863a3c897baeb852ba21ea9a9f1414736394ae7fcaf", False, []),
        (
            "sha256:da304e823d8ca2b9d863a3c897baeb852ba21ea9a9f1414736394ae7fcaf9821",
            False,
            [],
        ),
        (
            "da304e823d8ca2b9d863a3c897baeb852ba21ea9a9f1414736394ae7fcaf98218482",
            False,
            [],
        ),
    ),
)
def test_identifier_regexp(value, match, result):
    check_regexp(reference.ANCHORED_IDENTIFIER_REGEXP, value, match, result)


@pytest.mark.parametrize(
    "value, match, result",
    (
        ("da304e823d8ca2b9d863a3c897baeb852ba21ea9a9f1414736394ae7fcaf9821", True, []),
        ("7EC43B381E5AEFE6E04EFB0B3F0693FF2A4A50652D64AEC573905F2DB5889A1C", False, []),
        ("da304e823d8ca2b9d863a3c897baeb852ba21ea9a9f1414736394ae7fcaf", True, []),
        (
            "sha256:da304e823d8ca2b9d863a3c897baeb852ba21ea9a9f1414736394ae7fcaf9821",
            False,
            [],
        ),
        (
            "da304e823d8ca2b9d863a3c897baeb852ba21ea9a9f1414736394ae7fcaf98218482",
            False,
            [],
        ),
        ("da304", False, []),
        ("da304e", True, []),
    ),
)
def test_short_identifier_regexp(value, match, result):
    check_regexp(reference.ANCHORED_SHORT_IDENTIFIER_REGEXP, value, match, result)


@pytest.mark.parametrize(
    "testcase",
    (
        {
            "input": "test_com",
            "repository": "test_com",
        },
        {
            "input": "test.com:tag",
            "repository": "test.com",
            "tag": "tag",
        },
        {
            "input": "test.com:5000",
            "repository": "test.com",
            "tag": "5000",
        },
        {
            "input": "test.com/repo:tag",
            "domain": "test.com",
            "repository": "test.com/repo",
            "tag": "tag",
        },
        {
            "input": "test:5000/repo",
            "domain": "test:5000",
            "repository": "test:5000/repo",
        },
        {
            "input": "test:5000/repo:tag",
            "domain": "test:5000",
            "repository": "test:5000/repo",
            "tag": "tag",
        },
        {
            "input": "test:5000/repo@sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "domain": "test:5000",
            "repository": "test:5000/repo",
            "digest": "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        },
        {
            "input": "test:5000/repo:tag@sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "domain": "test:5000",
            "repository": "test:5000/repo",
            "tag": "tag",
            "digest": "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        },
        {
            "input": "test:5000/repo",
            "domain": "test:5000",
            "repository": "test:5000/repo",
        },
        {
            "input": "",
            "err": errors.ErrNameEmpty,
        },
        {
            "input": ":justtag",
            "err": errors.ErrReferenceInvalidFormat,
        },
        {
            "input": "@sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "err": errors.ErrReferenceInvalidFormat,
        },
        {
            "input": "repo@sha256:ffffffffffffffffffffffffffffffffff",
            "err": errors.ErrDigestInvalidLength,
        },
        {
            "input": "validname@invaliddigest:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "err": errors.ErrDigestUnsupported,
        },
        {
            "input": "Uppercase:tag",
            "err": errors.ErrNameContainsUppercase,
        },
        {
            "input": "test:5000/Uppercase/lowercase:tag",
            "err": errors.ErrNameContainsUppercase,
        },
        {
            "input": "lowercase:Uppercase",
            "repository": "lowercase",
            "tag": "Uppercase",
        },
        {
            "input": "a/" * 128 + "a:tag",
            "err": errors.ErrNameTooLong,
        },
        {
            "input": "a/" * 127 + "a:tag-puts-this-over-max",
            "domain": "a",
            "repository": "a/" * 127 + "a",
            "tag": "tag-puts-this-over-max",
        },
        {
            "input": "aa/asdf$$^/aa",
            "err": errors.ErrReferenceInvalidFormat,
        },
        {
            "input": "sub-dom1.foo.com/bar/baz/quux",
            "domain": "sub-dom1.foo.com",
            "repository": "sub-dom1.foo.com/bar/baz/quux",
        },
        {
            "input": "sub-dom1.foo.com/bar/baz/quux:some-long-tag",
            "domain": "sub-dom1.foo.com",
            "repository": "sub-dom1.foo.com/bar/baz/quux",
            "tag": "some-long-tag",
        },
        {
            "input": "b.gcr.io/test.example.com/my-app:test.example.com",
            "domain": "b.gcr.io",
            "repository": "b.gcr.io/test.example.com/my-app",
            "tag": "test.example.com",
        },
        {
            "input": "xn--n3h.com/myimage:xn--n3h.com",
            "domain": "xn--n3h.com",
            "repository": "xn--n3h.com/myimage",
            "tag": "xn--n3h.com",
        },
        {
            "input": f"xn--7o8h.com/myimage:xn--7o8h.com@sha512:{'f' * 128}",
            "domain": "xn--7o8h.com",
            "repository": "xn--7o8h.com/myimage",
            "tag": "xn--7o8h.com",
            "digest": f"sha512:{'f' * 128}",
        },
        {
            "input": "foo_bar.com:8080",
            "repository": "foo_bar.com",
            "tag": "8080",
        },
        {
            "input": "foo/foo_bar.com:8080",
            "domain": "foo",
            "repository": "foo/foo_bar.com",
            "tag": "8080",
        },
        {
            "input": "192.168.1.1",
            "repository": "192.168.1.1",
        },
        {
            "input": "192.168.1.1:tag",
            "repository": "192.168.1.1",
            "tag": "tag",
        },
        {
            "input": "192.168.1.1:5000",
            "repository": "192.168.1.1",
            "tag": "5000",
        },
        {
            "input": "192.168.1.1/repo",
            "domain": "192.168.1.1",
            "repository": "192.168.1.1/repo",
        },
        {
            "input": "192.168.1.1:5000/repo",
            "domain": "192.168.1.1:5000",
            "repository": "192.168.1.1:5000/repo",
        },
        {
            "input": "192.168.1.1:5000/repo:5050",
            "domain": "192.168.1.1:5000",
            "repository": "192.168.1.1:5000/repo",
            "tag": "5050",
        },
        {
            "input": "[2001:db8::1]",
            "err": errors.ErrReferenceInvalidFormat,
        },
        {
            "input": "[2001:db8::1]:5000",
            "err": errors.ErrReferenceInvalidFormat,
        },
        {
            "input": "[2001:db8::1]:tag",
            "err": errors.ErrReferenceInvalidFormat,
        },
        {
            "input": "[2001:db8::1]/repo",
            "domain": "[2001:db8::1]",
            "repository": "[2001:db8::1]/repo",
        },
        {
            "input": "[2001:db8:1:2:3:4:5:6]/repo:tag",
            "domain": "[2001:db8:1:2:3:4:5:6]",
            "repository": "[2001:db8:1:2:3:4:5:6]/repo",
            "tag": "tag",
        },
        {
            "input": "[2001:db8::1]:5000/repo",
            "domain": "[2001:db8::1]:5000",
            "repository": "[2001:db8::1]:5000/repo",
        },
        {
            "input": "[2001:db8::1]:5000/repo:tag",
            "domain": "[2001:db8::1]:5000",
            "repository": "[2001:db8::1]:5000/repo",
            "tag": "tag",
        },
        {
            "input": f"[2001:db8::1]:5000/repo@sha256:{'f' * 64}",
            "domain": "[2001:db8::1]:5000",
            "repository": "[2001:db8::1]:5000/repo",
            "digest": f"sha256:{'f' * 64}",
        },
        {
            "input": f"[2001:db8::1]:5000/repo:tag@sha256:{'f' * 64}",
            "domain": "[2001:db8::1]:5000",
            "repository": "[2001:db8::1]:5000/repo",
            "tag": "tag",
            "digest": f"sha256:{'f' * 64}",
        },
        {
            "input": "[2001:db8::]:5000/repo",
            "domain": "[2001:db8::]:5000",
            "repository": "[2001:db8::]:5000/repo",
        },
        {
            "input": "[::1]:5000/repo",
            "domain": "[::1]:5000",
            "repository": "[::1]:5000/repo",
        },
        {
            "input": "[fe80::1%eth0]:5000/repo",
            "err": errors.ErrReferenceInvalidFormat,
        },
        {
            "input": "[fe80::1%@invalidzone]:5000/repo",
            "err": errors.ErrReferenceInvalidFormat,
        },
    ),
)
def test_parse(testcase: Dict):
    input_value = testcase["input"]
    domain = testcase.get("domain", "")
    tag = testcase.get("tag", "")
    digest = testcase.get("digest", "")
    repository = testcase.get("repository", "")
    err = testcase.get("err", None)
    if err is not None:
        with pytest.raises(err):
            reference.parse(input_value)
    else:
        ref = reference.parse(input_value)
        assert str(ref) == input_value
        if isinstance(ref, NamedReference):
            assert ref.name == repository
            d, _ = reference.split_domain(ref.name)
            assert d == domain
        if isinstance(ref, TaggedReference):
            assert tag and ref.tag == tag
        if hasattr(ref, "digest"):
            assert ref.digest.value == digest
