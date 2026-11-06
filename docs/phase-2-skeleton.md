# Phase 2: first executable skeleton — review correction pass

Status: **IMPLEMENTED prototype, locally tested, reviewed by Claude at 879c245 — awaiting owner merge. NOT production validated.**

Run: `python -m demo`
Tests: `python -m unittest discover -s tests -v`

## Bounded architecture

The synthetic inventory adapter owns its observation timestamp, source references, and data-quality label. Core records these values without choosing them. The Task remains domain-neutral and includes a worker allowlist.

Execution is: Snapshot → Task → append-only Task State Transition (running) → Execution Attempt → Result or Execution Failure. Successful results receive a versioned deterministic Validation Check, separate Review, linked Evidence, and Pending Owner Approval. Invalid output receives Review → Correction Request → new Execution Attempt → new Result and independent Validation Check, with a finite correction budget. Exhaustion produces a blocking record and task transition. A rejected Result is never modified. No automated debugging agent exists.

A Validation Check is a factual record that a named validator/version/ruleset checked a referenced Result and observed a particular outcome. If a validator is defective, a corrected validator creates a **new** check; old checks remain. An interpretive/model-based Validation Assessment, if later needed, is a separate revisable judgment, **not implemented**. Review, event assessment, classification and approval judgments can be superseded without erasing prior records. Task state is derived from append-only transition history, never mutated in the original Task.

The Ledger exposes records through a read-only mapping. This is a guard against ordinary direct replacement/deletion, not tamper-resistant storage, and not an authentication boundary. Snapshot contents and Result contents are frozen in memory.

## Content links and explicit approval

Records carry SHA-256 of canonical JSON containing kind, frozen data and supersedes. The record envelope's generated ID and timestamp are excluded from that hash; referenced IDs inside data remain included. Supported values are finite JSON scalars, string-keyed mappings and sequences; mutable custom objects are rejected. Hashes establish content identity, not authenticity or production tamper resistance.

Each Validation Check binds the Result hash and the output-contract fingerprint, validator identity/version and ruleset. Rechecking the same Result under the same contract produces the same finding; check record IDs/times can differ. A changed contract or validator creates a new factual check without rewriting an earlier one.

A correction artifact links the original and replacement Result IDs/hashes, requesting reviewer, reason and request ID. Evidence links Task, Snapshot, Result, Validation and Review by ID and content hash. Automatic validation creates only a pending approval request. `decide_approval` requires an explicit owner-labeled approve/reject decision and reason, appends a decision superseding the pending record and appends the resulting task-state transition. Approval binds the existing evidence and Result; a superseded review cannot authorize it. This prototype does not authenticate the caller's owner label. A revised review requires a future refreshed-evidence workflow; no automatic reapproval is implemented. The demo deliberately stops pending approval.

## Run return contract

Every `run()` return has the same keys: outcome, task, snapshot, attempt, result, validation, review, evidence, approval, failure, blocked, authorization, results, validations, reviews, corrections. Unused single records are `None`; collection fields are always tuples. Outcomes are `pending_owner_approval`, `blocked_worker_failure`, `blocked_validation_failure`, `blocked_budget_exhausted`, `blocked_timeout`, and `duplicate_of_existing_task`. The validation-failure outcome names the new failure path explicitly, rather than mislabeling it as a worker failure. Validator calls, validation provenance checks, validation-record creation and review-record creation share the bounded exception handler. Completed records remain preserved if a later stage raises.

## P2-IDEMPOTENCY-001 — in-memory duplicate policy

The Task stores `task_key = content_hash({'domain_id': adapter.domain_id, 'domain_version': adapter.version, 'task_type': 'predict', 'inputs': inputs})`. The existing canonical serializer sorts mapping keys recursively, uses compact JSON separators, rejects nonfinite numbers and hashes UTF-8 bytes with SHA-256. Dictionary insertion order does not affect the key, including nested mappings. Inputs are frozen before keying and snapshot creation. Sequence order and JSON value types remain significant. Snapshot hashes and observation timestamps are excluded.

