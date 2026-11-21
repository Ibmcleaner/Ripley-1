# Ripley One — Offline Infrastructure Phase Exit Record

Prepared: 2026-11-20. Owner: Robert Legorreta, Cyrus Forge Systems, LLC.

## 1. Status of this record

This record is published in a Draft pull request and independently reviewed before the owner decides. It becomes the formal acceptance of the Ripley One Offline Infrastructure Phase only by the owner's merge of that pull request into main. This file exists on main only if the owner merged it; in that case the merge commit is the acceptance, and its date is the acceptance date. If you are reading this file on a branch or in an open pull request, the phase is not yet accepted.

Completing this phase is not production readiness, not provider readiness and not modeling readiness.

## 2. Why this phase existed

Owner direction of 2026-11-20 set the priority as infrastructure: how the engine works, what it does, and how it is prepared to gather data for a future model. The phase was meant to prove, offline and with evidence, the core of Ripley One: one task, one worker, an honest durable record, bounded execution, and a way to preserve and verify the exact input bytes a task relied on.

The phase covers the work recorded in docs/PROJECT_STATE.md section 7 from Phase 1 (2026-11-04) through the Sprint 10 closeout (2026-11-20).

The seven-condition exit gate was defined and approved by the owner on 2026-11-20, after most of the phase's work was complete and before Sprint 10 was chosen. Sprint 10 was selected to satisfy condition 5.

## 3. Accepted baseline

