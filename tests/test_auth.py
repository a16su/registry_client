#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/13-下午5:32
import base64
import datetime
import itertools
import os

import pytest
import requests

from registry_client.auth import encode_auth, Token, BasicToken, BearerToken, EmptyToken, TOKEN_CACHE_MIN_TIME, Auther
from registry_client.scope import EmptyScope
from tests.conftest import FakeResponse


def test_encode_auth():
    username = "username"
    password = "password"
    encode_value = encode_auth(username, password)
    assert base64.b64decode(encode_value).decode() == f"{username}:{password}"


def test_token_base():
    t = Token()
    assert t.expired is False
    with pytest.raises(NotImplementedError):
        token = t.token


def test_empty_token():
    e = EmptyToken()
    assert e.expired is False
    assert e.token == {}


def generate_resp(
        token: str = None, access_token: str = None, expires_in: int = None, issued_at: datetime.datetime = None
):
    value = {
        "token": token or os.urandom(16).hex(),
        "access_token": access_token or "",
        "expires_in": expires_in or 1800,
        "issued_at": issued_at or datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
    }
    return FakeResponse().set_json(value)


class TestBearerToken:
    @pytest.mark.parametrize(
        "issued_at, expires_in, result",
        (
                (None, TOKEN_CACHE_MIN_TIME - 1, True),
                (None, TOKEN_CACHE_MIN_TIME + 1, False),
                (None, TOKEN_CACHE_MIN_TIME, True),
                (None, -1, True),
        ),
    )
    def test_expired(self, issued_at, expires_in, result):
        t = BearerToken(generate_resp(expires_in=expires_in, issued_at=issued_at))
        assert t.expired == result

    @pytest.mark.parametrize("token, access_token, want", (("foo", "", "foo"), ("", "bar", "bar")))
    def test_token(self, token, access_token, want):
        assert BearerToken(generate_resp(token=token, access_token=access_token)).token == {
            "Authorization": f"Bearer {want}"
        }


def test_basic_token():
    username = "a"
    password = "b"
    b = BasicToken(username, password)
    assert not b.expired
    assert b.token == {"Authorization": f"Basic {encode_auth(username, password)}"}


class TestAuther:
    @pytest.mark.parametrize(
        "header, result", (('Basic realm="http://a.com",service="docker-auth"', True), (None, False))
    )
    def test_need_auth(self, header, result):
        assert Auther(header).need_auth == result

    @pytest.mark.parametrize(
        "header, want_class",
        (
                ('Basic realm="http://a.com",service="docker-auth"', BasicToken),
                ('Bearer realm="http://a.com",service="docker-auth"', BearerToken),
        ),
    )
    def test_auth_with_scope_return_type(self, monkeypatch, header, want_class):
        a = Auther(header)
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: generate_resp())
        t = a.auth_with_scope("a", "b", scope=EmptyScope())
        assert isinstance(t, want_class)

    @pytest.mark.parametrize(
        "host, username, password, headers_is_empty",
        [
            ("https://registry-1.docker.io", "", "", True),
            ("https://registry-1.docker.io", "foo", "", False),
            ("https://registry-1.docker.io", "", "bar", False),
            ("https://registry-1.docker.io", "foo", "bar", False),
        ]
        + list(itertools.product(["https://a.com"], ["", "foo"], ["", "bar"], [False])),
    )
    def test_auth_header(self, monkeypatch, host, username, password, headers_is_empty):
        def check_header(*args, **kwargs):
            headers = kwargs.get("headers")
            assert bool(headers) != headers_is_empty
            return generate_resp()

        header = f'Bearer realm="{host}",service="docker-auth"'
        a = Auther(header)
        monkeypatch.setattr(requests, "get", check_header)
        a.auth_with_scope(username=username, password=password, scope=EmptyScope())
