"""Passive attempt admission and accounting for a fixed reasoning envelope."""
from datetime import datetime as _datetime, timedelta as _timedelta, timezone as _timezone
import hashlib as _hashlib

from .core import canonical_json as _canonical_json


ENVELOPE_ID = 'reasoning-envelope-v1'
MAX_ATTEMPTS_PER_OPERATION = 1
MAX_INPUT_BYTES = 262144
MAX_OUTPUT_BYTES = 65536
DEADLINE_SECONDS = 120
MAX_BUDGET_MICRODOLLARS = 500000
AUTOMATIC_RETRIES = 0
PAID_AUTHORITY_MICRODOLLARS = 0
STATUSES = ('completed', 'failed', 'uncertain')


def _limits():
    return {'max_attempts_per_operation': MAX_ATTEMPTS_PER_OPERATION,
            'max_input_bytes': MAX_INPUT_BYTES, 'max_output_bytes': MAX_OUTPUT_BYTES,
            'deadline_seconds': DEADLINE_SECONDS, 'max_budget_microdollars': MAX_BUDGET_MICRODOLLARS,
            'automatic_retries': AUTOMATIC_RETRIES}


ENVELOPE_SHA256 = _hashlib.sha256(_canonical_json(
    {'envelope_id': ENVELOPE_ID, 'limits': _limits()})).hexdigest()


class EnvelopeError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _clock_time(clock):
    try:
        stamp = _datetime.now(_timezone.utc) if clock is None else clock()
        if not isinstance(stamp, _datetime) or stamp.utcoffset() != _timedelta(0):
            raise ValueError('UTC clock required')
        return stamp
    except Exception:
        raise EnvelopeError('invalid_clock') from None


def _add(ledger, kind, data):
    try:
        return ledger.add(kind, data)
    except Exception:
        raise EnvelopeError('ledger_write_failed') from None


def _count(ledger, snapshot_id):
    return sum(record.kind == 'reasoning_attempt' and record.data['snapshot_id'] == snapshot_id
               for record in ledger.records.values())


def remaining_attempts(ledger, snapshot_id):
    if type(snapshot_id) is not str:
        raise EnvelopeError('invalid_call')
    return max(0, MAX_ATTEMPTS_PER_OPERATION - _count(ledger, snapshot_id))


def open_attempt(ledger, snapshot_id, input_bytes, required_budget_microdollars, *, clock=None):
    if (type(snapshot_id) is not str or type(input_bytes) is not int
            or type(required_budget_microdollars) is not int):
        raise EnvelopeError('invalid_call')
    stamp = _clock_time(clock)

    def refuse(reason):
        return _add(ledger, 'reasoning_attempt_refusal', {
            'snapshot_id': snapshot_id if 1 <= len(snapshot_id) <= 64 else None,
            'envelope_id': ENVELOPE_ID, 'envelope_sha256': ENVELOPE_SHA256, 'reason': reason})

    snapshot = ledger.records.get(snapshot_id)
    if (snapshot is None or snapshot.kind != 'snapshot'
            or not snapshot.data.get('capture_references')):
        return refuse('operation_unavailable')
    consumed = _count(ledger, snapshot_id)
    if consumed >= MAX_ATTEMPTS_PER_OPERATION:
        return refuse('attempt_already_consumed')
    if input_bytes < 1:
        return refuse('input_invalid')
    if input_bytes > MAX_INPUT_BYTES:
        return refuse('input_too_large')
    if required_budget_microdollars < 0:
        return refuse('budget_invalid')
    if required_budget_microdollars > MAX_BUDGET_MICRODOLLARS:
        return refuse('budget_too_large')
    return _add(ledger, 'reasoning_attempt', {
        'snapshot_id': snapshot.id, 'snapshot_hash': snapshot.content_hash,
        'attempt_number': consumed + 1, 'envelope_id': ENVELOPE_ID,
        'envelope_sha256': ENVELOPE_SHA256, 'limits': _limits(), 'input_bytes': input_bytes,
        'required_budget_microdollars': required_budget_microdollars,
        'paid_authority_microdollars': PAID_AUTHORITY_MICRODOLLARS,
        'opened_at': stamp.isoformat(),
        'deadline_at': (stamp + _timedelta(seconds=DEADLINE_SECONDS)).isoformat()})


def close_attempt(ledger, attempt_id, status, output_bytes, reported_cost_microdollars, *, clock=None):
    if (type(attempt_id) is not str or type(status) is not str
            or any(value is not None and type(value) is not int
                   for value in (output_bytes, reported_cost_microdollars))):
        raise EnvelopeError('invalid_call')
    stamp = _clock_time(clock)

    def refuse(reason):
        return _add(ledger, 'reasoning_close_refusal', {
            'attempt_id': attempt_id if 1 <= len(attempt_id) <= 64 else None, 'reason': reason})

    attempt = ledger.records.get(attempt_id)
    if attempt is None or attempt.kind != 'reasoning_attempt':
        return refuse('attempt_unavailable')
    if any(record.kind == 'reasoning_attempt_close' and record.data['attempt_id'] == attempt.id
           for record in ledger.records.values()):
        return refuse('attempt_already_closed')
    if status not in STATUSES:
        return refuse('status_invalid')
    if ((status == 'completed' and
         any(value is None or value < 0 for value in (output_bytes, reported_cost_microdollars)))
            or (status in ('failed', 'uncertain')
                and (output_bytes is not None or reported_cost_microdollars is not None))):
        return refuse('report_invalid')
    data = attempt.data
    limits = data['limits']
    violations = []
    if status == 'completed' and reported_cost_microdollars > limits['max_budget_microdollars']:
        violations.append('budget_exceeded')
    if stamp > _datetime.fromisoformat(data['deadline_at']):
        violations.append('deadline_exceeded')
    if status == 'completed' and output_bytes > limits['max_output_bytes']:
        violations.append('output_too_large')
    outcome = ('completed_with_violation' if violations else 'completed_within_limits') \
        if status == 'completed' else status
    return _add(ledger, 'reasoning_attempt_close', {
        'attempt_id': attempt.id, 'attempt_hash': attempt.content_hash,
        'snapshot_id': data['snapshot_id'], 'envelope_id': data['envelope_id'],
        'envelope_sha256': data['envelope_sha256'], 'status': status,
        'output_bytes': output_bytes, 'reported_cost_microdollars': reported_cost_microdollars,
        'closed_at': stamp.isoformat(), 'violations': violations, 'outcome': outcome})
