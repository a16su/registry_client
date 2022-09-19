import pathlib
from typing import Dict

import pytest

from registry_client.client import ImageClient
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
        client = ImageClient(**config)
        client.pull_image(image_name, repo, tag, save_dir=temp_dir)
        assert temp_dir.joinpath(f"{repo}_{image_name}.tar").exists()

    @pytest.mark.official
    def test_pull_docker_official_image(self, docker_official_config, tmp_path):
        self._pull_image(docker_official_config, tmp_path, "hello-world")

    @pytest.mark.mirror
    def test_pull_docker_mirror_image(self, docker_mirror_config, tmp_path):
        self._pull_image(docker_mirror_config, tmp_path, "hello-world")

    @pytest.mark.skipif(
        HarborMirrorConfig().host == "", reason="harbor not config, skip"
    )
    @pytest.mark.harbor
    def test_pull_harbor_image(
            self,
    ):
        pass
