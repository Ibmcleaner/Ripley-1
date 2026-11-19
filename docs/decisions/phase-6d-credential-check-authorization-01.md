# Phase 6D — Owner authorization for credential check #1 (read-only, non-generation)

Owner: Robert Legorreta, Cyrus Forge Systems, LLC
Date (CT): ___11/18/26_________
main at authorization: 9b00853
Purpose: confirm that the corrected stored credential authenticates and that the pilot model is available to it, before any second dispatch is considered. Follows dispatch #1 (auth_rejected, HTTP 401); see docs/pilot/6d-dispatch-01.md.
Request: exactly ONE HTTP GET to https://api.anthropic.com/v1/models/claude-haiku-5-5
Sent: x-api-key header (from the Windows User variable RIPLEY_ANTHROPIC_API_KEY, referenced by name), anthropic-version header, user-agent. No request body. No packet, prompt, or Ripley data.
Not sent / not used: the Messages API; any generation request; the Ripley runner; Ripley live gates (RIPLEY_PROVIDER_TRANSPORT, RIPLEY_LIVE_DISPATCH stay unset); any ledger.
Tokens / cost: none expected; this endpoint returns model metadata only.
Success: HTTP 200 with id claude-haiku-5-5.
Failure: any other status (401 not authenticated, 403 not permitted, 404 model unavailable) — stop and investigate; no retry under this record.
Output permitted on screen: status code, returned model id, request-id header. The key, its length, and request headers are never printed, logged, or written to a file.
Evidence retained: time, status code, model id, request id, recorded in docs/pilot/6d-credential-check-01.md by a later docs-only PR.
Account state at authorization: Default workspace spend limit $5/month; spend this month $0.00; credit balance $20.00; auto-reload on. Stored credential passed five local Boolean shape checks on 2026-11-18.

I authorize exactly one read-only request as described above.
This record does not authorize a Messages API call, a dispatch, a retry, or any second request. Dispatch #2 requires its own separate authorization record.

Signed: ____Robert Legorreta________

Status: CONSUMED 2026-11-18 — one GET, HTTP 200; see docs/pilot/6d-credential-check-01.md.
