#!/usr/bin/env bash

curl -sSL https://dot.net/v1/dotnet-install.sh -o dotnet-install.sh
bash dotnet-install.sh --version 10.0.401 --install-dir "$PWD" --no-path
rm dotnet-install.sh
