import dataclasses
import gzip
import json
import os
import pathlib
import shutil
import tarfile
from typing import List

from loguru import logger

from registry_client import spec
from registry_client.digest import Digest
from registry_client.media_types import OCIImageMediaType

BZIP_MAGIC = b"\x42\x5A\x68"
GZIP_MAGIC = b"\x1F\x8B\x8B"
XZ_MAGIC = b"\xFD\x37\x7A\x58\x5A\x00"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


@dataclasses.dataclass
class ImageFileSort:
    image_name: str
    target_dir: pathlib.Path
    layers_by_sort: List[pathlib.Path]
    image_config: bytes

    def to_docker_v2(self):
        image_config_digest = Digest.from_bytes(self.image_config)
        with self.target_dir.joinpath(f"{image_config_digest.hex}.json").open("wb") as f:
            f.write(self.image_config)

        for index, layer_path in enumerate(self.layers_by_sort):
            layer_digest = layer_path.stem
            layer_dir = self.target_dir.joinpath(layer_digest)
            layer_dir.mkdir()
            target_path = layer_dir.joinpath("layer.tar")
            shutil.move(layer_path, target_path)
            self.layers_by_sort[index] = target_path

        with open(self.target_dir.joinpath("manifest.json"), "w", encoding="utf-8") as f:
            repo_tags = [self.image_name] if self.image_name else []
            data = {
                "Config": f"{image_config_digest.hex}.json",
                "RepoTags": repo_tags,
                "Layers": [str(path.relative_to(self.target_dir)) for path in self.layers_by_sort],
            }
            json.dump([data], f)

    def to_oci(self, image_config_digest: Digest):
        with self.target_dir.joinpath(spec.ImageLayoutFile).open("w", encoding="utf-8") as f:
            json.dump(spec.ImageLayout().dict(by_alias=True), f)

        blobs_dir = self.target_dir.joinpath("blobs")
        blobs_dir.mkdir()
        sub_dir: pathlib.Path = blobs_dir.joinpath(image_config_digest.algom.value)
        sub_dir.mkdir()
        layers: List[spec.Descriptor] = []
        for layer_file in self.layers_by_sort:
            target = sub_dir.joinpath(layer_file.stem)
            shutil.move(layer_file, sub_dir.joinpath(layer_file.stem))

            digest = Digest(f"{target.parent.name}:{target.stem}")
            size = target.stat().st_size
            layers.append(spec.Descriptor(mediaType=OCIImageMediaType.MediaTypeImageLayer, digest=digest, size=size))

        image_config_path = sub_dir.joinpath(image_config_digest.hex)
        with image_config_path.open("wb") as f:
            f.write(self.image_config)

        manifest = spec.Manifest(
            mediaType=OCIImageMediaType.MediaTypeImageManifest,
            config=spec.Descriptor(
                mediaType=OCIImageMediaType.MediaTypeImageConfig,
                digest=image_config_digest,
                size=image_config_path.stat().st_size,
            ),
            layers=layers,
        ).json(exclude_none=True, by_alias=True)
        manifest_digest = Digest.from_bytes(manifest.encode())
        manifest_path = sub_dir.joinpath(manifest_digest.hex)
        with open(manifest_path, "w") as f:
            f.write(manifest)

        index = spec.Index(
            mediaType=OCIImageMediaType.MediaTypeImageIndex,
            manifests=[
                spec.Descriptor(
                    mediaType=OCIImageMediaType.MediaTypeImageManifest,
                    digest=manifest_digest,
                    size=manifest_path.stat().st_size,
                )
            ],
        ).json(exclude_none=True, by_alias=True)
        with open(self.target_dir.joinpath("index.json"), "w") as f:
            f.write(index)


class TarImageDir:
    def __init__(
        self,
        src_dir: pathlib.Path,
        target_path: pathlib.Path,
        delete: bool = False,
        compress: bool = False,
    ):
        """
        src_dir: the dir want to tar
        target_path: final image save path
        delete: either or not delete src_dir when tar done
        compress: either gzip image
        """
        self.src_dir = src_dir
        assert self.src_dir.exists() and self.src_dir.is_dir()
        self.target_path = target_path
        assert not self.target_path.is_dir()
        self.delete_when_done = delete
        self.compress = compress

    @staticmethod
    def _check_digest(want: str, path: pathlib.Path):
        logger.info(f"check file:{path} digest == {want}")
        want_digest = Digest(want)
        with open(path, "rb") as f:
            get_digest = Digest.from_bytes(f.read())
        assert want_digest == get_digest, f"{get_digest}!={want_digest}"

    def do(self) -> pathlib.Path:
        with tarfile.open(self.target_path, "w") as tar_file:
            logger.info(f"tar {self.src_dir} to {self.target_path}")
            tar_file.add(self.src_dir, arcname=os.path.sep)
        final_path = self.target_path
        if self.compress:
            gzip_target = self.target_path.with_suffix(".tar.gz")
            logger.info(f"gzip {self.target_path} to {gzip_target}")
            with gzip.open(gzip_target, "wb") as file_out:
                with open(self.target_path, "rb") as file_in:
                    file_out.write(file_in.read())
            self.target_path.unlink()
            final_path = gzip_target
        if self.delete_when_done:
            try:
                logger.info(f"delete {self.src_dir}!!!")
                shutil.rmtree(self.src_dir)
            except Exception as e:
                logger.error(f"rmtree {self.src_dir} failed: {e}, ignore")
        return final_path


