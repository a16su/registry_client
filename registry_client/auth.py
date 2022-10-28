#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午4:31
import base64
import datetime
from enum import Enum
from typing import Dict, NamedTuple, Optional, Union
from urllib.parse import unquote
from urllib.request import parse_http_list

import httpx
import iso8601
import requests
from loguru import logger

from registry_client.scope import Scope

TOKEN_CACHE_MIN_TIME = 60
AUTH_TYPE = Union[httpx._types.AuthTypes, Scope, None]


class ChallengeScheme(Enum):
    Bearer = "Bearer"
    Basic = "Basic"


def encode_auth(username: str, password: str) -> str:
    base_str = f"{username}:{password}"
    return base64.urlsafe_b64encode(base_str.encode()).decode()


class Token:
    @property
    def expired(self) -> bool:
        return False

    @property
    def token(self) -> Dict[str, str]:
        raise NotImplementedError


class EmptyToken(Token):
    @property
    def token(self) -> Dict[str, str]:
        return {}


class BasicToken(Token):
    def __init__(self, username: str, password: str):
        if username == "" or password == "":
            raise Exception("failed to handle basic auth because missing username or secret")
        self._auth_header = {"Authorization": f"Basic {encode_auth(username, password)}"}

    @property
    def token(self):
        return self._auth_header


class BearerToken(Token):
    def __init__(self, resp: requests.Response):
        resp_dict = resp.json()
        self._token: str = resp_dict["token"]
        _expires_in: datetime.timedelta = datetime.timedelta(seconds=resp_dict["expires_in"])
        _issued_at = iso8601.parse_date(resp_dict["issued_at"])
        self._expired_at = _expires_in + _issued_at
        self.access_token: Optional[str] = resp_dict["access_token"]

    @property
    def token(self):
        token = self.access_token or self._token
        return {"Authorization": f"Bearer {token}"}

    @property
    def expired(self) -> bool:
        now = datetime.datetime.now(tz=self._expired_at.tzinfo)
        if now >= self._expired_at:
            return True
        return (self._expired_at - now).total_seconds() <= TOKEN_CACHE_MIN_TIME


class _BearerChallenge(NamedTuple):
    realm: str
    service: str
    scope: str = None


class CustomAuth(httpx.Auth):
    def auth_with_scope(self, request: httpx.Request, scope: Scope) -> httpx.Auth:
        raise NotImplementedError


class BasicAuth(CustomAuth, httpx.BasicAuth):
    def auth_with_scope(self, request: httpx.Request, scope: Scope):
        return self


class BearerAuth(CustomAuth):
    def __init__(self, username: str, password: str, challenge: _BearerChallenge):
        self._username = username
        self._password = password
        token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        self._auth_header = {"Authorization": f"Basic {token}"}
        self._challenge = challenge
        self._token_cache: Dict[str, BearerToken] = {}

    def auth_with_scope(self, request: httpx.Request, scope: Scope):
        scope = str(scope)
        token_from_cache = self._token_cache.get(scope)
        if token_from_cache and not token_from_cache.expired:
            token = token_from_cache
        else:
            token = self._build_auth_header(request=request, scope=scope, challenge=self._challenge)
            self._token_cache[scope] = token
        request.headers.update(token.token)
        return self

    def _build_auth_header(self, request: httpx.Request, scope: str, challenge: _BearerChallenge):
        params = {
            "scope": scope,
            "service": challenge.service,
            "client_id": "python_registry_client",
            "account": self._username,
        }
        header = self._auth_header
        if request.url.netloc.endswith(b"docker.io") and not (self._username or self._password):
            header = None
        resp = httpx.Client().get(challenge.realm, headers=header, params=params)
        return BearerToken(resp)


def request_hook(request: httpx.Request):
    logger.debug(f"{request.method} {request.url} {request.headers}")


def response_hook(response: httpx.Response):
    logger.debug(f"RESPONSE: {response.status_code} {response.url} {response.headers}")


class AuthClient(httpx.Client):
    #
    def __init__(self, auth: Optional[Union[httpx._types.AuthTypes, Scope]] = None, *args, **kwargs):
        self._ping_flag = False
        self.__need_auth = True
        super(AuthClient, self).__init__(auth=auth, *args, **kwargs)
        self.follow_redirects = True
        self.event_hooks = {"request": [request_hook], "response": [response_hook]}

    def _parse_challenge(self, auth_header: str) -> _BearerChallenge:
        scheme, _, fields = auth_header.partition(" ")
        assert scheme.lower() == "bearer"

        header_dict: Dict[str, str] = {}
        for field in parse_http_list(fields):
            key, value = field.strip().split("=", 1)
            header_dict[key] = unquote(value)
        try:
            realm = header_dict["realm"].strip('"')
            service = header_dict["service"].strip('"')
            scope = header_dict.get("scope", None)
            return _BearerChallenge(realm=realm, service=service, scope=scope)
        except KeyError as exc:
            raise Exception("Malformed Bearer WWW-Authenticate header") from exc

    def _build_auth(self, auth: Optional[httpx._types.AuthTypes]) -> Optional[httpx.Auth]:
        if not self.__need_auth and isinstance(auth, Scope):
            return None
        if self._ping_flag:
            return super(AuthClient, self)._build_auth(auth)

        self._username, self._password = auth
        c = httpx.Client()
        resp = c.get(self.base_url.join("/v2/"))
        _auth_header = resp.headers.get("www-authenticate")
        self._ping_flag = True
        if not _auth_header:
            self.__need_auth = False
            return None
        if _auth_header.startswith("Basic"):
            return BasicAuth(self._username, self._password)
        elif _auth_header.startswith("Bearer"):
            challenge = self._parse_challenge(auth_header=_auth_header)
            return BearerAuth(self._username, self._password, challenge)
        return None

    def _build_request_auth(self, request: httpx.Request, auth: AUTH_TYPE = None) -> httpx.Auth:
        if not self.__need_auth or auth is None:
            return httpx.Auth()
        elif self._auth and isinstance(auth, Scope):
            return self._auth.auth_with_scope(request, auth)
        elif isinstance(auth, tuple):
            return httpx.BasicAuth(*auth)
        return httpx.Auth()

    def get(self, url: httpx._types.URLTypes, auth: AUTH_TYPE, *args, **kwargs) -> httpx.Response:
        return super(AuthClient, self).get(url=url, auth=auth, *args, **kwargs)
