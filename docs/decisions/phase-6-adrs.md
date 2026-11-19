# Phase 6 architecture decision records

Cyrus Ripley One (Ripley / R1) — Cyrus Forge Systems, LLC

These records continue [ADR-001 through ADR-006](phase-1-adrs.md), [ADR-007](phase-3-adrs.md), [ADR-008](phase-4-adrs.md), and [ADR-009](phase-5-adrs.md).

## ADR-010 — External provider Worker and paid-dispatch governance

Status: **ACCEPTED — revision 11 (Decisions 4 and 13 amended after 6D dispatch #2; Decision 14 evidence timestamps amended during 6D-prep; revision 9 amended during 6B) — drafted by Claude from the Phase 6 whiteboard; revised for thirteen Copilot corrections and three rounds of ChatGPT pre-commit findings; Decision 1 ruled by the owner 2026-11-17 after a read-only Models API confirmation; merged (PR #11 a7cbfd2; amended PR #13 200f3fc).**

Implementation status: **6B and 6C accepted (PR #12, PR #15). 6D NOT AUTHORIZED — requires a separate owner record before any live dispatch. 6E not started. No live API calls are authorized by this record.**

Recorded: 2026-11-17 · Revised: 2026-11-17
Baseline: `main` after PR #10 (Phase 5 accepted; independently executed on Windows).

### Context

Phases 1–5 built a domain-neutral core, durable append-only facts, explicit recovery, and isolated local Workers with enforceable deadlines. Every Worker so far has been local, deterministic, and free. Phase 6 introduces the first Worker that calls an external AI provider — the first time a Ripley attempt costs money, leaves the machine, and can end in a state Ripley cannot observe.

Owner decision (2026-11-17): **Ripley stays native.** No orchestration framework enters the control plane. Provider SDKs are used inside Workers, behind the Phase 5 execution envelope. Frameworks remain a reopen-on-evidence question, bounded inside a Worker if one ever earns its place.

> A paid dispatch is a fact Ripley must be able to count. Ripley never sends a second paid request on its own authority, and it never pretends to know a remote outcome it did not observe.

The Record Principle is unchanged: facts are durable; assessments are attributable; judgments are revisable; revisions supersede rather than erase; history remains auditable.

### Boundaries stated plainly

- **Money boundary.** At most one provider send per Execution Attempt. Automatic correction of a provider Worker's output is disabled (paid correction allowance is zero). A second paid dispatch for the same task key requires an explicit owner record.
- **Observation boundary.** Only the child knows whether bytes left the machine. The parent learns it from the child's response or not at all. Ripley distinguishes what the child *observed* from what Ripley can *conclude*.
- **Secret boundary.** Only provider-child application code intentionally reads the credential. The credential never enters Ripley protocol output, diagnostics, durable records, prompts, logs, or the repository. The child sanitizes everything it returns; the parent adds generic pattern masking. This is an application-level promise: on Windows and POSIX a child process inherits its parent's environment by default, so the parent *process* can technically see the variable — Ripley code never reads it. An OS-level parent-exclusion design (credential delivered to the child by a channel the parent never holds) is DESIGN FOR LATER, not required for a controlled local pilot.
- **Security boundary (ADR-009).** Subprocess isolation is crash/hang containment and deadline enforcement, not a sandbox. The provider Worker is first-party trusted code.
- **Pilot boundary.** One provider, one Worker class, one pinned SDK version, one exact model, one extraction task, at most 25 dispatches, behind two owner gates and a separate mock mode that cannot reach the network.

### Decision 1 — One provider for Phase 6

Phase 6 implements **exactly one** concrete provider Worker. The provider-neutral `ProviderWorker` contract is kept so a second provider is additive later; **no placeholder class for a second provider is created.**

**Owner decision, recorded 2026-11-17:**

| Item | Decision | Note |
|---|---|---|
| Provider | **Anthropic** | active account with promotional credit |
| Worker class | **`AnthropicWorker`**, identity `'anthropic-worker'` | — |
| SDK package and pinned version | **`anthropic==2.9.0`** | the mock transport/client mechanism this SDK supports is established by P6-16 as the first step of 6B. Mock-mode evidence proves serialization, request construction, response parsing, failure mapping, and Ripley integration against the real SDK code path; it does not prove the account or model accepts the live request. Only the owner-authorized 6D live pilot proves that. Recorded in `requirements-providers.txt` and on every attempt as `sdk: {package, version}` |
| Exact model identifier | **`claude-haiku-5-5`** | confirmed present in the account's `GET /v1/models` response on 2026-11-17 (read-only lookup; no message call) — evidence only that the model was available to the account at selection time. The owner-authorized 6D pilot verifies whether this account and model accept the exact request and schema |
| `max_output_tokens` | **1024** | — |
| Maximum frozen input size | **24,000 characters** of row text | adapter refuses larger packets at snapshot time |
| Attempt deadline (`timeout_seconds`) | **45** | — |
| SDK automatic retries | **0** | — |
| SDK timeout policy | per Decision 6 | — |
| Second provider | **deferred** | — |

The second provider Worker is **DEFERRED**, not designed in this record.

### Decision 2 — Worker descriptors: trusted parent-visible metadata

Ripley Core must distinguish local from provider execution **without importing any provider code**. A new module `ripley/workers.py` (imports nothing from `providers.py` or any SDK) holds a frozen registry of `WorkerSpec` descriptors:

```
WorkerSpec(identity, kind: 'local' | 'provider', response_envelope_version: '1' | '1.1',
           external_calls: 'no external calls' | 'provider', paid_correction_allowed: bool,
           provider: str | None, model: str | None, credentials_ref: str | None,
           prompt_ref: {name, version} | None)
```

`WORKER_SPECS` is trusted configuration. `run()` and `recover()` resolve `worker.identity → WorkerSpec`; an identity with no spec is refused (in addition to the existing allowlist). **A `kind == 'provider'` spec requires `execution == 'subprocess'`:** selecting a provider Worker with inline execution raises `ValueError('provider workers run only in subprocess execution')` before any record is appended, so provider SDK code can never execute inside the parent process. `recover()` may not switch a historical local Task to a provider Worker (the recovered attempt's `worker` must have the same `kind` as the original); provider tasks themselves remain non-recoverable through the ceiling gate. From the spec, Core: forces the correction budget to zero for `kind == 'provider'` (recording `correction_budget_forced: true` on the attempt); selects the expected response envelope version; applies pilot-budget checks; requires `dispatch` on the response; freezes `external_calls` and `dispatch_policy` onto the Task. `worker_host.py` maps the same identities to classes; the two registries are cross-checked by test (P6-16). Task input can never supply or override a spec.

### Decision 3 — `resource_ceiling` keeps its type; dispatch policy is a separate field

`resource_ceiling` remains the scalar used by Phases 2–5. Values: `'no external calls'` (unchanged) and, new, `'provider'`. The existing ADR-008 resource-ceiling check remains unchanged; a `'provider'` ceiling therefore makes the task non-recoverable through that check. (Decision 2 separately adds a Worker-kind compatibility refusal to `recover()`; the ceiling logic itself is not modified.)

Provider limits live in a **separate frozen Task field** copied from the spec at submission:

```
dispatch_policy: {max_dispatches_per_attempt: 1, paid_correction_allowed: false}
```

Local tasks carry `dispatch_policy: None`.

### Decision 4 — Credential resolution and the secret boundary

`credentials_ref` is on the `WorkerSpec` (parent-visible name only) and on the Worker class (used by the child). Resolution happens in the child, at dispatch time, from `os.environ[credentials_ref]`, after the live gate check and before client construction. The attempt records `credential_source: {ref: <name>, kind: 'env'}`. Missing or empty → child returns `error`, `provider_error: 'auth_unavailable'`, `dispatch.observation: 'not_sent'`, before any client exists.

**Child-side sanitization is the primary control.** Before writing any response or stderr, the child passes every string it emits (error messages, SDK exception text, provider error bodies, tracebacks, diagnostics) through a sanitizer that (a) removes the full credential, (b) removes configured synthetic canary fragments of at least eight characters supplied only in test mode, and (c) strips authorization headers and known provider-key patterns from any request/response material it reports. The child never returns the secret, a prefix, a hash of it, or any value derived from it. **There is no `redaction_prefix` field.** Tests verify that neither the full synthetic credential nor the designated canary fragments cross stdout/stderr or enter any persisted field.

**Parent-side redaction is generic defense in depth only:** `ripley/isolation.py` masks known credential *patterns* (`sk-ant-…`, `sk-…`, `Bearer …`, 40+ character base64/hex runs adjacent to `key`/`token`/`authorization`) and the explicit synthetic test marker. Ripley parent code never reads the credential variable and never receives information about the secret from the child.

### Decision 5 — Provider Worker contract and SDK configuration

`ProviderWorker` (base) and `AnthropicWorker` live in `ripley/providers.py`, imported only by `worker_host.py`. `produce()` builds the request from the frozen packet, renders the prompt template, checks the live/mock gate (Decision 11), resolves the credential, constructs the SDK client **once** with `max_retries = 0`, the SDK timeout from Decision 6, and `max_output_tokens` from the spec; calls the SDK **once**; returns the structured output. Structured output is requested through the provider's native JSON-schema mechanism using the adapter-owned `output_schema`: a complete JSON Schema of the adapter's Worker output in which every object declares its `properties`, lists all of them as `required`, and sets `additionalProperties: false`, using only schema keywords the provider documents as supported. An adapter without `output_schema` cannot be dispatched (`invalid_request`, `not_sent`). The schema constrains shape only; independent validation still decides correctness. (Dispatch #2 sent a coarse schema derived from the `expected_output` type map and was rejected by the live API with HTTP 400. The provider's reason was not recorded, so the schema is the leading but unconfirmed cause. Independently of that, the provider documents that an object without declared properties can only yield an empty object, so the coarse schema could not have produced the required output.) No retries, no fallbacks, no second model.

### Decision 6 — Deadline and SDK timeout contract

- The Execution Attempt deadline (`deadline_at`, real UTC, ADR-009) is authoritative. The parent's terminate → grace → kill path is an **expected and tested fallback**, not an edge case.
- Provider adapters **must** declare `timeout_seconds ≥ 10`; `run()` rejects a provider task otherwise (P6-01).
- Constants: `PARENT_CONTROL_RESERVE_SECONDS = 3.0` (= `TERMINATION_GRACE_SECONDS + WATCHDOG_MARGIN_SECONDS`), `MIN_SDK_TIMEOUT_SECONDS = 5.0`.
- At dispatch time the child computes `remaining = deadline_at − now_utc` (after startup, packet parsing, prompt rendering) and `sdk_timeout = remaining − PARENT_CONTROL_RESERVE_SECONDS`. If `sdk_timeout < MIN_SDK_TIMEOUT_SECONDS`, the child returns `not_sent` with `provider_error: 'insufficient_time'` **before** invoking the SDK.
- A provider SDK timeout proves nothing about the provider: the request may complete server-side. An SDK timeout therefore maps to `provider_timeout` with `dispatch.observation: 'possibly_sent'` → `remote_outcome: 'unknown'`.
- No statement in this record or the docs may claim that the shorter SDK timeout guarantees a child response before the parent deadline.

### Decision 7 — Response envelope version 1.1 (provider responses only; strict)

Request envelope stays `'1'`. Provider Workers respond with `envelope_version: '1.1'`, which adds one mandatory object to **both** `ok` and `error` responses:

```
dispatch: {
  observation: 'not_sent' | 'sent' | 'possibly_sent',
  provider, model, sdk: {package, version},
  provider_request_id: str | null,
  sent_at: ISO-8601 UTC | null,
  usage: {input_tokens, output_tokens, cache_read_tokens | null} | null,
  prompt_ref: {name, version, content_hash}
}
```

**`observation` is fixed by the child under these rules, and only these:**
- `not_sent` — dispatch was impossible by construction: live gate closed; credential missing/empty before client construction; local request or schema construction failed before the SDK was called; insufficient time (Decision 6); or, in mock mode, the trusted mock transport proves zero requests were received.
- `sent` — the provider returned an HTTP response of any status, **or** a provider request identifier is known.
- `possibly_sent` — the SDK network call was invoked and neither of the `sent` proofs exists. Connection errors, resets, write/read timeouts, TLS failures, and any other transport exception after invocation are `possibly_sent`. **`not_sent` is never inferred from an exception type once the SDK call has been invoked.**

**Version compatibility is strict:** the parent expects the version named by the `WorkerSpec`; a local Worker responding `'1.1'`, a provider Worker responding `'1'`, or any `'1.1'` response lacking a well-formed `dispatch` object → `host_failure` (`'unsupported envelope version for worker class'`). No field of `'1'` changes meaning.

### Decision 8 — `remote_outcome` is derived by the parent

| Evidence | `remote_outcome` |
|---|---|
| `ok` response | `completed` |
| `error`, `observation = not_sent` | `failed_before_send` |
| `error`, `observation = sent`, provider error class present | `failed_after_send` |
| `error`, `observation = possibly_sent` | `unknown` |
| no parseable response (parent timeout/kill, host_failure, restart interruption) | `unknown` |

A parseable child error does **not** by itself resolve the outcome. Fail closed: `unknown` consumes dispatch budget everywhere.

### Decision 9 — Dispatch accounting, zero paid correction, owner-authorized redispatch

- The Execution Attempt is the authorization for one dispatch; no separate first-dispatch record.
- `dispatches_consumed(task_key)` = count of provider **Execution Attempts** (never Result or Failure records, so an attempt that produced more than one durable fact is charged once) across the key's lineage that are **not** resolved as `failed_before_send`. **Any provider attempt lacking a Result or Execution Failure with a resolved `remote_outcome` is treated as `unknown` for accounting and consumes one dispatch slot** — this covers a crash after attempt creation, after `execution_request`, or during provider execution. Derived on every call; never stored; never dependent on a null-comparison quirk.
- **Correction budget is zero for provider Workers** (forced from the spec; recorded as `correction_budget_forced: true`). Failed validation blocks the task.
- **Recovery is unavailable** to provider tasks by ADR-008's ceiling gate; the existing resource-ceiling logic is unchanged, and the only addition to `recover()` is Decision 2's Worker-kind refusal. Recovery (execution-safety) and redispatch (spending) are deliberately separate owner acts.
- **Second paid dispatch requires `dispatch_authorization`**: `{task_key, prior_attempt_id, prior_remote_outcome, actor: 'owner', reason}`. `run()` for a provider task refuses whenever `dispatches_consumed(task_key) ≥ 1` unless an unconsumed authorization exists for the key; the next attempt records `dispatch_authorization_id`, consuming it. One authorization = one additional attempt. Ripley never writes this record itself.

### Decision 10 — Usage now, dollars later

Results and failures carry `dispatch.usage`, `provider_request_id`, `sdk`, and `model`. There is **no** `send_count` field: `dispatch.observation` (`not_sent | sent | possibly_sent`) is the single representation of whether a send occurred, and accounting is Attempt-based (Decision 9). **Ripley records no currency amounts in Phase 6.** A `price_table` record kind and cost-on-read reporting are DESIGN ONLY, deferred until pilot usage exists. No hardcoded price table may appear in `ripley/`.

### Decision 11 — Provider transport modes and pilot gates

Two explicit, mutually exclusive modes, selected by trusted environment configuration read by the **child**, never by task input:

| Mode | Selected by | Transport | Network |
|---|---|---|---|
| **mock** | `RIPLEY_PROVIDER_TRANSPORT=mock` **and** `RIPLEY_ENABLE_TEST_WORKERS=1` | real SDK client constructed with an injected mock transport/client **compatible with and supported by the pinned `anthropic==2.9.0` SDK** (the exact injection mechanism is established by the first 6B test, not assumed here); scripted by `RIPLEY_MOCK_PROVIDER_SCRIPT` (e.g. `200:valid`, `401`, `429`, `500`, `reset_after_write`, `read_timeout`) | **forbidden**: before importing the SDK the child installs a socket guard that makes any real connection attempt raise; P6-14 proves it |
| **live** | `RIPLEY_PROVIDER_TRANSPORT=live` **and** `RIPLEY_LIVE_DISPATCH=1` | real transport | allowed, within pilot budget |
| neither / inconsistent | — | — | child returns `not_sent`, `provider_error: 'live_gate_closed'`, before client construction |

Unit tests never set `RIPLEY_LIVE_DISPATCH`. The parent records `transport_mode` and `{name, present}` for each gate variable on the attempt — never values.

**Pilot budget:** `RIPLEY_PILOT_DISPATCH_BUDGET` (pilot value **25**), read by the parent; before creating a provider attempt the parent counts **live-mode** provider attempts (attempt records carry `transport_mode`) that are not `failed_before_send`, and at or above budget appends `pilot_budget_exhausted {budget, consumed}` and raises. Mock-mode attempts never count toward the live budget; in mock mode the same check logic runs against mock attempts with a test-supplied budget (P6-14).

### Decision 12 — Prompt as a fact

Every provider attempt records `prompt_ref: {name, version, content_hash}`. Templates live in `ripley/prompts/<name>/<version>.md`; the child reports the hash of the template it rendered from; a test verifies it against the repository file (P6-11). The parent computes `content_hash` from the repository template before appending the Attempt; the child reports the hash it rendered from in `dispatch.prompt_ref`; a mismatch is a `host_failure` with `remote_outcome: 'unknown'`.

### Decision 13 — Provider error normalization

Exactly nine Ripley classes in `error.type` / `provider_error`:

`live_gate_closed` · `auth_unavailable` · `insufficient_time` · `auth_rejected` · `rate_limited` · `invalid_request` · `provider_unavailable` · `provider_timeout` · `malformed_provider_response`

(The first three are always `not_sent`; the rest follow Decision 7.) A model refusal or off-schema answer is an `ok` response that fails validation. Provider-specific exception names, HTTP statuses, and the provider's own error type and message are kept under `error.detail` for diagnostics only. The provider message is sanitized first and length-capped second, so truncation can never expose part of a secret.

### Decision 14 — First NFL task: frozen player-availability evidence packet

**Scope.** Extraction with deterministic, field-level support checking against frozen evidence. No prediction, no odds, no market data, no network in the Worker.

**Snapshot inputs** (`NflAvailabilityAdapter`, domain `nfl-availability`, version `'1'`, `replay_policy: 'no'`, `timeout_seconds: 45`):

```
{
  game_id, team, cutoff_at,
  source_published_at,          # ISO-8601 UTC or null
  observed_at,                  # ISO-8601 UTC, required
  evidence_at_basis,            # 'source_published_at' | 'observed_at'
  expected_players: [ { player_id, name, team, position } ... ],
  rows: [ { row_id, player_id, name, team, position, evidence_at,
            source: 'nfl.com-injury-report', report_date, text } ... ]
}
```

**The evidence unit is the structured injury-report row, bound to exactly one `player_id`** — not a free-text passage that may name several players. Acquisition produces rows deterministically from the report table; `expected_players` is the set of distinct `player_id`s across rows and is the only basis for completeness. Field-level support therefore always points at evidence already scoped to one player, and the validator never has to decide which player a sentence is about. A row's `text` is the normalized row content (status, practice cells, notes) verbatim.

**Evidence timestamps.** Three times are kept distinct and none is ever inferred from another. `source_published_at` is the publication time the source itself states; it is `null` when the source exposes none — it is never estimated, back-filled from another page, or replaced by a league reporting deadline or filing policy, which may be recorded in provenance as context only. `observed_at` is the exact time the owner (or, later, Ripley) captured the evidence; it is required, must come from a recorded capture time (a file's recorded timestamp or a time written down at capture), and is never reconstructed from recollection. `evidence_at` on every row is the single timestamp the validator orders and cutoff-filters by; `evidence_at_basis` names which packet field it was copied from, and the adapter rejects a packet whose rows' `evidence_at` differ from that field or whose basis field is `null`. A single-snapshot packet (every row from one capture of one source) has `cutoff_at == evidence_at` on every row; `report_date` is the only per-row calendar distinction. Multi-source packets with differing `evidence_at` per row are permitted by the validator rules below but are DESIGN FOR LATER. Rows may be produced by deterministic acquisition or, for a frozen pilot packet, by owner-verified manual transcription recorded in provenance; a row whose `report_date` the source does not establish is omitted, never dated by assumption.

**Worker output** (`expected_output`), one entry per `expected_players` member:

```
{ players: [ {
    player_id,
    designation: { value: 'out' | 'doubtful' | 'questionable' | 'unlisted' | 'unknown',
                   support: [row_id ...] },
    practice: [ { date: 'YYYY-MM-DD', status: 'full' | 'limited' | 'dnp',
                  support: [row_id ...] } ... ],
    supersession: [ { field: 'designation' | 'practice:<date>',
                      governing: row_id, superseded: [row_id ...] } ... ],
    conflict: { flag: bool, support: [row_id ...], note: str },
    as_of: ISO-8601 UTC | null
} ] }
```

Designation semantics: `out`/`doubtful`/`questionable` are official game-status designations that must be supported verbatim; `unlisted` means the player is in `expected_players` and a cited row lists them **without** a game-status designation (practice-only row); `unknown` means no cited row supports any designation **and no unambiguous supported designation exists in the player's rows** — `unknown` is a failure when the rows do support one. `as_of` is `null`, never invented, for a player with no qualifying evidence. **There is no `active` value: absence from a row never establishes availability.**

**Independent validation** (`AvailabilityValidator`, deterministic, no model), **field by field, across all frozen rows:**

1. `players` contains each `expected_players.player_id` **exactly once** and no other id.
2. Every `row_id` in any `support`, `governing`, or `superseded` list exists in the packet.
3. **Ownership:** every cited row's `player_id` equals the entry's `player_id`. Cross-player citation fails regardless of text content.
4. **Designation is determined by this precedence, in order:** (a) consider only the player's rows with `evidence_at ≤ cutoff_at`; (b) among those, find the latest `evidence_at` at which any row states an explicit game designation (`out`/`doubtful`/`questionable` or NFL.com abbreviation) — a practice-only row never supersedes an earlier explicit designation merely by being newer; (c) if exactly one designation is stated at that latest timestamp, it governs: `designation.value` must equal it, `designation.support` must cite **at least one row from that governing timestamp** and may cite only rows agreeing with the governing value; (d) if more than one designation is stated at that same latest timestamp, the tie is unresolvable: `designation.value` must be `unknown`, all conflicting rows are added to `conflict.support`, and `conflict.note` is non-empty (the flag itself is set per rule 9); (e) if no row states any designation but at least one row lists the player, `unlisted` with `support` citing such a row; (f) if no qualifying row exists for the field, `unknown` with empty `support`; the field contributes nothing to `conflict`. **`unknown` is invalid whenever (c) applies.**
5. Each `practice` entry has **non-empty** `support`; `date ≤ cutoff_at`; the status word appears in **each** cited row; each cited row's `report_date ≥ date`. For a given practice `date`, the latest `evidence_at` row stating a status for that date governs; if rows at that same latest `evidence_at` state **different** statuses for the same date, the practice entry for that date is **omitted** from `practice`, the conflicting rows are added to `conflict.support`, and `conflict.note` names the date (the flag itself is set per rule 9). A `practice` entry for a date with equal-timestamp conflicting evidence is a validation failure.
6. **Supersession records are consistent with rule 4:** when rule 4(c) governs and an earlier row stated a different designation, that earlier row must appear under `supersession` with `field: 'designation'` and `governing` = a row at the governing timestamp. Under rule 4(d) no `supersession` entry for `designation` is permitted. For `practice:<date>` fields, a later-timestamp row superseding an earlier different status is recorded under `supersession` with `field: 'practice:<date>'`; equal-timestamp practice conflicts follow rule 5 (omit the entry, record under `conflict`) and never appear under `supersession`.
7. `as_of` equals the maximum `evidence_at` among all rows the entry cites for any field and is `≤ cutoff_at`; if the entry cites no rows (every field resolved by rule 4(f)), `as_of` is `null` — never invented.
8. `unlisted` and `unknown` are distinct and are never interchangeable under rules 4 and 6.
9. **Player-level conflict semantics.** `conflict` is evaluated **once per player, after every field for that player has been evaluated under rules 4–8**. `conflict.flag = true` if and only if **any field** (designation under rule 4(d), or any practice date under rule 5) has an unresolved equal-timestamp conflict among rows eligible by `cutoff_at`; otherwise `conflict.flag = false` with empty `conflict.support`. `conflict.support` is the union of the conflicting rows from every such field, and `conflict.note` identifies each conflicting field (and the date for a practice field). A resolved supersession in one field never forces `conflict.flag = false` while an unresolved conflict exists in another field for the same player. Combined case: a designation resolved by rule 4(c) with an earlier differing row **and** an equal-timestamp practice conflict on some date → the governing designation and its `supersession` record are preserved, the disputed practice entry is omitted, the conflicting practice rows appear in `conflict.support`, `conflict.note` identifies the disputed practice date, and `conflict.flag = true`.

Any failed rule → validation failure → task blocks (no paid correction). The validator reports rule number, player_id, and field.

### Decision 15 — Owner pilot grading is a distinct review purpose

Pilot grading uses the existing `review` record kind with mandatory `purpose: 'pilot_quality_grade'` and fields `{result_id, snapshot_id, rubric: {name: 'availability-pilot', version: '1'}, grader: 'owner', field_assessments: [{player_id, field, correct: bool, note}], notes}`. Policy reviews carry `purpose: 'policy'` (added to existing writes, additive). Owner approval, Validation, policy Review, and pilot grading are four different records and are never counted as one another. Prediction-outcome grading is a future record (Phase 7 candidate).

### Decision 16 — Pilot reporting

The 6E report states seven counts **separately**, all counted over live-mode provider **Attempts**, and never collapses them: **attempted** (attempts created) · **confirmed_sent** (`observation = sent`) · **uncertain_dispatch** (`possibly_sent`, or no resolved response/outcome) · **budget_slots_consumed** (everything except definitive `failed_before_send`) · **completed** (`remote_outcome = completed`) · **validated** (all validation rules passed) · **owner_graded** (a `review` with `purpose = 'pilot_quality_grade'` exists). Plus latency distribution and `usage` totals. No dollar figure.

### Phase 6 sequencing and gates

| Stage | Content | Paid calls |
|---|---|---|
| 6A | This ADR accepted with the Decision 1 table filled by the owner | none |
| 6B | `workers.py` specs; `providers.py` with `ProviderWorker` + the one concrete Worker; envelope 1.1; `remote_outcome`; dispatch accounting; `dispatch_authorization`; `NflAvailabilityAdapter`; `AvailabilityValidator`; prompt template; **mock mode only** | none |
| 6C | Secret-sanitization, timeout-budget, restart-during-dispatch, gate-separation, socket-guard tests | none |
| 6D | Owner sets `RIPLEY_ANTHROPIC_API_KEY` as a Windows **User** environment variable (not session-only, not inside the Claude app), opens live mode; ≤ 25 dispatches | yes, gated |
| 6E | Seven-count report; owner grades each completed Result | none |

Only after 6E does any provider Worker touch a prediction task.

### Acceptance (required tests, preserved by number in the implementation assignment)

| # | Required test |
|---|---|
| P6-01 | Provider task with no `timeout_seconds` or `timeout_seconds < 10` → `run()` raises; no records |
| P6-02 | Credential env var missing → `error`, `auth_unavailable`, `not_sent`, `failed_before_send`; a recursive scan of every persisted field finds neither the full synthetic credential nor any configured canary fragment (≥ 8 chars) of it |
| P6-03 | Mock `200:valid` → `ok`, `sent`, `usage` + `provider_request_id` on the Result, `completed`, validation runs |
| P6-04 | Mock `401` / `400` / `429` / `500` → `auth_rejected` / `invalid_request` / `rate_limited` / `provider_unavailable`, each `sent`, `failed_after_send`, blocked; the mock transport saw exactly one request per attempt |
| P6-05 | Mock `reset_after_write` → `possibly_sent`, `unknown`, despite a parseable child error |
| P6-06 | Mock `read_timeout` → child reports `provider_timeout`, `possibly_sent`, `unknown`; `termination` absent |
| P6-07 | Child sleeps past deadline after a mocked send → parent kill path; `termination` present; `remote_outcome = unknown` |
| P6-08 | Second `run()` on the same key after `sent`/`possibly_sent`/`unknown` → refused, no records; after owner `dispatch_authorization` → one attempt, authorization consumed; third `run()` refused |
| P6-09 | Provider task validation failure → blocked, `correction_budget_forced: true`, no second attempt; `recover()` refused by the ceiling gate; **`run(worker=AnthropicWorker(), execution='inline')` raises before any record; `recover()` of a historical local task with a provider Worker raises before any record** |
| P6-10 | Envelope strictness: local `'1.1'`, provider `'1'`, or `'1.1'` without `dispatch` → `host_failure` |
| P6-11 | `prompt_ref.content_hash` equals the repository template's hash |
| P6-12 | Mock error body and a planted traceback contain the full synthetic credential, two configured canary fragments, and an `Authorization:` header; the child's response and stderr contain none of them; the parent's pattern redaction additionally masks a planted `sk-ant-…` string written directly to stderr by the test worker |
| P6-13 | Validator: each of the nine rules with one pass and one fail fixture; ownership fixture (row for player B cited under player A fails even though the text contains A's name and 'out'); `unknown`-with-supported-designation fails; practice entry with empty `support` fails; `as_of` invented for a player who has rows but no qualifying evidence for any field fails, `null` passes; practice-only newer row does not supersede an earlier explicit designation; a governing designation whose `support` cites only an older agreeing row (none from the governing timestamp) fails, and the same with one governing-timestamp row passes; latest-timestamp designation tie → `unknown` + `conflict` passes, and `unknown` with a single governing designation fails; equal-timestamp conflicting practice statuses for one date → entry omitted with rows in `conflict.support` and the date in `conflict.note` passes, while including that practice entry fails; supersession (later governs, `conflict false`) and tie (`conflict true`, `unknown`) fixtures; **combined case** (resolved designation supersession plus an equal-timestamp practice conflict for the same player): governing designation and its `supersession` record preserved, disputed practice entry omitted, conflicting practice rows in `conflict.support`, date in `conflict.note`, `conflict.flag = true` passes, while the same entry with `conflict.flag = false` fails; completeness (missing and extra player both fail) |
| P6-14 | Gates: mock mode with the socket guard → any real connection attempt raises inside the child and surfaces as `host_failure`, proving no network; live gate absent → `live_gate_closed`, `not_sent`, zero transport requests; budget 2 → third attempt appends `pilot_budget_exhausted` and raises; mock attempts do not count toward the live budget |
| P6-15 | Insufficient time: deadline such that `remaining − 3.0 < 5.0` at dispatch → `insufficient_time`, `not_sent`, SDK never invoked |
| P6-16 | **First 6B test:** the pinned `anthropic==2.9.0` client accepts the injected mock transport/client, the real request path reaches it, exactly one request is observed, retries are disabled, and no socket opens. `workers.WORKER_SPECS` and `worker_host.WORKERS` agree on identities and envelope versions; no module outside `providers.py` and `worker_host.py` imports the provider SDK; Phase 2–5 suites unchanged (hash guards extended to `test_isolation.py`); `ALLOWED_TRANSITIONS` unchanged |
| P6-17 | SQLite restart during a provider attempt → failure carries `remote_outcome = unknown`; `recover()` refused; `dispatches_consumed` counts it. Also: an attempt record with **no** failure or result at all (crash before reopen classification, simulated by direct ledger construction) counts as one slot. For that single unresolved live attempt the report counts are exactly `confirmed_sent = 0`, `uncertain_dispatch = 1`, `budget_slots_consumed = 1` |

### Implementation contracts (resolved at drafting)

1. **Observation mapping lives in one function** in `providers.py`, keyed on *where* in `produce()` the failure occurred (before client / before call / after call) first and on exception class second; tested per class.
2. **`dispatches_consumed`, pilot budget, and authorization consumption are derived from records on every call**; never cached. An attempt with no resolved `remote_outcome` counts as `unknown` (one slot) — implement as an explicit branch, not as `!= 'failed_before_send'`.
3. **Correction budget forcing** reads `WorkerSpec.paid_correction_allowed`, never `isinstance`.
4. **Record order on a provider attempt**: `execution_attempt` → `execution_request` → (child) → `result` or `execution_failure` (with `dispatch`, `remote_outcome`, `provider_error`, `usage`) → existing validation/review/approval or block. New record kinds: `dispatch_authorization`, `pilot_budget_exhausted`; `price_table` is DESIGN ONLY.
5. **Envelope 1.1 is response-only**; the host chooses the response version from the Worker class; the parent checks it against the spec.
6. **Mock transport, not mock Worker**: the real SDK client runs against a mock transport/client the pinned SDK supports; mocking `produce()` is not acceptance evidence. The first 6B test establishes that `anthropic==2.9.0` accepts the injected transport, that the real request path reaches it, that exactly one request is observed, that retries stay disabled, and that no real socket can open. **Evidence claim is bounded:** mock mode proves serialization, request construction, response parsing, failure mapping, and Ripley integration; only the owner-authorized live pilot proves that the account and model accept the exact live request and schema.
7. **Socket guard in mock mode** is installed in the child before the SDK import and is itself tested (P6-14).
8. **ADR-009 proof-of-death is unchanged and insufficient** for provider tasks: it proves the child is dead, not that the request did not complete. Hence `unknown` plus owner-only redispatch.
9. **Policy reviews gain `purpose: 'policy'`** additively; no existing test body changes because none asserts the absence of that key (verify in 6B; if one does, stop and report).

### DESIGN ONLY

OS-level parent-exclusion credential delivery (a channel the parent process never holds); `price_table` and cost-on-read reporting; `remote_outcome_resolution` (owner later confirms a provider-side outcome from the provider console — a judgment superseding `unknown`, never rewriting the fact); provider-side idempotency keys; a second concrete provider Worker; a second prompt version with A/B grading; non-environment credential resolvers.

### DEFERRED

Any prediction task; odds or market data in a provider task; The Odds API or any network fetch inside a Worker; more than one model, Worker class, or SDK version in the pilot; automatic retries at any layer; streaming; tool use; RAG; multi-turn; frameworks (reopen-on-evidence); NFL outcome grading/postmortem records; concurrency; cloud deployment; dollar accounting.

### Compatibility with ADR-007/008/009

- Ledger interface, table, INSERT-only rule, hash verification: unchanged.
- `ALLOWED_TRANSITIONS`: unchanged. Provider failures use existing stages plus `provider_error`.
- ADR-008's resource-ceiling check is relied upon, not altered: `resource_ceiling: 'provider'` ≠ `'no external calls'` → non-recoverable. `recover()` gains exactly one new precondition (Decision 2, Worker-kind compatibility) and no other change.
- ADR-009 request envelope v1 frozen; response gains an additive `'1.1'` for one Worker class; Phase 5 test worker, gates, and seam reused for process-level faults.
- `resource_ceiling` keeps its scalar type; provider limits live in the new `dispatch_policy` field.

### Consequences and evidence boundary

Ripley gains its first Worker that spends money and leaves the machine, with every send countable, every unknown outcome named, credential material never entering Ripley protocol output, diagnostics, durable records, prompts, logs, or the repository (only provider-child application code intentionally reads it), and no second paid request without an owner's signature in the ledger. The first NFL task is an extraction task whose correctness a deterministic validator establishes field by field against a frozen subject scope. Prediction waits until the provider pipeline has a measured record.

This record authorizes no implementation and no live calls. Maturity remains prototype-level; nothing here is production validated.
