# Phase 5 architecture decision records

Cyrus Ripley One (Ripley / R1) — Cyrus Forge Systems, LLC

These records continue [ADR-001 through ADR-006](phase-1-adrs.md), [ADR-007](phase-3-adrs.md), and [ADR-008](phase-4-adrs.md).

## ADR-009 — Local Worker process isolation and enforceable deadlines

Status: **ACCEPTED — reviewed by Claude at c39dcec with implementation contracts resolved; awaiting owner merge.**

Implementation status: **NOT STARTED. Documentation only.**

Recorded: 2026-11-06

Baseline: `main` at `f799f42e27166a786bd49d549f529c99cc212d6e`.

### Context and governing objective

Phase 4 preserves execution facts, detects deadline overrun, and permits explicit recovery under bounded policy gates. Its inline worker executes synchronously in the parent and cannot be stopped by that deadline detector. Phase 5 introduces an opt-in local subprocess boundary and enforceable execution deadlines for trusted first-party Workers.

> Ripley must be able to stop a trusted local Worker that exceeds its deadline without giving the Worker direct authority over Ripley’s memory, ledger, validation, or approval process.

The Ripley Record Principle remains unchanged: facts are durable; assessments are attributable; judgments are revisable; revisions supersede rather than erase; history remains auditable.

### Security boundary

> Phase 5 isolation provides crash containment, hang containment, and deadline enforcement. It is not a security sandbox. The child process runs with the same operating-system user, filesystem access, and network access as Ripley. Only trusted first-party Worker code may be executed.

These are intended Phase 5 capabilities, not claims of an implementation delivered by this ADR. Restrictions on Worker authority below are protocol and application responsibilities, not operating-system access controls. A same-user child is not prevented by this design from opening files or using the network; trusted code must honor the execution contract.

### Decision — IMPLEMENT NOW (subsequent bounded implementation only)

This section identifies the approved whiteboard scope to formalize for implementation. It does not authorize implementation during the documentation assignment. After review and owner approval, a separate bounded implementation assignment is required.

#### Isolation mechanism and execution modes

Use Python standard-library `subprocess` execution, not `multiprocessing`, threads, or async. The conceptual flow is:

1. The Ripley parent prepares canonical JSON request bytes.
2. The parent sends those bytes on stdin to `python -m ripley.worker_host`.
3. The host executes the selected trusted local Worker.
4. The host emits one canonical JSON response on stdout.
5. The parent interprets the response and writes durable facts.

The isolation boundary is serialized bytes, not a Python object graph. The execution modes are `inline` and `subprocess`. Default remains `inline`; existing behavior must remain unchanged unless subprocess execution is explicitly selected. This does not introduce concurrent workers or parallel task execution.

#### Worker authority

The child receives no Ledger or Ripley object. It receives only a frozen serialized execution packet and returns only a protocol response. It cannot write durable Ripley records directly through the supported Worker interface, and must not bypass the parent to write them. It does not validate, review, approve, or promote its own output. The parent owns response interpretation, ledger writes, independent validation, review, evidence, and approval.

“Frozen serialized packet” means the submitted observation is fixed in the parent record and transmitted as bytes; decoding it in a child does not give the child mutable access to parent objects or authority to revise history.

#### Canonical envelope version 1

The request packet stored for the Attempt must use canonical JSON, and the child must receive exactly those bytes. Reuse the existing canonical serialization contract: sorted keys, compact separators, no nonfinite JSON numbers, UTF-8. The exact storage placement and protocol framing are review items below.

| Request field | Contract |
|---|---|
| `envelope_version` | `'1'` |
| `attempt_id` | Execution Attempt correlation identifier |
| `task_id` | Owning Task identifier |
| `task_type` | Submitted task type |
| `domain_id` | Submitted domain identifier |
| `domain_version` | Submitted domain version |
| `worker_identity` | Expected trusted local Worker identity |
| `inputs` | Serialized execution inputs |
| `deadline_at` | Execution deadline, retaining the existing no-deadline case |

| Response field | Contract |
|---|---|
| `envelope_version` | Supported version; version 1 is `'1'` |
| `attempt_id` | Must match the request |
| `worker_identity` | Must match the expected Worker |
| `status` | `ok` or `error` |
| `output` | Present when status is `ok` |
| `error` | Object with `type` and `message` when status is `error` |

