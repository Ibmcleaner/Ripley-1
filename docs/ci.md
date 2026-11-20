# Advisory pull-request CI

The tests workflow runs one advisory Linux job for pull requests targeting main. It runs on opening, reopening and proposal updates, including Draft PRs.

## What the check does

1. Records the event, PR number, proposal head, base, actual tested commit, checkout HEAD and Python version.
2. Installs dependencies from requirements-providers.txt and records their versions.
3. Verifies that the installed Anthropic SDK matches the requirement pin.
4. Refuses to run if any of RIPLEY_ANTHROPIC_API_KEY, ANTHROPIC_API_KEY, RIPLEY_LIVE_DISPATCH or RIPLEY_PILOT_DISPATCH_BUDGET has a non-empty value.
5. Archives the checked-out commit into a disposable directory outside the checkout.
6. Self-checks the runner's pass/fail rule and connection guard.
7. Runs the complete test suite in the disposable copy.
8. Checks that the authoritative checkout has no changes, including after an earlier step fails.

Setup uses network access for GitHub checkout, Python setup and dependency installation.

## Pass and fail

Any failure, error, skip, unexpected success or zero-test run makes the check red. Installation and other workflow-step failures also fail the job.

At the Sprint 8 baseline, the expected Linux result is 202 run, 202 passed and zero skipped. The total is not permanently fixed at 202. Reviewed future tests may increase it.

## Which commit was tested

GitHub's pull_request workflow checks the proposal merged into the current base. The logs identify the PR, proposal head, base and actual tested merge commit. These identities make the result attributable when the proposal or main changes.

## Network and secrets

The runner wraps socket connect and connect_ex in the main test process. It refuses connections whose string host does not begin with one of its loopback prefixes. This guard is limited to those main-process calls. It does not globally sandbox arbitrary child processes started by tests. Existing Ripley mock transports and socket protections remain part of the suite.

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

**Loopback rule.** The connection guard treats any host name beginning with "localhost" or "127." as loopback. A name such as `localhost.example.com` is therefore not refused. Ordinary outside addresses, including a provider address, are refused. This was an error in the runner as designed by Claude. A future correction candidate is to accept only the exact name localhost and addresses that parse as loopback IPs.

**Self-check coverage.** The pass/fail rule rejects unexpected successes. The `--self-check` does not exercise that specific case. A future correction candidate is to add an unexpected-success self-check.

**Credential check wording.** The workflow refuses the listed variables when they contain a non-empty value. An empty-but-present variable passes. The current log line says no variable "is set." An empty value carries no provider/live authority. A future wording candidate is no variable "has a value."

**Network-guard scope.** The runner's connection guard covers the main test process only. It is not a complete network sandbox for arbitrary child processes. This limit remains part of the documented CI semantics.

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
