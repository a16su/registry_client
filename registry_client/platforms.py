import functools
import json
import pathlib
import platform
import re
from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel

from registry_client import spec
from registry_client.utlis import get_cpu_info

DEFAULT_SYSTEM = platform.system().lower()
DEFAULT_ARCH = platform.machine().lower()
specifier_regex = re.compile("^[A-Za-z0-9_-]+$")


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


def get_cpu_variant() -> Optional[str]:
    """
    arm only
    Returns:

    """
    if DEFAULT_SYSTEM == "windows" or DEFAULT_SYSTEM == "darwin":
        if DEFAULT_ARCH == "arm64":
            return "v8"
        elif DEFAULT_ARCH == "arm":
            return "v7"
        return "unknown"
    cpu_info = get_cpu_info()
    variant = ""
    for one in cpu_info:
        if one.get("Cpu architecture"):
            variant = one.get("Cpu architecture")
            break
    else:
        return variant
    if DEFAULT_ARCH == "arm" and variant == "7":
        for one in cpu_info:
            model = one.get("model name")
            if model and model.lower().startswith("armv6-compatible"):
                variant = "6"
    if variant in ("8", "aarch64"):
        return "v8"
    elif variant in ("7", "7m", "?(12)", "?(13)", "?(14)", "?(15)", "?(16)", "?(17)"):
        return "v7"
    elif variant in ("6", "6tej"):
        return "v6"
    elif variant in ("5", "5t", "5te", "5tej"):
        return "v5"
    elif variant in ("4", "4t"):
        return "v4"
    elif variant == "3":
        return "v3"
    return None


def is_known_arch(arch: str):
    return arch in (
        "386",
        "amd64",
        "amd64p32",
        "arm",
        "armbe",
        "arm64",
        "arm64be",
        "ppc64",
        "ppc64le",
        "loong64",
        "mips",
        "mipsle",
        "mips64",
        "mips64le",
        "mips64p32",
        "mips64p32le",
        "ppc",
        "riscv",
        "riscv64",
        "s390",
        "s390x",
        "sparc",
        "sparc64",
        "wasm",
    )


def normalize_os(os: str):
    if os == "":
        return DEFAULT_SYSTEM
    os = os.lower()
    if os == "macos":
        return "darwin"
    return os


def is_known_os(os: str) -> bool:
    return os in (
        "aix",
        "android",
        "darwin",
        "dragonfly",
        "freebsd",
        "hurd",
        "illumos",
        "ios",
        "js",
        "linux",
        "nacl",
        "netbsd",
        "openbsd",
        "plan9",
        "solaris",
        "windows",
        "zos",
    )


def normalize_arch(arch: str, variant: str) -> Tuple[str, str]:
    arch, variant = arch.lower(), variant.lower()
    if arch == "i386":
        arch, variant = "386", ""
    elif arch in ("x86_64", "x86-64", "amd64"):
        arch = "amd64"
        if variant == "v1":
            variant = ""
    elif arch in ("aarch64", "arm64"):
        arch = "arm64"
        if variant in ("8", "v8"):
            variant = ""
    elif arch == "armhf":
        arch = "arm"
        variant = "v7"
    elif arch == "armel":
        arch = "arm"
        variant = "v6"
    elif arch == "arm":
        if variant == "" or variant == "7":
            variant = "v7"
        elif variant in ("5", "6", "8"):
            variant = "v" + variant
    return arch, variant


# vendor/github.com/containerd/containerd/platforms/database.go:83
class Platform(BaseModel):
    os: str = ""
    architecture: str = ""
    variant: Optional[str] = ""
    os_features: Optional[List[str]] = []
    os_version: Optional[str] = ""

    def __eq__(self, other: "Platform"):
        if other.__class__.__name__ != self.__class__.__name__:
            raise TypeError(f"unsupported operand type(s) for ==: 'Platform' and '{type(other)}'")
        return self.os == other.os and self.architecture == other.architecture and self.variant == other.variant

    def __ne__(self, other):
        return not self.__eq__(other)

    def dict(self, *args, **kwargs):

        data = super(Platform, self).dict(*args, **kwargs)
        if data["variant"] is None:
            del data["variant"]
        return data

    def json(self, *args, **kwargs) -> str:
        data = {"os": self.os, "architecture": self.architecture}
        if self.variant is not None:
            data["variant"] = self.variant
        return json.dumps(data)


def platform_vector(p: Platform) -> List[Platform]:
    vector: List[Platform] = []
    if p.architecture == "amd64":
        if p.variant.strip("v").isnumeric():
            amd64_version = int(p.variant.strip("v"))
            if amd64_version > 1:
                while amd64_version >= 1:
                    vector.append(
                        Platform(
                            os=p.os,
                            os_version=p.os_version,
                            os_features=p.os_features,
                            variant=f"v{amd64_version}",
                            architecture=p.architecture,
                        )
                    )
                    amd64_version -= 1
        vector.append(
            Platform(
                os=p.os,
                os_version=p.os_version,
                os_features=p.os_features,
                architecture="386",
            )
        )
    elif p.architecture == "arm":
        if p.variant.strip("v").isnumeric():
            arm_version = int(p.variant.strip("v"))
            if arm_version > 5:
                while arm_version >= 5:
                    vector.append(
                        Platform(
                            os=p.os,
                            os_version=p.os_version,
                            os_features=p.os_features,
                            variant=f"v{arm_version}",
                            architecture=p.architecture,
                        )
                    )
                    arm_version -= 1
    elif p.architecture == "arm64":
        variant = p.variant or "v8"
        vector.append(
            Platform(
                architecture="arm",
                os=p.os,
                os_version=p.os_version,
                os_features=p.os_features,
                variant=variant,
            )
        )
    return vector


