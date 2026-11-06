# Phase 3 — Durable Ledger & Restart Honesty

Status: **IMPLEMENTED prototype, ChatGPT-locally tested; awaiting Claude review and owner acceptance. NOT production validated.**

Authority: [Accepted ADR-007](decisions/phase-3-adrs.md). No automatic recovery or re-execution is implemented.

## Implemented boundary

`SQLiteLedger(path)` preserves the same five public ledger calls: `add`, `records`, `task_for_key`, `task_state`, `transition`. `Ripley.__init__` already accepts either ledger without modification. In-memory Ledger remains the default. Each database operation closes its connection; each add commits independently before publishing the record in memory. Reopening means constructing a new SQLiteLedger for the same file, not invoking a sixth close/open method.

One application table, `records`, has the specified columns: seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, kind TEXT, at TEXT, supersedes TEXT NULL, content_hash TEXT, data TEXT. SQLite itself creates its internal sqlite_sequence bookkeeping for AUTOINCREMENT; there is no second application table or persisted task index. Schema creation is DDL; the only row-writing SQL statement in ripley/ is INSERT. No schema versioning, concurrent writer support, or application locks were added.

`canonical_json` supplies sorted keys, compact separators, allow_nan=False and UTF-8 bytes to both hashing and persistence. Phase 2 hashes the envelope `{kind, data, supersedes}`, not the payload alone. Therefore the data TEXT column stores that complete canonical envelope, decoded as UTF-8 for SQLite TEXT and encoded back to identical bytes on read. Record.data still exposes the frozen inner payload, preserving the existing API and hashes. IDs and timestamps retain the Phase 2 boundary: they are outside their own record's content hash.

Opening verifies every row's stored bytes and hash, canonical form, and kind/supersedes agreement before appending restart evidence. A mismatch refuses open. The task-key index is rebuilt in seq order from task rows, with the newest lineage member winning. Both Ledger implementations raise a clear ValueError when a task record lacks task_key. task_state and prior-transition lookup use ORDER BY seq; transition-chain consistency is checked against that order. Derived state and the task-key index are never persisted separately.

## Restart policy

Tasks whose derived state is **submitted**, **running**, or **validated** are interrupted executable work. On open, append execution_failure with stage **interrupted**, latest attempt_id for that task or None, and message **interrupted_by_restart**. Then append a transition from the observed state to **blocked**, actor **ripley**, reason **interrupted_by_restart**. The constructor-only transitions from submitted/validated to blocked do not broaden ordinary Phase 2 execution transitions.

Tasks in **pending_owner_approval**, **blocked**, **approved**, or **rejected** are untouched. Owner approval can be recorded after reopen. A second open after completed restart marking appends nothing. Interrupted work is never silently resumed or rerun. Automatic recovery/re-execution is deferred as **P4-RECOVERY-001**.

Active task duplicates continue to reference the existing task. A task blocked by restart is terminal, so a later explicit run may create a new task with previous_task_id under the existing Phase 2 policy; constructor restart marking itself never calls run.

## Failure-mode maturity

| Mode | Status | Current behavior / limit |
|---|---|---|
| Malformed worker output | IMPLEMENTED (shape only) | Separate failed validation, bounded corrections; semantic checking remains outside scope |
| Worker exception | IMPLEMENTED (basic) | Attempt/failure records and blocked transition |
| Validator/review-record exception | IMPLEMENTED (basic) | Stage validation failure and blocked transition; completed records preserved |
| Reviewer rejection | PARTIAL | Deterministic review only; human reviewer workflow deferred |
| Correction-budget exhaustion | IMPLEMENTED | Exhaustion record, blocked task, no further attempt |
| Durable records | IMPLEMENTED | Per-add SQLite commits; immutable exposed records; one application table |
| Hash mismatch on open | IMPLEMENTED (refuse) | All stored hashes verified before restart writes; no automatic repair |
| Interrupted by restart | IMPLEMENTED (block only); recovery deferred P4-RECOVERY-001 | submitted/running/validated blocked with evidence; waiting and terminal states untouched |
| Duplicate task/idempotency | IMPLEMENTED (sequential) | Index rebuilt on open; active duplicate retained; terminal task allows explicit new lineage |
| Timeout | DEFERRED | No deadline enforcement or cancellation |
| Automatic recovery/re-execution | DEFERRED — P4-RECOVERY-001 | No automatic resume, replay or retry |
| Restart-only transition edges | IMPLEMENTED (gated) | test_p3_11 verifies already-open SQLiteLedger and in-memory Ledger reject submitted/validated → blocked even with restart actor/reason |

## Test evidence

November 6, 2026, local verification:

- `python3 -m unittest discover -s tests -v`: 72 tests passed in 1.043s; zero failures/errors. 31 existing test bodies run against Ledger and again against SQLiteLedger (62), plus ten numbered ADR tests (10).
- `tests/test_durable.py`: test_p3_01 through test_p3_10 correspond to the ADR table. Interruption fixtures stop between ledger calls, without killing processes. Test 01 also verifies storage order versus transition lineage, exact canonical stored bytes, and missing task-key rejection. Test 06 covers all three interrupted states.
- The parameterization uses only fixture/class wiring: all 31 Phase 2 test method sources were compared to main and are byte-for-byte unchanged. Fresh temporary database paths isolate every test and every additional ledger created inside a test.
- ADR documentation was checked byte-for-byte against the supplied attachment.

Independent execution by a second party has not occurred; test results above are ChatGPT-local.

No CI or independent code-review outcome is claimed for Phase 3. Acceptance and merge remain with the reviewer and owner.

## Limits

No timeouts, automatic recovery, threads/concurrency, additional application table, schema migration/versioning, authentication, NFL, RAG, providers, agents or cloud deployment. Storage is local and sequential. Hashes detect content mismatch; they are not authenticated signatures or a guarantee against an actor rewriting both data and hashes. Per-add commit boundaries do not make a multi-record run or restart-marking sequence atomic. Backups, retention, tamper repair and operational recovery are deferred.
