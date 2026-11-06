# Phase 3 architecture decision records

Cyrus Ripley One (Ripley / R1) — Cyrus Forge Systems, LLC

These records continue the numbering in `phase-1-adrs.md` (ADR-001 through ADR-006).

## ADR-007 — Durable ledger and restart honesty

Status: **Accepted** (whiteboard: Rob, Copilot, Claude — November 6, 2026)

### Context

Phase 2 established Ripley's domain-neutral execution and record model using an in-memory ledger. That proves contract behavior during one process lifetime but does not establish durability. Ripley's Record Principle (ADR-003) requires historical facts and their audit lineage to survive process termination without silent rewriting or invention.

### Decision

Ripley's **first** durable ledger uses Python's standard-library `sqlite3`. "First" is deliberate: the ledger interface is held at its current five public calls (`add`, `records`, `task_for_key`, `task_state`, `transition`) so that the storage backend can be replaced later without touching orchestration. Phase 3 adds no sixth call.

The durable store:

1. uses a single local SQLite database file, one table, no second table;
2. stores records append-only: **the ledger module contains exactly one SQL write statement, `INSERT`.** No `UPDATE`, `DELETE`, `REPLACE`, or `INSERT OR REPLACE` may appear anywhere under `ripley/` for any reason. Reviewers verify by search, and a test asserts it;
3. uses an explicit insertion sequence (`seq`) as the durable storage order. The `preceding_transition_id` chain remains the semantic truth for transition lineage; storage order and the chain must agree, and a test asserts that they do;
4. rebuilds every derived structure — the task-key index and all derived task states — from durable records when opened. No derived index or state cache is ever persisted as a second source of truth;
5. uses one canonical JSON representation for both persistence and content hashing: a single `canonical_json()` helper in `ripley/core.py` is used by `content_hash` and by the store. The `data` column holds the exact bytes that were hashed;
6. re-verifies every stored record's `content_hash` against its stored bytes on open and **refuses to open** on any mismatch. A ledger containing an unverifiable record is not a ledger Ripley reasons from;
7. preserves Phase 2 idempotency semantics (P2-IDEMPOTENCY-001) across restart: same task key with an active task → `duplicate_submission`; same key with a terminal task → new task with `previous_task_id`.

### Restart policy

Phase 3 provides **restart honesty, not automatic recovery.**

Interrupted executable work is defined by state: any task whose derived state on open is `submitted`, `running`, or `validated` — the three states that exist only inside a `run()` call. For each such task, on open, Ripley appends an `execution_failure` record (`stage: 'interrupted'`, `attempt_id` = the task's latest execution attempt or `None`, `message: 'interrupted_by_restart'`) and then appends a transition to `blocked` with reason `interrupted_by_restart`. Ripley never silently resumes or re-runs interrupted work.

Tasks in `pending_owner_approval` are legitimately waiting for a human and are **untouched** by restart; `decide_approval` must work after reopen. Tasks already in `blocked`, `approved`, or `rejected` are untouched.

The restart policy is idempotent: opening a ledger a second time appends nothing.

Automatic recovery / re-execution of interrupted work is deferred and named **P4-RECOVERY-001**.

### In-scope changes to existing Phase 2 code

These are corrections required by persistence, not scope creep:

- `task_state()` and the prior-transition lookup currently depend on dict insertion order; under the durable store they order by `seq`.
- `Ledger.add` reads `task_key` from any `task` record without a guard; the open-time index rebuild walks every task row, so a missing key must raise a clear error rather than crash open.
- `content_hash` and the store must share `canonical_json()` so hashes re-verify after reload.

### Acceptance

Phase 3 is not accepted merely because rows can be saved and reloaded. Acceptance requires all of the following, each with a named test (`test_p3_01` … `test_p3_10` in `tests/test_durable.py`):

| # | Property | Test |
|---|---|---|
| 01 | Round-trip integrity | Full run → close → reopen → every `task_state` identical, every hash re-verifies |
| 02 | Interruption before any attempt | Task + first transition only → reopen → `blocked`, `stage: 'interrupted'`, `attempt_id` is `None` |
| 03 | Interruption after attempt, before result | → reopen → `blocked`, failure references that attempt |
| 04 | Interruption after result, before validation | → reopen → `blocked`; result preserved; no validation fabricated |
| 05 | Waiting-for-owner untouched | `pending_owner_approval` → reopen → unchanged; `decide_approval` succeeds |
| 06 | Restart policy idempotent | Reopen twice → record count unchanged by second open |
| 07 | Idempotency across restart | Active duplicate → `duplicate_of_existing_task`; blocked-by-restart → new lineage |
| 08 | Index rebuilt from records | Key with two-task lineage → after reopen `task_for_key` returns the newest |
| 09 | Tamper detection | Modify one row's `data` out of band → open raises; nothing appended |
| 10 | Append-only enforced | Source of the ledger module contains no `UPDATE`/`DELETE`/`REPLACE` |

Plus: the existing Phase 2 suite runs **unchanged** against both the in-memory `Ledger` and `SQLiteLedger` (parameterized; zero test-body edits).

Interruption is simulated by stopping between ledger calls — building the partial state, closing, and reopening — not by killing processes. The ledger's commit boundary is per-`add`, so "between two adds" is the unit of interruption that matters.

### Deferred

Explicitly outside Phase 3: automatic recovery / re-execution (P4-RECOVERY-001); timeout or deadline enforcement; concurrency of any kind (threads, multiple processes, locking); schema migration or versioning; any query or reporting interface beyond what tests need; backup, compaction, retention; encryption at rest; authentication of the owner label; real reviewers or external providers; NFL; RAG; security or debug agents; self-modifying learning; cloud deployment.

### Consequences

Ripley's facts survive the process. Interrupted work is visible and blocked rather than silently lost or silently retried. The in-memory ledger remains the test-speed default; the SQLite ledger is the first durable implementation behind an unchanged interface. The cost is one more module, one table, and ten tests.
