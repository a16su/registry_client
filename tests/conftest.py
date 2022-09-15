from dataclasses import dataclass, asdict

import pytest


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


@pytest.fixture(scope="session")
def docker_official_config():
    return asdict(DockerOfficialConfig())


@pytest.fixture(scope="session")
def docker_mirror_config():
    return asdict(DockerMirrorConfig())
