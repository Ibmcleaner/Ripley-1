# Ripley One — NFL Milestone 2A domain package

Owner: Robert Legorreta, Cyrus Forge Systems, LLC.  
Authorization: "APPROVE ALL+" — reconciled owner-decision block supplied by Copilot; exact owner-decision date not independently recovered from the available record. MISSING DATE — OWNER/CHAIR RECORD REQUIRED; unresolved, non-blocking, must not be inferred.  
Source-strategy amendment authorization: "APPROVE NFLVERSE INTERIM SOURCE".  
Baseline: `21e48d0527c3a36795ccf8d42d119f4b8c50ffb9` (PR #65 merge).  
Status: AUTHORIZED — domain contract, source rules, fixture/test-material specification and evaluation design only. Source-strategy amendment baseline: `0214f285c31b2dabbccaf35e9a4e78ef5d9a5f46` (PR #66 merge). This package is a specification for independent review, not selected or frozen fixture bytes, approved answer keys, implementation acceptance or production-source approval.

## 2A-D01 — Owner decision record

2A defines what is correct; 2B builds and proves the Worker offline. 2B requires separate owner authorization.

1. One bounded NFL Player Availability Worker records supported official facts, not football-performance judgments.
2. Preserve the complete official description exactly as published (including multiple body areas, Illness, Rest or blank). Do not infer diagnosis, severity, laterality, prognosis, playing likelihood or performance effect.
3. Preserve practice observations by day when the source supplies the day. Retain undated league participation separately; never invent a date.
4. Field-specific, time-aware authority: official club injury report primary for dated practice chronology; official league injury report cross-check/additional observation. Neither automatically overrides legitimate later eligible evidence from the other. A confirmed later official update may supersede an earlier observation; preserve both. If chronology cannot be established for differing comparable observations, flag unresolved conflict; do not guess. Capture time is not publication time.
5. Exclude beat writers, player accounts, X posts, free-text club news, healing/re-aggravation interpretation, pitch-count and workload expectations and football-performance interpretation. These belong to a later separately researched and approved lane.
6. Separate mechanical detection from human adjudication. Mechanically process differences, supported updates, missing fields, potential staleness, out-of-scope inputs, absence against an explicitly defined expected population, unsupported structure and post-cutoff evidence. Human judgment is needed where deterministic rules cannot establish a supported result: unresolved official conflict, ambiguous identity, uncertain admissibility chronology, unexplained missing required information, materially changed structure, disappearance whose reason matters, or proposed expansion. A legitimate supported update does not automatically require human review. Review-screen construction is deferred.
7. Define correctness, versioned rubric, independently approved expected outputs, negative cases, acceptance and safe failures in 2A; implement offline evaluation in 2B. Native pilot-quality-grade ledger writer DEFERRED; required before the next applicable graded live provider pilot. ADR-010 revision 12 historical documentary exception is not presumed available for a future pilot. Native reporting requirements likewise remain in force.
8. Future implementation is parser-first; no competing parser/model implementations. A model becomes a candidate only on an approved representative fixture demonstrating necessary in-scope information that bounded deterministic rules cannot reliably extract or reconcile. Separate authorization required.
9. New versioned domain contract; no retroactive changes to frozen Phase 6 contract, no implied Core record type or general schema framework.
10. Inactive-list extraction excluded from first Worker; later availability stage and/or separately identified outcome evidence. Never overwrite an earlier cutoff-bound injury-report state retroactively.
11. No severity scales, weights, probabilities, thresholds, player importance, team impact, performance effects, availability or game prediction, market lines or market-line reasoning.

12. APPROVE NFLVERSE INTERIM SOURCE: nflverse is the interim research source for real 2A sample records, with required attribution and dataset-specific provenance, rights and timing audit before production reliance. Controlled F01–F15 cases are primary contract tests; permitted frozen real samples separately establish mapping/realism. No mandatory NFL/club webpage captures or dependency on rare natural events. Share the SOURCE with Cyrus, not its code or storage. Ripley retains its own frozen sample identities.
13. STRICT PASS: every required case must satisfy its independently approved expected result; no partial-credit milestone pass. Every explicit cutoff must be no later than scheduled kickoff.
14. NO NEW DATABASE NOW. Use existing supported Ripley persistence and immutable fixture files for 2A/candidate 2B. If workload evidence requires a query layer, evaluate local SQL first; PostgreSQL if shared transactional/concurrent requirements arise; BigQuery if measured analytical scale, shared access or query requirements justify cloud warehousing. Storage never replaces Ripley provenance/admissibility governance. Deferred architecture note only.
15. ROADMAP ONLY: PFF/performance evidence, weather, news, X/social, local reporting, market expansion, FantasyPros/RotoWire context, other paid providers, SQL analytical expansion, PostgreSQL and BigQuery. No substantial design or implementation of these lanes here.

Worker implementation, 2B, live Worker, provider calls, provider purchase/account/subscription, automated or live acquisition, database construction, agent implementation and generic infrastructure work are NOT AUTHORIZED. Generic infrastructure remains CLOSED; workload evidence is required to reopen a specific capability. First capability is a Worker, not an agent; no agent ADR is justified by this bounded contract.

Research basis: reconciled owner-approved rules supplied by the Chair; supporting brief identified as ripley-nfl-milestone-2a-research-brief-and-owner-choices-2026-11-27.md, reported 18,655 bytes, SHA-256 bf57963ee3f2bef1af17c54bb21a7947a9a128a5f913354a918d08c0d355accd. Original brief not independently authenticated by this author. No current 2026 full league injury-report policy text was confirmed in the research package; observed 2026 pages do not replace current governing policy. Do not treat historical policy as a confirmed 2026 rule. Automated acquisition terms/rights and X/third-party automated acquisition remain outside scope.

### Existing Cyrus source evidence (read-only)

Repository `Ibmcleaner/cyrus-nfl-analytics`, commit `715d5c66c038857419efcbc5c847fd311f0c7621`, file `weekly_props.py`, Git blob `36ce8d033d538a1726c67030c78c9ab07cc773ba`, independently inspected. Base URL `https://github.com/nflverse/nflverse-data/releases/download`; injury path `/injuries/injuries_{season}.csv`, saved as `inj.csv`; filtered by week and `game_type == REG`; status lookup uses `gsis_id` and `report_status`. Also downloads depth-chart data. Historical exception handler substitutes an empty injury DataFrame following acquisition/read failure. Ripley MUST NOT inherit that behavior: ACQUISITION / EXTRACTION FAILURE is distinct from SUCCESSFUL SOURCE WITH NO LISTED INJURIES. No historical workload modification, dependency on its directories, code reuse or shared storage. Historical code proves acquisition path, not present availability, sample identity, exact upstream rights or completeness.

## 2A-D02 — Versioned Worker domain contract

Proposed logical identity: nfl-player-availability / version 1 (new domain contract, distinct from historical Phase 6 prompt/schema). This is a document contract only; no executable schema or runtime change. Detailed representation choices below are proposed specification refinements for exact-head review, not new owner rulings.

### Inputs

One identified game per case: season, week, game identifier, participating clubs, scheduled kickoff timestamp with offset, explicit inclusive cutoff timestamp with offset no later than scheduled kickoff, source manifest and frozen input. Normalize comparable instants to UTC while preserving originals. Domain semantics are independent of CSV, JSON, XML or HTML. First candidate mapping: nflverse structured records; not implemented here. Controlled observations and permitted real samples are separate evidence classes. Each snapshot carries source/register version, supplier, dataset identity/URL, exact bytes/hash, capture time and independently supported availability/report-state evidence or unknown. No network fetch or out-of-scope input. A case may have no qualifying evidence. Optional expected population separately supplied, bounded to game and supported/approved; no implied entire roster.

### Outputs

One record per unambiguously identified player actually listed in eligible reports, not one per source row. Unresolved identities are preserved as separate unresolved observations/exceptions rather than falsely merged or assigned a fabricated player record. Separately report expected-population absences only if that population was supplied. No invented players. Case output includes contract version, game identity, cutoff, kickoff, eligible/excluded source IDs and reasons, player records, unresolved observations and case-level exceptions. Each substantive value references exact frozen snapshot and record/field locator; references resolve against frozen bytes. Relay values are literal as supplied; do not claim exact original official wording without evidence of fidelity. Controlled outputs are test-only.

| Field | Meaning and allowed values |
|---|---|
| player | Exact displayed name(s), plus bounded player key if resolved; never invent identity |
| club | Listed club as supported by admitted source, constrained to game clubs; conflicting attribution unresolved |
| position | Literal position where supplied; otherwise explicit missing state |
| published_description | Complete literal source text including punctuation, multiple body areas, non-injury descriptions and visible blank; no anatomical normalization or inferred diagnosis |
| practice | Supported dated observations with exact source date, literal status and canonical DNP / LP / FP when unambiguous; undated values held separately, date null; other labels preserved literally and not coerced |
| game_status | Literal supplied designation or missing state; recognized Out / Doubtful / Questionable when supported; other labels preserved and flagged if unsupported; no probability; original authority identified only when established |
| observation history | Every eligible observation retained, including superseded observations; governing reference or unresolved field; no deletion of earlier states |
| provenance | Source ID, row locator, field/cell locator if needed, capture time and supported publication/report-state evidence or unknown |
| timing | Case cutoff, kickoff and capture timestamps; publication timestamp only if supported |
| flags | Typed missing, potential staleness, unresolved conflict, ambiguous identity, unsupported layout, extraction failure, excluded input, post-cutoff and expected-population absence; each with evidence and reason; no unsupported clinical conclusion |

For every field, preserve source literal separately from interpreted status. Missing state vocabulary: BLANK = visibly empty source field; UNLISTED = source or applicable established rule explicitly establishes no listed value/status; UNKNOWN = evidence cannot establish field; NOT APPLICABLE = field does not apply under contract; EXTRACTION FAILURE = supported source contains information processing failed to extract safely. None is interchangeable. An empty cell is not automatically UNLISTED. Not-yet-due practice is not a missing required observation. No qualifying evidence yields no supported player facts, explicit case-level no-qualifying-evidence disposition and separately justified expected-population absence if applicable.

Identity: use a stable source player identifier only where supplied and reliably linked; otherwise match exact displayed name plus club in the identified game only when unique and unambiguous across eligible observations. Preserve source identifiers and names; do not silently normalize ambiguous variants, use position as proof, match across games or invent a universal identity service. Conflicting identifiers, duplicate names or unsupported cross-source matches remain unresolved and require human judgment.

### Minimal neutral observation representation

Logical contract only, not an executable schema or new Core record type. Case context binds game/season/week, scheduled kickoff, cutoff and expected population. Referenced snapshot metadata binds bytes/hash, capture time and schema/register versions. Source ID resolves the register; record-specific upstream/authority exceptions remain in provenance.

| Proposed field | Disposition |
|---|---|
| observation_id | KEEP — stable within frozen case |
| source_id | KEEP — versioned register reference |
| source_class | MOVE TO SOURCE REGISTER — controlled/real also explicit in manifest |
| upstream_source | MOVE TO SOURCE REGISTER — record-specific exceptions in provenance |
| provider_record_id | KEEP — nullable if absent |
| player_id | KEEP — nullable if unresolved; displayed name in literal player observation |
| player_id_namespace | KEEP — never equate supplier IDs by spelling alone |
| team | KEEP — bounded game club |
| game_id / season / week | MOVE TO EVALUATION CONTEXT |
| field_type | KEEP — player/name, position, description, practice, designation or report observation |
| literal_value | KEEP — exact supplied value |
| normalized_value | KEEP — nullable, supported canonical mapping only |
| observed_for_date | KEEP — nullable, no invented date |
| provider_updated_at | KEEP — nullable raw supplier value with qualified meaning |
| captured_at | MOVE TO EVALUATION CONTEXT — referenced snapshot metadata |
| missing_state | KEEP — existing vocabulary; null for present value |
| evidence_locator | KEEP — exact row/field or equivalent |
| snapshot_id | KEEP — immutable evidence reference |
| schema_version | MOVE TO SOURCE REGISTER — snapshot binds actual version |
| derivation_reference | KEEP — nullable; required for derived controlled cases |

Rights not duplicated per observation. Supersession/conflict and review are reconciliation outputs, not source assertions. Failed acquisition/read/extraction requires explicit failure disposition, never successful empty report. Valid, admitted, successfully parsed source with no listed injuries is a distinct successful-empty disposition. Neither implies an unlisted player is healthy.

## 2A-D03 — Source authority / temporal contract

Interim research source: nflverse real samples subject to applicable rights/provenance checks before admission; controlled cases separately identified. Authorized official club/league evidence may be used where permitted but is not mandatory. Club remains primary for dated practice chronology; league additional official evidence/cross-check. Relay supplier, upstream/original source (if known) and original reporting authority are distinct; open or licensed relay status does not establish official authority. Preserve unknown lineage. Compare like fields for same resolved player/game and report context. Dated and undated values are not automatically contradictory. No unconditional supplier priority. Distinguish provider update time, Ripley capture time, independently supported publication/availability time, observation/report date and cutoff. nflverse date_modified is semantically UNKNOWN until audited; preserve literal value, never treat it as publication time or supersession proof merely by name.

Admissibility: verify manifest identity and frozen bytes; verify game/source scope; require evidence of availability by the explicit inclusive cutoff. A reliably timestamped capture at or before cutoff establishes that captured content existed by capture, not first publication. A later capture alone does not establish earlier availability. A post-cutoff capture is excluded unless independent evidence establishes the exact relevant content was available by cutoff; evidence first available after cutoff is always excluded. If the evidence cannot establish eligibility, retain it separately with reason and do not let it influence player facts, governing values or cutoff-bound evaluation. Do not infer chronology from capture order across publishers. Preserve capture time separately from publication/report-state evidence.

Reconciliation: compare eligible observations for same resolved player, field, practice day (where applicable) and comparable report state. Identical values corroborate. Confirmed later official update of the same applicable field may supersede earlier observation, with both references and chronology basis retained. A normal supported update is not a human-review exception. Differing comparable values at the same state, or with unestablished relative chronology, remain unresolved; preserve both, mark conflict and do not choose a winner. Earlier practice days are distinct observations, not superseded simply because another day exists. Omission in a later comparable report is an observation, not automatic evidence of health, reserve move or status change. Require comparable scope/completeness before classifying omission; failed or partial acquisition cannot establish disappearance.

Staleness: use season/game-specific reporting expectations only when supported by an independently identified applicable policy or approved evidence for the case. Record expected report type/time and evidence basis in manifest. Compare observed report state to that expectation; flag potential staleness if expected report is due and available saved evidence is older. If schedule/report deadline is unconfirmed, mark expectation unknown and do not assert lateness or missing required status. Do not assume a universal Wednesday-Friday schedule or a 2026 deadline from historical policy. Missing day not yet due is not an exception. No current full 2026 policy confirmed; page observations alone are not policy.

## 2A-D04 — Fixture package specification

Primary contract tests: controlled F01–F15. Realism/source mapping: frozen permitted nflverse samples, separately classified. No mandatory official webpage captures, no acquisition here, no reliance on rare natural events. No actual fixture bytes selected or frozen; no answer keys approved. Every controlled case below is a specification using fictional entities, not an assertion about a real player/game. Label every future controlled fixture **CONTROLLED TEST CONDITION — NOT ACTUAL NFL REPORTING HISTORY**. Use independently created content or permitted derivatives; preserve parent identity, exact derivation and separate hash for derivatives. Real records carry **REAL NFLVERSE SAMPLE — SOURCE-MAPPING / REALISM EVIDENCE**. Source-use permission must be established before admission/publication.

### Controlled case specification

Common fictional context C1: game TEST-G1, clubs TEST-A/TEST-B, players P1/P2 in TEST namespace unless specified. Synthetic scheduled kickoff K = 2030-09-08T18:00:00Z; T1 = 2030-09-04T18:00:00Z, T2 = 2030-09-05T18:00:00Z, T3 = 2030-09-06T18:00:00Z, L = 2030-09-08T19:00:00Z. These are invented test-clock parameters, not NFL schedules/publication claims. Unless stated otherwise cutoff K; fixture manifest establishes synthetic eligibility and chronology for T1/T2/T3, with capture at those instants. Each case independent; unmentioned fields UNKNOWN or NOT APPLICABLE as justified by answer key, not invented. Each eventual fixture binds controlled bytes, source/record locators, expected fields, dispositions and owner-approved answer key. All below are PROPOSED CONTROLLED SPECIFICATION — fixture bytes and answer approval outstanding.

| ID / purpose | Controlled inputs / cutoff | Expected fields and safe behavior for owner approval | Proves / does NOT prove | Real nflverse sample additionally useful? |
|---|---|---|---|---|
| F01 dated practice progression | P1 DNP on T1 date, LP on T2 date, FP on T3 date; K | Three distinct dated entries, exact literals/canonical values and references; no conflict or severity inference | Chronological retention / not actual improvement or daily source coverage | Conditional on actual dated entries |
| F02 multiple descriptions | P1 description "Thumb, Toe" at T1; K | Preserve exact whole literal; no inferred anatomy/laterality/severity; cite row | Literal preservation / not clinical accuracy | Yes if supplied; preserve split fields without claiming original punctuation |
| F03 non-anatomical description | P1 "Rest", P2 "Illness" at T1; K | Preserve both literals, correct attribution, no invented body area | Non-anatomical handling / not diagnosis or real player condition | Conditional on actual records |
| F04 game-status change | P1 Questionable T1, Out T3, supported later state; K | Both retained, governing Out; normal update not mandatory review; no probabilities | Status change / not natural NFL transition or prediction | Only if comparable revisions retained |
| F05 supersession | P1 Doubtful T1, Questionable T2 with explicit same-field update relation in test metadata; K | Governing T2, supersedes T1, both locators and chronology basis; no automatic review | Supported precedence / not actual publication chronology or revision retention | Conditional on audited timing/revisions |
| F06 disappearance | Complete comparable report T1 lists P1/P2; complete later T3 lists only P2; K | Preserve P1 history; flag later absence, no inferred cause/deletion; human judgment only if reason needed | Bounded omission detection / not real reserve move or health | Only with comparable complete retained states |
| F07 comparable-source conflict | S1/S2 disagree on P1 same game/field/report state T2 (Out vs Questionable), no ordering; K | Both literals/references; unresolved governing value UNKNOWN, conflict/review required | Conflict branch / not real independent-source disagreement | Conditional; one feed may not supply it |
| F08 undated practice | P1 league-style LP T2, no practice date; K | Undated LP separate, date null; no invented date | Undated handling / not actual league layout | Yes if undated value present |
| F09 blank vs unlisted | P1 visibly empty designation; P2 explicit none-listed with supported source meaning; K | P1 BLANK, P2 UNLISTED, preserve literal and reason; no availability inference | Missing-state distinction / not actual source blank semantics | Conditional on audited schema; null not automatically either |
| F10 day not yet due | T1 P1 DNP; approved synthetic T2 expectation later than cutoff T1 | Retain T1, T2 not yet due; no false missing/stale or review | Timing expectation logic / not 2026 deadline | Only with applicable schedule evidence |
| F11 unsupported structure | Controlled malformed/unrecognized layout T1; K | Explicit unsupported-structure/extraction failure, block affected facts, diagnostic and human review if material; not successful empty | Safe failure / not supported real mapping | Permitted real parent only, not failure evidence itself |
| F12 post-cutoff evidence | P1 Questionable T1; Out first available L; K | Same supported facts as early-only; exclude L with reason; no leakage | Cutoff isolation / not actual publication timing | Conditional on verified availability |
| F13 no qualifying evidence | Only P1 Out L, no independent earlier proof; K | No qualifying evidence, empty supported player set, exclusion reason; not successful empty or extraction failure | No-evidence disposition / not no injuries or history | Conditional on documented temporal limits |
| F14 identity ambiguity | Two same-name TEST-A players with no reliable IDs and ambiguous cross-source match T1; K | Separate unresolved observations, no false merge/ID; human review | Identity safeguard / not universal ID resolution | Conditional on actual ambiguity |
| F15 multiple-player attribution | P1 TEST-A Toe/DNP, P2 TEST-B Thumb/FP T1; K | Separate players, correct club/description/practice/references; zero cross-attribution | Attribution / not full roster coverage | Yes with distinct real IDs/records |

Additional required negatives: N01 conflicting capture order without supported publication order — no inferred supersession; N02 out-of-scope input — reject/quarantine; N03 unreadable source vs visible blank vs valid successful empty report — distinguish all three with diagnostic; N04 unsupported cross-source identity — unresolved review; N05 unknown reporting expectation — no asserted staleness/deadline; N06 hash/manifest mismatch — block; N07 cutoff later than kickoff — reject case before player evaluation. Use C1/K unless invalid cutoff L. All test-only, expected answers approved before execution.

### Manifest and future real nflverse sample package

Each case manifest: case ID/version, evidence class, game/season/week/clubs, scheduled kickoff/cutoff, expected population if any, source-register ID/version, snapshot IDs, original URL/dataset identity, saved filename, exact frozen bytes or expressly authorized subset, byte count, SHA-256, retrieval/capture time with basis, independently supported availability/publication/report-state evidence or unknown, applicable reporting expectation and basis or unknown, schema/version reference if available, selected record identifiers (e.g. supplied GSIS IDs and row locators), coverage IDs, provenance/temporal limitations, expected-output identity, owner approval and rights status. For subsets preserve parent identity when available, exact selection/derivation and limitations; never claim reproduction of unavailable full bytes. Keep Ripley's immutable artifacts outside Cyrus directories. No credentials. No acquisition now. date_modified is not publication time unless NV-04 establishes that meaning. Retrospective samples lacking admissibility proof test mapping/realism but cannot establish cutoff-eligible facts. Real mapping independently demonstrates actual field/identity/missing-value mapping; unsupported fields remain explicit limitations. No sample selected, downloaded, retained or approved here.

### Versioned source register (documentation only)

Register version 1, effective on owner acceptance of this amendment; exact effective date to be recorded, not invented. Each entry records source identifier, supplier/project name, dataset/feed, source class, upstream/original source and original authority if known, license/rights reference, attribution requirement, permitted internal use, permitted retention, permitted derived/controlled use, reviewer-access restrictions, production/commercial status, unresolved rights questions and effective/version date. No licensing engine.

| Entry | Current disposition |
|---|---|
| NV-INJURY | nflverse / injuries CSV / open-data relay candidate. https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv (historical acquisition path verified, current bytes not verified). Upstream/official authority UNKNOWN pending NV-01. Dataset-specific license/rights unresolved NV-02/NV-08. Attribution as required, exact wording pending NV-03. Owner-approved interim research candidate only; actual internal use, retention, derivative use and reviewer permission must be established before admission; no production/commercial reliance authorized. NV-01–NV-08 OPEN. |
| CONTROLLED-2A | Owner-created fictional test observations; no original official authority or third-party content required. Internal specification permitted by owner decision; reviewer access under project governance; if derived from real parent, require parent rights, attribution, retention and reviewer permissions. Not actual NFL reporting history or production source. |

### nflverse open audit questions

| ID | Question | State |
|---|---|---|
| NV-01 | Exact upstream injury dataset source? | OPEN |
| NV-02 | Exact applicable injury dataset license? | OPEN |
| NV-03 | Required attribution? | OPEN |
| NV-04 | Exact meaning of date_modified? | OPEN — semantically UNKNOWN |
| NV-05 | Update latency relative to underlying report? | OPEN |
| NV-06 | Historical revisions retained or overwritten? | OPEN |
| NV-07 | Exact frozen copies retainable as evaluation artifacts under terms? | OPEN |
| NV-08 | Dataset-specific commercial/internal-use restrictions or exceptions? | OPEN |

Do not answer by assumption. Audit provenance/license, attribution and timing before production reliance; resolve actual use/retention/reviewer rights before sample admission. Owner source approval is not a grant of third-party rights.

## 2A-D05 — Expected-result specification

Before Worker execution, owner/team inspect frozen controlled inputs and permitted real samples separately and apply D02/D03 independently of Worker output. Controlled expected results must not mirror implementation behavior; real-source answers identify actual supplied fields and distinguish mapping correctness from factual/temporal admissibility. Produce a versioned answer key per case containing case/manifest hash, contract/rubric version, exact expected player set, each literal and canonical field, missing state, observation history, governing/superseded references, conflicts, exclusions, timestamps, flags and safe disposition. Every assertion points to a frozen record/field locator or governing rule; expected unknowns and absent population are explicitly justified. Robert approves the expected results and any unresolved case disposition; approval recorded with identity/date and answer-key bytes/hash. No answer key generated from future Worker results or validator success; disagreements in expected answers resolved before acceptance. Preserve original approved key; changes require review and versioning, not tuning after seeing outputs. No actual answer keys claimed complete here.

## 2A-D06 — Evaluation and review specification

Rubric logical identity nfl-availability-offline / version 1. Field-level assessments: case ID, player key or unresolved observation ID, field, expected value/state, actual value/state, supporting references, correct true/false, reason. Assess player population/identity, club, position, literal description, dated and undated practice, game status, history/supersession, provenance, cutoff/admissibility, missing-state distinctions, conflict/staleness flags, exclusions and safe-failure disposition. Compare exact text (no trimming away source meaning), dates/instants, allowed values, reference sets and multiplicity; ordering is deterministic for comparison but does not invent chronological order when unknown. Compare complete output, including unexpected players/fields/observations and missing expected ones. Verify every source locator and content identity. No partial-credit weighting or probabilities.

Owner-approved STRICT PASS: every required case passes its approved expected result; no partial-credit milestone pass. Category A — DOMAIN-CONTRACT TESTS: controlled F01–F15 and required negatives. Category B — SOURCE-MAPPING / REALISM TESTS: permitted real frozen nflverse samples with independent expected mappings and stated limitations. Every required coverage ID has an approved controlled fixture and independently approved answer key; every required real mapping case likewise has an approved sample and key. Every case passes exact comparison of all applicable fields and expected dispositions; zero unsupported facts, wrong-player attribution, invented dates, cutoff leaks, missing required observations, unreported unresolved conflicts, unsafe fallback or unexplained skips. Negative cases must produce the expected safe failure, not merely crash. Repeat same frozen inputs and contract to obtain equivalent output; preserve test command, baseline, fixture/answer-key identities, actual outputs, comparison report and pass/fail evidence. No claim of general NFL source coverage or live-model accuracy. Controlled cases do not prove real provider mapping; real records alone do not prove every rare contract branch. Report categories separately; unknown temporal eligibility is not silently upgraded. Reject cutoff later than scheduled kickoff. Acceptance requires independent review and owner decision.

Mechanical detection: validate input/manifest and scope; detect comparable source differences, supported later changes, missing fields, potential staleness, out-of-scope data, expected-population absences, unsupported structure and post-cutoff content. Reject/quarantine ineligible inputs with explicit reasons. For unsupported layout or extraction failure, block affected facts and preserve diagnostic evidence; do not silently return success. For missing facts return explicit missing states; no-evidence case cannot fabricate a player. A supported ordinary update needs no automatic human review.

Human adjudication: unresolved official conflict, ambiguous identity, uncertain chronology affecting eligibility, unexplained missing required information, materially changed structure, disappearance when its reason matters, or scope expansion. Human decision cannot manufacture evidence or silently relax cutoff. Exception review is distinct from owner quality grading of completed outputs, including outputs with no exceptions. Offline comparisons and owner judgments are test artifacts, not native ledger grades. Native pilot-quality-grade writer remains DEFERRED and is a prerequisite before the next applicable graded live provider pilot; future ADR-010 Decision 15/16 requirements remain controlling. No review GUI authorized.

## 2A-D07 — Candidate Milestone 2B assignment

**NFL AVAILABILITY OBSERVATION NORMALIZER — SINGLE-SOURCE OFFLINE PROOF**

**NOT AUTHORIZED FOR EXECUTION.**

Objective: build and prove offline one bounded deterministic availability normalizer against the separately versioned D02/D03 contract and approved D04/D05/D06 evidence. Candidate source: nflverse unless replaced by separate owner approval. Prerequisites: independently reviewed 2A package, approved frozen controlled fixtures and permitted real samples, independent answer keys, confirmed source format and rights, exact repository baseline and separately released owner assignment defining file scope and acceptance commands.

Candidate future work: deterministic field mapping, source identifier/namespace and literal-value preservation, bounded identity matching, missing-state handling, temporal admissibility, supported supersession, unresolved conflicts, explicit flags and safe failure; offline evaluation of both categories. Use existing supported Ripley persistence and immutable fixtures; first establish fit without Core changes. Exact paths/test counts determined only at release after actual fixture inspection. Verify reproducibility and applicable regression gates. Parser-first means deterministic processing of supported structured input, not webpage-first. No competing parser/model implementation. If a representative approved fixture proves deterministic processing insufficient for a necessary in-scope requirement, stop and report; model requires separate authorization. A concrete missing Ripley capability requires separate workload-triggered decision, not automatic Foundation reopening.

Acceptance: STRICT PASS, approved fixtures and keys, exact bounded diff, independent review and owner acceptance. Exclude live acquisition, multiple provider integrations, LLM inference, provider purchase/account/calls, database construction, SQL/BigQuery build, PFF, weather, news/X/local reporting, market feeds, prediction/weighting/severity, agents, inactive-list extraction, GUI, native grade writer and frozen Phase 6 changes. No runtime work now. 2B remains NOT AUTHORIZED. This amendment is not 2A exit acceptance; fixture materialization, sample rights/selection and expected-answer approval remain outstanding.

