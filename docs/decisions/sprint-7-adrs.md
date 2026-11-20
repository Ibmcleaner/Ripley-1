# Sprint 7 ADRs

## ADR-011 — Capture receipt and content-addressed artifact store

**Status:** Accepted by owner 2026-11-20. Implemented in Sprint 7.

**Context:** Ripley records a Snapshot of the inputs a task used, with a source label and an observation time supplied by the domain adapter or a person. It does not preserve the source material itself, and it cannot distinguish when Ripley received material from when someone says it was observed. Future workloads need inputs whose origin, receipt time and content can be checked later.

**Decision:**
1. A capture preserves the exact bytes received and identifies them by the SHA-256 of those bytes.
2. Exact bytes are kept in a content-addressed store outside the repository. Identical bytes are stored once.
3. Each capture writes one append-only ledger record of kind `capture`, the capture receipt. Repeated captures of identical bytes create separate receipts that share one stored object.
4. `captured_at` is Ripley's own UTC clock reading taken when the read of the bytes completed successfully. It states that Ripley held these exact bytes at that time. It does not state when the source published them or when anyone retrieved them from their origin.
5. Source location, declared retrieval time and declared effective time are recorded as declared by the supplier. They are kept separate from `captured_at` and are not verified by Ripley.
6. A receipt is written only after the bytes are durably stored. A failed or incomplete read, or a failed store write, produces no receipt.
7. Verification compares a stored object with its receipt and reports MATCHED, MISMATCHED or UNAVAILABLE.
8. Sprint 7 intake is local files from an explicitly approved directory. Network acquisition is not designed, scheduled or authorized by this ADR.

**Consequence:** This places a Capture step in front of Snapshot in the ADR-006 provenance chain. Linking a Snapshot to the captures it used, parsing captured content, network acquisition, rights classification and any AI reading of captured content each require their own decision. A stored object without a receipt can exist after a ledger failure; it is harmless and is not evidence of a capture. Adding this module changes a governed path, so a new reviewed baseline must be named before any future provider dispatch.
