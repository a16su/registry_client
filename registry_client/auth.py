#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午4:31
import base64
import datetime
import sys
from enum import Enum
from typing import Dict, NamedTuple, Optional, Tuple, Union

from pydantic import BaseModel

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

from urllib.parse import unquote
from urllib.request import parse_http_list

import httpx
import iso8601
import requests
from loguru import logger

from registry_client.scope import Scope

TOKEN_CACHE_MIN_TIME = 60
AUTH_TYPE = Union[httpx._types.AuthTypes, Scope, None]

GLOBAL_TOKEN_CACHE: Dict[str, "Token"] = {}


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


class FakeToken(Token):
    def __init__(self, token: Dict[str, str]):
        self._token = token

    @property
    def token(self) -> Dict[str, str]:
        return self._token


class BasicToken(Token):
    def __init__(self, username: str, password: str):
        if username == "" or password == "":
            raise Exception("failed to handle basic auth because missing username or secret")
        self._auth_header = {"Authorization": f"Basic {encode_auth(username, password)}"}

    @property
    def token(self):
        return self._auth_header


class BearerTokenResp(BaseModel):
    token: str
    access_token: str
    expires_in: int
    issued_at: str


class BearerToken(Token):
    def __init__(self, resp: requests.Response):
        token_resp = BearerTokenResp(**resp.json())
        _expires_in: datetime.timedelta = datetime.timedelta(seconds=token_resp.expires_in)
        _issued_at = iso8601.parse_date(token_resp.issued_at)
        self._expired_at = _expires_in + _issued_at
        self.access_token: Optional[str] = token_resp.access_token
        self._token = token_resp.token

    @property
    def token(self):
        token = self.access_token or self._token
        if not token:
            raise Exception("expect token in response")
        return {"Authorization": f"Bearer {token}"}

    @property
    def expired(self) -> bool:
        now = datetime.datetime.now(tz=self._expired_at.tzinfo)
        if now >= self._expired_at:
            return True
        return (self._expired_at - now).total_seconds() <= TOKEN_CACHE_MIN_TIME


class RegistryChallenge(NamedTuple):
    scheme: ChallengeScheme
    realm: str
    service: str = ""
    scope: str = None


def parse_challenge(auth_header: str) -> RegistryChallenge:
    scheme, _, fields = auth_header.partition(" ")
    scheme = ChallengeScheme(scheme)
    header_dict: Dict[str, str] = {}
    for field in parse_http_list(fields):
        key, value = field.strip().split("=", 1)
        header_dict[key] = unquote(value)
    try:
        realm = header_dict["realm"].strip('"')
        service = header_dict.get("service", "").strip('"')
        scope = header_dict.get("scope", None)
        if scope:
            scope = scope.strip('"')
        return RegistryChallenge(scheme=scheme, realm=realm, service=service, scope=scope)
    except KeyError as exc:
        raise KeyError(f"Malformed Bearer WWW-Authenticate header: missing key {exc}")


class BearerAuth(httpx.Auth):
    def __init__(self, username: str, password: str, challenge: RegistryChallenge, scope: Scope):
        assert challenge.scheme == ChallengeScheme.Bearer
        self._username = username
        self._password = password
        token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        self._auth_header = {"Authorization": f"Basic {token}"}
        self._challenge = challenge
        self._scope = scope

    def auth_flow(self, request: httpx.Request):
        scope = str(self._scope)
        token_from_cache = GLOBAL_TOKEN_CACHE.get(scope)
        if token_from_cache and not token_from_cache.expired:
            request.headers.update(token_from_cache.token)
        response = yield request
        if response.status_code != 401:
            # If the response is not a 401 then we don't
            # need to build an authenticated request.
            return
        token = self._build_auth_header(request=request, scope=scope, challenge=self._challenge)
        GLOBAL_TOKEN_CACHE[scope] = token
        request.headers.update(token.token)
        yield request

    def _build_auth_header(self, request: httpx.Request, scope: str, challenge: RegistryChallenge):
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
    def __init__(self, *args, **kwargs):
        self.__need_auth = True
        self._username = ""
        self._password = ""
        super(AuthClient, self).__init__(*args, **kwargs)
        self.__challenge: Optional[RegistryChallenge] = None
        self.event_hooks = {"request": [request_hook], "response": [response_hook]}

    @property
    def need_auth(self) -> bool:
        return self.__need_auth

    @property
    def challenge(self) -> RegistryChallenge:
        return self.__challenge

    def ping(self):
        c = httpx.Client(base_url=self.base_url)
        resp = c.get("/v2/")
        _auth_header = resp.headers.get("www-authenticate")
        if not _auth_header:
            # docker registry proxy, like: `hub-mirror.c.163.com`
            self.__need_auth = False
            return
        self.__challenge = parse_challenge(auth_header=_auth_header)

    def new_auth(self, auth_by: Optional[Union[Tuple[str, str], Scope]] = None) -> httpx.Auth:
        if auth_by is None:
            return httpx.Auth()
        if self.__challenge is None:
            self.ping()
        if not self.__need_auth:
            return httpx.Auth()
        if isinstance(auth_by, tuple):
            return httpx.BasicAuth(*auth_by)
        elif self.challenge.scheme == ChallengeScheme.Basic:
            return httpx.BasicAuth(self._username, self._password)
        elif self.challenge.scheme == ChallengeScheme.Bearer and isinstance(auth_by, Scope):
            return BearerAuth(self._username, self._password, self.__challenge, auth_by)
        return httpx.Auth()

    def _build_auth(self, auth: Optional[httpx._types.AuthTypes]) -> Optional[httpx.Auth]:
        if not self.__need_auth:
            return httpx.Auth()
        if isinstance(auth, tuple):
            self._username, self._password = auth
        return super(AuthClient, self)._build_auth(auth)
