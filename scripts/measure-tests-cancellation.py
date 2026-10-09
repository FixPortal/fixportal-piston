"""Observe HTTP disconnect cost on the disposable candidate; never a timing unit test."""

import http.client
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse

spec = importlib.util.spec_from_file_location("measurement", Path(__file__).with_name("measure-tests.py"))
measurement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurement)
BASE, CONTAINER, OUTPUT = sys.argv[1:]
assert CONTAINER == "piston-m6-runtime-candidate"
measurement.quiescent()
target = urllib.parse.urlparse(BASE)
connection = http.client.HTTPConnection(target.hostname, target.port, timeout=20)
source = '''
System.IO.File.WriteAllText("m6-started", System.Environment.ProcessId.ToString());
while (true) { }
'''
body = json.dumps({"language": "csharp.net", "version": "10.0.401",
                   "files": [{"name": "Program", "content": source}]}).encode()
connection.request("POST", "/api/v2/execute", body, {"Content-Type": "application/json"})
deadline = time.monotonic() + 20
pid = None
try:
    while time.monotonic() < deadline:
        observed = subprocess.run([
            "docker", "exec", CONTAINER, "find", "/var/local/lib/isolate",
            "-name", "m6-started", "-exec", "cat", "{}", ";",
        ], capture_output=True, text=True, timeout=10)
        if observed.returncode == 0 and observed.stdout.strip():
            pid = int(observed.stdout)
            break
    assert pid is not None, "Never observed the job's actual Main entry."
    processes = subprocess.run(["docker", "exec", CONTAINER, "ps", "-eo", "pid,args"],
                               capture_output=True, text=True, timeout=10)
    assert processes.returncode == 0, processes.stderr
    candidates = [line.split(maxsplit=1) for line in processes.stdout.splitlines()
                  if line.strip().endswith("dotnet app.dll")]
    assert len(candidates) == 1, processes.stdout
    container_pid = int(candidates[0][0])
    disconnected = time.monotonic()
    connection.close()
    alive = subprocess.run(["docker", "exec", CONTAINER, "kill", "-0", str(container_pid)],
                           capture_output=True, text=True, timeout=10)
    started = time.monotonic()
    following = measurement.smoke.request("POST", "/api/v2/execute", {
        "language": "csharp.net", "version": "10.0.401",
        "files": [{"name": "Program", "content": 'System.Console.WriteLine("following");'}],
    })
    elapsed = (time.monotonic() - started) * 1000
    assert following["compile"]["code"] == 0 and following["run"]["code"] == 0, following
    assert following["run"]["stdout"].strip() == "following", following
    measurement.quiescent()
    evidence = {"isolatePid": pid, "containerPid": container_pid, "aliveAfterDisconnect": alive.returncode == 0,
                "followingRequestElapsedMs": round(elapsed, 2),
                "disconnectToQuiescentMs": round((time.monotonic() - disconnected) * 1000, 2),
                "following": following}
    Path(OUTPUT).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in evidence.items() if key != "following"}))
finally:
    connection.close()
