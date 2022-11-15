#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午4:06
import pathlib
from typing import List, Optional

from loguru import logger

from registry_client import errors
from registry_client.auth import AuthClient
from registry_client.image import ImageClient, ImageFormat, ImagePullOptions
from registry_client.platforms import Platform
from registry_client.reference import (
    CanonicalReference,
    NamedReference,
    parse_normalized_named,
)
from registry_client.repo import RepoClient


class RegistryClient:
    def __init__(
        self,
        host="https://registry-1.docker.io",
        username: str = "",
        password: str = "",
        skip_verify=False,
    ):
        self._username = username
        self._password = password
        self.client = AuthClient(
            base_url=host,
            auth=(username, password),
            verify=not skip_verify,
            follow_redirects=True,
        )
        self._registry_client = RepoClient(self.client)

    def catalog(self, count: Optional[int] = None, last: Optional[str] = None) -> List[str]:
        """
        Retrieve a sorted, json list of repositories available in the registry.

        Args:
            count (int): Limit the number of entries in each response. It not present, 100 entries will be returned.
            last (str): Result set will include values lexically after last.

        Returns:
            ["library/hello-world", "repo/image_name"]
        """
        resp = self._registry_client.list(count, last)
        resp.raise_for_status()
        return resp.json().get("repositories", [])

    def list_tags(self, image_name: str, limit: Optional[int] = None, last: Optional[str] = None) -> List[str]:
        """
        Return all tags for the repository

        Args:
            image_name (str): hello-world、library/hello-world
            limit (int): Limit the number of entries in each response. It not present, all entries will be returned.
            last (str): Result set will include values lexically after last.

        Returns:
            List[str]
        """
        ref = parse_normalized_named(image_name)
        assert isinstance(ref, NamedReference), Exception("No tag or digest allowed in reference")
        resp = ImageClient(self.client).list_tag(ref, limit, last)
        if resp.status_code in [
            401,
            404,
        ]:  # docker hub status_code is 401, harbor is 404, registry mirror is 200
            logger.warning("image may be dont exist, return empty list")
            return []
        resp.raise_for_status()
        tags = resp.json().get("tags", None)
        return tags if tags is not None else []

    def delete_image(self, image_name: str):
        """
        delete an image by digest

        Args:
            image_name (str): hello-world@sha256:f54a58bc1aac5ea1a25d796ae155dc228b3f0e11d046ae276b39c4bf2f13d8c4
        Raises:
            ImageNotFountError, ErrNameNotCanonical
        Returns:
            bool
        """
        ref = parse_normalized_named(image_name)
        if not isinstance(ref, CanonicalReference):
            raise errors.ErrNameNotCanonical()
        resp = ImageClient(self.client).delete(ref)
        if resp.status_code == 404:
            raise errors.ImageNotFoundError(image_name)
        resp.raise_for_status()
        logger.info(f"delete image:{image_name} success")
        return True

    def pull_image(
        self,
        image_name: str,
        save_dir: pathlib.Path,
        platform: Platform = Platform(),
        image_format: ImageFormat = ImageFormat.V2,
    ) -> pathlib.Path:
        """
        pull image and tar
        :param image_name: image name
        :param save_dir: where to save the final image tar
        :param platform: image platform
        :param image_format: tar to `Docker V2` or `OCI`
        :return: image file path
        :rtype: pathlib.Path
        """
        ref = parse_normalized_named(image_name)
        if save_dir.exists():
            assert save_dir.is_dir(), Exception("save_dir must be a directory")
        image_path = ImageClient(self.client).pull(
            ref, options=ImagePullOptions(save_dir=save_dir, image_format=image_format, platform=platform)
        )
        assert image_path.exists() and image_path.is_file(), RuntimeError("Image Pull Failed")
        return image_path
