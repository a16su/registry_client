#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午4:06
import json
import pathlib
import re
import tempfile
import typing
from typing import List, Optional, Union

import httpx
from loguru import logger

from registry_client import errors, spec
from registry_client.auth import AuthClient
from registry_client.digest import Digest
from registry_client.export import ImageV2Tar, OCIImageTar
from registry_client.image import BlobClient, ImageClient, ImageFormat
from registry_client.media_types import ImageMediaType, OCIImageMediaType
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
            count (int): Limit the number of entries in each response. If not present, 100 entries will be returned.
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

    def _get_manifest(self, ref: CanonicalReference, platform: Platform) -> httpx.Response:
        manifest_content_resp = self._image_client.get_manifest(ref)
        return self._image_client._handle_manifest(manifest_content_resp, ref, platform)

    def inspect_image(self, image_name: str, platform: Platform) -> spec.Image:
        ref = parse_normalized_named(image_name)

        digest_ref = self._get_manifest_digest(ref)
        manifest_resp = self._get_manifest(digest_ref, platform)
        manifest = spec.Manifest(**manifest_resp.json())

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
        image_name = self.repo_tag(ref)

        digest_ref = self._get_manifest_digest(ref)
        manifest_resp = self._get_manifest(digest_ref, platform)
        manifest = spec.Manifest(**manifest_resp.json())

        image_digest_ref = CanonicalReference(ref.domain, ref.path, digest=manifest.config.digest)
        image_config_resp = self._image_client.get_config(image_digest_ref)
        image_config = spec.Image(**image_config_resp.json())
        target = ref.target
        image_save_path = save_dir.joinpath(f"{re.sub(r'[.:/]', '_', ref.name)}_{target}.tar")

        if image_format == ImageFormat.OCI:
            self._pull_oci_image(
                ref=image_digest_ref,
                image_name=image_name,
                save_dir=temp_dir_path,
                manifest=manifest_resp,
                image_config=image_config_resp,
            )
            image_path = OCIImageTar(src_dir=temp_dir_path, target_path=image_save_path).do()
        elif image_format == ImageFormat.V2:
            self._pull_docker_v2_image(
                ref=image_digest_ref,
                image_name=image_name,
                save_dir=temp_dir_path,
                manifest=manifest_resp,
                image_config=image_config_resp,
            )
            image_path = ImageV2Tar(src_dir=temp_dir_path, target_path=image_save_path).do()
        else:
            raise RuntimeError(f"Invalid Image Format: {image_format}")
        assert image_path.exists() and image_path.is_file(), RuntimeError("Image Pull Failed")
        return image_path

    def _download_blob(self, ref: CanonicalReference, target: pathlib.Path, content_encoding=None):
        with open(target, "wb") as f:
            with self._blob_client.get(ref, stream=True) as resp:
                if content_encoding is not None:
                    resp.headers["content-encoding"] = content_encoding
                for content in resp.iter_bytes():
                    f.write(content)

    def _pull_docker_v2_image(
        self,
        ref: CanonicalReference,
        image_name: str,
        save_dir: pathlib.Path,
        manifest: httpx.Response,
        image_config: httpx.Response,
    ):
        manifest_spec = spec.Manifest(**manifest.json())
        image_config_spec = spec.Image(**image_config.json())
        layer_id_generator = diff_ids_to_chain_ids(image_config_spec.rootfs.diff_ids)

        layer_path_list = []
        for index, layer_id in enumerate(layer_id_generator):
            layer_save_dir = save_dir.joinpath(Digest(layer_id).hex)
            layer_save_dir.mkdir()
            layer_desc = manifest_spec.layers[index]
            new_ref = ref
            new_ref.digest = layer_desc.digest
            layer_path = layer_save_dir.joinpath("layer.tar")
            encoding = (
                "gzip"
                if layer_desc.media_type
                in (
                    ImageMediaType.MediaTypeDockerSchema2LayerGzip,
                    OCIImageMediaType.MediaTypeImageLayerGzip,
                )
                else None
            )
            self._download_blob(new_ref, layer_path, content_encoding=encoding)
            layer_path_list.append(str(layer_path.relative_to(save_dir).as_posix()))

        image_config_digest = Digest.from_bytes(image_config.content)
        image_config_path = save_dir.joinpath(image_config_digest.hex)
        image_config_path.write_bytes(image_config.content)

        data = [
            {
                "Config": image_config_path.name,
                "RepoTags": [image_name] if image_name else [],
                "Layers": layer_path_list,
            }
        ]
        with open(save_dir.joinpath("manifest.json"), "w") as out_file:
            json.dump(data, out_file)

    def _pull_oci_image(
        self,
        ref: CanonicalReference,
        image_name: str,
        save_dir: pathlib.Path,
        manifest: httpx.Response,
        image_config: httpx.Response,
    ):
        def write_json(content: bytes) -> typing.Tuple[Digest, pathlib.Path]:
            d = Digest.from_bytes(content)
            p = layer_save_dir.joinpath(f"{d.algom.value}/{d.hex}")
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(content)
            return d, p

        layer_save_dir = save_dir.joinpath("blobs")
        layer_save_dir.mkdir(parents=True)
        layers: typing.List[spec.Descriptor] = []
        for layer_spec in spec.Manifest(**manifest.json()).layers:
            target_digest = layer_spec.digest
            target_temp = layer_save_dir.joinpath(f"{target_digest.algom.value}/{target_digest.hex}")
            if target_temp.exists():
                continue
            target_temp.parent.mkdir(exist_ok=True)
            new_ref = ref
            new_ref.digest = target_digest
            self._download_blob(new_ref, target_temp)
            size = target_temp.stat().st_size
            layers.append(spec.Descriptor(mediaType=layer_spec.media_type, digest=target_digest, size=size))
        write_json(image_config.content)

        with save_dir.joinpath(spec.ImageLayoutFile).open("w", encoding="utf-8") as f:
            json.dump(spec.ImageLayout().dict(by_alias=True), f)

        manifest_digest, manifest_path = write_json(manifest.content)

        index = spec.Index(
            mediaType=OCIImageMediaType.MediaTypeImageIndex,
            manifests=[
                spec.Descriptor(
                    mediaType=OCIImageMediaType.MediaTypeImageManifest,
                    digest=manifest_digest,
                    size=manifest_path.stat().st_size,
                    annotations={spec.AnnotationsKey.AnnotationBaseImageName.value: image_name},
                )
            ],
        ).json(exclude_none=True, by_alias=True)
        with open(save_dir.joinpath("index.json"), "w") as f:
            f.write(index)

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
