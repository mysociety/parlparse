FROM mysocietyorg/debian:bookworm
RUN apt-get update && \
    apt-get install python3-distutils python3-pip libxml2-dev libxslt-dev python-dev-is-python3 libffi-dev -y && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

ENV POETRY_VERSION 2.2.1
RUN curl -sSL https://install.python-poetry.org | /usr/bin/python3 -
ENV PATH="/root/.local/bin:$PATH"

ENV PYTHONPATH=$PYTHONPATH:/usr/lib/python3.11/site-packages

COPY pyproject.toml poetry.loc[k] /tmp/pyproject/
RUN cd /tmp/pyproject && poetry install