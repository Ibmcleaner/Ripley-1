# Offline capture receipts

A capture preserves the exact bytes of a local file and appends one receipt to the supplied ledger. This is offline, local-file intake only, separate from the provider path.

## Capture

`capture_file(ledger, store_dir, source_path, *, approved_root, source_id, source_location, supplied_by, content_type, declared_retrieved_at=None, declared_effective_at=None, clock=None, max_bytes=DEFAULT_MAX_BYTES)` returns the record appended by the ledger.

Supply an in-memory ledger or an external SQLite ledger, an external object store, and a regular source file whose real path is within the approved directory. Source paths must be strings or path-like objects returning strings. Byte-string source paths, including path-like objects returning bytes, are refused before any source read or storage. Use local storage and directories controlled by the operator during capture and verification. URL and network-share path syntax are refused. The source is opened in binary mode. The default limit is 10 MiB. A complete zero-byte file is a valid input.

| Receipt key | Meaning |
|---|---|
| `capture_version` | Receipt format version, currently `1` (string). |
| `source_id` | Supplier's logical source identifier. Use 1–64 lowercase ASCII letters, digits, periods, underscores or hyphens, starting with a letter or digit. |
| `source_location` | Origin as declared by the supplier. A location label is recorded without contacting the origin. |
| `source_filename` | Basename of the supplied local path. |
| `intake_method` | `local-file`. |
| `supplied_by` | Supplier identification as declared. |
| `content_type` | Media type as declared by the supplier. |
| `sha256`, `size_bytes` | Lowercase hexadecimal SHA-256 and byte count of the exact input. |
| `captured_at` | Ripley's own UTC clock reading taken when the read of the bytes completed successfully. It states that Ripley held these exact bytes at that time. It does not state when the source published them or when anyone retrieved them from their origin. |
| `declared_retrieved_at` | Supplier's stated time of retrieval from the origin, or null. |
| `declared_effective_at` | Supplier's stated effective time for the material, or null. |

Source location, declared retrieval time and declared effective time are recorded as declared by the supplier. They are kept separate from `captured_at` and are not verified by Ripley. Both optional timestamps require an explicit UTC offset and are normalized to UTC. The three free-text fields accept 1–512 characters and must contain a non-whitespace character. An injected `clock` returns a timezone-aware UTC datetime.

## Stored object and receipt

The object is stored at `<store_dir>/sha256/<first two hex digits>/<64 hex digits>`. Capture re-hashes an existing object and refuses corruption before reuse. On POSIX it syncs the destination directory before creating a receipt for that object, including on reuse.

For a new object, capture writes and flushes a same-directory temporary file, calls file fsync, checks its digest and size by re-reading it, and publishes it with os.replace. On POSIX it then syncs the destination directory. A sync failure produces artifact_write_failed without a receipt. A final object that has already been published remains in place after a later failure; only the failing capture's temporary file is cleaned up. A later sequential capture can verify the existing object and retry its applicable durability sync before appending a receipt.

Sprint 9 removes the per-digest reservation. Capture creates no .lock directory. Legacy reservation directories are ignored and left untouched; their former manual-removal procedure is no longer needed for capture to proceed. No automatic recovery or cleanup is provided.

Capture is supported sequentially, one at a time. Concurrent capture publication is unsupported, untested and unclaimed.

After publication, each successful capture appends a distinct record of kind `capture`, including repeat observations of the same bytes. If the ledger append fails, the object stays available for reuse. Its presence alone is not evidence of a capture.

## Verify

`verify_capture(ledger, store_dir, capture_id)` uses an already-open ledger, the store root, and a ledger record ID. It returns a status and short detail without writing anything.

| Status | Finding |
|---|---|
| MATCHED | Stored SHA-256 and size agree with the receipt. |
| MISMATCHED | The stored bytes have a different SHA-256 or size. |
| UNAVAILABLE | The receipt is absent, identifies another record kind, has no usable object identifier, or its stored object cannot be read. |

## Capture errors

Inspect `CaptureError.reason` for the failed step.

| Reason | Condition |
|---|---|
| `invalid_metadata` | Invalid source metadata, timestamp, clock value or byte limit. |
| `store_invalid` | Invalid store location, including a path into the repository. |
| `source_missing` | The source does not exist. |
| `source_unapproved` | The source path is bytes or resolves to bytes, is outside the approved root, is a directory or other nonregular file, or is a URL. |
| `source_unreadable` | Source inspection or opening failed. |
| `read_interrupted` | Reading failed or the byte count differs from the file size just before the read. |
| `too_large` | The bytes read exceed the configured limit. |
| `store_corrupt` | An existing object's identity differs from the expected bytes. |
| `artifact_write_failed` | Object persistence, applicable durability sync or temporary-file verification failed. |
| `ledger_write_failed` | The ledger append raised after the object was stored. The original exception is chained. |

