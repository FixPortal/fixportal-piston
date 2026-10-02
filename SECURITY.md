# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via
[GitHub Security Advisories](https://github.com/FixPortal/fixportal-piston/security/advisories/new)
rather than opening a public issue. A minimal submission (language, version and source)
that reproduces the problem is the most useful evidence.

You should receive an acknowledgement within a few days. Please allow a reasonable
window to investigate and ship a fix before any public disclosure.

## Attack surface

This service executes untrusted code. Its security-relevant surface is the sandbox:

- **isolate confinement**: process, file-size, open-file, wall-clock and CPU limits;
  the directories mounted into each box; and network isolation.
- **The container**: it runs `--privileged` so isolate can create cgroups and
  namespaces. It must only be reachable from a trusted caller (the portal API on an
  internal network), never exposed directly.
- **Baked-in runtimes**: the environment variables and scripts each runtime runs inside
  the box.

An escape from a box, a way to reach the network or another submission's files, or a
way to exhaust the host past the configured limits is in scope.

## Supported versions

Only the latest `main` is supported.
