# Governed Source Interpretation Phase — Sprint 2 ADRs

## ADR-014 — Independent semantic review record

**Status:** Accepted by owner for Sprint 2 of the Governed Source Interpretation Phase. The acceptance date is recorded in the sprint closeout.

**Context:** ADR-013 shows whether a proposed observation points at real bytes of the captured source. It does not show that the observation is a correct reading of those bytes. That judgment needs a person, and the person must not be the producer of the proposal. Ripley needs a durable record of that judgment, bound to the exact evidence that was judged, that gives nothing any authority to act.

**Decision:**
1. A semantic review targets exactly one existing `grounding_validation` record. The reviewer supplies the validation id and the validation hash shown in the review package. Ripley resolves the record itself and refuses the review if the hash differs.
2. Only a validation whose review state is `awaiting_semantic_review` can be reviewed. A validation whose evidence was blocked is refused.
3. The proposal pinned by the validation must exist and its hash must equal the pinned hash. The producer identity is read from that proposal. It is never supplied by the reviewer.
4. The reviewer kind is `human`. Ripley sets it; the caller cannot. The reviewer identity is a label of 1 to 128 characters: letters, digits, dot, underscore, colon, hyphen; first character a letter or digit.
5. The reviewer identity must differ from the producer identity, compared without regard to letter case. A review where they match is refused.
6. This check proves only that the record names a reviewer label different from the producer label. It does not prove who typed the label, or that two labels are two people. Sprint 2 does not authenticate identities. Different labels are accepted under the assumption of a trusted owner-operated installation.
7. One fixed set of review criteria applies. Its identifier is `semantic-review-criteria-v1`. Its text is fixed in the repository and its SHA-256 is recorded on every review. Neither the producer nor the reviewer can supply or replace the criteria. Changing the criteria requires a repository change under a new identifier. The criteria are:
   - A. Decide whether the observation is a reasonable interpretation of the evidence shown in the review package.
   - B. Preserve declared uncertainty. Do not treat an uncertain observation as certain.
   - C. Do not infer information that the cited evidence does not support.
   - D. If the evidence does not support a clear judgment, use needs_clarification.
   - E. acceptable means semantically acceptable under these criteria only.
   - F. acceptable does not mean approved for execution, source authenticated, source true, provider authorized, budget authorized, task approved or deployment approved.
8. An observation is eligible for review when its grounding verdict is `grounded` or `no_evidence_claimed`. Every eligible observation receives exactly one decision. None may be omitted and none may be decided twice. An observation that is `not_grounded`, or that is not in the proposal, cannot receive a decision. A validation with no eligible observation cannot be reviewed.
9. A decision's verdict is `acceptable`, `rejected` or `needs_clarification`. These are semantic judgments only.
10. Every decision carries a reason of 1 to 512 characters. A `needs_clarification` decision also carries 1 to 8 unresolved issues of 1 to 256 characters each. Other verdicts carry none.
11. Ripley copies each observation's declared status and grounding verdict into its decision. An `acceptable` decision on an `uncertain` observation remains visibly uncertain. A `not_found` observation remains a declaration by the proposal; reviewing it does not prove the information is absent in reality.
12. A validation can be reviewed once. A second review of the same validation is refused, whoever the reviewer is. A review is never edited or superseded. To correct a semantic judgment, the proposal is grounded again, which creates a new validation, and that validation is reviewed.
13. A refused review leaves exactly one `semantic_review_refusal` record holding the validation id when it is 1 to 64 characters, the reviewer identity when it is well formed, and one reason. The supplied decisions are not stored. Reasons, checked in this order: `reviewer_invalid`, `validation_unavailable`, `validation_hash_mismatch`, `not_reviewable`, `proposal_unavailable`, `already_reviewed`, `reviewer_is_producer`, `no_eligible_observations`, `decision_schema_invalid`, `decision_duplicate`, `decision_not_eligible`, `decision_missing`.
14. An accepted review is stored as one `semantic_review` record that pins the validation id and hash, the proposal id and hash and the Snapshot id and hash, and holds the producer identity, the reviewer kind and identity, the criteria identifier and hash, and the decisions in proposal order.
15. A semantic review changes no proposal, grounding validation, citation, capture evidence, Snapshot, Task, Result, Core Review, Evidence or Approval record. It writes only its own record.
16. A semantic review creates no authority. It does not invoke a Worker or Core execution, reserve provider authority, authorize spending, create a Task, create a child, change a budget, permit a retry or authorize deployment. `acceptable` is not approval.
17. A review does not read the stored capture bytes again. It binds to what grounding established at grounding time.
18. After a ledger is closed and reopened, the chain from a review back through the grounding validation, the proposal, the Snapshot and the capture receipt identity can be reconstructed from the ledger alone.
19. The review function is called directly and is not a step in the Core Task and Worker flow. The Core's existing `review` record kind is a different thing and is unchanged.
20. Every refusal reason named here must be produced by at least one test.

