import platform
from dataclasses import dataclass
from enum import Enum

DEFAULT_SYSTEM = platform.system()
DEFAULT_MACHINE = platform.machine()


class System(Enum):
    Windows = "Windows"
    Linux = "Linux"
    Mac = "Darwin"


class Machine(Enum):
    INTEL_386 = "386"
    ARM = "ARM"
    AMD_64 = "AMD64"
    MIPS_64le = "MIPS64LE"
    ARM_64 = "ARM64"
    S390X = "S390X"
    PPC_64LE = "PPC64LE"
    RISCV_64 = "RISCV64"
    X86_64 = "x86_64"


class CPUVariant(Enum):
    V8 = "v8"
    V7 = "v7"
    V6 = "V6"
    V5 = "v5"
    V4 = "V4"
    V3 = "V3"
    Unknown = None


# vendor/github.com/containerd/containerd/platforms/database.go:83
@dataclass
class Platform:
    os_name: System = System(DEFAULT_SYSTEM)
    arch: Machine = Machine(DEFAULT_MACHINE)
    cpu_variant: CPUVariant = CPUVariant.Unknown
