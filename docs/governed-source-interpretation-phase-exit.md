# Ripley One — Governed Source Interpretation Phase Exit Record

Prepared: 2026-11-23. Owner: Robert Legorreta, Cyrus Forge Systems, LLC.

## 1. Status of this record

This record is published in a Draft pull request and independently reviewed before the owner decides. It is also the Sprint 2 closeout. It becomes the formal closure of Sprint 2 and the formal acceptance of the Governed Source Interpretation Phase only by the owner's merge of that pull request into main. This file exists on main only if the owner merged it; in that case the merge commit is the acceptance, and its date is the acceptance date. If you are reading this file on a branch or in an open pull request, Sprint 2 and the phase are not yet closed.

Completing this phase is not production readiness, not provider readiness and not modeling readiness. It authorizes no source reader, model, provider activity, agent capability, Sprint 3, Phase 6E, Dispatch #3 or Track B work.

## 2. Why this phase existed

Owner direction of 2026-11-21 set Track A as Ripley One, the native agentic orchestration platform, and Track B as the NFL Predictor, a later workload on Ripley One. This is the first Track A phase.

Its purpose was to prove that Ripley One can accept an untrusted proposal about captured evidence, deterministically establish whether the proposal is grounded in the exact captured bytes, route the grounded proposal to independent human semantic review, and preserve the complete evidence chain without granting the proposal-producing component authority to act. It also had to put fixed limits around a future reasoning attempt before any reasoning component exists.

The phase was offline. It used UTF-8 plain text, a human semantic reviewer and no model. It deliberately stopped short of building a source reader.

## 3. Accepted baseline

