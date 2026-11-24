# Source datasets — Sprint 1 (ADR-018)

A Source Dataset is an immutable, Task-independent collection of exact Capture receipts. It states only that those captured observations belong together. It does not interpret evidence, approve a reading, or provide a consumer.

**A verified Source Dataset is an integrity result, not a trust, quality, approval, interpretation, availability-time, consent, or fitness-for-use result.**

## Local example

The following uses synthetic local text and a temporary directory, with no external service:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from ripley.core import Ledger
from ripley.capture import capture_file
from ripley.datasets import create_source_dataset, verify_source_dataset

with TemporaryDirectory() as temp:
    base = Path(temp)
    approved = base / 'approved'
    approved.mkdir()
    store = base / 'store'
    source = approved / 'fixture.txt'
    source.write_text('Crates: 12\n', encoding='utf-8')
    ledger = Ledger()
    receipt = capture_file(
        ledger, store, source, approved_root=approved,
        source_id='fixture', source_location='fixture:local',
        supplied_by='operator', content_type='text/plain; charset=utf-8')
    references = [{'capture_id': receipt.id, 'receipt_hash': receipt.content_hash}]
    dataset = create_source_dataset(ledger, store, references)
    result = verify_source_dataset(ledger, store, dataset.id)
    assert result['outcome'] == 'verified'
