"""Measure the approved eight-job M6 protocol on a disposable one-slot runner.

Usage: python scripts/measure-tests.py URL CONTAINER OUTPUT_JSON
This is developer evidence, not a learner grader or a CI timing assertion.
"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location("smoke_tests", Path(__file__).with_name("smoke-tests.py"))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
BASE, CONTAINER, OUTPUT = sys.argv[1:]
smoke.BASE = BASE
SOURCES = [
    "return System.Math.Clamp(value, min, max);",
    "return value < min ? value : System.Math.Min(value, max);",
    "return value > max ? value : System.Math.Max(value, min);",
    "return value > min && value < max ? min : System.Math.Clamp(value, min, max);",
]
TESTS = """
using Xunit;
using AwesomeAssertions;
public class ClampTests
{
    [Theory]
    [InlineData(-1, 0)]
    [InlineData(5, 5)]
    [InlineData(11, 10)]
    public void Clamps(int value, int expected)
    {
        Clamper.Clamp(value, 0, 10).Should().Be(expected);
    }
}
"""
EXPECTED_FAILURES = [None, "value: -1", "value: 11", "value: 5"]


def job(subject):
    nonce = secrets.token_hex(16)
    source = "public static class Clamper { public static int Clamp(int value, int min, int max) { " + SOURCES[subject] + " } }"
    started = time.monotonic()
    body = smoke.request("POST", "/api/v2/execute", {
        "language": "csharp-tests", "version": "10.0.401",
        "files": [
            {"name": "Tests", "content": TESTS},
            {"name": "Clamper", "content": source},
            {"name": "Program", "content": smoke.BOOTSTRAP.replace("__NONCE__", nonce)},
        ],
        "args": ["-noLogo", "-noColor", "-noAutoReporters"],
    })
    elapsed = (time.monotonic() - started) * 1000
    assert body["compile"]["code"] == 0 and body["compile"]["signal"] is None, body
    run = body["run"]
    assert run["code"] == (0 if subject == 0 else 1) and run["signal"] is None, body
    lines = run["stdout"].splitlines()
    assert len(lines) == 1 and lines[0].startswith("__M6_TESTS__"), body
    envelope = json.loads(lines[0][len("__M6_TESTS__"):])
    assert envelope["nonce"] == nonce, envelope
    xml = envelope["xml"]
    assert "<!DOCTYPE" not in xml and "<!ENTITY" not in xml
    assembly = ET.fromstring(xml).find("assembly")
    assert assembly is not None and int(assembly.get("total")) == 3, xml
    assert int(assembly.get("skipped")) == 0 and int(assembly.get("errors")) == 0, xml
    tests = assembly.findall("./collection/test")
    failures = [test for test in tests if test.get("result") == "Fail"]
    assert len(failures) == (0 if subject == 0 else 1), xml
    if subject != 0:
        assert EXPECTED_FAILURES[subject] in failures[0].get("name"), xml
        assert failures[0].find("failure").get("exception-type") == "Xunit.Sdk.XunitException", xml
    return {
        "subject": subject, "elapsedMs": round(elapsed, 2), "nonce": nonce,
        "learnerSha256": hashlib.sha256(TESTS.encode()).hexdigest(),
        "inventory": sorted(test.get("name") for test in tests),
        "failed": [test.get("name") for test in failures],
        "compile": {key: body["compile"][key] for key in ("code", "signal", "cpu_time", "wall_time")},
        "run": {key: run[key] for key in ("code", "signal", "cpu_time", "wall_time")},
    }


def schedule(barrier=None):
    if barrier is not None:
        barrier.wait(timeout=20)
    started = time.monotonic()
    jobs = [job(subject) for subject in (0, 0, 1, 2, 3, 1, 2, 3)]
    assert len({row["nonce"] for row in jobs}) == 8
    assert all(row["inventory"] == jobs[0]["inventory"] for row in jobs)
    assert all(jobs[index]["failed"] == jobs[index + 3]["failed"] for index in (2, 3, 4))
    return {"elapsedMs": round((time.monotonic() - started) * 1000, 2), "jobs": jobs}


def quiescent():
    result = subprocess.run(["docker", "exec", CONTAINER, "sh", "-c", "ls -A /var/local/lib/isolate"],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and not result.stdout.strip(), result.stdout + result.stderr


def main():
    assert CONTAINER == "piston-m6-runtime-candidate", "use the dedicated one-slot candidate"
    config = subprocess.run(["docker", "exec", CONTAINER, "printenv", "PISTON_MAX_CONCURRENT_JOBS"],
                            capture_output=True, text=True, timeout=20)
    assert config.returncode == 0 and config.stdout.strip() == "1"
    quiescent()
    evidence = {"base": BASE, "container": CONTAINER, "idle": [], "concurrentSubmitters": [], "error": None}
    try:
        for _ in range(3):
            evidence["idle"].append(schedule())
            quiescent()
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(schedule, barrier) for _ in range(2)]
            evidence["concurrentSubmitters"] = [future.result() for future in futures]
        quiescent()
    except Exception as error:
        evidence["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        Path(OUTPUT).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    for mode in ("idle", "concurrentSubmitters"):
        print(mode, [row["elapsedMs"] for row in evidence[mode]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
