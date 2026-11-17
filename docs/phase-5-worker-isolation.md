# Phase 5 — Local Worker isolation and enforceable deadlines

Status: **IMPLEMENTED prototype, ChatGPT-locally tested; awaiting Claude review and owner acceptance. NOT production validated.**

## Implemented boundary

Ripley can execute one trusted Worker in a fresh local Python process per Attempt. Select it with `run(..., execution='subprocess')`. The default is `inline`. Recovery inherits the prior Attempt's mode unless explicitly overridden. A legacy Attempt without a mode reads as inline. The mode override applies to the new execution. Ripley checks the prior execution's exit evidence before authorizing recovery.

> Phase 5 isolation provides crash containment, hang containment, and deadline enforcement. It is not a security sandbox. The child process runs with the same operating-system user, filesystem access, and network access as Ripley. Only trusted first-party Worker code may be executed.

The parent appends the Attempt, then an `execution_request` with its Attempt ID and packet, before starting `python -m ripley.worker_host`. It writes the packet's canonical JSON bytes to stdin. The v1 packet contains the envelope version, Attempt ID, Task ID and type, domain ID and version, Worker identity, inputs, and nullable deadline. The host binds the identity and version to registered first-party code. It gives the Worker frozen Task and Snapshot mappings. The parent retains sole responsibility for ledger writes, validation, review and approval.

The ordinary registry contains `mock-worker` and the `synthetic-inventory` adapter. A test host registers `test-behavior-worker` only with `RIPLEY_ENABLE_TEST_WORKERS=1`. The behavior setting alone cannot enable it. Each correction starts a new child with its own Attempt and request.

## How the parent classifies an execution

The first applicable rule determines the outcome.

1. The initial deadline wait raises `TimeoutExpired`. Record a timeout and apply the termination sequence below.
2. Accept one UTF-8 JSON object with optional trailing JSON whitespace. Reject duplicate keys, unsupported fields, invalid status-specific fields, nonfinite numbers and extra stdout as `host_failure`.
3. Check the envelope version, Attempt ID and Worker identity. A mismatch produces `host_failure`.
4. A well-formed `error` response produces `worker_failure` for any exit code. Preserve the reported error type, message and exit facts.
5. An `ok` response with a nonzero exit code produces `host_failure`.
6. An `ok` response with output and exit zero produces a Result. If completion is strictly later than the deadline, preserve the Result and append the Phase 4 post-hoc timeout with `termination: None`. Otherwise validation proceeds. Equality is on time.

## Deadlines, termination and diagnostics

Subprocess start, deadline, timeout declaration, termination request and observed completion use real UTC. The parent gives `communicate` the declared duration in seconds. Inline timing and the recovery comparison use Ripley's evidence clock. With no deadline, the initial wait is unbounded and the host starts no watchdog.

On an enforced timeout the parent records the declaration time, calls `terminate()` and drains both pipes with `communicate(timeout=TERMINATION_GRACE_SECONDS)` (2 seconds). If grace expires, it requests `kill()` and drains with `communicate(timeout=KILL_WAIT_SECONDS)` (5 seconds). If that wait expires, the parent requests one final kill without waiting and records an unconfirmed exit. The child watchdog is due at deadline + grace + `WATCHDOG_MARGIN_SECONDS` (1 second). The termination object records the request time, last escalation requested, PID, observed exit flag and return code.

Only a complete, valid, correlated `ok` response returned by the grace call can produce a `late_result`. Ripley appends the timeout failure first, the linked late result second, then blocks the Task. That output consumes neither budget and never enters validation or approval. If the parent crashes between the first two appends, the timeout survives and the late output can be lost.

Failure diagnostics retain the final 8,192 **bytes** of stderr, the total byte count observed and a truncation flag. The retained bytes are decoded as UTF-8 with replacement of invalid sequences. A protocol failure carries a capped `stdout_excerpt`. Output observed only in the post-kill drain, or rejected grace output, belongs only in the timeout's `diagnostics.stdout_excerpt`. The parent discards successful stderr. The cap bounds retained diagnostics, not pipe memory usage.

