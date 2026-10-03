# AGENTS.md

Repo-specific conventions for agents working in `fixportal-piston`.

## What this is

A sandboxed code runner for the FixPortal learning portal, derived from Piston.
Only two runtimes are supported and baked into the image: `csharp` (.NET 10.0.401)
and `python` (3.13.16). The other directories under `packages/` are upstream's and are
not built, shipped or tested; do not fix them up.

## The image is the product

- The root `Dockerfile` is the only image definition. `.dockerignore` is an
  allow-list: a new file the image needs must be added there explicitly.
- Runtimes are installed at build time by `scripts/install-package.sh`, never through
  `ppman` or upstream's package index.
- Every runtime download is verified against a digest hardcoded in its `build.sh`,
  checked against the downloaded bytes when it was set. Bump URL and digest together;
  never fetch "latest" or an install script at build time.
- Upstream's registries (`ghcr.io/engineer-man/piston`, its package index) are not
  dependencies. Do not reintroduce them.

## Sandbox changes are security changes

Anything that alters what a submission can reach is HIGH tier: isolate arguments and
limits in `api/src/job.js` and `api/src/config.js`, `api/src/docker-entrypoint.sh`,
the container's privileges, and the baked-in packages' `compile`, `run` and
`environment` scripts. Run the smoke test after any such change.

## Checking a change

```bash
docker build -t fixportal-piston:local .
```

```bash
docker run --privileged -d -p 127.0.0.1:2000:2000 --tmpfs /tmp:exec --name piston fixportal-piston:local
```

```bash
python3 scripts/smoke.py
```

`scripts/smoke.py` is what CI runs. It asserts both runtimes work and that the sandbox
holds: wall-clock kill, no network, no writes outside the box.

## Known traps

- .NET under isolate needs `DOTNET_EnableWriteXorExecute=0`. Without it the runtime's
  W^X double-mapping exceeds isolate's `--fsize` limit and the process aborts with
  `Out of memory` before `Main`.
- C# compiles by calling Roslyn's `csc.dll` directly against the reference pack;
  `dotnet build` works but costs about 2s more per submission in MSBuild evaluation.
- The entrypoint chowns only `/piston` and `/piston/packages`, not recursively. The
  packages are owned by `piston` at build time, and a recursive chown of the SDK made
  every cold start take about a minute.
