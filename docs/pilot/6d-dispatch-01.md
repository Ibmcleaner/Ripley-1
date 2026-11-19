# Phase 6D — Dispatch #1 closeout

| Dispatch evidence | Recorded value |
|---|---|
| Dispatch time (CT / UTC) | 2026-11-18 9:15:57.943083 PM CST / 2026-11-19T03:15:57.943083+00:00 (`$.data.dispatch.sent_at`) |
| Repository revision | `main` at `e48b33b` |
| Packet SHA-256 | `1ce3f332e1e8ff7aa113bbb0cd2688583086c29a050be909d9607e1a3c2c0aa6` |
| Prompt SHA-256 | `7d5094d53f2e1f4924b1daa727a7fb7563048743082306908825604d3da06904` |
| Ledger | `pilot/6d-dispatch-01.sqlite` |
| Ledger SHA-256 | `88994d1c2458425395a65536b52dbea96f432229aa1a54120c1ffd54d3d36260` |
| Runner outcome | `blocked_worker_failure` |
| Provider error | `auth_rejected` (HTTP 401, SDK `AuthenticationError`) |
| `dispatch.observation` | `sent` |
| `remote_outcome` | `failed_after_send` |
| Provider request ID | `req_011ChBZTkCasGqMvd7ApZ8HP` |
| Usage | Unavailable |
| `dispatches_consumed` | 1 |
| Live pilot counts | `confirmed_sent` 1 / `uncertain_dispatch` 0 / `budget_slots_consumed` 1 |
| Anthropic console | $0.00 before dispatch. The console showed no cost afterward. |

## Before the dispatch

The first invocation used system `python`. The runner refused with “required provider SDK is not installed” before the confirmation prompt. It sent nothing and wrote no ledger record. The owner retried with `.\.venv6\Scripts\python.exe`.

## Cause (owner investigation, no provider call)

The Windows User-scope credential had been copied from the Console’s abbreviated key display. The stored value began with `sk-ant-`, had no whitespace or quotes, and was shorter than a complete secret. The owner found no Machine-scope duplicate. The key itself was valid and the owner retained it.

Ripley classified, recorded and contained the rejection as designed; no code defect identified.

## Remediation (2026-11-18)

The owner replaced the abbreviated Windows User-scope value with the saved original full secret through the Windows Environment Variables GUI. In a new PowerShell session, all five checks returned `True` without displaying the key. The stored value had the expected prefix, equaled its trimmed value, contained no whitespace or quote characters, passed the complete-length check, and contained no ASCII or Unicode ellipsis. The owner then removed the temporary PowerShell variable.

The remediation used no live gates and made no network or provider call. No second dispatch occurred. Shape is verified; authentication is not, and will not be until a credentialed call the owner authorizes.

No model output was produced. The question Phase 6D exists to answer — whether this account and model accept Ripley’s exact request and schema — remains unanswered. Authorization #1 is consumed and ended by its own terms. No second dispatch is authorized.