Ledger indexes each key to its latest Task ID. After ordinary execution-policy checks, a same-key submission whose existing derived state is nonterminal appends only a `duplicate_submission` referencing that task. It returns the existing Task with outcome `duplicate_of_existing_task`, no new Snapshot/Task/Attempt, and empty collections for this submission. It does not call the adapter's timestamp-bearing snapshot metadata function.

If the indexed task is `blocked`, `approved`, or `rejected`, a fresh Snapshot/Task and execution attempt are allowed. The new Task records `previous_task_id`, retains the same key, and becomes the indexed task. The old records and terminal state remain intact. This deliberately deduplicates active work, not all historical work forever; different inputs/domain versions produce different keys. The policy is in-memory and single-process sequential only: no persistence, restart recovery or concurrent submission guarantee is claimed. No state-machine transitions were added.

Status: **IMPLEMENTED AND LOCALLY TESTED; awaiting independent review.** Landing this change does not itself constitute Phase 2 acceptance.

## Failure-mode maturity

| Mode | Status | Current behavior / limit |
|---|---|---|
| Malformed worker output | IMPLEMENTED (shape only) | Failed deterministic validation, correction request, bounded retry; no semantic correctness test |
| Worker exception | IMPLEMENTED (basic) | Execution Attempt and Execution Failure with exception type/message, blocked transition; no fabricated Result |
| Validator/review-record exception | IMPLEMENTED (basic) | Failure records stage validation, attempt ID, exception type/message; running → blocked with validation_failure; completed records preserved |
| Reviewer rejection | PARTIAL | Deterministic review rejects failed validation; human reviewer rejection workflow deferred |
| Correction-budget exhaustion | IMPLEMENTED | Explicit exhaustion record and blocked transition; no further attempt |
| Timeout | DEFERRED | No deadline enforcement or cancellation |
| Restart/recovery | DEFERRED | In-memory records and task-key index are lost on process restart |
| Duplicate task/idempotency | IMPLEMENTED AND LOCALLY TESTED — **P2-IDEMPOTENCY-001**; review pending | Canonical key; active duplicates reference existing Task without new Snapshot/Task; terminal blocked/approved/rejected tasks permit new lineage; sequential in-memory scope only |

## Test evidence

Local verification on November 6, 2026, after rebasing onto Phase 1 merge `681426328dd4c76af631198e0fe4066ab998a757`:
- `python3 -m unittest discover -s tests -v`: **31 tests passed**, zero failures/errors (full output reported in the PR handoff).
- `python3 -m demo`: exit 0; reorder True, projected stock 2, validation True, approval pending_owner_approval.
- `git diff --check`: exit 0, no whitespace errors.

Independent execution by a second party has not occurred; test results above are ChatGPT-local.

Tests cover adapter-owned facts, deterministic validation against a specific Result and contract, independent approval/rejection, content hashes, original-result preservation, linked corrections, immutable history, bounded exhaustion and worker failure. Additional tests cover validator/review exceptions, uniform returns, pending duplicates, terminal resubmission, different inputs/versions, and nested mapping-order invariance. No GitHub CI or independent reviewer execution is claimed. Independent adversarial review remains required.

## Known limitations and Phase 1 alignment

No database, external AI provider, NFL implementation, RAG, autonomous security/debug agents, self-modifying learning, or live-event monitoring. No persistence, durable audit, secure worker identity, authorization, timeout enforcement, replay recovery, event assessment workflow, outcome/grade/classification pipeline, or factual correction implementation. Worker and validator/review exceptions are captured; snapshot/serialization/evidence-storage exceptions are not normalized by these bounded handlers. The duplicate guard does not survive restarts or provide concurrency control. Validation checks are factual observations of checks, not guarantees of truth.

Phase 1 contracts are conceptual and do not prescribe complete state transitions or validation schemas. The added append-only state transitions and factual validation checks refine those contracts without changing the record principle. **In-memory storage is not production durability.**
