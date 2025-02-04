#!/usr/bin/env sh

set -o errexit
set -o nounset

## NOTE: Bump this version when a new release.
VERSION="0.6.5"
OS=$(uname -s| tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m| tr '[:upper:]' '[:lower:]')
if [ "${ARCH}" = "aarch64" ] ; then
    ARCH_SUFFIX=arm64
elif [ "${ARCH}" = "x86_64" ] ; then
    ARCH_SUFFIX=amd64
elif [ "${ARCH}" = "arm64" ] ; then
    ARCH_SUFFIX=arm64
else
    echo "Unsupported architecture: ${ARCH}"
    exit 1
fi

URL="https://github.com/elastic/terranova/releases/download/${VERSION}/terranova-${VERSION}-${OS}-${ARCH_SUFFIX}"

LOCATION="/usr/local/bin"
curl -sSLo "$LOCATION/terranova" "$URL"
chmod +x "$LOCATION/terranova"