`attempt_id` is the correlation identifier. Do not add a separate nonce. No credentials field is implemented in version 1 by this assignment.

#### Success and failure classification

Successful isolated execution requires a zero process exit before the deadline, stdout parsing as exactly one JSON response, a supported envelope version, matching Attempt and Worker identity, status `ok`, and an `output` field. For execution without a declared deadline, no deadline-expiration condition applies. Domain output correctness remains the independent Validator's responsibility; protocol acceptance is not validation or approval.

| Failure class | Required classification |
|---|---|
| `worker_failure` | Isolated Worker reports status `error`; preserve error type/message and exit information; no Result |
| `timeout` | Execution deadline expires; preserve the timeout and termination facts |
| `host_failure` | Subprocess fails to start, exits without a valid response, returns malformed or extra stdout protocol content, uses an unsupported envelope, or echoes the wrong Attempt ID or Worker identity |

Wrong-correlation output is discarded. stdout is the protocol channel only: any unexpected stdout causes `host_failure`. The exact precedence when several failure conditions overlap must be resolved before implementation, rather than inferred from this table.

#### Deadline enforcement and termination facts

The engine constants are `TERMINATION_GRACE_SECONDS = 2.0` and `KILL_WAIT_SECONDS = 5.0`.

When the deadline expires:

1. Request process termination.
2. Wait a single engine-level grace period.
3. Kill the process if it is still active.
4. Wait for process completion.
5. Append one `execution_failure` with `stage = 'timeout'`.

The timeout failure contains a `termination` object with appropriate facts, including `requested_at`, `method` (`terminate` or `kill`), `exited`, `returncode`, and `pid`. Do not create a separate termination record. Report observed facts rather than assuming that sending a termination request proves exit.

If the parent cannot confirm the child exited, record `termination.exited = false`, block the Task, mark the Attempt as unconfirmed dead, and prohibit recovery for that Attempt. The exact append-only representation of “unconfirmed dead,” grace duration, and bound on final waiting are unresolved implementation contracts; no new Task state or mutation is introduced by this ADR.

#### Recovery requires proof of exit

`recover()` requires proof that the prior execution is no longer active, in addition to the existing replay-policy, resource-ceiling, identity, active-key, and budget gates. Eligible evidence includes restart interruption **where the prior child ended with the parent**, or enforced timeout with `termination.exited = true`. A timeout with `termination.exited = false` is not recoverable even with a safe replay policy.

An interruption record alone is not evidence that a subprocess ended. The mechanism establishing the stated restart condition on Windows and Linux must be agreed before implementing this gate. There is no automatic recovery on open. Blocked Tasks remain terminal; permitted recovery creates new lineage and preserves the observation and original failure.

The approved P4-15 distinction remains: `previous_task_id` references the newest Task for the key, while `recovers_task_id` references the original blocked Task being recovered. Recovery/correction budgets remain independent. Existing inline recovery must remain compatible; it cannot require termination fields that older inline Attempts never had.

#### Narrow late-result handling

If a complete Worker response arrives during the termination grace window after timeout was declared, append `late_result` and preserve it as factual history. Never validate or promote it. It consumes neither correction nor recovery budget. Preserve the timeout failure as well.

This is limited to the grace-window case. After the final pipe read, close the pipes and accept no additional result. Do not create a general concurrent-result or remote-response subsystem.

P5-07 preserves the Phase 4 post-hoc behavior when the Worker completed after the deadline but before the parent's timeout check: preserve the returned Result and timeout failure, and do not validate or promote the output. That path differs from a response arriving after timeout declaration during termination grace, which produces `late_result`. Timing and classification precedence require the review resolution below.

#### Diagnostics

`DIAGNOSTICS_CAP_BYTES = 8192`, tail-retaining.

stderr may be captured as diagnostics, truncated to a fixed engine-level cap **proposed at 8 KB**. Diagnostics are debugging information, not validated domain evidence. stdout cannot be repurposed for logs. The exact byte cap, truncation marker/encoding, and collection strategy require review; this proposal does not establish general memory or disk limits.

#### Bounded implementation inventory

