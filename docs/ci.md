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
