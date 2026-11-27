# Phase 6D — Dispatch #3 evidence record

Date: 2026-11-27 (Central Time). This is factual diagnostic evidence, not Stage 6D acceptance, Stage 6E acceptance or Phase 6 closure.

## Authorization and pre-execution evidence

| Item | Evidence |
|---|---|
| Authorization-containing main | `56112bf7a8700b4c6221c2a66e800a772cd0f442` (PR #60) |
| Signed authorization | [phase-6d-authorization-03.md](../decisions/phase-6d-authorization-03.md) |
| Execution-time authorization blob | `30fda119f738003e590f84e0a0b1aaaa901c364f` |
| Governing R1 plan SHA-256 | `3fbe809b36d415dafd517fe0b882e9dbe99abd388cc97d8793f8213c5817f4a1` |
| Authorized date and cutoff | 2026-11-27; 5:00 PM Central |
| Windows Section 7 | One fresh PowerShell window; blocks 01–04 PASS |
| HEAD / authorization blob | Both matched the identities above |
| Offline preflight | 12 of 12 MATCHED; OFFLINE PREFLIGHT: PASSED |
| Local-state checks | True, False, True, False |
| Owner credential and signature facts | Signature/date his; Option B true; credential unchanged since restoration |

The first signed authorization window on 2026-11-26 expired unused: no live gates, runner or DISPATCH. The same record was re-dated through the reviewed route. Robert typed DISPATCH exactly once on 2026-11-27.

## Diagnostic result

| Field | Recorded value |
|---|---|
| Ledger start | 2026-11-27T16:48:02Z |
| Runner outcome | `pending_owner_approval` |
| Task ID | `22f21174-3047-4d0a-a209-eaeed1bc68d2` |
| Attempt ID | `aac3f216-2810-4545-aa77-cf70aa181b57` |
| Result ID | `8cb121b4-466b-4005-a991-72cb71445bfe` |
| Failure record | NONE |
| Observation | `sent` |
| Remote outcome | `completed` |
| Provider error | none |
| Model / SDK | `claude-haiku-5-5` / `anthropic 2.9.0` |
| Usage | input 2222; output 521; cache read 0 |
| Provider request ID | `req_011ChTms6hUogRFwaY9twKzj` |
| dispatches_consumed | 1 |
| confirmed_sent | 1 |
| uncertain_dispatch | 0 |
| budget_slots_consumed | 1 |
| Authorization | CONSUMED 2026-11-27 |

No second confirmed invocation, retry, alternate ledger or model substitution is authorized.

## Section 12 read-only inspection and preservation

In a new window, the owner reported no Python process active, ledger present, and no journal, WAL or SHM sidecars. Read-only inspection confirmed sent/completed, model and SDK, the same request ID and usage, serialized output size 803 characters, validation passed = True with no failures, and pending_owner_approval. The actual answer was not examined for this publication. The inspection reported LEDGER UNCHANGED.

| Evidence | Value |
|---|---|
| Original ledger | `C:\Users\rober\Ripley-1\pilot\6d-dispatch-03.sqlite` |
| Preserved copy | `C:\RipleyProof\phase-6d-dispatch-03\6d-dispatch-03.sqlite` |
| SHA-256 (both) | `cd5e83e27d56f7f086b8299baea631348db8af3d298d980636ed4a2af6b5bbe7` |
| Preservation | Copied, not moved; original remains in place unchanged |

The hashes and stability checks are owner-side evidence relayed in the execution handoff, not independent access to either SQLite file by the documentation author. Preserve both files; no recovery, deletion or rerun.

## Post-call Console observation

Owner-reported transcribed observations, approximately 10:55 AM Central on 2026-11-27:

| Field | Observation |
|---|---|
| Spend this month | $0.00 of $500 limit |
| Credit balance | $20.00 |
| Auto-reload | ON, not triggered |
| Promotional credit | $216.36 |
| Pre-call promotional credit (9:57 AM Central) | $216.37 |
| Usage and cost charts | No data yet; Console indicated reporting may be delayed by a few hours |

The $0.01 promotional-credit change is not definitively attributable to dispatch #3 on the available provider evidence. No cost is inferred.

## R1 status vocabulary

| Status | Evidence disposition |
|---|---|
| 1. Execution concluded | Local YES; remote COMPLETED |
| 2. Useful diagnostic evidence obtained | YES |
| 3. Live provider path verified | YES — one call |
| 4. Output validated | YES against existing validator rules; NOT owner-graded |
| 5. Authorization consumed | YES |
| 6. Owner decision on pending task | NOT MADE |
| 7. Stage 6D dispositioned | NOT YET |
| 8. Stage 6E dispositioned | NOT YET |
| 9. Phase 6 closed | NO |

R1 Appendix A row 1 applies. The frozen repaired request was accepted once; a live model result returned and passed Ripley's existing validator. Model access was observed once for this credential/date. This is not general reliability or usability evidence, owner acceptance, owner grading or proof of the exact historical November 18 HTTP 400 cause. [FI-001](../failure-intelligence/FI-001-anthropic-messages-http-400.md) remains inferential as to that cause.

## Deviations and findings

1. November 26 signed window expired unused; re-dated by the reviewed route.
2. Raw ledgers for dispatches #1/#2 are UNLOCATED, not proven destroyed. Documentary records [#1](6d-dispatch-01.md) and [#2](6d-dispatch-02.md) remain.
3. Pilot folder was absent on November 26 and recreated empty with owner/Chair approval. Cause unknown; no historical ledger investigation authorized here.
4. R1 section 12 helper was delivered directly to Python rather than saved as a helper file: same code, different delivery, as reported.
5. Section 10 included one extra printed time line; no executable time gate added.
6. Block files were delivered code-only in the established owner workflow.
7. Optional fail-closed Section 7 wrapper was drafted but abandoned unrun.

## Evidence boundary and next gate

Source: owner execution and read-only inspection evidence relayed in the Copilot/owner closeout assignment of 2026-11-27. Repository identities checked by the documentation author; raw ledger, actual model output and Console not independently accessed by that author. The task remains pending_owner_approval per supplied evidence; this publication does not approve or reject it. Stage 6D and Stage 6E disposition, seven-count accounting and owner grading remain separate gates. Phase 6 is open. No further provider activity, dispatch or NFL/agent implementation is authorized.

## Subsequent governed owner decision and evidence preservation — 2026-11-27

The execution-time status above is historical. The owner subsequently approved the task through Ripley's governed approval route. Approved approval record: `9f06d661-bfce-4c49-a45e-fb40defb9466`. Owner reason: "The extraction matches the packet and the diagnostic purpose was met."

Stage 6D owner decision: "ACCEPT STAGE 6D".

| Evidence state | SHA-256 |
|---|---|
| Preserved pre-owner-decision ledger | `cd5e83e27d56f7f086b8299baea631348db8af3d298d980636ed4a2af6b5bbe7` |
| Post-owner-approval ledger | `af4a11ac3bad4ffc57cb27ec7fe1dee1aec03ebbbefc26146ac8892192b7bc17` |

The post-approval preserved copy has the same reported SHA-256 as the post-approval ledger. These are distinct evidence states; the pre-decision copy remains separate. The post-approval Result ID is `8cb121b4-466b-4005-a991-72cb71445bfe`, content hash `2a9e3c2d741a3dfbd218212ec5703a512e69f0e7ed659ae02e207edc2f90b49d`; Snapshot ID is `c43444ee-a671-4e03-a482-41c12fbc6828`, content hash `24480b47c801f69705db100ac059ab03ea402ade3362339c1e8d70d7b4d3450e`. These identities and the approval outcome are supplied owner/team read-only evidence, not direct SQLite inspection by the documentation author.

Claude relay text was accidentally pasted into PowerShell after preservation. PowerShell rejected it. Subsequent read-only verification established no evidence change. This was a relay/presentation issue, not a Ripley runtime failure. Relay messages are now labeled by destination.

The documentary owner field-level judgments are recorded separately in [the Stage 6E pilot report](6e-pilot-report.md); no native pilot_quality_grade record is claimed. Stage 6E ACCEPTED BY OWNER on 2026-11-27. Phase 6 CLOSED AND MERGED on 2026-11-27; final repository acceptance complete (PR #63 merged). Foundation Exit RELEASED BY OWNER. This release does not authorize Milestone 2A, NFL Worker or agent implementation, provider activity or changes to frozen historical provider artifacts. No further provider activity, dispatch, retry or rerun is authorized.
