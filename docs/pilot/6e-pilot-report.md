# Phase 6E — historical live pilot report and documentary owner grade

Prepared 2026-11-27. Documentary grade explicitly accepted and Stage 6E accepted by the owner on 2026-11-27; final repository acceptance completed by merge of PR #63. ADR-010 revision 12 is merged and controlling (PR #62). This report covers only Dispatches #1–#3.

## 1. Evidence and seven-count accounting

Sources: [Dispatch #1](6d-dispatch-01.md), [Dispatch #2](6d-dispatch-02.md), [Dispatch #3](6d-dispatch-03.md), and supplied owner/team read-only evidence. #1/#2 raw ledgers UNLOCATED, not recovered or proven destroyed; their values are documentary-supported historical values, not reproduced from raw ledgers during 6E. Their recorded historical hashes remain verification identities if found. #3 preserved raw-ledger evidence is relayed from the owner/team; documentation author did not independently open SQLite. No substitute ledger, reconstruction or fabricated value.

| Measure | #1 documentary | #2 documentary | #3 preserved raw evidence | Pilot value |
|---|---:|---:|---:|---:|
| attempted | 1 | 1 | 1 | 3 |
| confirmed_sent | 1 | 1 | 1 | 3 |
| uncertain_dispatch | 0 | 0 | 0 | 0 |
| budget_slots_consumed | 1 | 1 | 1 | 3 |
| completed | 0 | 0 | 1 | 1 |
| validated | 0 | 0 | 1 | 1 |
| native owner_graded | 0 evidenced | 0 evidenced | 0 evidenced | 0 evidenced |

Separately: documentary owner grades accepted under ADR-010 revision 12 = 1. This is not a native ledger review record. Stage 6E acceptance is a separate owner decision, recorded on 2026-11-27.

The measures are live-mode provider Attempts only; mock runs, credential checks, refused pre-confirmation invocation, expired unused authorization and owner approval are excluded.

## 2. Usage

| Dispatch | Input tokens | Output tokens | Cache read |
|---|---:|---:|---:|
| #1 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| #2 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| #3 | 2222 | 521 | 0 |
| Known usage subtotal | 2222 | 521 | 0 |

Unavailable is not zero. This is a qualified known subtotal, not a complete pilot total. No dollar figure.

## 3. Latency observations

| Dispatch | Boundary | Interval |
|---|---|---:|
| #3 | attempt start -> completion | 8.613577 seconds |
| #3 | sent -> completion | 4.361814 seconds |
| #2 | dispatch sent -> task blocked | approximately 0.71 seconds |
| #1 | No comparable end timestamp | UNAVAILABLE |

Neither #3 interval is generic provider latency. #2 has a different boundary and is not comparable to #3. No distribution or aggregate statistics are established; no mean, median, spread or percentile.

## 4. Documentary owner grade

- Purpose: pilot_quality_grade (documentary label under ADR-010 revision 12).
- Result ID: `8cb121b4-466b-4005-a991-72cb71445bfe`; content hash: `2a9e3c2d741a3dfbd218212ec5703a512e69f0e7ed659ae02e207edc2f90b49d`.
- Snapshot ID: `c43444ee-a671-4e03-a482-41c12fbc6828`; content hash: `24480b47c801f69705db100ac059ab03ea402ade3362339c1e8d70d7b4d3450e`.
- Rubric: availability-pilot; version: 1; grader: owner.
- Bound to the frozen packet and stored Result reviewed by Robert, as supplied in the reviewed grade handoff.
- Exact owner statement: "ROWS 1–15: TRUE".

| Row | player_id | field | correct | note |
|---:|---|---|---|---|
| 1 | kyle-monangai-chi | designation | TRUE | No additional field-specific note supplied |
| 2 | kyle-monangai-chi | practice | TRUE | No additional field-specific note supplied |
| 3 | kyle-monangai-chi | supersession | TRUE | No additional field-specific note supplied |
| 4 | kyle-monangai-chi | conflict | TRUE | No additional field-specific note supplied |
| 5 | kyle-monangai-chi | as_of | TRUE | No additional field-specific note supplied |
| 6 | malik-muhammad-chi | designation | TRUE | No additional field-specific note supplied |
| 7 | malik-muhammad-chi | practice | TRUE | No additional field-specific note supplied |
| 8 | malik-muhammad-chi | supersession | TRUE | No additional field-specific note supplied |
| 9 | malik-muhammad-chi | conflict | TRUE | No additional field-specific note supplied |
| 10 | malik-muhammad-chi | as_of | TRUE | No additional field-specific note supplied |
| 11 | tyrique-stevenson-chi | designation | TRUE | No additional field-specific note supplied |
| 12 | tyrique-stevenson-chi | practice | TRUE | No additional field-specific note supplied |
| 13 | tyrique-stevenson-chi | supersession | TRUE | No additional field-specific note supplied |
| 14 | tyrique-stevenson-chi | conflict | TRUE | No additional field-specific note supplied |
| 15 | tyrique-stevenson-chi | as_of | TRUE | No additional field-specific note supplied |

Robert's existing overall notes (owner-reported, not independent outcome verification):

- Kyle Monangai: correct. Robert knows he was questionable; he played.
- Malik Muhammad: correct. Questionable; he played.
- Tyrique Stevenson: looks right against the report; Robert did not follow him that week and cannot confirm from his own knowledge.
- The answer should carry the injury itself with the designation; "toe" as the report states it is sufficient.

Governed task-approval reason: "The extraction matches the packet and the diagnostic purpose was met." This is distinct from the grade. Approved approval record: `9f06d661-bfce-4c49-a45e-fb40defb9466`.

Each player had exactly one frozen packet row; practice, supersession and conflict exercised only the nothing-to-report case. The grade does not establish broader live handling of conflicting or superseding evidence. Future Milestone 2A ideas are not retroactive grade criteria; no additional judgments, scoring, severity or weights inferred.

## 5. Deferred / not done

- Native pilot-quality-grade tooling: DEFERRED.
- Complete automated Stage 6E reporting tooling: DEFERRED.
- Live provider-error capture verification: NOT EXERCISED because Dispatch #3 succeeded; offline verification is not a live failure observation.
- Cause of the missing pilot folder: UNKNOWN.
- Historical raw ledgers #1/#2: UNLOCATED, not proven destroyed. Retain their recorded hashes for verification if located; no substitute ledgers.
- Earlier unrelated account-activity/security question: SEPARATELY TRACKED in FI-001.
- Repository ignore-file issue: existing documented finding in PROJECT_STATE.md, not corrected here.

## 6. Disposition boundary

Stage 6D owner statement: "ACCEPT STAGE 6D". Documentary judgments given: 15 TRUE. Owner decisions (2026-11-27): "I explicitly accept the documentary field-level grade of ROWS 1–15: TRUE." "I accept Stage 6E." "I close Phase 6." Stage 6E ACCEPTED BY OWNER on 2026-11-27. Phase 6 CLOSED AND MERGED (PR #63, 2026-11-27). Foundation Exit RELEASED BY OWNER. NFL/agent implementation HOLD pending its own approved assignment. No further provider activity, dispatch, retry or rerun is authorized.
