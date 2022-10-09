ARG python_version
FROM python:$python_version
WORKDIR /registry_client
COPY dist/*.whl .
RUN python -m pip install *.whl
ENTRYPOINT registry_client

