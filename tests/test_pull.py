import pathlib
from typing import Dict
from src.client import ImageClient


class TestImagePull:
    def _pull_image(
        self,
        config: Dict,
        temp_dir: pathlib.Path,
        image_name,
        repo="library",
        tag="latest",
    ):
        client = ImageClient(**config)
        client.pull_image(image_name, repo, tag, save_dir=temp_dir)
        assert temp_dir.joinpath("library_hello-world.tar").exists()

    def test_pull_docker_official_image(self, docker_official_config, tmp_path):
        self._pull_image(docker_official_config, tmp_path, "hello-world")

    def test_pull_docker_mirror_image(self, docker_mirror_config, tmp_path):
        self._pull_image(docker_mirror_config, tmp_path, "python", "library", "latest")
