# Cyrus Engineering Doctrine

Cyrus Forge Systems, LLC

| | |
|---|---|
| Version | 1 |
| Status | ACCEPTED. Adopted by owner decision on 2026-11-19; in force from merge. |
| Owner | Robert Legorreta |
| Applies to | Every Cyrus engine, present and future |
| Changed by | Owner decision only, recorded as a new version. Earlier versions are kept. |
| Adoption record | The adopted text is Revision 2 as reviewed by Claude (architecture lead), ChatGPT (implementation engineer) and Copilot (scope control), and approved by Robert Legorreta on 2026-11-19. Reviewed pre-adoption artifact SHA-256: `b82e5236804d57770f5d5a093fadfa5e75909972eccdbadaa81711498d0b4467`. Adoption changed only the Version and Status rows and added this row. |

## Purpose and standing

This doctrine states the engineering principles, evidence standards, authority boundaries and prohibitions that every Cyrus engine inherits. It is implementation-neutral: it says what must be true and does not say which components make it true.

**Adopting this doctrine is not evidence that any engine conforms to it.** The doctrine is the standard. An engine's ADRs describe how that engine meets the standard. Conformance evidence shows what a specific engine version actually provides. Where an engine does not yet meet a requirement, its records say so.

This doctrine creates no runtime requirement for any engine by itself. A requirement enters an engine through that engine's own ADR, review and owner authorization.

## 1. Priority hierarchy

1. Security and Core Integrity
2. Health and Customer Protection
3. Reliability and Service Continuity
4. Failure Intelligence and Safe Recovery
5. Evolution and Modernization
6. Performance and Efficiency
7. Customer Extensibility

The hierarchy resolves trade-offs among otherwise permissible options. An unresolved conflict affecting security, integrity, or governing obligations is escalated to the designated authority before the affected operation proceeds.

Four constraints hold without exception:

- Evolution cannot violate security.
- Performance cannot violate correctness.
- Availability cannot justify corrupted evidence.
- Autonomy cannot overrule governance.

## 2. Evidence truthfulness

- **Facts and judgments are kept separate.** What happened is recorded apart from what anyone concluded about it.
- **How evidence was obtained stays distinguishable.** *Observed*: recorded by the engine or seen directly. *Reconstructed*: reproduced afterward under controlled conditions. *Documented*: stated by an authoritative external source. *Inferred*: reasoned from the others. These describe provenance. They are not a ranking of confidence.
- **Claims show their support.** A claim identifies its necessary supporting evidence, how each item was obtained, and the limits of what it establishes. Evidence provenance and confidence in the claim are recorded separately. Mixed support remains visible.
- **Unknown is a legitimate answer.** An engine never invents a cause, a value, a time or an outcome to fill a gap. Missing evidence is recorded as missing.
- **Evidence is not silently changed.** Ordinary evidence writes may append or supersede records. They may not silently alter or remove prior evidence. A later judgment supersedes an earlier one by reference, never by replacement. Archival and authorized disposition follow a separately governed policy. Subsequent judgments must accurately identify which supporting evidence remains available for verification.

## 3. Independence of authority

An authority may check its own work or propose acceptance criteria. It may not independently certify its own work or unilaterally make its proposed criteria effective.

Independence is assessed by effective control over the decision, its criteria, and its supporting evidence. The party under evaluation must be unable to issue, impersonate, delegate, or alter the independent verdict, directly or through a shared privileged identity. Role labels do not establish independence; effective identities and credentials do.

The following combinations are prohibited:

- A producer may not be the sole certifier of its own result.
- A remediator may not be the sole certifier of recovery.
- A component under evaluation may not make its own acceptance or health criteria effective.
- The proposer of a core change may not be its sole approver.
- A deployer may not define what counts as a successful deployment.
- An editor of security policy may not authorize its own change to that policy.
- An authority may not grant a permission of which it is the beneficiary.
- A party that ingests external content may not directly execute instructions derived from it.

## 4. Recovery

Detecting a problem is not diagnosing it. Diagnosing it is not authorization to act. Executing a repair does not establish recovery.

Recovery is verified when an authority independent of the remediator obtains evidence that the originally failed property meets its recorded acceptance criterion in the affected scope. The signal, criterion, and scope are identified before verification. If the original observation cannot safely be repeated, an independently approved equivalent check must state what it establishes and its limits. Otherwise recovery remains unverified. Performing a verification that has external effects requires its own applicable authorization.

## 5. Customer protection

The protected objective is the customer's operation, data, security and trustworthy evidence. Keeping the engine itself running is not a protected objective.

- When integrity cannot be established, the engine has no right to continue the affected operation. It isolates or stops that operation.
- An authorized halt takes precedence over admission of new work in its scope. The engine follows the declared containment procedure and reports what it could and could not confirm. Rollback or correction proceeds only under its applicable authorization and safety conditions.
- Degrading one capability is preferred to stopping everything. Remaining operations must satisfy their applicable integrity conditions within the declared failure scope.

## 6. External research

Content from outside the trust boundary is untrusted data. It may produce evidence, hypotheses and proposals. It cannot, by being retrieved or read:

- create authority;
- change policy;
- act as an instruction;
- approve a candidate change;
- gain access to production credentials.

A proposal derived from external content identifies its source, distinguishes externally documented claims from locally verified facts, and follows the same authorization path as any other proposal.

## 7. Autonomous actions

Any action an engine takes without a human decision must be:

- **enumerated**: a named action class with its trigger, scope, effect ceiling and authorization. This means the class, not every runtime instance;
- **bounded** in scope and effect;
- **approved in advance** through governance.

