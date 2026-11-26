# Advisory pull-request CI

The tests workflow runs one advisory Linux job for pull requests targeting main. It runs on opening, reopening and proposal updates, including Draft PRs.

## What the check does

1. Records the event, PR number, proposal head, base, actual tested commit, checkout HEAD and Python version.
2. Installs dependencies from requirements-providers.txt and records their versions.
3. Verifies that the installed Anthropic SDK matches the requirement pin.
4. Refuses to run if any of RIPLEY_ANTHROPIC_API_KEY, ANTHROPIC_API_KEY, RIPLEY_LIVE_DISPATCH or RIPLEY_PILOT_DISPATCH_BUDGET has a non-empty value.
5. Archives the checked-out commit into a disposable directory outside the checkout.
6. Self-checks the runner's pass/fail rule, including unexpected successes, and its exact loopback and connection rules.
7. Runs the complete test suite in the disposable copy.
8. Checks that the authoritative checkout has no changes, including after an earlier step fails.

Setup uses network access for GitHub checkout, Python setup and dependency installation.

## Pass and fail

Any failure, error, skip, unexpected success or zero-test run makes the check red. Installation and other workflow-step failures also fail the job.

At the Sprint 8 baseline, the expected Linux result is 202 run, 202 passed and zero skipped. The total is not permanently fixed at 202. Reviewed future tests may increase it.

## Which commit was tested

GitHub's pull_request workflow checks the proposal merged into the current base. The logs identify the PR, proposal head, base and actual tested merge commit. These identities make the result attributable when the proposal or main changes.

## Network and secrets

The runner wraps socket connect and connect_ex in the main test process. For network address tuples it accepts the exact name localhost or a numeric address parsed as loopback. Byte-string and bytearray hosts are decoded as ASCII before that check; invalid text and other host types are refused. This guard is limited to those main-process calls. It does not globally sandbox arbitrary child processes started by tests. Existing Ripley mock transports and socket protections remain part of the suite.

The workflow supplies no application or provider secret. No application or provider secret should be added to the repository for this workflow.

A green check does not authorize dispatch, merge or deployment. It does not establish Windows success or a global network sandbox.

## Disposable copy and P6-11

P6-11 briefly rewrites the prompt file and then restores it. Sprint 8 leaves that test intact. The suite runs in the disposable copy, and the workflow confirms that the authoritative checkout remains unchanged.

## Review and Windows

The check is advisory. Sprint 8 configures no branch protection or required checks. Robert retains merge authority and Claude independently reviews the published implementation and evidence.

Owner/manual Windows testing remains available whenever a Sprint calls for it. Sprint 8 creates no Windows CI.

## Local commands

From a clean disposable repository copy with the pinned SDK installed:

```text
python -B .github/scripts/ci_tests.py --self-check
python -B .github/scripts/ci_tests.py
```

The ordinary command remains available:

```text
python -m unittest discover -s tests
```

Run reference suites with inherited proxy variables unset: ALL_PROXY, all_proxy, HTTPS_PROXY, https_proxy, HTTP_PROXY and http_proxy. The existing provider test P6-14 depends on this. With a SOCKS proxy variable set, the SDK fails while building its client before the socket guard is reached, and P6-14 reports blocked_worker_failure where blocked_host_failure is expected. This is an environment effect and not a defect. The hosted check runs with no proxy configured.

## Sprint 8 acceptance evidence

