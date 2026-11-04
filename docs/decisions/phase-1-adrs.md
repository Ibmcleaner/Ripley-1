# Phase 1 architecture decision records

Decision status: **Accepted architectural direction (DESIGNED)**  
Implementation status: **NOT STARTED**  
Recorded: 2026-11-04

These ADR identifiers organize the owner's approved handoff; they do not add architecture decisions. The owner reports Copilot and Claude completed the Phase 1 review. No unprovided review transcript, experiment, benchmark, or test result is claimed.

## ADR-001 — Domain-agnostic Core

**Context:** Ripley is intended to support multiple prediction and decision-support domains.

**Decision:** Cyrus Forge Systems, LLC remains the company; Cyrus Ripley One (Ripley / R1) is the engine/platform. NFL prediction is a future domain implementation. Keep domain-specific terminology, schemas, features, models, and grading logic outside Core.

**Consequence:** Domain integration must preserve this separation. This decision does not deliver a domain implementation.

## ADR-002 — Lean infrastructure before extension capability

**Context:** Broad future capabilities could expand the first executable skeleton beyond the foundation that can be proved.

**Decision:** Design for extension; build the minimum necessary foundation; prove it; then add controlled layers. Use the conceptual flow Task → Ripley → Worker → Result → Validation → Review/Correction → Evidence → Approval.

**Consequence:** RAG, policy/security, reliability/debugging, learning, postmortems, model governance, and material-event monitoring may have extension points without becoming automatic MVP implementations.

## ADR-003 — Durable facts and separate revisable judgments

**Context:** Later interpretations or corrections must not erase what was known or recorded earlier.

**Decision:** Core stores facts; judgments are separate, referenced, and revisable. Corrections supersede prior judgments rather than rewriting historical facts. Facts are durable; assessments attributable; judgments revisable; revisions supersede rather than erase; history remains auditable.

**Consequence:** Preserve used snapshots and original predictions. Correct erroneous factual data through historical correction/supersession. Separate factual Events from Event Assessments, including materiality judgments.

## ADR-004 — Worker eligibility and independent validation

**Context:** Task routing must permit eligible worker/model alternatives while keeping result production separate from validation authority.

**Decision:** Task contracts include an allowlist of permitted workers/models or an execution-policy reference, not permanent binding to a single worker/model. Workers produce Results; separate independent validation references result_id.

**Consequence:** Worker output is not independently validated solely because its producer says so. Concrete eligibility and independence enforcement remain implementation work.

## ADR-005 — Grade separately from explanatory classification

**Context:** A wrong prediction alone cannot establish why it was wrong.

**Decision:** Outcomes and mechanically determinable Grades belong on the factual side. Later Classification is interpretive and revisable. Distinguish model error, bad/stale/incomplete input, material post-prediction change, ordinary variance, system failure, and insufficient evidence where evidence permits.

**Consequence:** Classification may require accumulated evidence. Domain grading logic stays outside Core; an event can lead to a new snapshot/prediction while preserving originals.

## ADR-006 — Durable provenance and honest engineering documentation

**Context:** Assertions, decisions, changes, and maturity claims must be traceable.

**Decision:** Use the conceptual provenance chain Task → Snapshot → Result → Validation → Review → Decision. Retain appropriate ADRs, architecture, interfaces, source when implemented, tests, postmortems, known issues, and documentation.

**Consequence:** Distinguish planned, designed, recovered, implemented, tested, and production-validated work. Preserve historical work and useful failures. RAG evidence or AI recommendations do not themselves authorize production modifications.
