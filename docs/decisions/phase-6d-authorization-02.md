# Phase 6D — Owner authorization for live dispatch #2  
 
Owner: Robert Legorreta, Cyrus Forge Systems, LLC  
Date (CT): ____________  
main at authorization: 2850114  
History: dispatch #1 ended failed_after_send / auth_rejected (HTTP 401) because an abbreviated credential had been stored; see docs/pilot/6d-dispatch-01.md. The stored value was corrected. Credential check #1 returned HTTP 200 for claude-haiku-5-5 (request id req_011ChBiTetuYkBFBxdVnmWg1); see docs/pilot/6d-credential-check-01.md. No model output has yet been produced.  
Packet: fixtures/nfl-availability/TB-at-CHI-2026-11-08.json  
Packet SHA-256: 1ce3f332e1e8ff7aa113bbb0cd2688583086c29a050be909d9607e1a3c2c0aa6  
Prompt: ripley/prompts/nfl-availability/1.md (prompt_ref nfl-availability/1)  
Prompt SHA-256: 7d5094d53f2e1f4924b1daa727a7fb7563048743082306908825604d3da06904  
Provider/model: Anthropic claude-haiku-5-5 via anthropic==2.9.0; max_tokens 1024; max_retries 0; output_config.format json_schema  
Ledger: pilot/6d-dispatch-02.sqlite — a new file that must not exist before the run; pilot/6d-dispatch-01.sqlite is retained unmodified as evidence  
Interpreter: .\.venv6\Scripts\python.exe invoked directly; no activation script and no bare python  
Budget: exactly ONE dispatch (RIPLEY_PILOT_DISPATCH_BUDGET=1); no dispatch_authorization ledger record will be written  
Anthropic console at authorization: Default workspace spend limit $5/month; spend this month $0.00; credit balance $20.00; auto-reload on — owner confirmed unchanged 2026-11-18  
Credential: RIPLEY_ANTHROPIC_API_KEY in Windows User scope, set via the environment-variables GUI; never in shell history, chat, or repository  
Pre-live checks required before any gate is set: no RIPLEY live, mock, or test variables present; clean working tree at the SHA above; packet and prompt hashes match this record; interpreter path and anthropic 2.9.0 verified; process credential equals the User-scope value and passes the five shape checks; console spend baseline noted; ledger path absent; this record contains the packet hash  
Live gates: RIPLEY_PROVIDER_TRANSPORT=live, RIPLEY_LIVE_DISPATCH=1, RIPLEY_PILOT_DISPATCH_BUDGET=1 — session-only, set immediately before the run, destroyed by closing the window  
Governing records: ADR-010 revision 10; this record  
 
I authorize exactly one live dispatch of the packet above under ADR-010 revision 10.  
A runner refusal before the DISPATCH confirmation prompt sends nothing and does not consume this authorization.  
This record does not authorize a third dispatch, any other packet, any other prompt version, or any other model.  
Any outcome other than remote_outcome: completed ends the authorization; a further dispatch requires a new record.  
 
Signed: ____________  

