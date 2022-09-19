from dataclasses import dataclass, asdict

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "official: mark docker official registry test")
    config.addinivalue_line("markers", "mirror: mark docker mirror registry test")
    config.addinivalue_line("markers", "harbor: mark custom harbor registry test")


@dataclass
class BaseConfig:
    host: str = ""
    username: str = ""
    password: str = ""
    scheme: str = "https"


@dataclass
class DockerOfficialConfig(BaseConfig):
    host: str = "registry-1.docker.io"


@dataclass
class DockerMirrorConfig(BaseConfig):
    host: str = "hub-mirror.c.163.com"
    scheme: str = "http"


@dataclass
class HarborMirrorConfig(BaseConfig):
    host: str = ""
    scheme: str = "http"


@pytest.fixture(scope="session")
def docker_official_config():
    return asdict(DockerOfficialConfig())


@pytest.fixture(scope="session")
def docker_mirror_config():
    return asdict(DockerMirrorConfig())


@pytest.fixture(scope="session")
def harbor_config():
    return asdict(HarborMirrorConfig())


if __name__ == "__main__":
    print(HarborMirrorConfig().host)
