# Source Dataset Provenance Phase — Sprint 1 ADRs

## ADR-018 — Source dataset: immutable source membership

**Status:** Accepted by owner for Sprint 1 of the Source Dataset Provenance Phase. The acceptance date is recorded in the sprint closeout.

**Context:** Ripley holds source evidence as Capture receipts (ADR-011). Each receipt identifies one observation of one local file and its stored bytes. A Snapshot can carry capture references (ADR-012), but a Snapshot exists only inside a task run, and its hash also covers that task's inputs, so the same captures in two tasks give two different Snapshot identities. The owner has approved a two-layer data architecture. Layer 1, the source dataset, is an exact reusable membership of captured source evidence. Layer 2, the interpreted dataset, is governed interpreted observations. This ADR covers Layer 1 only.

**Problem:** Nothing persisted today states, independently of a Task, which exact Capture observations belong together. A Capture is one observation. A Snapshot is grouped evidence tied to one task and to a task-specific identity. A view derived at read time cannot recover an intended membership after a restart, because the membership was never written down. Evaluation that is meant to be reproducible needs to name its source membership exactly and to check it again later.

**Decision:**
1. Ripley adds one ledger record kind, `source_dataset`. It records one immutable membership of capture receipts. It is written through the existing ledger append and uses no supersession.
2. Layer 1 holds references only. It copies no Capture metadata, no bytes, no content hash, no source name and no time.
3. Two operations are defined, in one new module. Create records a membership after verifying every member. Verify is read-only and rebuilds and checks one source dataset from ledger records and stored bytes alone.
4. Neither operation creates a Task, a Snapshot, a Worker attempt, an envelope reservation, a review, a release or an approval. Neither launches anything. Neither takes or records an actor.
5. This decision changes nothing in `ripley/core.py`, `ripley/storage.py` or `ripley/capture.py`.

**Record contract:**
1. The record data has exactly three keys: `contract_version`, `membership_sha256` and `members`.
2. `contract_version` is the integer 1.
3. `members` holds 1 to 16 capture references. Its canonical persisted JSON representation is an array. The supported ledger interface may expose that array as a list or as a frozen tuple, and both are accepted; nothing else is. Each reference is a mapping with exactly the keys `capture_id` and `receipt_hash`, the shape accepted by ADR-012. `capture_id` is a canonical lowercase UUID string. `receipt_hash` is 64 lowercase hexadecimal characters.
4. Members are in ascending order of `capture_id`. The order a caller supplies never matters.
5. A duplicate `capture_id` is refused. It is never silently dropped.
6. Empty membership is refused.
7. The maximum of 16 applies to Sprint 1 only. It is the number of capture references a Task can carry today. It is not a permanent platform limit.
8. `membership_sha256` is the SHA-256, in lowercase hexadecimal, of the accepted canonical JSON of the mapping with exactly `contract_version` and `members`, where `members` is the canonical list.

**Identity semantics:**
1. `membership_sha256` is the identity of the source dataset. Identical exact membership always gives the identical value.
2. The ledger record id and the record content hash say where a membership is written in one ledger. They are not the dataset identity and must not be used to compare datasets.
3. Nothing else participates in the identity: no actor, no dataset name, no time, no ledger record id, no creation context, no Task, no approval, no source metadata and no Layer 2 field.
4. Membership identity is not content identity. Two separate captures of byte-identical files are two different members and give two different source datasets.
5. Changed membership is a different membership identity. Nothing links the two.

**Creation semantics:**
1. Create takes a ledger, the capture store directory and a list or tuple of references.
2. It validates the call and the original representation of every reference, then puts the references in canonical order.
3. It verifies every member. A member verifies only if a record with that id exists in the ledger, that record is a capture receipt, its content hash equals the member's `receipt_hash`, and the existing Capture verification reports that the stored bytes match.
4. Creation is all-or-nothing. If any member fails, nothing is written and the first failing member is reported.
5. It computes the membership identity and looks for existing `source_dataset` records that claim it.
6. If none exists, it appends one `source_dataset` record and returns it.
7. If two or more exist, it refuses with `dataset_ambiguous`.
8. If exactly one exists, its complete data is compared with the data that would be written. On exact equality create returns that record and writes nothing; every member was verified again first. Otherwise, or if that comparison cannot be performed on the stored data, it refuses with `dataset_ambiguous` and writes nothing.

