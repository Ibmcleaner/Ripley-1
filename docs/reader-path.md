# Governed reader path — Sprint 1

ADR-016 adds a reader-only Core entry point. A first-party deterministic Worker reads verified UTF-8 plain text and reports matching `Field: value` lines, or `not_found`. It uses no model, provider, network or tool. It makes no semantic judgment.

## Order and authority

`run_reader` validates its arguments, canonicalizes the Capture references and checks for an active duplicate. It creates a Snapshot and Task, starts the Task, records Capture verification, and reads the Snapshot's stored objects through the trusted grounding helper. Each delivered object must match its receipt's size and SHA-256 and decode as strict UTF-8. Only the Snapshot's referenced evidence is delivered.

Core computes the input size from the artifact bytes plus canonical inputs and opens one ADR-015 attempt with zero required budget. It records an execution attempt and request, launches the isolated reader once, records the result and closes the envelope from the observed outcome. Core admits only an output containing an observations list, supplies the trusted Worker producer identity and Snapshot identity, and grounds the resulting proposal. The public grounding function still refuses the `worker` producer kind.

The reader receives verified text and evidence identities, not a store path, file path, ledger handle, credential or provider authority. Full delivered text is omitted from the recorded execution request. Quoted spans may be persisted in admitted proposals. The process is trusted first-party code; this is process isolation, not hostile-code sandboxing.

If grounding leaves an eligible observation, Core records a binding and moves the Task to `awaiting_semantic_review`. That durable state has no exit in Sprint 1. A separate human semantic review may be recorded under ADR-014; it changes no Task state and is not approval. Core creates no validation, review, Evidence, approval, correction request or recovery authorization on this path.

## Calling the reader

```python
from ripley.capture import capture_file
from ripley.core import Ledger, Ripley

ledger = Ledger()
receipt = capture_file(
    ledger, store_dir, source_path, approved_root=approved_root,
    source_id='synthetic-inventory', source_location='local:fixture',
    supplied_by='Fixture.Author', content_type='text/plain; charset=utf-8')
ripley = Ripley(ledger, capture_store=store_dir)
run = ripley.run_reader(['Units', 'Place'], [
    {'capture_id': receipt.id, 'receipt_hash': receipt.content_hash}])
chain = ripley.reader_chain(run['reader_proposal'].id)
```

Fields are 1–32 distinct ASCII strings, 1–64 characters each, beginning with a letter and otherwise containing letters, digits, spaces, underscores or hyphens. References use ADR-012's canonical order and reject duplicate Capture IDs.

## Reader-only identity and packet

The existing task-key formula is unchanged. For reader Tasks only, inputs contain `fields` and `sources`, where `sources` is the canonical Capture references. Those same references also live on the Snapshot. Different receipts produce different reader task keys, even for identical bytes. Active repeats of the same fields and references are duplicates; reference order does not matter. ADR-016 explicitly excepts only this path from ADR-012 decisions 3, 11 and 12. Other Tasks and provider Workers retain their existing packet, identity and Capture rules.

The reader packet has exactly ten keys:

| Key | Value |
|---|---|
| envelope_version | Existing Core envelope version |
| attempt_id | Execution attempt record ID |
| task_id | Task record ID |
| task_type | `read` |
| domain_id | `source-reading` |
| domain_version | `1` |
| worker_identity | Trusted reader Worker identity |
| inputs | `fields` and canonical `sources` |
| deadline_at | Absolute envelope deadline, ISO 8601 UTC |
| evidence | One item per Snapshot Capture reference, in canonical order |

Each evidence item has exactly `capture_id`, `receipt_hash`, `content_sha256`, `size_bytes` and `text`. The host checks the text's UTF-8 size and hash before passing it to the Worker. The recorded packet omits `text` from each evidence item. Every other Worker packet retains its existing nine keys, without `evidence` or Capture references in inputs.

## Single attempt and absolute deadline

ADR-015 admits at most one attempt per Snapshot. Input measurement includes all delivered bytes and canonical inputs; output is measured after the process ends. The deadline is the reservation's absolute instant. Immediately before launch Core subtracts its current time and gives only the remaining allowance to ADR-009 isolation. Preparation never resets the allowance. At zero or negative allowance the process is not launched: Core closes the consumed attempt as failed, records `timeout` with `deadline_expired_before_launch` and blocks the Task.

