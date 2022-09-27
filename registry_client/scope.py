#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/24-下午6:46

from dataclasses import dataclass


@dataclass
class Scope:
    pass


@dataclass
class EmptyScope(Scope):
    def __str__(self):
        return ""


@dataclass
class RepositoryScope(Scope):
    repo_name: str
    actions: list[str]
    class_name: str = ""

    def __str__(self) -> str:
        repo_type = "repository"
        if self.class_name != "" and self.class_name != "image":
            repo_type = f"{repo_type}({self.class_name})"
        return f"{repo_type}:{self.repo_name}:{','.join(self.actions)}"


@dataclass
class RegistryScope(Scope):
    rs_name: str
    actions: list[str]

    def __str__(self) -> str:
        return f"registry:{self.rs_name}:{','.join(self.actions)}"
