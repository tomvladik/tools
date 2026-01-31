ARG PYTHON_BASE_IMAGE="mcr.microsoft.com/devcontainers/python:3.11-bookworm"
FROM ${PYTHON_BASE_IMAGE}

# Remove Yarn repo to avoid GPG error (some base images add it)
RUN rm -f /etc/apt/sources.list.d/yarn.list || true

# Build args let you pin exact package versions. Example values:
#   --build-arg LIBOPENSHOT_VERSION==0.2.1-3
#   --build-arg FFMPEG_VERSION==7:4.3.3-1~deb11u1
ARG LIBOPENSHOT_VERSION="=0.2.7+dfsg1-4+b1"
ARG FFMPEG_VERSION="=7:5.1.8-0+deb12u1"

RUN set -eux; \
    apt-get update; \
    LIBOPENSHOT_PKG="libopenshot21${LIBOPENSHOT_VERSION}"; \
    LIBOPENSHOT_DEV_PKG="libopenshot-dev${LIBOPENSHOT_VERSION}"; \
    FFMPEG_PKG="ffmpeg${FFMPEG_VERSION}"; \
    apt-get install -y --no-install-recommends \
    ${LIBOPENSHOT_PKG} \
    ${LIBOPENSHOT_DEV_PKG} \
    python3-openshot${LIBOPENSHOT_VERSION} \
    ${FFMPEG_PKG} \
    ca-certificates \
    cmake \
    git \
    build-essential \
    ; \
    rm -rf /var/lib/apt/lists/*;

# Pin pip/tool versions (change these in requirements.txt if needed)
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip && python -m pip install -r /tmp/requirements.txt

WORKDIR /workspace