Failed, uncertain and interrupted attempts stay consumed. `recover()` refuses reader Tasks and writes no recovery authorization. A stranded running Task is blocked on restart. Continuing from an already recorded result is not implemented. A person may resubmit after a block: the new Task links to the prior Task, has a new Snapshot and its own single attempt. This is allowed because this reader is local and free; it must be decided again before a paid reader.

## Failure stages

There is no fallback or retry. A failed boundary blocks the Task with an execution failure:

| Stage | Boundary |
|---|---|
| capture_verification | Snapshot Capture evidence did not verify |
| evidence_delivery | Trusted read, identity, size, hash or UTF-8 delivery failed |
| envelope_refused | The envelope did not admit an attempt |
| timeout | Deadline expired before launch or execution exceeded it |
| worker_failure | The Worker raised an error |
| host_failure | Crash, unusable host response or host failure |
| envelope_violation | Attempt close was not within limits |
| reader_output_invalid | Output was not exactly an observations list wrapper |
| proposal_rejected | Proposal failed admission |
| grounding_blocked | Admitted proposal evidence could not be verified |
| nothing_grounded | No observation was eligible for semantic review |

## Binding and read-only chain check

The `reader_proposal` binding has exactly sixteen keys: `task_id`, `attempt_id`, `result_id`, `result_hash`, `proposal_id`, `proposal_hash`, `proposal_sha256`, `grounding_validation_id`, `grounding_validation_hash`, `producer`, `reasoning_attempt_id`, `reasoning_attempt_hash`, `reasoning_close_id`, `reasoning_close_hash`, `snapshot_id`, `snapshot_hash`.

`reader_chain(binding_id)` returns exactly `outcome`, `reason` and `reader_proposal_id`. It checks the binding's shape, then the existence, kind and pinned hash of result, proposal, grounding validation, envelope attempt, close and Snapshot in that order, then their required cross-links. It writes nothing, raises nothing and does not reread artifact bytes. A verified result has reason `None`. Break reasons are `binding_unavailable`; each of `result`, `proposal`, `grounding_validation`, `reasoning_attempt`, `reasoning_close`, `snapshot` suffixed by `_missing`, `_wrong_kind` or `_hash_mismatch`; and `chain_link_mismatch`.

## Limits and non-claims

This Sprint proves a deterministic reader path only, for UTF-8 plain text. It provides no release from semantic review to approval and no continuation after interruption. Process output is measured after termination; the envelope does not cap bytes written before that measurement.

It does not prove that a model can run on this path, that a reader's reading is correct, that hostile code is contained, that output is bounded before measurement, that a reviewer is who a label says, or that anything is approved. It adds no provider access, model, network, tool, child or agent. Provider request, prompt, model, schema and dispatch remain unchanged.

## Sprint 1 acceptance evidence

Independent, owner-reported, implementer-reported and hosted evidence are kept separate.

**Publication**
- Implementation PR #47. Commit 1: 77ae5fdd4d23548e5553598251b2d10480c0fb81 (ADR-016 only). Commit 2 and reviewed head: abca2ef75eab59e2302459d0a396cd6f281f9488. Merged to main as 1374b2fc13b5c96da6c27d24bf85fe87bc49561c. The merged tree is identical to the reviewed head.
- ADR-016 was accepted by the owner on 2026-11-23, as Revision 1 of the assignment. The published file docs/decisions/reader-path-sprint-1-adrs.md has SHA-256 37ef4fcdf59583ac540ec7e557c7b3a905d58c95bd2f64d05fdb0b2c8d9920cf.
- The assignment was delivered as one self-contained file: ripley-governed-reader-path-sprint-1-final-r1.md, 67,363 bytes, SHA-256 3b97b7f2a8c058bacfdff394401afaf6a722d84d87a6d319e7f2fa8feacadad7.

