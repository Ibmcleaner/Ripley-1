# FI-001 — Anthropic Messages API HTTP 400 (`invalid_request`) on Phase 6D dispatch #2

Cyrus Ripley One · Cyrus Forge Systems, LLC · Failure Intelligence record 001
Prepared by Claude (architecture lead) from owner-supplied evidence; reviewed by Copilot and ChatGPT; accepted by Robert Legorreta (owner).
Record opened 2026-11-19. Baseline `main` 9e3bc51.

## Status

| Question | Status |
|---|---|
| Defect repaired | **YES — PROVEN** (a real defect against the provider's documented rules; fixed in Sprint 5, verified offline) |
| Historical incident attributed to that defect | **NO — UNCONFIRMED** (leading hypothesis only) |
| Recovery verified against the live provider | **YES — OBSERVED ONCE** (dispatch #3, 2026-11-27, returned a result that passed the existing validator; subsequently governed owner-approved; documentary field-level judgments given under revision 12) |
| Provider support | Owner-reported reply 2026-11-24: original error text unavailable, conversation 215476929378097 |

Every statement below carries one of four evidence levels. **Observed**: recorded by Ripley or seen directly by the owner. **Reconstructed**: produced offline by running Ripley's real request-construction code against an in-memory mock transport; it shows what the code builds, not what crossed the wire on the night. **Documented**: stated in the provider's published documentation on 2026-11-19. **Inferred**: reasoning from the other three.

## 1. Failure signature (observed)

| Field | Value |
|---|---|
| Incident | Phase 6D live dispatch #2, authorized by `docs/decisions/phase-6d-authorization-02.md` |
| Provider request id | `req_011ChBm8QrsiEErhYw6LkrRD` |
| `dispatch.sent_at` | `2026-11-19T05:48:57.512673+00:00` (2026-11-18 11:48:57 PM CST) |
| Task `running → blocked` | `2026-11-19T05:48:58.225582+00:00` |
| HTTP status / SDK exception | 400 / `BadRequestError` |
| Ripley classification | `provider_error: invalid_request` · `observation: sent` · `remote_outcome: failed_after_send` |
| Retries | 0 |
| Model output | none |
| Ledger | `pilot/6d-dispatch-02.sqlite`, SHA-256 `ebd8fda51c510d457c0cfb2de2cff743302fe260dd145d0fa3862f154ad051dd` |
| Provider's own error type and message | **not recorded** — at that commit Ripley stored only the exception class and status |

Full closeout: `docs/pilot/6d-dispatch-02.md`.

## 2. Environment (observed)

Execution commit c44e379 (code identical to reviewed ef54955) · Windows, Python 3.13.9 · `anthropic==2.9.0` from `.venv6` · model `claude-haiku-5-5` · `max_tokens` 1024 · `max_retries` 0 · frozen packet `fixtures/nfl-availability/TB-at-CHI-2026-11-08.json` (SHA-256 `1ce3f332e1e8ff7aa113bbb0cd2688583086c29a050be909d9607e1a3c2c0aa6`) · prompt `nfl-availability/1` (SHA-256 `7d5094d53f2e1f4924b1daa727a7fb7563048743082306908825604d3da06904`).

## 3. Request fingerprints (reconstructed)

Four offline reconstructions were run with the procedure in Appendix A: the historical commit and current `main`, each on Linux (Claude) and on the owner's Windows machine. Canonical hashes are SHA-256 over `json.dumps(value, sort_keys=True, separators=(',', ':'))` encoded as UTF-8. The raw-body hash is SHA-256 over the exact bytes the SDK handed to the transport.

| Item | Historical request (c44e379) | Current request (9e3bc51) |
|---|---|---|
| Method and path | `POST /v1/messages` | same |
| Body keys | `max_tokens`, `messages`, `model`, `output_config` | same |
| Model / `max_tokens` | `claude-haiku-5-5` / 1024 | same |
| Messages | 1 user message, string, 3,106 characters | same |
| Messages canonical hash | `6c528d5d4cb157d3c37c5d7adda63bda853f52574e8233d6fbb82c1f34ab6384` | **identical** |
| Output-schema canonical hash | `3c3efcd462345d68f1a982e88dcef2c4cda68e9ad08898957a70b398b9911bf5` | `bbefc6a8fce78143a8c0ff5eb918db4a43373af7bbe578348fca96f3dd47f41a` |
| `output_config` canonical hash | `c523221dc15dcd46b05fe17efc0a7fe84c015071fd918692b1ab3fe809c8bf75` | `bc890dd45f64adbec90669e9efab3ae59bb5a1d50759055ead47f38d18a7d3b8` |
| Body canonical hash | `138976b487bb9ba284fe6c8f9f2b69569c3642bfed707c74f0f7ba4731181e34` | `b0cfac4f2f94aa928f68dfe8df4f22cd9e1cc3e1db7941963c7087f8baf2f0be` |
| Raw body | 3,597 bytes, `c91106744618adda9588e95cd8a950b02c9974c90ede837ab77f4bdb994e2990` | 4,805 bytes, `037e813693e8bbdd1e6bb6ad0a843c233fa5b8ef3472031f5e2dd5baade737e7` |
| Linux vs Windows | byte-identical | byte-identical |
| SDK-set headers | `anthropic-version: 2026-10-21`, `user-agent: Anthropic/Python 2.9.0`, authentication as `Authorization: Bearer` (no `x-api-key` header) | same |

**Finding (reconstructed):** the output schema is the only material difference between the reconstructed request body at dispatch #2 and the reconstructed request body Ripley builds today.

The historical schema declared each item of `players` as `{"type": "object"}` with no `properties`, no `required`, and no `additionalProperties`.

## 4. Provider rules consulted (documented, 2026-11-19)

- Structured outputs: `additionalProperties` "must be set to `false` for objects"; an object schema without declared properties can only yield an empty object; unsupported schema features return "a 400 error with details"; no beta header is required; the feature is listed for all models.
- API errors: 400 `invalid_request_error` covers the format or content of the request, and is also returned when usage reaches an organization or workspace spend limit the customer set; billing problems are 402 `billing_error`; 401 is an API-key problem; 403 is a permission problem; 404 is a missing resource. Every response carries a `request-id`, to be quoted to support.

Sources: `https://platform.claude.com/docs/en/build-with-claude/structured-outputs`, `https://platform.claude.com/docs/en/api/errors`.

## 5. Fault tree

| # | Candidate cause | Evidence | Level | Classification |
|---|---|---|---|---|
| 1 | Historical schema: `players` items declared as a bare object | Violates the documented `additionalProperties: false` rule; only body difference from the current request | reconstructed + documented | **PROVEN DEFECTIVE** against the documented rule. As the cause of the historical 400: **PLAUSIBLE / UNPROVEN** |
| 2 | Model identifier | `GET /v1/models/claude-haiku-5-5` returned 200 with the same credential between 33 and 43 minutes earlier (`req_011ChBiTetuYkBFBxdVnmWg1`) | observed | PROVEN COMPLIANT |
| 3 | `max_tokens` | 1024 | reconstructed + documented | PROVEN COMPLIANT (by documentation) |
| 4 | Message format or size | One user message, plain string, 3,106 characters | reconstructed + documented | PROVEN COMPLIANT (by documentation) |
| 5 | `output_config` name or shape | Matches the documented `format` / `json_schema` / `schema` form | reconstructed + documented | PROVEN COMPLIANT (by documentation) |
| 6 | Stray or unknown body fields | Exactly four body keys | reconstructed | DISPROVEN |
| 7 | Malformed JSON or encoding | SDK-serialized, parses, byte-identical on two platforms | reconstructed | DISPROVEN |
| 8 | Authentication | Dispatch #1 with an incomplete credential returned 401; this request returned 400 | observed + inferred | DISPROVEN |
| 9 | Billing or credit balance | Billing errors are 402; the ledger recorded 400; balance was $20.00 with auto-reload on | observed + documented | DISPROVEN |
| 10 | Workspace spend limit reached | A reached limit returns 400; the limit was $5/month and spend was $0.00 with zero tokens | observed + documented | DISPROVEN |
| 11 | Windows built a different body than Linux | Byte-identical at both commits | reconstructed | DISPROVEN |
| 12 | SDK-set API version header | Set by the pinned SDK; no indication of a defect | reconstructed | PLAUSIBLE / UNPROVEN (low) |
| 13 | Model lacks structured-output support | Documentation lists all models | documented | REQUIRES LIVE EVIDENCE |
| 14 | Transient or server-side condition | No evidence either way | — | PLAUSIBLE / UNPROVEN (low); REQUIRES LIVE EVIDENCE |

## 6. Confidence, stated separately

- **Historical cause of dispatch #2 — moderate to high, inferential.** One defect was identified, it violates a documented rule, and it is the only reconstructed body difference. The provider's stated reason was never observed.
- **Sprint 5 repair — high.** The defect was real; the adapter-owned schema passes the structural rule; a complete schema is necessary for the feature to return usable output at all; the request is byte-stable across platforms.
- **Current live compatibility — observed once.** Dispatch #3 accepted the frozen repaired request and returned a result that passed the existing validator. This is not general reliability, usability or owner grading evidence.

## 7. What evidence would change the status

- **Confirm directly:** provider support returns the original error message and it names the schema.
- **Support by elimination (inferential):** the separately authorized dispatch #3 accepted the repaired request on 2026-11-27. The schema was the only material reconstructed body difference; this strengthens the historical hypothesis but does not establish the original cause or exclude a transient or server-side condition.
- **Displace:** support's message names something else, or a future dispatch is rejected and the provider message Ripley now records points elsewhere.
- **Permanently unconfirmed:** support cannot retrieve the message and no future dispatch resolves it.

## 8. Resolution to date

- ADR-010 revision 11 (PR #26): adapter-owned complete output schema; provider error type and message kept in `error.detail`, sanitized first and length-capped second.
- PR #27 (reviewed at 63c8f5f, merged ccb054d): schema, pre-send structural check, mock transport enforcing the same rule, provider diagnostics. Tests P6-18, P6-19, P6-20. Linux 167 OK; Windows 167 run / 163 pass / 4 expected Phase 5 skips / 0 fail; owner mock dry-run exit 0.
- PR #28: acceptance record and schema hash.

These verified the repair offline. Separately, dispatch #3 on 2026-11-27 observed live recovery once: `observation: sent`, `remote_outcome: completed`, `pending_owner_approval`, validation passed. Provider request ID `req_011ChTms6hUogRFwaY9twKzj`. See [dispatch #3 evidence](../pilot/6d-dispatch-03.md). The historical cause remains INFERRED, not directly confirmed. The task was subsequently approved through the governed owner route; documentary field-level judgments were given under revision 12, not a native grade.

## 9. Open items

1. **Provider support.** Conversation 215476929378097, escalated to a human Product Support agent on 2026-11-19, citing `req_011ChBm8QrsiEErhYw6LkrRD` and requesting the original error type and message, the rejected field or schema condition if available, and the provider's original wording. Status: owner reports support replied on 2026-11-24 that the original error text cannot be retrieved.
2. **Dispatch #3.** Completed once on 2026-11-27 under the re-dated authorization, now consumed. No further dispatch is authorized. Stage 6D owner accepted; Stage 6E remains OPEN. Live recovery OBSERVED ONCE; historical November 18 HTTP 400 cause INFERRED, not directly confirmed. Provider could not recover the historical error. No additional diagnostic/provider call is required for this historical pilot.

**Tracked separately, not FI-001 evidence:** the Default-workspace Messages log showed two entries with OK status dated Oct 20 and Oct 21, 2026. Neither request id matches dispatch #1 or #2, and the screenshot does not show which API key made them. Both dates precede the creation of the pilot key on 2026-11-17. They are an account-activity question for later security review.

## 10. What this record does not claim

- That an HTTP 400 from this provider means a schema error.
- That Sprint 5 proved the historical cause.
- That the mock transport's HTTP 400 reproduces the provider's historical reason. The mock returns 400 because it was written to enforce the documented rule; it is a regression guard, not evidence about the provider.
- That the absence of the request from the visible Console log means the request never arrived. Ripley recorded a provider request id for it.

## 11. Reusable lessons for Cyrus Failure Intelligence

1. **On a provider rejection, capture the request as built before forming a hypothesis:** fingerprint it, compare each field with the provider's documented constraints, and read the provider's own message.
2. **A failure whose reason was not recorded may never be diagnosable.** Retaining the provider's sanitized diagnostic is a design requirement, not an enhancement.
3. **A test double that accepts what the provider rejects is a blind spot.** Mocks should enforce the provider's documented constraints.
4. **Record a fingerprint of every outbound provider request with the attempt,** so that reconstruction is never needed. (Design note for later; not implemented.)
5. **Keep observed, reconstructed, documented, and inferred evidence visibly separate,** and attach an evidence level to every causal claim.
6. **Change one variable between attempts whenever possible.** Sprint 5 changed only the schema in the request body, which is what makes any future result interpretable.

**Do not generalize:** "HTTP 400 → fix the schema." The reusable rule is the procedure in lesson 1, not this incident's leading hypothesis.

## 12. Corrections recorded here

- Billing errors are HTTP 402 `billing_error` per the provider's documentation; an earlier planning statement that a low balance returns 400 was wrong.
- The pinned SDK authenticates Ripley's Messages requests with `Authorization: Bearer`, not an `x-api-key` header; an earlier planning document said `x-api-key`. No committed project record contains that error: the one committed mention of `x-api-key`, in `docs/decisions/phase-6d-credential-check-authorization-01.md`, accurately describes a hand-built PowerShell request that did use that header.

## Appendix A — Safe offline request-capture procedure

Purpose: reconstruct the exact Messages request Ripley's code builds at any commit without any network access or real credential. Run from the repository root at the commit of interest, in a shell with no live gates set:

```
<interpreter> - . < capture-script
```

On Windows, paste the script as a PowerShell single-quoted here-string piped to `.\.venv6\Scripts\python.exe - .`

Safety properties: the script deletes every `RIPLEY_*` variable from its own process (including an inherited real credential) and sets a synthetic one; installs Ripley's socket guard before the SDK loads; replaces the mock transport in memory only; changes no file; prints header names, three non-sensitive header values, and the authentication scheme word only.

The script is kept in this document rather than under `scripts/` because it deliberately imports the SDK and `ripley.providers`, which test P6-16 forbids under `scripts/`.

```python
import hashlib, json, os, sys
from datetime import datetime, timezone, timedelta
root = os.path.abspath(sys.argv[1]); sys.path.insert(0, root)
for name in [n for n in os.environ if n.startswith('RIPLEY_')]:
    del os.environ[name]                      # drops the inherited real credential from THIS process only
os.environ.update({'RIPLEY_PROVIDER_TRANSPORT': 'mock', 'RIPLEY_ENABLE_TEST_WORKERS': '1',
                   'RIPLEY_ANTHROPIC_API_KEY': 'sk-ant-test-synthetic-fi001-0123456789'})
from ripley import providers
providers.install_socket_guard()              # any real connection attempt now raises
import anthropic, httpx2
from ripley.nfl_availability import NflAvailabilityAdapter
seen = []
def transport():
    def handler(request):
        seen.append(request)
        return httpx2.Response(200, headers={'request-id': 'req_fi001_offline'}, json={
            'id': 'msg_fi001', 'type': 'message', 'role': 'assistant', 'model': 'claude-haiku-5-5',
            'content': [{'type': 'text', 'text': '{"players": []}'}], 'stop_reason': 'end_turn',
            'stop_sequence': None, 'usage': {'input_tokens': 1, 'output_tokens': 1, 'cache_read_input_tokens': 0}})
    return httpx2.MockTransport(handler)
providers._mock_transport = transport         # in-memory only; no file is changed
packet_path = os.path.join(root, 'fixtures', 'nfl-availability', 'TB-at-CHI-2026-11-08.json')
packet = json.load(open(packet_path, encoding='utf-8'))
task = {'deadline_at': (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat()}
outcome = providers.AnthropicWorker().produce(task, {'inputs': packet}, NflAvailabilityAdapter())
canon = lambda v: json.dumps(v, sort_keys=True, separators=(',', ':')).encode('utf-8')
sha = lambda b: hashlib.sha256(b).hexdigest()
assert len(seen) == 1, f'expected exactly one captured request, saw {len(seen)}'
r = seen[0]; body = json.loads(r.content); msgs = body['messages']
auth = r.headers.get('authorization', '')
print('fi001_capture: OFFLINE (mock transport, socket guard installed)')
print('anthropic_sdk:', anthropic.__version__, '| python:', sys.version.split()[0], '| platform:', sys.platform)
print('requests_captured:', len(seen), '| socket_guard_attempts:', providers.GUARD_ATTEMPTS)
print('method:', r.method, '| host:', r.url.host, '| path:', r.url.path)
print('body_keys:', sorted(body))
print('model:', body['model'], '| max_tokens:', body['max_tokens'])
print('messages:', len(msgs), '| role:', msgs[0]['role'], '| content_type:', type(msgs[0]['content']).__name__,
      '| content_chars:', len(msgs[0]['content']))
print('packet_file_sha256:', sha(open(packet_path, 'rb').read()))
print('messages_canonical_sha256:', sha(canon(msgs)))
print('output_schema_canonical_sha256:', sha(canon(body['output_config']['format']['schema'])))
print('output_config_canonical_sha256:', sha(canon(body['output_config'])))
print('body_canonical_sha256:', sha(canon(body)))
print('body_raw_bytes:', len(r.content), '| body_raw_sha256:', sha(r.content))
print('header_names:', sorted(r.headers))
print('anthropic-version:', r.headers.get('anthropic-version'), '| content-type:', r.headers.get('content-type'),
      '| user-agent:', r.headers.get('user-agent'))
print('auth_header_scheme:', auth.split(' ')[0] if auth else None, '| x-api-key_present:', 'x-api-key' in r.headers)
print('dispatch_observation:', outcome.dispatch['observation'], '| request_id:', outcome.dispatch['provider_request_id'])
```
