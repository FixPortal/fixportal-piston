"""Throwaway feasibility measurement of the approved compile-once/fresh-child fallback.

Usage: python scripts/measure-tests-once.py URL CONTAINER OUTPUT_JSON
The authored clamp variants below are fixtures, not a product harness.
"""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import secrets
import sys
import threading
import time
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location("measurement", Path(__file__).with_name("measure-tests.py"))
measurement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurement)
smoke = measurement.smoke
BASE, CONTAINER, OUTPUT = sys.argv[1:]
smoke.BASE = BASE
CHILD = smoke.BOOTSTRAP.replace("internal static class Program", "internal static class TestRunner")
CHILD = CHILD.replace("Main(string[] args)", "Run(string[] args, string nonce)")
CHILD = CHILD.replace('nonce = "__NONCE__"', "nonce")
PARENT = r'''
internal static class Program
{
    internal static int Subject;
    public static int Main(string[] args)
    {
        if (args.Length == 3 && args[0] == "child")
        {
            Subject = int.Parse(args[1]);
            return TestRunner.Run(["-noLogo", "-noColor", "-noAutoReporters"], args[2]);
        }
        return RunChildren().GetAwaiter().GetResult();
    }

    private static async System.Threading.Tasks.Task<int> RunChildren()
    {
        var results = new System.Collections.Generic.List<object>();
        var root = System.IO.Path.GetFullPath("children");
        System.IO.Directory.CreateDirectory(root);
        var assembly = typeof(Program).Assembly.Location;
        foreach (var subject in new[] { 0, 0, 1, 2, 3, 1, 2, 3 })
        {
            var nonce = System.Convert.ToHexString(System.Security.Cryptography.RandomNumberGenerator.GetBytes(16));
            var directory = System.IO.Path.Combine(root, nonce);
            System.IO.Directory.CreateDirectory(directory);
            foreach (var file in System.IO.Directory.EnumerateFiles(System.IO.Path.GetDirectoryName(assembly)!))
            {
                var name = System.IO.Path.GetFileName(file);
                var destination = System.IO.Path.Combine(directory, name);
                if (name.StartsWith("app.", System.StringComparison.Ordinal))
                    System.IO.File.Copy(file, destination);
                else if (name.EndsWith(".dll", System.StringComparison.Ordinal))
                    System.IO.File.CreateSymbolicLink(destination, file);
            }
            var start = new System.Diagnostics.ProcessStartInfo("/bin/bash")
            {
                WorkingDirectory = directory,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false
            };
            foreach (var value in new[] { "-c", "ulimit -t 3; exec \"$1\" \"$2\" child \"$3\" \"$4\"", "m6",
                System.Environment.ProcessPath!, System.IO.Path.Combine(directory, "app.dll"), subject.ToString(), nonce })
                start.ArgumentList.Add(value);
            using var child = System.Diagnostics.Process.Start(start)
                ?? throw new System.InvalidOperationException("Child did not start.");
            var stdout = ReadBounded(child.StandardOutput);
            var stderr = ReadBounded(child.StandardError);
            try
            {
                await System.Threading.Tasks.Task.WhenAll(child.WaitForExitAsync(), stdout, stderr)
                    .WaitAsync(System.TimeSpan.FromSeconds(3));
                results.Add(new { subject, nonce, pid = child.Id, code = child.ExitCode,
                    stdout = await stdout, stderr = await stderr });
            }
            finally
            {
                if (!child.HasExited)
                    child.Kill(entireProcessTree: true);
                await child.WaitForExitAsync();
            }
            System.IO.Directory.Delete(directory, recursive: true);
        }
        var line = "__M6_CHILDREN__" + System.Text.Json.JsonSerializer.Serialize(new { nonce = "__REQUEST__", results });
        if (System.Text.Encoding.UTF8.GetByteCount(line + "\n") > 65_536)
            throw new System.IO.InvalidDataException("Combined report exceeds 65536 bytes.");
        System.Console.WriteLine(line);
        return 0;
    }

    private static async System.Threading.Tasks.Task<string> ReadBounded(System.IO.StreamReader reader)
    {
        var buffer = new char[1024];
        var text = new System.Text.StringBuilder();
        int count;
        while ((count = await reader.ReadAsync(buffer)) != 0)
        {
            if (text.Length + count > 65_536)
                throw new System.IO.InvalidDataException("Child output exceeds 65536 characters.");
            text.Append(buffer, 0, count);
        }
        return text.ToString();
    }
}
public static class Clamper
{
    public static int Clamp(int value, int min, int max) => Program.Subject switch
    {
        0 => System.Math.Clamp(value, min, max),
        1 => value < min ? value : System.Math.Min(value, max),
        2 => value > max ? value : System.Math.Max(value, min),
        3 => value > min && value < max ? min : System.Math.Clamp(value, min, max),
        _ => throw new System.InvalidOperationException("Unknown authored subject.")
    };
}
'''
FRESH = r'''
public class FreshChildTests
{
    private static int calls;
    [Xunit.Fact]
    public void HasFreshStaticsAndDirectory()
    {
        System.Threading.Interlocked.Increment(ref calls).Should().Be(1);
        System.IO.File.Exists("child-marker").Should().BeFalse();
        System.IO.File.WriteAllText("child-marker", "present");
    }
}
'''