## Linking a task to its captures (ADR-012)

Supply `capture_references` to `Ripley.run()` and the local artifact store as `capture_store` when constructing Ripley. Each reference contains exactly `capture_id` (a lowercase canonical UUID) and `receipt_hash` (64 lowercase hexadecimal characters). Up to 16 references are accepted. References are semantically unordered, canonicalized by capture_id and frozen on the Snapshot outside inputs. Duplicate Capture IDs and malformed references are refused before any ledger write. Distinct receipts for identical bytes remain distinct observations. None and empty references retain the existing no-reference behavior.

Before every Worker attempt, including correction attempts, Ripley resolves the references and verifies receipt identity and stored bytes through the existing Capture verifier. It records a separate `capture_verification` after Task/Snapshot creation and before creating the execution attempt. Every reference is evaluated. A failed verification records an execution failure at stage `capture_verification`, blocks the Task and invokes no Worker for that boundary. There is no fallback.

| Verification reason | Meaning |
|---|---|
| `receipt_missing` | The referenced receipt is absent. |
| `receipt_wrong_kind` | The referenced record is not a Capture receipt. |
| `receipt_hash_mismatch` | Receipt identity differs; artifact bytes are not inspected. |
| `verified` | Receipt identity and artifact verification matched. |
| `artifact_mismatched` | Stored bytes or size differ from the receipt. |
| `artifact_unavailable` | Stored artifact verification is unavailable. |
| `verification_error` | The artifact verifier raised an exception. |

The task key remains unchanged and identifies the requested computation. An active task with the same key and different Capture references produces a `capture_reference_conflict` record and an explicit refusal. Equal canonical references retain the existing duplicate behavior. After a terminal task, a new submission may carry a different evidence context.

Recovery preserves the original Snapshot's references and accepts no replacements. A recovery pre-check occurs before recovery authorization. A failed pre-check is recorded without consuming authorization or creating a recovered Task. A passing pre-check writes nothing, and every later Worker boundary verifies freshly again. An earlier MATCHED observation is never reused as execution authority.

Evidence pins every referenced Capture receipt and the successful verification record for the accepted attempt. Provider Workers refuse nonempty Capture references in Sprint 10 before duplicate writes, dispatch gating or execution.

Sprint 10 proves that the declared Capture evidence was identified and verified at the execution boundary and bound into the Task evidence chain. It does not prove extraction or derivation correctness, source authenticity, truth of source declarations, or artifact availability at approval time. Approval checks ledger-record hashes without re-reading artifact bytes. See docs/decisions/sprint-10-adrs.md (ADR-012).

## Sprint 7 acceptance evidence

| Evidence | Result |
|---|---|
| Publication | Implementation PR #34; reviewed published head 8f8dc24314acac2ef854931e3a517d9601527e44; merged to main as 86012c8924d24a49e4448904dac7dc53e4df3d38. The merged tree is identical to the reviewed commit. |
| Independent review | Independent review (Claude): APPROVED WITH NONBLOCKING NOTES FOR OWNER MERGE. |
| Independent Linux run | Linux, independent, Python 3.13 with anthropic 2.9.0: 202 run, 202 passed, 0 failed, 0 errors, 0 skipped. Focused capture tests: 17 run, 17 passed. |
| Independent receipt reproduction | Independent receipt reproduction (Claude): receipt read directly from the SQLite ledger; stored object's SHA-256 computed with a separate tool matched the receipt and the source; MATCHED after reopening the ledger; MISMATCHED after one stored byte was altered; UNAVAILABLE after the object was deleted. |
| Owner Windows run | Windows, owner-run, as reported by the owner: 202 run, 4 expected Phase 5 skips, 0 failures, 0 errors. Line-ending warnings appeared during the run; they were warnings and did not change the result. |
| Implementer Linux run | Implementer environment note: ChatGPT's Linux run showed 38 skips because the optional pinned SDK was not installed there. This was an environment limitation, not a defect. |

## Known limitations

Remaining limitations:

Capture references are not accepted on provider Workers.

Approval verifies ledger-record hashes but does not reverify stored Capture bytes.

**Sequential capture.** Capture is supported one at a time. Concurrent capture publication is unsupported, untested and unclaimed.

**Interrupted capture.** A capture that is terminated abruptly can leave a temporary file in the destination directory. It is not a stored object and is not evidence of a capture. The operator may delete it. No automatic cleanup is provided.

