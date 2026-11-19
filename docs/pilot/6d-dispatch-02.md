# Phase 6D — Dispatch #2 closeout

| Dispatch evidence | Recorded value |
|---|---|
| `dispatch.sent_at` (CT / UTC) | 2026-11-18 11:48:57.512673 PM CST / 2026-11-19T05:48:57.512673+00:00 |
| Repository revision | `main` at `c44e379` |
| Packet SHA-256 | `1ce3f332e1e8ff7aa113bbb0cd2688583086c29a050be909d9607e1a3c2c0aa6` |
| Prompt SHA-256 | `7d5094d53f2e1f4924b1daa727a7fb7563048743082306908825604d3da06904` |
| Ledger | `pilot/6d-dispatch-02.sqlite` |
| Ledger SHA-256 | `ebd8fda51c510d457c0cfb2de2cff743302fe260dd145d0fa3862f154ad051dd` |
| Runner outcome | `blocked_worker_failure` |
| `provider_error` | `invalid_request` |
| `error.detail` | `BadRequestError status=400` |
| `dispatch.observation` | `sent` |
| `remote_outcome` | `failed_after_send` |
| Provider request ID | `req_011ChBm8QrsiEErhYw6LkrRD` |
| Usage | Unavailable |
| `dispatches_consumed` | 1 |
| Live pilot counts | `confirmed_sent` 1 / `uncertain_dispatch` 0 / `budget_slots_consumed` 1 |
| Task transition | `running → blocked` at `2026-11-19T05:48:58.225582+00:00` |
| Console before dispatch | $0.00, Input 0 / Output 0 |

## Pre-live checks

All checks passed in a new session. No live, mock, or test variables were present. The packet and prompt hashes matched. The interpreter was `.venv6\Scripts\python.exe` with `anthropic 2.9.0`. The process credential equaled the Windows User-scope value and passed all five shape checks. The ledger path was fresh, and the authorization hash check returned true.

## What this established

Authentication succeeded and the request reached the Messages API, which rejected the request body (HTTP 400). No model output was produced. Ripley records the SDK exception class and status but not the provider’s error message, so the exact reason is not in the ledger. Leading hypothesis, unconfirmed: the structured-output schema declares each `players` item as a bare object without `additionalProperties: false` or declared properties, which Anthropic’s structured-output rules do not accept. Independently of the 400, a schema without declared properties could only have produced empty objects.

## Shutdown

The owner removed the three live gates. A fresh-session check showed only the credential variable. The runner was not rerun.

Authorization #2 is consumed and ended by its own terms. No further dispatch is authorized. A code fix, reviewed and verified in mock mode on Linux and Windows, is required before any new authorization is considered.

Follow-up: [PR #27](https://github.com/Ibmcleaner/Ripley-1/pull/27) implements the schema and diagnostics changes in [ADR-010 revision 11](../decisions/phase-6-adrs.md).
Root-cause analysis: FI-001. Historical cause UNCONFIRMED; provider support case pending.
