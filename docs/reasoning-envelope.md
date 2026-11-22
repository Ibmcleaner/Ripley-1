# Bounded reasoning envelope (ADR-015)

The envelope is a passive, deterministic open/close gate. It runs nothing. It
does not contain a source reader or call a model, provider, network, tool,
subprocess or Worker. It is direct use, outside the Core Task and Worker flow.

## Identity and limits

Identifier: `reasoning-envelope-v1`.

SHA-256: `0ef7f6be571dc111d359202471d6c8ab9b12193adaf879b66664b3b26fd99224`.

| Limit | Fixed value |
|---|---:|
| Attempts per operation | 1 |
| Input size | 262,144 bytes |
| Output size | 65,536 bytes |
| Accounting deadline | 120 seconds |
| Synthetic budget | 500,000 micro-dollars |
| Automatic retries | 0 |

Actual paid authority is always **0 micro-dollars**. The synthetic ceiling is
not spending permission. No provider or model is selected or authorized.
Children, fan-out, delegation, tools and their budgets have no fields or authority.

An operation is an existing Snapshot with at least one Capture reference. The
envelope creates no Snapshot or replacement operation. Input/output sizes and
cost figures are integer reports from its trusted host; it does not measure
payloads or authenticate those reports. Input must be at least one byte.

The hash covers the identifier and six limits using Core's canonical JSON. Each
attempt pins that hash and a copy of the limits. A close uses the attempt's
pinned values, not newly changed module constants. Changing the envelope
requires a repository change under a new identifier.

## Calling open and close

The following numbers are synthetic host reports; the example performs no work:

```python
from datetime import datetime, timedelta, timezone
from ripley.reasoning_envelope import open_attempt, close_attempt, remaining_attempts

opened_at = datetime.now(timezone.utc)
attempt = open_attempt(
    ledger, snapshot_id, input_bytes=128, required_budget_microdollars=1000,
    clock=lambda: opened_at,
)
if attempt.kind == 'reasoning_attempt':
    closing = close_attempt(
        ledger, attempt.id, 'completed', output_bytes=64,
        reported_cost_microdollars=0,
        clock=lambda: opened_at + timedelta(seconds=30),
    )
    assert remaining_attempts(ledger, snapshot_id) == 0
```

Both calls accept an optional keyword-only clock. Without one they use current
UTC time. A supplied clock is called once and must return a datetime whose UTC
offset is exactly zero. The deadline is opening time plus 120 seconds; a close
exactly at the deadline is within the limit. This is detection/accounting, not
termination or cancellation.

## Admission and durable consumption

Open appends a `reasoning_attempt` before returning it. A failed write raises an
error and returns no attempt. A refusal consumes nothing. Remaining attempts
are derived from ledger records on every call.

Opening consumes the operation's one attempt permanently: completion, failure,
uncertainty, absence of a close, elapsed time and ledger reopen do not restore
it. There is no automatic refund, retry, fallback or replacement operation.

Open refusal reasons, in order:

| Reason | Check |
|---|---|
| `operation_unavailable` | Snapshot is missing, wrong kind or has no Capture references |
| `attempt_already_consumed` | Its one attempt is already recorded |
| `input_invalid` | Declared input is below one byte |
| `input_too_large` | Declared input exceeds 262,144 bytes |
| `budget_invalid` | Required synthetic budget is negative |
| `budget_too_large` | Required synthetic budget exceeds 500,000 micro-dollars |

## Closing and violations

Close once with `completed`, `failed` or `uncertain`. For `completed`, output
bytes and reported cost must be non-negative integers. For `failed` and
`uncertain`, both must be `None`.

Close refusal reasons, in order:

| Reason | Check |
|---|---|
| `attempt_unavailable` | Target is missing or is not an attempt |
| `attempt_already_closed` | A close already exists |
| `status_invalid` | Status is not one of the three allowed values |
| `report_invalid` | Output/cost figures do not fit the status |

Violations are recorded in this order: `budget_exceeded`, `deadline_exceeded`,
`output_too_large`. Cost and output checks apply to completed reports. Deadline
checks apply to every status.

| Report | Outcome |
|---|---|
| Completed, no violation | `completed_within_limits` |
| Completed, any violation | `completed_with_violation` |
| Failed | `failed`, retaining any deadline violation |
| Uncertain | `uncertain`, retaining any deadline violation |

Refusals write only their assigned identity and reason fields. Invalid argument
types raise `EnvelopeError('invalid_call')`; an invalid clock raises
`EnvelopeError('invalid_clock')`. Both write nothing. A ledger write exception
raises `EnvelopeError('ledger_write_failed')`.

## What is not proven

This does not prove process termination; provider, network or SDK cancellation;
the correctness of a provider bill; token-to-cost conversion accuracy; or the
truth of host-declared sizes and costs. Nothing uses the envelope yet, and it
grants no actual spending authority.

ADR-010 dispatch governance remains separate and unchanged. A later reader or
provider integration must reconcile the two through its own decision. The
normative contract is [ADR-015](decisions/source-interpretation-sprint-2-adrs.md).
