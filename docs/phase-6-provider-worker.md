# Phase 6 external provider Worker

Status: **ACCEPTED prototype (6B + 6C, mock transport only) — Claude-reviewed at eaaa192; executed independently on Linux (Claude, 159 OK) and Windows (owner, 159 run / 155 pass / 4 expected Phase 5 signal skips / 0 fail). Merged to main 2026-11-17 (PR #15). Stage 6D accepted by the owner on 2026-11-27 after one successful bounded live diagnostic (Dispatch #3); Stage 6E accepted by owner on 2026-11-27 under ADR-010 revision 12 by documentary report and explicitly accepted grade. Phase 6 closed by owner on 2026-11-27; final repository acceptance awaits reviewed merge; Foundation Exit HELD. NOT production validated.** 6D-prep artifacts present (PR #17). Sprint 5 schema/diagnostics fix ACCEPTED — Claude-reviewed at 63c8f5f; Linux 167 OK (Claude); Windows 167 run / 163 pass / 4 expected Phase 5 skips / 0 fail (owner); owner mock dry-run exited 0; merged PR #27

## Implemented boundary

ADR-010 revision 8 governs one registered provider identity, one pinned SDK, one model,
and frozen NFL availability fixtures. Parent execution remains native. The provider
Worker runs in a subprocess. Parent-only ledger writes preserve the Task, Attempt,
request, Result, independent Validation, policy Review, Evidence, and owner approval.

The provider extra is installed with `python -m pip install -r requirements-providers.txt`.
The requirement is exactly `anthropic==2.9.0`. Provider execution is opt-in through the
registered identity, its allowlist, and `execution='subprocess'`. The parent supplies
an identity reference and imports no provider implementation or SDK.

The executed path uses `RIPLEY_PROVIDER_TRANSPORT=mock`, the separate test-Worker gate,
a synthetic credential, frozen output files, and a child socket guard installed
before the SDK import. Automated tests never set `RIPLEY_LIVE_DISPATCH`.
The later live-mode gate is implemented as assigned and remains unexercised.

## SDK transport and structured output

P6-16 was written and passed before production files changed. Version 2.9.0 uses
`httpx2`, so the supported injection is
`http_client=httpx2.Client(transport=httpx2.MockTransport(handler))`.
The structured-output parameter is
`output_config={'format': {'type': 'json_schema', 'schema': schema}}`.
The message request uses `max_tokens=1024`.

The probe checks POST `/v1/messages`, the `anthropic-version` header, model identity,
and serialized schema. Its success handler sees one request. Its 429 handler also
sees one request with `max_retries=0` and raises the SDK's rate-limit exception.
The socket guard counter remains zero. The Worker obtains headers and token usage
through `client.messages.with_raw_response.create`, then parses the message text.
The request schema derives the top-level contract from `adapter.expected_output`.
The independent validator checks the detailed NFL fields.

ADR-010 Decision 1 states the evidence boundary verbatim.

> Mock-mode evidence proves serialization, request construction, response parsing, failure mapping, and Ripley integration against the real SDK code path; it does not prove the account or model accepts the live request. Only the owner-authorized 6D live pilot proves that.

## Record additions

| Record | Provider additions |
|---|---|
| Task | Adapter task type `extract`, scalar resource ceiling `provider`, frozen dispatch policy allowing one send per Attempt and zero paid corrections |
| Execution Attempt | Correction-budget override, transport mode, gate-variable presence, credential-reference name, provider/model/SDK metadata, complete prompt reference and hash, optional owner dispatch-authorization reference |
| Execution Request | Existing v1 request packet, with its nine fields preserved |
| Result | `execution='provider'`, `cost=None`, response dispatch metadata and `remote_outcome='completed'` |
| Execution Failure | Normalized provider error, dispatch metadata when observed, and parent-derived remote outcome. Parent timeout or host failure records dispatch as null and outcome as unknown |
| Validation | Existing provenance fields plus rule/player/field failures from independent snapshot-aware checks |
| Policy Review | Additive `purpose='policy'`, including revisions |
| Dispatch authorization | Owner-appended record permitting one further Attempt for the same Task key. Consumption derives from Attempt references |
| Pilot budget exhausted | Budget, consumed Attempt slots, and transport mode |

Every provider Attempt carries the template's SHA-256 before it is appended. The
child hashes the bytes it renders independently and returns that reference inside
`dispatch.prompt_ref`. A mismatch blocks with `stage='host_failure'`, message
`prompt_ref hash mismatch`, null dispatch, and unknown remote outcome. The Attempt
consumes one slot. The template itself remains versioned in the repository.

## Provider errors and observation

| Error class | Dispatch observation |
|---|---|
| `live_gate_closed` | `not_sent` |
| `auth_unavailable` | `not_sent` |
| `insufficient_time` | `not_sent` |
| `auth_rejected` | `sent` with an HTTP response |
| `rate_limited` | `sent` with an HTTP response |
| `invalid_request` | `not_sent` before SDK invocation, otherwise per observed HTTP evidence |
| `provider_unavailable` | `sent` with HTTP evidence, otherwise `possibly_sent` after invocation |
| `provider_timeout` | `possibly_sent` after invocation without HTTP evidence |
| `malformed_provider_response` | `sent` after an observed response |

An error before dispatch resolves as `failed_before_send`. An error with confirmed
send evidence resolves as `failed_after_send`. A possible send, missing response,
parent timeout, or host failure resolves as unknown. Unknown Attempts consume budget.
Counts are per Attempt and derived from ledger facts. Result evidence takes precedence
when both a Result and a subsequent local failure exist for that Attempt.

The first Attempt requires no separate dispatch record. Another consumed Attempt
for the same key requires an unused owner authorization. Provider paid corrections
are forced to zero. Existing resource-ceiling checks prohibit provider recovery.
Recovery additionally checks that a historical local Task cannot select a provider Worker.
The pilot ceiling counts only Attempts in the selected transport mode across the ledger.

## NFL availability validation

The adapter validates frozen game/team metadata, expected-player scope, row ownership,
unique row IDs, timestamps, and the 24,000-character row-text cap before records are
created. It performs no acquisition or inference. Fixtures are the inputs in 6B.

The independent validator receives the exact frozen Snapshot through an opt-in
`requires_snapshot` hook. It enforces the nine ADR rules, including citation ownership,
governing-timestamp support, designation and practice supersession, cutoff handling,
null timestamps when evidence is absent, and the distinction between unknown and
unlisted. Conflict is evaluated once per player. The combined fixture preserves a
resolved designation while omitting an unresolved practice entry and retaining both
conflicting practice rows.

## Test evidence

Executed locally by ChatGPT on Linux, Python 3.12.14, in a dedicated virtual environment
with `anthropic==2.9.0` and `httpx2==2.16.2` installed.

`python -m unittest discover -s tests -v` runs **146 tests**.
The total is 128 existing tests plus eight provider cases against two ledgers (16),
one independent-validator case, and one standalone SDK probe. All 146 passed with
zero skips and zero failures on the final local run.
That run completed in 35.581 seconds. A separate optional-dependency check on the
system interpreter, with the SDK absent, ran the 18 provider cases with one
validator pass and 17 explicit SDK-dependent skips.

The 6B cases are P6-01, P6-03, P6-04, P6-05, P6-08, P6-09, P6-10, P6-11, P6-13,
and P6-16. Provider cases skip explicitly when the optional SDK is absent. Provider
cases use no platform-specific signals and are eligible on Windows when the SDK is
installed. Existing Phase 5 tests retain their four expected Windows signal skips.

The reported test execution was ChatGPT-local. Independent Windows execution of 6B: owner, Python 3.13.9,
146 run / 142 pass / 4 expected Phase 5 signal skips / 0 fail. The previous independent Phase 5 execution remains its own evidence.
Phase 2–5 test files remain byte-identical to the baseline. P6-16 pins the normalized
hash of `test_isolation.py`, extending the existing regression-file hash chain.

## 6C evidence

Provider tasks are non-recoverable in Phase 6. Existing fail-closed recovery preconditions retain their established ordering; `replay_policy='no'` may reject before the resource-ceiling check. ADR-010 does not require reordering those guards.

The 6C tests use only synthetic credentials and mock execution; neither live gate
nor live transport is selected. The live-mode record in P6-14 is a directly
appended accounting fixture, not an execution.

ChatGPT executed `python -m unittest discover -s tests -v` on Linux, Python
3.12.14, with `anthropic==2.9.0` and `httpx2==2.16.2`: **159 tests passed,
0 skips, 0 failures**, in 58.947 seconds. Execution used a clean environment
with no inherited credentials, live-mode configuration, or proxy settings.
Phase 2–5 test files are byte-identical to baseline `053137d`.

| Test | Claim |
|---|---|
| P6-02 | A missing credential invokes no SDK request, consumes no slot, permits a later attempt, and a successful synthetic-credential run persists neither the key nor canary fragments. |
| P6-06 | An SDK read timeout is uncertain dispatch without parent termination and prevents unauthorized redispatch. |
| P6-07 | A hung mock request is terminated by the parent, creates no late result, and consumes one uncertain slot. |
| P6-12 | Child sanitization removes the synthetic key, canaries, and authorization lines; independent local-Worker diagnostics prove parent pattern redaction and test-marker gating. |
| P6-14 | Bypassing the mock transport reaches the socket guard, closed gates prevent dispatch, budget exhaustion appends only its refusal fact, and mock/live accounting remains separate. |
| P6-15 | Startup delay exhausts the minimum SDK allowance before invocation, while the same declared deadline succeeds without delay. |
| P6-17 | A bare SQLite provider attempt consumes an uncertain slot before and after restart; interruption adds no invented dispatch observation, recovery is refused, and a second reopen appends nothing. |

Owner independently executed 6C on Windows with **159 run / 155 pass / 4 expected Phase 5 signal skips / 0 fail**. Claude review complete at eaaa192. No 6C test
adds a Windows skip; the four existing Phase 5 signal skips remain unchanged.
These tests do not prove that the account/model accepts the live request.
Only the separately owner-authorized 6D pilot can establish that.

## Implementation decisions recorded for review

- The registry uses an outer read-only mapping of immutable namedtuple descriptors,
  with nested prompt metadata frozen individually. Existing `freeze()` converts
  namedtuples to plain tuples, so applying it to the whole registry would remove
  the descriptor attributes. Shared `freeze()` behavior is preserved.
- Module-level dispatch accounting takes the ledger explicitly as an argument,
  `dispatches_consumed(ledger, task_key)`, instead of introducing implicit global state.
- Parent references use registered identities without importing provider classes.
  Provider task views in the child include the existing packet's `deadline_at` so
  the Worker can calculate its remaining budget. Envelope v1 gains no fields.
- Provider redispatch authorization is checked before the active-duplicate return.
  A previously consumed provider key without authorization is refused without writes.
  Local duplicate behavior remains governed by its existing path.
- P6-11 temporarily changes the same template file after parent hashing and before
  the real subprocess starts, using the existing private wait seam. It restores
  the file in `finally` and proves that independently observed child bytes disagree.
- P6-10 corrupts response bytes at the parent's parser boundary after real mock-SDK
  child execution. Process creation and the provider request path remain real.
- Practice evidence is grouped by a row's `report_date` or an explicit ISO date
  mentioned in its text. The fixtures use individual dated rows. Interpreting a
  live source's weekday columns belongs to the later acquisition work.

## 6D-prep

The designation-only Bears packet `TB-at-CHI-2026-11-08` contains three players
and three rows. Its SHA-256 is
`1ce3f332e1e8ff7aa113bbb0cd2688583086c29a050be909d9607e1a3c2c0aa6`.
Revision 10 records the owner's capture time separately from the nullable source
publication time. Each row uses the selected timestamp for cutoff and validation.
The expected output and [transcription provenance](../fixtures/nfl-availability/TB-at-CHI-2026-11-08.provenance.md)
accompany the packet.

The [Windows mock dry-run](pilot/6d-dry-run.md) invokes `scripts/pilot_dispatch.py`
with that packet and a dedicated SQLite ledger. The offline tests check the frozen
bytes, validate the hand-derived output, and exercise the runner's preconditions,
duplicate handling, owner-authorized redispatch and budget refusal. Mock results
establish no live account or model acceptance. Owner verified all rows 2026-11-18; Windows suite 162 run / 158 pass / 4 expected Phase 5 skips / 0 fail; owner mock dry-run exited 0 with pending_owner_approval. Claude-reviewed at ef54955; merged PR #17. Stage 6D was subsequently authorized, executed and accepted by the owner on 2026-11-27 following Dispatch #3.

## Dispatch #2 fix (Sprint 5)

Dispatch #2 reached the Messages API and received HTTP 400. The ledger retained
the SDK exception class and status. The coarse schema is the leading hypothesis
for the rejection. The provider's reason was not captured.

The NFL adapter owns the complete Worker output schema. Every object declares
its properties, requires every property, and rejects additional properties.
The child checks the schema before sending. The offline transport checks the
schema in the serialized request before returning a success fixture. P6-18
exercises both schemas through structural checks and sends the old schema
through the real SDK to the offline transport. The independent validator still
checks whether each player's output is supported by the frozen rows.

When available, the provider error type and message are sanitized before their
respective 100- and 500-character caps are applied in `error.detail`. P6-19
places a synthetic credential across the cap boundary. P6-20 checks that a
missing or invalid schema consumes zero dispatch slots.

Output schema canonical SHA-256 (sorted keys, compact separators): `bbefc6a8fce78143a8c0ff5eb918db4a43373af7bbe578348fca96f3dd47f41a`.

Mock mode now enforces Anthropic's documented structural rules for structured-output schemas. It still cannot prove that the live API accepts this schema; only a later owner-authorized dispatch can.

## Remaining stages

6C is accepted following Claude review and independent Linux and owner Windows execution.

6D is owner accepted following the separately authorized Dispatch #3, which established live acceptance once. No further dispatch is authorized. Stage 6E documentary grade and seven-count pilot report accepted by the owner on 2026-11-27 under ADR-010 revision 12. Phase 6 closed by owner on 2026-11-27; Foundation Exit remains held awaiting separate owner decision; NFL/agent implementation remains on HOLD. Currency reporting, provider replay, additional
providers, predictions, and later deployment features retain their ADR deferrals.
