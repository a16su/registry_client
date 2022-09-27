import platform
from enum import Enum
from typing import Optional

from pydantic import BaseModel

DEFAULT_SYSTEM = platform.system().lower()
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


# vendor/github.com/containerd/containerd/platforms/database.go:83
class Platform(BaseModel):
    os: OS = OS(DEFAULT_SYSTEM)
    architecture: Arch = Arch(DEFAULT_MACHINE)
    variant: Optional[Variant] = Variant.Unknown

    def __eq__(self, other: "Platform"):
        return self.os == other.os and self.architecture == other.architecture

    def __ne__(self, other):
        return not self.__eq__(other)


if __name__ == "__main__":
    # print(Platform(os="Linux", architecture="x86_64", variant=""))
    print(Arch("x86_64").value)
