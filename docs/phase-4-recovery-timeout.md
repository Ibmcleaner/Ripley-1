# Phase 4 — Explicit recovery and timeout detection

Status: **IMPLEMENTED prototype, ChatGPT-locally tested; awaiting Claude review and owner acceptance. NOT production validated.**

Authority: [ADR-008](decisions/phase-4-adrs.md), including the implementation contracts resolved at review. Baseline: `main` at `0d835540197b56c9bfeb0d601a8e6a46c4c34f39`.

## Implemented boundary

`InventoryAdapter` declares `replay_policy = 'safe'` and no timeout. Core reads optional declarations with `getattr(adapter, name, None)`. Task records capture `safe`, `no`, or `unknown` and ordinary submissions carry `recovers_task_id: None`. Missing legacy replay policy fails closed. No migration or backfill occurs.

Each Execution Attempt carries `deadline_at` (UTC ISO-8601 or None) and `replays_attempt_id` (None ordinarily). `Ripley(ledger=None, validator=None, clock=None)` accepts a callable clock; the default returns current UTC time. Deadlines are computed per attempt, and completion is sampled immediately after the worker returns, before recording its Result.

A completion strictly after the deadline preserves the Result, appends a timeout failure with attempt, deadline and completion references, blocks with reason `deadline_exceeded`, and returns `blocked_timeout`. The late output is not validated, reviewed, promoted, or used to request a correction. Prior completed records remain preserved. Completion exactly at the deadline is allowed.

On SQLite open, integrity verification still precedes all writes. In the restart loop, only a `running` Task whose latest Attempt has a passed deadline is classified as `timeout`, with message `deadline_exceeded_before_restart`. Its transition reason remains `interrupted_by_restart`. Other `submitted`, `running`, or `validated` Tasks retain the Phase 3 interruption policy. Waiting-for-owner and terminal states remain untouched. A second open appends nothing after completed restart marking.

> Ripley detects and records deadline overrun; it does not preemptively cancel worker execution

Explicit recovery and ordinary submissions share the same execution loop. Recovery creates a new Snapshot copying the original inputs, observation time, sources, quality, and domain version, and adds `replays_snapshot_id`. It never calls `adapter.snapshot_metadata()`. New Task B references A through both `previous_task_id` and `recovers_task_id`; its first Attempt references A's latest Attempt, or None if A had none. Later correction Attempts have no replay reference. A stays blocked and its history is unchanged.

Every run/recovery return has the same keys, including `authorization` (None outside recovery). The collections `results`, `validations`, `reviews`, and `corrections` remain tuples. Explicit recovery does not use the ordinary submission duplicate guard. Recovery authorization does not approve the Result; successful execution still waits for owner approval.

## Recovery check order

`recover(blocked_task_id, actor, reason, adapter, worker=None, allowed_workers=('mock-worker',), correction_budget=1)` performs these checks:

1. The identified record exists, is a Task, and has derived state `blocked`.
2. The latest Execution Failure for that Task has stage `interrupted` or `timeout`, and the Task has no `correction_budget_exhaustion` record. Otherwise raise `ValueError('recovery not eligible for this failure')`.
3. The recorded replay policy is `safe`; missing means unknown and rejects.
4. The recorded resource ceiling is exactly `'no external calls'`.
5. The supplied adapter domain ID and version equal the Task's recorded values.
6. Apply the same worker allowlist and self-validation checks as `run()`; violations raise `PermissionError`.
7. Require a non-empty string actor and a string reason with non-empty `strip()`.
8. Walk `recovers_task_id` to the root and count `recovery_authorization` records whose `blocked_task_id` is in that chain. A count of at least 1 appends exactly one `recovery_budget_exhaustion` with task ID, root ID, budget 1 and consumed count, then raises `ValueError('recovery budget exhausted')`.

Checks 1–7 append nothing when rejected. Before step 8, argument validation also checks the correction budget and timeout declaration, as documented below. Budget exhaustion is the only failed eligibility check that writes a record. Budget usage is derived, never stored separately.

After successful checks, append `recovery_authorization` containing the blocked Task ID, nullable latest Attempt ID, actor, reason, replay policy cited and resource ceiling cited. Then create the new Snapshot/Task/Attempt lineage and use the ordinary validation, review, correction, evidence and pending-approval path. The recovery budget is independent of the new execution's correction budget.

## Failure-mode maturity

