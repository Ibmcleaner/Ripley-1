# Ripley One — Project State and Handoff

Last updated: 2026-11-20, against main aca9d4d (PR #40).
Owner: Robert Legorreta, Cyrus Forge Systems, LLC.

Read this file first in any new chat. It is the entry point, not the full record. Where this file and a detailed record disagree, the detailed record (ADR, pilot record, FI record) is correct and this file needs fixing.

## 1. Vision

Cyrus Forge Systems builds durable engines meant to stay useful for many years, not disposable AI apps that customers must rebuild. Revenue comes from continuing value, never from preventable failures.

- One engine, many uses. An engine must transfer to different customer needs.
- Human-in-the-loop is part of every Cyrus engine.
- The engine must not grade its own homework.
- Design for extension. Build the minimum necessary foundation. Prove the foundation. Then add capability in controlled layers.
- Build what we need. Earn complexity through evidence.
- This repository is also the owner's engineering portfolio. The real process is documented as it happens, including failures and limitations.

Priority order (Doctrine v1, section 1): Security and Core Integrity; Health and Customer Protection; Reliability and Service Continuity; Failure Intelligence and Safe Recovery; Evolution and Modernization; Performance and Efficiency; Customer Extensibility.

Evolution cannot violate security. Performance cannot violate correctness. Availability cannot justify corrupted evidence. Autonomy cannot overrule governance.

The governing standard is docs/architecture/cyrus-engineering-doctrine.md (Doctrine v1, accepted 2026-11-19). Adopting it is not evidence that Ripley implements it.

## 2. What we are building

Cyrus Ripley One (Ripley, R1) is a domain-agnostic engine. The Core handles tasks, workers, results, validation, review, evidence and approval. It contains no domain logic.

Core flow: Task -> Ripley -> Worker -> Result -> Validation -> Review/Correction -> Evidence -> Approval

- Today Ripley runs one task through one worker and records hash-verified evidence in an append-only ledger. It has no agents, no queues and one provider. An advisory test check runs on pull requests; it is development tooling, not part of the runtime.
- The NFL is the first real domain. It was chosen because it is a hard, multi-pipeline problem. All NFL logic lives outside the Core.
- A small synthetic non-NFL domain exists to test the domain-agnostic claim.
- The first NFL task is a pregame player-availability brief, not game prediction.
- NFL Predictor V2+ is a future workload on Ripley. It is not the current build.
- The separate market-informed weekly NFL beta is not part of Ripley, is never cited as Ripley evidence, and is frozen and untouched by Ripley work.
- Future domains under consideration: inventory and demand, logistics, sales forecasting, business operations.

## 3. Agent and orchestration direction

This section is direction, not an accepted design.

- Ripley is intended to become an agentic orchestration platform. Domain workloads exercise the platform without redefining it.
- Orchestration and state are native to Ripley. No LangGraph, CrewAI, BeeAI, Microsoft Agent Framework or AutoGen in the control plane. Reopen only on evidence, and then only bounded inside a Worker. (Owner decision, 2026-11-17.)
- Agents are defined by responsibility before count. There is no fixed number of agents.
- Hard spending limits must not depend solely on an LLM agent.
- No agent design has been accepted. Building any agent capability requires an ADR and an owner decision.

Owner direction, 2026-11-20 (record direction, defer implementation): the first future agent capability to evaluate is a bounded source-reader / extraction Worker: captured artifact -> proposed structured observations -> deterministic validation -> human or independent review. This is direction only. No agent has been implemented and no agent ADR has been accepted. Any agent implementation requires a future ADR and an owner decision. Capture, hashing, validation, budgets, state transitions and approval remain deterministic controls.

## 4. Roles

| Who | Role |
|---|---|
| Robert Legorreta | Product Owner and CEO. Sets priorities, makes owner decisions, accepts work, merges, and personally signs any live or paid authorization. |
| Copilot | Senior PM and Scrum Master. Chairs round tables, rules on scope, writes decision briefs, keeps the decision log. Does not implement or review code. |
| Claude | Architecture lead and principal independent reviewer. Writes assignments, reviews published commits, runs tests on Linux. Does not push to the repository. |
| ChatGPT | Primary implementer and documentation maintainer. Builds on a branch, publishes its own branches and PRs. Does not merge. |

The owner relays every message between models. Models work from actual artifacts (files, diffs, test output), not summaries.

## 5. Workflow

Work runs in short Sprints. No story points, velocity targets or ceremony.

Each Sprint has: a Sprint Goal, a prioritized backlog, acceptance criteria, a Definition of Done, and assigned implementation and review responsibilities.

Normal sequence:
1. Owner sets the direction.
2. Claude proposes the architecture. ChatGPT gives an independent implementation view.
3. Copilot compares both and writes one decision brief.
4. Owner decides GO or NO-GO.
5. Claude writes the assignment as one copy block. Copilot makes a final scope check.
6. ChatGPT implements on a branch, opens a draft PR and reports back.
7. Claude reviews the published commit and runs the tests on Linux.
8. Owner runs the tests on Windows where the sprint calls for it.
9. Owner merges.
10. A closeout PR records the evidence and updates sections 6 and 7 of this file.

Daily cadence: a round table each morning at 9:00 AM Central and a closeout recap each evening. Each party states what it needs from the others and from the owner.

Status updates use: Completed / In progress / Blocked / Owner decision needed / Next.

Each Sprint ends with a Review on working evidence and a short Retrospective: what worked, what caused rework, what should change, what should remain, one improvement to carry forward.

Definition of Done: acceptance criteria met, tests run independently with results recorded, PR merged by the owner, and this file updated.

Standing rules:
- The repository is the system of record. Chat history is not.
- Never claim something is implemented or tested without evidence. Use the maturity labels in docs/project-status.md.
- Never silently redesign established architecture. Raise the concern with reasoning and an alternative.
- Think independently. No agreement for the sake of consensus. Separate evidence from hypothesis.
- Size concerns. Mid-to-major concerns get full reasoning. Minor ones get one line or are left out.
- Every prompt the owner must relay is one copy block.
- Before a workstream is proposed to the owner: three plain sentences stating what it is, what it examines or builds, and why it is needed now. If it looks backward at old material, say so in the first sentence.
- Any live or paid provider call needs a separate written owner authorization recorded in docs/decisions. API keys never appear in records or chat.
- If an instruction from another model does not match this workflow or these roles, stop and tell the owner.
- A shared Google Drive folder is approved for passing files among the models. It is transport only: original bytes, hash-verified on both ends, no secrets, no silent changes to another party's file.
- Before acting, a new chat confirms the current main commit from GitHub and states it. It does not rely on the "Last updated" line of this file alone.
- Every pull request targeting main gets an advisory Linux test check (docs/ci.md). A green check is evidence. It does not authorize a merge, a dispatch, provider activity, a deployment or an architecture change, and it does not replace independent review or the owner's merge decision.

## 6. Current state (as of 2026-11-20)

Completed:
- Phases 1 to 5 merged.
- Phase 6A (ADR-010) complete, PR #11.
- Phase 6B, 6C and 6D-prep accepted, mock transport only.
- Sprint 5 (output schema and provider error diagnostics) accepted, PR #27.
- FI-001 offline root-cause analysis merged, PR #29. Historical cause of the HTTP 400 is UNCONFIRMED.
- Cyrus Engineering Doctrine v1 adopted, PR #30.
- Sprint 6 (offline dispatch identity preflight) accepted, PR #31, closeout PR #32. Tests: Linux 185 run, 0 skips. Windows 185 run, 4 expected skips. Owner Windows preflight 12 of 12 matched.
- Handoff file and model role cards added, PR #33.
- Sprint 7 (offline capture receipt, ADR-011) accepted, PR #34. Tests: Linux 202 run, 0 skips. Windows 202 run, 4 expected skips. Focused capture tests 17 of 17.
- Sprint 7 closeout, PR #35.
- Sprint 8 (advisory CI on pull requests) accepted, PR #36. Independent reproduction: 202 run, 0 skips. Hosted runs 1 and 2 green. Sprint 8 is closed when its closeout PR is reviewed and merged by the owner.
- Sprint 8 closeout, PR #37.
- Sprint 9 (capture and CI runner corrections) accepted, PR #38. Tests: Linux 206 run, 0 skips. Windows 206 run, 4 expected skips. Focused capture tests 21 of 21. Seven mutation checks detected. Sprint 9 is closed when its closeout PR is reviewed and merged by the owner.
- Sprint 9 closeout, PR #39.
- Sprint 10 (Snapshot-to-capture linking, ADR-012) accepted, PR #40. Tests: Linux 231 run, 0 skips. Windows 231 run, 4 expected skips. Focused link tests 25 of 25. Fifteen mutation checks detected. Sprint 10 is closed when its closeout PR is reviewed and merged by the owner.

Advisory CI:
- One advisory Linux check runs on pull requests targeting main: pinned SDK verified, full suite in a disposable copy, red on any failure, error, skip, unexpected success or zero tests. It uses a read-only token and no secrets. It is not a merge gate; no branch protection is configured. It is not a network sandbox and does not run Windows.
- The connection guard accepts only the exact name localhost or a numeric loopback address, and covers the main test process only.

Capture capability (ADR-011, ADR-012):
- Ripley One now has a deterministic offline local-file capture capability. It can: accept a local file from an approved directory; preserve the exact bytes in a content-addressed store outside the repository; write a capture receipt to the ledger; record Ripley's UTC captured_at separately from declared source times; verify stored content as MATCHED, MISMATCHED or UNAVAILABLE.
- It does not: acquire anything over a network; use or contain agents; select sources on its own; parse content; involve any provider; do predictive modeling.
- Capture is sequential-only; concurrent capture is unsupported, untested and unclaimed. Byte-string source paths are refused before any read or store write. An object published at its final path is not removed by a later failure of that capture. Reuse of an existing object repeats the applicable durability sync before a receipt is written. There is no reservation or lock.
- A task run can declare the capture receipts it relies on (ADR-012). References are stored on the Snapshot outside inputs, as capture_id plus receipt_hash, in canonical order. Ripley verifies every reference before every worker attempt and records each verification separately; a failed verification blocks the task with no fallback. The task key is unchanged; a submission with the same active task key and different references is refused as capture_reference_conflict. Recovery keeps the original references, verifies before spending its authorization, and verifies again at each boundary. The Evidence record pins the receipts and the verification record. This proves the declared evidence was identified and verified at the execution boundary. It does not prove extraction correctness, source authenticity, truth of source declarations, or availability of the stored bytes at approval time. Provider workers refuse capture references.

Offline Infrastructure Phase exit gate (approved by the owner, 2026-11-20):
1. Core execution and evidence flow proven within bounded local and mock scope. SATISFIED.
2. Durable state and honest recovery proven. SATISFIED.
3. Worker isolation and bounded execution proven. SATISFIED.
4. Offline local-file capture and provenance foundation proven. SATISFIED.
5. A Task/Snapshot identifies the exact capture evidence it consumed and Ripley verifies that evidence. SATISFIED by Sprint 10 (ADR-012).
6. Advisory full-suite CI proven. SATISFIED.
7. A final repository phase-exit record states the evidence, limitations and deferred work, and the owner accepts the phase by merging it. NOT YET DONE.
Sprint 10 completes the ENGINEERING exit gate (conditions 1 to 6). This does not itself close the phase. After this closeout is reviewed and merged, the next and final action is the docs-only Ripley One Offline Infrastructure Phase Exit Record. The owner's merge of that record is the formal phase acceptance. No Sprint 11 engineering work is authorized.

Reviewed code baseline:
The reviewed code baseline is main aca9d4d2264a71fe6b41d286c745a43a1e06907a (merge of PR #40), whose tree is identical to commit fa9c136, which Claude reviewed. It supersedes 697680b. The reviewed CI tooling is unchanged since PR #38: runner SHA-256 95b5dfd0...5643, workflow SHA-256 68b451b8...c239. The provider path is proven against mock transport only; live validation has not been performed. None of these statements authorizes a dispatch.

Blocked:
- Live dispatch #3 is paused and NOT authorized. A provider support case is open.
- Two authorized live dispatches have been used. Neither produced model output (#1 auth_rejected, since remediated; #2 HTTP 400).
- Phase 6E has not started.

Frozen by owner direction:
- Provider request, prompt, model, schema and dispatch logic.
- No further sprint re-investigating the HTTP 400 without materially new evidence.

Owner direction of 2026-11-20:
- Priority is infrastructure: how the engine works, what it does, and how it is prepared to gather data for a future model.
- Recovered NFL material (old workbooks, scripts, coefficients, reports) is reference only. No auditing, validating, reproducing or comparing it.
- No data comparison, accuracy check or backtest until a new model exists.

Known small items:
- Test P6-11 briefly rewrites the real prompt file. To be changed to use a temporary copy in a sprint allowed to touch existing tests.
- Run scripts/pilot_preflight.py with python -I, and do not run it while the test suite is running.
- docs/project-status.md still carries Phase 1-era rows such as "Phase 2 implementation: NOT STARTED". Deferred documentation cleanup, not authorized here.
- Capture is sequential-only, and an abruptly terminated capture can leave a temporary file. See docs/capture.md, "Known limitations".
- The CI connection guard covers the main test process only. See docs/ci.md, "Known limitations".
- Exact payloads sent through long chat messages have been reformatted or truncated in transit. Prefer a hash-verified file through the approved shared Drive folder. Process recommendation only.
- Capture references are not accepted on provider workers (ADR-012), and approval does not re-verify stored capture bytes. See docs/capture.md, "Known limitations".
- Reference test runs need proxy variables unset; P6-14 depends on it. See docs/ci.md, "Local commands".

Owner decision needed:
- Acceptance of the Offline Infrastructure Phase, by merging the phase-exit record. No Sprint 11 engineering work is authorized, and no next-phase direction is chosen by this record. Candidates carried forward for later planning: a read-only ledger status report; timing of the source-reader ADR.
- Whether capture should ever acquire over a network. Blocked pending an owner decision on sources and a rights classification.
- Whether and when the advisory check becomes a required check. Not decided.

Next round-table topics:
- The Offline Infrastructure Phase Exit Record.
- Provider support reply on FI-001, when it arrives.
- Timing of the source-reader ADR.

## 7. History

| Date | Milestone | Evidence |
|---|---|---|
| 2026-11-04 | Phase 0 inventory and salvage complete (per owner). Phase 1 architecture approved. | docs/architecture/phase-1.md, ADR-001 to ADR-006 |
| 2026-11-06 | Phase 2 executable skeleton | PR #2 |
| 2026-11-06 | Phase 3 durable ledger and restart honesty, ADR-007 | PR #3 |
| 2026-11-06 | Phase 4 explicit recovery and timeout detection, ADR-008 | PR #5 |
| 2026-11-17 | Phase 5 local worker isolation and enforceable deadlines, ADR-009 | PR #9 |
| 2026-11-17 | Phase 6A ADR-010, external provider Worker and paid-dispatch governance | PR #11 |
| 2026-11-17 | Phase 6B and 6C, mocked provider worker and safety tests | PR #12, PR #15 |
| 2026-11-18 | Phase 6D-prep, frozen Bears packet and owner pilot runner | PR #17 |
| 2026-11-18 | Live dispatch #1 auth_rejected. Credential check HTTP 200. | docs/pilot |
| 2026-11-18 | Live dispatch #2 HTTP 400 (sent 11:48 PM Central; 2026-11-19 UTC) | docs/pilot/6d-dispatch-02.md |
| 2026-11-19 | Sprint 5 schema and diagnostics fix | PR #27 |
| 2026-11-19 | FI-001 record | PR #29 |
| 2026-11-19 | Doctrine v1 adopted | PR #30 |
| 2026-11-19 | Sprint 6 offline preflight and closeout | PR #31, PR #32 |
| 2026-11-20 | Handoff file and model role cards | PR #33 |
| 2026-11-20 | Sprint 7 offline capture receipt, ADR-011 | PR #34, docs/capture.md |
| 2026-11-20 | Sprint 8 advisory CI on pull requests | PR #36, docs/ci.md |
| 2026-11-20 | Sprint 9 capture and CI runner corrections | PR #38, docs/capture.md, docs/ci.md |
| 2026-11-20 | Sprint 10 Snapshot-to-capture linking, ADR-012; engineering exit gate complete | PR #40, docs/capture.md |

## 8. Future add-ons (ideas only)

Nothing in this section is designed, scheduled or authorized. Each item needs its own entry criteria, ADR, review and owner authorization.

From the Phase 1 extension points:
- RAG and knowledge layer
- Security and policy agents
- Debugging and reliability agents
- Controlled learning
- Postmortem automation
- Model governance
- Live and material-event monitoring

From the owner's product vision (2026-11-19):
- An internal "clinical doctor" for operational self-awareness, where "unknown" is an acceptable diagnosis
- Self-healing: detect, diagnose, select an approved response, remediate, verify recovery, record, learn
- A reusable Cyrus Failure Intelligence Catalog, where a similar past failure is a reason to investigate and not proof
- Technology horizon monitoring
- A sandboxed Evolution Lab kept separate from production
- A protected, signed core with a customer extension layer
- Tiered autonomy

Deferred by the Doctrine (section 12):
- Health agents, autonomous remediation, horizon-monitoring agents, a shared machine-readable Failure Intelligence platform, customer plugin execution, production signing infrastructure, staged deployment automation, multi-tenant services, multi-provider orchestration

Deferred from earlier phases:
- Automatic recovery (P4-RECOVERY-001)
- A second provider Worker
- A real reviewer workflow

Infrastructure candidates raised for Sprint 7 and later:
- Network acquisition for capture (needs its own decision and a rights classification)
- A read-only status report from the ledger
- Separating prompt and adapter from the provider worker
- Dispatch-time request evidence (needs an ADR-010 revision and the freeze lifted)
- Cost-on-read
- Prediction, Outcome and Grade records

## 9. Where things live

| Need | Location |
|---|---|
| The standard every engine inherits | docs/architecture/cyrus-engineering-doctrine.md |
| Architecture and contracts | docs/architecture/phase-1.md, docs/architecture/contracts.md |
| Decisions (ADR-001 to ADR-012) | docs/decisions/ |
| Owner authorizations for live actions | docs/decisions/phase-6d-*.md |
| Phase write-ups | docs/phase-2-skeleton.md through docs/phase-6-provider-worker.md |
| Live pilot and preflight records | docs/pilot/ |
| Failure records | docs/failure-intelligence/ |
| Milestone table and maturity labels | docs/project-status.md |
| Model role cards and catch-up prompts | docs/onboarding/ |
| Capture receipts and the artifact store | docs/capture.md, docs/decisions/sprint-7-adrs.md, docs/decisions/sprint-10-adrs.md |
| Advisory CI check | docs/ci.md, .github/workflows/tests.yml, .github/scripts/ci_tests.py |

## 10. Keeping this file current

- ChatGPT updates sections 6 and 7 in every sprint closeout PR.
- Claude checks the update during review.
- Sections 1 to 5 and 8 change only by owner decision.
- Update the "Last updated" line with the date and the main commit.
