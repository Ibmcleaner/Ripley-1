# Phase 6D — Owner authorization for live dispatch #1

Owner: Robert Legorreta, Cyrus Forge Systems, LLC
Date (CT): ____________
main at authorization: aac4732
Packet: fixtures/nfl-availability/TB-at-CHI-2026-11-08.json
Packet SHA-256: 1ce3f332e1e8ff7aa113bbb0cd2688583086c29a050be909d9607e1a3c2c0aa6
Prompt: ripley/prompts/nfl-availability/1.md (prompt_ref nfl-availability/1)
Prompt SHA-256: 7d5094d53f2e1f4924b1daa727a7fb7563048743082306908825604d3da06904
Provider/model: Anthropic claude-haiku-5-5 via anthropic==2.9.0; max_tokens 1024; max_retries 0; output_config.format json_schema
Budget: exactly ONE dispatch (RIPLEY_PILOT_DISPATCH_BUDGET=1); no dispatch_authorization record will be written for this task key
Anthropic console: Default workspace spend limit $5/month set 2026-11-18 at $0.00 usage; ripley-pilot key associated with that workspace
Credential: RIPLEY_ANTHROPIC_API_KEY stored in Windows User scope via the environment-variables GUI on 2026-11-18; never in shell history, chat, or repository
Live gates: RIPLEY_PROVIDER_TRANSPORT=live, RIPLEY_LIVE_DISPATCH=1, RIPLEY_PILOT_DISPATCH_BUDGET=1 — session-only, set immediately before the run, destroyed by closing the window
Governing records: ADR-010 revision 10; docs/pilot/6d-dry-run.md (mock); this record

I authorize exactly one live dispatch of the packet above under ADR-010 revision 10.
This record does not authorize a second dispatch, any other packet, any other prompt version, or any other model.
Any outcome other than remote_outcome: completed ends the authorization; a further dispatch requires a new record.

Signed: ____________
