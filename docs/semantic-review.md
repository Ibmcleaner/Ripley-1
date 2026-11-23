# Independent semantic review (ADR-014)

A semantic review records a human judgment about the eligible observations in
one exact grounding validation. It is called directly, outside the Core Task
and Worker flow. Mechanically grounded is not semantically acceptable, and
semantically acceptable is not approval or permission to act.

## Reviewer independence

The reviewer kind is always `human`; the caller cannot choose it. The reviewer
identity is a label of 1 to 128 ASCII letters, digits, dots, underscores, colons
or hyphens, beginning with a letter or digit. It must differ from the producer
identity without regard to letter case. The producer identity comes from the
pinned proposal, not from the review caller.

This proves only that the record names a different reviewer label. It does not
authenticate who typed it or prove that two labels represent two people. The
prototype assumes a trusted owner-operated installation.

## Fixed criteria

Criteria identifier: `semantic-review-criteria-v1`.

SHA-256: `50fca7d3f9064bfcaeac785064ec35b13475f7f5881f9d543371b5028d747a38`.

The criteria text is the following six lines joined by a newline, without a
trailing newline. Neither the producer nor the reviewer can replace it.

```text
A. Decide whether the observation is a reasonable interpretation of the evidence shown in the review package.
B. Preserve declared uncertainty. Do not treat an uncertain observation as certain.
C. Do not infer information that the cited evidence does not support.
D. If the evidence does not support a clear judgment, use needs_clarification.
E. acceptable means semantically acceptable under these criteria only.
F. acceptable does not mean approved for execution, source authenticated, source true, provider authorized, budget authorized, task approved or deployment approved.
```

Changing criteria requires a repository change under a new identifier.

## Decisions and evidence

Only a validation with review state `awaiting_semantic_review` can be reviewed.
Its hash and proposal hash must match the specified links. Each observation
whose verdict is `grounded` or `no_evidence_claimed` receives exactly one
decision. Observations that are `not_grounded` cannot receive a decision. A
validation with no eligible observations cannot be reviewed.

| Verdict | Required explanation |
|---|---|
| `acceptable` | A reason of 1 to 512 characters |
| `rejected` | A reason of 1 to 512 characters |
| `needs_clarification` | A reason of 1 to 512 characters and 1 to 8 unresolved issues, each 1 to 256 characters |

For other verdicts, the caller must omit `unresolved_issues`. Stored decisions
include an empty list for that field. Every string must encode as UTF-8.
Decisions are stored in proposal order, with the observation's declared status
and grounding verdict preserved. An acceptable uncertain observation remains
uncertain. Reviewing `not_found` does not prove information is absent in reality.

The append-only `semantic_review` pins validation, proposal and Snapshot IDs and
hashes, producer and reviewer labels, fixed criteria identity and decisions.
Its evidence chain can be reconstructed after reopening the ledger. It does not
read Capture storage again or alter the derived, read-only review package.

## Calling the function

After a person has read the review package and made the judgment, submit their
decisions. This example assumes exactly one eligible observation, `obs-1`:

```python
from ripley.semantic_review import record_semantic_review

record = record_semantic_review(
    ledger, validation_id, validation_hash, 'Independent.Reviewer',
    [{'observation_id': 'obs-1', 'verdict': 'needs_clarification',
      'reason': 'The quote does not settle the requested interpretation.',
      'unresolved_issues': ['Which period does the observation describe?']}],
)
```

The validation ID and hash are those shown in the review package. Supply every
eligible decision, not just the first one. The function returns either the
review record or one refusal record.

## Refusals, in order

| Reason | First failing check |
|---|---|
| `reviewer_invalid` | Reviewer label is malformed |
| `validation_unavailable` | Target is missing or is not a grounding validation |
| `validation_hash_mismatch` | Target hash differs |
| `not_reviewable` | Review state is not awaiting semantic review |
| `proposal_unavailable` | Linked proposal is missing, wrong kind or hash-mismatched |
| `already_reviewed` | This validation already has a semantic review |
| `reviewer_is_producer` | Reviewer and producer labels match without regard to case |
| `no_eligible_observations` | No observation is eligible |
| `decision_schema_invalid` | A supplied decision fails the exact schema |
| `decision_duplicate` | An observation receives more than one decision |
| `decision_not_eligible` | A decision targets an ineligible or unknown observation |
| `decision_missing` | An eligible observation has no decision |

A refusal stores only the bounded validation ID, well-formed reviewer label and
reason. It does not store the supplied decisions. Invalid direct-call argument
types raise `SemanticReviewError('invalid_call')` without a write. A ledger write
exception raises `SemanticReviewError('ledger_write_failed')`.

## Authority and limitations

`acceptable` is a semantic verdict only. Review does not change grounding,
proposals, citations, Capture, Snapshots, Tasks, Results, Core Reviews, Evidence
or Approvals. It does not run work, authorize spending, grant execution or
deployment authority, or change an allowance.

There is no authentication, reviewer interface or review revision. A validation
can be reviewed once. To correct a judgment, ground the proposal again and
review the new validation; the old review remains unchanged. Integration with
Core requires its own decision. The normative contract is
[ADR-014](decisions/source-interpretation-sprint-2-adrs.md).