def schedule(barrier=None):
    if barrier is not None:
        barrier.wait(timeout=20)
    nonce = secrets.token_hex(16)
    started = time.monotonic()
    response = smoke.request("POST", "/api/v2/execute", {
        "language": "csharp-tests", "version": "10.0.401",
        "files": [{"name": "Tests", "content": measurement.TESTS + FRESH},
                  {"name": "Program", "content": PARENT.replace("__REQUEST__", nonce)},
                  {"name": "TestRunner", "content": CHILD}],
        # Aggregate ceiling for eight independently bounded, sequential children.
        "run_timeout": 26000, "run_cpu_time": 26000,
    })
    elapsed = (time.monotonic() - started) * 1000
    assert response["compile"]["code"] == 0 and response["compile"]["signal"] is None, response
    run = response["run"]
    assert run["code"] == 0 and run["signal"] is None, response
    lines = run["stdout"].splitlines()
    assert len(lines) == 1 and lines[0].startswith("__M6_CHILDREN__"), response
    envelope = json.loads(lines[0][len("__M6_CHILDREN__"):])
    assert envelope["nonce"] == nonce
    rows = envelope["results"]
    assert [row["subject"] for row in rows] == [0, 0, 1, 2, 3, 1, 2, 3]
    assert len({row["nonce"] for row in rows}) == 8
    assert len({row["pid"] for row in rows}) == 8
    for row in rows:
        subject = row["subject"]
        assert row["code"] == (0 if subject == 0 else 1) and not row["stderr"], row
        child_lines = row["stdout"].splitlines()
        assert len(child_lines) == 1 and child_lines[0].startswith("__M6_TESTS__"), row
        report = json.loads(child_lines[0][len("__M6_TESTS__"):])
        assert report["nonce"] == row["nonce"]
        assert "<!DOCTYPE" not in report["xml"] and "<!ENTITY" not in report["xml"]
        assembly = ET.fromstring(report["xml"]).find("assembly")
        assert int(assembly.get("total")) == 4 and int(assembly.get("errors")) == 0
        assert int(assembly.get("skipped")) == 0
        tests = assembly.findall("./collection/test")
        failures = [test for test in tests if test.get("result") == "Fail"]
        assert len(failures) == (0 if subject == 0 else 1), row
        if subject:
            assert measurement.EXPECTED_FAILURES[subject] in failures[0].get("name"), row
            assert failures[0].find("failure").get("exception-type") == "Xunit.Sdk.XunitException"
        row["inventory"] = sorted(test.get("name") for test in tests)
        row["failed"] = [test.get("name") for test in failures]
    assert all(row["inventory"] == rows[0]["inventory"] for row in rows)
    assert all(rows[index]["failed"] == rows[index + 3]["failed"] for index in (2, 3, 4))
    return {"elapsedMs": round(elapsed, 2), "compile": response["compile"], "run": run,
            "children": rows}


def check_inherited_pipe_timeout():
    parent = PARENT.replace("new[] { 0, 0, 1, 2, 3, 1, 2, 3 }", "new[] { 0 }")
    child = '''
internal static class TestRunner
{
    public static int Run(string[] args, string nonce)
    {
        System.Diagnostics.Process.Start("/bin/sleep", "5");
        return 0;
    }
}
'''
    result = smoke.request("POST", "/api/v2/execute", {
        "language": "csharp-tests", "version": "10.0.401",
        "files": [{"name": "Program", "content": parent},
                  {"name": "TestRunner", "content": child}],
        "run_timeout": 26000, "run_cpu_time": 26000,
    })
    assert result["compile"]["code"] == 0, result
    assert result["run"]["code"] != 0, result
    assert "TimeoutException" in result["run"]["stderr"], result
    assert "__M6_CHILDREN__" not in result["run"]["stdout"], result
    measurement.quiescent()
    return {"accepted": False, "run": result["run"]}


if __name__ == "__main__":
    assert CONTAINER == "piston-m6-runtime-fallback"
    measurement.quiescent()
    evidence = {"fixtureOnly": True, "idle": [], "concurrentSubmitters": [], "error": None}
    try:
        evidence["inheritedPipeCheck"] = check_inherited_pipe_timeout()
        for _ in range(3):
            evidence["idle"].append(schedule())
            measurement.quiescent()
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(schedule, barrier) for _ in range(2)]
            evidence["concurrentSubmitters"] = [future.result() for future in futures]
        measurement.quiescent()
    except Exception as error:
        evidence["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        Path(OUTPUT).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    for mode in ("idle", "concurrentSubmitters"):
        print(mode, [row["elapsedMs"] for row in evidence[mode]])
