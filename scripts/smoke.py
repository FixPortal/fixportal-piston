"""Smoke-test a running Piston image: both runtimes work and the sandbox holds.

Usage: python3 scripts/smoke.py [base-url]   (default http://127.0.0.1:2000)

Stdlib only, so CI needs no install step. Exits non-zero on the first failed
check, printing every result so a red run says which property broke.
"""

import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:2000"
CSHARP = ("csharp", "10.0.401")
PYTHON = ("python", "3.13.16")


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
        "network is unreachable from the sandbox",
        PYTHON,
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('https://example.com', timeout=5)\n"
        "    print('reached')\n"
        "except Exception:\n"
        "    print('blocked')\n",
        lambda r: r["run"]["stdout"].strip() == "blocked",
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

    print(f"{len(CHECKS) + 1 - failed}/{len(CHECKS) + 1} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