**Consequence:** Ripley can record a human judgment about grounded observations, bound to the exact evidence judged and made by someone other than the producer's label. It cannot authenticate the reviewer and it gives the judgment no power to act. Authentication, a reviewer interface, revision of reviews, any use of a review to authorize work, and integration with the Core flow each require their own decision.

## ADR-015 — Bounded reasoning envelope

**Status:** Accepted by owner for Sprint 2 of the Governed Source Interpretation Phase. The acceptance date is recorded in the sprint closeout.

**Context:** A later source reader may use a reasoning model. Before any such reader is permitted, hard limits on attempts, input, output, time and cost must exist and must not depend on the reasoning component. No reader exists yet, so this ADR defines the limits and the gate that applies them, and nothing that runs.

**Decision:**
1. The envelope is a deterministic two-step gate: open an attempt, then close it. It executes nothing. It calls no model, provider, network, tool, subprocess or Worker.
2. A governed operation is one Snapshot that carries at least one capture reference. The envelope never creates a Snapshot or any other operation identity.
3. The limits are fixed constants in the repository: 1 attempt per operation; 0 automatic retries; input at most 262,144 bytes; output at most 65,536 bytes; deadline 120 seconds; budget at most 500,000 micro-dollars. No caller can pass a limit. The envelope identifier is `reasoning-envelope-v1`. Its SHA-256 is computed over the identifier and the limits, and every attempt records that hash and a copy of the limits.
4. The envelope has no field for children, fan-out, delegation depth, parent or child budget, tool permission, provider or model. Those capabilities do not exist, and the absence of a field is the absence of authority.
5. Opening an attempt is refused, in this order, when: the operation does not exist (`operation_unavailable`); the operation's one attempt was already consumed (`attempt_already_consumed`); the input size is below 1 (`input_invalid`) or above the limit (`input_too_large`); the required budget is negative (`budget_invalid`) or above the limit (`budget_too_large`). A refusal consumes nothing.
6. Sizes and costs are integers declared by the trusted host that calls the envelope. The envelope does not measure them. Money is counted in integer micro-dollars. No floating point is used.
7. An attempt is recorded durably before the open call returns. If the record cannot be written, the call fails and no attempt exists.
8. The paid authority of every attempt is 0 micro-dollars. The budget limit is proven with synthetic accounting only and authorizes no spending.
9. The deadline of an attempt is its opening time plus 120 seconds, by Ripley's UTC clock. A close at or before the deadline is within the limit. A later close is a violation. This is detection and record. It is not termination or cancellation of anything.
10. An attempt is closed once, with a reported status of `completed`, `failed` or `uncertain`. A `completed` close reports the output size and the cost as non-negative integers. A `failed` or `uncertain` close reports neither.
11. A close is evaluated against the limits copied into the attempt when it opened. Violations are `budget_exceeded`, `deadline_exceeded` and `output_too_large`, recorded in that order. The outcome is `completed_within_limits`, `completed_with_violation`, `failed` or `uncertain`.
12. Closing is refused, in this order, when: the attempt does not exist (`attempt_unavailable`); it was already closed (`attempt_already_closed`); the status is not one of the three (`status_invalid`); the reported figures do not fit the status (`report_invalid`).
13. An attempt is consumed when it is opened. It stays consumed whether it closes as completed, failed or uncertain, and when it never closes. There is no automatic refund, retry, fallback, replacement operation or fresh allowance. A retry is another attempt, and none is available.
14. Remaining authority is derived from ledger records only, never from memory. After a ledger is closed and reopened, consumed attempts remain consumed.
15. The limits change only through a repository change under a new envelope identifier. A reasoning component cannot alter a limit, choose another envelope, reset or add an attempt, or grant itself paid authority, a provider, a network, a tool or a child.
16. This ADR does not prove: termination of a process; cancellation by a provider, a network or an SDK; correctness of a provider's bill; accuracy of any conversion from tokens to cost; or that the sizes and costs declared by a host are true.
17. ADR-010's dispatch governance is separate and unchanged. When a reader is given a provider, that decision must reconcile the two.
18. The envelope is called directly and is not a step in the Core Task and Worker flow.
19. Every refusal reason, violation and outcome named here must be produced by at least one test.

**Consequence:** Ripley has a fixed, hash-identified set of limits for one future reasoning attempt and a ledger gate that refuses a second attempt, records violations and survives restart. Nothing uses it yet. A source reader, a model, a provider, real cost figures, enforcement by termination, and any change to the limits each require their own decision.
