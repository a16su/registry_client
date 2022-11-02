#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/13-下午5:32
import base64
import datetime
import uuid
from typing import Optional, Dict

import httpx
import pytest

from registry_client.auth import (
    FakeToken,
    Token,
    encode_auth,
    BasicToken,
    BearerToken,
    TOKEN_CACHE_MIN_TIME,
    GLOBAL_TOKEN_CACHE,
    BearerAuth,
    RegistryChallenge,
    ChallengeScheme,
    parse_challenge,
    AuthClient,
)
from registry_client.scope import EmptyScope, RepositoryScope
from tests.conftest import FAKE_REGISTRY_AUTH_HOST


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
    e = FakeToken({"foo": "bar"})
    assert e.expired is False
    assert e.token == {"foo": "bar"}


class TestBasicToken:
    def test_expired_is_false(self):
        assert not BasicToken("foo", "bar").expired

    @pytest.mark.parametrize(
        "username, password, result",
        (
            ("foo", "bar", "Zm9vOmJhcg=="),
            ("foo", "", "exception"),
            ("", "bar", "exception"),
            ("", "", "exception"),
        ),
    )
    def test_token(self, username, password, result):
        if result == "exception":
            with pytest.raises(Exception):
                BasicToken(username, password)
        else:
            assert BasicToken(username, password).token == {"Authorization": f"Basic {result}"}


class TestBearerToken:
    @classmethod
    def fake_resp(
        cls,
        token: str,
        access_token: Optional[str] = None,
        issued_at: datetime.datetime = datetime.datetime.now(),
        expires_in=1800,
    ):
        resp = httpx.Response(
            200,
            json={
                "token": token or "",
                "access_token": access_token or "",
                "issued_at": issued_at.isoformat(),
                "expires_in": expires_in,
            },
        )
        return resp

    @pytest.mark.parametrize(
        "token, access_token, result",
        (("foo", "", "foo"), ("foo", "bar", "bar"), ("", "bar", "bar"), ("", "", "exception")),
    )
    def test_token(self, token, access_token, result):
        resp = self.fake_resp(token=token, access_token=access_token)
        token = BearerToken(resp)
        if result == "exception":
            with pytest.raises(Exception):
                token.token
        else:
            assert token.token == {"Authorization": f"Bearer {result}"}

    @pytest.mark.parametrize(
        "expires_in, is_expired",
        (
            (-TOKEN_CACHE_MIN_TIME, True),
            (-TOKEN_CACHE_MIN_TIME - 1, True),
            (TOKEN_CACHE_MIN_TIME - 1, True),
            (TOKEN_CACHE_MIN_TIME + 1, False),
        ),
    )
    def test_token_expired(self, expires_in, is_expired: bool):
        """
        ---------now-60----------now----------------
                 |->expired
        """
        create_at = datetime.datetime.now(tz=datetime.timezone.utc)
        resp = self.fake_resp("foo", "foo", issued_at=create_at, expires_in=expires_in)
        token = BearerToken(resp)
        assert token.expired == is_expired


class TestBearerAuth:
    @classmethod
    def gen_bearer_auth(
        cls,
        username="",
        password="",
        realm=FAKE_REGISTRY_AUTH_HOST,
        scope=None,
        service="",
        scheme=ChallengeScheme.Bearer,
    ):
        challenge = RegistryChallenge(scheme=scheme, realm=realm, service=service)
        return BearerAuth(username, password, challenge=challenge, scope=scope)

    def test_normal_resp(self):
        request = httpx.Request("GET", url="http://example.com")
        normal_resp = httpx.Response(200)
        scope = EmptyScope()
        a = self.gen_bearer_auth(scope=scope)
        flow = a.sync_auth_flow(request)
        request = next(flow)
        assert "Authorization" not in request.headers
        with pytest.raises(StopIteration):
            flow.send(normal_resp)

    def test_401_resp(self, auth_request_checker):
        username = "username"
        password = "password"
        service = "fake-service"
        token = uuid.uuid1().hex
        request = httpx.Request("GET", url="http://example.com")
        scope = RepositoryScope(repo_name=uuid.uuid1().hex, actions=["pull"])
        auth = self.gen_bearer_auth(scope=scope, service=service, username=username, password=password)
        flow = auth.sync_auth_flow(request)
        request = next(flow)
        assert "Authorization" not in request.headers
        assert str(scope) not in GLOBAL_TOKEN_CACHE
        resp_401 = httpx.Response(401)

        return_value = httpx.Response(
            200,
            json={
                "token": token,
                "access_token": token,
                "issued_at": datetime.datetime.now().isoformat(),
                "expires_in": 1800,
            },
        )
        auth_request_checker(
            username=username, password=password, scope=scope, service=service, return_value=return_value
        )
        request = flow.send(resp_401)
        assert request.headers.get("Authorization") == f"Bearer {token}"
        assert GLOBAL_TOKEN_CACHE.get(str(scope))
        with pytest.raises(StopIteration):
            flow.send(httpx.Response(200))

    def test_get_token_from_cache(self, monkeypatch):
        random_key = uuid.uuid1().hex
        token = FakeToken({"Authorization": random_key})
        monkeypatch.setitem(GLOBAL_TOKEN_CACHE, random_key, value=token)
        req = httpx.Request("GET", "https://example.com")
        auth = self.gen_bearer_auth(scope=random_key)
        flow = auth.sync_auth_flow(req)
        req = next(flow)
        assert req.headers.get("Authorization") == token.token["Authorization"]
        with pytest.raises(StopIteration):
            flow.send(httpx.Response(200))

    def test_token_expired_and_auth_again(self, monkeypatch, registry_auth_root):
        scope = uuid.uuid1().hex
        token = FakeToken({"token_key": "token_value"})
        monkeypatch.setitem(GLOBAL_TOKEN_CACHE, scope, token)
        req = httpx.Request("GET", "https://example.com")
        auth = self.gen_bearer_auth(scope=scope)
        flow = auth.sync_auth_flow(req)
        req = next(flow)
        assert req.headers.get("token_key") == token.token.get("token_key")
        resp_401 = httpx.Response(401)
        return_value = httpx.Response(
            200,
            json={
                "token": scope,
                "access_token": scope,
                "issued_at": datetime.datetime.now().isoformat(),
                "expires_in": 1800,
            },
        )
        registry_auth_root.mock(return_value=return_value)
        req = flow.send(resp_401)
        assert req.headers.get("Authorization") == f"Bearer {scope}"

    def test_docker_io_default_need_not_auth(self, auth_request_checker):
        req = httpx.Request("GET", "https://registry-1.docker.io")
        scope = uuid.uuid1().hex
        auth = self.gen_bearer_auth(scope=scope)
        flow = auth.sync_auth_flow(req)
        req = next(flow)
        resp = httpx.Response(401)
        return_value = httpx.Response(
            200,
            json={
                "token": scope,
                "access_token": scope,
                "issued_at": datetime.datetime.now().isoformat(),
                "expires_in": 1800,
            },
        )
        auth_request_checker(no_need_auth=True, return_value=return_value)
        req = flow.send(resp)

    def test_error_challenge_scheme(self):
        challenge = RegistryChallenge(ChallengeScheme.Basic, realm="http://example.com")
        with pytest.raises(AssertionError):
            b = BearerAuth("", "", challenge=challenge, scope=EmptyScope())


