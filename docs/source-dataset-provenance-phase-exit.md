# Ripley One — Source Dataset Provenance Phase Exit Record

Prepared: 2026-11-24. Owner: Robert Legorreta, Cyrus Forge Systems, LLC.

## 1. Status of this record

This record is published in a Draft pull request. Under the owner's rule of 2026-11-23, it is not to be merged until the independent-review verdict on that pull request is present in the active owner handoff. It is also the Sprint 1 closeout. It becomes the formal closure of Sprint 1 and the formal acceptance of the Source Dataset Provenance Phase only by the owner's merge of that pull request into main. This file exists on main only if the owner merged it; in that case the merge commit is the acceptance.

Completing this phase is not production readiness, not provider readiness and not modeling readiness. It authorizes no Layer 2 work, no interpreted dataset, no consumer of a source dataset, no Sprint 2, no next phase, no model, provider activity, network use, tool, agent, child or delegation, no Phase 6E, no Dispatch #3, no live replay, no Track B work, no NFL data, no authentication project, no commercial work, and no change of repository visibility or licensing.

## 2. Why this phase existed

The owner approved a two-layer data architecture on 2026-11-24. Layer 1, the source dataset, is an exact reusable membership of captured source evidence. Layer 2, the interpreted dataset, is governed interpreted observations. The owner directed that Layer 1 be built and proven first and that Layer 2 is deferred and is not automatically the next sprint.

Before this phase, nothing persisted in Ripley stated, independently of a Task, which exact Capture observations belong together. A Capture receipt identifies one observation. A Snapshot groups captures only inside one task run, and its identity varies with that task's inputs.

The objective of Sprint 1 was one thing: an immutable, task-independent Source Dataset membership identity that survives restart and can be rebuilt and checked from persisted evidence alone, without creating any execution or approval authority. The phase ran offline on synthetic, local, non-NFL UTF-8 text.

## 3. Accepted baseline

