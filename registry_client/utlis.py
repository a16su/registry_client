import hashlib
import re
from typing import List

from registry_client import reference

IMAGE_DEFAULT_TAG: str = "latest"
DEFAULT_REPO: str = "library"
DEFAULT_REGISTRY_HOST: str = "registry-1.docker.io"
DEFAULT_CLIENT_ID = "registry-python-client"
INDEX_NAME = "docker.io"


def split_docker_domain(name: str):
    index = name.find("/")
    if index == -1 or (not re.findall(r"[.:]", name[:index]) and name[:index] != "localhost"):
        domain, remainder = DEFAULT_REGISTRY_HOST, name
    else:
        domain, remainder = name[:index], name[index + 1 :]
    if domain == "index.docker.io":
        domain = DEFAULT_REGISTRY_HOST
    if domain == DEFAULT_REGISTRY_HOST and "/" not in remainder:
        remainder = f"{DEFAULT_REPO}/{remainder}"
    return domain, remainder


def parse_normalized_named(name: str) -> reference.Reference:
    if re.match(r"^([a-f0-9]{64})$", name):
        raise Exception(f"invalid repository name ({name}), cannot specify 64-byte hexadecimal strings")
    domain, remainder = split_docker_domain(name)
    if remainder.find(":") != -1:
        remote_name = remainder.partition(":")[0]
    else:
        remote_name = remainder
    if not remote_name.islower():
        raise Exception("invalid reference format: repository name must be lowercase")
    return reference.parse(f"{domain}/{remainder}")


def get_chain_id(parent: str, ids: List[str]) -> str:
    if not ids:
        return parent
    if parent == "":
        return get_chain_id(ids[0], ids[1:])
    value = hashlib.sha256(f"{parent} {ids[0]}".encode()).hexdigest()
    value = f"sha256:{value}"
    return get_chain_id(value, ids[1:])


def diff_ids_to_chain_ids(diff_ids: List[str]) -> List[str]:
    assert diff_ids
    result = [diff_ids[0]]
    parent = ""
    for diff_id in diff_ids[1:]:
        result.append(get_chain_id(result[-1], [diff_id]))
    return result


# def v1_image_id(layer_id: str, parent: str, v1image: "V1Image" = None) -> str:
#     config = {"created": "1970-01-01T08:00:00+08:00", "layer_id": layer_id}
#     if parent != "":
#         config["parent"] = parent
#     return f"sha256:{hashlib.sha256(str(config).encode()).hexdigest()}"


# class V1Image(BaseModel):
#     id: Optional[str]
#     parent: Optional[str]
#     comment: Optional[str]
#     created: Optional[str]
#     container: Optional[str]
#     container_config: Optional[str]
#     docker_version: Optional[str]
#     author: Optional[str]
#     config: Optional[str]
#     architecture: Optional[str]
#     variant: Optional[str]
#     os: Optional[str]
#     size: Optional[float]
if __name__ == "__main__":
    parse_normalized_named("127.0.0.1:8000/library/hello")