## Proof of exit for explicit recovery

After the existing blocked-task, active-key and failure-eligibility checks, the parent evaluates evidence for the prior subprocess Attempt in this order.

| Prior evidence | Recovery gate |
|---|---|
| No matching execution request | Pass immediately. The parent had not reached spawn. |
| Termination object | Pass only for `exited is True`. An unconfirmed exit stays ineligible. |
| Completion timestamp and no termination object | Pass. The completed process returned to the parent. |
| Restart interruption, including an open-time timeout with `deadline_exceeded_before_restart` | Require a deadline and an evidence clock strictly later than deadline + grace + watchdog margin + 1 second (4 seconds beyond the deadline). Equality is refused. |
| Other evidence, or restart after a request with no deadline | Refuse recovery. |

A refusal adds no record. A permitted replay still passes the existing policy, identity, resource and budget checks. SQLite reopening only classifies and blocks interrupted work. Explicit recovery creates the new lineage.

## Failure-mode table

These entries extend the [Phase 4 failure modes](phase-4-recovery-timeout.md#failure-mode-maturity).

| Mode | Parent record and Task outcome |
|---|---|
| Host failure | Launch refusal, broken protocol, wrong correlation or a nonzero exit with an `ok` response blocks with `blocked_host_failure`. A launch exception carries its type and message, with null termination and diagnostics. |
| Worker-reported error | Store the correlated error and exit information. Block with `blocked_worker_failure`. |
| Enforced timeout, terminate | Store one timeout failure with the termination facts. Block with `blocked_timeout`. |
| Enforced timeout, kill | Store the last escalation as `kill`. Post-kill stdout is diagnostic evidence only. |
| Unconfirmed exit | Record `exited: false` and a null return code. Block the Task and refuse replay. |
| Grace-window late result | Link `late_result` to the timeout failure and Attempt. The Task stays blocked. |
| Restart of a subprocess Attempt | Preserve Phase 4 open-time classification. Apply the evidence table above at explicit recovery. |
| Post-hoc timeout | Preserve the Result and a timeout failure. Block before validation. |

## Test evidence and limits

P5-01 through P5-13 run on both ledgers. P5-14 and P5-15 exercise real SQLite reopen boundaries. The discovery total is 62 skeleton + 11 durability + 27 Phase 4 recovery + (13 × 2) shared Phase 5 + 2 SQLite-only = **128 tests**.

ChatGPT-local platform run — Debian GNU/Linux 13.6, Linux 6.18.57 x86_64, CPython 3.12.14. `python3 -m unittest discover -s tests -v` passed all 128 tests with zero failures, errors or skips. P5-04 observed the parent kill on Linux. P5-08 observed both a grace response and a post-kill drain with a partial envelope.

First independent execution (owner, Windows, `py -m unittest discover -s tests -v`): 128 run; 4 expected SIGTERM-dependent skips; 4 hash-guard failures caused by platform-dependent working-tree bytes; all behavioral isolation tests passed. Resolved by normalized hashing in PR #10.

The expected Windows skips are P5-04 and P5-08 on each ledger (four test instances). Regression-file integrity hashes are computed over line-ending-normalized UTF-8 text so Windows CRLF checkouts hash identically to Linux.

Bad-then-good correction success is exercised inline. The stateless subprocess fixture exercises a second child and correction-budget exhaustion. The unconfirmed-exit recovery rule is tested with ledger evidence. An actual child surviving the final kill wait was not observed. Windows and Linux scheduling and dispatch latency are outside the parent's control.

Execution is sequential and limited to trusted first-party code. The child inherits the parent's operating-system privileges. There are no resource limits or OS sandbox, and a Worker with no declared deadline may wait indefinitely. Restart replay after a recorded request relies on the trusted watchdog contract.
