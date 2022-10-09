import gzip
import os
import pathlib
import tarfile

from loguru import logger

BZIP_MAGIC = b"\x42\x5A\x68"
GZIP_MAGIC = b"\x1F\x8B\x8B"
XZ_MAGIC = b"\xFD\x37\x7A\x58\x5A\x00"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


class DeCompressBase:
    def __init__(self, src: pathlib.Path, save_dir: pathlib.Path = "."):
        self.src = src
        assert self.src.exists()
        save_dir.mkdir(parents=True)
        self.target_path = save_dir.joinpath("layer.tar")

    def do(self) -> pathlib.Path:
        raise NotImplementedError


class GZipDeCompress(DeCompressBase):
    def do(self) -> pathlib.Path:
        logger.info(f"ungzip {self.src} to {self.target_path}")
        with open(self.target_path, "wb") as target:
            g_file = gzip.GzipFile(self.src, mode="rb")
            target.writelines(g_file)
        return self.target_path


class TarImageDir:
    def __init__(self, src_dir: pathlib.Path, target_path: pathlib.Path):
        self.src_dir = src_dir
        assert self.src_dir.exists() and self.src_dir.is_dir()
        self.target_path = target_path
        logger.info(f"{self.src_dir, self.target_path}")
        assert not self.target_path.is_dir()

    def do(self):
        with tarfile.open(self.target_path, "w") as tar_file:
            tar_file.add(self.src_dir, arcname=os.path.sep)


if __name__ == "__main__":
    b = pathlib.Path("./library/hello-world/latest")
    a = TarImageDir(b, b.parent.joinpath("test.tar"))
    a.do()