**Verification semantics:**
1. Verify takes a ledger, the capture store directory and a record id. It writes no record and holds no state between calls. Nothing is answered from process memory.
2. It returns a mapping with exactly: `notice`, `outcome`, `reason`, `dataset_id`, `membership_sha256` and `members`. `outcome` is `verified` or `failed`. `reason` is null on success and is one bounded reason on failure.
3. The original stored representation is validated before anything is copied or normalised. The record data must be a mapping with exactly the three keys and an integer contract version. The `members` value, as the supported ledger exposes it, must be a list or a tuple of 1 to 16 entries; each entry, in that original exposed representation, must itself be a mapping with exactly the two keys; each field must have the required type and format; there must be no duplicate; the stored order must be the canonical order. Only then may a member be copied, and only then is the identity recomputed and compared with the stored `membership_sha256`.
4. A stored member written as a sequence of key and value pairs is not a mapping. It fails as `dataset_malformed` even when its mapping form would produce the stored hash, and even though the outer `members` collection is itself an accepted list or tuple.
5. Verification returns a bounded failure result, without raising, for malformed Source Dataset records and record identifiers representable through the supported ledgers and their JSON-compatible record data, including the explicitly tested malformed structures and identifiers. Arbitrary hostile Python objects, custom mapping implementations with failing methods, and invalid ledger implementations are outside this guarantee. No hostile-object containment and no sandbox is added.
6. A source dataset is verified only when its record is well formed, its identity recomputes, it is the only record claiming that identity, and every member verifies.
7. The result echoes the record id as supplied. The result is not guaranteed to be JSON-serialisable when the caller supplied an arbitrary Python object as the record id. This does not alter lookup.

**Failure taxonomy:**
1. Create fails only by raising one error type that carries one reason and, when one member is at fault, that member's `capture_id`. The thirteen reasons are: `invalid_call`, `empty_membership`, `too_many_members`, `malformed_member`, `duplicate_member`, `receipt_missing`, `receipt_wrong_kind`, `receipt_hash_mismatch`, `artifact_mismatched`, `artifact_unavailable`, `verification_error`, `dataset_ambiguous` and `ledger_write_failed`.
2. Verify reports one of six reasons for the dataset: `dataset_unavailable`, `dataset_malformed`, `contract_unsupported`, `membership_hash_mismatch`, `dataset_ambiguous` and `member_failed`.
3. Verify reports one of seven reasons for each member: `verified`, `receipt_missing`, `receipt_wrong_kind`, `receipt_hash_mismatch`, `artifact_mismatched`, `artifact_unavailable` and `verification_error`.
4. A reference to a record in another ledger is `receipt_missing`. A reference to a record that exists and is not a capture receipt is `receipt_wrong_kind`.
5. This contract covers the references, record ids and stored records representable through the supported ledgers and their JSON-compatible record data. It makes no promise for arbitrary hostile Python objects or when the caller passes something that is not a supported ledger.

**Reason precedence:**
1. Create reports the first failure in this order: the call and the reference shapes (`invalid_call`, then `empty_membership`, then `too_many_members`, then for each reference in the order supplied `malformed_member` or `duplicate_member`); the members in canonical order (for each member `receipt_missing`, then `receipt_wrong_kind`, then `receipt_hash_mismatch`, then the stored-byte result); the membership identity is then computed; competing records (`dataset_ambiguous`); the append (`ledger_write_failed`).
2. Verify reports the first failure in this order: the target is located (`dataset_unavailable`); the target's top-level structure (`dataset_malformed`); an unsupported integer contract version (`contract_unsupported`); the original member representations, the canonical form and the type of the stored hash (`dataset_malformed`); the recomputed identity (`membership_hash_mismatch`); competing records (`dataset_ambiguous`); the members (`member_failed`).
3. A malformed target is `dataset_malformed` before ambiguity is evaluated.
4. An unsupported integer contract version is `contract_unsupported` before any version-specific member representation is interpreted.
5. A well-formed target that shares its membership hash with another record is `dataset_ambiguous` before any member is verified.

**Sequential uniqueness boundary:** Under supported sequential, single-writer use, one exact membership has one `source_dataset` record per ledger, and a repeat creation returns that record and writes nothing. This is not a storage-level concurrent uniqueness guarantee.

**Concurrency limitation:** Concurrent identical creation is outside the Sprint 1 guarantees. Two writers creating the same membership at the same moment can each append a record. The result is not silent: both creation and verification then report `dataset_ambiguous`. Preventing it would need a storage-level uniqueness rule, which this ADR does not add.

**Strict ambiguity:** Any second `source_dataset` record claiming the same `membership_sha256` causes `dataset_ambiguous`. This includes a malformed competing record that claims the same membership hash. Ripley does not select one automatically. `dataset_ambiguous` means manual inspection is required. It does not mean that the valid record was disproved, that the Capture evidence was invalidated, or that one competing record should win. Because any code inside the process can append a ledger record, a stray record can make a sound source dataset unusable until a person inspects it. That is the accepted cost of failing closed.

**Capture-reference validation strategy:** Reference validation is local to the new module so that each failure has a bounded reason. It does not call Core's private canonicalisation helper, Core is not refactored and no shared public helper is added. The local validation mirrors the accepted ADR-012 reference semantics, and a test must pin the stored members against the form Core produces for the same input. Stored-byte verification is not duplicated: the existing Capture verification is reused unchanged. The comparison of a receipt's content hash with a member's `receipt_hash` is local, because the existing equivalent is private to Core and bound to a Task.

**Validation-drift rule:** Any future change to the accepted Capture-reference contract requires a coordinated review of Source Dataset validation.

