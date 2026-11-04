# Cyrus Ripley One

Cyrus Ripley One (Ripley / R1) is a domain-agnostic AI engine/platform being developed under **Cyrus Forge Systems, LLC**.

## Current status

**Phase 1: Architecture & Implementation Baseline**

| Milestone | Status |
|---|---|
| Phase 0: Inventory & Salvage | COMPLETE, as reported by the project owner |
| Phase 1 architecture decisions | COMPLETE; approved design |
| Phase 1 GitHub documentation handoff | This documentation change |
| Phase 2 implementation | NOT STARTED |

This repository documents architecture, not working Ripley software. No production implementation, executable skeleton, runtime tests, or production validation is included.

## Architecture documentation

- [Phase 1 architecture](docs/architecture/phase-1.md)
- [Conceptual interface contracts](docs/architecture/contracts.md)
- [Approved architecture decision records](docs/decisions/phase-1-adrs.md)
- [Status, evidence, and known limitations](docs/project-status.md)

Ripley Core remains domain-neutral. NFL prediction is expected to be the first substantial future domain implementation; its terminology, schemas, features, models, and grading logic belong outside Core. Other potential domains include inventory/demand forecasting, logistics, sales forecasting, business operations, and prediction/decision support.

**Design for extension. Build the minimum necessary foundation. Prove the foundation. Then add capability in controlled layers.**

## Engineering record

Document decisions, implementation, tests, failures, debugging, postmortems, lessons, demonstrations, and limitations as work occurs. Preserve useful history rather than rewriting it to imply maturity. Recovered components are not production-ready merely because they exist.
