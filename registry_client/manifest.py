#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/27-下午6:40
from typing import Dict

import requests
from loguru import logger

from registry_client.digest import Digest
from registry_client.media_types import ImageMediaType
from registry_client.platforms import Platform


class LayerInfo:
    def __init__(self, info: Dict):
        self.mediaType = ImageMediaType(info["mediaType"])
        self.size = info["size"]
        self.digest = Digest(info["digest"])
        self.platform = Platform(**info["platform"]) if info.get("platform") else None


class ManifestsHandler:
    def __init__(self, resp: requests.Response):
        info = resp.json()
        logger.info(info)
        self.schema_version = info["schemaVersion"]
        self.media_type = ImageMediaType(info.get("mediaType", ImageMediaType.MediaTypeDockerSchema2Manifest.value))
        self.config = LayerInfo(info["config"])
        self.layers = [LayerInfo(one) for one in info["layers"]]


class ManifestsListHandler:
    def __init__(self, resp: requests.Response):
        info = resp.json()
        logger.info(info)
        self.manifests = [LayerInfo(one) for one in info["manifests"]]
        self.media_type = ImageMediaType(info["mediaType"])
        self.schema_version = info["schemaVersion"]

    def filter(self, target_platform: Platform) -> Digest:
        """sample filter"""
        target_platform = target_platform or Platform()
        for manifest in self.manifests:
            if manifest.platform == target_platform:
                target_manifest = manifest
                break
        else:
            raise Exception("Not Found Matching image")
        return target_manifest.digest