**Time non-claims:** A source dataset has no time field: no admission time, no version time and no creation time in its data. The ledger's own record time is wall-clock time that the record content hash does not cover; it is not used for identity, for ordering or for any decision. Ripley does not rely on ledger wall-clock ordering. A Capture's `captured_at`, `declared_retrieved_at` and `declared_effective_at` stay at the Capture layer and do not prove when information was available. Sprint 1 answers which exact source evidence. It does not answer as of when. No arbitrary "as of T" claim is made, and the current ledger could not support one.

**Integrity-only meaning:** A verified Source Dataset is an integrity result, not a trust, quality, approval, interpretation, availability-time, consent, or fitness-for-use result. Every verification response carries this notice: "A source dataset records which captured evidence belongs to a collection. A verified Source Dataset is an integrity result, not a trust, quality, approval, interpretation, availability-time, consent, or fitness-for-use result." The operator documentation carries the same meaning. It must not be weakened.

**Security and authority boundary:** A source dataset grants nothing. Holding one or verifying one authorizes no run, no release, no approval and no downstream action. Creation records no actor because it decides nothing. The module reads no credential, key or token. No model, provider, network, tool, child process or agent is part of this ADR. The provider request, prompt, model and schema are unchanged.

**Alternatives considered:** A Capture receipt alone; a Snapshot used as a dataset; a read-only view derived from existing records; a minimal new record. A private prototype compared them on both ledgers.

**Rejected alternatives:**
1. Capture receipt alone. It identifies one observation and cannot state a collection.
2. Snapshot as a dataset. It would need a Task that does no work, or a change to what a Snapshot means, and its identity varies with task inputs.
3. Derived view. It can hash a list it is handed and cannot say which list was meant after a restart.
4. Calling Core's private reference helper. It couples a new module to a private name and loses the bounded reasons.
5. Counting only well-formed identical records as competitors. It is more code and would let two records stand for one dataset.
6. A storage-level uniqueness rule. It requires a change to storage that Sprint 1 does not need.
7. A name, a predecessor reference, a version chain or a time field. Nothing in Sprint 1 reads one, and each carries a meaning that has not been decided.

**Consequences:** Upon implementation and acceptance of the specified behavior, an exact collection of captured source evidence will have a durable identity independent of a Task and will be verifiable after restart. One record kind and one module will be added. Nothing will consume a source dataset in Sprint 1. Acceptance of this ADR is acceptance of the design; it is not acceptance of an implementation.

**Limitations:**
1. No consumer. No Task will accept a source dataset in Sprint 1, so reuse will be shown as stable identity and repeatable verification, not as an end-to-end run.
2. At most 16 members.
3. Sequential single-writer use only.
4. Ambiguity can be induced by a stray record and needs manual inspection.
5. The write-failure claim is bounded to what is tested: with an injected failure of the ledger append on the two supported ledgers, creation must report `ledger_write_failed` and no `source_dataset` record may be present afterwards. No universal transactional guarantee is claimed for every possible backend failure.
6. No time claim, no name, no lineage and no retraction.
7. Labels and records are not authenticated. Code inside the process can append records directly.

**Test obligations:** Eleven test categories, SD-01 to SD-11, run on both ledger implementations: 22 tests. They must cover the record and its identity; order independence and repeat creation; the difference between membership identity and content identity; every call and member refusal; every member failure and all-or-nothing creation; reconstruction after a SQLite close and reopen; later damage; malformed stored records, including record data that is not a mapping and a member stored as a sequence of pairs with a matching hash; interrupted creation; that the tested create and verify paths invoke no prohibited operation, introduce no unauthorized record kind and respect the source, public-name and signature restrictions; and that a Snapshot is not a dataset identity. The tests do not claim proof of network or process unreachability under every conceivable environment. Persistence claims rest on SQLite. Every reason in the failure taxonomy must be produced by at least one test.

**Mutation obligations:** Thirty mutations, each weakening one enforcement rule of this ADR, each with a designated detecting test, each to be detected on both ledgers. They include, as distinct mutations, verification accepting a stored record with extra keys, verification normalising stored members before validating their original type, and a Capture-verification exception or unexpected status escaping instead of being bounded as `verification_error`.

**Windows gate:** Windows is an implementation acceptance gate. The owner runs it with the pinned provider SDK installed. The expected result is the full suite with the four existing Phase 5 skips and no other. Any other skip count is a gate failure until explained.

**Non-goals:** No Layer 2. No interpreted data. No consumer of approved readings. No authenticated-identity work. No semantic schema, feature, label, target, outcome or split. No model, agent, provider or network acquisition. No NFL data. No paid reasoning. No generic query engine. No "as of T" claim. No correction, supersession or retraction framework. No dataset name. No version lineage. No Task that consumes a source dataset. No command-line entry point. No storage migration.

**Future compatibility:** A later contract version can add fields, such as lineage, without disturbing version 1 records, because the contract version takes part in the identity and an unsupported version is refused by name. Raising the member limit, admitting concurrent writers, adding a consumer and adding any time meaning each need their own decision.

**Layer 2 deferral:** Layer 2 is deferred. It is not automatically the next sprint. Nothing in this ADR reads, links to or prepares storage for reader proposals, releases, approvals or readings. Corrected source bytes remain a new Capture under existing behavior.
