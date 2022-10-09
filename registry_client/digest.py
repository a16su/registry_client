import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Union

DIGEST_REGEX = re.compile(r"sha(256|384|512):[a-z0-9]{64}")


class Algorithm(Enum):
    SHA384 = "sha384"
    SHA512 = "sha512"
    SHA256 = "sha256"


DEFAULT_ALGORITHM = Algorithm.SHA256


@dataclass
class Digest:
    digest_str: str

    def __post_init__(self):
        self._raw = self.digest_str
        self._algorithm, self._hash = self.digest_str.split(":")
        self._algorithm = Algorithm(self._algorithm)

    @classmethod
    def _get_hasher(cls, algom: Algorithm) -> Callable[[Union[str, bytes]], Any]:
        hash_func = getattr(hashlib, algom.value, None)
        if hash_func is None:
            raise Exception(f"Error Hash Algorithm: {algom}")
        return hash_func

    def __eq__(self, other: "Digest"):
        return self.value == other.value

    def __ne__(self, other: "Digest"):
        return not self == other

    def __str__(self):
        return self.value

    __repr__ = __str__

    @property
    def hex(self) -> str:
        return self._hash

    @property
    def algom(self) -> Algorithm:
        return self._algorithm

    @property
    def short(self) -> str:
        return self._hash[:8]

    @property
    def value(self) -> str:
        return self._raw

    @classmethod
    def from_bytes(cls, content: bytes, algorithm: Algorithm = DEFAULT_ALGORITHM):
        hash_func = cls._get_hasher(algorithm)
        hash_value = hash_func(content).hexdigest()
        return Digest(f"{algorithm.value}:{hash_value}")

    @classmethod
    def is_digest(cls, value: str):
        return DIGEST_REGEX.match(value)

    def validate_bytes(self, content: bytes, algorithm: Algorithm = DEFAULT_ALGORITHM):
        new_digest = self.from_bytes(content, algorithm)
        return self == new_digest


if __name__ == "__main__":
    d = Digest.from_bytes("123".encode())
    print(d.algom)
    print(d.hex)
    print(d.short)
    print(d.value)
    assert d.validate_bytes("123".encode())