- Baseline before Sprint 1: main a7e1598a9eca3bfc151d9a9ff26bf5937f192f67. 82 tracked files; 428 tests.
- Merged main after Sprint 1: 8a3c331df61067e0338809f298d2a882ba53993d (merge of PR #53, 2026-11-24). 86 tracked files; 450 tests.
- The tree of that merge is identical to the tree of commit 71b2f592b44fed03c02e5c9570e67b40dc099000, the published head that Claude reviewed.
- CI tooling is unchanged by this phase.
- This record changes documentation only.

## 4. Governing decisions

- Two-layer data architecture, Layer 1 first, Layer 2 deferred: owner decision of 2026-11-24.
- ADR-018, source dataset: immutable source membership. Accepted by the owner on 2026-11-24, before the implementation release. It is published at docs/decisions/source-dataset-sprint-1-adrs.md.
- Necessity verdict recorded in ADR-018: a new record was required, because no existing persisted primitive provides a durable, task-independent statement of membership. One record kind, `source_dataset`, with exactly three data keys.
- Owner decisions carried by ADR-018: membership identity is the membership hash, not the ledger record id; one membership has one record per ledger under sequential single-writer use; any second record claiming the same membership hash is ambiguous and needs manual inspection; at most 16 members in Sprint 1; no time claim, name, lineage or retraction.
- ADR-001 to ADR-017 are unchanged. ADR-012's capture-reference shape is reused, not amended.
- The timebox and accountability standard governed the sprint.

## 5. Exit gate evaluation

Seven conditions were set for this phase in the reconciled planning artifact, which also stated that the phase could close after one sprint if all seven were met.

| # | Condition | Status | Evidence in the repository |
|---|---|---|---|
| 1 | Necessity: the existing Capture and Snapshot representation is compared with a minimal source dataset design, and any new persistent abstraction is justified by a capability existing mechanisms do not provide | SATISFIED | ADR-018, "Problem", "Alternatives considered", "Rejected alternatives"; test SD-11 |
| 2 | Identity: exact immutable source membership has a deterministic canonical identity; one membership has one record per ledger under sequential single-writer use; repeat creation writes nothing | SATISFIED | Tests SD-01, SD-02, SD-03 |
| 3 | Integrity: every member is verified through existing source-evidence mechanisms; missing, substituted, corrupted, malformed, duplicated or foreign membership fails closed; malformed stored records fail closed with a bounded reason and are validated in their original stored form | SATISFIED | Tests SD-04, SD-05, SD-07, SD-08 |
| 4 | Persistence: a SQLite close and reopen reconstructs the exact persisted membership and identity from durable evidence | SATISFIED | Tests SD-02, SD-06, SD-08, SD-09 on the SQLite ledger |
| 5 | Authority: no Task, Snapshot, Worker, attempt, review, release, approval, interpreted observation, model, provider or network operation, or downstream authority is created | SATISFIED | Tests SD-10, SD-11; ADR-018, "Security and authority boundary" |
| 6 | Regression: existing behavior stays green and frozen except for the approved additive work | SATISFIED | The 428 earlier tests pass unchanged; no existing file changed in Sprint 1 except one added row in docs/project-status.md |
| 7 | Closeout: formal acceptance by owner merge after independent review | PENDING — satisfied only by the owner's merge of this closeout record after independent review. | This file. See section 1 |

All engineering conditions, 1 to 6, are satisfied. Condition 7 is pending the owner's merge. No Sprint 2 is justified by this gate.

## 6. What was built

Sprint 1 changed exactly five paths.

New:
- docs/decisions/source-dataset-sprint-1-adrs.md (ADR-018)
- ripley/datasets.py
- tests/test_source_dataset.py
- docs/source-datasets.md

Modified:
- docs/project-status.md (one added row)

ripley/core.py, ripley/storage.py and ripley/capture.py are byte-identical to the baseline. No provider, dispatch, reader, release, grounding, semantic-review, envelope or CI file changed, and no existing test or earlier ADR changed.

What the module does, in short: `create_source_dataset` records one membership of 1 to 16 capture references after verifying every member, all-or-nothing, and returns the existing record on a repeat; `verify_source_dataset` is read-only and rebuilds and checks one source dataset from ledger records and stored bytes. The contract, reasons and precedence are in docs/source-datasets.md and ADR-018.

A verified Source Dataset is an integrity result, not a trust, quality, approval, interpretation, availability-time, consent, or fitness-for-use result.

## 7. Evidence identities

| Item | Value |
|---|---|
| Baseline main | a7e1598a9eca3bfc151d9a9ff26bf5937f192f67 |
| Sprint 1 implementation PR | #53 |
| Sprint 1 commit 1 (ADR-018 only) | c9c7a5e8e8324c6f05819b71dc55b721cb34c112 |
| Sprint 1 reviewed head | 71b2f592b44fed03c02e5c9570e67b40dc099000 |
| Sprint 1 merged main | 8a3c331df61067e0338809f298d2a882ba53993d |
| ADR-018 file | 18,822 bytes; SHA-256 6fe2d9ccdf11a8ccd1073b3ccddad944a75b9e6dd1e72c6e09c33d104c5b8c49 |
| ripley/datasets.py SHA-256 | 43a17b412c9a4b3ddad40c7d2ab1be0e09c49cf948def974da41c25cf294c13f |
| tests/test_source_dataset.py SHA-256 | 9f40f092d3cb8270dd04140d4c6651601f71ebce33c72636405208adde69296e |
| Sprint 1 tests | 22 new (11 on each of two ledgers); 450 in the full suite |
| Reconciled planning artifact | ripley-source-dataset-provenance-sprint-1-planning-r1.md; 46,354 bytes; SHA-256 527ac0ba561951bfca53cb63331962ed85528811d6a3b7ace1ac76773ffc8f51 |
| Released implementation assignment | ripley-source-dataset-sprint-1-implementation-assignment-released.md; 66,330 bytes; SHA-256 2dc85d7c1939080742b26bc505fc4ce665993fd958918eee845628a3eaf91a84 |

## 8. Sprint 1 acceptance evidence

Evidence is grouped by who established it.

Independently reproduced by Claude, on the published head 71b2f59 before the merge:
- Lineage: two commits; commit 1 changes only the ADR file; the head's parent is commit 1 and commit 1's parent is the baseline a7e1598.
- Scope: five paths, four new and one modified. The other 81 baseline files were byte-identical. The literal command git diff --check exited 0 with no output.
- The published ADR-018 differs from the reviewed draft only by the prescribed status paragraph.
- Linux, Python 3.13 with anthropic 2.9.0, in a disposable copy with no proxy variables: focused source dataset tests 22 run, 0 failures, 0 errors, 0 skipped; full suite 450 run, 0 failures, 0 errors, 0 skipped. Commit 1 alone: 428 run, 0 skipped.
- The module was read against the released assignment and conformed on every listed point, including validation of the original stored member representation before any copy.
- Mutation checks: section 9, variance 1.

Independently reproduced by Claude, on merged main 8a3c331:
- The merge has the baseline and the reviewed head as its two parents, and its tree is identical to the reviewed head's tree.
- Linux, same environment: focused 22 run, 0 failures, 0 errors, 0 skipped; full suite 450 run, 0 failures, 0 errors, 0 skipped.

Reported by the implementer (ChatGPT), as relayed by the chair:
- Hosted advisory check, pull request #53: commit 1 run 45479974673, 428 tests, 0 failures, 0 errors, 0 skips; final-head run 45481406650, job 138755273630, 450 tests, 0 failures, 0 errors, 0 skips, anthropic 2.9.0, checkout unchanged, tested merge commit 9c8d2628e9bdbd091bd2730773ee456cceb15f95.
- Claude observed on the public pages that the commit 1 run concluded with success for commit c9c7a5e and that the final-head job concluded with success for commit 71b2f59, and that the pull request's merge reference was 9c8d2628. The log lines and the counts need sign-in; Claude did not observe them. Claude's own runs are the independent figures.

Reported by the owner (Windows gate; Claude did not observe the terminal output):
- Focused source dataset tests: 22 run, 0 failures, 0 errors, 0 skips.
- Full suite: 450 run, 0 failures, 0 errors, 4 expected skips.

How the phase's required evidence is covered by tests in tests/test_source_dataset.py:
- Record and identity: SD-01. Order independence and repeat creation: SD-02. Membership is not content identity: SD-03.
- Call and member refusals: SD-04. Member verification, all-or-nothing creation and bounded capture-verification failure: SD-05.
- Reconstruction after reopen, read-only verification and the exact notice: SD-06. Later damage and repeat re-verification: SD-07.
- Malformed stored records and strict ambiguity: SD-08. Interrupted creation: SD-09.
- No prohibited operation on the tested paths, no unauthorized record kind, source and public-name restrictions: SD-10. A Snapshot is not a dataset identity: SD-11.

No provider call was made in this phase.

## 9. Owner-approved variances and the review sequence

Variance 1 — mutation specification (SM19).
- Claude applied the thirty assigned mutations, SM01 to SM30, one at a time to the published code and ran each ledger's test class separately.
- Result against the matrix as originally written: 29 of 30 detected on the in-memory ledger and 29 of 30 on SQLite. The original SM19 survived on both.
- Cause: the released assignment required an explicit check, at the start of verification, that the stored record data is a mapping, and it also assumed that record data which is not a mapping would reach the later malformed-record guard. With the required check in place, nothing representable in the supported ledgers reaches that guard's other exception types, so narrowing the guard alone changes no behavior. Claude ran the mutated module against 12,000 generated records on the two ledgers and no exception escaped.
- This was a defect in the mutation specification, written by Claude. It was not a demonstrated defect in the production code.
- Owner-approved revised SM19: remove the explicit stored-record mapping check and narrow the malformed-record guard together, so that supported malformed record data can escape instead of returning dataset_malformed. Revised SM19 was detected on the in-memory ledger and on SQLite.
- Final owner-approved disposition: 30 of 30 mutations detected on both ledgers. The production code was not changed. The original SM19 did not pass, and this record does not say that it did.

Variance 2 — controlled Linux execution.
- The implementer could not run the required local Linux gates before publication, because the implementation environment had no executable repository checkout.
- The owner approved a controlled procedural variance: the second commit could be published to the existing Draft pull request, the hosted check on the final head became the first mandatory executable Linux gate, and Claude's independent Linux execution remained mandatory.
- The hosted final-head check passed. Claude then independently reproduced 22 of 22 focused tests and 450 of 450 in the full suite with zero Linux skips.
- The variance changed the timing of the evidence only. It did not waive the evidence requirement.

The independent-review sequence, recorded plainly.
- Claude's written independent-review verdict on the published head was FAIL — CORRECTION REQUIRED, on the original SM19 only, with no other blocking finding.
- In the same review Claude stated that redefining SM19 as recommended would make the disposition PASS WITH NONBLOCKING NOTES with no further review work.
- The owner selected and approved that option before the merge. The condition Claude had stated was therefore met before the owner merged PR #53.
- No separate PASS message was issued between the owner's decision and the merge, and this record does not claim one.

## 10. Accepted limits

These are accepted limits, not unresolved implementation defects.

- A source dataset has no consumer. No Task accepts one.
- At most 16 members under contract version 1 in Sprint 1. This is not a permanent platform limit.
- Uniqueness of one record per membership holds for sequential single-writer use only. It is not a storage-level concurrent guarantee.
- Ambiguity can be induced: any second record claiming the same membership hash, even a malformed one, makes the dataset ambiguous. It fails closed and requires manual inspection. It does not disprove the valid record.
- No trustworthy arbitrary "as of T" claim. The ledger's record time is wall-clock time that the record content hash does not cover. Sprint 1 answers which exact source evidence, not as of when.
- No dataset name.
- No lineage.
- No retraction.

## 11. What this phase deliberately did not prove

- That any source is authentic or truthful, or that any collection is fit for any use.
- Anything about interpreted data, readings or approvals. Layer 2 was not started.
- Use of a source dataset by any Task, evaluation or model.
- Behavior under concurrent writers.
- Behavior with arbitrary hostile Python objects, failing custom mappings or invalid ledger implementations.
- Universal transactional behavior under every backend failure. Only an injected failure of the ledger append on the two supported ledgers was tested.
- Network or process unreachability under every conceivable environment.

## 12. Deferred work and classifications

None of these is a phase-gate requirement. None is authorized or scheduled. Layer 2 is not automatically authorized by the closure of this phase.

| Item | Classification |
|---|---|
| Layer 2, the interpreted dataset | DEFERRED CAPABILITY; requires its own owner decision and ADR |
| A consumer of a source dataset, including a Task that accepts one | DEFERRED CAPABILITY; requires its own decision |
| A member limit above 16 | DEFERRED CAPABILITY; tied to the first consumer |
| Storage-level uniqueness for concurrent writers | DEFERRED CAPABILITY; requires a storage change |
| Dataset names, version lineage and predecessor references | DEFERRED CAPABILITY; a later contract version |
| Retraction and correction semantics | DEFERRED CAPABILITY |
| Any time meaning, including "as of T" | DEFERRED CAPABILITY; the ledger cannot support it today |
| A consumer of approved readings, and authenticated identities | FUTURE GOVERNANCE DECISION; unchanged from the Governed Reader Path Phase |
| Keeping Source Dataset reference validation aligned with the ADR-012 reference contract | STANDING RULE; any change to that contract requires a coordinated review |
| Malformed hand-added records raising KeyError or TypeError in the reader owner decision | KNOWN BOUNDED ITEM from the Governed Reader Path Phase; unchanged; not touched by this phase |

## 13. FI-001, kept separate

FI-001 is unrelated to this phase and to this closeout. Its state is recorded here only so that it is not lost.

- Anthropic Support: response received on 2026-11-24. Support could not retrieve the error text or confirm the cause.
- Historical cause of the HTTP 400: UNCONFIRMED.
- Historical schema defect: PROVEN against the provider's documented rules.
- Repair: verified offline; untested live.
- Dispatch #3: PAUSED and UNAUTHORIZED. Live replay is not authorized.

## 14. Schedule and retrospective

Schedule (Central Time). Sprint 1 target: Wednesday, December 2, 2026; reauthorization boundary Friday, December 4, 2026. Phase target: Friday, December 4, 2026; reauthorization boundary Tuesday, December 8, 2026. Planning, feasibility review, ADR acceptance, implementation, independent review, the Windows gate and the merge all took place on Tuesday, November 24, 2026. No reauthorization was needed. No work was added to fill time.

What worked:
- The first question asked was whether a new record was needed at all. The prototype compared a Capture receipt, a Snapshot and a derived view before any record was proposed.
- The feasibility review found a real defect in the prototype before release: a stored member written as a sequence of pairs was normalised into a mapping and could be reported as verified. It was corrected in one round.
- The buildability review removed wording that claimed more than the design supports, including an unbounded statement that verification never raises.
- ADR-018 was published byte-identical to the accepted text.
- The implementer stopped when the hash-verified assignment still read as a draft after the owner's GO, and waited for a released copy.
- Malformed stored records were tested with missing keys, wrong types and wrong representations from the first day, applying the lesson of the previous phase.

What caused friction:
- The assignment contained a mutation that the specified code made undetectable (section 9, variance 1). It was found only at independent review.
- The implementer had no executable checkout, so local Linux evidence could not precede publication (section 9, variance 2).
- Claude reported that a viewer displayed parts of correct files as blank, contributing to two artifact revisions; byte-level checks indicated the source files contained the expected text.
- The planning artifact carried the private prototype's source in an appendix, and the published module follows it closely. The independent review therefore tested code largely derived from the reviewer's own prototype, which is a weaker separation than intended.

One improvement to carry forward:
Before releasing a mutation matrix, check each mutation against the code path the same assignment prescribes, and confirm that at least one prescribed test input reaches the weakened rule. Keep prototype source out of any artifact the implementer receives.

## 15. What follows

By the owner's merge of this record, Sprint 1 is closed and the Source Dataset Provenance Phase is accepted and closed. That merge authorizes nothing further. No Sprint 2 exists. No next phase is chosen. Layer 2 is deferred and is not automatically next. Every capability in section 12 requires its own decision.
