import hashlib
from collections import UserString
from enum import Enum
from typing import Any, Callable, Union

import re2

DIGEST_REGEX = re2.compile(r"sha(256|384|512):[a-z0-9]{64}")


class Algorithm(Enum):
    SHA384 = "sha384"
    SHA512 = "sha512"
    SHA256 = "sha256"


DEFAULT_ALGORITHM = Algorithm.SHA256


class Digest(UserString):
    def __init__(self, seq):
        super(Digest, self).__init__(seq)
        self._algorithm, self._hash = self.data.split(":")
        self._algorithm = Algorithm(self._algorithm)

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
        return DIGEST_REGEX.match(value)

    def validate_bytes(self, content: bytes, algorithm: Algorithm = DEFAULT_ALGORITHM):
        new_digest = self.from_bytes(content, algorithm)
        return self == new_digest