The subsequent Phase 5 pass covers `ripley.worker_host`, canonical envelope v1, the subprocess execution path, deadline enforcement, terminate/grace/kill handling, `host_failure`, the narrow `late_result` case, capped stderr diagnostics, the proof-of-death recovery gate, the execution-mode option, and P5-01 through P5-13. No implementation is included in this commit.

### Acceptance

These are required future tests, not executed evidence. Preserve these identifiers in the later implementation assignment.

| # | Required acceptance test |
|---|---|
| P5-01 | Pure Worker through subprocess produces the same domain output and expected record flow as inline execution, plus host-execution metadata |
| P5-02 | Worker exception in child returns Worker error and produces `worker_failure`; error type/message and exit information preserved; no Result |
| P5-03 | Worker exceeds deadline; terminate path enforced; timeout failure recorded; exit confirmed; Task blocked; no Result |
| P5-04 | Worker ignores graceful termination where supported; kill path enforced and recorded; platform-specific test may be skipped where signal semantics do not support it |
| P5-05 | Garbage, partial JSON, or successful exit with no response produces `host_failure` |
| P5-06 | Wrong `attempt_id` or identity produces `host_failure` and output is discarded |
| P5-07 | Worker completes after deadline but before the parent's timeout check; existing Phase 4 post-hoc timeout behavior remains intact |
| P5-08 | Complete response arrives during termination grace window; `late_result` is recorded, never validated or promoted, and timeout failure remains |
| P5-09 | Timeout with `termination.exited = true` and safe replay policy may be recovered when other gates pass; `termination.exited = false` prohibits recovery |
| P5-10 | stderr diagnostics are captured and truncated to the fixed cap |
| P5-11 | Request packet stored for the Attempt uses canonical JSON and the child receives exactly those bytes |
| P5-12 | Execution mode is explicit and opt-in; existing Phase 2/3/4 behavior passes unchanged inline; applicable recovery behavior passes under subprocess mode |
| P5-13 | Platform-dependent termination tests use explicit skip conditions; the supported test suite passes on Windows and Linux |
| P5-14 | subprocess attempt interrupted by restart *after* `execution_request`: `recover()` refused while `clock() ≤ deadline_at + grace + 1s`; succeeds once the clock passes it; an attempt with `deadline_at: None` is refused at any time. |
| P5-15 | subprocess attempt interrupted *before* `execution_request` exists → `recover()` eligible immediately (no process ever started). |

A skipped platform-specific termination case is not evidence that its path was exercised. Windows and Linux execution evidence must be reported separately; neither is claimed by this ADR.

### DESIGN ONLY

Also design only: a `process_exit_confirmation` record for unconfirmed-dead attempts (Phase 6 candidate).

Document for later design, without implementing: resource-limiting requirements; provider-worker envelope extension; a future `credentials_ref` slot without credentials handling; and a future stronger sandbox boundary. These are not version 1 capabilities.

### DEFERRED

Arbitrary untrusted code; security sandboxing; containers; separate operating-system identities; CPU/memory/disk limits; remote workers; concurrent workers; per-adapter grace periods; provider-side idempotency; real external provider integration; NFL; production RAG; autonomous Security/Debug agents; advanced learning; cloud deployment.

### Compatibility with Phase 2/3/4

- Phase 2's independent validation and explicit owner approval remain parent responsibilities. A successful child response cannot approve itself. Existing worker eligibility checks remain applicable.
- ADR-007's durable, append-only facts, canonical hashing, five-call ledger interface, single application table, and refusal on integrity mismatch remain the foundation. New process facts must not rewrite existing Attempt records or introduce an independent mutable status authority.
- ADR-008 deliberately deferred cancellation, isolation, and late-result code during Phase 4. Phase 5 explicitly advances only the bounded subprocess and grace-window portions. Inline behavior retains Phase 4's detection-only limitation. This is a new phase decision, not a claim that Phase 4 already enforced deadlines.
- ADR-008 allows eligible interrupted/timeout recovery without subprocess-exit evidence because its Workers run inline. Phase 5 requires stronger evidence for isolated execution. Applying that requirement globally to legacy inline Attempts would conflict with P5-12; mode/legacy behavior must be resolved explicitly.
- Phase 4's `late_result` wording is “already has an execution_failure,” while this assignment's timeout failure is appended after termination and its grace-window response can arrive before that append. The intended facts can coexist, but record append order and what constitutes timeout declaration require reviewer resolution.
- A strict “exit zero before the deadline” success test and P5-07's preservation of a late Result must be distinguished: the latter is a failed post-hoc timeout, not successful isolated execution. P5-03's no-Result expectation applies to the enforced timeout case.
- “Cannot write durable records directly” is an application authority contract. Reading it as an operating-system prohibition would contradict the explicitly shared filesystem/user security boundary. This ADR makes no such sandbox claim.
- The older ADR-008 generic lineage table says `previous_task_id = A`; its later P4-15 acceptance row and merged implementation distinguish newest-task lineage from recovery lineage. Preserve the reviewed P4-15 behavior. Earlier ADR files are unchanged by this documentation assignment.

