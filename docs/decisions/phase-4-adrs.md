# Phase 4 architecture decision records

Cyrus Ripley One (Ripley / R1) — Cyrus Forge Systems, LLC

These records continue [ADR-001 through ADR-006](phase-1-adrs.md) and [ADR-007](phase-3-adrs.md).

## ADR-008 — Explicit recovery and timeout detection

Status: **DESIGNED — formal ADR pending Claude and Copilot review.** Rob reports the Phase 4 whiteboard review completed by Rob, Copilot, and Claude. This record captures that supplied direction; it does not claim acceptance of this commit.

Implementation status: **NOT STARTED. Documentation only.**
Recorded: 2026-11-06
Baseline: `main` at `bbc89631ec372f52284dbfb91126c874be97f98f`.

### Context

Phase 3 durably records interrupted work and blocks it without rerunning it. Phase 4 addresses P4-RECOVERY-001 (when unfinished work may safely be replayed) and timeout semantics (how deadline overrun is detected and recorded). A repeated task key does not prove that repeating a worker's effects is safe.

> Task idempotency does not imply worker replay safety. Ripley must never automatically repeat an interrupted execution unless the execution policy explicitly permits replay.

Phase 4 is stricter than that general principle: even eligible replay requires an explicit recovery request. Opening a ledger never authorizes execution.

The Ripley Record Principle remains unchanged:

> Facts are durable. Assessments are attributable. Judgments are revisable. Revisions supersede rather than erase. History remains auditable.

### Decision — IMPLEMENT NOW (scope for a subsequent authorized implementation)

“IMPLEMENT NOW” identifies the bounded Phase 4 implementation scope. It is not authorization to implement during this documentation assignment.

#### Replay policy belongs to the submitted Task

The durable Task carries the adapter's declared `replay_policy`, copied at submission so the policy in effect remains auditable. The Worker does not self-declare replay safety.

| Task audit label | Engine behavior |
|---|---|
| `safe` | Replay may be permitted only after all additional recovery checks pass |
| `no` | Replay forbidden |
| `unknown` | Replay forbidden; fail closed |

For Phase 4, both the adapter declaration captured on the Task must be `safe` and the Task's `resource_ceiling` must equal `'no external calls'`. This deliberately limits SAFE_REPLAY to pure/local workers. External-call workers require future provider-side idempotency/replay guarantees and remain deferred. SAFE_REPLAY permits an explicit request without an override; it does not cause autonomous reruns.

#### Explicit recovery creates new lineage

The conceptual orchestration operation is `recover(blocked_task_id, actor, reason)`. It is not a new ledger storage method. Ripley never invokes it automatically on open.

Before authorizing recovery, verify:

1. The target Task's derived state is `blocked`.
2. Its blocking Execution Failure is eligible: `interrupted` or `timeout`. Worker failure, validation failure, and correction-budget exhaustion are ineligible.
3. Its recorded `replay_policy` is `safe`.
4. Its recorded `resource_ceiling` is `'no external calls'`.
5. Its recovery budget has not been exhausted.

An unknown or `no` policy rejects recovery without appending records. A resource-ceiling mismatch or an ineligible blocking failure rejects recovery. No policy override is introduced.

If all checks pass, first append a durable `recovery_authorization`, including the blocked Task reference, interrupted Attempt reference, actor, reason, and replay policy cited. Then create the new Task/Attempt lineage:

| New record | Required lineage |
|---|---|
| Task B | `previous_task_id = Task A`; `recovers_task_id = Task A` |
| Execution Attempt B | `replays_attempt_id = Execution Attempt A` |

Task A and its failed Attempt retain their original records. Task A remains terminal `blocked`. There is no `blocked → running` transition and no generic unblock operation. Recovery does not fabricate a successful outcome for the original Attempt.

#### Replay the same observation

Recovered execution reuses the original Snapshot inputs and metadata by reference/preserved value. It must not silently call observation collection again or replace observation time, sources, or data-quality metadata. A newly observed state is a new prediction/decision context, not a replay. Successful recovered execution follows the normal independent validation/review path to `pending_owner_approval`; recovery authorization is not owner approval of its Result.

#### Recovery and correction budgets are separate

The default recovery budget is **1**. Recovery concerns an Execution Attempt that did not finish normally. Correction concerns a Worker that completed but whose Result failed validation/review. Neither mechanism spends the other's budget.

When the recovery budget is exhausted, append `recovery_budget_exhaustion`, leave the lineage terminal/blocked, and perform no additional replay. Further work requires an explicit new submission under existing lineage rules. Recovery cannot obtain a fresh recovery allowance merely by creating the next Task in the same recovery lineage.

#### Timeout detection, not cancellation

The domain adapter may declare `timeout_seconds`; the default is `None` (no deadline). Execution Attempt records carry `deadline_at` to make their deadline auditable.

**Post-hoc detection:** after `worker.produce()` returns, if completion time is strictly greater than `deadline_at`, preserve the returned Result, append `execution_failure` with `stage: 'timeout'`, and transition the Task to `blocked`. Do not validate or promote the late Result, and do not automatically replay it. A returned value is a fact even when it missed its deadline.

**Open-time detection:** after normal durable integrity verification, if a `running` Task's latest Execution Attempt has passed `deadline_at`, append a timeout failure rather than a generic interrupted failure, then apply the normal block path. For other unfinished work, retain ADR-007's interruption behavior: `submitted`, `running`, and `validated` are blocked on open; `pending_owner_approval`, `blocked`, `approved`, and `rejected` remain untouched. The overdue-running case refines the failure classification; it does not introduce execution on open. Reopening after completed marking appends nothing further.

