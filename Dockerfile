FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        calibre \
        ca-certificates \
        python3 \
        python3-venv \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir watchdog==6.0.0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:/usr/bin:$PATH"

WORKDIR /app
COPY app/ /app/

ENTRYPOINT ["python3", "/app/watch_epubs.py"]
