# Ripley One — Governed Reader Path Phase Exit Record

Prepared: 2026-11-23. Owner: Robert Legorreta, Cyrus Forge Systems, LLC.

## 1. Status of this record

This record was published in a Draft pull request, PR #50. The intended process is independent review before the owner decides. For PR #50 that order was not followed: the owner merged first and the independent review followed. Section 14 records what happened. It is also the Sprint 2 closeout. It becomes the formal closure of Sprint 2 and the formal acceptance of the Governed Reader Path Phase only by the owner's merge of that pull request into main. This file exists on main only if the owner merged it; in that case the merge commit is the acceptance.

Completing this phase is not production readiness, not provider readiness and not modeling readiness. It authorizes no model, provider activity, network use, tool, agent, child, delegation, Sprint 3, next phase, Phase 6E, Dispatch #3, Track B work, new source format, authentication project, consumer of approved readings, commercial work, or change of repository visibility or licensing.

## 2. Why this phase existed

The Governed Source Interpretation Phase proved grounding, independent semantic review and a bounded reasoning envelope as three separate modules, each called directly. None ran inside Core, no Worker had ever received captured bytes, and nothing had produced a proposal except by hand.

This phase existed to prove one governed reader path — verified captured bytes, to a deterministic isolated reader Worker, to an untrusted proposal, to grounding, to independent human semantic review, to human approval — under Ripley's existing lifecycle, provenance, recovery, isolation and authority controls. It was required not to implement a model-backed reader. It ran offline on UTF-8 plain text with a deterministic reader, a human semantic reviewer and a human owner.

## 3. Accepted baseline

