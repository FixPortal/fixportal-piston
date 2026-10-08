"""Smoke-test a running Piston image: both runtimes work and the sandbox holds.

Usage: python3 scripts/smoke.py [base-url]   (default http://127.0.0.1:2000)

Stdlib only, so CI needs no install step. Exits non-zero on the first failed
check, printing every result so a red run says which property broke.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:2000"
CSHARP = ("csharp", "10.0.401")
PYTHON = ("python", "3.13.16")
CONTAINER = os.environ.get("PISTON_CONTAINER", "piston")
_cleanup_check_skipped = False


def execute(runtime, code):
    language, version = runtime
    body = json.dumps(
        {"language": language, "version": version, "files": [{"content": code}]}
    ).encode()
    request = urllib.request.Request(
        f"{BASE}/api/v2/execute",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def malformed_json_is_a_bare_400():
    """A bad request body gets a 400 that names the problem but leaks no stack trace."""
    request = urllib.request.Request(
        f"{BASE}/api/v2/execute",
        data=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(request, timeout=10)
        return False, "expected HTTP 400, got 2xx"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            return False, f"HTTP {e.code}, not JSON: {body[:300]}"
        # Exactly one field, a message that names no internal path (stack frames
        # always carry one). body-parser's own text says "at position N"; that is fine.
        ok = (
            e.code == 400
            and isinstance(parsed, dict)
            and set(parsed) == {"message"}
            and isinstance(parsed["message"], str)
            and parsed["message"]
            and "/" not in parsed["message"]
        )
        return ok, f"HTTP {e.code}: {body[:300]}"


def oversized_body_is_a_413_that_says_so():
    """The status and the message must agree: too large is not a JSON syntax problem."""
    request = urllib.request.Request(
        f"{BASE}/api/v2/execute",
        data=b'{"pad":"' + b"x" * 300_000 + b'"}',
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(request, timeout=10)
        return False, "expected HTTP 413, got 2xx"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        ok = e.code == 413 and "too large" in body and "    at " not in body
        return ok, f"HTTP {e.code}: {body[:300]}"


def cleanup_finished_before_response(check_name):
    """After a CHECKS response, no isolate box may remain.

    Returns (counted, failed). A docker failure is printed once as SKIP and
    is not counted.
    """
    global _cleanup_check_skipped
    if _cleanup_check_skipped:
        return 0, 0

    try:
        completed = subprocess.run(
            [
                "docker",
                "exec",
                CONTAINER,
                "sh",
                "-c",
                "ls -A /var/local/lib/isolate",
            ],
            capture_output=True,
            text=True,
        )
    except OSError as error:
        _cleanup_check_skipped = True
        print(f"SKIP cleanup check: {error}")
        return 0, 0

    if completed.returncode != 0:
        _cleanup_check_skipped = True
        reason = completed.stderr.strip() or f"exit {completed.returncode}"
        print(f"SKIP cleanup check: {reason}")
        return 0, 0

    if completed.stdout.strip():
        print(f"FAIL cleanup finished before the response: {check_name}")
        print(completed.stdout.rstrip())
        return 1, 1

    print(f"PASS cleanup finished before the response: {check_name}")
    return 1, 0


def wait_for_api(deadline_seconds=60):
    deadline = time.monotonic() + deadline_seconds
    while True:
        try:
            with urllib.request.urlopen(f"{BASE}/api/v2/runtimes", timeout=5) as r:
                return json.load(r)
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)


CHECKS = [
    (
        "C# compiles and runs current language features",
        CSHARP,
        "int[] values = [1, 2, 3];\n"
        "Console.WriteLine(new Point(values.Length, values.Sum()) == new Point(3, 6) ? \"OK\" : \"FAIL\");\n"
        "record Point(int X, int Y);\n",
        lambda r: r["compile"]["code"] == 0 and r["run"]["stdout"].strip() == "OK",
    ),
    (
        "C# compile error reports the diagnostic",
        CSHARP,
        "Console.WriteLine(undefinedThing);\n",
        lambda r: r["compile"]["code"] != 0 and "CS0103" in r["compile"]["output"],
    ),
    (
        "Python runs",
        PYTHON,
        "print(sum([1, 2, 3]))\n",
        lambda r: r["run"]["code"] == 0 and r["run"]["stdout"].strip() == "6",
    ),
    (
        "infinite loop is killed by the wall-clock limit",
        PYTHON,
        "while True: pass\n",
        lambda r: r["run"]["status"] == "TO",
    ),
    (
        # Structural, not "a request failed": any error (HTTP, TLS, timeout)
        # would otherwise pass. The box must have no interface but loopback,
        # and a connect to a raw IP must fail with ENETUNREACH specifically.
        "network namespace has only loopback",
        PYTHON,
        "import errno, socket\n"
        "ifaces = [l.split(':')[0].strip() for l in open('/proc/net/dev').readlines()[2:]]\n"
        "print('ifaces=' + ','.join(sorted(ifaces)))\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 443), timeout=3)\n"
        "    print('connect=CONNECTED')\n"
        "except OSError as e:\n"
        "    print('connect=' + str(errno.errorcode.get(e.errno, e.errno)))\n",
        lambda r: r["run"]["stdout"].split() == ["ifaces=lo", "connect=ENETUNREACH"],
    ),
    (
        "writes outside the box are denied",
        PYTHON,
        "import os\n"
        "for p in ['/piston/packages/pwned', '/etc/pwned']:\n"
        "    try:\n"
        "        open(p, 'w').write('x'); print('wrote', p)\n"
        "    except OSError:\n"
        "        print('denied')\n",
        lambda r: r["run"]["stdout"].split() == ["denied", "denied"],
    ),
]


def main():
    runtimes = {(r["language"], r["version"]) for r in wait_for_api()}
    expected = {("csharp.net", CSHARP[1]), ("python", PYTHON[1])}
    failed = 0
    cleanup_total = 0
    if not expected <= runtimes:
        print(f"FAIL runtimes: expected {sorted(expected)}, got {sorted(runtimes)}")
        failed += 1

    for name, runtime, code, passed in CHECKS:
        started = time.monotonic()
        result = execute(runtime, code)
        elapsed = time.monotonic() - started
        ok = passed(result)
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'} {name} ({elapsed:.2f}s)")
        if not ok:
            print(json.dumps(result, indent=1))

        counted, cleanup_failed = cleanup_finished_before_response(name)
        cleanup_total += counted
        failed += cleanup_failed

    ok, detail = malformed_json_is_a_bare_400()
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'} malformed JSON is a 400 without a stack trace")
    if not ok:
        print(detail)

    ok, detail = oversized_body_is_a_413_that_says_so()
    failed += not ok
    print(f"{'PASS' if ok else 'FAIL'} oversized body is a 413 whose message says so")
    if not ok:
        print(detail)

    total = len(CHECKS) + 3 + cleanup_total
    print(f"{total - failed}/{total} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