### Implementation contracts (resolved at review)

**1. Proof of death after parent crash/restart.**
Honest baseline: plain `subprocess` does **not** make a child die with its parent on either Linux or Windows. Job Objects (Windows) and `PR_SET_PDEATHSIG` (Linux) would, but both are platform-specific and the latter needs `ctypes`. Not lean. The lean mechanism is a **child-side watchdog**: `worker_host` starts a daemon thread that calls `os._exit(124)` at `deadline_at + TERMINATION_GRACE_SECONDS`. `os._exit` ends the process regardless of what the worker thread is doing, on both platforms, from the stdlib. It is first-party trusted code honoring a contract, which is exactly the security boundary the ADR declares.

Proof-of-death rule for `recover()` on a *subprocess* attempt interrupted by restart: eligible only if the attempt had a `deadline_at` **and** `clock() > deadline_at + TERMINATION_GRACE_SECONDS + 1s` at the time `recover()` is called. Otherwise unconfirmed → refused. A subprocess attempt with no deadline has no watchdog and is **never** confirmable after restart → permanently ineligible; the owner's path is a new submission. The ledger does no PID probing — PID reuse makes it unreliable and the ledger should not make OS calls.

Inline attempts are unaffected: no process existed, ADR-008 eligibility stands.

**2. Grace / final wait / unconfirmed death.**
Two engine constants, not adapter knobs: `TERMINATION_GRACE_SECONDS = 2.0`, `KILL_WAIT_SECONDS = 5.0`. Sequence: `terminate()` → `communicate(timeout=grace)` → if still running `kill()` → `wait(timeout=KILL_WAIT_SECONDS)`. If it still hasn't exited: `termination = {requested_at, method: 'kill', exited: false, returncode: null, pid}`. `method` is the **last escalation step requested**. Unconfirmed-dead is not a state; it is the fact `exited: false` on the timeout failure, and `recover()` reads it. It is permanent — no later record can "confirm" it in Phase 5 (a `process_exit_confirmation` record is a possible Phase 6 item; name it, don't build it). Failed launch: `termination: null`, `stage: 'host_failure'`, `launch_error: {type, message}`.

