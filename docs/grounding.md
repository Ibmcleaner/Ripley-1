# Proposal grounding (ADR-013)

A proposal is untrusted UTF-8 JSON data about Capture evidence already attached
to an existing Snapshot. Sprint 1 supports fixture and human producers. It does
not run a source reader, use a model, or invoke the Core Task and Worker flow.

## Citation rule

Each citation contains `capture_id`, `start`, `end` and `quote`. Its Capture must
already be referenced by the named Snapshot. The trusted grounding module reads
each referenced object once, checks the receipt hash, size and content SHA-256,
and evaluates citations against those same in-memory bytes. Callers supply
neither source bytes nor an object path.

Offsets are zero-based bytes with start inclusive and end exclusive: `[start, end)`.
For the exact UTF-8 source `Café\n`, `é` occupies bytes 3 and 4. Its citation is
`start=3`, `end=5`, `quote="é"`. Character offsets are not an alternative.
Case, whitespace, Unicode form, line endings and BOM bytes are not normalized.

The proposal limit is 65,536 bytes; the artifact limit is 1,048,576 bytes. A
proposal has 1 to 64 observations and at most 8 citations per observation.
Quotes and cited ranges are each limited to 4,096 UTF-8 bytes.

## Results

Evidence is all-or-nothing. If any Snapshot reference fails, the outcome is
`blocked_evidence`, the review state is `not_reviewable`, and observations are
not evaluated. Otherwise the outcome is `evaluated` and the review state is
`awaiting_semantic_review`.

| Evidence reason | Meaning |
|---|---|
| `verified` | Receipt identity, stored size, digest and UTF-8 checks passed |
| `receipt_missing` | Referenced receipt does not exist |
| `receipt_wrong_kind` | Referenced record is not a Capture |
| `receipt_hash_mismatch` | Receipt hash differs from the Snapshot reference |
| `artifact_too_large` | Receipt size exceeds the limit; object is not read |
| `artifact_unavailable` | Store path cannot be resolved or object cannot be read |
| `artifact_mismatched` | Read bytes differ in size or SHA-256 from the receipt |
| `artifact_not_utf8` | Verified bytes do not decode as strict UTF-8 |

Citations receive the first applicable result in this order:
`capture_not_on_snapshot`, `out_of_bounds`, `splits_character`, `quote_mismatch`,
`matched`.

| Observation verdict | Reason | Meaning |
|---|---|---|
| `grounded` | `all_citations_matched` | At least one citation; every citation matched |
| `not_grounded` | `citation_missing` | An asserted or uncertain observation has no citations |
| `not_grounded` | `citation_failed` | At least one citation failed |
| `no_evidence_claimed` | `declared_not_found` | Status is `not_found`, value is null, citations empty |

An `uncertain` observation follows the same citation rule as an `asserted` one.
Status and note remain visible to the human reviewer. Fields with multiple
observations are listed without choosing between them. A `not_grounded`
observation is not eligible for semantic review.

Before admission, failures produce only `grounding_rejection` with the received
bytes' SHA-256, size and reason. Reasons are `proposal_too_large`,
`proposal_not_utf8`, `proposal_not_json`, `proposal_schema_invalid`,
`duplicate_observation_id`, and `snapshot_unavailable`. Rejected content is not
stored. An admitted proposal produces a `proposal` record followed by a
`grounding_validation` record, including when its evidence is blocked.

## Calling the functions

The caller already has `ledger`, the configured `store_dir`, an existing
`snapshot`, and its referenced `capture` receipt. This example assumes that the
captured source is exactly the six UTF-8 bytes of `Café\n`:

```python
import json
from ripley.grounding import ground_proposal, review_package

proposal = {
    'proposal_version': 1,
    'snapshot_id': snapshot.id,
    'producer': {'kind': 'human', 'identity': 'operator.example'},
    'observations': [{
        'observation_id': 'obs-1',
        'field': 'quoted_text',
        'status': 'asserted',
        'value': 'é',
        'citations': [{
            'capture_id': capture.id,
            'start': 3,
            'end': 5,
            'quote': 'é',
        }],
    }],
}
received = json.dumps(proposal, ensure_ascii=False).encode('utf-8')
record = ground_proposal(ledger, store_dir, received)
if record.kind == 'grounding_validation':
    package = review_package(ledger, record.id)
    print(json.dumps(package, ensure_ascii=False))
```

`ground_proposal` requires exactly `bytes`; other direct-call types raise
`GroundingError('invalid_call')` without a write. Ledger write failures raise
`GroundingError('ledger_write_failed')`.

`review_package` reads ledger records only and writes nothing. It remains usable
after Capture storage is unavailable. It raises `validation_unavailable` for an
unknown/wrong-kind validation and `proposal_unavailable` for a missing,
wrong-kind or hash-mismatched proposal. It never records a human review decision.
Ordinary source text such as "accepted" or "approved" is preserved as data.

## What grounding does not prove

Grounded is not semantically accepted. Grounding proves only that the proposal points at bytes that exist in the relied-upon captured source under these rules. It does not prove that the interpretation is correct, that the source is authentic, that the source is truthful, that the proposed fact is valid, or that anything is approved. No record or function under this ADR marks an observation as semantically accepted or approved.

## Known limitations

Only UTF-8 plain text is supported. `value` is not checked against `quote`.
There is no semantic-review decision record or enforcement of reviewer identity
yet. This is direct use, outside the Core Task and Worker flow. There is no
model, agent, acquisition or execution authority. The normative contract is
[ADR-013](decisions/source-interpretation-sprint-1-adrs.md).

## Sprint 1 acceptance evidence

| Evidence classification | Recorded evidence |
|---|---|
| Publication | Publication: implementation PR #43. Commit 1: 2b711e039a5d82362753ab88c1ddbd406b373b9d (ADR-013 only). Commit 2 / reviewed head: bdcfb0382e8a373df6e539fe821f7295f4e5e352. Merged to main as 4e10661c1bbd636695a718eb3c2bdadb78ebda58. The merged tree is identical to the reviewed head. |
| Independent verification — Claude | Scope: five files, four new and one bounded modification. The other 62 baseline files were byte-identical (verified independently by Claude). |
| Owner approval and independent verification — Claude | ADR-013: approved by the owner, dated 2026-11-22. Published file SHA-256 8166d06cdde52e3901db2520302ab2877f001f730316a0bc2ca60b1d28cbf771, byte-identical to the approved text (verified independently by Claude). |
| Independent review — Claude | Independent review (Claude): APPROVED WITH NONBLOCKING NOTES FOR OWNER WINDOWS GATE. |
| Independent Linux execution — Claude | Independent Linux run (Claude), Python 3.13 with anthropic 2.9.0, on tested commit aa0e700d4944103572081984aa3c3b7a05a05e67, in a disposable copy with no proxy variables: focused grounding tests 54 run, 54 passed, 0 skipped; full suite 285 run, 0 failures, 0 errors, 0 skipped. |
| Independent mutation checks — Claude | Independent mutation checks (Claude): the 29 assigned defects M01 to M29 were applied one at a time to the published ripley/grounding.py. Each made at least one assigned test fail. The unknown-field defect was applied at all four schema levels and each was detected. |
| Independent supplemental probes — Claude | Independent supplemental probes (Claude), outside the assigned tests: a byte-order mark is treated as ordinary bytes; composed and decomposed Unicode are not treated as equal; doubled whitespace is not normalized; source and proposal text containing instruction-like content was stored as data; task state did not change and no semantic-acceptance state was produced. |
| Independent provenance reconstruction — Claude | Independent end-to-end trace (Claude): from the SQLite file alone, the chain validation, proposal, Snapshot, capture receipt and stored bytes was reconstructed and every verdict was recomputed from the raw bytes. Fourteen checks passed. |
| Implementer-reported — ChatGPT | Implementer-reported local results (ChatGPT), Python 3.12.14 with anthropic 2.9.0, proxy variables unset: focused 54 run, 54 passed, 0 skipped; full suite 285 run, 285 passed, 0 skipped. Implementer-reported mutation probes: 29 of 29 detected. |
| Owner-reported Windows gate | Owner Windows gate, as reported by the owner, on head bdcfb0382e8a373df6e539fe821f7295f4e5e352: focused 54 run, 54 passed, 0 skipped; full suite 285 run, 4 expected existing Phase 5 skips, 0 failures, 0 errors. |
| Hosted page observed by Claude; logs implementer-reported | Hosted run for commit 1 (ID 44952108084): the public run page was read by Claude and shows Success, pull request #43, commit 2b711e0, event pull_request, one job, no artifacts. Log lines reported by the implementer: tested commit 563d7fd4ecb5b6bc8f7ab0a50b50305e2b13f569; 231 run, 0 skipped; PASSED; checkout unchanged. Claude did not observe the logs. |
| Hosted page observed by Claude; logs implementer-reported | Hosted run for commit 2 (ID 44952322275): the public run page was read by Claude and shows Success, pull request #43, commit bdcfb03, event pull_request, one job, no artifacts. Log lines reported by the implementer: tested commit aa0e700d4944103572081984aa3c3b7a05a05e67; 285 run, 0 skipped; PASSED; checkout unchanged. Claude did not observe the logs; the 285 figure agrees with Claude's own run. |
| Implementation boundary | No provider call was made. No pre-existing runtime, test, CI, provider or ADR file was changed. |