**Reversibility.** An autonomous action must be reversible unless the governing policy explicitly identifies its irreversible effects and grants advance authorization for those effects under defined conditions and limits. If the action or its effects fall outside that authorization, execution requires a new decision by the designated authority.

**State changes.** An autonomous action may append evidence and change operational state within its approved scope. It may not rewrite prior evidence, expand its permissions, or change the criteria used to judge its result. Any authority to change credential state must be separately and explicitly bounded.

**Learning.** Recording a new observation does not change governing behavior. Using learned material to change permissions, decision rules, acceptance criteria, or executable behavior requires the governance applicable to that change.

An action class that is not enumerated is not autonomous. Autonomous authority may be narrowed at any time. Widening it requires an explicit governance decision on record.

## 8. Customer boundaries

Customer evidence is governed within the customer's authorized data boundary, however that boundary is implemented.

**Cross-customer knowledge.** Reuse across customer boundaries requires a separately governed export with an approved purpose, recipient scope, sanitization, and provenance, and with the source customer's approval. Neither the export nor its accessible references may disclose source-customer evidence or identifying operational details. Approval may cover a defined class of exports; it does not grant access to the original incident.

## 9. Invariants

Every Cyrus engine must satisfy these. Each is written so that a reviewer or a test can check it.

1. **Evidence preservation.** Ordinary evidence writes append or supersede by reference. No ordinary path silently alters or removes prior evidence. Disposition occurs only under the governed policy, and later judgments state which supporting evidence remains available.
2. **Independent certification.** Every certified result identifies the certifying authority and the applicable criteria. The producer cannot control the independent certification decision.
3. **Independent recovery verification.** A claim of verified recovery references the original failure, applicable criterion, verification evidence, and independent verifier. A repair or attempted verification may be recorded without a recovery claim.
4. **Protected criteria.** The evaluated party cannot make or activate a change to its own governing criteria. A criteria change requires independent approval, a recorded version, and an explicit scope of application. This does not prevent a party from proposing criteria or experimenting in isolation.
5. **No authority from external data.** A state-changing action requires authorization from an authority entitled to grant it for that action and scope. Retrieval, parsing, summarization, or reissuance by an internal component cannot confer that authority.
6. **No silent expansion.** Every widening of an autonomous permission has an explicit governance record.
7. **Halt, containment, and rollback.**
   - **Declare.** For each operation, the engine declares the scope, failure conditions, and response bound within which it can enforce a halt.
   - **Contain.** Within those conditions, invoking containment prevents new work in the affected scope without requiring the affected component's cooperation. If containment cannot be confirmed, the engine reports that condition and escalates under policy.
   - **Record.** A halt request, confirmed containment, and the disposition of work already in flight are recorded separately.
   - **Roll back.** Rollback is a separate, authorized action. Its reversible effects are verified before rollback is declared complete. Irreversible, unknown, or unverified effects remain identified as such.
8. **No collapsed status.** A material health summary identifies its scope, observation time, underlying claims, and supporting evidence or recorded gaps. An authorized reviewer can distinguish observations from judgments and inspect the basis permitted by the applicable access and retention policies.
9. **Tenancy protection.** Nothing crosses a customer boundary except through the governed export described in section 8.
10. **Secret exclusion.** Usable credentials and authentication secrets are prohibited in evidence, logs, prompts, and shared knowledge. Each engine identifies the paths that can receive secret-bearing input, verifies its exclusion or redaction controls on those paths, and treats detected exposure as an incident. Clearly identified synthetic test values must confer no real access.

## 10. Acceptance case: FI-001

The first Failure Intelligence record, FI-001, is the worked test of this doctrine. After the incident was analyzed and a defect repaired, the evidence supported three distinct judgments at once:

| Judgment | Status |
|---|---|
| Defect repaired | Yes, proven |
| Historical cause confirmed | No, unconfirmed |
| Live recovery verified | No, untested |

A conforming engine must be able to hold and report all three together. A system that reduces them to a single healthy or unhealthy state does not conform.

FI-001's specific technical hypothesis is evidence about one incident. It is not part of this doctrine and must not be applied to other incidents as a rule. A similar symptom is a reason to run known discriminating diagnostics, never a diagnosis.

## 11. Long-life aspiration

Cyrus engines are designed to remain secure, supportable, adaptable and useful through technological change, so that customers are not forced into unnecessary ground-up rebuilds. This is an engineering aspiration and a design goal. It is not a warranty of uninterrupted or defect-free operation.

## 12. Explicitly deferred

This doctrine does not design, schedule or authorize any of the following: health agents; autonomous remediation; an evolution lab; horizon-monitoring agents; a shared machine-readable Failure Intelligence platform; customer plugin execution; production signing infrastructure; staged deployment automation; multi-tenant services; multi-provider orchestration.

Implementation of a deferred capability requires its own entry criteria, engine ADR, review, and owner authorization. Planning alone does not authorize implementation or production use.

## 13. Document hierarchy

1. **Cyrus Engineering Doctrine** (this document): the standard.
2. **Engine ADRs**: how a particular engine implements doctrine requirements. Each ADR names the invariants it affects.
3. **Conformance evidence**: what a specific engine version demonstrably provides.
4. **Failure Intelligence records**: incident evidence.
5. **Authorization and operational records**: owner decisions and what was done under them.

This hierarchy governs internal Cyrus engineering decisions within the bounds of applicable law, regulation, binding agreements, and binding security obligations. An internal document or owner approval cannot waive an external obligation. An apparent conflict is recorded and referred to the designated authority before affected work proceeds. For internal normative conflicts, the higher governing requirement controls. Evidence and incident records retain what was observed, including facts that demonstrate nonconformance.
