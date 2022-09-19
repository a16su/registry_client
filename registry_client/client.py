#!/usr/bin/python3
# encoding: utf-8
import hashlib
import json
import pathlib
import shutil
from typing import Dict, Optional, Union, Type
from concurrent.futures import ThreadPoolExecutor

import requests
from loguru import logger
from tqdm import tqdm

from registry_client.digest import Digest
from registry_client.utlis import (
    RegistryScope,
    RepositoryScope,
    IMAGE_DEFAULT_TAG,
    DEFAULT_REPO,
    ScopeType,
    PingResp,
    BearerChallengeHandler,
    ChallengeScheme,
    ChallengeHandler,
    ManifestsResp,
    DEFAULT_REGISTRY_HOST,
    BasicChallengeHandler,
    ManifestsListResp,
)
from registry_client.media_types import ImageMediaType
from registry_client.platforms import Platform
from registry_client.decompress import GZipDeCompress, TarImageDir

logger.add("./client.log", level="INFO")


class ImageClient:
    def __init__(
        self,
        host: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        scheme: str = "https",
        platform: Platform = Platform(),
    ):
        self._host: str = host
        self._username: str = username
        self._password: str = password
        self._schema: str = scheme
        self._base_url = f"{scheme}://{host}"
        self._ping_resp: Optional[PingResp] = None
        self._pinged = False
        self._default_headers = {}
        self._platform = platform

    def ping(self) -> Optional[PingResp]:
        resp = requests.get(f"{self._base_url}/v2/", verify=False)
        logger.debug(f"{resp.headers=}, {resp.text=}, {resp.status_code=}")
        auth_header = resp.headers.get("WWW-Authenticate", None)
        if auth_header is None:
            return None
        return PingResp(headers=auth_header)

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
            ChallengeScheme.Bearer: BearerChallengeHandler,
            ChallengeScheme.Basic: BasicChallengeHandler,
        }
        handler = scheme_dict.get(challenge.scheme, None)
        if handler is None:
            return {}
        return handler(
            ping_resp=challenge,
            username=self._username,
            password=self._password,
            scope=scope,
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
        return requests.request(
            method=method.upper(), url=url, headers=headers, **kwargs
        )

    def list_registry(self) -> Dict:
        suffix = "/v2/_catalog"
        scope = RegistryScope("catalog", ["*"])
        return self._request(suffix=suffix, scope=scope, method="GET").json()

    def _image_manifest(
        self, method: str, image_path: str, reference: str, auth_info: Dict[str, str]
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
        return requests.request(
            url=f"{self._base_url}{suffix}", method=method, headers=auth_info
        )

    def fetch_image_manifest(
            self, image_path: str, reference: str, auth_info: Dict[str, str]
    ) -> ManifestsResp:
        resp = self._image_manifest(
            "GET", image_path=image_path, reference=reference, auth_info=auth_info
        )
        if Digest.is_digest(reference):  # check resp sha256
            logger.info("check manifest sha256 is equal to digest")
            assert Digest(reference) == Digest.from_bytes(resp.content)
        if (
                resp.json()["mediaType"]
                == ImageMediaType.MediaTypeDockerSchema2ManifestList.value
        ):
            target_digest = ManifestsListResp(**resp.json()).filter(self._platform)
            resp = self._image_manifest(
                "GET",
                image_path=image_path,
                reference=target_digest.value,
                auth_info=auth_info,
            )
        return ManifestsResp(**resp.json())

    def image_manifest_existed(
        self, image_path: str, reference: str, auth_info
    ) -> requests.Response:
        resp = self._image_manifest("HEAD", image_path, reference, auth_info)
        logger.debug(f"{resp.status_code=},{resp.text=}")
        return resp

    def _pull_schema2_config(
        self, url_base: str, digest: Digest, headers: Dict[str, str]
    ) -> requests.Response:
        url = f"{self._base_url}/v2/{url_base}/blobs/{digest}"
        resp = requests.get(url, headers=headers)
        logger.debug(resp.headers)
        return resp

    def _download_and_decompress_layer(
        self,
        base_url: str,
        digest: Digest,
        save_dir: pathlib.Path,
        headers: Dict[str, str],
        index: int,
    ) -> pathlib.Path:
        url = f"{self._base_url}/v2/{base_url}/blobs/{digest}"
        tmp_file = save_dir.joinpath(f"layer_{index}.tar.gz")
        text = f"{digest.short}: "
        with requests.get(url, headers=headers, stream=True) as resp, open(
            tmp_file, "wb"
        ) as f, tqdm(
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            total=int(resp.headers.get("content-length")),
            desc=text,
        ) as progress:
            hasher = hashlib.sha256()
            for chunk in resp.iter_content(5120):
                if chunk:
                    data_size = f.write(chunk)
                    progress.update(data_size)
                    hasher.update(chunk)
            assert hasher.hexdigest() == digest.hex
            logger.info(f"download to {tmp_file}")
        logger.info(f"decompress file {tmp_file}")
        progress.clear()
        progress.write("Decompress")
        GZipDeCompress(tmp_file, save_dir.joinpath(digest.hex)).do()
        tmp_file.unlink()
        return save_dir.joinpath(digest.hex, "layer.tar")

    def pull_image(
        self,
        image_name: str,
        repo_name: str = DEFAULT_REPO,
        reference: str = IMAGE_DEFAULT_TAG,
        save_dir: Union[pathlib.Path, str] = None,
        check_layer: bool = False,
    ):
        save_dir = pathlib.Path(save_dir or ".").absolute()
        if not save_dir.is_dir():
            raise Exception(f"save dir {save_dir} not exists")
        save_dir.mkdir(exist_ok=True)

        image_name_with_repo = f"{repo_name}/{image_name}"
        scope = RepositoryScope(repo_name=image_name_with_repo, actions=["pull"])
        headers = self.auth_header(scope)
        headers["Accept"] = "application/vnd.docker.distribution.manifest.v2+json"
        headers.update(self._default_headers)
        head_resp = self.image_manifest_existed(
            image_name_with_repo, reference=reference, auth_info=headers
        )
        if head_resp.status_code != 200:
            raise Exception(f"{image_name_with_repo}:{reference} not found")
        main_manifest = head_resp.headers.get("Docker-Content-Digest")
        manifest = self.fetch_image_manifest(
            image_name_with_repo, reference=main_manifest, auth_info=headers
        )
        image_config = self._pull_schema2_config(
            image_name_with_repo, manifest.config.digest, headers
        )

        image_save_dir = save_dir.joinpath(image_name_with_repo, reference)
        image_save_dir.mkdir(parents=True, exist_ok=True)
        config_digest = Digest.from_bytes(image_config.content)
        with open(
            image_save_dir.joinpath(f"{config_digest.hex}.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(image_config.json(), f)
        with open(image_save_dir.joinpath("VERSION"), "w") as f:
            f.write("1.0")

        digests = [layer.digest for layer in manifest.layers]
        with ThreadPoolExecutor(max_workers=5) as executor:
            jobs = [
                executor.submit(
                    self._download_and_decompress_layer,
                    image_name_with_repo,
                    digest,
                    image_save_dir,
                    headers,
                    index,
                )
                for index, digest in enumerate(digests)
            ]

        with open(image_save_dir.joinpath("manifest.json"), "w", encoding="utf-8") as f:
            if self._host == DEFAULT_REGISTRY_HOST and repo_name == DEFAULT_REPO:
                repo_tags = [f"{image_name}:{reference}"]
            else:
                repo_tags = [f"{self._host}/{repo_name}/{image_name}:{reference}"]
            data = {
                "Config": f"{config_digest.hex}.json",
                "RepoTags": repo_tags,
                "Layers": [f"{digest.hex}/layer.tar" for digest in digests],
            }
            json.dump([data], f)
        with open(image_save_dir.joinpath(digests[-1].hex, "json"), "w") as f:
            json.dump(image_config.json(), f)

        TarImageDir(
            image_save_dir, save_dir.joinpath(f"{repo_name}_{image_name}.tar")
        ).do()
        layer_save_dir = save_dir.joinpath(repo_name).absolute()
        logger.info(f"rm layer download dir {layer_save_dir}")
        shutil.rmtree(layer_save_dir)


if __name__ == "__main__":
    from tomlkit import parse

    with open(
            pathlib.Path(".").absolute().parent.joinpath("registry_info.toml"),
            "r",
            encoding="utf-8",
    ) as f:
        info = parse(f.read())
    img_name = "hello-world"
    repo = "library"
    ref = "latest"

    c = ImageClient(**info.get("docker-official"))
    c.pull_image(image_name=img_name, repo_name=repo, reference=ref, check_layer=False)
