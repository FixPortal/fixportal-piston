# M6 csharp-tests runtime spike

Measured 2026-10-09 on runner main `1d9f2de9cdc67c1791c983491f6e37c334c9049b`.
Portal main was `7b18119a4fb73dec141f31ce3bec99cc19b04138`, still pinning that runner revision.
This change supplies the runtime prerequisite; it does not enable learner-test grading.

## Runtime and protocol

The third .NET runtime is `csharp-tests` 10.0.401. Plain C# and EF retain their
existing package references and behavior. A fixed project restores xunit.v3
4.0.1, AwesomeAssertions 9.6.0 and NSubstitute 6.2.0 with a committed lockfile.
All 21 resolved nupkgs are downloaded and verified against their raw-byte
SHA512 before the offline locked restore. Restores and MSBuild run only during
image construction. Submissions still use direct `csc`.

The published closure contains 59 files. Two verified xUnit assembly-registration
sources are compiled from outside the submission directory, avoiding learner
filename collisions. The publish project's stub entry point is removed from the
installed assets. Each submission supplies its trusted `Program.cs`, so the
portal can own the nonce and result protocol. Forcing the prototype's baked entry
point failed the new protocol smoke; removing it made that smoke pass.

The public API is
`Xunit.Runner.InProc.SystemConsole.ConsoleRunner.Run(string[])`.
The smoke bootstrap supplies `-result-xml`, suppresses framework console output,
then emits one bounded JSON line with its nonce and XML report. A failing
AwesomeAssertions assertion consistently reports `Xunit.Sdk.XunitException`.
Empty discovery, skipped tests and oversized reports remain explicit outcomes;
they are not proof of a valid learner suite. Authenticity additionally requires
the portal's source grammar and per-test provenance checks before execution.

Image ID: `sha256:4005b487191de861dd705080cf9ebfb8d17c90e1819d1e0c371b65f0afa13851`.
The adjacent JSON records its layers, all 61 installed asset digests (closure
plus registrations), stage timings and parsed child inventories. Raw fallback
XML is retained locally; the committed evidence records report digests.
The image's compiler reports C# 14.0 as the default, including `latest` support.
The HTTP runner has no compile-only operation; execute always compiles and runs.

## Latency gate and approved fallback

The original eight independent jobs retain both public-reference runs and all
three defect confirmations, with fresh nonces and identical discovered tests.
On the dedicated candidate with concurrency exactly one:

| Schedule | Elapsed milliseconds |
| --- | --- |
| Independent jobs, idle | 10782, 10094, 10219 |
| Independent jobs, two concurrent submitters | 19031, 20265 |
| Compile once, eight fresh children, idle | 3922, 3797, 4110 |
| Compile once, two concurrent submitters | 3984, 8438 |

Independent compilation misses the proposed 15-second target under actual
concurrent submissions. The approved fallback is feasible on this host: one
compile, followed by eight sequential fresh processes. The fixture checks a
fresh static counter and working-directory marker in every child, distinct
process IDs and nonces, stable test inventory and assertion-failure identity,
and agreement of each confirmation with its defect run. All sandbox directories
are gone after the response.

`scripts/measure-tests-once.py` is explicitly a developer fixture, not the
product grader. Each child has a three-second wall watchdog, a three-second CPU
limit and a bounded output reader, with kill and wait on every exit path. The
aggregate sandbox has a 26-second wall/CPU ceiling and the runtime's 256 MiB
memory cap. Its disposable container overrides that ceiling; this PR does not
widen ordinary runtime defaults. The parent copies the compiled app into each
fresh directory because xUnit changes its working directory to the assembly's
directory; merely changing the process launch directory did not isolate files.

Before product adoption, slice 7 must enforce its grammar, deliver only the
authorized report fields, handle child limits as inconclusive, verify hostile
and weak-suite fixtures, and preserve logical stage identity and deadlines.
This fixture holds all four authored variants in its trusted program; it does
not itself establish hidden-subject redaction or a production isolation boundary.
There is no cross-request compilation cache or same-process test loop.

## Cancellation gate

Disconnecting HTTP after the spinning job entered `Main` did not cancel the
job: its actual container PID remained alive after disconnect. The next request
took 3375 ms, and the runner became quiescent 3703 ms after disconnect. The
bounded abandoned job held its slot until its configured limits completed.
The evidence distinguishes the isolate PID from the container PID.

G8's early-release hypothesis is refuted. A portal deadline can bound learner
wait, but cannot claim to release the runner slot early. In the fallback, an
abandoned aggregate request could retain the slot for its aggregate ceiling;
that larger ceiling must be accounted for before production activation.
The separate lifecycle-recovery proposal remains unimplemented here.

Decision 5's 60-second portal deadline remains a proposal for Chris to confirm.
The measured fallback is comfortably below 15 seconds for this fixture and
two submitters, but these five schedules are feasibility evidence, not a p95
or capacity guarantee. More production-representative schedules belong to the
completed grader's release gate.

## Checks

Baseline image: all 19 smoke checks passed. Candidate image: all 26 parent smoke
checks passed, including the ten csharp-tests cases: three discovered theory
rows, assertion provenance, three registration filename collisions, empty and
skipped discovery, dependency loading, sandbox boundaries and output overflow.
The baseline remains independently available; ordinary portal and GLM stacks
were untouched.

This note does not claim compiler parity for future pilot source or a passed
end-to-end grader gate. Those require slices 4 and 7 and the real runner lane.
