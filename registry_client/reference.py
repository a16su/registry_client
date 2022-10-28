#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午2:52
from dataclasses import dataclass
from typing import ClassVar

import re2

from registry_client.digest import Digest

NameTotalLengthMax = 255
reference_regexp = re2.compile(
    "^((?:(?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])(?:(?:\\.(?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]))+)?(?::[0-9]+)?/)?[a-z0-9]+(?:(?:(?:[._]|__|[-]*)[a-z0-9]+)+)?(?:(?:/[a-z0-9]+(?:(?:(?:[._]|__|[-]*)[a-z0-9]+)+)?)+)?)(?::([\\w][\\w.-]{0,127}))?(?:@([A-Za-z][A-Za-z0-9]*(?:[-_+.][A-Za-z][A-Za-z0-9]*)*[:][[:xdigit:]]{32,}))?$"
)
anchored_name_regexp = re2.compile(
    "^(?:((?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])(?:(?:\\.(?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]))+)?(?::[0-9]+)?)/)?([a-z0-9]+(?:(?:(?:[._]|__|[-]*)[a-z0-9]+)+)?(?:(?:/[a-z0-9]+(?:(?:(?:[._]|__|[-]*)[a-z0-9]+)+)?)+)?)$"
)


@dataclass
class Repository:
    domain: str = ""
    path: str = ""

    def name(self):
        if self.domain == "":
            return self.path
        return f"{self.domain}/{self.path}"


@dataclass
class Reference:
    repository: Repository
    tag: str = ""
    digest: Digest = ""
    is_named_only: ClassVar[bool] = True
    is_named_tagged: ClassVar[bool] = False
    is_named_digested: ClassVar[bool] = False

    @property
    def path(self):
        return self.repository.path


@dataclass
class TagReference(Reference):
    is_named_only: ClassVar[bool] = False
    is_named_tagged: ClassVar[bool] = True
    is_named_digested: ClassVar[bool] = False

    def __str__(self):
        return f"{self.repository.name()}:{self.tag}"


@dataclass
class DigestReference(Reference):
    is_named_only: ClassVar[bool] = False
    is_named_tagged: ClassVar[bool] = False
    is_named_digested: ClassVar[bool] = True

    def __str__(self):
        return f"{self.repository.name()}@{self.digest}"


def parse(name: str) -> Reference:
    """
    Parse parses s and returns a syntactically valid Reference.
    If an error was encountered it is returned, along with a nil Reference.
    NOTE: Parse will not handle short digests.
    :param name:
    :return:
    """
    result = reference_regexp.findall(name)
    if not result:
        raise Exception("invalid reference format")
    if len(result[0]) > NameTotalLengthMax:
        raise Exception(f"repository name must not be more than {NameTotalLengthMax} characters")
    result = result[0]
    name_match = anchored_name_regexp.findall(result[0])[0]
    if len(name_match) == 2:
        domain, path = name_match
    else:
        domain = ""
        path = name_match[-1]
    repo = Repository(domain, path)
    if result[1]:
        return TagReference(repository=repo, tag=result[1])
    elif result[2]:
        if not Digest.is_digest(result[2]):
            raise Exception(f"invalid digest format: {result[2]}")
        return DigestReference(repository=repo, digest=Digest(result[2]))
    return Reference(repository=repo)
