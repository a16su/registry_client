import os
import pathlib
import gzip
import tarfile

from loguru import logger


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
        logger.info(f"gunzip {self.src} to {self.target_path}")
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
        old_dir = pathlib.Path(".").absolute()
        with tarfile.open(self.target_path, "w") as tar_file:
            os.chdir(self.src_dir)
            for filename in pathlib.Path(".").iterdir():
                logger.info(f"compress {filename}")
                tar_file.add(filename)
        os.chdir(old_dir)


if __name__ == "__main__":
    b = pathlib.Path("./library/hello-world/latest")
    a = TarImageDir(b, b.parent.joinpath("test.tar"))
    a.do()