**Directory sync on Windows.** Directory sync is performed on POSIX only. Windows has no portable equivalent in the standard library.

Corrected in Sprint 9 (PR #38), recorded for history:

- Bytes source path. A byte-string source path previously raised an unclassified TypeError after content was stored. It is now refused as source_unapproved before any read or store write.
- Reservation. The per-digest reservation directory, and the stale-reservation failure it could cause, were removed.
- Test coverage. The temporary-file re-hash and the sync protocol previously had no detecting test. CAP-20 and CAP-21 now detect their removal.

## Sprint 7 retrospective

**What worked**

- Independent planning converged on a smaller offline capture primitive than the starting proposal.
- File scope was bounded before implementation.
- The provider path stayed isolated.
- The receipt and digest were independently reproduced.
- Linux and Windows runs completed before merge.

**What caused rework or friction**

- The first frozen-file wording contradicted the authorization for two new files and was corrected before implementation.
- The implementer's Linux environment lacked the pinned optional SDK, producing environment-driven skips.
- As reported by the owner, authorization had to be restated directly before implementation because the implementation environment did not accept relayed authorization.

What should remain: one measurable sprint outcome; independent implementation and review; hard-stop conditions; review of the exact published SHA; owner Windows verification for file-system work; the frozen provider boundary.

One improvement to carry forward: assignments that change the repository carry the owner's direct authorization and the exact file scope in a form the implementation environment can check before work begins.

## Sprint 9 acceptance evidence

| Evidence type | Recorded evidence |
|---|---|
| Publication | Implementation PR #38. Commit 1: `d4c9bce193c40ca0547e06a11b04eafc31b65674`. Commit 2 / reviewed head: `3893fa54e11ace1b7250950533c038a4ffda0e98`. Merged main: `697680bb2c69d0f7fa6bbb1557912ecf694c24cc`. The merged tree is identical to the reviewed head. |
| Independent review | Claude verdict: APPROVED WITH NONBLOCKING NOTES FOR OWNER WINDOWS GATE. |
| Independent Linux run | Claude independently ran the published implementation using Python 3.13 and anthropic 2.9.0 on tested commit `531b0acbed6aa4a5e87d130e575d8ef308b8a12c`. Disposable-copy focused capture result: 21 run, 21 passed. Full suite: 206 run, 206 passed, 0 failures, 0 errors, 0 skipped. Self-check: PASSED. |
| Independent mutation checks | Claude applied seven deliberate defects individually to the published capture implementation. Each was detected: temporary re-hash removed — CAP-20; file sync removed — CAP-20 and CAP-21; post-publication directory sync removed — CAP-21; published object deleted after sync failure — CAP-21; reuse directory sync removed — CAP-21; bytes-path refusal removed — CAP-18; reservation reintroduced — CAP-19. |
| Existing test preservation | The first 229 lines of tests/test_capture.py, through CAP-17, are byte-identical to the pre-Sprint file. |
| Frozen identities | Packet, prompt and output-schema hashes remained unchanged. |
| Owner Windows run — owner-reported | As reported by Robert: focused capture, 21 run, 21 passed. Full suite: 206 run, 4 expected Phase 5 skips, 0 failures, 0 errors. |
| Hosted checks — implementer-reported | As reported by ChatGPT: Run 44831869741 on Commit 1 was green, 202 run, 0 skipped. Run 44832602272 on Commit 2 was green, 206 run, 0 skipped. |
| Hosted check identity — independently confirmed | Claude independently confirmed from GitHub that each tested merge commit has main and the corresponding Sprint commit as parents. Claude did not independently observe either run page. |
| ADR-011 | UNCHANGED. |

## Sprint 9 retrospective

**What worked**

- The correction sprint stayed bounded to seven known items.
- Claude and ChatGPT independently converged on removing the reservation.
- Four new tests detect durability and error-handling regressions that were previously uncovered.
- All seven deliberate mutations were detected.
- Linux and Windows verification both passed.
- The advisory check evaluated both commits.

**What caused rework or friction**

- The exact CI runner payload was reformatted in transit.
- The published runner hash therefore did not match Claude's originally assigned reference hash.
- Claude reconciled the published runner as a layout-only, behaviorally equivalent transmission difference.
- Long implementation payloads sent through chat repeatedly risked truncation or missing content between chats.

**One improvement to carry forward**

For exact or verbatim implementation payloads, prefer a hash-verified file passed through the already-approved shared Drive folder over a long chat message.

This is a process recommendation only.

It does not change the shared-Drive rules.