**3. Protocol parsing and classification precedence** — evaluated strictly in this order, first match wins:
- (a) `TimeoutExpired` raised by the deadline wait → **timeout** (plus `late_result` per contract 4 if a valid response arrives during grace).
- (b) stdout must be exactly one JSON object plus optional trailing whitespace, UTF-8, no duplicate keys (`object_pairs_hook` rejects), no fields outside the response schema. Any violation → **host_failure**, regardless of exit code. Exit code is recorded.
- (c) `envelope_version`, `attempt_id`, or `worker_identity` mismatch → **host_failure**; output discarded.
- (d) `status == 'error'` with a well-formed `error` object → **worker_failure**, regardless of exit code (the worker reported; the host did its job).
- (e) `status == 'ok'` but exit code ≠ 0 → **host_failure**; output discarded (the host's own state is in doubt).
- (f) `status == 'ok'`, exit 0 → success → Result; validation proceeds as in Phase 2.
Response at exactly the deadline: Phase 4's strict `>` stands — equal is on time.

**4. Deadline timing and late-result ordering.**
`started_at = clock()` immediately before `Popen`; `deadline_at = started_at + timeout_seconds`, persisted UTC on the attempt. The wait budget is `(deadline_at − started_at)` real seconds passed to `communicate(timeout=…)`; the injected clock sets the persisted facts, the real wait governs enforcement (tests use tiny real timeouts, not sleeps in the parent). **Timeout is declared at the instant `TimeoutExpired` is raised**; record `declared_at`. P5-07 = `communicate` returned normally and `completed_at > deadline_at` → Phase 4 post-hoc path unchanged. P5-08 = `TimeoutExpired` → terminate → a complete valid response arrives during grace → **append `execution_failure(timeout)` first, then `late_result` {attempt_id, failure_id, output, worker_identity}**. That ordering satisfies ADR-008's "already has an execution_failure" wording exactly. A crash between those two appends loses only the late output; documented, acceptable. No deadline → `communicate()` with no timeout; no timeout can occur; no watchdog in the child.

**5. Packet storage and attempt-ID ordering.**
Sequence: (i) append `execution_attempt` {…, `execution: 'subprocess'`, `deadline_at`, `replays_attempt_id`}; (ii) build the packet with `attempt.id`; (iii) append **one new record kind, `execution_request`** {attempt_id, packet} — justified because the packet is a fact Ripley acted on and no existing record can hold it without mutation; (iv) `Popen`, write `canonical_json(packet)` to stdin. P5-11 asserts the bytes written equal `canonical_json(record.data['packet'])`. Crash windows: attempt without request → no process was ever spawned → on restart, the interruption is **trivially confirmed dead** → eligible (new test P5-15). Attempt with request → contract 1 applies. Launch failure after request → `host_failure` as in contract 2; not a recoverable class (ADR-008 lists only interrupted/timeout), owner resubmits.

**6. Trusted binding, mode, legacy.**
`worker_host` holds a static registry: `WORKERS = {'mock-worker': MockWorker}` and `ADAPTERS = {'synthetic-inventory': InventoryAdapter}`; version checked against `domain_version`. Identity not in the registry, or version mismatch → host exits 3 with no response → host_failure by rule 3(b). The envelope carries identities only; no module paths, no class names, no pickles. `run(..., execution='inline')` default; `recover(..., execution=None)` defaults to the blocked attempt's recorded `execution`, legacy attempts without the field read as `'inline'`. The proof-of-death gate applies **only** when the blocked attempt's `execution == 'subprocess'`; inline eligibility is byte-for-byte ADR-008. That keeps P5-12 true by construction.

**7. Diagnostics.**
`DIAGNOSTICS_CAP_BYTES = 8192`. Keep the **tail** (tracebacks end with the useful line). Read stderr in full via `communicate` (trusted workers; no backpressure subsystem), then truncate. Decode UTF-8 with `errors='replace'`. Record as `diagnostics: {bytes_total, truncated: bool, text}` on `worker_failure`, `host_failure`, and `timeout` failures. On success, stderr is discarded — not persisted. Excess **stdout** is a protocol violation and already host_failure; cap the parent's read of it at the same 8192 for the diagnostic copy.

**8. Platform test contract.**
All P5 tests run on Linux and Windows except P5-04 (SIGTERM trap), skipped with `@unittest.skipIf(sys.platform == 'win32', 'graceful-termination signal not supported on Windows')`. `termination.method` expectations: P5-03 → `'terminate'` on both platforms (it's what was requested; on Windows it happens to be forceful); P5-04 → `'kill'` on Linux. Platform changes expected metadata, never acceptance. Each platform's run is reported separately; a skip is reported as a skip. **Rob runs the suite on Windows** — that would be the first second-party execution in the project's history and closes the caveat we've carried since Phase 2.

### Consequences and evidence boundary

The intended design separates trusted Worker execution from the parent's record and judgment authority and allows the parent to stop overdue isolated work. Serialization, process lifecycle management and protocol validation become explicit failure boundaries. Deadlines and replay safety remain separate decisions; an unconfirmed child exit blocks replay even when the Worker is otherwise replay-safe.

Only this ADR is added. No Phase 5 production code, tests, process host, or sandbox has been created. No Phase 5 acceptance tests have been run. The previous 100-test execution remains ChatGPT-local; Claude's independent code review is not independent test execution by Claude or Copilot. Nothing here upgrades Ripley to production validated.

Claude and Copilot review the actual ADR commit; Rob approves and merges. A separate bounded Phase 5 implementation assignment follows only after review and owner approval.
