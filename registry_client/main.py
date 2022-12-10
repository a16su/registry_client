#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/10/4-下午10:16
import pathlib
from typing import Optional, cast

from pydantic import BaseModel
from typer import Argument, BadParameter, Context, Exit, Option, Typer, echo

from registry_client.client import RegistryClient
from registry_client.image import ImageFormat
from registry_client.platforms import OS, Arch, Platform
from registry_client.reference import NamedReference, Reference, parse_normalized_named

app = Typer(name="registry_client")


def version_callback(value: bool):
    if value:
        from registry_client._version import version

        print(f"Registry Client: {version}")
        raise Exit()


def platform_callback(ctx: Context, value: str):
    if ctx.resilient_parsing:
        return
    if value is None:
        return None
    tmp = value.split("/")
    if len(tmp) != 2:
        raise BadParameter("Formatter Error, it should be like linux/amd64")
    os_name, arch_name = tmp
    os_name_list = [one.value for one in OS.__members__.values()]
    arch_name_list = [one.value for one in Arch.__members__.values()]
    if os_name.lower() not in os_name_list:
        raise BadParameter(f"platform.os not in {os_name_list}")
    if arch_name.lower() not in arch_name_list:
        raise BadParameter(f"platform.arch not in {arch_name_list}")
    return Platform(os=OS(os_name), arch=Arch(arch_name))


def platform_complete(incomplete: str):
    if "/" not in incomplete:
        name_list = OS.__members__.values()
    else:
        name_list = Arch.__members__.values()
        incomplete = incomplete.split("/")[-1]
    for item in name_list:
        if item.value.startswith(incomplete):
            yield item.value


def image_name_callback(name: str):
    ref = parse_normalized_named(name)
    return ref


image_name_option = Argument(
    help="image name, like: hello-world:latest|library/hello-world:latest",
    default=...,
    callback=image_name_callback,
)


def new_client(ref: Reference) -> RegistryClient:
    global_options: "GlobalOptions" = Context.global_options
    scheme = "https"
    if global_options.plain_http:
        scheme = "http"
    domain = ref.domain or "registry-1.docker.io"
    return RegistryClient(
        host=f"{scheme}://{domain}",
        username=global_options.username,
        password=global_options.password,
        skip_verify=global_options.ignore_cert_error,
    )


@app.command("list-tags")
def list_tags(
    name: str = image_name_option,
    limit: int = Option(default=None, help="limit return count", min=0),
    last: str = Option(default=None, help="the last tag for pagination"),
):
    ref: Reference = name
    if not isinstance(ref, NamedReference):
        raise BadParameter("No tag or digest allowed in reference")
    client = new_client(ref)
    tags = client.list_tags(image_name=str(ref), limit=limit, last=last)
    echo(tags)


@app.command("inspect")
def inspect_image(
    name: str = image_name_option,
    platform: str = Option(
        None,
        "--platform",
        "-p",
        help="",
        callback=platform_callback,
        autocompletion=platform_complete,
    ),
):
    ref: Reference = cast(Reference, name)
    client = new_client(ref)
    image_config = client.inspect_image(str(ref), platform=platform)
    echo(image_config.json())


@app.command("pull")
def pull_image(
    name: str = image_name_option,
    platform: str = Option(
        None,
        "--platform",
        "-p",
        help="default linux/amd64, exec `docker info -f '{{.OSType}}/{{.Architecture}}'` to view",
        callback=platform_callback,
        autocompletion=platform_complete,
    ),
    image_format: ImageFormat = Option(ImageFormat.V2.value, "--format", "-f"),
    save_to: pathlib.Path = Option(..., help="save image to which dir"),
    just_download: bool = Option(False, help="just download image config and layer, don't tar them to image"),
):
    want_platform: Optional[Platform] = platform
    if save_to.exists() and not save_to.is_dir():
        raise BadParameter(f"param:save_to({save_to}) must be a directory")
    ref = name
    client = new_client(ref)
    image_path = client.pull_image(
        image_name=str(ref),
        save_dir=save_to,
        image_format=image_format,
        platform=platform,
    )
    echo(f"image save to {image_path}")


@app.command("tar")
def tar_to_image(
    image_dir: pathlib.Path = Option(..., "--image-dir", "-C", help="image config and layer dir"),
    save_to: pathlib.Path = Option(..., "--output", "-o", help="save image to"),
    image_format: ImageFormat = Option(ImageFormat.V2.value, "--format", "-f"),
    compress: bool = Option(False, "-z", help="compress image by gzip"),
):
    if not image_dir.exists():
        raise BadParameter(f"{image_dir} doesn't exists")
    if not image_dir.is_dir():
        raise BadParameter(f"{image_dir} must be a directory")
    if save_to.exists() and save_to.is_dir():
        raise BadParameter(f"image outfile: {save_to} can't be a directory")
    echo(f"will tar image_dir {image_dir} to image {save_to}, format is {image_format.value}")
    image_dir = image_dir.absolute()
    save_to = save_to.absolute()
    if image_format == ImageFormat.V2:
        config_json = image_dir.joinpath("manifest.json")
        assert config_json.exists() and config_json.is_file()


class GlobalOptions(BaseModel):
    ignore_cert_error: bool = False
    plain_http: bool = False
    username: str = ""
    password: str = ""


@app.callback()
def main(
    version: Optional[bool] = Option(None, "--version", callback=version_callback, is_eager=True),
    ignore_cert_error: bool = Option(False, help="either ignore server cert error"),
    plain_http: bool = Option(False, help="allow connections using plain HTTP"),
    username: str = Option("", help="registry username"),
    password: str = Option("", help="registry password", hide_input=True),
):
    Context.global_options = GlobalOptions(
        ignore_cert_error=ignore_cert_error,
        plain_http=plain_http,
        username=username,
        password=password,
    )
