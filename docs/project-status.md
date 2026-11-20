# Project status and known limitations

Recorded: 2026-11-04  
Scope: approved Phase 1 documentation handoff for Ibmcleaner/Ripley-1.

## Milestones

| Milestone | Status and evidence basis |
|---|---|
| Phase 0: Inventory & Salvage | COMPLETE, per owner; prior inventories are not re-audited or imported by this change |
| Phase 1 architecture decisions | COMPLETE, per approved owner handoff following reported Copilot/Claude review |
| Phase 1 documentation | Captured in this documentation branch; merge status is tracked by the pull request |
| Phase 2 implementation | NOT STARTED |
| Phase 6A ADR-010 | COMPLETE (PR #11, main a7cbfd2) |
| Phase 6B + 6C | ACCEPTED (mock transport only; PR #12, PR #15) |
| Phase 6D-prep (packet + runner, mock-only) | ACCEPTED (mock-only; PR #17) |
| Phase 6D live pilot | NOT AUTHORIZED |
| Phase 6D dispatch #1 | auth_rejected (failed_after_send); cause: abbreviated credential stored; remediated; no further dispatch authorized |
| Phase 6D credential check #1 | HTTP 200, model available; dispatch #2 not authorized |
| Phase 6D dispatch #2 | invalid_request (HTTP 400, failed_after_send); request schema fix required; no further dispatch authorized |
| Sprint 5 — output schema + provider error diagnostics | ACCEPTED (mock-only; PR #27) |
| FI-001 — dispatch #2 HTTP 400 root-cause analysis | Offline RCA complete; historical cause UNCONFIRMED; awaiting provider support; dispatch #3 paused and unauthorized |
| Cyrus Engineering Doctrine v1 | ACCEPTED by owner 2026-11-19 (docs/architecture/cyrus-engineering-doctrine.md). A standard for future ADRs and engines. Adoption does not certify that Ripley conforms; no Ripley runtime requirement is created by this document |
| Sprint 6 — offline dispatch identity preflight | ACCEPTED (PR #31, merged fa44976). Offline only; Linux 185/0 skips, Windows 185/4 skips, preflight 12 of 12 matched. Passing it does not authorize dispatch or establish provider acceptance |
| Sprint 7 — offline capture receipt (ADR-011) | ACCEPTED (PR #34, merged 86012c8). Offline, local-file intake only. Linux 202/0 skips, Windows 202/4 expected skips, focused capture tests 17/17. No network acquisition, no provider activity |
| Sprint 8 — advisory CI on pull requests | ACCEPTED (PR #36, merged ddb23be). One advisory Linux check: full suite, pinned SDK, zero skips, disposable copy. Independent reproduction 202 run / 0 skips; hosted runs 1 and 2 green. Not a merge gate; no secrets; no provider activity |
| Sprint 9 — capture and CI runner corrections | ACCEPTED (PR #38, merged 697680b). Seven known items from Sprints 7 and 8 corrected; no new capability. Linux 206/0 skips, Windows 206/4 expected skips, focused capture tests 21/21; seven mutation checks detected. Capture is sequential-only. Advisory CI; no provider activity |

## Maturity vocabulary

These labels describe different evidence states; one does not automatically imply another.

| Label | Meaning in project documentation |
|---|---|
| PLANNED | Intended future work without an implementation claim |
| DESIGNED | Documented architecture/contracts; not proof of runtime behavior |
| RECOVERED | Located historical material; requires assessment before reuse |
| IMPLEMENTED | Actual code exists for the stated scope; no automatic test or readiness claim |
| TESTED | Specific verification was performed with recorded results and limitations |
| PRODUCTION VALIDATED | Evidence supports the stated behavior in the defined production environment |

Current Ripley architecture and conceptual contracts are **DESIGNED**. Future extension capabilities remain **PLANNED** except for the architectural guardrails documented here. No component is promoted to IMPLEMENTED, TESTED, or PRODUCTION VALIDATED by this handoff. Phase 0 completion does not make recovered code production-ready.

## Known limitations and deferred detail

- No production code, executable skeleton, runtime tests, deployment, or production validation is included.
- Conceptual fields are not executable schemas. Types, serialization, persistence, retention, identifier formats, and migration details are unspecified.
- Lifecycle states, dependency execution semantics, retry/recovery mechanics, worker selection, and cost-ceiling enforcement are not defined here.
- Complete Validation, Review, Decision, Prediction, Outcome, Grade, and Classification contracts are not supplied in this handoff.
- Concrete independence enforcement for validation, approval authority, and security-policy enforcement remain unspecified.
- Materiality criteria and domain grading rules require domain-specific design outside Core.
- RAG, controlled learning, debugging/reliability, postmortem automation, model governance, and live-event monitoring are not implemented.
- This documentation does not claim historical model accuracy, backtest performance, operational reliability, or test results.
- The owner reports the Copilot/Claude architecture review; their underlying review artifacts are not included.

These are explicit documentation boundaries, not silently resolved design choices.

## History and handoff record

The repository was inspected before this documentation change. At inspection, main contained only README.md at initial commit `9b8b5cb93efa129e002d2fc7c5549d1b2400bb4f`; there were no open pull requests and no repository instruction files.

This change preserves that parent history, expands the README, corrects its leaked ampersand HTML entity in the same documentation commit, and adds the architecture, conceptual contracts, ADRs, and this status record. No other Cyrus repository is in scope.

Future work should document actual decisions, implementation, tests, failures, debugging, postmortems, lessons, improvements, demonstrations, and limitations as they occur. Protect secrets, credentials, personal information, and sensitive system details. Preserve useful failures and their resolutions.

Microsoft Copilot maintains architecture continuity. ChatGPT supports approved GitHub documentation and independently raises technical concerns with reasoning and alternatives; it must not silently redesign Ripley.

Note (2026-11-20): role statements above reflect 2026-11-04. Current roles are in docs/PROJECT_STATE.md section 4.
