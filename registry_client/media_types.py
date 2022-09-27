#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/19-下午5:25
from enum import Enum


class V1ImageMediaType(Enum):
    MediaTypeImageLayer = "application/vnd.oci.image.layer.v1.tar"
    MediaTypeImageLayerGzip = "application/vnd.oci.image.layer.v1.tar+gzip"


class ImageMediaType(Enum):
    MediaTypeDockerSchema2Layer = "application/vnd.docker.image.rootfs.diff.tar"
    MediaTypeDockerSchema2LayerForeign = "application/vnd.docker.image.rootfs.foreign.diff.tar"
    MediaTypeDockerSchema2LayerGzip = "application/vnd.docker.image.rootfs.diff.tar.gzip"
    MediaTypeDockerSchema2LayerForeignGzip = "application/vnd.docker.image.rootfs.foreign.diff.tar.gzip"
    MediaTypeDockerSchema2Config = "application/vnd.docker.container.image.v1+json"
    MediaTypeDockerSchema2Manifest = "application/vnd.docker.distribution.manifest.v2+json"
    MediaTypeDockerSchema2ManifestList = "application/vnd.docker.distribution.manifest.list.v2+json"
    MediaTypeContainerd1Checkpoint = "application/vnd.containerd.container.criu.checkpoint.criu.tar"
    MediaTypeContainerd1CheckpointPreDump = "application/vnd.containerd.container.criu.checkpoint.predump.tar"
    MediaTypeContainerd1Resource = "application/vnd.containerd.container.resource.tar"
    MediaTypeContainerd1RW = "application/vnd.containerd.container.rw.tar"
    MediaTypeContainerd1CheckpointConfig = "application/vnd.containerd.container.checkpoint.config.v1+proto"
    MediaTypeContainerd1CheckpointOptions = "application/vnd.containerd.container.checkpoint.options.v1+proto"
    MediaTypeContainerd1CheckpointRuntimeName = "application/vnd.containerd.container.checkpoint.runtime.name"
    MediaTypeContainerd1CheckpointRuntimeOptions = (
        "application/vnd.containerd.container.checkpoint.runtime.options+proto"
    )
    # Legacy Docker schema1 manifest
    MediaTypeDockerSchema1Manifest = "application/vnd.docker.distribution.manifest.v1+prettyjws"
    # Encypted media types
    MediaTypeImageLayerEncrypted = V1ImageMediaType.MediaTypeImageLayer.value + "+encrypted"
    MediaTypeImageLayerGzipEncrypted = V1ImageMediaType.MediaTypeImageLayerGzip.value + "+encrypted"
