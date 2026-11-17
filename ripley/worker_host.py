"""Envelope v1 entry point for trusted first-party Workers."""
from datetime import datetime, timezone
import os
import sys
import threading

from ripley.core import (ENVELOPE_VERSION, TERMINATION_GRACE_SECONDS, WATCHDOG_MARGIN_SECONDS,
                         MockWorker, canonical_json, decode_protocol_object, freeze)
from ripley.synthetic import InventoryAdapter


WORKERS = {'mock-worker': MockWorker}
ADAPTERS = {'synthetic-inventory': InventoryAdapter}
if os.environ.get('RIPLEY_ENABLE_TEST_WORKERS') == '1':
    from ripley.synthetic import TestBehaviorWorker
    WORKERS['test-behavior-worker'] = TestBehaviorWorker

IDENTITY_FIELDS = ('envelope_version', 'attempt_id', 'task_id', 'task_type', 'domain_id',
                   'domain_version', 'worker_identity')


def _read_request(raw):
    packet = decode_protocol_object(raw)
    if set(packet) != set(IDENTITY_FIELDS) | {'inputs', 'deadline_at'}:
        raise ValueError('invalid request fields')
    if packet['envelope_version'] != ENVELOPE_VERSION or any(
            not isinstance(packet[key], str) or not packet[key] for key in IDENTITY_FIELDS):
        raise ValueError('invalid request identity or version')
    deadline = packet['deadline_at']
    if deadline is not None:
        deadline = datetime.fromisoformat(deadline)
        if deadline.utcoffset() != timezone.utc.utcoffset(None):
            raise ValueError('expected UTC deadline')
    return packet, deadline


def _watchdog(deadline):
    # Use bounded waits even for deadlines outside the platform timer range.
    while True:
        seconds = (deadline - datetime.now(timezone.utc)).total_seconds()
        remaining = seconds + TERMINATION_GRACE_SECONDS + WATCHDOG_MARGIN_SECONDS
        if remaining <= 0:
            os._exit(124)
        threading.Event().wait(min(remaining, threading.TIMEOUT_MAX))


def main():
    try:
        packet, deadline = _read_request(sys.stdin.buffer.read())
    except (ValueError, TypeError, RecursionError):
        return 2
    worker_class = WORKERS.get(packet['worker_identity'])
    adapter_class = ADAPTERS.get(packet['domain_id'])
    if worker_class is None or adapter_class is None or adapter_class.version != packet['domain_version']:
        return 3
    if deadline is not None:
        threading.Thread(target=_watchdog, args=(deadline,), daemon=True).start()

    worker = worker_class()
    task = freeze({'id': packet['task_id'], 'task_type': packet['task_type'],
                   'domain_id': packet['domain_id'], 'domain_version': packet['domain_version']})
    snapshot = freeze({'inputs': packet['inputs'], 'domain_version': packet['domain_version']})
    response = {key: packet[key] for key in ('envelope_version', 'attempt_id', 'worker_identity')}
    try:
        output = worker.produce(task, snapshot, adapter_class())
    except Exception as exc:
        response.update(status='error', error={'type': type(exc).__name__, 'message': str(exc)})
    else:
        response.update(status='ok', output=output)

    if worker.identity == 'test-behavior-worker':
        worker.write_test_response(response, sys.stdout.buffer)
    else:
        sys.stdout.buffer.write(canonical_json(response))
    return 0


if __name__ == '__main__':
    sys.exit(main())
