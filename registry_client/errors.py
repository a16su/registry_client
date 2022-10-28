#!/usr/bin/env python3
# encoding : utf-8
# create at: 2022/9/27-下午4:36
class ImageNotFoundError(Exception):
    def __init__(self, image_name):
        super(ImageNotFoundError, self).__init__(f"Image {image_name} not Found")


class ImageManifestCheckError(Exception):
    def __init__(self):
        super(ImageManifestCheckError, self).__init__("image manifest check error")
