# Contributing

Issues and pull requests are welcome. This repository is derived from
[engineer-man/piston](https://github.com/engineer-man/piston), trimmed to the two
runtimes the FixPortal learning portal uses (.NET 10 C# and Python 3.13). Fixes to
those runtimes, the sandbox and the API are in scope; reviving upstream's other
language packages is not.

## Checking a change

Build the image, start it, and run the smoke test, which is what CI runs:

```bash
docker build -t fixportal-piston:local .
```

```bash
docker run --privileged -d -p 127.0.0.1:2000:2000 --tmpfs /tmp:exec --name piston fixportal-piston:local
```

```bash
python3 scripts/smoke.py
```

Changes to isolate arguments, limits, the entrypoint or a runtime's scripts change what
submitted code can reach. Say so in the pull request and describe what you verified.

## Pull requests

Pull requests target `main` and are merged by rebase. `CI Gate` and
`Review policy intact` must pass.
