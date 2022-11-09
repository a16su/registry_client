import json
import platform
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

from registry_client.digest import Digest

DEFAULT_SYSTEM = platform.system().lower()
if DEFAULT_SYSTEM == "windows":
    DEFAULT_SYSTEM = "linux"
DEFAULT_MACHINE = platform.machine().lower()


class OS(Enum):
    Windows = "windows"
    Linux = "linux"
    Mac = "darwin"

    def __init__(self, value):
        self._value_ = value.lower()


class Arch(Enum):
    INTEL_386 = "386"
    ARM = "arm"
    AMD_64 = "amd64"
    MIPS_64le = "mips64le"
    ARM_64 = "arm64"
    S390X = "s390x"
    PPC_64LE = "ppc64le"
    RISCV_64 = "riscv64"
    X86_64 = "x86_64"

    def __init__(self, value):
        v_lower = value.lower()
        if v_lower in ["x86_64", "x86-64", "amd64"]:
            self._value_ = "amd64"
        elif v_lower in ["aarch64", "arm64"]:
            self._value_ = "arm64"
        elif v_lower == "armhf":
            self._value_ = "arm"
        else:
            self._value_ = value


class Variant(Enum):
    V8 = "v8"
    V7 = "v7"
    V6 = "v6"
    V5 = "v5"
    V4 = "v4"
    V3 = "v3"
    Unknown = None

    def __init__(self, value):
        if not value:
            self._value_ = None
        else:
            self._value_ = value.lower()

    def __str__(self):
        return self.value


# vendor/github.com/containerd/containerd/platforms/database.go:83
class Platform(BaseModel):
    os: OS = OS(DEFAULT_SYSTEM)
    architecture: Arch = Arch(DEFAULT_MACHINE)
    variant: Optional[Variant] = None
    os_features: Optional[List[str]]

    def __eq__(self, other: "Platform"):
        return self.os == other.os and self.architecture == other.architecture

    def __ne__(self, other):
        return not self.__eq__(other)

    def dict(self, *args, **kwargs):

        data = super(Platform, self).dict(*args, **kwargs)
        if data["variant"] is None:
            del data["variant"]
        return data

    def json(self, *args, **kwargs) -> str:
        data = {"os": self.os.value, "architecture": self.architecture.value}
        if self.variant is not None:
            data["variant"] = self.variant.value
        return json.dumps(data)


def filter_by_platform(manifests: List["Descriptor"], target_platform: Platform) -> Digest:
    if target_platform is None:
        return manifests[0].digest
    for manifest in manifests:
        if manifest.platform == target_platform:
            return manifest.digest
    else:
        raise Exception("Not Found Matching image")