def only_match(p_list: List[Platform], p: Platform) -> bool:
    """
    For arm/v8, will also match arm/v7, arm/v6 and arm/v5
    For arm/v7, will also match arm/v6 and arm/v5
    For arm/v6, will also match arm/v5
    For amd64, will also match 386
    """
    for one in p_list:
        if one == p:
            return True
    return False


def platform_normalize(plat: Platform) -> Platform:
    plat.os = normalize_os(plat.os)
    plat.architecture, plat.variant = normalize_arch(plat.architecture, plat.variant)
    return plat


def maximum_spec():
    """
    returns the distribution platform with maximum compatibility for the current node.
    """
    p = Platform(
        os=DEFAULT_SYSTEM,
        architecture=normalize_arch(DEFAULT_ARCH, "")[0],
        variant=get_cpu_variant(),
    )
    if p.architecture == "amd64":
        p.variant = "v3"  # fixme
    return p


def with_default(p: Platform):
    d = maximum_spec()
    if p.os == "":
        p.os = d.os

    if p.architecture == "":
        p.architecture = d.architecture
        p.variant = d.variant
    return p


def check_image_compatibility(image_os_version: str):
    """
    windows only
    Args:
        image_os_version:

    Returns:
        bool
    """
    if image_os_version is None:
        return True
    host_osv = platform.version().split(".")
    split_image_version = image_os_version.split(".")
    if len(split_image_version) == 3:
        build = int(split_image_version[2])
        if build > int(host_osv[2]):
            return False
    return True


def filter_by_platform(
    manifests: List["spec.Descriptor"], target_platform: Optional[Platform] = None
) -> List["spec.Descriptor"]:
    # if target_platform is None:
    #     return manifests[0].digest
    # for manifest in manifests:
    #     if manifest.platform == target_platform:
    #         return manifest.digest
    # else:
    #     raise Exception("Not Found Matching image")
    if platform.system().lower() == "windows":
        result = []
        found_windows_match = False
        for desc in manifests:
            if desc.platform.architecture == DEFAULT_ARCH and (
                (target_platform.os != "" and desc.platform.os == target_platform.os)
                or (target_platform.os == "" and desc.platform.os.lower() == DEFAULT_SYSTEM.lower())
            ):
                if desc.platform.os.lower() == "windows":
                    if not check_image_compatibility(desc.platform.os_version):
                        continue
                    found_windows_match = True
                result.append(desc)
        if found_windows_match:
            version = platform.version()

            def windows_sort_by_version(a: "spec.Descriptor", b: "spec.Descriptor"):
                return (a.platform.os.lower() == "windows" and b.platform.os.lower() != "windows") or (
                    a.platform.os_version.startswith(version + ".")
                    and not b.platform.os_version.startswith(version + ".")
                )

            return sorted(result, key=functools.cmp_to_key(windows_sort_by_version))
        return result
    else:

        target_platform = target_platform if target_platform is not None else Platform()
        targets = [
            platform_normalize(one) for one in platform_vector(platform_normalize(with_default(target_platform)))
        ]
        result = filter(lambda p: only_match(targets, p.platform), manifests)

        def sort_func(a: "spec.Descriptor", b: "spec.Descriptor"):
            a_result = only_match(targets, a.platform)
            b_result = only_match(targets, b.platform)
            if a_result and not b_result:
                return -1
            elif a_result or b_result:
                return 1

        return sorted(result, key=functools.cmp_to_key(sort_func))


def parse(specifier: str) -> Platform:
    if "*" in specifier:
        raise Exception("wildcards not yet supported")
    parts = specifier.split("/")
    for part in parts:
        if not specifier_regex.match(part):
            raise Exception(
                f"{part} is an invalid component of {specifier}:  platform specifier component must match{specifier_regex.pattern}"
            )
    p_len = len(parts)
    p = Platform()
    if p_len == 1:
        p.os = normalize_os(parts[0])
        if is_known_os(p.os):
            p.architecture = DEFAULT_ARCH
            if p.architecture == "arm" and get_cpu_variant() != "v7":
                p.variant = get_cpu_variant()
            return p
        p.architecture, p.variant = normalize_arch(parts[0], "")
        if p.architecture == "arm" and p.variant == "v7":
            p.variant = ""
        if is_known_arch(p.architecture):
            p.os = DEFAULT_SYSTEM
            return p
        raise Exception(f"unknown operating system or architecture: {specifier}")
    elif p_len == 2:
        p.os = normalize_os(parts[0])
        p.architecture, p.variant = normalize_arch(parts[1], "")
        if p.architecture == "arm" and p.variant == "v7":
            p.variant = ""
        return p
    elif p_len == 3:
        p.os = normalize_os(parts[0])
        p.architecture, p.variant = normalize_arch(parts[1], parts[2])
        if p.architecture == "arm64" and p.variant == "":
            p.variant = "v8"
        return p
    raise Exception(f"cannot parse platform specifier{specifier}")
