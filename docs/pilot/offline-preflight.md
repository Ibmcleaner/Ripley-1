# Offline dispatch identity preflight

Use this command in a trusted local checkout to compare the files, Git history and Python environment with independently reviewed expectations. Supply the expected hashes, interpreter, Python version and reviewed commit from the review record. Using values discovered from the checkout as its own expectations defeats the comparison.

From the repository root in PowerShell, set `$baseline` to the reviewed full commit, `$interpreter` to the intended absolute venv interpreter path and `$pythonVersion` to the expected major.minor string. The frozen Bears inputs use this command:

```powershell
& $interpreter scripts/pilot_preflight.py --baseline $baseline --packet fixtures/nfl-availability/TB-at-CHI-2026-11-08.json --expected-packet-sha256 1ce3f332e1e8ff7aa113bbb0cd2688583086c29a050be909d9607e1a3c2c0aa6 --expected-prompt-sha256 7d5094d53f2e1f4924b1daa727a7fb7563048743082306908825604d3da06904 --expected-schema-sha256 bbefc6a8fce78143a8c0ff5eb918db4a43373af7bbe578348fca96f3dd47f41a --expected-interpreter $interpreter --expected-python $pythonVersion
```

Supply `--expected-head` for an additional exact HEAD comparison. `--repo` defaults to the directory above `scripts/`. Relative packet paths use the calling directory. For a passing comparison the baseline must include the reviewed preflight script and tests because both are governed paths.

```text
"Offline preflight checks passed" does not mean:
- dispatch authorized;
- provider acceptance established;
- live compatibility verified;
- recovery verified;
- files cannot change after verification.
```

| # | Check | Evidence for MATCHED |
|---|---|---|
| 1 | Git HEAD | A full commit resolves and equals the optional expected HEAD when supplied. |
| 2 | Reviewed baseline | The named commit exists and equals HEAD or is its ancestor. |
| 3 | Tracked differences from baseline | The baseline matched and comparing its tree to HEAD finds no governed change. |
| 4 | Uncommitted changes | No governed tracked change in the index or working tree. |
| 5 | Untracked files | Git reports no untracked governed file after exclusions. |
| 6 | Packet SHA-256 | Hash of raw packet bytes matches. |
| 7 | Prompt-template SHA-256 | Hash of raw bytes of `ripley/prompts/nfl-availability/1.md` matches. |
| 8 | Canonical output-schema SHA-256 | An isolated child imports the adapter from the checkout. The UTF-8 JSON hash (sorted keys and compact separators) matches. |
| 9 | Interpreter path | Absolute, platform-normalized paths compare equal, preserving symlink identity. |
| 10 | Python version | Running major.minor equals the expectation. |
| 11 | Installed Anthropic distribution version | Distribution metadata supplies a version. |
| 12 | SDK version against the repository pin | The installed version equals the single exact pin in `requirements-providers.txt`. |

MATCHED means the evidence satisfied the stated comparison. MISMATCHED means a comparison completed and differed. UNAVAILABLE means evidence or a valid expectation was missing, or a prerequisite failed. Hashes and commits require full lowercase hexadecimal values. Exit 0 requires twelve matches. Exit 1 reports the number of mismatched or unavailable checks. CLI usage errors exit 2.

The governed paths are `ripley/`, `tests/`, `scripts/`, `fixtures/`, root-level `requirements*.txt` (including `requirements-providers.txt`), `.gitattributes`, `pyproject.toml`, `setup.py` and `setup.cfg`. Paths containing a `__pycache__` component and files ending in `.pyc` are excluded. Git-reported changes elsewhere, including `docs/`, `pilot/`, root venv directories, `README.md` and `demo.py`, are summarized by their total count and sorted unique top-level path components. Check 5 detects ignored files and directories in governed paths and fails on them, subject to the cache exclusions above.

Do not run the test suite and the preflight at the same time because an existing test briefly rewrites the prompt file.

Results describe the moment of the run only. The command prints to standard output. It is separate from `scripts/pilot_dispatch.py` and grants no authorization.
