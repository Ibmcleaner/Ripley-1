# Phase 6D — Credential check #1

The owner signed the [credential-check authorization](../decisions/phase-6d-credential-check-authorization-01.md) on 11/18/26. PR #22 merged it into `main` at `d856996`.

## Pre-check

In a new PowerShell session, the process value equaled the Windows User variable. All five shape Booleans were true. No Ripley live gate was present.

## Request and result

The owner made one HTTP GET from PowerShell to `https://api.anthropic.com/v1/models/claude-haiku-5-5` with no request body. The check used no Ripley runner, SDK, live gates, or ledger.

| HTTP status | Returned model ID | Request ID |
|---|---|---|
| 200 | `claude-haiku-5-5` | `req_011ChBiTetuYkBFBxdVnmWg1` |

Exact request time was not captured. The request was made on 2026-11-18 between 11:06 PM and 11:15 PM CT (2026-11-19 05:06–05:15 UTC), bounded by the owner’s ready confirmation and result report. No time has been reconstructed beyond that window.

After the successful response, a mistyped local cleanup command produced a PowerShell parameter error; the corrected `Remove-Variable` command was then run. No second request was made.

## Conclusion

The corrected stored credential authenticates and `claude-haiku-5-5` is available to it. This check does not show that the Messages API accepts Ripley’s exact request and schema, and produced no model output; that remains the open question of Phase 6D. The authorization for credential check #1 is consumed. No Messages API call or dispatch occurred. Dispatch #2 is not authorized.
