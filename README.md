[![Build Status](https://github.com/immortal-n/registry_client/actions/workflows/python-app.yml/badge.svg?branch=master)](https://github.com/immortal-n/registry_client/actions/workflows/python-app.yml/)
## undone...

based on [docker-registry-api](https://docs.docker.com/registry/spec/api/#detail)

#### TODO

- cli
- more image format
- stream transport

### example

#### 1. list tags
```python
from registry_client.client import RegistryClient

client = RegistryClient(host="https://registry-1.docker.io",
                        username="",
                        password="")
tags = client.list_tags("hello-world")
print(tags)
# ['latest', 'linux', 'nanoserver', 'nanoserver-1709', 'nanoserver-1803', 'nanoserver-1809', 'nanoserver-ltsc2022', 'nanoserver-sac2016', 'nanoserver1709']
```
#### 2. list repo
```python
from registry_client.client import RegistryClient

client = RegistryClient(host="https://registry-1.docker.io",
                        username="your_username",
                        password="your_password")
repos = client.catalog()
print(repos)  # ['library/hello-world']
```

#### 3. delete a image
```python
from registry_client.client import RegistryClient

client = RegistryClient(host="https://registry-1.docker.io",
                        username="your_username",
                        password="your_password")
repos = client.delete_image(
    image_name="repo/hello-world@sha256:f54a58bc1aac5ea1a25d796ae155dc228b3f0e11d046ae276b39c4bf2f13d8c4"
)

```