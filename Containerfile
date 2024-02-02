# Base image for build
ARG base_image_version=3.10.12
FROM python:${base_image_version}-bullseye as builder

# Switch workdir
WORKDIR /opt/terranova

# Arguments
ARG platform_arch
ARG app_version

# Copy files
COPY . .

# Install poetry
RUN \
  pip3 install --no-cache-dir --upgrade pip poetry

# Build
RUN \
  poetry install \
  && poetry run pyinstaller terranova.spec \
  && mv /opt/terranova/dist/terranova /opt/terranova/dist/terranova-${app_version}-${platform_arch}
