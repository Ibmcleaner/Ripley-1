# Phase 2: first executable skeleton

Status: IMPLEMENTED prototype; not production validated.

Run: `python -m demo`
Test: `python -m unittest discover -s tests -v`

The deterministic synthetic inventory adapter exercises the domain-neutral Task → Ripley → Worker → Result → independent Validation → Review → Evidence → pending Approval chain. No NFL concepts, external AI calls, or third-party dependencies.

The core is a single module to avoid premature package hierarchy. The adapter is isolated in `ripley/synthetic.py`. Task eligibility is an allowlist. Worker identity must differ from validator identity. Snapshots and results are frozen; review revisions append records referencing earlier reviews. Factual events cannot be superseded as judgments. Approval remains pending owner authority, not automatic.

Limitations: records are only in memory and disappear on restart; UUIDs and timestamps vary between runs although the mock output is deterministic. Validation checks output structure, not prediction accuracy. Identity separation is a prototype guard, not secure authentication. No outcome/grade/classification workflow, factual correction mechanism, persistent audit store, event monitoring, or production authorization is claimed.
