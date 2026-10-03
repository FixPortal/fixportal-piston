#!/usr/bin/env bash
set -euo pipefail

# Relocatable prebuilt CPython instead of compiling from source. The digest is
# hardcoded and was checked against the downloaded bytes, not just copied from
# the release's SHA256SUMS. Bump URL and digest together.
url="https://github.com/astral-sh/python-build-standalone/releases/download/20261001/cpython-3.13.16+20261001-x86_64-unknown-linux-gnu-install_only.tar.gz"
sha256="b55f90dfb060e998a47e4a811dae46aaa27b923244044bbcf88de5e57a5fa4c7"

curl --fail --silent --show-error --location "$url" -o python.tar.gz
echo "${sha256}  python.tar.gz" | sha256sum --check --strict
tar xzf python.tar.gz --strip-components=1
rm python.tar.gz
