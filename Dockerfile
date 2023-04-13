FROM mysocietyorg/debian:bullseye
RUN apt-get update && \
    apt-get install python3-distutils python3-pip libxml2-dev libxslt-dev python-dev -y && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 1
COPY requirements.txt requirements.dev.txt /tmp/
RUN pip install -r /tmp/requirements.txt -r /tmp/requirements.dev.txt
