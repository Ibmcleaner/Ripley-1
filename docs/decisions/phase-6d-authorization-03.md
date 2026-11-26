# Phase 6D — Owner authorization for live dispatch #3 (diagnostic)

- Owner: Robert Legorreta, Cyrus Forge Systems, LLC
- Date signed (CT): __11/26/26__________
- Valid only on: 2026-11-26, and not after 5:00 PM Central Time on that date. Start as soon as every approved gate is satisfied; do not wait until the cutoff.
- Purpose: one diagnostic dispatch to test the Sprint 5 repair against the live provider and, if it is rejected, to record whatever error type and message the provider supplies. This is not Phase 6E and not an NFL result.
- Governing plan: ripley-phase-6d-diagnostic-dispatch-3-plan-release-candidate-r1.md, 50,485 bytes, SHA-256 3fbe809b36d415dafd517fe0b882e9dbe99abd388cc97d8793f8213c5817f4a1; approved by the owner on 2026-11-26 (ACT 1).
- Owner decision recorded here (ACT 2), decided 2026-11-26: the pause on dispatch #3 is lifted for exactly one confirmed execution attempt. The freeze on the provider implementation, prompt, packet, schema, model, SDK pin, request settings, retry settings and correction budget remains in force and nothing in them is changed for this dispatch.
- Reviewed frozen baseline: e574ab5a7b7fbc31db679a571be8c831d7a2cfe8
- Execution commit: the commit of main that contains this signed record. This record does not state its own commit. That commit's SHA and this file's Git object id are supplied in the owner handoff after merge and checked by section 7 steps 4 to 6 of the governing plan.
- History: dispatch #1 ended failed_after_send / auth_rejected (HTTP 401); the stored credential was corrected. Dispatch #2 ended failed_after_send / invalid_request (HTTP 400), request id req_011ChBm8QrsiEErhYw6LkrRD; see docs/pilot/6d-dispatch-02.md and FI-001. Provider support replied on 2026-11-24 that the original error text cannot be retrieved. No model output has yet been produced.
- Packet: fixtures/nfl-availability/TB-at-CHI-2026-11-08.json
- Packet SHA-256: 1ce3f332e1e8ff7aa113bbb0cd2688583086c29a050be909d9607e1a3c2c0aa6
- Prompt: ripley/prompts/nfl-availability/1.md (prompt_ref nfl-availability/1)
- Prompt SHA-256: 7d5094d53f2e1f4924b1daa727a7fb7563048743082306908825604d3da06904
- Output schema canonical SHA-256: bbefc6a8fce78143a8c0ff5eb918db4a43373af7bbe578348fca96f3dd47f41a
- Provider/model: Anthropic claude-haiku-5-5 via anthropic==2.9.0; max_tokens 1024; max_retries 0; output_config.format json_schema
- Request body as reviewed (informational, not enforced): 4,805 bytes, SHA-256 037e813693e8bbdd1e6bb6ad0a843c233fa5b8ef3472031f5e2dd5baade737e7
- Model availability: not separately checked; unknown at authorization. A rejection for that reason is an accepted outcome. No other model may be used.
- Ledger: pilot/6d-dispatch-03.sqlite — a new file that must not exist before the run. No other ledger path may be used. The ledgers of dispatches #1 and #2 are retained unmodified as evidence.
- Interpreter: .\.venv6\Scripts\python.exe invoked directly; no activation script and no bare python
- Budget: exactly ONE dispatch (RIPLEY_PILOT_DISPATCH_BUDGET=1); no dispatch_authorization ledger record will be written
- Anthropic console at authorization: organization monthly spend limit $500; Default workspace monthly spend limit $5; spend this month $0.00; credit balance $20.00; auto-reload ON (threshold below $5; target balance $20); promotional credit shown $216.37 — owner confirmed and accepted these account conditions for the single bounded diagnostic on 2026-11-26.
- Credential: RIPLEY_ANTHROPIC_API_KEY in Windows User scope, set via the environment-variables GUI; never in shell history, chat, or repository
- Credential owner fact: Option B of the governing plan, section 9 — owner confirmed that the current Windows User-scope credential was established from the complete original secret, not an abbreviated provider-console display.
- Pre-execution gate: section 7 of the governing plan, completed in one fresh Windows PowerShell session, including the replacement credential-check procedure (not the historical commands), the tracked-change and record-identity check, the offline preflight with expected-head, and the local-state and record checks
- Live gates: RIPLEY_PROVIDER_TRANSPORT=live, RIPLEY_LIVE_DISPATCH=1, RIPLEY_PILOT_DISPATCH_BUDGET=1 — session-only, set immediately before the run, removed by closing the window
- Governing records: ADR-010 revision 11; the governing plan; this record

I authorize exactly one confirmed invocation of the runner for the packet above under ADR-010 revision 11.

A runner refusal before the DISPATCH confirmation prompt sends nothing and does not consume this authorization.

Once DISPATCH is typed, this authorization is consumed, even if the recorded provider-dispatch accounting later says not_sent or failed_before_send. There is no rerun, no other ledger and no retry.

This record does not authorize a fourth dispatch, any other packet, prompt version or model, or any change to the request.

This record is valid only on the date and before the time written above. It does not carry forward to another date.

A further dispatch requires a new record.

Signed: __Robert Legorreta__________
