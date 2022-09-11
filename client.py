#!/usr/bin/python3
# encoding: utf-8
import hashlib
import pathlib
from typing import Dict, Optional, Union, Type

import requests
from loguru import logger

from utlis import (
    RegistryScope,
    RepositoryScope,
    IMAGE_DEFAULT_TAG,
    DEFAULT_REPO,
    ScopeType,
    PingResp,
    BearerChallengeHandler,
    ChallengeScheme,
    ChallengeHandler, ManifestsResp,
)

logger.add("./client.log", level="INFO")


class ImageClient:
    def __init__(
            self,
            host: str,
            username: Optional[str] = None,
            password: Optional[str] = None,
            scheme: str = "https",
    ):
        self._host: str = host
        self._username: str = username
        self._password: str = password
        self._schema: str = scheme
        self._base_url = f"{scheme}://{host}"
        self._ping_resp: Optional[PingResp] = None
        self._pinged = False

    def ping(self) -> Optional[PingResp]:
        resp = requests.get(f"{self._base_url}/v2/")
        logger.debug(f"{resp.headers=}, {resp.text=}, {resp.status_code=}")
        auth_header = resp.headers.get("WWW-Authenticate", None)
        if auth_header is None:
            return None
        return PingResp(auth_header)

    def auth_header(self, scope: Union[str, RegistryScope, RepositoryScope] = ""):
        if self._pinged:
            ping_resp = self._ping_resp
        else:
            ping_resp = self.ping()
        if ping_resp is None:
            return {}
        return self._handle_challenges(ping_resp, scope)

    def _handle_challenges(self, challenge: PingResp, scope: ScopeType) -> Dict:
        scheme_dict: Dict[ChallengeScheme, Type[ChallengeHandler]] = {
            ChallengeScheme.Bearer: BearerChallengeHandler
        }
        handler = scheme_dict.get(challenge.scheme, None)
        if handler is None:
            return {}
        return handler(
            challenge, self._username, self._password, scope
        ).get_auth_header()

    def _request(
            self, suffix: str, scope: ScopeType, method: str, **kwargs
    ) -> requests.Response:
        if not suffix.startswith("/"):
            suffix = f"/{suffix}"
        url = f"{self._base_url}{suffix}"

        headers_in_param = kwargs.get("headers", None)
        if headers_in_param is None:
            headers = self.auth_header(scope)
        else:
            headers = headers_in_param
            del kwargs["headers"]
        logger.debug(f"{suffix=}, {scope=}, {method=}, {kwargs=}, {headers=}")
        return requests.request(method=method.upper(), url=url, headers=headers, **kwargs)

    def list_registry(self) -> Dict:
        suffix = "/v2/_catalog"
        scope = RegistryScope("catalog", ["*"])
        return self._request(suffix=suffix, scope=scope, method="GET").json()

    def _image_manifest(
            self,
            method: str,
            image_path: str,
            reference: str,
            auth_info: Dict[str, str]
    ) -> requests.Response:
        """
        fetch or check image manifest
        :param image_path: `repo_name/image_name`
        :param auth_info: {"Authorization": "Bearer token"}
        :param reference: tag or digest
        :return:
        """
        suffix = f"/v2/{image_path}/manifests/{reference}"
        logger.debug(f"{suffix=}, {auth_info=}")
        return requests.request(url=f"{self._base_url}{suffix}", method=method, headers=auth_info)

    def fetch_image_manifest(self, image_path: str, reference: str, auth_info: Dict[str, str]):
        resp = self._image_manifest("GET", image_path=image_path, reference=reference, auth_info=auth_info)
        if reference.startswith("sha256:"):  # check resp sha256
            logger.info("check manifest sha256 is equal to digest")
            resp_sha256 = hashlib.sha256(resp.content).hexdigest()
            assert reference[7:] == resp_sha256, resp_sha256
        return resp

    def image_manifest_existed(self, image_path: str, reference: str, auth_info) -> requests.Response:
        resp = self._image_manifest("HEAD", image_path, reference, auth_info)
        logger.debug(f"{resp.status_code=},{resp.text=}")
        return resp

    def _pull_schema2_config(self, url_base: str, digest: str):
        suffix = f"{url_base}/{digest}"

    def pull_image(self, image_name: str, repo_name: str = DEFAULT_REPO, reference: str = IMAGE_DEFAULT_TAG,
                   save_dir: Union[pathlib.Path, str] = None):
        save_dir = pathlib.Path(save_dir or ".").absolute()
        if not save_dir.is_dir():
            raise Exception(f"save dir {save_dir} not exists")
        save_dir.mkdir(exist_ok=True)

        image_name_with_repo = f"{repo_name}/{image_name}"
        scope = RepositoryScope(image_name_with_repo, ["pull"])
        headers = self.auth_header(scope)
        head_resp = self.image_manifest_existed(image_name_with_repo, reference=reference, auth_info=headers)
        if head_resp.status_code != 200:
            raise Exception(f"{image_name_with_repo}:{reference} not found")
        main_manifest = head_resp.headers.get("Docker-Content-Digest")
        manifest_resp = self.fetch_image_manifest(image_name_with_repo, reference=main_manifest, auth_info=headers)
        manifest = ManifestsResp(**manifest_resp.json())


if __name__ == "__main__":
    from tomlkit import parse

    with open("./registry_info.toml", "r", encoding="utf-8") as f:
        info = parse(f.read())
    c = ImageClient(**info.get("docker-mirror"))
    a = c.head_image_with_tag("python", repo_name="library")
    logger.info(a.headers.get("Etag"))
