#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午4:06
import pathlib
import re
import tempfile
from typing import List, Optional, Union

from loguru import logger

from registry_client import errors, spec
from registry_client.auth import AuthClient
from registry_client.digest import Digest
from registry_client.export import ImageFileSort, ImageV2Tar, OCIImageTar
from registry_client.image import BlobClient, ImageClient, ImageFormat
from registry_client.media_types import ImageMediaType
from registry_client.platforms import Platform
from registry_client.reference import (
    CanonicalReference,
    DigestReference,
    NamedReference,
    Reference,
    TaggedReference,
    parse_normalized_named,
)
from registry_client.repo import RepoClient
from registry_client.utlis import (
    DEFAULT_REGISTRY_HOST,
    DEFAULT_REPO,
    diff_ids_to_chain_ids,
)


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
        self._image_client = ImageClient(self.client)
        self._blob_client = BlobClient(self.client)

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

    def _get_manifest_digest(self, ref: Reference) -> CanonicalReference:
        manifest_digest = self._image_client.get_manifest_digest(ref)
        return CanonicalReference(ref.domain, ref.path, digest=manifest_digest)

    def _get_manifest(self, ref: CanonicalReference, platform: Platform) -> spec.Manifest:
        manifest_content_resp = self._image_client.get_manifest(ref)
        return self._image_client._handle_manifest(manifest_content_resp, ref, platform)

    def inspect_image(self, image_name: str, platform: Platform) -> spec.Image:
        ref = parse_normalized_named(image_name)
        digest_ref = self._get_manifest_digest(ref)

        manifest = self._get_manifest(digest_ref, platform)

        image_digest_ref = CanonicalReference(ref.domain, ref.path, digest=manifest.config.digest)
        resp = self._image_client.get_config(image_digest_ref)
        return spec.Image(**resp.json())

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
        :return: image save path
        :rtype: pathlib.Path
        """
        ref = parse_normalized_named(image_name)
        if save_dir.exists():
            assert save_dir.is_dir(), Exception("save_dir must be a directory")
        if not save_dir.exists():
            save_dir.mkdir(parents=True)
        tmp_dir = tempfile.TemporaryDirectory(prefix="image_download_")
        temp_dir_path = pathlib.Path(tmp_dir.name)
        temp_dir_path.mkdir(exist_ok=True)

        digest_ref = self._get_manifest_digest(ref)

        manifest = self._get_manifest(digest_ref, platform)

        image_digest_ref = CanonicalReference(ref.domain, ref.path, digest=manifest.config.digest)
        image_config_resp = self._image_client.get_config(image_digest_ref)
        image_config = spec.Image(**image_config_resp.json())

        assert len(image_config.rootfs.diff_ids) == len(manifest.layers), Exception("Invalid Manifest And ImageConfig")

        with open(temp_dir_path.joinpath("image_config.json"), "wb") as f:
            f.write(image_config_resp.content)

        layer_id_generator = diff_ids_to_chain_ids(image_config.rootfs.diff_ids)

        index = 0
        for layer_id in layer_id_generator:
            layer_path = temp_dir_path.joinpath(Digest(layer_id).hex)
            layer_path.mkdir()
            layer_desc = manifest.layers[index]
            is_gzip = layer_desc.media_type == ImageMediaType.MediaTypeDockerSchema2LayerGzip
            with open(layer_path.joinpath("layer.tar"), "wb") as f:
                with self._blob_client.get(
                    CanonicalReference(
                        image_digest_ref.domain,
                        image_digest_ref.path,
                        digest=layer_desc.digest,
                    ),
                    stream=True,
                ) as resp:
                    if is_gzip and image_format != ImageFormat.OCI:  # oci image use gzip layer
                        if resp.headers.get("Content-Encoding") is None:
                            resp.headers["content-encoding"] = "gzip"  # let httpx decode gzip
                    for content in resp.iter_bytes():
                        f.write(content)
            index += 1
        image_path = self._tar_layers(
            ref, layers_dir=temp_dir_path, save_dir=save_dir, image_format=image_format, compression=False
        )
        assert image_path.exists() and image_path.is_file(), RuntimeError("Image Pull Failed")
        return image_path

    def repo_tag(self, reference: TaggedReference):
        assert reference != ""
        if isinstance(reference, (CanonicalReference, DigestReference)):
            return None
        if isinstance(reference, NamedReference):
            reference = TaggedReference(reference.domain, reference.path, "latest")
        target = reference.target
        result = reference.path.split("/", 1)
        if self.client.base_url.netloc.decode() == DEFAULT_REGISTRY_HOST:
            if len(result) == 2 and result[0] == DEFAULT_REPO:
                return f"{result[-1]}:{target}"
            return f"{reference.path}:{target}"
        return str(reference)

    def _tar_layers(
        self,
        reference: Union[TaggedReference, CanonicalReference, DigestReference],
        layers_dir: pathlib.Path,
        save_dir: pathlib.Path,
        image_format: ImageFormat,
        compression: bool = False,
    ) -> pathlib.Path:
        """
        |- layer_id1/layer.tar
        |- layer_id2/layer.tar
        |- image_config.json
        Args:
            reference:
            layers_dir:
            save_dir:
            image_format:
            compression

        Returns:

        """
        target = reference.target
        image_save_path = save_dir.joinpath(f"{re.sub(r'[.:/]', '_', reference.name)}_{target}.tar")
        assert layers_dir.exists() and layers_dir.is_dir()
        image_name = self.repo_tag(reference=reference)
        sort_tool = ImageFileSort(
            image_name=image_name,
            target_dir=layers_dir,
        )
        format_handler = {ImageFormat.V2: ImageV2Tar, ImageFormat.OCI: OCIImageTar}
        if image_format == ImageFormat.V2:
            sort_tool.to_docker_v2()
        elif image_format == ImageFormat.OCI:
            sort_tool.to_oci()
        else:
            raise Exception("invalid image format")
        final_path = format_handler[image_format](
            src_dir=layers_dir,
            target_path=image_save_path,
            compress=compression,
        ).do()
        return final_path
