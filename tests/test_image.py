import httpx
import pytest

from registry_client import errors, spec
from registry_client.digest import Digest
from registry_client.reference import (
    CanonicalReference,
    DigestReference,
    TaggedReference,
    parse_normalized_named,
)

DEFAULT_IMAGE_NAME = "library/hello-world"


class TestImage:
    @pytest.mark.parametrize(
        "count, last",
        (
            (1, None),
            (None, "latest"),
            (1, "latest"),
        ),
    )
    def test_list_tag(self, image_client, registry_tags, count, last):
        tags = {"tags": ["foo", "bar"]}

        def check_request(request: httpx.Request, repo, name, action):
            params = request.url.params
            if count:
                assert params.get("n") == str(count)
            if last:
                assert params.get("last") == last

            assert repo == "library"
            assert name == "hello-world"
            assert action == "list"
            return httpx.Response(status_code=200, json=tags)

        registry_tags.side_effect = check_request
        resp = image_client.list_tag(parse_normalized_named("hello-world"), limit=count, last=last)
        assert resp.json() == tags

    def test_delete_image(self, image_client, registry_manifest):
        def delete_image_side_effect(request: httpx.Request, repo, name, target: str):
            assert request.method == "DELETE"
            return httpx.Response(200, json={"target": target})

        registry_manifest.side_effect = delete_image_side_effect
        target_digest = Digest.from_bytes(b"123")
        ref = CanonicalReference(path="library/repo", digest=target_digest)
        resp = image_client.delete(ref)
        assert resp.json()["target"] == target_digest.value

    @pytest.mark.parametrize("image_name", ("hello-world:latest", f"hello-world@sha256:{'f' * 64}"))
    def test_manifest_head(self, image_client, registry_manifest, image_name):
        def check_req(request, repo, name, target):
            assert request.method == "HEAD"
            assert image_name.endswith(target)
            return httpx.Response(200)

        registry_manifest.side_effect = check_req
        image_client.exist(parse_normalized_named(image_name))

    def test_get_config(self, image_client, registry_blobs):
        d = Digest.from_bytes(b"")

        def check_req(request, repo, name, digest):
            assert request.method == "GET"
            assert digest == d.value
            return httpx.Response(200)

        registry_blobs.side_effect = check_req
        image_client.get_config(CanonicalReference(path="library/hello-world", digest=d))

    @pytest.mark.parametrize(
        "ref, want",
        (
            (DigestReference(Digest.from_bytes(b"")), Digest.from_bytes(b"")),
            (CanonicalReference(path="foo/bar", digest=Digest.from_bytes(b"1")), Digest.from_bytes(b"1")),
        ),
    )
    def test_get_manifest_digest_with_digest_ref(self, image_client, registry_manifest, ref, want):
        assert image_client.get_manifest_digest(ref) == want
        assert not registry_manifest.called

    def test_get_manifest_digest_with_tag_ref(self, image_client, registry_manifest):
        want = Digest.from_bytes(b"123")
        registry_manifest.return_value = httpx.Response(200, headers={"docker-content-digest": want.value})
        assert image_client.get_manifest_digest(TaggedReference(path="foo/bar", tag="latest")) == want

    def test_get_manifest_digest_exception(self, image_client, registry_manifest):
        registry_manifest.return_value = httpx.Response(404)
        with pytest.raises(errors.ImageNotFoundError):
            image_client.get_manifest_digest(parse_normalized_named("foo/bar"))

    def test_get_manifest_digest_from_resp_content(self, image_client, registry_manifest):
        resp_content = b"abc"
        registry_manifest.return_value = httpx.Response(200, content=resp_content)
        get_d = image_client.get_manifest_digest(parse_normalized_named("foo/bar"))
        assert get_d == Digest.from_bytes(resp_content)