Timeout records why an Attempt failed. Replay eligibility is a separate decision enforced by explicit `recover()`: `safe` plus all other gates may permit recovery; `no` and `unknown` prohibit it.

The required maturity statement is:

> Ripley detects and records deadline overrun; it does not preemptively cancel worker execution.

A synchronous worker that never returns cannot be cancelled by this design. No threads, process pools, or asynchronous execution are introduced to enforce a deadline.

### DESIGN ONLY — Result arriving after a recorded failure

For future isolated/concurrent execution, a Result associated with an Attempt that already has an `execution_failure` is recorded as `late_result`. It remains factual history, is never validated or promoted, and consumes neither correction nor recovery budget.

Do not implement this record handling in Phase 4. It cannot naturally arise in the current synchronous execution model. This differs from the Phase 4 post-hoc path: there the returned Result is preserved before the timeout failure is recorded; no `late_result` mechanism is needed.

### Acceptance

These are required future acceptance tests, not claims of executed tests. The numbering matches the supplied Phase 4 assignment.

| # | Required test |
|---|---|
| P4-01 | `unknown` replay policy → recovery rejected; no records appended |
| P4-02 | `no` replay policy → recovery rejected; no records appended |
| P4-03 | `safe` but `resource_ceiling != 'no external calls'` → recovery rejected |
| P4-04 | `safe` plus eligible interruption → authorization present, new Task references old Task, new Attempt references interrupted Attempt, original blocked history unchanged |
| P4-05 | Recovered execution reaches `pending_owner_approval` using original observation Snapshot inputs and metadata |
| P4-06 | Recovery against worker failure, validation failure, or correction-budget exhaustion → rejected |
| P4-07 | Recovery budget exhausted → `recovery_budget_exhaustion` recorded; no additional replay |
| P4-08 | Correction budget and recovery budget remain independent |
| P4-09 | Post-hoc deadline overrun → Result preserved, timeout failure recorded, Task blocked, no Validation |
| P4-10 | Open-time overdue running Attempt → timeout failure, not generic interrupted failure |
| P4-11 | Timed-out Task: `safe` permits explicit recovery if remaining gates pass; `no`/`unknown` reject it |
| P4-12 | Recovery lineage survives SQLite close/reopen without retriggering on open |
| P4-13 | Existing Phase 2 and Phase 3 regression suites remain unchanged and passing as applicable |

### DEFERRED

Outside Phase 4: automatic replay on open; scheduled automatic recovery; preemptive cancellation; worker isolation; threads/process pools/async concurrency; provider-side idempotency; external-call SAFE_REPLAY; `late_result` handling code; per-attempt/conditional replay policies; NFL; production RAG; autonomous Security Agent; autonomous Debug Agent; advanced learning; real external AI providers; multi-provider optimization; cloud deployment; unrelated persistence expansion.

ADR-007's single application table, five-call ledger interface, INSERT-only record writes, canonical hashing and refuse-on-mismatch verification, sequence ordering, and rebuilt indexes remain the storage boundary. Recovery and timeout facts are appended through that interface. No schema migration, extra persistence system, authentication system, or new state-machine edge is authorized here.

### Compatibility and review notes

- ADR-007 calls P4-RECOVERY-001 “automatic recovery / re-execution.” This ADR narrows the Phase 4 scope to **explicit** recovery; automatic execution remains deferred. Earlier decisions are retained as historical phase records.
- ADR-007 classifies all unfinished executable states as `interrupted`. This ADR intentionally refines only an overdue `running` Attempt to `timeout`. Deadline-free Phase 2/3 fixtures retain the original behavior.
- Phase 2/3 allow an explicit fresh submission after a terminal Task, with `previous_task_id`. That remains a new submission, not evidence of safe replay or a substitute for `recovery_authorization`. Task-key deduplication alone cannot establish replay safety.
- Existing Task records have no replay-policy field, and restart can record `attempt_id = None` before any Attempt exists. The supplied direction does not specify the exact legacy-field handling or nullable `replays_attempt_id` contract. Review must resolve these before implementation; missing evidence must not be silently treated as `safe`, and an absent Attempt must not be invented.
- The concrete recovery-budget accounting fields, orchestration signature for obtaining the adapter/local worker, and crash behavior between authorization and new-lineage appends require implementation-contract review. Per-add durability does not imply atomicity of that sequence. This ADR does not authorize automatic resumption of a partially recorded recovery.
- The baseline Phase 3 document's status line records Claude review and owner merge, but its older Test evidence closing sentence still says no review outcome is claimed and acceptance/merge remain pending. That is a pre-existing documentation inconsistency; this documentation-only change leaves Phase 2/3 files untouched. Its historical 72-test paragraph predates the separately documented P3-11 test.

### Consequences and evidence boundary

Ripley can later offer bounded, attributable replay of the same observation without rewriting a failed Task or conflating idempotency with replay safety. Deadline overrun becomes a visible failure, not a claim of cancellation. Recovery introduces new auditable authorization and lineage records, and remains an explicit operation.

This commit adds only the ADR. No Phase 4 production code or acceptance tests have been implemented or run. Existing maturity remains prototype-level, not production validated.

Independent execution by a second party has not occurred; previously reported Phase 2/3 test results are ChatGPT-local. Claude's code review is distinct from independent test execution. Claude and Copilot review this ADR commit before any Phase 4 implementation begins; Rob retains merge authority.
