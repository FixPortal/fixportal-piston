"""Smoke-test real xUnit discovery in the isolated csharp-tests runtime.

Usage: python scripts/smoke-tests.py [base-url] (default http://127.0.0.1:2000)
Set PISTON_CONTAINER to the dedicated candidate container for cleanup checks.
Missing runtime, missing reports, crashes and empty discovery never pass a theory.
"""

import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:2000"
CONTAINER = os.environ.get("PISTON_CONTAINER", "piston")
LANGUAGE = "csharp-tests"
VERSION = "10.0.401"
USINGS = "using Xunit;\nusing AwesomeAssertions;\n"
BOOTSTRAP = """
internal static class Program
{
    public static int Main(string[] args)
    {
        const string report = "test-results.xml";
        var stdout = System.Console.Out;
        var stderr = System.Console.Error;
        int exitCode;
        System.Console.SetOut(System.IO.TextWriter.Null);
        System.Console.SetError(System.IO.TextWriter.Null);
        try
        {
            exitCode = Xunit.Runner.InProc.SystemConsole.ConsoleRunner
                .Run([.. args, "-result-xml", report]).GetAwaiter().GetResult();
        }
        finally
        {
            System.Console.SetOut(stdout);
            System.Console.SetError(stderr);
        }
        if (new System.IO.FileInfo(report).Length > 65_536)
            throw new System.IO.InvalidDataException("Test report exceeds 65536 bytes.");
        var line = "__M6_TESTS__" + System.Text.Json.JsonSerializer.Serialize(new
        {
            nonce = "__NONCE__",
            xml = System.IO.File.ReadAllText(report)
        });
        if (System.Text.Encoding.UTF8.GetByteCount(line + "\\n") > 65_536)
            throw new System.IO.InvalidDataException("Test report exceeds 65536 bytes.");
        System.Console.WriteLine(line);
        return exitCode;
    }
}
"""
THEORY = USINGS + """
public class ClampTests
{
    [Theory]
    [InlineData(-1, 0)]
    [InlineData(5, 5)]
    [InlineData(11, 10)]
    public void Clamps(int value, int expected)
    {
        System.Math.Clamp(value, 0, 10).Should().Be(expected);
    }
}
"""
FAILING = USINGS + """
public class AssertionTests
{
    [Fact]
    public void FailsAssertion() { (1).Should().Be(2); }
}
"""
EMPTY = "public class NoTests { public int Value() => 1; }"
SKIPPED = USINGS + """
public class SkippedTests
{
    [Fact(Skip = "smoke skip")]
    public void SkippedAssertion() { (1).Should().Be(2); }
}
"""
RESOLUTION = USINGS + """
public class ResolutionTests
{
    [Fact]
    public void LoadsNSubstitute()
    {
        typeof(NSubstitute.Substitute).Assembly.GetName().Name.Should().Be("NSubstitute");
        foreach (var dependency in typeof(NSubstitute.Substitute).Assembly.GetReferencedAssemblies())
            System.Reflection.Assembly.Load(dependency).Should().NotBeNull();
    }
}
"""
SANDBOX = USINGS + """
public class SandboxTests
{
    [Fact]
    public void HasNoDatabaseSocket() { System.IO.Directory.Exists("/pgsock").Should().BeFalse(); }

    [Fact]
    public void HasNoNetwork()
    {
        using var socket = new System.Net.Sockets.Socket(System.Net.Sockets.SocketType.Stream, System.Net.Sockets.ProtocolType.Tcp);
        System.Action connect = () => socket.Connect("1.1.1.1", 443);
        connect.Should().Throw<System.Net.Sockets.SocketException>()
            .Which.SocketErrorCode.Should().Be(System.Net.Sockets.SocketError.NetworkUnreachable);
        System.IO.File.ReadAllLines("/proc/net/dev").Skip(2)
            .Select(line => line.Split(':')[0].Trim()).Should().Equal("lo");
    }

    [Fact]
    public void CannotWriteOutsideTheBox()
    {
        foreach (var path in new[] { "/piston/packages/pwned", "/etc/pwned" })
        {
            System.Action write = () => System.IO.File.WriteAllText(path, "x");
            write.Should().Throw<System.Exception>()
                .Where(error => error is System.UnauthorizedAccessException || error is System.IO.IOException);
        }
    }
}
"""
OVERSIZED_REPORT = """
using Xunit;
public class LargeReportTests(Xunit.ITestOutputHelper output)
{
    [Fact]
    public void ProducesLargeReport() { output.WriteLine(new string('x', 70_000)); }
}
"""


