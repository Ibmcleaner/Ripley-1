# Phase 2: first executable skeleton — review correction pass

Status: **IMPLEMENTED prototype, NOT production validated, NOT ready to merge pending independent review.**

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

## Failure-mode maturity

| Mode | Status | Current behavior / limit |
|---|---|---|
| Malformed worker output | IMPLEMENTED (shape only) | Failed deterministic validation, correction request, bounded retry; no semantic correctness test |
| Worker exception | IMPLEMENTED (basic) | Execution Attempt and Execution Failure with exception type/message, blocked transition; no fabricated Result |
| Reviewer rejection | PARTIAL | Deterministic review rejects failed validation; human reviewer rejection workflow deferred |
| Correction-budget exhaustion | IMPLEMENTED | Explicit exhaustion record and blocked transition; no further attempt |
| Timeout | DEFERRED | No deadline enforcement or cancellation |
| Restart/recovery | DEFERRED | In-memory records are lost on process restart |
| Duplicate task/idempotency | PLANNED / REQUIRED BEFORE PHASE 2 ACCEPTANCE — **P2-IDEMPOTENCY-001** | Next named Phase 2 acceptance item, after execution-attempt/failure, task-transition, and bounded-correction primitives are stabilized and reviewed. Define deterministic task key, input equality/conflict policy, and in-memory duplicate guard; implement and test before Phase 2 acceptance. Not implemented or tested in this correction pass |

## Test evidence

Local verification on November 6, 2026, after rebasing onto Phase 1 merge `681426328dd4c76af631198e0fe4066ab998a757`:
- `python3 -m unittest discover -s tests -v`: **23 tests passed**, zero failures/errors (0.008 seconds).
- `python3 -m demo`: exit 0; reorder True, projected stock 2, validation True, approval pending_owner_approval.
- `git diff --check`: exit 0, no whitespace errors.

Tests cover adapter-owned facts, deterministic validation against a specific Result and contract, independent approval/rejection, content hashes, original-result preservation, linked corrections, immutable history, bounded exhaustion and worker failure. Repeated approval is rejected by task-state eligibility; this is **not** duplicate-task/idempotency protection. No GitHub CI or independent reviewer execution is claimed. Independent adversarial review remains required.

## Known limitations and Phase 1 alignment

No database, external AI provider, NFL implementation, RAG, autonomous security/debug agents, self-modifying learning, or live-event monitoring. No persistence, durable audit, secure worker identity, authorization, timeout enforcement, replay recovery, duplicate-task/idempotency guard (required before Phase 2 acceptance), event assessment workflow, outcome/grade/classification pipeline, or factual correction implementation. A worker exception is captured; validator/review internal exceptions are not yet normalized as failures. Validation checks are factual observations of checks, not guarantees of truth.

Phase 1 contracts are conceptual and do not prescribe complete state transitions or validation schemas. The added append-only state transitions and factual validation checks refine those contracts without changing the record principle. **In-memory storage is not production durability.**
