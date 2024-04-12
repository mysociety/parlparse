FROM mysocietyorg/debian:buster
RUN apt-get update && \
    apt-get install python3-distutils python3-pip libxml2-dev libxslt-dev python-dev libffi-dev -y && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1 && \
    pip install --upgrade pip
COPY requirements.txt requirements.dev.txt /tmp/
RUN pip install -r /tmp/requirements.txt -r /tmp/requirements.dev.txt
