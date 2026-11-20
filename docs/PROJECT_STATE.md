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
- Build what we need. Earn complexity through evidence.
- This repository is also the owner's engineering portfolio. The real process is documented as it happens, including failures and limitations.

Priority order (Doctrine v1, section 1): Security and Core Integrity; Health and Customer Protection; Reliability and Service Continuity; Failure Intelligence and Safe Recovery; Evolution and Modernization; Performance and Efficiency; Customer Extensibility.

Evolution cannot violate security. Performance cannot violate correctness. Availability cannot justify corrupted evidence. Autonomy cannot overrule governance.

The governing standard is docs/architecture/cyrus-engineering-doctrine.md (Doctrine v1, accepted 2026-11-19). Adopting it is not evidence that Ripley implements it.

## 2. What we are building

Cyrus Ripley One (Ripley, R1) is a domain-agnostic engine. The Core handles tasks, workers, results, validation, review, evidence and approval. It contains no domain logic.

Core flow: Task -> Ripley -> Worker -> Result -> Validation -> Review/Correction -> Evidence -> Approval

- Today Ripley runs one task through one worker and records hash-verified evidence in an append-only ledger. It has no agents, no queues, no CI and one provider.
- The NFL is the first real domain. It was chosen because it is a hard, multi-pipeline problem. All NFL logic lives outside the Core.
- A small synthetic non-NFL domain exists to test the domain-agnostic claim.
- The first NFL task is a pregame player-availability brief, not game prediction.
- NFL Predictor V2+ is a future workload on Ripley. It is not the current build.
- The separate market-informed weekly NFL beta is not part of Ripley and is never cited as Ripley evidence.
- Future domains under consideration: inventory and demand, logistics, sales forecasting, business operations.

## 3. Agent and orchestration direction

This section is direction, not an accepted design.

- Ripley is intended to become an agentic orchestration platform. Domain workloads exercise the platform without redefining it.
- Orchestration and state are native to Ripley. No LangGraph, CrewAI, BeeAI, Microsoft Agent Framework or AutoGen in the control plane. Reopen only on evidence, and then only bounded inside a Worker. (Owner decision, 2026-11-17.)
- Agents are defined by responsibility before count. There is no fixed number of agents.
- Hard spending limits must not depend solely on an LLM agent.
- No agent design has been accepted. Building any agent capability requires an ADR and an owner decision.

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

## 6. Current state (as of 2026-11-20)

Completed:
- Phases 1 to 5 merged.
- Phase 6A (ADR-010) complete, PR #11.
- Phase 6B, 6C and 6D-prep accepted, mock transport only.
- Sprint 5 (output schema and provider error diagnostics) accepted, PR #27.
- FI-001 offline root-cause analysis merged, PR #29. Historical cause of the HTTP 400 is UNCONFIRMED.
- Cyrus Engineering Doctrine v1 adopted, PR #30.
- Sprint 6 (offline dispatch identity preflight) accepted, PR #31, closeout PR #32. Tests: Linux 185 run, 0 skips. Windows 185 run, 4 expected skips. Owner Windows preflight 12 of 12 matched.

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

Owner decision needed:
- Sprint 7 goal. In planning.
- Direction on a first agent capability (requires an ADR).

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
- A first data-capture task that records source, capture time and content hash
- CI on pull requests
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
| Decisions (ADR-001 to ADR-010) | docs/decisions/ |
| Owner authorizations for live actions | docs/decisions/phase-6d-*.md |
| Phase write-ups | docs/phase-2-skeleton.md through docs/phase-6-provider-worker.md |
| Live pilot and preflight records | docs/pilot/ |
| Failure records | docs/failure-intelligence/ |
| Milestone table and maturity labels | docs/project-status.md |
| Model role cards and catch-up prompts | docs/onboarding/ |

## 10. Keeping this file current

- ChatGPT updates sections 6 and 7 in every sprint closeout PR.
- Claude checks the update during review.
- Sections 1 to 5 and 8 change only by owner decision.
- Update the "Last updated" line with the date and the main commit.