```

This example creates a source membership only. Nothing consumes or acts on it. For durable restart evidence, use the existing SQLiteLedger and reopen the ledger file.

## Contract and identity

The new record kind is `source_dataset`, using exactly three data keys:

```python
{
    'contract_version': 1,
    'membership_sha256': '<64 lowercase hex>',
    'members': [
        {'capture_id': '<canonical lowercase UUID>',
         'receipt_hash': '<64 lowercase hex>'},
    ],
}
```

There are 1–16 members, each with precisely the two indicated keys. They are canonically ordered by `capture_id`; duplicates and malformed references are refused. The canonical persisted JSON members representation is an array. A supported ledger may expose that array as a list or frozen tuple; each member in its original exposed representation must be a mapping, not a list of pairs.

Membership identity is:
`sha256(canonical_json({'contract_version': 1, 'members': canonical_members}))`.

`membership_sha256` is the source dataset identity, distinct from the ledger record ID and the record content hash. Separate Capture receipts for byte-identical objects are distinct source observations and yield different dataset membership identities. The source dataset contains only references: it copies neither source bytes nor Capture metadata.

## Creation

`create_source_dataset(ledger, store_dir, references)` returns the new record or the existing record for the same membership under supported sequential, single-writer use. It verifies every member again on every call, including a repeat, before returning. Its thirteen `DatasetError.reason` values are:

| Reason | Meaning |
|---|---|
| `invalid_call` | Reference collection is not a list or tuple |
| `empty_membership` | No member was supplied |
| `too_many_members` | More than 16 references |
| `malformed_member` | A reference has wrong shape, type or canonical form |
| `duplicate_member` | One Capture ID appears more than once |
| `receipt_missing` | Referenced receipt is absent, including a foreign-ledger ID |
| `receipt_wrong_kind` | Referenced record is not a Capture receipt |
| `receipt_hash_mismatch` | Receipt record hash differs from the pinned reference |
| `artifact_mismatched` | Stored object bytes or size differ from Capture |
| `artifact_unavailable` | Stored bytes cannot be found or verified |
| `verification_error` | Capture verification raises or returns an unknown status |
| `dataset_ambiguous` | Conflicting same-membership records exist |
| `ledger_write_failed` | The dataset append operation raised |

Creation reason precedence: check the call and input references in supplied order (invalid, empty, limit, malformed, duplicate), verify members in canonical order (missing, wrong kind, receipt hash, stored bytes), compute the identity, inspect competing records, then append. The first failure is reported. Members are all-or-nothing; a failed verification writes no dataset.

Sequential single-writer creation gives one record per membership per ledger. This is **not** an atomic concurrent uniqueness guarantee. Competing records, even malformed records claiming the membership hash, cause `dataset_ambiguous` and require manual inspection; the result does not disprove the original source evidence or mean a particular record should win. A malformed existing comparison likewise fails as ambiguous without writing.

The write-failure claim is bounded to injected ledger append failures tested on the supported ledgers: the call reports `ledger_write_failed` and no dataset record is present after that tested failure. No universal transaction guarantee is claimed.

## Read-only verification

`verify_source_dataset(ledger, store_dir, dataset_id)` returns a mapping with exactly `notice`, `outcome`, `reason`, `dataset_id`, `membership_sha256`, and `members`. It writes nothing and reconstructs its result from ledger records and stored object bytes on every call.

Dataset-level reasons:

| Reason | Meaning |
|---|---|
| `dataset_unavailable` | Target record is missing or has the wrong kind |
| `dataset_malformed` | Target record has invalid shape, types, order or member representation |
| `contract_unsupported` | Target uses an unknown integer contract version |
| `membership_hash_mismatch` | Recomputed membership identity differs |
| `dataset_ambiguous` | More than one source dataset claims the identity |
| `member_failed` | At least one stored member did not verify |

Member reasons:

| Reason | Meaning |
|---|---|
| `verified` | Receipt and stored object match |
| `receipt_missing` | Receipt is absent |
| `receipt_wrong_kind` | Referenced record is not Capture |
| `receipt_hash_mismatch` | Receipt record hash changed or differs |
| `artifact_mismatched` | Stored bytes or size do not match |
| `artifact_unavailable` | Stored bytes are unavailable |
| `verification_error` | Unexpected Capture verification error or status |

Verification precedence: locate the target; validate the record's top-level structure; check the integer contract version; validate original members, canonical order and hash field; recompute the identity; check strict ambiguity; finally verify every member. Malformed target takes precedence over ambiguity, unsupported version precedes interpreting its members, and competing records take precedence over member-byte verification. After members are reached, all member reasons are returned even if one fails.

Verification returns a bounded failure without raising for malformed data and IDs representable through the supported ledgers' JSON-compatible record data. Arbitrary hostile Python objects, failing custom Mapping methods, and invalid ledger implementations are outside that guarantee; no sandbox exists. `dataset_id` is echoed exactly as supplied. If an arbitrary Python object was supplied, the result need not be JSON-serialisable.

## Explicit limits

There is no dataset time field, no admission time, no arbitrary historical "as of T", and no claim that the source was available at a particular decision instant. The unhashed ledger wall-clock time is not used for dataset identity, ordering or decisions. Capture's acquired/declared timestamps remain at the Capture layer and do not prove real-world availability. This sprint answers **which exact source evidence**, not **as of when**.

There is no dataset name, predecessor, version series, correction lineage or retraction. Changed membership yields a different dataset identity. Corrected source bytes require a new Capture receipt; prior source datasets stay unchanged. The 16-member limit belongs to Sprint 1 only.

No Task yet accepts a source dataset; there is no consumer, model, agent, provider, network acquisition, tool execution, review, release or approval in this API. The code creates no Task, Snapshot, Worker or approval records. Its verification is not a declaration of trust, source authenticity, consent, semantic correctness or permission to train a model.

The local reference validator mirrors ADR-012. **Any future change to the accepted Capture-reference contract requires a coordinated review of Source Dataset validation.**

Windows acceptance results, and any later independent review results, belong in the separate sprint closeout; none are claimed here.

## Using a source dataset with the governed reader

No Task accepts a source dataset. A caller can still run the existing governed reader over a source dataset's evidence, using only existing operations:

1. Call `verify_source_dataset(ledger, store_dir, dataset_id)`. If the outcome is not `verified`, stop and start nothing.
2. Take each member's `capture_id` and `receipt_hash` from the result.
3. Pass those references to the existing reader entry point, `Ripley.run_reader(fields, capture_references)`.

The reader stores the same references, in the same canonical order, on the run's Snapshot. After a restart, the Snapshot's capture references can be compared with the source dataset's members, and the membership identity can be recomputed from the Snapshot's references with the formula above.

What the persisted records then establish:

| Claim | Established? |
|---|---|
| A successful governed reader run consumed exactly these Capture references | Yes, when supported by its Snapshot and execution evidence; a Snapshot alone does not establish consumption |
| Those references have membership identity X | Yes |
| A source dataset record with identity X exists | Only as of the moment someone checks; not as of the run |
| That record verified before the run | No |
| The caller selected that record | No |
| The caller was permitted to use the source material | No |

Limits, stated plainly:

- A Snapshot records the input membership only. A task can hold a Snapshot and then be blocked at Core's capture verification or at evidence delivery, before the reader runs. Consumption is established only together with the run's execution evidence: Core's capture verification, the evidence delivery, and a successful governed reader execution.
- Nothing persisted names a source dataset on a run. There is no dataset-to-run binding. A source dataset created after a run matches that run's evidence equally well.
- Equal evidence is not proof of selection, of timing, or of permission.
- The check in step 1 confirms that the dataset exists, is well formed and is unambiguous. It is not persisted, it is not authoritative, and it is not what protects the evidence. On the new-execution path, Core verifies every referenced capture itself before the reader is launched, and blocks the task if one fails. A call that returns as a duplicate of an active task launches no reader, performs no fresh capture verification and establishes no fresh evidence consumption.
- The reader's task identity already covers the capture references. A run started this way and a run given the same references by hand, with the same fields, have the same task identity; while the first is still active, the second is reported as a duplicate of it.

This pattern is pinned by tests/test_dataset_reader_composition.py. It adds no runtime code, no record kind and no authority.
