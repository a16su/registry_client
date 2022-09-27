import pathlib
from typing import Dict

import pytest

from registry_client.client import RegistryClient
from registry_client.image import ImagePullOptions
from tests.conftest import HarborMirrorConfig


class TestImagePull:
    def _pull_image(
            self,
            config: Dict,
            temp_dir: pathlib.Path,
            image_name,
            repo="library",
            tag="latest",
    ):
        client = RegistryClient()
        reg = client.registry(**config)
        img = reg.image(repo, image_name)
        image_path = img.pull(ImagePullOptions(
            reference=tag, save_dir=temp_dir
        ))
        assert image_path.exists() and image_path.is_file()

    @pytest.mark.official
    def test_pull_docker_official_image(self, docker_official_config, tmp_path):
        self._pull_image(docker_official_config, tmp_path, "hello-world")

    @pytest.mark.mirror
    def test_pull_docker_mirror_image(self, docker_mirror_config, tmp_path):
        self._pull_image(docker_mirror_config, tmp_path, "hello-world")

    @pytest.mark.skipif(HarborMirrorConfig().host == "", reason="harbor not config, skip")
    @pytest.mark.harbor
    def test_pull_harbor_image(
            self,
    ):
        pass
