#!/usr/bin/env bash
set -euo pipefail

# The SDK tarball, not dotnet-install.sh: an install script fetched at build
# time runs as root at whatever content it has that day. The digest is
# hardcoded and was checked against the downloaded bytes, not just copied
# from the release metadata. Bump URL and digest together.
url="https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.401/dotnet-sdk-10.0.401-linux-x64.tar.gz"
sha512="51c8b999af9e8dd9998c9edc5944e19a90788862068acd38694e098889054ce8c23d4f0c5cccfa16bf187d044562359e5ee69a9f8ad0bbe913ba90311fbce25b"

curl --fail --silent --show-error --location "$url" -o dotnet.tar.gz
echo "${sha512}  dotnet.tar.gz" | sha512sum --check --strict
tar xzf dotnet.tar.gz
rm dotnet.tar.gz
