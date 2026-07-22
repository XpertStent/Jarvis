FROM python:3.12-alpine

ARG BUILD_VERSION=1.0.0
ARG BUILD_ARCH=amd64

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="addon" \
  io.hass.arch="${BUILD_ARCH}"

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apk add --no-cache ca-certificates

COPY requirements.txt /opt/jarvis/requirements.txt
RUN python -m pip install --upgrade pip
RUN python3 -m pip install --no-cache-dir -r /opt/jarvis/requirements.txt

COPY default_main.py /opt/jarvis/default_main.py
COPY run.sh /run.sh

RUN chmod a+x /run.sh

CMD ["/run.sh"]