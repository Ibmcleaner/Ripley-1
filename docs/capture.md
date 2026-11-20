# Offline capture receipts

A capture preserves the exact bytes of a local file and appends one receipt to the supplied ledger. This is offline, local-file intake only, separate from the provider path.

## Capture

`capture_file(ledger, store_dir, source_path, *, approved_root, source_id, source_location, supplied_by, content_type, declared_retrieved_at=None, declared_effective_at=None, clock=None, max_bytes=DEFAULT_MAX_BYTES)` returns the record appended by the ledger.

Supply an in-memory ledger or an external SQLite ledger, an external object store, and a regular source file whose real path is within the approved directory. Use local storage and directories controlled by the operator during capture and verification. URL and network-share path syntax are refused. The source is opened in binary mode. The default limit is 10 MiB. A complete zero-byte file is a valid input.

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

The object is stored at `<store_dir>/sha256/<first two hex digits>/<64 hex digits>`. Capture re-hashes an existing object before reuse. For a new object it reserves the digest with a temporary sibling lock directory, writes and flushes a same-directory temporary file, calls fsync, checks the temporary file's digest and size, and publishes by atomic replacement. On POSIX it also syncs the affected directories. A competing writer encountering the reservation fails without retry. An abrupt process termination can leave a reservation; this version performs no automatic stale-lock recovery.

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
| `source_unapproved` | The source is outside the approved root, is a directory or other nonregular file, or is a URL. |
| `source_unreadable` | Source inspection or opening failed. |
| `read_interrupted` | Reading failed or the byte count differs from the file size just before the read. |
| `too_large` | The bytes read exceed the configured limit. |
| `store_corrupt` | An existing object's identity differs from the expected bytes. |
| `artifact_write_failed` | Object reservation, persistence or verification failed. |
| `ledger_write_failed` | The ledger append raised after the object was stored. The original exception is chained. |
