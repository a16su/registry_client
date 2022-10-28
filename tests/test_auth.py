#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/13-下午5:32
import base64

import pytest

from registry_client.auth import EmptyToken, Token, encode_auth


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
