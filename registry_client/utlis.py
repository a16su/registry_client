import hashlib
import pathlib
import platform
from typing import Dict, Generator, Iterable, List, Union

from pydantic import BaseModel

IMAGE_DEFAULT_TAG: str = "latest"
DEFAULT_REPO: str = "library"
DEFAULT_REGISTRY_HOST: str = "registry-1.docker.io"
DEFAULT_CLIENT_ID = "registry-python-client"
INDEX_NAME = "docker.io"


def get_chain_id(parent: str, ids: List[str]) -> str:
    if not ids:
        return parent
    if parent == "":
        return get_chain_id(ids[0], ids[1:])
    value = hashlib.sha256(f"{parent} {ids[0]}".encode()).hexdigest()
    value = f"sha256:{value}"
    return get_chain_id(value, ids[1:])


def diff_ids_to_chain_ids(diff_ids: Iterable[Union[str, "Digest"]]) -> Generator[str, None, None]:
    assert diff_ids
    parent = ""
    for diff_id in diff_ids:
        chain_id = get_chain_id(parent=parent, ids=[(str(diff_id))])
        parent = chain_id
        yield chain_id


def get_cpu_info() -> List[Dict[str, str]]:
    assert platform.system().lower() == "linux"
    cpu_info: str = pathlib.Path("/proc/cpuinfo").read_text()
    result = []
    for one_core in cpu_info.split("\n\n"):
        core_info = {}
        for info in one_core.split("\n"):
            info_split = info.split(":")
            if len(info_split) == 2:
                key, value = info_split
            else:
                key = info_split[0]
                value = ""
            core_info[key.strip()] = value.strip()
        result.append(core_info)
    return result


class CustomModel(BaseModel):
    class Config:
        from registry_client.digest import Digest

        json_encoders = {Digest: str}

    def json(self, *args, **kwargs):
        if kwargs.get("by_alias") is None:
            kwargs["by_alias"] = True
        return super(CustomModel, self).json(*args, **kwargs)


# def v1_image_id(layer_id: str, parent: str, v1image: "V1Image" = None) -> str:
#     config = {"created": "1970-01-01T08:00:00+08:00", "layer_id": layer_id}
#     if parent != "":
#         config["parent"] = parent
#     return f"sha256:{hashlib.sha256(str(config).encode()).hexdigest()}"