def request(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            assert response.status == 200, response.status
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise AssertionError(f"HTTP {error.code}: {error.read().decode('utf-8', 'replace')}") from error


def cleanup(name):
    completed = subprocess.run(
        ["docker", "exec", CONTAINER, "sh", "-c", "ls -A /var/local/lib/isolate"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr or completed.returncode
    assert not completed.stdout.strip(), completed.stdout
    print(f"PASS cleanup finished before the response: {name}")


def suite(name, source, *, total, passed, failed, skipped, exit_code, filename="Tests"):
    nonce = secrets.token_hex(16)
    body = request(
        "POST",
        "/api/v2/execute",
        {
            "language": LANGUAGE,
            "version": VERSION,
            "files": [
                {"name": filename, "content": source},
                {"name": "Program", "content": BOOTSTRAP.replace("__NONCE__", nonce)},
            ],
            # The portal supplies its trusted nonce-bearing entry point as source.
            "args": ["-noLogo", "-noColor", "-noAutoReporters"],
            "compile_timeout": 10_000,
            "run_timeout": 3_000,
        },
    )
    cleanup(name)
    compile_result = body["compile"]
    run = body["run"]
    assert compile_result["code"] == 0 and compile_result["signal"] is None, compile_result
    assert run["code"] == exit_code and run["signal"] is None, run
    assert run.get("status") in ((None, "OK") if exit_code == 0 else ("RE",)), run
    output = run["stdout"]
    lines = output.splitlines()
    assert len(lines) == 1 and lines[0].startswith("__M6_TESTS__"), f"{name}: missing single results line: {run}"
    assert len(output.encode()) <= 65_536, name
    envelope = json.loads(lines[0][len("__M6_TESTS__"):])
    assert envelope["nonce"] == nonce, envelope
    xml = envelope["xml"]
    assert "<!DOCTYPE" not in xml and "<!ENTITY" not in xml, xml
    report = ET.fromstring(xml)
    assemblies = report.findall("assembly")
    assert len(assemblies) == 1, xml
    assembly = assemblies[0]
    expected = {"total": total, "passed": passed, "failed": failed, "skipped": skipped, "errors": 0}
    for key, count in expected.items():
        assert int(assembly.attrib[key]) == count, f"{name}: {key}: {xml}"
    tests = assembly.findall("./collection/test")
    assert len(tests) == total, xml
    for result, count in (("Pass", passed), ("Fail", failed), ("Skip", skipped)):
        assert sum(test.get("result") == result for test in tests) == count, xml
    assert len({test.attrib["name"] for test in tests}) == total, xml
    assert not assembly.findall("./errors/error"), xml
    print(f"PASS {name}: discovered {total}, passed {passed}, failed {failed}, skipped {skipped}")
    return tests


def main():
    assert urllib.parse.urlparse(BASE).port != 2001, "port 2001 is the baseline runner"
    assert CONTAINER != "piston-m6-probes", "use a dedicated candidate container"
    runtimes = request("GET", "/api/v2/runtimes")
    matches = [rt for rt in runtimes if rt.get("language") == LANGUAGE and rt.get("version") == VERSION]
    assert len(matches) == 1, f"{LANGUAGE} {VERSION} is absent or duplicated: {runtimes}"
    assert matches[0].get("aliases") == [], matches[0]
    print(f"PASS {LANGUAGE} {VERSION} is present with no aliases")

    tests = suite("three-row AwesomeAssertions theory", THEORY, total=3, passed=3, failed=0, skipped=0, exit_code=0)
    assert all(test.get("method") == "Clamps" for test in tests), tests

    tests = suite("real assertion failure", FAILING, total=1, passed=0, failed=1, skipped=0, exit_code=1)
    failure = tests[0].find("failure")
    assert failure is not None, ET.tostring(tests[0], encoding="unicode")
    assert failure.get("exception-type") == "Xunit.Sdk.XunitException", ET.tostring(failure, encoding="unicode")
    message = failure.findtext("message", "")
    assert "Expected" in message and "2" in message and "1" in message, message

    for filename in ("TestBootstrap", "DefaultResultWriters", "DefaultRunnerReporters"):
        suite(
            f"learner filename {filename} is preserved", FAILING,
            total=1, passed=0, failed=1, skipped=0, exit_code=1, filename=filename,
        )

    suite("empty suite", EMPTY, total=0, passed=0, failed=0, skipped=0, exit_code=0)
    tests = suite("skipped test", SKIPPED, total=1, passed=0, failed=0, skipped=1, exit_code=0)
    assert tests[0].findtext("reason") == "smoke skip", ET.tostring(tests[0], encoding="unicode")
    suite("NSubstitute assembly resolution only", RESOLUTION, total=1, passed=1, failed=0, skipped=0, exit_code=0)
    suite("test-runtime sandbox boundaries", SANDBOX, total=3, passed=3, failed=0, skipped=0, exit_code=0)
    body = request(
        "POST", "/api/v2/execute",
        {
            "language": LANGUAGE, "version": VERSION,
            "files": [
                {"name": "Tests", "content": OVERSIZED_REPORT},
                {"name": "Program", "content": BOOTSTRAP.replace("__NONCE__", secrets.token_hex(16))},
            ],
            "args": ["-noLogo", "-noColor", "-noAutoReporters"],
        },
    )
    cleanup("oversized report")
    assert body["compile"]["code"] == 0 and body["compile"]["signal"] is None, body["compile"]
    assert body["run"]["code"] != 0, body["run"]
    assert "Test report exceeds 65536 bytes." in body["run"]["stderr"], body["run"]
    assert "__M6_TESTS__" not in body["run"]["stdout"], body["run"]
    print("PASS oversized report fails without a success envelope")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, OSError, ValueError, KeyError, TypeError, ET.ParseError, subprocess.TimeoutExpired) as error:
        print(f"FAIL {error}")
        sys.exit(1)
