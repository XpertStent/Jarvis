FROM python:3.12-alpine

ARG BUILD_VERSION=2.0.1
ARG BUILD_ARCH=amd64

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="addon" \
  io.hass.arch="${BUILD_ARCH}"

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apk add --no-cache ca-certificates

COPY requirements.txt /opt/jarvis/requirements.txt
RUN python3 -m pip install --upgrade pip setuptools wheel \
    && python3 -m pip install --no-cache-dir -r /opt/jarvis/requirements.txt

COPY default_backend.py /opt/jarvis/default_backend.py
COPY default_frontend.html /opt/jarvis/default_frontend.html
COPY run.sh /run.sh

RUN chmod a+x /run.sh

CMD ["/run.sh"]