- Code, tests and CI: main 2a4d606f0d0ae5a8c9ac3f265bd4e2b5a052cf44 (merge of PR #45). Its tree is identical to commit e32e831f1429da2d42249f89ee578b145d1efcee, which Claude reviewed.
- CI tooling, unchanged since PR #38: runner SHA-256 95b5dfd04e30938e94b6835b52aecfdd55a658c4018a4c74972f8cf207675643; workflow SHA-256 68b451b8994aaf2e67cf261d95aca71d880a79ea4c6dcda41284cc5d4369c239.
- Test suite at this baseline: 351 tests. Linux: 351 run, 0 skipped (independently run by Claude). Windows: 351 run, 4 expected Phase 5 skips (reported by the owner).
- This record changes documentation only.

## 4. Governing decisions

- ADR-013: proposal contract and grounding trust boundary. Approved by the owner, dated 2026-11-22.
- ADR-014: independent semantic review record. Approved by the owner before the Sprint 2 implementation release on 2026-11-21.
- ADR-015: bounded reasoning envelope. Approved by the owner before the Sprint 2 implementation release on 2026-11-21.
- ADR-001 to ADR-012 are unchanged by this phase.
- The timebox and accountability standard, approved by the owner on 2026-11-21, governed both sprints.

## 5. Exit gate evaluation

The owner approved six conditions for this phase.

| # | Condition | Status | Evidence in the repository |
|---|---|---|---|
| 1 | Proposal contract established: a governed contract defines how untrusted proposals refer to captured evidence, including exact source and citation semantics and the distinction between grounding and semantic correctness | SATISFIED | ADR-013; docs/grounding.md |
| 2 | Exact-byte grounding proven: Ripley deterministically demonstrates that proposed observations cite the exact Snapshot-bound captured bytes they claim to rely on, with detecting tests for substitution, malformed citations, byte and character confusion, normalization, and unavailable or altered evidence | SATISFIED | Sprint 1 (PR #43); docs/grounding.md, "Sprint 1 acceptance evidence" |
| 3 | Hostile and malformed inputs proven safe within scope: malformed proposals, unsupported content, contradictory observations, injection-like instructions, excessive inputs and evidence failures produce bounded outcomes without gaining authority or silently changing evidence | SATISFIED within the approved deterministic scope | Sprint 1 (PR #43); tests GV-01 to GV-28 |
| 4 | Independent semantic-review boundary implemented and proven: a grounded proposal can be handed to an independently controlled human semantic reviewer through a durable review record that identifies the exact proposal, grounding evidence, reviewer and verdict; the producer cannot approve the proposal's meaning or control the review criterion | SATISFIED | Sprint 2 (PR #45); ADR-014; docs/semantic-review.md |
| 5 | Cost and execution envelope proven for the first reasoning-capable profile: deterministic limits exist for requests, retries, input and output size, deadline and paid execution; exhaustion or uncertainty fails closed; a live provider call is not required | SATISFIED within the approved offline contract | Sprint 2 (PR #45); ADR-015; docs/reasoning-envelope.md |
| 6 | Phase closeout accepted by owner merge: a final phase record states what was proven, what remains unproven, the security and authority limitations and deferred work | SATISFIED BY THE OWNER'S MERGE OF THIS RECORD | This file. See section 1 |

## 6. What was built and proven

Each item is proven only within the scope stated.

Grounding (ADR-013, Sprint 1):
- A proposal is untrusted data. It binds to one Snapshot and may cite only the capture references already on that Snapshot. It cannot add evidence.
- Capture evidence is verified all-or-nothing. The stored object is read once, checked against the receipt's size and SHA-256, and citations are evaluated against those same bytes.
- Citation offsets are zero-based byte offsets, start inclusive and end exclusive. A match is exact UTF-8 byte equality. Case, whitespace, line endings, Unicode form and byte-order marks are not normalized. A citation that splits a multi-byte character fails.
- A verdict is recorded for every observation. Declared uncertainty stays declared. A field with more than one observation is listed, not resolved.
- Rejected proposal content is not stored. Only its hash, size and bounded rejection reason are recorded.
- Instructions inside captured text or a proposal remain data and acquire no authority.

Semantic review (ADR-014, Sprint 2):
- A review targets one grounding validation by id and hash, and the pinned proposal is checked.
- The producer identity is read from the proposal, never from the reviewer. The reviewer kind is human. A reviewer label equal to the producer label, compared without regard to case, is refused.
- One fixed, hash-pinned set of criteria applies. Neither the producer nor the reviewer can replace it.
- Every eligible observation receives exactly one decision: acceptable, rejected or needs_clarification. An observation that is not grounded cannot receive one.
- Each decision carries the observation's declared status and grounding verdict, so an acceptable decision on an uncertain observation stays visibly uncertain.
- A validation is reviewed once. A review is never edited or superseded. A refused review stores none of the supplied decisions.
- A review changes no earlier record and creates no authority. acceptable is not approval.

Reasoning envelope (ADR-015, Sprint 2):
- The envelope is a two-step ledger gate that executes nothing.
- Fixed limits: 1 attempt per operation; 0 automatic retries; input at most 262,144 bytes; output at most 65,536 bytes; deadline 120 seconds; budget at most 500,000 micro-dollars. Actual paid authority is 0.
- No caller can pass a limit. Each attempt pins the envelope hash and a copy of the limits, and a close is judged against that copy.
- A second attempt on the same operation is refused. A failed, uncertain or never-closed attempt stays consumed. Consumption is counted from the ledger and survives restart.
- Oversized output, a cost above the limit and a late close are each recorded as violations.
- It has no field for children, fan-out, delegation, tools, provider or model.

## 7. Evidence identities

| Item | Value |
|---|---|
| Sprint 1 implementation PR | #43 |
| Sprint 1 commit 1 (ADR-013 only) | 2b711e039a5d82362753ab88c1ddbd406b373b9d |
| Sprint 1 reviewed head | bdcfb0382e8a373df6e539fe821f7295f4e5e352 |
| Sprint 1 merged main | 4e10661c1bbd636695a718eb3c2bdadb78ebda58 |
| ADR-013 file SHA-256 | 8166d06cdde52e3901db2520302ab2877f001f730316a0bc2ca60b1d28cbf771 |
| Sprint 1 tests | 54 new; 285 in the full suite |
| Sprint 1 mutation checks | 29 of 29 detected (independent, Claude) |
| Sprint 1 closeout PR | #44; reviewed head 6fa36c0f0e8ac155ddc1e646864d2caf90027644; merged main 375a368a77257b95085340d128cdaca3992426e7 |
| Sprint 2 implementation PR | #45 |
| Sprint 2 commit 1 (ADR-014 and ADR-015 only) | d231af9595d310428678c6cbb9a07531992e291b |
| Sprint 2 reviewed head | e32e831f1429da2d42249f89ee578b145d1efcee |
| Sprint 2 merged main | 2a4d606f0d0ae5a8c9ac3f265bd4e2b5a052cf44 |
| ADR-014 and ADR-015 file SHA-256 | a59474cd722eac649bfcff8cc185291c9931f9dad684b21a0f94956fe1d133c9 |
| Review criteria identifier and SHA-256 | semantic-review-criteria-v1; 50fca7d3f9064bfcaeac785064ec35b13475f7f5881f9d543371b5028d747a38 |
| Reasoning envelope identifier and SHA-256 | reasoning-envelope-v1; 0ef7f6be571dc111d359202471d6c8ab9b12193adaf879b66664b3b26fd99224 |
| Sprint 2 tests | 66 new (33 semantic review, 33 reasoning envelope); 351 in the full suite |
| Sprint 2 mutation checks | 52 of 52 detected: 26 semantic review, 26 reasoning envelope (independent, Claude) |
| Sprint 2 assignment artifact | 51,843 bytes; SHA-256 41888ddd410c20fa900e40459bd96c34a121b9950e02080b5d159e599e6ec2f8 |

Sprint 1's detailed evidence is in docs/grounding.md.

## 8. Sprint 2 acceptance evidence

Evidence is grouped by who established it.

Independently reproduced or observed by Claude:
- Scope: eight files, seven new and one bounded modification. The other 66 baseline files were byte-identical.
- The published ADR file is byte-identical to the approved text. The criteria hash and the envelope hash were recomputed from the published code and match the values in section 7.
- Linux, Python 3.13 with anthropic 2.9.0, on tested commit 94444162f44a24e31ee07dd8a0a75e26b47462f8, in a disposable copy with no proxy variables: semantic review 33 run, 33 passed, 0 skipped; reasoning envelope 33 run, 33 passed, 0 skipped; full suite 351 run, 0 failures, 0 errors, 0 skipped.
- Mutation checks: the 52 assigned defects were applied one at a time to the published modules. Each made at least one assigned test fail. Both modules were restored and their hashes re-checked.
- Supplemental probes outside the assigned tests: a reviewer using the producer's label in upper case was refused; decision text containing instruction-like wording was stored as data and changed nothing else; a reopened ledger refused a second attempt.
- End-to-end trace from the SQLite file alone: review to grounding validation, proposal, Snapshot and capture receipt, and attempt to close. Ten checks passed.
- Review verdict: APPROVED WITH NONBLOCKING NOTES FOR OWNER WINDOWS GATE.

Public hosted page observed by Claude:
- Run 44966347112, for commit 2: Success, pull request #45, commit e32e831, event pull_request, one job, no artifacts. Claude did not observe its logs.

Reported by the owner (Windows gate; Claude did not observe the terminal output):
- Semantic review: 33 run, 33 passed, 0 failures, 0 errors, 0 skips.
- Reasoning envelope: 33 run, 33 passed, 0 failures, 0 errors, 0 skips.
- Full suite: 351 run, 4 expected existing Phase 5 skips, 0 failures, 0 errors.

Reported by the implementer (ChatGPT):
- Local, Python 3.12.14 with anthropic 2.9.0, proxy variables unset: semantic review 33 of 33; reasoning envelope 33 of 33; full suite 351 of 351, 0 skipped.
- Hosted check for commit 1: successful; tested commit 2e1be0ac8ce2c45a6681d776cb64b6d36c8088d8; 285 run, 0 failures, 0 errors, 0 skipped; PASSED; checkout unchanged. Claude did not observe this run's page, and no run identifier for it is recorded here.
- Hosted check for commit 2, log lines: tested commit 94444162f44a24e31ee07dd8a0a75e26b47462f8; 351 run, 0 skipped; PASSED; checkout unchanged. The 351 figure agrees with Claude's own run.

Nonblocking review notes:
- The hosted run for commit 1 was not independently observed.
- An injected clock that raises an error is reported as invalid_clock. The contract did not spell this case out; the behavior is reasonable.
Neither is scheduled work.

No provider call was made. No pre-existing runtime, test, CI, provider or ADR file was changed. No spending occurred.

## 9. Operating boundaries that remain

- Grounding handles UTF-8 plain text only and does not check a value against its quote.
- Reviewer and producer identities are labels. They are not authenticated. The independence check does not detect one person using two labels.
- A validation is reviewed once. There is no revision and no reviewer interface.
- The envelope runs nothing and nothing uses it yet. Its deadline is detection and record, not termination. Its budget is synthetic accounting. Sizes and costs are declared by a trusted host and are not measured.
- Grounding, semantic review and the envelope are called directly. None is a step in the Core Task and Worker flow.
- ADR-010's dispatch governance is separate from the envelope and unchanged.
- The provider request, prompt, model, schema and dispatch logic remain frozen by owner direction.

## 10. What this phase does not claim

Acceptance of this phase does NOT establish any of the following:
- a source-reading model or a reasoning agent
- model-generated proposals
- autonomous research
- provider execution or successful live provider validation
- correctness of a provider's bill or of any conversion from tokens to cost
- compliance of a provider SDK with the envelope
- cancellation of a network call or termination of a process at a deadline
- authenticated or alias-resistant reviewer identity
- multi-agent orchestration, parent and child agents, or tool-enabled reasoning
- automated remediation or self-modification
- deployment authority
- source formats other than UTF-8 plain text
- that a grounded observation is true, or that a source is authentic or truthful
- production readiness
- modeling readiness or any predictive capability

These are not defects. They are capabilities this phase did not attempt and does not claim.

## 11. Provider and FI-001 status

This phase did not touch the provider-validation track.
- Provider path: mock-proven. Live validation is incomplete.
- Dispatch #3: PAUSED and UNAUTHORIZED.
- Phase 6E: NOT STARTED.
- FI-001 historical cause: UNCONFIRMED, pending the provider's reply.
- No live provider call was required or made in this phase. No provider freeze is lifted by it. Neither a semantic review nor the envelope creates provider authority.

## 12. Track A and Track B

This phase is Track A infrastructure. It built domain-independent governance for captured evidence, proposals, grounding, semantic review and a bounded future reasoning attempt, proven on synthetic non-NFL fixtures. It introduced no NFL features, forecasts, models, historical comparisons or analytics logic. Track B remains separate and is not started.

## 13. Remaining work and its disposition

A classification is NOT authorization to begin work. Each item needs its own planning, review and owner decision. No Sprint 3 is authorized.

| Item | Classification | Note |
|---|---|---|
| A bounded source reader as a model-backed Worker | NEXT-PHASE CANDIDATE | Needs its own ADR and owner decision |
| Running grounding, semantic review and the envelope inside the Core Task and Worker flow | NEXT-PHASE CANDIDATE | Each ADR says this needs its own decision |
| A read-only ledger status report | NEXT-PHASE CANDIDATE | Carried from the previous phase |
| A model or Worker producer kind for proposals | FUTURE GOVERNANCE DECISION | Requires a revision of ADR-013 |
| Reconciling the envelope with ADR-010 dispatch governance | FUTURE GOVERNANCE DECISION | Required when a reader is given a provider |
| Agents, parent and child work, and tool use | FUTURE GOVERNANCE DECISION | Each needs an ADR, independent review and the owner's decision |
| Authenticated reviewer identity | DEFERRED | |
| Revision of a review; a reviewer interface | DEFERRED | |
| Checking a value against its quote | DEFERRED | |
| Source formats other than UTF-8 plain text | DEFERRED | |
| Real cost figures and enforcement by termination for a reasoning attempt | DEFERRED | |
| Network acquisition for capture | DEFERRED | Needs an owner decision on sources and a rights classification |
| Health observation, diagnosis, remediation and an upgrade sandbox | DEFERRED | Product vision; not designed |
| Live provider validation, Dispatch #3, Phase 6E | EXTERNALLY BLOCKED | Pending the provider's reply on FI-001, and then a separate written owner authorization |
| NFL Predictor and any analytics modeling | SEPARATE TRACK | Track B |
| Test P6-11 rewrites the real prompt file; Phase 1-era rows in docs/project-status.md; a hand-forged capture record can raise an error in grounding | BACKLOG | None scheduled |

## 14. Schedule and accountability outcome

Both sprints ran under the owner-approved timebox standard: a target date, a reauthorization deadline, a midpoint, at most two material architecture correction rounds, and quality gates that outrank the date.

- Sprint 1: target Monday, November 23, 2026, 6:00 PM Central; reauthorization deadline Tuesday, November 24, 2026, 6:00 PM Central. Implementation merged Saturday, November 21, 2026. Closeout merged the same day. Two architecture rounds were used.
- Sprint 2: target Monday, November 23, 2026, 6:00 PM Central; reauthorization deadline Wednesday, November 25, 2026, 6:00 PM Central. Implementation was published and independently reviewed on Saturday, November 21, 2026, and merged after the owner's Windows gate on Monday, November 23, 2026, before the target. The assignment was implemented as first issued.
- Phase: planning window November 21 to 27, 2026; reauthorization boundary Monday, November 30, 2026, 6:00 PM Central. This record was prepared on November 23, 2026.
No reauthorization was needed. No work was added to fill remaining time.

## 15. Sprint 2 retrospective

**What worked**
- The improvement carried from Sprint 1 was applied: the assignment went out once, as one self-contained file with a byte count and SHA-256, and was implemented as issued.
- Both modules were prototyped before release, and the test list and mutation list were fixed from that prototype.
- The ADR file was published byte-identical to the approved text. The criteria text and the envelope limits are pinned by literal hashes in the tests.
- The first published commits passed independent review with no correction. All 52 assigned mutations were detected.
- No pre-existing runtime or test file changed. The only pre-existing file modified was docs/project-status.md, by its one assigned row.

**What caused friction**
- During prototyping, the reviewer's mutation tool reused cached bytecode from a defective copy of a module and showed two false failures. The cause was found, caching was disabled, and the independent review ran without it.
- The run identifier for the commit 1 hosted check did not reach the reviewer, so that run could not be observed.
- The owner's Windows output was not passed to the reviewer, so it is recorded as owner-reported.
- A phase closeout draft was prepared outside the assignment workflow before Sprint 2 had a closeout. The owner resolved this by choosing one combined closeout.

**One improvement to carry forward**
Every publication report and every review request lists the hosted run identifier for each commit, and the owner's gate output is passed to the reviewer as text.

## 16. Phase retrospective

**What worked**
- A written exit gate, approved before the work, decided when the phase was finished. It ended after two sprints with no work invented to fill the estimate.
- Narrow capabilities, each with an ADR accepted before implementation.
- An independent feasibility review before release, and an independent review of the published commits after.
- Mutation checks specified in advance and applied to the published code.
- Frozen-file boundaries: across both sprints no existing runtime or test file changed.
- Linux and Windows verification, and owner-controlled merges.
- Claims kept separate from deferred capability.

**What caused friction**
The largest process failure was at the start of Sprint 1. Controlling material was handed between models in fragments across several chat messages. That produced incomplete artifacts, repeated feasibility loops and extra relays by the owner. The engineering design was not the problem. The transport was.

**Improvement adopted**
One complete, self-contained, hash-verified artifact per major handoff. The chair confirms that an artifact is complete before asking the owner to relay it. The owner is not asked to reconstruct or splice messages from the models.

## 17. What happens next

After the owner accepts this phase, the next action is a Phase Transition Round Table. The next phase is selected only there. This record does not choose it, does not name it and does not authorize any of its work. No Sprint 3 exists.

## 18. Acceptance

By merging the pull request that adds this file to main, Robert Legorreta, Product Owner, closes Sprint 2 and accepts the Governed Source Interpretation Phase as complete against its approved exit gate. The merge does not authorize a source reader, model or provider activity, agent capability, Sprint 3, Phase 6E, Dispatch #3 or Track B modeling. Any later capability requires its own governed scope and authorization. No signature line is used; the repository history is the record.