@pytest.mark.parametrize(
    "header, scheme, realm, service, scope, exception",
    (
        ('Basic realm="a.com",service="foo"', "Basic", "a.com", "foo", "", False),
        ('Bearer realm="a.com",service="foo"', "Bearer", "a.com", "foo", "", False),
        (
            'Bearer realm="a.com",service="foo",scope="registry:catalog:*"',
            "Bearer",
            "a.com",
            "foo",
            "registry:catalog:*",
            False,
        ),
        ("Basic service=foo", "", "", "", "", KeyError),
        ("BadScheme service=foo", "", "", "", "", ValueError),
    ),
)
def test_parse_challenge(header, scheme, realm, service, scope, exception):
    if exception:
        with pytest.raises(exception) as e:
            parse_challenge(header)
    else:
        challenge = parse_challenge(header)
        assert challenge.scheme == ChallengeScheme(scheme)
        assert challenge.realm == realm
        assert challenge.service == service
        if scope:
            assert challenge.scope == scope


class TestAuthClient:
    @pytest.mark.parametrize(
        "scheme, need_auth, exception",
        (
            ("Basic", True, None),
            ("Bearer", True, None),
            (None, False, None),
            ("BadBearer", True, ValueError),
        ),
    )
    def test_ping(self, docker_registry_client, registry_v2, scheme, need_auth, exception):
        client = AuthClient(base_url=docker_registry_client.client.base_url)
        if scheme:
            registry_v2.respond(headers={"www-authenticate": f'{scheme} realm="http://foo.com", service="bar"'})
        if exception:
            with pytest.raises(exception):
                client.ping()
        else:
            client.ping()
            if scheme:
                assert client.challenge.scheme.value == scheme
        assert client.need_auth is need_auth

    @pytest.mark.parametrize(
        "challenge_scheme, auth_by, want_auth_type",
        (
            ("Bearer", ("", ""), httpx.BasicAuth),
            ("Bearer", EmptyScope(), BearerAuth),
            ("Bearer", None, httpx.Auth),
            ("Bearer", 1, httpx.Auth),
            ("Basic", ("", ""), httpx.BasicAuth),
            ("Basic", EmptyScope(), httpx.BasicAuth),
            ("Basic", None, httpx.Auth),
            ("Basic", 1, httpx.BasicAuth),
        ),
    )
    def test_new_auth(self, auth_client, challenge_scheme, auth_by, want_auth_type, registry_v2, monkeypatch):
        registry_v2.respond(headers={"www-authenticate": f"{challenge_scheme} realm='http://example.com'"})
        auther = auth_client.new_auth(auth_by=auth_by)
        assert auth_client.need_auth
        assert auther.__class__ == want_auth_type

    def test_new_auth_with_need_not_auth(self, auth_client, registry_v2):
        auth_client.ping()
        assert not auth_client.need_auth
        assert auth_client.new_auth(EmptyScope()).__class__ == httpx.Auth

    def test_build_auth_by_tuple(self):
        client = AuthClient(auth=("foo", "bar"))
        assert client._username == "foo"
        assert client._password == "bar"
        assert client._auth.__class__ == httpx.BasicAuth

    def test_build_auth_default(self):
        client = AuthClient()
        assert client._auth is None

    def test_build_auth_with_need_not_auth(self, auth_client, monkeypatch, registry_v2):
        auth_client.ping()
        auth = auth_client._build_auth(None)
        assert auth.__class__ == httpx.Auth
