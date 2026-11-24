"""Envelope v1 entry point for trusted first-party Workers."""
from datetime import datetime, timezone
import os
import sys
import threading
from contextlib import redirect_stderr
from io import StringIO

from ripley.core import (ENVELOPE_VERSION, TERMINATION_GRACE_SECONDS, WATCHDOG_MARGIN_SECONDS,
                         MockWorker, canonical_json, decode_protocol_object, freeze)
from ripley.synthetic import InventoryAdapter
from ripley.nfl_availability import NflAvailabilityAdapter
from ripley.workers import spec_for
from ripley.reader import LineReaderWorker, ReaderAdapter, evidence_is_valid


WORKERS = {'mock-worker': MockWorker, 'line-reader': LineReaderWorker}
ADAPTERS = {'synthetic-inventory': InventoryAdapter, 'nfl-availability': NflAvailabilityAdapter,
            'source-reading': ReaderAdapter}
if os.environ.get('RIPLEY_ENABLE_TEST_WORKERS') == '1':
    from ripley.synthetic import TestBehaviorWorker
    WORKERS['test-behavior-worker'] = TestBehaviorWorker
    from ripley.reader import TestReaderWorker
    WORKERS['test-reader-worker'] = TestReaderWorker

IDENTITY_FIELDS = ('envelope_version', 'attempt_id', 'task_id', 'task_type', 'domain_id',
                   'domain_version', 'worker_identity')


def _worker_class(identity):
    if identity == 'anthropic-worker':
        if os.environ.get('RIPLEY_PROVIDER_TRANSPORT') == 'mock':
            from ripley.providers import install_socket_guard

            install_socket_guard()
        from ripley.providers import AnthropicWorker

        WORKERS[identity] = AnthropicWorker
    return WORKERS.get(identity)


def _read_request(raw):
    packet = decode_protocol_object(raw)
    if set(packet) - {'evidence'} != set(IDENTITY_FIELDS) | {'inputs', 'deadline_at'}:
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
    worker_class = _worker_class(packet['worker_identity'])
    adapter_class = ADAPTERS.get(packet['domain_id'])
    if worker_class is None or adapter_class is None or adapter_class.version != packet['domain_version']:
        return 3
    if deadline is not None:
        threading.Thread(target=_watchdog, args=(deadline,), daemon=True).start()

    worker = worker_class()
    spec = spec_for(worker.identity)
    if (spec.kind == 'reader') != ('evidence' in packet):
        return 2
    if spec.kind == 'reader' and not evidence_is_valid(packet['evidence']):
        return 2
    task = freeze({'id': packet['task_id'], 'task_type': packet['task_type'],
                   'domain_id': packet['domain_id'], 'domain_version': packet['domain_version'],
                   **({'deadline_at': packet['deadline_at']} if spec.kind == 'provider' else {})})
    snapshot = freeze({'inputs': packet['inputs'], 'domain_version': packet['domain_version'],
                       **({'evidence': packet['evidence']} if spec.kind == 'reader' else {})})
    response = {key: packet[key] for key in ('envelope_version', 'attempt_id', 'worker_identity')}
    if spec.kind == 'provider':
        diagnostics = StringIO()
        try:
            with redirect_stderr(diagnostics):
                outcome = worker.produce(task, snapshot, adapter_class())
        except Exception:
            # An unexpected host failure has no valid provider response.
            return 3
        sys.stderr.write(worker.sanitize_response(diagnostics.getvalue()))
        from ripley.providers import GUARD_ATTEMPTS

        if GUARD_ATTEMPTS:
            return 3
        response.update(envelope_version=spec.response_envelope_version, dispatch=outcome.dispatch)
        if outcome.error is None:
            response.update(status='ok', output=outcome.output)
        else:
            response.update(status='error', error=outcome.error)
        sys.stdout.buffer.write(canonical_json(worker.sanitize_response(response)))
        return 0
    try:
        output = worker.produce(task, snapshot, adapter_class())
    except Exception as exc:
        response.update(status='error', error={'type': type(exc).__name__, 'message': str(exc)})
    else:
        response.update(status='ok', output=output)

    if worker.identity in ('test-behavior-worker', 'test-reader-worker'):
        worker.write_test_response(response, sys.stdout.buffer)
    else:
        sys.stdout.buffer.write(canonical_json(response))
    return 0


if __name__ == '__main__':
    sys.exit(main())