class ImageV2Tar(TarImageDir):
    """
    ├── c28b9c2faac407005d4d657e49f372fb3579a47dd4e4d87d13e29edd1c912d5c
    │  ├── json
    │  ├── layer.tar
    │  └── VERSION
    ├── feb5d9fea6a5e9606aa995e879d862b825965ba48de054caab5ef356dc6b3412.json
    ├── manifest.json
    └── repositories
    """

    def __init__(
        self,
        src_dir: pathlib.Path,
        target_path: pathlib.Path,
        delete: bool = False,
        compress: bool = False,
    ):
        super(ImageV2Tar, self).__init__(src_dir, target_path, delete=delete, compress=compress)

    @classmethod
    def _check_manifest(cls, path: pathlib.Path):
        logger.info(f"check image_manifest:{path}")
        assert path.exists() and path.is_file()

    @classmethod
    def _check_image_config(cls, image_config_path: pathlib.Path):
        assert image_config_path and image_config_path.is_file()
        logger.info(f"check image_config:{image_config_path} digest")
        cls._check_digest(f"sha256:{image_config_path.stem}", image_config_path)

    @classmethod
    def _check_layers(cls, layers_path: List[pathlib.Path], diff_ids: List[str]):
        assert layers_path
        for index, one_layer_path in enumerate(layers_path):
            assert one_layer_path.exists(), one_layer_path
            logger.info(f"check layer:{one_layer_path} digest")
            cls._check_digest(diff_ids[index], one_layer_path)

    def check(self):
        image_manifest_path = self.src_dir.joinpath("manifest.json")
        self._check_manifest(image_manifest_path)
        with image_manifest_path.open("r") as f:
            image_manifest = json.load(f)[0]  #

        image_config_path = self.src_dir.joinpath(image_manifest["Config"])
        self._check_image_config(image_config_path)
        with image_config_path.open("rb") as f:
            image_config = json.load(f)

        layer_paths = image_manifest["Layers"]
        layer_paths = [self.src_dir.joinpath(layer_path) for layer_path in layer_paths]
        # diff_id is layer sha256sum
        layer_diff_ids: List[str] = image_config["rootfs"]["diff_ids"]
        self._check_layers(layer_paths, layer_diff_ids)

    def do(self) -> pathlib.Path:
        self.check()
        return super(ImageV2Tar, self).do()


class OCIImageTar(TarImageDir):
    """
    Tar directory to oci image format
    ─ blobs
    │  └── sha256
    │     ├── 2db29710123e3e53a794f2694094b9b4338aa9ee5c40b930cb8063a1be392c54
    │     ├── e18f0a777aefabe047a671ab3ec3eed05414477c951ab1a6f352a06974245fe7
    │     ├── f54a58bc1aac5ea1a25d796ae155dc228b3f0e11d046ae276b39c4bf2f13d8c4
    │     └── feb5d9fea6a5e9606aa995e879d862b825965ba48de054caab5ef356dc6b3412
    ├── index.json
    └── oci-layout
    """

    @classmethod
    def _check_oci_layout(cls, layout_file: pathlib.Path):
        logger.info("check oci-layout")
        assert layout_file.exists() and layout_file.is_file()
        with layout_file.open("r", encoding="utf-8") as f:
            oci_layout = json.load(f)
            image_layout_version = oci_layout.get("imageLayoutVersion")
            assert image_layout_version and image_layout_version == "1.0.0", image_layout_version

    @classmethod
    def _check_index(cls, index_path: pathlib.Path):
        logger.info("check index.json")
        assert index_path.exists() and index_path.is_file()
        with index_path.open("r", encoding="utf-8") as f:  # check json format
            index_content = json.load(f)
        assert index_content["schemaVersion"] == 2
        manifests = index_content.get("manifests")
        assert manifests

    def _check_blobs(self, blobs_path: pathlib.Path, algom: str = "sha256"):
        logger.info(f"check blobs:{blobs_path}/{algom}")
        blobs_dir = blobs_path.joinpath(algom)
        assert blobs_dir.exists() and blobs_dir.is_dir()
        for file in blobs_dir.iterdir():
            assert file.is_file()
            want_digest = f"{algom}:{file.name}"
            self._check_digest(want=want_digest, path=file)

    def check(self):
        oci_layout_file = self.src_dir.joinpath("oci-layout")
        self._check_oci_layout(oci_layout_file)

        index_file = self.src_dir.joinpath("index.json")
        self._check_index(index_path=index_file)
        with index_file.open("r", encoding="utf-8") as f:
            index = spec.Index(**json.load(f))
        manifest = index.manifests[0]
        digest: Digest = manifest.digest
        blob_dir = self.src_dir.joinpath("blobs")
        self._check_blobs(blob_dir, digest.algom.value)

    def do(self) -> pathlib.Path:
        self.check()
        return super(OCIImageTar, self).do()
