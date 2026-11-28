# Ripley One — NFL Milestone 2A domain package

Owner: Robert Legorreta, Cyrus Forge Systems, LLC.  
Authorization: "APPROVE ALL+" — reconciled owner-decision block supplied by Copilot.  
Baseline: `21e48d0527c3a36795ccf8d42d119f4b8c50ffb9` (PR #65 merge).  
Status: AUTHORIZED — domain contract, source rules, fixture/test-material specification and evaluation design only. This package is a specification for independent review, not a completed fixture selection or implementation acceptance.

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

Worker implementation, 2B, provider calls, automated network acquisition, agent implementation and generic infrastructure work are NOT AUTHORIZED. Generic infrastructure remains CLOSED; workload evidence is required to reopen a specific capability. First capability is a Worker, not an agent; no agent ADR is justified by this bounded contract.

Research basis: reconciled owner-approved rules supplied by the Chair; supporting brief identified as ripley-nfl-milestone-2a-research-brief-and-owner-choices-2026-11-27.md, reported 18,655 bytes, SHA-256 bf57963ee3f2bef1af17c54bb21a7947a9a128a5f913354a918d08c0d355accd. Original brief not independently authenticated by this author. No current 2026 full league injury-report policy text was confirmed in the research package; observed 2026 pages do not replace current governing policy. Do not treat historical policy as a confirmed 2026 rule. Automated acquisition terms/rights and X/third-party automated acquisition remain outside scope.

## 2A-D02 — Versioned Worker domain contract

Proposed logical identity: nfl-player-availability / version 1 (new domain contract, distinct from historical Phase 6 prompt/schema). This is a document contract only; no executable schema or runtime change. Detailed representation choices below are proposed specification refinements for exact-head review, not new owner rulings.

### Inputs

One identified game per case: season, game identifier, participating clubs, kickoff timestamp with offset, explicit cutoff timestamp with offset, source manifest and frozen official club/league injury report bytes. Normalize comparable instants to UTC while preserving supplied originals. Kickoff is context, not an implicit cutoff. Each page must carry source identifier, publisher, report type, original URL, content hash, byte count, capture time and any independently supported publication/report-state evidence with its provenance. Unknown publication time is allowed and must remain unknown. No network fetch or unofficial input. Case may intentionally contain no qualifying pages. Optional expected population must be separately supplied, bounded to this game and supported/approved; no implied entire roster.

### Outputs

One record per unambiguously identified player actually listed in eligible reports, not one per source row. Unresolved identities are preserved as separate unresolved observations/exceptions rather than falsely merged or assigned a fabricated player record. Separately report expected-population absences only if that population was supplied. No invented players. Case output includes contract version, game identity, cutoff, kickoff, eligible/excluded source IDs and reasons, player records, unresolved observations and case-level exceptions. Each substantive value references exact source page and row (or field/cell where needed); evidence references must resolve against frozen bytes.

| Field | Meaning and allowed values |
|---|---|
| player | Exact displayed name(s), plus bounded player key if resolved; never invent identity |
| club | Official listed club, constrained to game clubs; conflicting attribution unresolved |
| position | Literal official position where supplied; otherwise explicit missing state |
| published_description | Complete literal source text including punctuation, multiple body areas, non-injury descriptions and visible blank; no anatomical normalization or inferred diagnosis |
| practice | List of dated official observations with exact source date, literal status and supported canonical DNP / LP / FP when unambiguous; undated league values held in a separate undated list, date null; other labels preserved literally and not coerced |
| game_status | Literal official word or missing state; recognized Out / Doubtful / Questionable when actually published; other labels preserved and flagged if unsupported; no probability |
| observation history | Every eligible observation retained, including superseded observations; governing reference or unresolved field; no deletion of earlier states |
| provenance | Source ID, row locator, field/cell locator if needed, capture time and supported publication/report-state evidence or unknown |
| timing | Case cutoff, kickoff and capture timestamps; publication timestamp only if supported |
| flags | Typed missing, potential staleness, unresolved conflict, ambiguous identity, unsupported layout, extraction failure, excluded input, post-cutoff and expected-population absence; each with evidence and reason; no unsupported clinical conclusion |

For every field, preserve source literal separately from interpreted status. Missing state vocabulary: BLANK = visibly empty source field; UNLISTED = source or applicable established rule explicitly establishes no listed value/status; UNKNOWN = evidence cannot establish field; NOT APPLICABLE = field does not apply under contract; EXTRACTION FAILURE = supported source contains information processing failed to extract safely. None is interchangeable. An empty cell is not automatically UNLISTED. Not-yet-due practice is not a missing required observation. No qualifying evidence yields no supported player facts, explicit case-level no-qualifying-evidence disposition and separately justified expected-population absence if applicable.

Identity: use a stable source player identifier only where supplied and reliably linked; otherwise match exact displayed name plus club in the identified game only when unique and unambiguous across eligible observations. Preserve source identifiers and names; do not silently normalize ambiguous variants, use position as proof, match across games or invent a universal identity service. Conflicting identifiers, duplicate names or unsupported cross-source matches remain unresolved and require human judgment.

## 2A-D03 — Source authority / temporal contract

Only owner-saved official club injury-report pages and official NFL league injury-report pages for the identified game. Club is primary for dated practice chronology; league is additional official evidence/cross-check, not a source of invented practice dates. For description, position and game status retain source-specific observations; compare only like fields for same resolved player/game and report context. A dated practice value and an undated value are not automatically contradictory. No unconditional publisher priority.

Admissibility: verify manifest identity and frozen bytes; verify game/source scope; require evidence of availability by the explicit inclusive cutoff. A reliably timestamped capture at or before cutoff establishes that captured content existed by capture, not first publication. A later capture alone does not establish earlier availability. A post-cutoff capture is excluded unless independent evidence establishes the exact relevant content was available by cutoff; evidence first available after cutoff is always excluded. If the evidence cannot establish eligibility, retain it separately with reason and do not let it influence player facts, governing values or cutoff-bound evaluation. Do not infer chronology from capture order across publishers. Preserve capture time separately from publication/report-state evidence.

Reconciliation: compare eligible observations for same resolved player, field, practice day (where applicable) and comparable report state. Identical values corroborate. Confirmed later official update of the same applicable field may supersede earlier observation, with both references and chronology basis retained. A normal supported update is not a human-review exception. Differing comparable values at the same state, or with unestablished relative chronology, remain unresolved; preserve both, mark conflict and do not choose a winner. Earlier practice days are distinct observations, not superseded simply because another day exists. Omission in a later page is an observation, not automatic evidence of health, reserve move or status change.

Staleness: use season/game-specific reporting expectations only when supported by an independently identified applicable policy or approved evidence for the case. Record expected report type/time and evidence basis in manifest. Compare observed report state to that expectation; flag potential staleness if expected report is due and available saved evidence is older. If schedule/report deadline is unconfirmed, mark expectation unknown and do not assert lateness or missing required status. Do not assume a universal Wednesday-Friday schedule or a 2026 deadline from historical policy. Missing day not yet due is not an exception. No current full 2026 policy confirmed; page observations alone are not policy.

## 2A-D04 — Fixture package specification

No fixtures selected or acquired by this package. First establish coverage, then request targeted owner-saved evidence rather than arbitrary weeks. Keep real source bytes immutable; no synthetic evidence represented as official. Each case manifest records case ID/version, season/game/clubs/kickoff/cutoff, expected population if any, source ID/publisher/type/URL, saved filename, bytes/SHA-256, capture timestamp and basis, independently supported publication/report state and basis or unknown, relevant reporting expectation and basis or unknown, row locators, coverage IDs, expected-output identity, owner approval and allowed-use status. Unsupported layout/no-evidence cases may use documented negative test inputs, explicitly distinguished from real official pages; do not fabricate source facts. No automated acquisition; source-use permission must be resolved before material is admitted or published.

| ID | Required scenario | Expected behavior | Selection |
|---|---|---|---|
| F01 | DNP -> LP -> FP progression | Preserve three dated observations without interpreting improvement | REQUIRED — FIXTURE NOT YET SELECTED |
| F02 | Multiple body areas | Preserve exact complete description | REQUIRED — FIXTURE NOT YET SELECTED |
| F03 | Non-anatomical description | Preserve literal Illness/Rest or other published description without injury classification | REQUIRED — FIXTURE NOT YET SELECTED |
| F04 | Status upgrade or downgrade | Preserve official status history without probability or severity inference | REQUIRED — FIXTURE NOT YET SELECTED |
| F05 | Confirmed later official update | Supersede only with established chronology and retain earlier evidence | REQUIRED — FIXTURE NOT YET SELECTED |
| F06 | Player omitted from later report | Record absence; no inferred reason or automatic deletion | REQUIRED — FIXTURE NOT YET SELECTED |
| F07 | Club/league disagreement | Resolve supported supersession or flag unresolved comparable conflict | REQUIRED — FIXTURE NOT YET SELECTED |
| F08 | Undated league practice | Retain separately with null date | REQUIRED — FIXTURE NOT YET SELECTED |
| F09 | Blank versus none-listed | Distinguish BLANK from UNLISTED | REQUIRED — FIXTURE NOT YET SELECTED |
| F10 | Practice day not yet due | No false missing-required-field or stale flag | REQUIRED — FIXTURE NOT YET SELECTED |
| F11 | Unsupported source structure | Fail safely; no invented player facts; identify structure exception | REQUIRED — FIXTURE NOT YET SELECTED |
| F12 | Post-cutoff evidence | Exclude from cutoff-bound facts and retain exclusion reason | REQUIRED — FIXTURE NOT YET SELECTED |
| F13 | No qualifying source evidence | Explicit no-evidence disposition; no fabricated result | REQUIRED — FIXTURE NOT YET SELECTED |
| F14 | Potentially ambiguous player identity | Preserve unresolved observations; no unsupported merge | REQUIRED — FIXTURE NOT YET SELECTED |
| F15 | Multiple-player attribution | Each field references correct player and source row | REQUIRED — FIXTURE NOT YET SELECTED |

Additional negative coverage: distinct capture/publication chronology; out-of-scope input; extraction failure versus visible blank; unsupported cross-source identity; unknown reporting schedule; hash/manifest mismatch. All REQUIRED — FIXTURE NOT YET SELECTED. A case may cover multiple IDs if independently demonstrated; coverage must be documented, not presumed.

## 2A-D05 — Expected-result specification

Before Worker execution, owner/team inspect frozen eligible pages and apply D02/D03 manually and independently of Worker output. Produce a versioned answer key per case containing case/manifest hash, contract/rubric version, exact expected player set, each literal and canonical field, missing state, observation history, governing/superseded references, conflicts, exclusions, timestamps, flags and safe disposition. Every assertion points to a source row/cell or governing rule; expected unknowns and absent population are explicitly justified. Robert approves the expected results and any unresolved case disposition; approval recorded with identity/date and answer-key bytes/hash. No answer key generated from future Worker results or validator success; disagreements in expected answers resolved before acceptance. Preserve original approved key; changes require review and versioning, not tuning after seeing outputs. No actual answer keys claimed complete here.

## 2A-D06 — Evaluation and review specification

Rubric logical identity nfl-availability-offline / version 1. Field-level assessments: case ID, player key or unresolved observation ID, field, expected value/state, actual value/state, supporting references, correct true/false, reason. Assess player population/identity, club, position, literal description, dated and undated practice, game status, history/supersession, provenance, cutoff/admissibility, missing-state distinctions, conflict/staleness flags, exclusions and safe-failure disposition. Compare exact text (no trimming away source meaning), dates/instants, allowed values, reference sets and multiplicity; ordering is deterministic for comparison but does not invent chronological order when unknown. Compare complete output, including unexpected players/fields/observations and missing expected ones. Verify every source locator and content identity. No partial-credit weighting or probabilities.

Proposed offline passing criterion: every required coverage ID has a selected, approved case and independently approved expected output; every case passes exact comparison of all applicable fields and expected dispositions; zero unsupported facts, wrong-player attribution, invented dates, cutoff leaks, missing required observations, unreported unresolved conflicts, unsafe fallback or unexplained skips. Negative cases must produce the expected safe failure, not merely crash. Repeat same frozen inputs and contract to obtain equivalent output; preserve test command, baseline, fixture/answer-key identities, actual outputs, comparison report and pass/fail evidence. No claim of general NFL source coverage or live-model accuracy. Acceptance requires independent review and owner decision.

Mechanical detection: validate input/manifest and scope; detect page differences, supported later changes, missing fields, potential staleness, out-of-scope data, expected-population absences, unsupported structure and post-cutoff content. Reject/quarantine ineligible inputs with explicit reasons. For unsupported layout or extraction failure, block affected facts and preserve diagnostic evidence; do not silently return success. For missing facts return explicit missing states; no-evidence case cannot fabricate a player. A supported ordinary update needs no automatic human review.

Human adjudication: unresolved official conflict, ambiguous identity, uncertain chronology affecting eligibility, unexplained missing required information, materially changed structure, disappearance when its reason matters, or scope expansion. Human decision cannot manufacture evidence or silently relax cutoff. Exception review is distinct from owner quality grading of completed outputs, including outputs with no exceptions. Offline comparisons and owner judgments are test artifacts, not native ledger grades. Native pilot-quality-grade writer remains DEFERRED and is a prerequisite before the next applicable graded live provider pilot; future ADR-010 Decision 15/16 requirements remain controlling. No review GUI authorized.

## 2A-D07 — Candidate Milestone 2B assignment

**NOT AUTHORIZED FOR EXECUTION.**

Objective: build and prove offline one bounded deterministic NFL Player Availability Worker against the separately versioned D02/D03 contract and approved D04/D05/D06 evidence. Prerequisites: independently reviewed 2A package, selected and approved coverage fixtures and answer keys, confirmed supported source layouts, exact repository baseline and separately released owner assignment defining file scope and acceptance commands.

Candidate implementation: deterministic parsing of supported club per-day and league tables; bounded identity matching, literal extraction, temporal eligibility and deterministic reconciliation; explicit flags and safe failure. Use existing supported Ripley mechanisms; first establish fit without Core changes. Exact file paths and test count must be established at release after inspection of actual fixture formats; no implementation now. Build offline evaluator and tests covering F01-F15 and additional negative cases, verify repeated outputs, preserve evidence and run applicable existing regression gates. No parallel model implementation. If an approved fixture demonstrates a material required capability cannot reliably be handled with bounded deterministic rules, stop and report reproducible evidence; model candidate requires separate authorization. A concrete missing Ripley capability likewise requires separate workload-triggered decision, not automatic infrastructure reopening.

Acceptance: all D06 criteria, approved fixtures and expected answers, exact bounded diff, independent review and owner merge/acceptance. No provider calls, automated acquisition, agent, inactive-list extraction, weights/severity/prediction, frozen Phase 6 changes, GUI or native grade writer in this candidate. No 2B work until separate owner release. This package's publication is not 2A exit acceptance; fixture selection and expected-answer approval remain outstanding.
