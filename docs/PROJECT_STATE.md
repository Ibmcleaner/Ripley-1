# Ripley One — Project State and Handoff

Last updated: 2026-11-20, against main c854144 (PR #32).
Owner: Robert Legorreta, Cyrus Forge Systems, LLC.

Read this file first in any new chat. It is the entry point, not the full record. Where this file and a detailed record disagree, the detailed record (ADR, pilot record, FI record) is correct and this file needs fixing.

## 1. Vision

Cyrus Forge Systems builds durable engines meant to stay useful for many years, not disposable AI apps that customers must rebuild. Revenue comes from continuing value, never from preventable failures.

- One engine, many uses. An engine must transfer to different customer needs.
- Human-in-the-loop is part of every Cyrus engine.
- The engine must not grade its own homework.
- Design for extension. Build the minimum necessary foundation. Prove the foundation. Then add capability in controlled layers.
- This repository is also the owner's engineering portfolio. The real process is documented as it happens, including failures and limitations.

The governing standard is docs/architecture/cyrus-engineering-doctrine.md (Doctrine v1, accepted 2026-11-19).

## 2. What we are building

Cyrus Ripley One (Ripley, R1) is a domain-agnostic engine. The Core handles tasks, workers, results, validation, review, evidence and approval. It contains no domain logic.

Core flow: Task -> Ripley -> Worker -> Result -> Validation -> Review/Correction -> Evidence -> Approval

- Orchestration and state are native to Ripley. No LangGraph, CrewAI, BeeAI, Microsoft Agent Framework or AutoGen in the control plane. Reopen only on evidence, and then only bounded inside a Worker.
- The NFL is the first real domain. It was chosen because it is a hard, multi-pipeline problem. All NFL logic lives outside the Core.
- A small synthetic non-NFL domain exists to test the domain-agnostic claim.
- The first NFL task is a pregame player-availability brief, not game prediction.
- The separate market-informed NFL beta is not part of Ripley and is never cited as Ripley evidence.
- Future domains under consideration: inventory and demand, logistics, sales forecasting, business operations.

## 3. Roles

| Who | Role |
|---|---|
| Robert Legorreta | Product Owner. Sets priorities, makes owner decisions, accepts work, merges, and authorizes any live or paid action. |
| Claude | Architecture lead and principal reviewer. Writes assignments, reviews actual diffs and test output, runs tests on Linux. Does not modify the repository. |
| ChatGPT | Primary implementation agent. Writes code and documentation on a branch and opens PRs. Does not merge. |
| Copilot | Scope control, architecture and quality review, Product Owner support. |

The owner relays every message between models. Models work from actual artifacts (files, diffs, test output), not summaries.

## 4. Workflow

Work runs in short Sprints. No story points, velocity targets or ceremony.

Each Sprint has: a Sprint Goal, a prioritized backlog, acceptance criteria, a Definition of Done, and assigned implementation and review responsibilities.

Normal sequence:
1. Owner sets the Sprint Goal.
2. Claude writes the assignment as one copy-and-paste block. Copilot checks scope.
3. Owner relays it to ChatGPT.
4. ChatGPT implements on a branch, opens a PR and reports back.
5. Claude reviews the diff and runs the tests on Linux.
6. Owner runs the tests on Windows.
7. Owner merges.
8. Closeout PR records the evidence and updates section 5 and section 6 of this file.

Status updates use: Completed / In progress / Blocked / Owner decision needed / Next.

Each Sprint ends with a Review on working evidence and a short Retrospective: what worked, what caused rework, what should change, what should remain, one improvement to carry forward.

Definition of Done: acceptance criteria met, tests run independently on Linux and Windows with results recorded, PR merged by the owner, and this file updated.

A whiteboard session and an ADR are used only for real architecture, safety, governance or owner decisions.

Standing rules:
- The repository is the system of record. Chat history is not.
- Never claim something is implemented or tested without evidence. Use the maturity labels in docs/project-status.md.
- Never silently redesign established architecture. Raise the concern with reasoning and an alternative.
- Think independently. No agreement for the sake of consensus. Separate evidence from hypothesis.
- Size concerns. Mid-to-major concerns get full reasoning. Minor ones get one line or are left out.
- Any live or paid provider call needs a separate written owner authorization recorded in docs/decisions. API keys never appear in records or chat.
- If an instruction from another model does not match this workflow, stop and tell the owner.

## 5. Current state (as of 2026-11-20)

Completed:
- Phases 1 to 5 merged.
- Phase 6A, 6B, 6C and 6D-prep accepted, mock transport only.
- Sprint 5 (output schema and provider error diagnostics) accepted, PR #27.
- FI-001 offline root-cause analysis merged, PR #29. Historical cause of the HTTP 400 is UNCONFIRMED.
- Cyrus Engineering Doctrine v1 adopted, PR #30.
- Sprint 6 (offline dispatch identity preflight) accepted, PR #31, closeout PR #32. Tests: Linux 185 run, 0 skips. Windows 185 run, 4 expected skips. Preflight 12 of 12 matched.

Blocked:
- Live dispatch #3 is paused and NOT authorized. A provider support case is open.
- Two authorized live dispatches have been used. Neither produced model output (#1 auth_rejected, since remediated; #2 HTTP 400).

Frozen by owner direction:
- Provider request, prompt, model, schema and dispatch logic.
- No further sprint re-investigating the HTTP 400 without materially new evidence.

Known small item:
- Test P6-11 briefly rewrites the real prompt file. To be changed to use a temporary copy in a later sprint.

Owner decision needed:
- Sprint 7 goal. Not yet set.

## 6. History

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
| 2026-11-19 | Live dispatch #2 HTTP 400 | docs/pilot/6d-dispatch-02.md |
| 2026-11-19 | Sprint 5 schema and diagnostics fix | PR #27 |
| 2026-11-19 | FI-001 record | PR #29 |
| 2026-11-19 | Doctrine v1 adopted | PR #30 |
| 2026-11-19 | Sprint 6 offline preflight | PR #31, PR #32 |

## 7. Future add-ons (ideas only)

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
- A reusable Cyrus Failure Intelligence Catalog, where a similar past failure is a reason to investigate and not proof
- A sandboxed Evolution Lab kept separate from production
- A protected, signed core with a customer extension layer
- Tiered autonomy

Deferred by the Doctrine (section 12):
- Health agents, autonomous remediation, horizon-monitoring agents, a shared machine-readable Failure Intelligence platform, customer plugin execution, production signing infrastructure, staged deployment automation, multi-tenant services, multi-provider orchestration

Deferred from earlier phases:
- Automatic recovery (P4-RECOVERY-001)
- A second provider Worker
- A real reviewer workflow

## 8. Where things live

| Need | Location |
|---|---|
| The standard every engine inherits | docs/architecture/cyrus-engineering-doctrine.md |
| Architecture and contracts | docs/architecture/phase-1.md, docs/architecture/contracts.md |
| Decisions (ADR-001 to ADR-010) | docs/decisions/ |
| Owner authorizations for live actions | docs/decisions/phase-6d-*.md |
| Phase write-ups | docs/phase-2-skeleton.md through docs/phase-6-provider-worker.md |
| Live pilot and preflight records | docs/pilot/ |
| Failure records | docs/failure-intelligence/ |
| Milestone table and maturity labels | docs/project-status.md |
| Model role cards and catch-up prompts | docs/onboarding/ |

## 9. Keeping this file current

- ChatGPT updates sections 5 and 6 in every sprint closeout PR.
- Claude checks the update during review.
- Sections 1 to 4 and 7 change only by owner decision.
- Update the "Last updated" line with the date and the main commit.
