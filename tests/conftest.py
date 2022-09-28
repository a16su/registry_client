import pytest
from loguru import logger

from registry_client.client import RegistryClient
from registry_client.registry import Registry
from tests.docker_hub_client import DockerHubClient


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("registry_client")
    group.addoption(
        "--registry-host",
        action="store",
        default="https://registry-1.docker.io",
        dest="registry_host",
        help="the docker registry host for test",
    )
    group.addoption(
        "--registry-username",
        action="store",
        default="",
        dest="registry_username",
        help="the docker registry username for test",
    )
    group.addoption(
        "--registry-password",
        action="store",
        default="",
        dest="registry_password",
        help="the docker registry password for test",
    )
    group.addoption(
        "--registry-ignore-certificate-errors",
        action="store_true",
        default=False,
        dest="ignore-certificate-errors",
        help="ignore registry certificate errors",
    )


@pytest.fixture(scope="session")
def docker_registry_client():
    return RegistryClient()


@pytest.fixture(scope="session")
def docker_registry(pytestconfig: pytest.Config, docker_registry_client) -> Registry:
    host = pytestconfig.option.registry_host
    username = pytestconfig.option.registry_username
    password = pytestconfig.option.registry_password
    logger.info(f"host: {host}, username: {username}, password: {password}")
    return docker_registry_client.registry(host=host, username=username, password=password)


@pytest.fixture(scope="session")
def docker_hub_client() -> DockerHubClient:
    return DockerHubClient()


@pytest.fixture(scope="function")
def docker_image(docker_registry):
    return docker_registry.image
