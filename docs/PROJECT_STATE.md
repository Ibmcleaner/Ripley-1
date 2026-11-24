# Ripley One — Project State and Handoff

Last updated: 2026-11-24, against main 8a3c331 (PR #53).
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

Owner direction, 2026-11-23 (ownership and commercial model): Ripley One and every Cyrus engine are proprietary Cyrus Forge Systems intellectual property. Current public visibility of this repository is temporary development, review and portfolio visibility, not the intended long-term commercial distribution model. The intended commercial model is that Cyrus Forge Systems retains ownership of its engines and may license engine use or capability to customers while Cyrus maintains and evolves the engine under the applicable commercial agreement. Licensing an engine does not inherently transfer ownership of Cyrus engine architecture, infrastructure, governance, construction methods or other proprietary Cyrus intellectual property. Commercial marketplace skills, if evaluated separately, are a different bounded product category and must not expose protected Cyrus engine internals. This direction is not authorization to change repository visibility, change licensing, commercialize Ripley One, publish a marketplace skill, contact a marketplace or begin a commercial workstream. Each of those requires a separate owner decision.

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

Owner direction, 2026-11-21: Track A is Ripley One as the native agentic orchestration platform. Track B is the NFL Predictor as a later workload running on Ripley One. Current work is Track A only. Agents are defined by responsibility before count. The first Track A phase is the Governed Source Interpretation Phase (section 6). Since then the Governed Reader Path Phase built one deterministic reader Worker (ADR-016), which uses no model. No agent, model-backed reader or model-produced proposal has been built or authorized.

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
- Timebox and accountability standard (owner-approved 2026-11-21). No phase, sprint or material workstream is released for implementation without: a target completion date; a reauthorization deadline; named milestones, each with an accountable owner; acceptance criteria; explicit non-goals; known dependencies; a midpoint checkpoint; a defined response to schedule variance; and quality gates that cannot be weakened to meet the date. A timebox is a maximum boundary, not a work quota. Finishing early is success. At the reauthorization deadline unfinished work stops and returns to the owner, who decides to continue, narrow, split, defer or cancel.
- At most two material architecture correction rounds. A material disagreement that remains after the second goes to the owner through Copilot.
- A newly discovered item enters an active sprint only if it is blocking now or a defect in current work. Anything else is deferred. Schedule pressure never authorizes weakening a test, bypassing review or a hard stop, relaxing evidence, widening agent authority or merging unverified work.
- One complete, self-contained, hash-verified artifact per major handoff. The chair confirms an artifact is complete before asking the owner to relay it. The owner is not asked to reconstruct or splice messages from the models.
- Independent review precedes owner merge (owner rule, 2026-11-23). A pull request requiring independent review must not be owner-merged until the independent-review verdict is present in the active owner handoff. If an owner merge occurs before that verdict, the variance must be explicitly recorded and independently reconciled before project advancement.
- Evidence keeps its source. Results are attributed to whoever established them: independently reproduced by the reviewer, reported by the owner, reported by the implementer, or shown on a hosted run page. Tests the reviewer runs are the independent evidence. Hosted log lines the reviewer could not see are implementer-reported and are never relabeled as independently observed.

## 6. Current state (as of 2026-11-24)

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
- Sprint 10 closeout, PR #41.
- Offline Infrastructure Phase Exit Record: docs/offline-infrastructure-phase-exit.md. The phase is accepted by the owner's merge of the pull request that adds that record. The record exists on main only if the owner merged it.
- Offline Infrastructure Phase accepted and closed by the owner's merge of PR #42 (main 4e278cb).
- Governed Source Interpretation Phase, Sprint 1 (proposal contract and grounding validator, ADR-013) accepted, PR #43. Tests: Linux 285 run, 0 skips. Windows 285 run, 4 expected skips. Focused grounding tests 54 of 54. Twenty-nine mutation checks detected. Sprint 1 is closed when its closeout PR is reviewed and merged by the owner.
- Governed Source Interpretation Phase, Sprint 1 closeout, PR #44.
- Governed Source Interpretation Phase, Sprint 2 (semantic review record and bounded reasoning envelope, ADR-014 and ADR-015) accepted, PR #45. Tests: Linux 351 run, 0 skips. Windows 351 run, 4 expected skips. Semantic review 33 of 33; reasoning envelope 33 of 33. Fifty-two mutation checks detected.
- Governed Source Interpretation Phase Exit Record: docs/governed-source-interpretation-phase-exit.md. Sprint 2 and the phase are closed by the owner's merge of the pull request that adds that record. The record exists on main only if the owner merged it.
- Governed Source Interpretation Phase accepted and closed by the owner's merge of PR #46 (main 1d8e44e).
- Governed Reader Path Phase, Sprint 1 (reader contract and deterministic isolated reader, ADR-016) accepted, PR #47. Tests: Linux 396 run, 0 skips. Windows 396 run, 4 expected skips. Focused reader tests 45 of 45. Forty-nine mutation checks detected. Sprint 1 is closed when its closeout PR is reviewed and merged by the owner.
- Governed Reader Path Phase, Sprint 1 closeout, PR #48 (main 0a520ab).
- Governed Reader Path Phase, Sprint 2 (reader semantic release and explicit owner approval, ADR-017) accepted, PR #49. Tests: Linux 428 run, 0 skips. Windows 428 run, 4 expected skips. Focused release tests 32 of 32. Fifty mutation checks detected on both ledgers.
- Governed Reader Path Phase Exit Record: docs/governed-reader-path-phase-exit.md. Sprint 2 and the phase are closed by the owner's merge of the pull request that adds that record. The record exists on main only if the owner merged it.
- Governed Reader Path Phase accepted and closed by the owner's merge of PR #50 (main b880fa4). PR #50 was merged before the planned independent review; Claude's post-merge reconciliation found no blocking defect.
- Governance correction of the phase exit record, PR #51 (main 5d7d592): records the PR #50 review order and the review-before-merge rule. Reviewed before merge. See docs/governed-reader-path-phase-exit.md, section 14.
- Project state synchronized after the reader phase closeout, PR #52 (main a7e1598). Documentation only.
- Phase Transition Hold released by the owner on 2026-11-24. The owner approved a two-layer data architecture (Layer 1 source dataset; Layer 2 interpreted dataset), directed that Layer 1 be proven first, and selected the Source Dataset Provenance Phase.
- Source Dataset Provenance Phase, Sprint 1 (immutable source membership, ADR-018) accepted, PR #53 (main 8a3c331). Tests: Linux 450 run, 0 skips. Windows 450 run, 4 expected skips (owner-reported). Focused source dataset tests 22 of 22. Thirty mutation checks detected on both ledgers under the owner-approved revised SM19; the original SM19 survived because of a mutation-specification defect, and the production code was not changed.
- Source Dataset Provenance Phase Exit Record: docs/source-dataset-provenance-phase-exit.md. Sprint 1 and the phase are closed by the owner's merge of the pull request that adds that record. The record exists on main only if the owner merged it.

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
7. A final repository phase-exit record states the evidence, limitations and deferred work, and the owner accepts the phase by merging it. SATISFIED BY THE OWNER'S MERGE of docs/offline-infrastructure-phase-exit.md.
The Offline Infrastructure Phase was accepted and closed by the owner's merge of PR #42 on 2026-11-20. Acceptance is not production readiness, provider readiness or modeling readiness. The record is docs/offline-infrastructure-phase-exit.md.

Governed Source Interpretation Phase (Track A) exit gate (approved by the owner):
1. Proposal contract established. SATISFIED (ADR-013).
2. Exact-byte grounding proven. SATISFIED (Sprint 1).
3. Hostile and malformed inputs proven safe within the approved deterministic scope. SATISFIED (Sprint 1).
4. Independent semantic-review boundary implemented and proven. SATISFIED (Sprint 2, ADR-014).
5. Cost and execution envelope proven offline for the first reasoning-capable profile. SATISFIED (Sprint 2, ADR-015).
6. Phase closeout accepted by owner merge. SATISFIED BY THE OWNER'S MERGE of docs/governed-source-interpretation-phase-exit.md.
Sprint 2 and the Governed Source Interpretation Phase are formally closed by the owner's merge of the phase-exit record. Acceptance is not production readiness, provider readiness or modeling readiness. The phase ran offline on UTF-8 plain text with a human semantic reviewer and no model. Sprint numbering had restarted at Sprint 1 for the phase; it ended after two sprints. No Sprint 3 exists. The phase was accepted and closed by the owner's merge of PR #46 on 2026-11-23. The next phase, the Governed Reader Path Phase, was chosen by the owner on 2026-11-23 and is described below.

Grounding capability (ADR-013):
- Ripley One can take a hand-written proposal about captured text and decide, observation by observation, whether each cited quote exists at the cited bytes. A proposal is untrusted data. It binds to one Snapshot and may cite only the capture references already on that Snapshot; it cannot add evidence.
- Capture evidence is verified all-or-nothing. The stored object is read once, checked against the receipt's size and SHA-256, and citations are evaluated against those same bytes. Offsets are zero-based byte offsets, start inclusive and end exclusive. A match is exact UTF-8 byte equality: case, whitespace, line endings, Unicode form and byte-order marks are not normalized. A citation that splits a multi-byte character fails.
- A verdict is recorded for every observation. Declared uncertainty stays declared. A field with more than one observation is listed, not resolved. The content of a rejected proposal is not stored. The review package is derived from the ledger, is deterministic and writes nothing.
- Mechanically grounded is not semantically reviewed or accepted. Grounding does not establish that an interpretation is correct, that a source is authentic or truthful, or that anything is approved.
- It does not: include a model-produced proposal; record a semantic-review decision; check a value against its quote; run inside the existing Core task path (Core calls it only on the reader path, ADR-016); use a provider, network, tool or agent; handle file types other than UTF-8 plain text; authenticate a reviewer's identity.

Semantic review capability (ADR-014):
- A human can record a semantic judgment about one grounding validation, bound to it by id and hash. Each eligible observation receives exactly one decision: acceptable, rejected or needs_clarification. The decision carries the observation's declared status and grounding verdict.
- The producer identity is read from the proposal. The reviewer kind is human. A reviewer label equal to the producer label, without regard to case, is refused. One fixed, hash-pinned set of criteria applies and cannot be replaced by the producer or the reviewer.
- A validation is reviewed once; a review is never edited or superseded. A refused review stores none of the supplied decisions.
- A review changes no earlier record and creates no authority. acceptable is not approval.
- It does not: authenticate anyone; detect one person using two labels; allow revision; provide a reviewer interface; run inside the Core Task and Worker flow.

Reasoning envelope (ADR-015):
- A two-step ledger gate for one reasoning attempt. By itself it executes nothing. Since ADR-016, Core opens and closes it around each reader attempt. Nothing else uses it.
- Fixed limits: 1 attempt per operation; 0 automatic retries; input at most 262,144 bytes; output at most 65,536 bytes; deadline 120 seconds; budget at most 500,000 micro-dollars. Actual paid authority is 0. No caller can pass a limit; each attempt pins the envelope hash and a copy of the limits.
- A second attempt is refused. A failed, uncertain or never-closed attempt stays consumed, and consumption survives restart. Oversized output, a cost above the limit and a late close are recorded as violations.
- It does not: call a model, provider, network, tool or Worker; terminate or cancel anything; authorize spending; measure the sizes or costs a host declares; have any field for children, fan-out, delegation, tools, provider or model. ADR-010 dispatch governance is separate and unchanged.

Governed Reader Path Phase (Track A) exit gate (approved by the owner, 2026-11-23):
1. Reader contract accepted. SATISFIED (ADR-016).
2. End-to-end reader path proven. SATISFIED (Sprint 1).
3. Envelope governs the attempt. SATISFIED (Sprint 1).
4. Hostile or failing reader contained. SATISFIED within the approved deterministic scope (Sprint 1).
5. Human gates preserved: no path reaches final approval without grounding, then independent semantic review, then human approval. SATISFIED (Sprint 2, ADR-017).
6. Existing behavior preserved. SATISFIED, with one owner-authorized two-line change to test RP-15.
7. Phase closeout accepted by owner merge. SATISFIED BY THE OWNER'S MERGE of docs/governed-reader-path-phase-exit.md.
Sprint 2 and the Governed Reader Path Phase are formally closed by the owner's merge of the phase-exit record. Acceptance is not production readiness, provider readiness or modeling readiness. The phase ran offline on UTF-8 plain text with a deterministic reader, a human semantic reviewer and a human owner, and no model. It ended after two sprints, both merged on Monday, November 23, 2026, ahead of the phase target of Friday, December 4, 2026. No Sprint 3 exists. No next phase is chosen and no next-phase work is authorized. The phase was accepted and closed by the owner's merge of PR #50 on 2026-11-23. A Phase Transition Round Table follows only when the owner releases the Phase Transition Hold described below.

Phase Transition Hold: RELEASED (by the owner, 2026-11-24).
- The owner released the hold for a Phase Transition Round Table and then selected the Source Dataset Provenance Phase. That phase has one sprint, and its closure is recorded below.
- A closed phase does not start the next one. No Sprint 2 is authorized. No next phase is selected or authorized. Layer 2 is deferred and is not automatically next.
- Only Robert's own statement selects a phase, or sets or releases a hold. An instruction from the chair or from any AI does not.

Source Dataset Provenance Phase (Track A) exit gate (set in the reconciled planning artifact, 2026-11-24):
1. Necessity: a new record is justified by a capability existing mechanisms do not provide. SATISFIED (ADR-018).
2. Identity: exact immutable membership has a deterministic canonical identity. SATISFIED (Sprint 1).
3. Integrity: every member verified through existing mechanisms; bad membership and malformed stored records fail closed. SATISFIED (Sprint 1).
4. Persistence: a SQLite close and reopen reconstructs the same membership and identity. SATISFIED (Sprint 1).
5. Authority: no Task, Snapshot, Worker, approval, model, provider or network operation is created. SATISFIED (Sprint 1).
6. Regression: existing behavior stays green and frozen. SATISFIED; no existing code or test changed.
7. Closeout accepted by owner merge after independent review. Satisfied only by the owner's merge of docs/source-dataset-provenance-phase-exit.md after independent review; that file exists on main only if the owner merged it.
Sprint 1 and the Source Dataset Provenance Phase are formally closed by the owner's merge of the phase-exit record. Acceptance is not production readiness, provider readiness or modeling readiness. The phase ran offline on synthetic UTF-8 text with no model. Layer 1 is established. Layer 2 is deferred. Two owner-approved variances (the SM19 mutation specification, and the timing of Linux evidence) are recorded in the exit record, section 9.

Reader path capability (ADR-016):
- Core has one reader entry point. A first-party deterministic Worker, run in the existing isolated process, is given the verified text of the captures on its Snapshot and returns observations: each requested "Field: value" line, or not found. It makes no judgment and holds no authority.
- Core, not the reader, selects the evidence, sets the producer identity from the trusted Worker descriptor, assembles the proposal and grounds it. A rejected, blocked or wholly ungrounded proposal blocks the task.
- Core reserves one ADR-015 attempt before launch. The attempt's absolute deadline governs preparation as well as execution: only the time remaining is given to the process, and an attempt that has already expired is not launched. One attempt, no retry, no correction loop. recover() refuses a reader task.
- Reader-only exception to ADR-012: for a reader task alone, the capture references are part of the inputs, the packet and the task key. Every other task and every provider packet is unchanged. ADR-012 itself is not amended.
- A grounded reader task is bound by a sixteen-key record that pins six linked records by id and hash, and stops in awaiting_semantic_review, which survives restart. Its only exits are the two defined by ADR-017. A read-only chain check reports any of 20 break reasons.
- It does not: use a model, provider, network, tool, child or agent; continue after an interruption; bound what a process writes before it is measured; contain hostile code; read anything other than UTF-8 plain text. A person may resubmit a blocked reader task as a new task with its own attempt; this must be decided again before any reader that costs money.

Reader release and owner approval (ADR-017):
- A person releases a reader task by naming its binding and its one ADR-014 semantic review, each by id and hash. Core verifies both, the chain and their exact relationship; any failure is a recorded refusal, one of twenty reasons, that leaves the task state unchanged. Release creates no owner verdict.
- Core derives the approval scope: included, uncertain, not-found and excluded observation ids. The caller cannot choose them. An observation that was not grounded is excluded and never approved. Declared uncertainty reaches the final approval record unchanged.
- All decisions acceptable: one release record, one pending approval with the status pending_reader_owner_approval, then the state pending_owner_approval. Any rejected or needs_clarification decision: one release record and the state blocked. A rejected semantic review is not an owner rejection.
- The owner decides through a separate entry point, decide_reader_approval, with the owner label, an explicit approved or rejected, and a reason. Core derives every release fact again before writing a judgment. The existing decide_approval is unchanged and refuses reader pending approvals; the reader entry point refuses existing-style ones.
- A repeated or interrupted release or decision writes no second release record, pending approval or judgment. An opposite decision is refused.
- Approval means the owner accepts the exact reviewed eligible observation set as an acceptable reading of the captured evidence. It authorizes no downstream action.
- It does not: authenticate any label; provide a clarification or revision path; give an approved reading any consumer; launch a reader, reserve an attempt or reread captured bytes.

Source dataset, Layer 1 (ADR-018):
- Ripley One can record an exact membership of capture receipts as one immutable ledger record, source_dataset, independently of any Task. The record has three data keys: contract_version, membership_sha256 and members. Members are 1 to 16 capture references in the ADR-012 shape, in ascending capture_id order.
- membership_sha256 is the dataset identity. Identical membership always gives the same value. The ledger record id is not the dataset identity. Two captures of byte-identical files are different members.
- Creation verifies every member, all-or-nothing, and on a repeat returns the existing record without writing. Verification is read-only and rebuilds its answer from ledger records and stored bytes.
- A verified Source Dataset is an integrity result, not a trust, quality, approval, interpretation, availability-time, consent, or fitness-for-use result.
- It does not: have any consumer (no Task accepts a source dataset); carry a name, a time, lineage or retraction; make an "as of T" claim; guarantee uniqueness under concurrent writers; resolve ambiguity automatically (any second record claiming the same membership hash needs manual inspection); allow more than 16 members; use a model, provider, network, tool or agent; touch Layer 2. See docs/source-datasets.md.

Reviewed code baseline:
Main is 8a3c331df61067e0338809f298d2a882ba53993d (merge of PR #53). Its tree is identical to commit 71b2f59, which Claude reviewed. It supersedes faeabd3 (merge of PR #49) as the reviewed code baseline; PR #50, PR #51 and PR #52 changed documentation only. Against a7e1598 it adds ripley/datasets.py and tests/test_source_dataset.py and changes no existing code or test. The reviewed CI tooling is unchanged since PR #38: runner SHA-256 95b5dfd0...5643, workflow SHA-256 68b451b8...c239. The provider path is proven against mock transport only; live validation has not been performed. None of these statements authorizes a dispatch.

Blocked:
- Live dispatch #3 is paused and NOT authorized. Provider support replied on 2026-11-24: it could not retrieve the error text or confirm the cause. Live replay is not authorized.
- Two authorized live dispatches have been used. Neither produced model output (#1 auth_rejected, since remediated; #2 HTTP 400).
- Phase 6E has not started.
- The cause of the HTTP 400 (FI-001) is unconfirmed. The historical schema defect is proven against the provider's documented rules; its repair is verified offline and untested live. The available FI-001 evidence does not establish a context, memory or retrieval cause. FI-001 alone is not a reason to add retrieval, vector storage or caching. FI-001 is separate from the Source Dataset Provenance Phase.

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
- Grounding supports UTF-8 plain text only and does not check a value against its quote. See docs/grounding.md, "Known limitations".
- A hand-forged capture record that lacks expected fields could raise an error in grounding instead of producing a reason code. Not reachable through the current capture_file writer. Not scheduled.
- Semantic review identities are labels, not authenticated identities; a validation is reviewed once with no revision. See docs/semantic-review.md.
- The reasoning envelope is used only by the reader path. Its own deadline is detection only (on the reader path the isolation layer enforces the same instant) and its budget is synthetic accounting. See docs/reasoning-envelope.md and docs/reader-path.md.
- The reader path has a deterministic reader only and no continuation after an interruption. An approved reading has no consumer. See docs/reader-path.md and docs/governed-reader-path-phase-exit.md.
- The line reader reports a matching line longer than 4,096 bytes as not found. As specified. Not scheduled.
- A hand-added, malformed approval record with the reader pending status makes decide_reader_approval raise KeyError or TypeError where the contract says ValueError. Nothing is written; Core never writes such a record. Known bounded item; future hardening; not blocking; not scheduled. No correction is authorized, and the owner's disposition is final for the closed phase. See docs/governed-reader-path-phase-exit.md, section 9.
- A Windows gate must be run with the pinned provider SDK installed; without it 39 provider tests are skipped and the gate is not met. One Sprint 2 Windows run reported 43 skips for that reason and was not acceptance evidence; the accepted run was 428 with 4 expected skips. Confirm the pinned SDK before every Windows gate; any skip count other than the expected one is a gate failure until explained.
- A source dataset has no consumer, at most 16 members, sequential single-writer uniqueness only, and no name, time, lineage or retraction; ambiguity can be induced by a stray record and needs manual inspection. Accepted limits. See docs/source-datasets.md and docs/source-dataset-provenance-phase-exit.md, section 10.
- Before a mutation matrix is released, each mutation must be checked against the code path the same assignment prescribes. One Sprint 1 mutation (SM19) was undetectable as written. See docs/source-dataset-provenance-phase-exit.md, section 9.

Owner decision needed:
- Selection of the next phase. The Source Dataset Provenance Phase is closed and a closed phase does not start the next one. No next phase is chosen and no next-phase work is authorized. Layer 2 is deferred and is not automatically next. Deferred items and their classifications are in docs/source-dataset-provenance-phase-exit.md, section 12, and docs/governed-reader-path-phase-exit.md, section 11; none is authorized.
- Whether a person may resubmit a blocked reader task. Permitted now because the reader is local and free (ADR-016 decision 25). Must be decided again before any reader that costs money.
- Repository visibility, licensing and any commercial workstream. Each requires a separate owner decision. None is made by the owner direction recorded in section 1.
- Whether capture should ever acquire over a network. Blocked pending an owner decision on sources and a rights classification.
- Whether and when the advisory check becomes a required check. Not decided.

Gates before specific future work (none of this work is authorized; each gate applies only if that work is later proposed):
- Any live provider work: FI-001 and any new provider evidence must be reconsidered first. FI-001 is unresolved, the provider path has never produced model output, Dispatch #3 is paused and not authorized, and Phase 6E has not started.
- Any reasoning that costs money: the reasoning envelope (ADR-015) must first be reconciled with dispatch governance (ADR-010).
- Any reader that costs money: the rule that a person may resubmit a blocked reader task must be decided again (ADR-016 decision 25).
- Any model-backed reader, or any reader that is not first-party deterministic code: its own ADR and owner decision; its instruction or prompt identity must be explicitly pinned and governed; and process and output containment must be reconsidered, because output is measured after a process ends and process isolation is not a sandbox.
- Any approval that authorizes an action, or any consumer of approved readings: authenticated identities must be decided first. Labels are not identities.

Next round-table topics:
- Selection of the next phase, when the owner calls for it.
- FI-001 after the provider support reply: whether any bounded diagnostic re-send is ever to be considered. None is authorized.
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
| 2026-11-20 | Sprint 10 closeout; Offline Infrastructure Phase Exit Record (phase accepted by the owner's merge of the record) | PR #41, docs/offline-infrastructure-phase-exit.md |
| 2026-11-20 | Offline Infrastructure Phase accepted and closed by owner merge | PR #42 |
| 2026-11-21 | Governed Source Interpretation Phase named; timebox and accountability standard adopted; Sprint 1 proposal contract and grounding validator, ADR-013 | PR #43, docs/grounding.md |
| 2026-11-21 | Governed Source Interpretation Phase, Sprint 1 closeout | PR #44 |
| 2026-11-23 | Sprint 2 semantic review record and bounded reasoning envelope, ADR-014 and ADR-015 | PR #45, docs/semantic-review.md, docs/reasoning-envelope.md |
| 2026-11-23 | Governed Source Interpretation Phase Exit Record (Sprint 2 and the phase closed by the owner's merge of the record); owner direction on ownership and commercial model recorded | docs/governed-source-interpretation-phase-exit.md |
| 2026-11-23 | Governed Source Interpretation Phase accepted and closed by owner merge | PR #46 |
| 2026-11-23 | Governed Reader Path Phase chosen by the owner; Sprint 1 reader contract and deterministic isolated reader, ADR-016 | PR #47, docs/reader-path.md |
| 2026-11-23 | Governed Reader Path Phase, Sprint 1 closeout | PR #48 |
| 2026-11-23 | Sprint 2 reader semantic release and explicit owner approval, ADR-017 | PR #49, docs/reader-path.md |
| 2026-11-23 | Governed Reader Path Phase Exit Record (Sprint 2 and the phase closed by the owner's merge of the record) | docs/governed-reader-path-phase-exit.md |
| 2026-11-23 | Governed Reader Path Phase accepted and closed by owner merge. Merged before the planned independent review; reconciled after the merge with no blocking finding | PR #50 |
| 2026-11-23 | Governance correction of the phase exit record: review order recorded; review-before-merge rule | PR #51, docs/governed-reader-path-phase-exit.md section 14 |
| 2026-11-24 | Project state synchronized after the reader phase closeout | PR #52 |
| 2026-11-24 | Phase Transition Hold released by the owner; two-layer data architecture approved; Source Dataset Provenance Phase selected (Layer 1 only) | docs/source-dataset-provenance-phase-exit.md, sections 2 and 4 |
| 2026-11-24 | Source Dataset Provenance Phase, Sprint 1 immutable source membership, ADR-018 | PR #53, docs/source-datasets.md |
| 2026-11-24 | Source Dataset Provenance Phase Exit Record (Sprint 1 and the phase closed by the owner's merge of the record) | docs/source-dataset-provenance-phase-exit.md |

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
| Decisions (ADR-001 to ADR-018) | docs/decisions/ |
| Owner authorizations for live actions | docs/decisions/phase-6d-*.md |
| Phase write-ups | docs/phase-2-skeleton.md through docs/phase-6-provider-worker.md |
| Live pilot and preflight records | docs/pilot/ |
| Failure records | docs/failure-intelligence/ |
| Milestone table and maturity labels | docs/project-status.md |
| Model role cards and catch-up prompts | docs/onboarding/ |
| Capture receipts and the artifact store | docs/capture.md, docs/decisions/sprint-7-adrs.md, docs/decisions/sprint-10-adrs.md |
| Advisory CI check | docs/ci.md, .github/workflows/tests.yml, .github/scripts/ci_tests.py |
| Offline Infrastructure Phase exit record | docs/offline-infrastructure-phase-exit.md |
| Proposal grounding | docs/grounding.md, docs/decisions/source-interpretation-sprint-1-adrs.md |
| Semantic review | docs/semantic-review.md, docs/decisions/source-interpretation-sprint-2-adrs.md |
| Reasoning envelope | docs/reasoning-envelope.md, docs/decisions/source-interpretation-sprint-2-adrs.md |
| Governed Source Interpretation Phase exit record | docs/governed-source-interpretation-phase-exit.md |
| Governed reader path | docs/reader-path.md, docs/decisions/reader-path-sprint-1-adrs.md, docs/decisions/reader-path-sprint-2-adrs.md |
| Governed Reader Path Phase exit record | docs/governed-reader-path-phase-exit.md |
| Source datasets (Layer 1) | docs/source-datasets.md, docs/decisions/source-dataset-sprint-1-adrs.md |
| Source Dataset Provenance Phase exit record | docs/source-dataset-provenance-phase-exit.md |

## 10. Keeping this file current

- ChatGPT updates sections 6 and 7 in every sprint closeout PR.
- Claude checks the update during review.
- Sections 1 to 5 and 8 change only by owner decision.
- Update the "Last updated" line with the date and the main commit.
