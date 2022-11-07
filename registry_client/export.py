import gzip
import json
import os
import pathlib
import shutil
import tarfile
from typing import List

from loguru import logger

from registry_client.digest import Digest

BZIP_MAGIC = b"\x42\x5A\x68"
GZIP_MAGIC = b"\x1F\x8B\x8B"
XZ_MAGIC = b"\xFD\x37\x7A\x58\x5A\x00"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


class TarImageDir:
    def __init__(self, src_dir: pathlib.Path, target_path: pathlib.Path, delete: bool = False, compress: bool = False):
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

    @staticmethod
    def _check_digest(want: str, path: pathlib.Path):
        want_digest = Digest(want)
        with open(path, "rb") as f:
            get_digest = Digest.from_bytes(f.read())
        assert want_digest == get_digest, f"{get_digest}!={want_digest}"

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
        with image_config_path.open("r", encoding="utf-8") as f:
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
    Tar directory to oci format image
    """

    pass
