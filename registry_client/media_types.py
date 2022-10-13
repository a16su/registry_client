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


# https://github.com/containerd/containerd/raw/main/vendor/github.com/opencontainers/image-spec/specs-go/v1/mediatype.go
class OCIImageMediaType(Enum):
    MediaTypeDescriptor = "application/vnd.oci.descriptor.v1+json"
    MediaTypeLayoutHeader = "application/vnd.oci.layout.header.v1+json"
    MediaTypeImageManifest = "application/vnd.oci.image.manifest.v1+json"
    MediaTypeImageIndex = "application/vnd.oci.image.index.v1+json"
    MediaTypeImageLayer = "application/vnd.oci.image.layer.v1.tar"
    MediaTypeImageLayerGzip = "application/vnd.oci.image.layer.v1.tar+gzip"
    MediaTypeImageLayerZstd = "application/vnd.oci.image.layer.v1.tar+zstd"
    MediaTypeImageLayerNonDistributable = "application/vnd.oci.image.layer.nondistributable.v1.tar"
    MediaTypeImageLayerNonDistributableGzip = "application/vnd.oci.image.layer.nondistributable.v1.tar+gzip"
    MediaTypeImageLayerNonDistributableZstd = "application/vnd.oci.image.layer.nondistributable.v1.tar+zstd"
    MediaTypeImageConfig = "application/vnd.oci.image.config.v1+json"