| Evidence type | Recorded evidence |
|---|---|
| Publication | Implementation PR #36. Commit 1: `9ac3df626206e8c00723084031d190977409a83c`. Commit 2 / reviewed head: `1b14d7dec15de83bbbcad494ae15256fdb0024e8`. Merged to main as `ddb23be065b8a3a91bf6bd14ad4ca5e5d6ab396b`. The merged tree is identical to the reviewed head. |
| File identity — workflow | Published tests.yml matched Claude's preflight SHA-256: `f3bf08c975bc6dfe147133857d7081407ad67a27c54b25fa05f60f99fbb3ca8b`. |
| File identity — runner | Published ci_tests.py matched Claude's preflight SHA-256: `eccadfcb378fcb89235b8eaf18d605193983eef5189295bee74b3e0e921e43cc`. |
| Independent review | Claude verdict: APPROVED WITH NONBLOCKING NOTES FOR OWNER MERGE. |
| Independent reproduction | Claude executed the published runner on tested commit `446625cc9ef70a662580965b259a5ec8beb1a26f`, using Python 3.13 and anthropic 2.9.0. Self-check passed. 202 tests run, 202 passed, 0 failures, 0 errors, 0 skipped. CI RESULT: PASSED. |
| Independent pass/fail verification | Claude separately confirmed the runner rejects zero tests, a failure, an error, a skip and an unexpected success. |
| Tested commit identities | Claude independently confirmed Run 1 tested `959d10313b42d265ebf825d507e3a33a1d5b010d`, whose parents are main and Commit 1. Run 2 tested `446625cc9ef70a662580965b259a5ec8beb1a26f`, whose parents are main and Commit 2. Commit 2 therefore produced a distinct later evaluation. |
| Hosted Run 1 — independently observed public page | [Run 44822013747](https://github.com/Ibmcleaner/Ripley-1/actions/runs/44822013747). Claude read the public run page. It showed Success, pull request #36, event pull_request, one job and no artifacts. |
| Hosted Run 1 — reported detailed logs | Detailed log lines were reported by ChatGPT. Claude did not independently observe those log lines because they require sign-in. |
| Hosted Run 2 — reported result | [Run 44822358618](https://github.com/Ibmcleaner/Ripley-1/actions/runs/44822358618). Reported green by ChatGPT. Claude could not load the run page and did not independently observe it. |
| Windows | No owner Windows suite was run for Sprint 8. Nothing that runs on Robert's machine changed. |

## Known limitations

Remaining limitation:

**Network-guard scope.** The runner's connection guard covers the main test process only. It is not a network sandbox for child processes started by tests. This limit is part of the documented CI semantics.

Corrected in Sprint 9 (PR #38), recorded for history:

- Loopback rule. The guard previously treated any host beginning with "localhost" or "127." as loopback. This was an error in the runner as designed by Claude. It now accepts only the exact name localhost or a numeric loopback IP address.
- Self-check coverage. The self-check previously did not exercise an unexpected success. It now does.
- Credential check wording. The success log previously said no variable "is set". It now says no variable "has a value". The check itself is unchanged: it refuses the listed variables when they hold a non-empty value.

## Sprint 8 retrospective

**What worked**

- Independent planning converged on CI as the next infrastructure need.
- The exact workflow and runner text was preflighted before release.
- Publication under .github/workflows/ succeeded through the connector.
- Two commits produced two distinct CI evaluations.
- The suite ran with the pinned SDK and zero skips.
- The disposable copy kept the checkout unchanged.
- The check stayed advisory and low privilege.

**What caused rework or friction**

- Whether the connector could publish workflow files was unknown until tried.
- As reported by the owner and implementer, the exact implementation payload had to be supplied directly in the implementation chat; authorization referring to an unavailable attachment was insufficient.
- Network-isolation scope required clarification so Sprint 8 did not expand into privileged/container infrastructure.
- A loopback-prefix weakness in the runner was found during independent review after release.

**What should remain**

- one measurable Sprint outcome
- exact file scope
- owner GO before repository change
- independent review
- attributable published SHAs
- truthful separation between hosted evidence and independent reproduction
- advisory CI until stronger governance is separately decided

**One improvement to carry forward**

Implementation-release messages include, or directly contain, every exact payload the implementer needs in a form actually available in the implementation chat.

## Sprint 9 runner corrections

- Changed in PR #38: .github/scripts/ci_tests.py for the loopback rule and unexpected-success self-check, plus one success-log line in .github/workflows/tests.yml.
- No trigger, permission, runner, Python version or action reference changed.

Authoritative published runner SHA-256:

`95b5dfd04e30938e94b6835b52aecfdd55a658c4018a4c74972f8cf207675643`

Published workflow SHA-256:

`68b451b8994aaf2e67cf261d95aca71d880a79ea4c6dcda41284cc5d4369c239`

The workflow hash matched its assigned reference.

Hash reconciliation:

The originally assigned runner reference was:

`7f26e2ddb71d13fb9e90906f569fc6e601defa67d9548e7ead828eca23e4e4b7`

The published runner differed from that assigned text in layout only:

- reflowed tables
- wrapped calls
- added blank lines
- one trailing comma

Claude confirmed the assigned and published versions parse to identical syntax trees and independently reviewed the published bytes.

Classification:

TRANSMISSION DIFFERENCE, NONBLOCKING

The advisory check remains advisory.

Full Sprint 9 evidence and retrospective are recorded in docs/capture.md.

## Windows expected-skip gate

This section records the opt-in expected-skip argument added to the advisory runner. It is development tooling, not Ripley One runtime capability.

### Default invocation is unchanged

Run with no arguments, the runner behaves exactly as before: any skip fails the run. Hosted Linux CI uses this default invocation, in self-check mode and in default mode only. The workflow file `.github/workflows/tests.yml` did not change in this pull request. Default-mode standard output is unchanged line for line, including the `CI SUMMARY`, `SKIPPED` and `CI RESULT` lines.

### The optional argument

The runner accepts exactly three forms: no arguments (default mode), `--self-check` alone, or one or more pairs `--expected-skip TEST_ID` (configured mode). The flag and its value are two separate arguments; the joined form `--expected-skip=TEST_ID` is refused. The pair is repeated once per expected skip, and the order of pairs has no meaning. The command line is the only source of the expected set. No environment variable, file or platform detection supplies or alters it, and the runner contains no list of approved tests.

A value must be an ordinary test identity: three or more parts joined by single full stops, each part starting with an ASCII letter or underscore and continuing with ASCII letters, digits or underscores. Class-setup and sub-test identities are refused.

### Owner-approved Windows identities

These four identities are approved by the owner for the Windows gate:

```text
test_isolation.MemoryIsolationTests.test_p5_04_parent_kills_unresponsive_child
test_isolation.MemoryIsolationTests.test_p5_08_grace_response_and_post_kill_drain
test_isolation.SQLiteIsolationTests.test_p5_04_parent_kills_unresponsive_child
test_isolation.SQLiteIsolationTests.test_p5_08_grace_response_and_post_kill_drain
```

They were approved before a Windows run was observed, subject to confirmation by the real Windows gate. The set changes only by owner decision, never from what a run skipped.

### Exact-match semantics

The identity of a skipped test is the exact string returned by the `id()` method of the test object that unittest recorded as skipped. Comparison is exact, case-sensitive and order-independent. There is no count, prefix, suffix, wildcard, pattern or reason matching, and no trimming or case-folding. The run is acceptable only when no expected identity is missing, no skipped identity is unexpected, and no identity is skipped more than once. A renamed test or a newly skipped test therefore fails the gate until the owner re-approves the set.

Failures, errors, unexpected successes and a zero-test run still make a configured run unacceptable even when the skips match.

### Skip reasons are diagnostic only

Each skip's reason text is printed for diagnosis. It is never compared, and an equal reason never grants a match.

### Output contract

In configured mode the lines appear in this order:

1. `CI SUMMARY: run=N failures=N errors=N skipped=N`, in the same format as default mode.
2. One `SKIPPED: TEST: REASON` line per recorded skip, printed whether or not the skips match. Every skip stays visible.
3. One `EXPECTED SKIP: TEST_ID` line per expected identity, sorted ascending, always printed.
4. One `MISSING EXPECTED SKIP: TEST_ID` line per expected identity that did not skip.
5. One `UNEXPECTED SKIP: TEST_ID` line per skipped identity that was not expected.
6. One `DUPLICATE SKIP: TEST_ID` line per identity that skipped more than once.
7. The result line.

Acceptable result line, where N is the number of expected identities (with the four approved identities this is exactly `CI RESULT: PASSED (4 expected skips)`):

```text
CI RESULT: PASSED (N expected skips)
```

Unacceptable result line, with reasons joined by a semicolon and a space, for example:

```text
CI RESULT: FAILED (skips differ from expected: 1 missing, 0 unexpected, 0 duplicated)
```

The reasons appear in this order: zero tests ran; failures; errors; the skip-difference reason; unexpected successes. The skip-difference reason always prints all three numbers.

### Refusals

A refused invocation prints exactly two lines and exits with status 2. No test is discovered or run, and no `CI SUMMARY`, `SKIPPED` or `CI RESULT` line is printed.

```text
ARGUMENT REFUSED: REASON
usage: ci_tests.py [--self-check | --expected-skip TEST_ID ...]
```

REASON is one of five fixed strings:

- `--self-check cannot be combined with other arguments`
- `unsupported argument`
- `missing value for --expected-skip`
- `malformed expected skip`
- `duplicate expected skip`

Refused values are not echoed, because an echoed value could contain a line break and forge a result line in captured evidence.

### Windows three-run gate

Performed by the owner on the exact final pull-request head, with the pinned SDK installed, in Command Prompt from the repository root. Output files are written outside the checkout. The last command is one line.

```text
set PYTHONUTF8=1

python -B -m unittest discover -s tests -v 1> "%TEMP%\ripley-gate-run1.txt" 2>&1
echo RUN1 EXIT %ERRORLEVEL%

python -B .github\scripts\ci_tests.py --self-check
echo SELFCHECK EXIT %ERRORLEVEL%

python -B .github\scripts\ci_tests.py 1> "%TEMP%\ripley-gate-run2.txt" 2>&1
echo RUN2 EXIT %ERRORLEVEL%

python -B .github\scripts\ci_tests.py --expected-skip test_isolation.MemoryIsolationTests.test_p5_04_parent_kills_unresponsive_child --expected-skip test_isolation.MemoryIsolationTests.test_p5_08_grace_response_and_post_kill_drain --expected-skip test_isolation.SQLiteIsolationTests.test_p5_04_parent_kills_unresponsive_child --expected-skip test_isolation.SQLiteIsolationTests.test_p5_08_grace_response_and_post_kill_drain 1> "%TEMP%\ripley-gate-run3.txt" 2>&1
echo RUN3 EXIT %ERRORLEVEL%
```

Expected: Run 1 exits 0 with OK and skipped=4; the self-check exits 0 with `SELF-CHECK PASSED`; Run 2 exits 1 with `CI RESULT: FAILED (4 skipped)`; Run 3 exits 0 with `CI RESULT: PASSED (4 expected skips)` and no MISSING, UNEXPECTED or DUPLICATE line. If Run 3 fails because the observed identities differ, the command is not changed to match what was observed; the observed identities go to the owner.

### Authority

The Windows gate remains owner evidence, not merge authority. The check remains advisory and authorizes no dispatch, merge or deployment.

### Commit-1 runner identity

The commit-1 runner is `.github/scripts/ci_tests.py` as physically published in commit 1, `021ec50b83a04d79131b7f0ee1df43cae7f9a9df`, and retrieved from GitHub at that exact commit:

- Byte count: 15,581
- SHA-256: `23f1457f8ff4d8413817f7d147008e3ee8bc465a905005e41408dd0c05465436`

This is the commit-1 runner hash. It is not asserted as the runner hash of any later head. The Sprint 9 runner SHA-256 recorded earlier in this file (`95b5dfd04e30938e94b6835b52aecfdd55a658c4018a4c74972f8cf207675643`) is historical.

### Evidence for this change

| Evidence | Source | Recorded evidence |
|---|---|---|
| Baseline | Implementer-reported | main at `41ba4cba5bcd46d5c062ea0aa7ae36d2b9541250`; committed runner, workflow and this file matched the assigned byte counts and SHA-256 values. |
| Published commit-1 runner | Implementer-reported | Retrieved from GitHub at commit 1; byte-identical to the intended runner; 15,581 bytes; SHA-256 above. |
| Local gates | Implementer-reported | Run on Windows 11 by local Claude Code in a disposable copy, Python 3.13.9, anthropic 2.9.0, proxy variables unset. No Linux environment was available locally. Self-check: exit 0, `SELF-CHECK PASSED`; its first 25 lines byte-identical to the base runner's. Default mode: 462 run, 0 failures, 0 errors, 4 skipped, exit 1, `CI RESULT: FAILED (4 skipped)`; standard output identical to the base runner's on the same tree. Configured mode with the four approved identities: exit 0, four `EXPECTED SKIP` lines, no MISSING, UNEXPECTED or DUPLICATE line, `CI RESULT: PASSED (4 expected skips)`. `--verbose`: exit 2 with exactly the two refusal lines. |
| Hosted, commit 1 | Hosted | [Run 45549077171](https://github.com/Ibmcleaner/Ripley-1/actions/runs/45549077171), as reported by the implementer from the run log: success; proposal head `021ec50b83a04d79131b7f0ee1df43cae7f9a9df`; tested merge commit `cdc58754d3758fa8ce772c17690f0929c78b536d`; anthropic 2.9.0; `SELF-CHECK PASSED`; `CI SUMMARY: run=462 failures=0 errors=0 skipped=0`; `CI RESULT: PASSED`; checkout unchanged. |
| Hosted, final head | Hosted | [Run 45549402553](https://github.com/Ibmcleaner/Ripley-1/actions/runs/45549402553), as reported by ChatGPT from the run log: success; proposal head `e3bf6f25150aa274b4f616800b254c5427e7221e`; tested merge commit `562eae81faf50db0099c9a1c94f6afae93aa6448`; base `41ba4cba5bcd46d5c062ea0aa7ae36d2b9541250`; anthropic 2.9.0; `SELF-CHECK PASSED`; `CI SUMMARY: run=462 failures=0 errors=0 skipped=0`; `CI RESULT: PASSED`; checkout unchanged. Claude did not observe the run log. Claude independently confirmed from the repository that GitHub's test merge commit for the pull request was `562eae81faf50db0099c9a1c94f6afae93aa6448`. |
| Independent reproduction of L1 to L9 and mutation checks | Claude-reproduced | On head `e3bf6f25150aa274b4f616800b254c5427e7221e` in a disposable copy on Linux, Python 3.13, anthropic 2.9.0, proxy variables unset. L1 self-check: exit 0, `SELF-CHECK PASSED`. L2 default mode: exit 0, `CI SUMMARY: run=462 failures=0 errors=0 skipped=0`, `CI RESULT: PASSED`. L3: default-mode standard output identical to the base runner's on the same tree. L4 with the four approved identities on Linux: exit 1, four `EXPECTED SKIP` lines, four `MISSING EXPECTED SKIP` lines, `CI RESULT: FAILED (skips differ from expected: 4 missing, 0 unexpected, 0 duplicated)`. L5 plain unittest: 462 tests, OK, 0 skips. L6 refused argument: exit 2, exactly the two refusal lines. L7 whitespace check clean. L8 exactly two files changed. L9 workflow SHA-256 unchanged. 22 of 22 mutation checks detected. |
| Windows three-run gate | Owner Windows | Reported by the owner on head `e3bf6f25150aa274b4f616800b254c5427e7221e`; Claude did not observe the runs. Run 1, plain unittest: 462 tests, 4 skips, exit 0, OK (skipped=4). Self-check: `SELF-CHECK PASSED`, exit 0. Run 2, default mode: exit 1, `CI SUMMARY: run=462 failures=0 errors=0 skipped=4`, four `SKIPPED` lines, `CI RESULT: FAILED (4 skipped)`. Run 3, configured mode: exit 0, `CI SUMMARY: run=462 failures=0 errors=0 skipped=4`, four `SKIPPED` lines, four `EXPECTED SKIP` lines, no MISSING, UNEXPECTED or DUPLICATE line, `CI RESULT: PASSED (4 expected skips)`. The four identities were the pre-approved set and were not changed after observation. Claude later received the Run 3 output file (2,118 bytes; SHA-256 `8982870ffb84c3c4ef3d204fc734da09e940daaf2d4f954cd7acdd1fb414c46a`) and confirmed that it contains those lines. |
| Final-head runner identity | Claude-reproduced | The runner at head `e3bf6f25150aa274b4f616800b254c5427e7221e` and on main `9402b5ba8e09f1b90491ade293a64018d6fe33d0` is byte-identical to the commit-1 runner: 15,581 bytes, SHA-256 `23f1457f8ff4d8413817f7d147008e3ee8bc465a905005e41408dd0c05465436`. |
| /ship steward | Implementer-reported | ChatGPT reported that a supervised local /ship steward session ran on the pull request and created or pushed zero commits; head and commit count unchanged. Claude independently confirmed from the repository that the pull request held exactly two commits at the reviewed head. |
| Implementation executor | Owner handoff | Variance: the assignment named ChatGPT as implementer. The implementation was executed by local Claude Code under an owner-approved variance. The separate Claude review session did not see that session's work. Commit metadata does not by itself establish which process authored the code. |
| Independent verdict and merge | Claude-reproduced | Verdict on the exact head: APPROVED FOR OWNER MERGE, in the owner handoff before the merge. Merged by the owner as `9402b5ba8e09f1b90491ade293a64018d6fe33d0`; the merged tree is identical to the reviewed head. |
| Release Gate Evidence proof | Owner Windows; Claude-reviewed | The Run 3 output above was the evidence file for the Release Gate Evidence proof completed on 2026-11-25 with existing Ripley. See docs/PROJECT_STATE.md, section 6, "Release Gate Evidence proof". |