**Independently reproduced by Claude, on the published head**
- Scope: nine files changed, four new and five modified. The other 70 baseline files were byte-identical, including all 12 existing files under tests/.
- The published ADR-016 text is byte-identical to the approved text (12,321 bytes).
- Linux, Python 3.13 with anthropic 2.9.0, in a disposable copy with no proxy variables: focused reader tests 45 run, 0 failures, 0 errors, 0 skipped; full suite 396 run, 0 failures, 0 errors, 0 skipped.
- Mutation checks: the 49 assigned defects RM01 to RM49 were applied one at a time to the published code. Each made at least one of its assigned tests fail. 49 of 49 detected.
- Review verdict: APPROVED WITH NONBLOCKING NOTES FOR OWNER WINDOWS GATE. No blocking defect.

**Owner Windows gate, as reported by the owner through the chair**
- Focused reader tests: 45 run, 0 failures, 0 errors, 0 skips.
- Full suite: 396 run, 4 expected existing Phase 5 skips, 0 failures, 0 errors.

**Implementer-reported (ChatGPT)**
- Local results, proxy variables unset, Python 3.12.14: focused 45 run, 0 failures, 0 errors, 0 skipped; full suite 396 run, 0 failures, 0 errors, 0 skipped.

**Hosted advisory check**
- Run 45261456966, commit 1 (77ae5fd), and run 45264262389, commit 2 (abca2ef): Claude read both public run pages. Each shows Success for pull request #47, one job, "Linux full suite (advisory)", and no artifacts.
- The job logs require sign-in and were not observed by Claude. Suite counts inside those logs are not independently confirmed here; Claude's own run of the same head is the independent figure.

No provider call was made. No existing test, CI, provider or earlier ADR file was changed.

## Sprint 1 acceptance criteria

All thirteen criteria are satisfied. Tests are in tests/test_reader_path.py; RM numbers are the independent mutation checks.

| Criterion | Evidence |
|---|---|
| A1. ADR-016 published byte-identical to the approved text | Byte comparison and SHA-256 by Claude |
| A2. A deterministic reader in the existing isolated subprocess receives the exact verified bytes of the Snapshot's captures and returns observations | RP-01, RP-02, RP-03, RP-06; RM05, RM06, RM31, RM34 |
| A3. Core sets the producer identity from the trusted Worker descriptor; a reader cannot | RP-04; RM01, RM02, RM17, RM18, RM19 |
| A4. Core reserves the envelope attempt before launch, uses the envelope deadline, and closes the attempt from the observed outcome | RP-01, RP-07, RP-10; RM07, RM20, RM21, RM22 |
| A5. Core grounds the proposal; a rejected, blocked or wholly ungrounded proposal blocks the task | RP-05, RP-13; RM12, RM13 |
| A6. A grounded reader task stops in awaiting_semantic_review, which survives restart and has no exit | RP-15, RP-17; RM15, RM16 |
| A7. A failing or hostile reader gives a bounded recorded outcome, one consumed attempt and no new authority | RP-08, RP-09, RP-10, RP-11, RP-13, RP-14; RM08, RM14, RM24 |
| A8. recover() refuses a reader task and writes nothing | RP-10, RP-16, RP-17; RM10, RM47 |
| A9. All 351 existing tests pass unmodified; no Linux skip | Existing test files byte-identical; 396 run, 0 skipped |
| A10. Every assigned mutation is detected | 49 of 49 |
| A11. Capture references and captured bytes reach a Worker only on the reader path, and a reader task's identity includes its capture references | RP-23; RM35, RM36, RM37 |
| A12. The binding pins every linked record by id and hash, and the read-only chain check reports any break | RP-01, RP-17, RP-22; RM29, RM38 to RM42 |
| A13. Only the time remaining before the absolute deadline is given to the process; an attempt that has expired before launch is not launched and stays consumed | RP-10; RM43 to RM49 |

**ADR-012 reader-only exception.** ADR-012 was not amended. ADR-016 decisions 5 to 7 make one exception, for a task of type `read` in the domain `source-reading` on the reader path only: the capture references are part of the inputs, the packet and the task key. Every other task and every provider packet was shown unchanged (RP-23).

**Sixteen-key binding.** The reader_proposal record has exactly sixteen keys and pins six records by id and content hash: result, proposal, grounding validation, envelope attempt, its close, and Snapshot (RP-01, RP-22).

