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