| Mode | Status | Behavior / limit |
|---|---|---|
| Worker exception | IMPLEMENTED (existing) | Attempt and failure retained; Task blocked |
| Validation/review exception | IMPLEMENTED (existing) | Validation-stage failure; completed records preserved |
| Correction-budget exhaustion | IMPLEMENTED (existing) | Task blocked; ineligible for this recovery mechanism |
| Durable integrity mismatch | IMPLEMENTED (existing) | Refuse open before restart writes |
| Interrupted executable work | IMPLEMENTED | Block on open; no automatic replay |
| Post-hoc timeout | IMPLEMENTED (detection only) | Result retained; timeout failure; blocked; no validation or promotion of late output |
| Open-time timeout classification | IMPLEMENTED | Overdue latest Attempt of running Task classified timeout; restart transition reason preserved |
| Explicit recovery | IMPLEMENTED (pure/local only) | All gates precede authorization; new lineage replays the original observation |
| Recovery-budget exhaustion | IMPLEMENTED | Derived lineage count; one exhaustion record per refused request; no new Task/Attempt |
| Authorization-then-crash | IMPLEMENTED (fail closed) | Orphan authorization consumes budget; A stays blocked; no automatic resumption or cleanup record; owner may make a normal new submission |
| Preemptive cancellation | DEFERRED | A synchronous worker that does not return cannot be stopped by this implementation |
| Result after an already-recorded failure | DESIGN ONLY | No `late_result` handling code |

## Test evidence

November 6, 2026, ChatGPT-local verification:

- `python3 -m unittest discover -s tests -v`: **98 tests passed in 1.932s; zero failures/errors**.
- The existing 62 parameterized skeleton tests and 11 durability tests pass unchanged. Both existing test files are byte-identical to baseline `0d83554`; no Phase 2/3 test body or fixture changed.
- P4-01 through P4-14 match the ADR numbering. Eleven shared cases execute against both ledgers through `patch.dict`; P4-10, P4-12 and P4-14 are SQLite-only: `73 + (11 × 2) + 3 = 98`.
- P4-13 checks discovery counts and baseline source hashes; the same full discovery command executes the 73 regression cases alongside the Phase 4 tests. It does not run a hidden nested copy of the suite.
- Coverage includes legacy absent policy, absent Attempt references, rejection without writes, binding/worker/actor checks, preserved record bytes, independent budgets, strict deadline equality, latest-Attempt selection, immutable snapshot values, SQLite reopening, and authorization-before-crash budget consumption.
- Controlled clock calls and patched open-time datetime avoid sleeps or killed processes. SQLite interruption fixtures stop between direct ledger calls and reopen. In-memory fixtures append the equivalent interruption failure and blocked transition directly, since the in-memory ledger has no reopen operation.

Independent execution by a second party has not occurred; test results above are ChatGPT-local.

No Phase 4 independent code review, CI result, owner acceptance, or production validation is claimed.

## Implementation choices not fully specified by the assignment

- Timeout declaration validation accepts positive finite built-in int/float values, excludes bool, and treats absent/None as no deadline. Invalid declarations raise ValueError before execution writes. This validation runs before duplicate handling in ordinary `run()`.
- Existing nonnegative-integer correction-budget validation is shared by run/recover. Recovery checks this and the timeout declaration after actor/reason and before recovery-budget accounting, so invalid arguments do not consume authorization or append an exhaustion record.
- The injected clock is expected to return timezone-aware datetime values. Core normalizes them to UTC for deadline arithmetic and serialization. It controls attempt timing, not record creation timestamps or adapter observation timestamps. SQLite samples one UTC open-time comparison value after integrity verification, before restart marking; its existing constructor interface is unchanged, and tests patch the module's datetime for deterministic classification.
- The common execution helper constructs Task B with the supplied adapter declarations and ordinary task fields, while replay eligibility uses Task A's stored policy and resource ceiling. The task key and observation come from A; only B's first Attempt has the replay reference. This follows the specified shared run path rather than adding per-attempt policy mechanisms.
- In-memory interruption fixtures have no physical close/reopen; they append the equivalent blocked-state records. SQLite cases exercise actual reopen behavior. P4-13 verifies source identity and discovery counts while the enclosing discovery run executes the unchanged regression suites.

## Limits

`ALLOWED_TRANSITIONS` is unchanged. No unblock edge, automatic recovery on open, timers, signals, threads, processes, async concurrency, second table, new ledger method, external calls, providers, agents, NFL, RAG or `late_result` implementation was added. Pure/local declarations and actor labels are not authenticated enforcement or sandboxing. The same five-call ledger API, INSERT-only writes, canonical hashes, sequence order and rebuilt indexes remain in place.

Record writes retain per-add commit boundaries; authorization and subsequent lineage writes are not one transaction. An orphan authorization consumes the one permitted recovery even when no new Task exists. Other storage/serialization failures retain the existing bounded prototype behavior rather than being normalized into a new failure subsystem. No production reliability or universal replay-safety claim is made.
