# Sprint 10 ADRs

## ADR-012 — Snapshot capture references and pre-execution verification

**Status:** Accepted by owner 2026-11-20. Implemented in Sprint 10.

**Context:** ADR-006 defines the provenance chain Task → Snapshot → Result → Validation → Review → Decision. ADR-011 places a Capture step in front of Snapshot. Nothing connects the two: Ripley can show that bytes were captured and that a task ran, but not that the task was tied to those bytes. A Snapshot records its sources only as a label supplied by the domain adapter.

**Decision:**
1. A task run may declare capture references. The Snapshot records them as the claim.
2. A capture reference has exactly two fields: `capture_id`, the ledger record id of one capture receipt, and `receipt_hash`, the content hash of that receipt record. Together they identify one capture observation. The SHA-256 of the captured bytes is content identity and is kept separate from receipt identity.
3. References are stored on the Snapshot outside `inputs`. They are not domain inputs and never enter a worker packet.
4. References are an unordered set. They are stored in one canonical form, sorted by `capture_id`.
5. The same `capture_id` supplied twice is rejected. It is not silently deduplicated.
6. Two different receipts for identical bytes are allowed and remain distinct observations.
7. Reference structure is validated before any Task or Snapshot record is written. A malformed or duplicate reference writes nothing.
8. Before every worker execution attempt, Ripley resolves each referenced receipt, confirms it is a capture receipt, confirms its hash equals `receipt_hash`, and verifies the stored bytes against the receipt. Execution proceeds only if every reference is MATCHED.
9. Each verification is recorded as a separate `capture_verification` record. The Snapshot holds the claim; the verification record holds the observation.
10. A failed verification blocks the task. The worker does not run, no execution attempt is created, and the failure is recorded at stage `capture_verification`. There is no fallback.
11. The task key formula is unchanged. The task key identifies the requested computation. Capture references identify the evidence for one execution context.
12. A submission whose task key matches an active task but whose capture references differ is refused with the reason `capture_reference_conflict`, and the refusal is recorded. The existing task is never returned as if it had consumed the newly supplied evidence. A submission after a terminal task proceeds as before and may carry a new evidence context.
13. Recovery uses the original Snapshot's references. Replacement references are not accepted. Recovery verifies again at every execution boundary and never relies on an earlier MATCHED observation. Recovery also verifies before consuming its authorization; if the evidence is not verified, recovery is refused, the refusal is recorded, and no authorization is consumed.
14. The Evidence record pins the hash of each referenced capture receipt and of the verification record for the accepted attempt.
15. Capture references are refused for provider workers under this ADR. This is a deliberate temporary boundary that protects the frozen provider path. Lifting it requires its own decision.
16. What this proves: the declared capture evidence was identified and verified at the execution boundary and is bound into the task's evidence chain.
17. What this does not prove: that the task's inputs were correctly extracted or derived from the captured bytes; that source declarations are truthful; that the source is authentic; or that the stored bytes are still available when the task is approved. Approval re-checks ledger records, not stored bytes.

**Consequence:** A run with no capture references produces the same records as before this ADR. Extraction or parsing of captured content, byte re-verification at approval, capture references on provider workers, network acquisition and any agent that reads captured content each require their own decision. ADR-010 and ADR-011 are unchanged.