- Code, tests and CI: main faeabd3569c0241032f27b452c547fc74c67d33a (merge of PR #49). Its tree is identical to commit ac2f345760e18019ada885a7c989295be873afa2, which Claude reviewed.
- CI tooling is unchanged by this phase.
- Test suite at this baseline: 428 tests. Linux: 428 run, 0 skipped (independently run by Claude). Windows: 428 run, 4 expected Phase 5 skips (reported by the owner).
- This record changes documentation only.

## 4. Governing decisions

- ADR-016: governed reader path and deterministic reader Worker. Accepted by the owner on 2026-11-23, as Revision 1 of the Sprint 1 assignment.
- ADR-017: reader semantic release and explicit owner approval. Accepted by the owner on 2026-11-23, before the Sprint 2 implementation release.
- ADR-016 makes one reader-only exception to ADR-012 and revises ADR-013 decision 3 in one respect (a Worker producer kind that only Core may use). ADR-017 revises ADR-016 decision 19 in one respect (awaiting_semantic_review gains two exits). ADR-010, ADR-011, ADR-014 and ADR-015 are unchanged.
- Owner policy decisions recorded in ADR-017: approval applies only to the reviewed eligible subset; a negative semantic review blocks the task; uncertainty stays visible; the owner decision is a separate entry point with a reader-specific pending status; approval authorizes no downstream action.
- The timebox and accountability standard governed both sprints.

## 5. Exit gate evaluation

The owner approved seven conditions for this phase on 2026-11-23.

| # | Condition | Status | Evidence in the repository |
|---|---|---|---|
| 1 | Reader contract accepted: an ADR defines the proposal-as-Worker-output contract, verified byte delivery, trusted producer identity and the authority boundary | SATISFIED | ADR-016; docs/reader-path.md |
| 2 | End-to-end reader path proven: a deterministic isolated reader consumes verified captured bytes and returns a proposal through governed Ripley flow, with a reconstructable evidence chain | SATISFIED | Sprint 1 (PR #47); tests RP-01 to RP-03, RP-22; docs/reader-path.md, "Sprint 1 acceptance evidence" |
| 3 | Envelope governs the attempt: durable reservation before execution; one attempt; input and output bounds; deadline; failure and uncertainty remain consumed; recovery cannot create a second attempt | SATISFIED | Sprint 1 (PR #47); tests RP-07, RP-08, RP-10 to RP-12, RP-16, RP-17 |
| 4 | Hostile or failing reader contained: malformed proposal, ungrounded proposal, oversized output, instruction-like content, crash, hang and evidence substitution are bounded, and no new authority results | SATISFIED within the approved deterministic scope | Sprint 1 (PR #47); tests RP-04, RP-05, RP-09 to RP-11, RP-13, RP-14, RP-23 |
| 5 | Human gates preserved: no path reaches final approval without grounding, then independent semantic review, then human approval; semantic acceptability is not execution approval | SATISFIED | Sprint 2 (PR #49); ADR-017; tests RR-01 to RR-16; section 8 |
| 6 | Existing behavior preserved: the existing regression suite stays green; the provider path is untouched; the provider request, prompt, model and schema remain frozen; no live activity | SATISFIED, with one owner-authorized change to an existing test recorded in section 8 | 428 tests; frozen-file comparisons in both sprints |
| 7 | Phase closeout accepted by owner merge | SATISFIED BY THE OWNER'S MERGE OF THIS RECORD | This file. See section 1 |

All engineering conditions, 1 to 6, are satisfied. No Sprint 3 is justified by this gate.

## 6. What was built and proven

Each item is proven only within the scope stated.

Reader production boundary (ADR-016, Sprint 1):
- A reader is a Worker that reads the text it is given and returns observations. It holds no authority. The first reader is deterministic: it reports each "Field: value" line for the requested fields, or not found. It uses no model, provider, network or tool.
- A reader runs only through one Core entry point. The existing task path refuses a reader Worker, and the reader path refuses any other Worker.
- Core, not the reader, selects the evidence: exactly the Snapshot's capture references. Core verifies each receipt and its stored bytes, delivers the verified text to the existing isolated process, and the host checks size and hash again. The reader is given no store path, ledger handle, credential or network. The delivered text is not copied into the ledger.
- Core sets the producer identity from the trusted Worker descriptor. A reader's output may hold observations only.
- Reader-only exception to ADR-012: for a reader task alone, the capture references are part of the inputs, the packet and the task key. Every other task and every provider packet is unchanged.

Exact-byte grounding, inside Core:
- Core assembles the proposal and grounds it under ADR-013 against the same Snapshot-bound bytes. A rejected proposal, blocked evidence, or a proposal in which nothing is grounded blocks the task. A proposal does not advance because an approved Worker produced it.

Bounded reasoning envelope, in use:
- Core reserves one ADR-015 attempt before launch, with an input size it measures itself, and closes the attempt from what it observed. The attempt's absolute deadline governs preparation as well as execution: only the time remaining is given to the process, and an attempt that has already expired is not launched and stays consumed.
- One attempt. No retry and no correction loop. The existing recovery function refuses a reader task and writes nothing.

Core-integrated deterministic reader:
- A grounded reader task is bound by a sixteen-key record that pins six linked records by id and content hash, and enters the durable state awaiting_semantic_review. A read-only chain check reports any of 20 break reasons and writes nothing.

Semantic-review independence:
- ADR-014 is unchanged. The reviewer is a human label that must differ from the reader's Worker identity, compared without regard to case. A review changes no task state and is not approval.

Release from semantic review (ADR-017, Sprint 2):
- Release is a separate Core operation invoked by a person, who names one binding and one semantic review, each by id and hash. Core verifies the binding, the chain, the task, the review, its exact relationship to the validation, proposal and Snapshot, the pinned criteria, the producer, the reviewer, complete decision coverage, and that the review is the only one. Any failure is a recorded refusal, one of twenty reasons, that leaves the task state unchanged.
- One immutable release record of fifteen keys is written for either outcome.
- A release creates no owner verdict.

Approval scope, excluded observations and preserved uncertainty:
- Core derives four lists in proposal order: included, uncertain, not found and excluded. The caller cannot choose them. An observation that was not grounded is excluded, stays visible and is never approved.
- If any decision is rejected or needs clarification, the task is blocked and no pending approval exists. Rejection takes precedence. A rejected semantic review is not an owner rejection. There is no clarification state, revision, second review or automatic reread.
- Uncertainty declared by the reader stays declared in the proposal, the grounding validation, the semantic review, the release record, the pending approval and the judgment.

Explicit separate owner decision:
- An eligible release writes a pending approval with the reader-specific status pending_reader_owner_approval and nine data keys, then moves the task to pending_owner_approval, in that order.
- The owner decision has its own entry point. The existing approval entry point refuses a reader pending approval for approval and for rejection, and the reader entry point refuses an existing-style pending approval, each by an explicit comparison of the status. The existing approval operation was not edited.
- The decision requires the owner label, an explicit approved or rejected, and a reason. Before writing it derives every release fact again from the ledger and compares it with the stored release record and the pending approval. A stored statement of eligibility is not trusted.
- The judgment is an approval record with ten data keys whose own supersedes field names the pending approval.
- Approval means the owner accepts the exact reviewed eligible observation set identified by the release record as an acceptable reading of the captured evidence. It approves nothing excluded, erases no uncertainty, establishes neither truth nor authenticity, and authorizes no downstream action.

Restart and duplicate protection:
- A reader task's consumed attempt stays consumed across restart. awaiting_semantic_review and pending_owner_approval survive restart.
- Records left by an interrupted release grant no authority; an identical repeat completes what is missing and writes nothing that exists. A different binding or review for an already released task is refused.
- If a judgment was written and the state change was not, an identical repeat adds only the state change. An opposite decision is refused.
- Neither release nor the owner decision creates a Task, Snapshot, Worker attempt or envelope reservation, launches anything, or rereads captured bytes.

## 7. Evidence identities

| Item | Value |
|---|---|
| Sprint 1 implementation PR | #47 |
| Sprint 1 commit 1 (ADR-016 only) | 77ae5fdd4d23548e5553598251b2d10480c0fb81 |
| Sprint 1 reviewed head | abca2ef75eab59e2302459d0a396cd6f281f9488 |
| Sprint 1 merged main | 1374b2fc13b5c96da6c27d24bf85fe87bc49561c |
| ADR-016 file SHA-256 | 37ef4fcdf59583ac540ec7e557c7b3a905d58c95bd2f64d05fdb0b2c8d9920cf |
| Sprint 1 tests | 45 new; 396 in the full suite |
| Sprint 1 mutation checks | 49 of 49 detected (independent, Claude) |
| Sprint 1 assignment artifact | ripley-governed-reader-path-sprint-1-final-r1.md; 67,363 bytes; SHA-256 3b97b7f2a8c058bacfdff394401afaf6a722d84d87a6d319e7f2fa8feacadad7 |
| Sprint 1 closeout PR | #48; reviewed head 4eb89f7cd9a2ba4a67f424b30db27beb2d5411ec; merged main 0a520ab7361ab4232efa593c1a93b2a69b300071 |
| Sprint 2 implementation PR | #49 |
| Sprint 2 commit 1 (ADR-017 only) | 4dd675c7fbb0c1c8e43dc0d4689137ce13430710 |
| Sprint 2 reviewed head | ac2f345760e18019ada885a7c989295be873afa2 |
| Sprint 2 merged main | faeabd3569c0241032f27b452c547fc74c67d33a |
| ADR-017 file SHA-256 | 7fc2c26827146e193903d4c10bb826135daa3b14e0d0c1f6854529dd41dd6223 |
| Sprint 2 tests | 32 new; 428 in the full suite |
| Sprint 2 mutation checks | 50 of 50 detected on the in-memory ledger and 50 of 50 on SQLite (independent, Claude) |
| Sprint 2 assignment artifact | ripley-governed-reader-path-sprint-2-final-r1.md; 58,503 bytes; SHA-256 d43252071677f06d04da36111b80c317faea1835d8d715a1c08e85f94f8d1a8c |

Sprint 1's detailed evidence is in docs/reader-path.md.

## 8. Sprint 2 acceptance evidence

Evidence is grouped by who established it.

Independently reproduced by Claude, on the published head ac2f345:
- Lineage: two commits; commit 1 changes only the ADR file; the head's parent is commit 1 and commit 1's parent is the baseline 0a520ab.
- Scope: six files, two new and four modified. The other 75 baseline files were byte-identical.
- The published ADR-017 text is byte-identical to the approved text (9,533 bytes).
- ripley/core.py changed in three places only: one new constant, one transition-table entry and three appended methods. The existing approval method and every other existing method were unchanged.
- tests/test_reader_path.py changed by exactly two lines of test RP-15. The owner authorized this change in advance, because RP-15 pinned the Sprint 1 rule that awaiting_semantic_review has no exit. RP-15 now proves that only the two ADR-017 exits exist and that no direct exit to approved or rejected exists. No other existing test was changed.
- Linux, Python 3.13 with anthropic 2.9.0, in a disposable copy with no proxy variables: focused release tests 32 run, 0 failures, 0 errors, 0 skipped; full suite 428 run, 0 failures, 0 errors, 0 skipped.
- Mutation checks: the 50 assigned defects RL01 to RL50 were applied one at a time to the published code, and each ledger's test class was run separately. Each defect made at least one of its assigned tests fail on the in-memory ledger and on SQLite. This includes a judgment written without its supersedes field and a judgment that supersedes the wrong record.
- Review verdict: APPROVE FOR OWNER WINDOWS GATE, with the known bounded item in section 9 recorded as nonblocking.

Reported by the implementer (ChatGPT), as relayed by the chair:
- Focused release tests 32 passed; Linux full suite 428 passed with zero failures, errors and skips; 50 of 50 mutations detected on both ledgers; git diff --check clean.
- Hosted advisory check, pull request #49: commit 1 run 45317365557, conclusion SUCCESS; commit 2 run 45319402229, conclusion SUCCESS, CI SUMMARY run=428 failures=0 errors=0 skipped=0.
- Claude was not given the hosted run identifiers and did not observe those runs. Claude's own run of the same head is the independent figure.

Reported by the owner (Windows gate; Claude did not observe the terminal output):
- Controlling result, on head ac2f345 with the pinned provider SDK installed: focused release tests 32 run, 32 passed, 0 failures, 0 errors, 0 skips; full suite 428 run, 4 expected existing Phase 5 skips, 0 failures, 0 errors.
- Chronology only, not acceptance evidence: an earlier Windows run of the same head reported 428 run, 0 failures, 0 errors and 43 skips. The pinned provider SDK was not installed in that environment, so the provider tests were skipped. Claude's review held the merge until the suite was rerun with the SDK installed. The controlling result above is that rerun.

How Sprint 2's required evidence is covered by tests in tests/test_reader_release.py:
- Approval-route isolation: RR-11.
- Reviewed eligible-subset policy, excluded not-grounded observations and preserved uncertainty: RR-01, RR-02, RR-05.
- Negative review blocks: RR-04.
- Release record and refusals: RR-01, RR-06, RR-07, RR-08.
- Reader pending approval: RR-01, RR-10.
- Explicit owner decision and re-verification: RR-02, RR-03, RR-12, RR-13.
- Restart, interruption and repeats: RR-09, RR-10, RR-14, RR-15.
- No execution and exact transitions: RR-16, RP-15.

No provider call was made in this phase. No provider, CI or earlier ADR file was changed.

## 9. Known bounded item

One deviation from the Sprint 2 implementation contract is known. It is recorded here and is not corrected by this record. No correction is authorized.

1. What produces it. A hand-added approval record that carries the reader pending status but is malformed — for example it lacks release_id, release_hash or task_id, or the release record it pins lacks one of its identifiers — makes the reader owner-decision operation raise KeyError or TypeError. The Sprint 2 assignment, and the sentence "Owner-decision refusals raise ValueError without writing anything" in docs/reader-path.md, say every refusal is a ValueError. Claude reproduced 16 such record shapes on the merged baseline.
2. Why it is bounded. In every reproduced case the call raised, nothing was written and no task state changed. The operation fails closed.
3. Whether an ordinary path can produce it. No. Core never writes such a record. It requires code inside the process to append a malformed record directly to the ledger, which ADR-017 decision 20 already names as outside the authority boundary.
4. What it does not do. It creates no authority, corrupts no evidence, bypasses no review or approval, and restores no consumed authority. It does not affect the isolation between the two approval routes, which rests on the explicit status comparison.
5. Classification: FUTURE HARDENING. It is not a blocking defect, it violates no exit-gate condition and no Sprint 2 acceptance criterion, and it is not scheduled.

## 10. What this phase deliberately did not prove

- That a model can be run on this path. No model, provider, network or tool was used. The reader is deterministic and first-party.
- That a reader's reading is correct, that a source is authentic or truthful, or that a not-found observation means real-world absence.
- That any label is an authenticated identity. Reviewer, releasing and owner labels are plain strings; one person can use two.
- That hostile code is contained. Process isolation is not a sandbox, and the amount a process writes is measured after it ends, not bounded while it runs.
- That code inside the Ripley process cannot write records or transitions directly to the ledger. A task moved that way has nothing that can be decided, and a hand-built release is decided only if every fact in it equals what Core derives from the evidence.
- That anything follows from approval. An approved reading has no consumer and authorizes no action.
- Continuation after an interruption, a clarification or revision path, any file type other than UTF-8 plain text, concurrency, or a paid reader.
- The provider path, which was not touched. Live validation has not been performed. Dispatch #3 remains paused and unauthorized.

## 11. Deferred work and classifications

None of these is a phase-gate requirement. None is authorized or scheduled.

| Item | Classification |
|---|---|
| A model-backed reader | DEFERRED CAPABILITY; requires its own ADR and owner decision |
| A consumer of approved readings | DEFERRED CAPABILITY; requires its own decision |
| A clarification or revision path after a negative semantic review | DEFERRED CAPABILITY |
| Continuation from a recorded result after an interruption | DEFERRED CAPABILITY |
| Source formats other than UTF-8 plain text | DEFERRED CAPABILITY |
| Authenticated reviewer, releasing and owner identities | FUTURE GOVERNANCE DECISION |
| Whether a person may resubmit a blocked reader task once a reader costs money (ADR-016 decision 25) | FUTURE GOVERNANCE DECISION |
| Reconciling the reasoning envelope with ADR-010 dispatch governance before any paid reasoning | FUTURE GOVERNANCE DECISION |
| Malformed hand-added records raising KeyError or TypeError in the reader owner decision (section 9) | KNOWN BOUNDED ITEM; FUTURE HARDENING |
| Bounding what a process writes before it is measured | LIMITATION |
| The line reader reports a matching line longer than 4,096 bytes as not found | LIMITATION; as specified |
| Records and transitions appended by code inside the process | LIMITATION; stated in ADR-017 decision 20 |

## 12. Schedule and retrospective

Schedule. Phase target: Friday, December 4, 2026, 6:00 PM Central; reauthorization deadline Wednesday, December 9, 2026, 6:00 PM Central. Sprint 1 target: Wednesday, November 25, 2026. Sprint 2 target: Monday, November 30, 2026; reauthorization deadline Wednesday, December 2, 2026. Both implementations were reviewed, verified on Windows and merged on Monday, November 23, 2026. No reauthorization was needed. No work was added to fill the remaining time. Each sprint used one of its two architecture correction rounds.

What worked in Sprint 2:
- The planning round table changed the design before any code. The cross-challenge between the implementer and the architecture lead showed that a second owner-decision method alone would still leave the existing approval method able to reach reader records; the chair's ruling of a reader-specific pending status closed that structurally, and the prototype then showed the existing approval method needed no edit at all.
- The owner decided the approval-scope policy explicitly: the reviewed eligible subset, with exclusions named.
- The design was prototyped before release, and ADR-017 was published byte-identical to the approved text.
- The first published head passed independent review with no correction. All 50 mutations were detected on both ledgers.
- The Windows gate's skip count was checked against the expectation, not waved through. The gate was rerun with the pinned SDK before merge.

What caused friction in Sprint 2:
- The assignment described the judgment's key count ambiguously, and the correction round was spent establishing that supersedes is a field of the ledger record and not a key of its data.
- Independent review found one deviation from the contract that the assigned tests did not cover (section 9). The assignment's tests exercised changed values in hand-added records but not missing keys.
- The first Windows gate ran in an environment without the pinned provider SDK.

One improvement to carry forward:
Before a Windows gate, confirm the pinned provider SDK is installed, and treat any skip count other than the expected one as a gate failure until explained. When a contract says every refusal has one form, test hand-added records with missing keys as well as changed values.

## 13. What follows

By the owner's merge of this record, Sprint 2 is closed and the Governed Reader Path Phase is accepted and closed. That merge authorizes nothing further. No Sprint 3 exists. No next phase is chosen. The next action is a Phase Transition Round Table. Every capability in section 11 requires its own decision.

## 14. Record of the review sequence for this record

This section was added after the merge, by a separate reviewed correction. It changes no engineering evidence and no exit-gate result.

What happened:
1. This record was published as PR #50 at head 85caf680237b1843f775239ffd464a0670b8c5d4, on the baseline faeabd3569c0241032f27b452c547fc74c67d33a.
2. The owner merged PR #50 on 2026-11-23 at 11:19 PM Central, as b880fa47c6f1743d7fd03f4ba1528ae84ba88375, before the planned independent closeout review had been performed.
3. Claude then performed the independent review as a post-merge reconciliation against the exact merged state.

What the post-merge reconciliation verified:
- Lineage: the head is one commit on the authorized baseline; main is the merge of that head; the merged tree is identical to the head.
- Scope: exactly four documentation files, one of them new; the other 78 baseline files byte-identical.
- The literal command git diff --check, baseline to head: no output, exit code 0.
- This record is identical to the assigned text apart from the one authorized implementer line; the other three files carry exactly the assigned edits.
- Every evidence identity, test count and mutation count in this record against the repository and Claude's own evidence.
- Full Linux suite on merged main, Python 3.13 with anthropic 2.9.0, proxy variables unset: 428 run, 0 failures, 0 errors, 0 skipped.
- The seven exit-gate conditions, and the disposition of the known bounded item in section 9.

Result: no blocking technical, evidentiary, scope or phase-gate defect was found.

Supplement to section 8. After the merge Claude read the public pages of the two PR #49 hosted runs named there, 45317365557 and 45319402229. Each shows Success for pull request #49 on the stated commit. Their log lines remain implementer-reported. Claude was not given a hosted run identifier for PR #50 and did not observe one; that gap is recorded as nonblocking, because the merged tree was independently verified and the full suite passed on it.

Owner rulings recorded with this correction: the ADR-017 acceptance date of 2026-11-23 is confirmed; the disposition of the known bounded item in section 9 is final for this closed phase.

The deviation. Merging before the independent review was a departure from the project's intended process of independent review before owner merge. It is recorded here, not concealed. It does not change the accepted engineering evidence or the exit-gate result. Sprint 2 and the phase remain closed by the merge named above; this section is not a second closure.

Rule carried forward. A pull request requiring independent review must not be owner-merged until the independent-review verdict is present in the active owner handoff. If an owner merge occurs before that verdict, the variance must be explicitly recorded and independently reconciled before project advancement.
