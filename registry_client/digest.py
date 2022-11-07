import hashlib
import re
from collections import UserString
from enum import Enum
from typing import Any, Callable, Union

from registry_client import errors

DIGEST_REGEX = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-_+.][A-Za-z][A-Za-z0-9]*)*[:][a-fA-F0-9]{32,}")

DIGEST_SIZE = {
    "sha256": 32,
    "sha384": 48,
    "sha512": 64,
}


class Algorithm(Enum):
    SHA384 = "sha384"
    SHA512 = "sha512"
    SHA256 = "sha256"

    def validate(self, encode: str):
        size = DIGEST_SIZE[self.value] * 2
        if size != len(encode):
            raise errors.ErrDigestInvalidLength()
        if not re.findall(f"^[a-f0-9]{{{size},}}$", encode):
            return errors.ErrDigestInvalidFormat()


DEFAULT_ALGORITHM = Algorithm.SHA256


class Digest(UserString):
    def __init__(self, seq):
        super(Digest, self).__init__(seq)
        _algorithm, self._hash = self.data.split(":")
        self._algorithm = Algorithm(_algorithm)

    @classmethod
    def __get_validators__(cls):
        # one or more validators may be yielded which will be called in the
        # order to validate the input, each validator will receive as an input
        # the value returned from the previous validator
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not cls.is_digest(v):
            raise ValueError("invalid postcode format")
        return cls(v)

    @classmethod
    def _get_hasher(cls, algom: Algorithm) -> Callable[[Union[str, bytes]], Any]:
        hash_func = getattr(hashlib, algom.value, None)
        if hash_func is None:
            raise Exception(f"Error Hash Algorithm: {algom}")
        return hash_func

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
        return self.data

    @classmethod
    def from_bytes(cls, content: bytes, algorithm: Algorithm = DEFAULT_ALGORITHM):
        hash_func = cls._get_hasher(algorithm)
        hash_value = hash_func(content).hexdigest()
        return Digest(f"{algorithm.value}:{hash_value}")

    @classmethod
    def is_digest(cls, value: Union[str, "Digest"]):
        if isinstance(value, Digest):
            return True
        index = value.find(":")
        if index == -1 or index == len(value) - 1:
            raise errors.ErrDigestInvalidFormat()
        match = DIGEST_REGEX.findall(value)
        if not match:
            raise errors.ErrDigestInvalidFormat()
        algm, hex_value = match[0].split(":", 1)
        a: Algorithm = Algorithm._value2member_map_.get(algm)
        if not a:
            raise errors.ErrDigestUnsupported()
        a.validate(hex_value)
        return True

    def validate_bytes(self, content: bytes, algorithm: Algorithm = DEFAULT_ALGORITHM):
        new_digest = self.from_bytes(content, algorithm)
        return self == new_digest
