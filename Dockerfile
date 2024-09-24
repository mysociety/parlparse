FROM mysocietyorg/debian:bullseye
RUN apt-get update && \
    apt-get install python3-distutils python3-pip libxml2-dev libxslt-dev python-dev libffi-dev -y && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1 && \
    pip install --upgrade pip

RUN curl -sSL https://install.python-poetry.org | /usr/bin/python3 -
ENV PATH="/root/.local/bin:$PATH"

ENV PYTHONPATH=$PYTHONPATH:/usr/lib/python3.9/site-packages
ENV POETRY_VIRTUALENVS_CREATE=false

COPY pyproject.toml poetry.loc[k] /tmp/pyproject/
RUN cd /tmp/pyproject && poetry install