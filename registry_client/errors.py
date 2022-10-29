#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/27-下午4:36
class ImageNotFoundError(Exception):
    def __init__(self, image_name):
        super(ImageNotFoundError, self).__init__(f"Image {image_name} not Found")


class ImageManifestCheckError(Exception):
    def __init__(self):
        super(ImageManifestCheckError, self).__init__("image manifest check error")


class ErrReferenceInvalidFormat(Exception):
    def __init__(self):
        super(ErrReferenceInvalidFormat, self).__init__("invalid reference format")


class ErrTagInvalidFormat(Exception):
    def __init__(self):
        super(ErrTagInvalidFormat, self).__init__("invalid tag format")


class ErrDigestInvalidFormat(Exception):
    def __init__(self):
        super(ErrDigestInvalidFormat, self).__init__("invalid digest format")


class ErrNameContainsUppercase(Exception):
    def __init__(self):
        super(ErrNameContainsUppercase, self).__init__("repository name must be lowercase")


class ErrNameEmpty(Exception):
    def __init__(self):
        super(ErrNameEmpty, self).__init__("repository name must have at least one component")


class ErrNameTooLong(Exception):
    def __init__(self):
        super(ErrNameTooLong, self).__init__("repository name must not be more than 255 characters")


class ErrNameNotCanonical(Exception):
    def __init__(self):
        super(ErrNameNotCanonical, self).__init__("repository name must be canonical")


class ErrDigestInvalidLength(Exception):
    def __init__(self):
        super(ErrDigestInvalidLength, self).__init__("invalid checksum digest length")


class ErrDigestUnsupported(Exception):
    def __init__(self):
        super(ErrDigestUnsupported, self).__init__("unsupported digest algorithm")


if __name__ == "__main__":
    raise ErrNameEmpty()