### Nonblocking review notes

- The deeply nested JSON case in GV-13 was a Windows watch item. The owner's Windows gate passed.
- A hand-forged capture record that lacks expected fields could raise an error instead of producing a reason code. This is not reachable through the current capture_file writer.
- _read_object checks that the path is a regular file before opening it. That is a status check, not a second content read.

None of these is scheduled work.

## Sprint 1 retrospective

**What worked**

- The trust boundary was built before any reader exists, so no later component is trusted because it produced the output.
- The specification was checked against a private prototype before release. That run found two defects the first test list could not catch (line-ending normalization and character offsets), and the tests were added before the assignment went out.
- The feasibility review improved the design within the two-round limit: quote length measured in bytes, a one-read test that does not depend on how a file is opened, and removal of a test that forbade the word "accepted" in ordinary text.
- ADR-013 was published byte-identical to the approved text.
- The first published commit passed independent review with no correction. All 29 assigned mutations were detected.
- No pre-existing runtime or test file changed and no existing test was touched. The only pre-existing file modified was docs/project-status.md, by its one assigned row.

**What caused friction**

- The assignment went through several versions across the two architecture rounds, and a summary of the final version was not enough to implement from. A complete self-contained artifact had to be assembled before the handoff.
- The first draft carried three weaknesses that the review caught: a length limit that mixed characters and bytes, an id format tied to how the ledger generates ids, and a test hooked to an implementation detail.

**Transport and communication lesson**
The final assignment was delivered as one self-contained file with a byte count and SHA-256 (37,570 bytes, e941adb053d94dc72fa9fdeec09f5ba7d45d13b6aa46aeaadbe06663c6f7a821). An implementation handoff should be one complete artifact that needs no earlier message, with a hash the receiver can check.

**Schedule outcome**
Target: Monday, November 23, 2026, 6:00 PM Central. Reauthorization deadline: Tuesday, November 24, 2026, 6:00 PM Central. Implementation was reviewed, verified on Windows and merged on Saturday, November 21, 2026, ahead of the target. No reauthorization was needed. No work was added to fill the remaining time.

**One improvement to carry forward**
Issue every implementation assignment as a single self-contained, hash-verified file from the first release, not after a completeness request.
