# Base image for build
FROM debian:bookworm-slim AS builder

# Switch workdir
WORKDIR /opt/terranova

# Copy files
COPY . .

# Install build packages
RUN \
  apt-get update > /dev/null \
  && apt-get install -y --no-install-recommends \
    binutils="*" \
    ca-certificates="*" \
    curl="*" \
  && apt-get clean

# Install uv
ENV UV_INSTALL_DIR="/opt/uv"
ENV PATH="${UV_INSTALL_DIR}:${PATH}"
RUN \
  curl -LsSf https://astral.sh/uv/install.sh | sh

# Build
RUN \
  uv sync \
  && uv run pyinstaller terranova.spec
