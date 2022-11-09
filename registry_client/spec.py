# https://github.com/opencontainers/image-spec
import datetime
import typing
from enum import Enum

from pydantic import Field, validator

from registry_client.digest import Digest
from registry_client.media_types import ImageMediaType, OCIImageMediaType
from registry_client.platforms import Platform
from registry_client.utlis import CustomModel

ImageLayoutFile = "oci-layout"
ImageLayoutVersion = "1.0.0"


class AnnotationsKey(Enum):
    AnnotationCreated = "org.opencontainers.image.created"
    AnnotationAuthors = "org.opencontainers.image.authors"
    AnnotationURL = "org.opencontainers.image.url"
    AnnotationDocumentation = "org.opencontainers.image.documentation"
    AnnotationSource = "org.opencontainers.image.source"
    AnnotationVersion = "org.opencontainers.image.version"
    AnnotationRevision = "org.opencontainers.image.revision"
    AnnotationVendor = "org.opencontainers.image.vendor"
    AnnotationLicenses = "org.opencontainers.image.licenses"
    AnnotationRefName = "org.opencontainers.image.ref.name"
    AnnotationTitle = "org.opencontainers.image.title"
    AnnotationDescription = "org.opencontainers.image.description"
    AnnotationBaseImageDigest = "org.opencontainers.image.base.digest"
    AnnotationBaseImageName = "org.opencontainers.image.base.name"
    AnnotationArtifactCreated = "org.opencontainers.artifact.created"
    AnnotationArtifactDescription = "org.opencontainers.artifact.description"
    AnnotationReferrersFiltersApplied = "org.opencontainers.referrers.filtersApplied"


Annotations = typing.Dict[typing.Union[str, AnnotationsKey], str]


class ImageLayout(CustomModel):
    image_layout_version: str = Field(default=ImageLayoutVersion, alias="imageLayoutVersion")


class Descriptor(CustomModel):
    media_type: typing.Union[ImageMediaType, OCIImageMediaType] = Field(alias="mediaType")
    digest: Digest
    size: int
    urls: typing.Optional[typing.List[str]]
    annotations: typing.Optional[Annotations]
    artifact_type: typing.Optional[str] = Field(alias="artifactType")
    platform: typing.Optional[Platform]


class Artifact(CustomModel):
    media_type: typing.Union[ImageMediaType, OCIImageMediaType] = Field(alias="mediaType")
    artifact_type: str = Field(alias="artifactType")
    blobs: typing.Optional[typing.List[Descriptor]]
    subject: typing.Optional[Descriptor]
    annotations: typing.Optional[Annotations]


class Manifest(CustomModel):
    schema_version: int = Field(alias="schemaVersion", default=2)
    media_type: typing.Union[ImageMediaType, OCIImageMediaType] = Field(alias="mediaType")
    config: Descriptor
    layers: typing.List[Descriptor]
    subject: typing.Optional[Descriptor]
    annotations: typing.Optional[Annotations]


class Index(CustomModel):
    schema_version: int = Field(alias="schemaVersion", default=2)
    media_type: typing.Optional[typing.Union[ImageMediaType, OCIImageMediaType]] = Field(alias="mediaType")
    manifests: typing.List[Descriptor]

    @validator("schema_version")
    def _validate_schema_version(cls, value):
        assert value == 2


class ImageConfig(CustomModel):
    user: typing.Optional[str] = Field(alias="User")
    exposed_ports: typing.Optional[typing.Dict[str, typing.Any]] = Field(alias="ExposedPorts")
    env: typing.Optional[typing.List[str]] = Field(alias="Env")
    entry_point: typing.Optional[typing.List[str]] = Field(alias="Entrypoint")
    cmd: typing.Optional[typing.List[str]] = Field(alias="cmd")
    volumes: typing.Optional[typing.Dict[str, typing.Any]] = Field(alias="Volumes")
    labels: typing.Optional[typing.Dict[str, str]] = Field(alias="Labels")
    working_dir: typing.Optional[str] = Field(alias="WorkingDir")
    stop_signal: typing.Optional[str] = Field(alias="StopSignal")
    args_escaped: typing.Optional[bool] = Field(alias="ArgsEscaped")


class RootFs(CustomModel):
    type: str
    diff_ids: typing.List[Digest]


class History(CustomModel):
    created: typing.Optional[datetime.datetime]
    create_by: typing.Optional[str]
    author: typing.Optional[str]
    comment: typing.Optional[str]
    empty_layer: typing.Optional[str]


class Image(CustomModel):
    created: typing.Optional[datetime.datetime]
    author: typing.Optional[str]
    architecture: str
    variant: typing.Optional[str]
    os: str
    os_version: typing.Optional[str] = Field(alias="os.version")
    os_features: typing.Optional[typing.List[str]] = Field(alias="os.features")
    config: typing.Optional[ImageConfig]
    rootfs: RootFs
    history: typing.Optional[typing.List[History]]


if __name__ == "__main__":
    a = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "size": 7023,
            "digest": "sha256:b5b2b2c507a0944348e0303114d8d93aaaa081732b86451d9bce1f432a537bc7",
        },
        "layers": [
            {
                "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                "size": 32654,
                "digest": "sha256:9834876dcfb05cb167a5c24953eba58c4ac89b1adf57f28f2f9d09af107ee8f0",
            },
            {
                "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                "size": 16724,
                "digest": "sha256:3c3a4604a545cdc127456d94e421cd355bca5b528f4a9c1905b15da2eb4a4c6b",
            },
            {
                "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                "size": 73109,
                "digest": "sha256:ec4b8955958665577945c89419d1af06b5f7636b4ac3da7f12184802ad867736",
            },
        ],
        "subject": {
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "size": 7682,
            "digest": "sha256:5b0bcabd1ed22e9fb1310cf6c2dec7cdef19f0ad69efa1f392e94a4333501270",
        },
        "annotations": {"com.example.key1": "value1", "com.example.key2": "value2"},
    }
    m = Manifest(**a)
    print(m.json(exclude_none=True))