**Chain check reasons: 20.** reader_chain can report exactly 20 break reasons: binding_unavailable; 18 formed from the six record names with _missing, _wrong_kind and _hash_mismatch; and chain_link_mismatch. The implementation assignment said 21. That was a counting error in the assignment, ruled nonblocking at review. Every named reason is implemented and tested. No code changed for it.

**Absolute deadline.** A 50-second preparation delay left exactly 70 seconds for the process; a 1-microsecond remainder still launched; a remainder of zero or less did not launch, closed the attempt as failed and left it consumed, including after a reopen (RP-10).

**Recovery and retry.** The reader is launched at most once. A second submission while a task is active is a duplicate. recover() raised and wrote nothing for a timed-out task, a crashed task, a task stranded by a restart and a task that expired before launch (RP-08, RP-10, RP-16, RP-17).

**Hostile and failing readers.** None of the following produced a binding or an approval record. Each of these was recorded as a block after the attempt was reserved, and left exactly one consumed attempt: an error, a crash, unusable output, a nonzero exit, a non-mapping output, a hang, an oversized output, a spoofed producer, a spoofed Snapshot identity, an extra authority field, ungrounded citations, a citation to a capture not on the Snapshot, and evidence that failed when grounding read it again. Evidence that was altered or was not UTF-8 when Core first read it was recorded as a block before any attempt was reserved: nothing was launched and no attempt was created or consumed. An instruction written as a value was stored as data and gained nothing (RP-04, RP-05, RP-09, RP-10, RP-11, RP-13, RP-14, RP-23).

**Nonblocking review notes.** None is scheduled work.
- The count correction above.
- A matching line longer than 4,096 bytes is reported by the line reader as not found. This is as specified.
- The existing recovery function refuses an attempt that expired before launch by two separate checks; the mutation for that case had to bypass both.

## Capability boundaries after Sprint 1

Deterministic reader only. No model. No provider. No network. No tool. No child. No delegation. No automatic retry. No Track B functionality. No approval bridge. A semantic review is not approval. awaiting_semantic_review has no exit.

## Phase exit gate after Sprint 1

| Condition | Position |
|---|---|
| 1. Reader contract accepted | SATISFIED (ADR-016) |
| 2. End-to-end deterministic reader path proven | SATISFIED |
| 3. Envelope governs the reader attempt | SATISFIED |
| 4. Hostile or failing deterministic reader contained | SATISFIED within the approved Sprint 1 scope |
| 5. Human gates preserved | PARTIALLY SATISFIED. A task reaches durable awaiting_semantic_review and an ADR-014 review can be recorded, but the governed release from semantic review to human Core approval does not exist |
| 6. Existing behavior preserved | SATISFIED |
| 7. Phase closeout accepted by owner merge | NOT YET APPLICABLE |

The phase remains active. This record does not define or authorize a Sprint 2.

## Sprint 1 retrospective

**What worked**
- The design was built as a private prototype before the assignment was released, so the test and mutation lists came from running code.
- The feasibility review caught three material objections before any implementation: capture references could not enter a reader packet while ADR-012 was called unchanged; the binding pinned the envelope attempt and its close by id only; and the process could have been given a full time allowance after preparation had already spent part of it. All three were correct.
- Architecture Correction Round 1 fixed all three. Round 2 was not used.
- ADR-016 was published byte-identical to the approved text. The first published head passed independent review with no correction, and all 49 mutations were detected.
- No existing test was touched.

**What caused friction**
- The three objections were gaps in the architecture draft, not in the implementation. Each would have been found earlier by reading the draft against the numbered decisions of the ADRs it claimed to leave unchanged.
- The assignment carried a wrong count (21 chain reasons where there are 20), left over from a reason removed during the correction round.

**Schedule outcome**
Target: Wednesday, November 25, 2026, 6:00 PM Central. Reauthorization deadline: Monday, November 30, 2026, 6:00 PM Central. Implementation was reviewed, verified on Windows and merged on Monday, November 23, 2026, ahead of the target. No reauthorization was needed. No work was added to fill the remaining time.

**One improvement to carry forward**
Before an architecture draft is released, check every statement that an earlier ADR is unchanged against that ADR's numbered decisions, and recount every stated total after any correction round.
