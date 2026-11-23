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
