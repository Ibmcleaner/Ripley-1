# Owner mock dry-run on Windows

**PR #17 tests and the documented mock dry-run cannot dispatch to the live provider.
The runner is live-capable. Its live path requires owner-controlled environment gates,
a packet-bound authorization file, a budget and typed interactive confirmation.
This PR does not authorize it.** A live procedure requires separate written owner
authorization and has not been written.

**Fixture pending.** Run the procedure below after the Bears packet, expected output,
and provenance have landed on this branch and Rob has checked the rows against the
report. The draft currently exercises the runner using the existing synthetic
Phase 6 test control. That execution supplies no Bears evidence.

## Prepare a mock session

In PowerShell, start at the repository root with no pre-existing Ripley variables.
Install the pinned SDK before the offline run. Use a new, dedicated mock ledger.
Keep the same file for a repeat invocation so duplicate and budget accounting remain visible.

```powershell
if (Test-Path 'Env:RIPLEY_*') { throw 'Use a clean PowerShell session for the mock dry-run.' }
python -m venv .venv6
.\.venv6\Scripts\Activate.ps1
python -m pip install -r requirements-providers.txt
$packets = @(Get-ChildItem -LiteralPath .\fixtures\nfl-availability -Filter '*.json' -File -ErrorAction Stop | Where-Object { $_.Name -notlike '*.expected.json' })
if ($packets.Count -ne 1) { throw 'One owner-verified packet is required.' }
$packet = $packets[0].FullName
$expected = [IO.Path]::ChangeExtension($packet, 'expected.json')
if (!(Test-Path -LiteralPath $expected -PathType Leaf)) { throw 'Missing expected output.' }
$ledger = Join-Path $PWD 'pilot-mock.sqlite'
if (Test-Path -LiteralPath $ledger) { throw 'Choose a new mock ledger path for the first run.' }
$env:RIPLEY_PROVIDER_TRANSPORT = 'mock'
$env:RIPLEY_ENABLE_TEST_WORKERS = '1'
$env:RIPLEY_MOCK_PROVIDER_OUTPUT_FILE = $expected
$env:RIPLEY_ANTHROPIC_API_KEY = 'sk-ant-test-synthetic-dryrun-0123456789'
$env:RIPLEY_PILOT_DISPATCH_BUDGET = '1'
```

The mock Worker defaults to the `200:valid` script in a clean session. The SDK
reads the expected output locally. The child installs its socket guard before
importing the SDK.

## Run once

```powershell
python scripts/pilot_dispatch.py --packet "$packet" --ledger "$ledger"
```

Compare the printed SHA-256 and counts with the verified provenance. On a fresh
ledger, expect exit 0, `transport_mode: mock`, `pending_owner_approval`,
`observation: sent`, `remote_outcome: completed`, and `'budget_slots_consumed': 1`.
The request ID and token counts come from the mock. A repeat of the same command
while approval is pending exits 1 with `duplicate_of_existing_task`. It records
the duplicate and leaves the attempt and slot counts at one. Runner precondition
refusals exit 2 before opening the ledger. Core records its own budget-exhaustion
fact when that separate gate refuses a new attempt.

## Inspect the ledger read-only

```powershell
@'
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

uri = Path(sys.argv[1]).resolve().as_uri() + "?mode=ro"
with closing(sqlite3.connect(uri, uri=True)) as db:
    for kind, count in db.execute("SELECT kind, COUNT(*) FROM records GROUP BY kind ORDER BY kind"):
        print(kind, count)
'@ | python - "$ledger"
```

The first run should include one task, execution attempt, execution request, result,
validation, review, evidence and pending approval. The query reads record kinds
and counts only. Close the mock PowerShell session when finished.
