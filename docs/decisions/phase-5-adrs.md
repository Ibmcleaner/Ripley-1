# Phase 5 architecture decision records

Cyrus Ripley One (Ripley / R1) — Cyrus Forge Systems, LLC

These records continue [ADR-001 through ADR-006](phase-1-adrs.md), [ADR-007](phase-3-adrs.md), and [ADR-008](phase-4-adrs.md).

## ADR-009 — Local Worker process isolation and enforceable deadlines

Status: **DESIGNED — whiteboard direction supplied by Rob following review with Copilot and Claude; this ADR commit awaits review and owner approval.**

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

A skipped platform-specific termination case is not evidence that its path was exercised. Windows and Linux execution evidence must be reported separately; neither is claimed by this ADR.

### DESIGN ONLY

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

### Unresolved implementation contracts — Claude/Copilot review required

1. **Parent exit and proof of death across restart.** Specify how a trusted child is guaranteed to end with its parent on both Windows and Linux, or how its exit is independently confirmed after restart. Subprocess launch plus ADR-007's interruption record does not itself supply that proof. Define the durable evidence, startup/recording crash windows, and handling of absent or inconclusive evidence. Do not silently equate restart, a PID, or a termination request with confirmed death. This resolution must fit the stated standard-library/no-sandbox scope.
2. **Termination timing and unconfirmed-death representation.** Choose the single engine grace duration and final wait bound so the unconfirmed-exit path is reachable without hanging the parent. Define what `method` means after escalation, null exit facts on failed start, how unconfirmed death is represented append-only, and how final pipe draining/closure completes without indefinite waiting. No separate termination record is permitted.
3. **Protocol and classification precedence.** Define strict JSON framing (including trailing whitespace, duplicate keys, extra fields, invalid values/encoding), valid error response requirements, and precedence for a valid response with nonzero exit. Decide how malformed or mismatched responses arriving during grace interact with “unexpected stdout causes host_failure,” the narrow late-result rule, and the requirement for one timeout failure. Do not silently turn an uncorrelated response into domain evidence or append competing failure classifications.
4. **Deadline observation and late-result ordering.** Specify the clock used for elapsed waits versus persisted UTC deadlines, the observable definition of completion/exit, and the boundary between P5-07 and P5-08. Define when timeout is declared, the order of `late_result` and timeout-failure appends, their references, and interrupted persistence between those appends. Define subprocess behavior with no deadline. Do not add a nonce or new envelope field without review.
5. **Request/response and host-metadata storage.** Decide how exact canonical request bytes are stored and linked to the Attempt, plus the schema/location of host-execution metadata, diagnostics and `late_result`. The current `Ledger.add` generates an Attempt ID when it appends the immutable record, yet the packet includes that ID; resolve the construction/append ordering without rewriting the Attempt or expanding the ledger API/table count. Define crash handling between Attempt creation, packet recording, spawn and response recording.
6. **Trusted Worker/domain binding and execution-mode API.** Define the parent's explicit mode argument and how mode is recorded, how recovery selects it, and how `worker_host` resolves known first-party Worker/domain implementations from envelope identifiers. No Python object transfer or arbitrary untrusted code loading is authorized. Preserve existing allowlist/self-validation checks, active-key rejection, recovery budgets and binding rules. Define legacy inline Attempts and pre-Attempt interruptions under the new proof gate without invalidating the unchanged regression suite.
7. **Diagnostics cap and collection.** Confirm whether proposed 8 KB means 8,000 or 8,192 bytes, whether truncation retains head/tail, decoding/marker rules, and bounded collection versus post-capture truncation. Define stdout handling for excessive output and pipe backpressure without introducing a general resource-limiting or concurrent-worker subsystem.
8. **Cross-platform acceptance evidence.** Specify supported Windows/Linux environments, explicit skip predicates, and the deterministic test strategy for graceful termination, forced kill, unconfirmed exit, post-hoc races and grace-window response arrival. The approved implementation assignment must distinguish exercised behavior from platform skips and from code review alone.

These are unresolved details for review, not additional accepted architecture decisions or permission to implement deferred systems.

### Consequences and evidence boundary

The intended design separates trusted Worker execution from the parent's record and judgment authority and allows the parent to stop overdue isolated work. Serialization, process lifecycle management and protocol validation become explicit failure boundaries. Deadlines and replay safety remain separate decisions; an unconfirmed child exit blocks replay even when the Worker is otherwise replay-safe.

Only this ADR is added. No Phase 5 production code, tests, process host, or sandbox has been created. No Phase 5 acceptance tests have been run. The previous 100-test execution remains ChatGPT-local; Claude's independent code review is not independent test execution by Claude or Copilot. Nothing here upgrades Ripley to production validated.

Claude and Copilot review the actual ADR commit; Rob approves and merges. A separate bounded Phase 5 implementation assignment follows only after review and owner approval.
