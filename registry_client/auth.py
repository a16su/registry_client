#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午4:31
import base64
import datetime
from enum import Enum
from typing import Dict, Optional
from urllib.parse import urlparse

import iso8601
import requests

from registry_client.scope import Scope
from registry_client.utlis import DEFAULT_CLIENT_ID, INDEX_NAME

TOKEN_CACHE_MIN_TIME = 60


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


class Auther:
    def __init__(self, auth_config_header: Optional[str] = None):
        self._need_auth = True
        if auth_config_header is None:
            self._need_auth = False
        else:
            assert auth_config_header
            scheme, params = auth_config_header.split(" ")
            param_dict = dict(param.split("=") for param in params.split(","))
            self.scheme = ChallengeScheme(scheme)
            self.realm = param_dict.get("realm").strip('"')
            self.service = param_dict.get("service").strip('"')

    @property
    def need_auth(self) -> bool:
        return self._need_auth

    def auth_with_scope(self, username: str, password: str, scope: Scope, verify=True) -> Token:
        auth_info = {"Authorization": f"Basic {encode_auth(username, password)}"}
        if self.scheme == ChallengeScheme.Basic:
            return BasicToken(username=username, password=password)
        elif self.scheme == ChallengeScheme.Bearer:
            params = {
                "scope": str(scope),
                "service": self.service,
                "client_id": DEFAULT_CLIENT_ID,
                "account": username,
            }
            if urlparse(self.realm).netloc.endswith(INDEX_NAME) and not username and not password:
                auth_info = None

            resp = requests.get(self.realm, params=params, headers=auth_info, verify=verify)
            return BearerToken(resp)
