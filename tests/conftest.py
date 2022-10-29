import os
import shutil

import docker
import pytest

from registry_client.client import RegistryClient
from registry_client.digest import Digest
from registry_client.image import BlobClient, ImageClient
from registry_client.manifest import ManifestClient
from registry_client.repo import RepoClient
from tests.docker_hub_client import DockerHubClient
from tests.local_docker import LocalDockerChecker


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
        "--registry-ignore_cert_error",
        action="store_true",
        default=False,
        dest="ignore_cert_error",
        help="ignore registry certificate errors",
    )
    group.addoption(
        "--registry-proxy", action="store", default="", dest="registry_proxy", help="the proxy used to connect registry"
    )


@pytest.fixture(scope="session")
def docker_registry_client(pytestconfig: pytest.Config) -> RegistryClient:
    host = pytestconfig.option.registry_host
    username = pytestconfig.option.registry_username
    password = pytestconfig.option.registry_password
    ignore_cert_error = pytestconfig.option.ignore_cert_error
    info_from_env = {
        "host": os.environ.get("REGISTRY_HOST"),
        "username": os.environ.get("REGISTRY_USERNAME"),
        "password": os.environ.get("REGISTRY_PASSWORD"),
        "skip_verify": ignore_cert_error,
    }
    if host:
        info_from_env["host"] = host
    if username:
        info_from_env["username"] = username
    if password:
        info_from_env["password"] = password
    return RegistryClient(**info_from_env)


@pytest.fixture(scope="session")
def repo_client(docker_registry_client):
    return RepoClient(docker_registry_client.client)


@pytest.fixture(scope="session")
def image_client(docker_registry_client):
    return ImageClient(docker_registry_client.client)


@pytest.fixture(scope="session")
def manifest_client(docker_registry_client):
    return ManifestClient(docker_registry_client.client)


@pytest.fixture(scope="session")
def blob_client(docker_registry_client):
    return BlobClient(docker_registry_client.client)


@pytest.fixture(scope="session")
def docker_hub_client() -> DockerHubClient:
    return DockerHubClient()


@pytest.fixture(scope="function")
def docker_image(docker_registry):
    return docker_registry.image


@pytest.fixture(scope="session")
def local_docker():
    return docker.from_env()


@pytest.fixture(scope="function")
def image_save_dir(tmp_path):
    yield tmp_path
    shutil.rmtree(tmp_path)


@pytest.fixture(scope="function")
def image_checker():
    checker = LocalDockerChecker()
    yield checker
    if checker.image:
        checker.image.remove(force=True)


@pytest.fixture(scope="function")
def random_digest():
    return Digest.from_bytes(os.urandom(1))
