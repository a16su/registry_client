import os
import shutil
from typing import NamedTuple

import docker
import httpx
import pytest
import respx

from registry_client.auth import AuthClient, encode_auth
from registry_client.client import RegistryClient
from registry_client.digest import Digest
from registry_client.image import BlobClient, ImageClient
from registry_client.manifest import ManifestClient
from registry_client.repo import RepoClient
from tests.local_docker import LocalDockerChecker

FAKE_REGISTRY_AUTH_HOST = "https://auth-test.registrt-fake.yy"
FAKE_REGISTRY_USERNAME = "foo"
FAKE_REGISTRY_PASSWORD = "bar"


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
        "--registry-proxy",
        action="store",
        default="",
        dest="registry_proxy",
        help="the proxy used to connect registry",
    )


class RegistryInfo(NamedTuple):
    host: str
    username: str = ""
    password: str = ""


@pytest.fixture(scope="session")
def registry_info(pytestconfig: pytest.Config) -> RegistryInfo:
    host = pytestconfig.option.registry_host
    username = pytestconfig.option.registry_username
    password = pytestconfig.option.registry_password
    ignore_cert_error = pytestconfig.option.ignore_cert_error
    info_from_env = {
        "host": os.environ.get("REGISTRY_HOST"),
        "username": os.environ.get("REGISTRY_USERNAME", ""),
        "password": os.environ.get("REGISTRY_PASSWORD", ""),
        "skip_verify": ignore_cert_error,
    }
    if host:
        info_from_env["host"] = host
    if username:
        info_from_env["username"] = username
    if password:
        info_from_env["password"] = password
    return RegistryInfo(
        host=info_from_env["host"],
        username=info_from_env["username"],
        password=info_from_env["password"],
    )


@pytest.fixture(scope="session")
def docker_registry_client(registry_info) -> RegistryClient:
    return RegistryClient(
        host=registry_info.host,
        username=registry_info.username,
        password=registry_info.password,
    )


@pytest.fixture(scope="function")
def auth_client(request: pytest.FixtureRequest, registry_info):
    info = registry_info._asdict()
    info_from_param = request.node.get_closest_marker("registry_info", default=None)
    if info_from_param:
        info.update(info_from_param)
    return AuthClient(base_url=info["host"], auth=(info["username"], info["password"]))


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


@pytest.fixture(scope="function")
def registry_mock(registry_info):
    global FAKE_REGISTRY_USERNAME
    global FAKE_REGISTRY_PASSWORD
    FAKE_REGISTRY_USERNAME = registry_info.username
    FAKE_REGISTRY_PASSWORD = registry_info.password
    with respx.mock(base_url=registry_info.host, assert_all_mocked=False, assert_all_called=False) as registry_mock:
        yield registry_mock


@pytest.fixture(scope="function")
def registry_auth_mock(registry_info):
    with respx.mock(
        base_url=FAKE_REGISTRY_AUTH_HOST, assert_all_mocked=False, assert_all_called=False
    ) as registry_auth_mock:
        yield registry_auth_mock


@pytest.fixture(scope="function")
def registry_auth_root(registry_auth_mock):
    yield registry_auth_mock.route(method="GET", path="/", name="root")


@pytest.fixture(scope="function")
def auth_request_checker(registry_auth_root, monkeypatch):
    def side_effect_gen(
        return_value,
        username="",
        password="",
        scope="",
        service="",
        no_need_auth=False,
        check=True,
    ):
        def side_effect(request_in: httpx.Request) -> httpx.Response:
            if not check:
                return return_value
            auth = request_in.headers.get("Authorization")
            if no_need_auth:
                assert auth is None
            else:
                assert auth == f"Basic {encode_auth(username, password)}"
            params = request_in.url.params
            if scope:
                assert params.get("scope") == str(scope)
            if username:
                assert params.get("account") == username
            if service:
                assert params.get("service") == service
            return return_value

        monkeypatch.setattr(registry_auth_root, "side_effect", side_effect)
        # registry_auth_root.side_effect = side_effect

    return side_effect_gen


@pytest.fixture(scope="function")
def registry_v2(registry_mock):
    yield registry_mock.route(path="/v2/", method="GET", name="v2")


@pytest.fixture(scope="function")
def registry_catalog(registry_mock):
    yield registry_mock.route(path="/v2/_catalog", method="GET", name="catalog")


@pytest.fixture(scope="function")
def registry_tags(registry_mock):
    yield registry_mock.route(path__regex="/v2/(?P<repo>.*?)/(?P<name>.*?)/tags/(?P<action>.*)", name="tags")


@pytest.fixture(scope="function")
def registry_manifest(registry_mock):
    yield registry_mock.route(path__regex="/v2/(?P<repo>.*?)/(?P<name>.*?)/manifests/(?P<target>.*)", name="manifest")