- Code, tests and CI: main aca9d4d2264a71fe6b41d286c745a43a1e06907a (merge of PR #40). Its tree is identical to commit fa9c136189a7d3d839d12717445ddedd8c1d5915, which Claude reviewed.
- Main immediately before this record: c168067246f5d0c8c4aa7cbee82174787c3053a0 (merge of PR #41). It differs from aca9d4d in four documentation files only.
- CI tooling, unchanged since PR #38: runner SHA-256 95b5dfd04e30938e94b6835b52aecfdd55a658c4018a4c74972f8cf207675643; workflow SHA-256 68b451b8994aaf2e67cf261d95aca71d880a79ea4c6dcda41284cc5d4369c239.
- Test suite at this baseline: 231 tests. Linux: 231 run, 0 skipped (independently run by Claude). Windows: 231 run, 4 expected Phase 5 skips (reported by the owner).
- This record changes documentation only.

## 4. Governing decisions

- ADR-001 to ADR-006: Phase 1 architecture (docs/decisions/phase-1-adrs.md).
- ADR-007: durable ledger and restart honesty.
- ADR-008: explicit recovery and timeout detection.
- ADR-009: local Worker process isolation and enforceable deadlines.
- ADR-010: external provider Worker and paid-dispatch governance.
- ADR-011: offline capture receipt and artifact store.
- ADR-012: Snapshot-to-capture linking.
- Cyrus Engineering Doctrine v1 (docs/architecture/cyrus-engineering-doctrine.md). Adoption does not certify that Ripley conforms.

## 5. Exit gate evaluation

| # | Condition | Status | Evidence in the repository |
|---|---|---|---|
| 1 | Core execution and evidence flow proven within bounded local and mock scope | SATISFIED | Phase 2 skeleton (PR #2, docs/phase-2-skeleton.md); full suite at the accepted baseline |
| 2 | Durable state and honest recovery proven | SATISFIED | Phase 3 (ADR-007, PR #3, docs/phase-3-durable-ledger.md); Phase 4 (ADR-008, PR #5, docs/phase-4-recovery-timeout.md) |
| 3 | Worker isolation and bounded execution proven | SATISFIED | Phase 5 (ADR-009, PR #9, docs/phase-5-worker-isolation.md) |
| 4 | Offline local-file capture and provenance foundation proven | SATISFIED | Sprint 7 (ADR-011, PR #34) and Sprint 9 corrections (PR #38); docs/capture.md |
| 5 | A Task/Snapshot identifies the exact capture evidence it consumed and Ripley verifies that evidence | SATISFIED | Sprint 10 (ADR-012, PR #40); docs/capture.md, "Sprint 10 acceptance evidence" |
| 6 | Advisory full-suite CI proven | SATISFIED | Sprint 8 (PR #36) and Sprint 9 runner corrections (PR #38); docs/ci.md |
| 7 | A final repository phase-exit record states the evidence, limitations and deferred work, and the owner accepts the phase by merging it | SATISFIED BY THE OWNER'S MERGE OF THIS RECORD | This file. See section 1 |

## 6. What was built and proven

Each item is proven only within the scope stated. Detailed evidence is in the records cited in section 5 and in docs/PROJECT_STATE.md.

- Bounded Task, Worker and Result execution: one task, one worker, no agents and no queues.
- A deterministic validation, review and approval flow.
- An append-only, hash-verified ledger with durable state (ADR-007).
- Restart honesty, explicit recovery and timeout detection (ADR-008).
- Local Worker process isolation with enforceable deadlines (ADR-009).
- A provider Worker and paid-dispatch governance, tested through mock transport and offline mechanisms only (ADR-010; Phase 6B, 6C, 6D-prep; Sprint 5).
- An offline dispatch identity preflight (Sprint 6). The owner's Windows preflight matched 12 of 12. Passing it does not authorize a dispatch or establish provider acceptance.
- Offline exact-byte capture of a local file from an approved directory into a content-addressed store outside the repository, with a capture receipt in the ledger (ADR-011).
- Capture verification with three outcomes: MATCHED, MISMATCHED, UNAVAILABLE.
- Snapshot-to-capture linking: references stored on the Snapshot, verified before every worker attempt, re-verified on recovery, and pinned in the Evidence record (ADR-012).
- One advisory Linux check on pull requests: full suite, pinned SDK, zero skips, disposable copy, read-only token, no secrets.

How it was verified:

- Independent Linux review by Claude of every published commit from Sprint 7 through Sprint 10, with a full-suite run on each tested commit.
- Mutation checks: seven in Sprint 9 and fifteen in Sprint 10, all detected.
- A synthetic end-to-end provenance trace in Sprint 10, using a newly created non-NFL file and reconstructed from the SQLite ledger alone. Fourteen checks passed.
- Three literal pins showing the frozen provider request unchanged by Sprint 10.
- Owner Windows runs, recorded as owner-reported.
- Hosted advisory runs, recorded in each closeout with observed and implementer-reported results kept separate.

## 7. Operating boundaries that remain

- Capture is offline and local-file only. It is sequential-only; concurrent capture is unsupported, untested and unclaimed. An abruptly terminated capture can leave a temporary file.
- Capture references are accepted on local workers only. Provider workers refuse them.
- Approval does not re-verify stored capture bytes.
- Worker isolation is process isolation with time bounds. It is not a sandbox for hostile or untrusted code.
- The CI check is advisory. It is not a merge gate, not a network sandbox, and does not run Windows. Its connection guard covers the main test process only.
- Reference test runs need proxy variables unset (docs/ci.md, "Local commands").
- The provider request, prompt, model, schema and dispatch logic are frozen by owner direction.

## 8. What this phase does not claim

Acceptance of this phase does NOT establish any of the following:

- production readiness
- successful live provider validation
- provider recovery
- authorization of Dispatch #3
- completion of Phase 6E
- the historical root cause of FI-001
- authenticity of any source
- truth of source declarations
- correctness of extraction or parsing from captured bytes
- network acquisition
- concurrent capture
- approval-time re-verification of stored capture bytes
- sandboxing of hostile or untrusted code
- any agent implementation
- any source-reader implementation
- modeling readiness
- NFL predictive capability

## 9. Provider and FI-001 status

- Provider path: mock-proven. Live validation is incomplete. Two authorized live dispatches were used and neither produced model output (#1 auth_rejected, since remediated; #2 HTTP 400).
- Dispatch #3: PAUSED and UNAUTHORIZED.
- Phase 6E: NOT STARTED.
- FI-001 historical cause: UNCONFIRMED, externally pending.
- Provider support response: externally pending.

This record does not reopen provider work and authorizes no dispatch.

## 10. Remaining work and its disposition

No classification below is an authorization. Each item needs its own planning, review and owner decision.

| Item | Classification | Note |
|---|---|---|
| Test P6-11 briefly rewrites the real prompt file | BACKLOG | Change to a temporary copy in a sprint allowed to touch existing tests |
| Phase 1-era rows in docs/project-status.md | BACKLOG | Excluded from this record's pull request by owner direction |
| Read-only ledger status report | NEXT-PHASE CANDIDATE | |
| Source-reader ADR | NEXT-PHASE CANDIDATE | Timing not decided |
| Sequential-only capture | DEFERRED | Accepted limitation; revisit only on evidence of need |
| CI connection guard covers the main process only | DEFERRED | Accepted limitation |
| Whether the advisory check becomes a required check | DEFERRED | Owner decision, not made |
| Capture references on provider workers | DEFERRED | Requires the provider freeze lifted and a new decision |
| Approval-time re-verification of capture bytes | DEFERRED | Owner decision in Sprint 10 |
| Network acquisition for capture | DEFERRED | Needs an owner decision on sources and a rights classification |
| Agent implementation | DEFERRED | By owner direction and Doctrine section 12 |
| Modeling and NFL work | DEFERRED | By owner direction of 2026-11-20; recovered NFL material is reference only |
| Live provider validation, Dispatch #3, Phase 6E | EXTERNALLY BLOCKED | Pending the provider's reply on FI-001, and then a separate written owner authorization |

Other ideas remain listed in docs/PROJECT_STATE.md section 8. None is designed, scheduled or authorized.

## 11. What happens next

After the owner accepts this phase, the next action is a Phase Transition Round Table. The next phase is selected only there. This record does not choose it, does not name it and does not authorize any of its work. Sprint numbering restarts at Sprint 1 once the next phase is named. No Sprint 11 exists.

## 12. Acceptance

Accepted by: Robert Legorreta, Product Owner, by merging the pull request that adds this file to main. No signature line is used; the repository history is the record.
