# Phase 1 architecture

Status: **DESIGNED — approved architecture; not implemented.**  
Company: Cyrus Forge Systems, LLC  
Engine: Cyrus Ripley One (Ripley / R1)  
Documentation date: 2026-11-04

Source: the project owner's approved Phase 1 GitHub documentation assignment. The owner reports that Copilot and Claude completed the architecture review. This document records that handoff; it does not independently certify their review or software readiness.

## 1. Identity and domain boundary

Ripley is a domain-agnostic core platform, not an NFL prediction engine. NFL prediction will later become the first substantial domain implementation. Future domains may include inventory/demand forecasting, logistics, sales forecasting, business operations, and other prediction/decision-support applications.

Domain-specific terminology, schemas, features, models, and grading logic remain outside Ripley Core.

## 2. Lean infrastructure first

Design for extension. Build the minimum necessary foundation. Prove the foundation. Then add capability in controlled layers.

Extension points may be designed for RAG/knowledge, security/policy, debugging/reliability, controlled learning, postmortems, model governance, and live/material-event monitoring. These are not automatically MVP implementations. The first executable skeleton should remain intentionally small.

## 3. Core MVP flow

Task → Ripley → Worker → Result → Validation → Review/Correction → Evidence → Approval

This is the approved conceptual flow, not a claim of an executable workflow. It contains no domain-specific concepts. A Worker produces a Result; validation authority belongs to a separate validation process.

## 4. Record principle

> Core stores facts; judgments are separate, referenced, and revisable records. Corrections supersede prior judgments rather than rewriting historical facts.

- Facts are durable.
- Assessments are attributable.
- Judgments are revisable.
- Revisions supersede rather than erase.
- History remains auditable.

If factual data later proves incorrect, preserve the historical record and record a correction/supersession rather than silently rewriting history.

## 5–8. Conceptual contracts

The [contract specification](contracts.md) records the approved minimum Task, Snapshot, Event, Event Assessment, Result, and Validation concepts. These are conceptual interfaces, not executable schemas.

Tasks support permitted worker/model allowlists or execution-policy references, rather than permanent binding to a single worker/model. A Snapshot used for a prediction or decision is immutable. Event observations are factual; materiality determinations are separate, revisable assessments. Results and independent Validation records remain separate.

## 9. Outcome, grade, and classification

Prediction → Outcome → Grade

Outcome is factual. Grade is the mechanically determinable comparison between the frozen prediction and the recorded outcome, and belongs on the factual side of the record system. Domain grading logic remains outside Core.

Classification comes later and is interpretive/revisable. One wrong prediction does not automatically imply model error. Where evidence permits, the eventual classification/postmortem layer should distinguish:

- Model error.
- Incorrect, stale, or incomplete input.
- Material post-prediction state change.
- Ordinary uncertainty/variance.
- System/implementation failure.
- Insufficient evidence.

Distinguishing prediction error from ordinary statistical variance may require accumulated evidence rather than one outcome.

## 10. Evidence and provenance

Important assertions should eventually be traceable through durable records:

Task → Snapshot → Result → Validation → Review → Decision

This is a provenance chain, not an additional execution sequence. GitHub should retain appropriate ADRs, architecture, interface specifications, source code when implementation begins, tests, documentation, postmortems, and known issues. Runtime evidence storage and retrieval are not implemented by these Markdown documents.

## Future extension guardrails

These standing project constraints describe future capabilities, not added MVP implementations:

- RAG supplies information and evidence; retrieved material does not authorize production changes.
- Where practical, hard security rules should be deterministic and not bypassable solely on an AI recommendation.
- Debugging/reliability may analyze failures and recommend or test repairs, but should not silently modify production.
- Controlled learning preserves the original prediction/decision snapshot, records outcomes and grading, classifies errors, archives postmortem evidence, and evaluates candidate improvements historically before validation and governed promotion into an approved version.
- A post-prediction event may justify a new snapshot and prediction; it does not erase the original or automatically prove model error.

Microsoft Copilot maintains Phase 1 architecture continuity. Technical disagreements should identify the decision, explain the concern with reasoning/evidence, and propose an alternative. Documentation work must not silently redesign Ripley.
