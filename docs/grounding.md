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
