# Third-party notices

## Piston

This repository is derived from [engineer-man/piston](https://github.com/engineer-man/piston),
a general purpose code execution engine, and keeps its full commit history. Piston is
licensed under the MIT licence; the original copyright notice and licence text are
retained in [`license`](license).

> Copyright (c) 2018-2021 Brian Seymour, Thomas Hobson, EMKC Contributors

FixPortal's changes (the bookworm image, the baked-in .NET 10 and Python 3.13 packages,
the smoke test and the CI) are released under the same MIT licence.

## isolate

The image builds [isolate](https://github.com/ioi/isolate) from the
[envicutor/isolate](https://github.com/envicutor/isolate) fork at a pinned commit, as
upstream Piston does. isolate is licensed under the GNU GPL, version 2 or later; it is compiled into the
image as a separate executable and is not linked into this repository's code.

## Runtimes

The image downloads, at build time:

- the .NET SDK via Microsoft's `dotnet-install.sh` (MIT);
- CPython from [astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone)
  (CPython is under the PSF licence; the build tooling is MPL-2.0).
