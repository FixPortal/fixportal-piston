#!/usr/bin/env bash

# Relocatable prebuilt CPython instead of compiling from source.
curl -sSL "https://github.com/astral-sh/python-build-standalone/releases/download/20261001/cpython-3.13.16+20261001-x86_64-unknown-linux-gnu-install_only.tar.gz" -o python.tar.gz
tar xzf python.tar.gz --strip-components=1
rm python.tar.gz
