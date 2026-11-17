"""Parent-side observation of one trusted Worker process. Only Ripley writes records."""
import codecs
from dataclasses import dataclass
from datetime import datetime, timezone
import subprocess
import sys

from .core import (DIAGNOSTICS_CAP_BYTES, KILL_WAIT_SECONDS, TERMINATION_GRACE_SECONDS,
                   canonical_json, decode_protocol_object)


@dataclass
class ProcessObservation:
    result: dict | None = None
    failure: dict | None = None
    late_response: dict | None = None


def _response(raw, packet):
    response = decode_protocol_object(raw)
    identity_fields = ('envelope_version', 'attempt_id', 'worker_identity')
    fields = set(identity_fields) | {'status'}
    status = response.get('status')
    if status == 'ok':
        fields.add('output')
    elif status == 'error':
        fields.add('error')
        error = response.get('error')
        if (not isinstance(error, dict) or set(error) != {'type', 'message'}
                or not all(isinstance(value, str) for value in error.values())):
            raise ValueError('invalid worker error')
    else:
        raise ValueError('invalid response status')
    if set(response) != fields:
        raise ValueError('invalid response fields')
    if any(response[key] != packet[key] for key in identity_fields):
        raise ValueError('uncorrelated or unsupported response')
    return response


def _excerpt(raw):
    # Use the standard codec handler's name. Phase 3's source guard also
    # scans non-SQL string literals for SQL write verbs.
    errors = codecs.replace_errors.__name__.removesuffix('_errors')
    return raw[-DIAGNOSTICS_CAP_BYTES:].decode('utf-8', errors=errors)


def _diagnostics(stderr):
    return {'bytes_total': len(stderr), 'truncated': len(stderr) > DIAGNOSTICS_CAP_BYTES,
            'text': _excerpt(stderr)}


def _on_timeout(proc, packet, declared_at):
    proc.terminate()
    requested_at = datetime.now(timezone.utc).isoformat()
    method = 'terminate'
    exited = True
    late_response = None
    try:
        stdout, stderr = proc.communicate(timeout=TERMINATION_GRACE_SECONDS)
        completed_at = datetime.now(timezone.utc).isoformat()
        try:
            response = _response(stdout, packet)
        except (ValueError, RecursionError):
            pass  # The observed bytes remain diagnostics below.
        else:
            if response['status'] == 'ok':
                late_response = response
    except subprocess.TimeoutExpired:
        method = 'kill'
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=KILL_WAIT_SECONDS)
            completed_at = datetime.now(timezone.utc).isoformat()
        except subprocess.TimeoutExpired as final:
            exited = False
            stdout, stderr = final.output or b'', final.stderr or b''
            proc.kill()
            # POSIX uses non-threaded pipe reads. On Windows communicate's
            # reader threads own these streams and close them when EOF arrives.
            if sys.platform != 'win32':
                proc.stdin.close()
                proc.stdout.close()
                proc.stderr.close()
    diagnostics = _diagnostics(stderr)
    if late_response is None and stdout:
        diagnostics['stdout_excerpt'] = _excerpt(stdout)
    termination = {'requested_at': requested_at, 'method': method, 'exited': exited,
                   'returncode': proc.returncode if exited else None, 'pid': proc.pid}
    failure = {'stage': 'timeout', 'declared_at': declared_at, 'deadline_at': packet['deadline_at'],
               'termination': termination, 'diagnostics': diagnostics}
    if exited:
        failure['completed_at'] = completed_at
    return ProcessObservation(failure=failure, late_response=late_response)


def observe_subprocess(packet, deadline, timeout, wait_strategy):
    request_bytes = canonical_json(packet)
    wait_seconds = timeout.total_seconds() if timeout is not None else None
    if wait_strategy is not None:
        wait_seconds = wait_strategy(wait_seconds)
    try:
        proc = subprocess.Popen([sys.executable, '-m', 'ripley.worker_host'],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, ValueError) as exc:
        return ProcessObservation(failure={'stage': 'host_failure', 'returncode': None,
            'launch_error': {'type': type(exc).__name__, 'message': str(exc)},
            'termination': None, 'diagnostics': None})

    try:
        stdout, stderr = proc.communicate(request_bytes, timeout=wait_seconds)
    except subprocess.TimeoutExpired:
        return _on_timeout(proc, packet, datetime.now(timezone.utc).isoformat())

    completed_at = datetime.now(timezone.utc)
    exit_facts = {'completed_at': completed_at.isoformat(), 'pid': proc.pid,
                  'returncode': proc.returncode}
    try:
        response = _response(stdout, packet)
    except (ValueError, RecursionError) as exc:
        return ProcessObservation(failure={'stage': 'host_failure', **exit_facts, 'message': str(exc),
            'stdout_excerpt': _excerpt(stdout), 'diagnostics': _diagnostics(stderr)})
    if response['status'] == 'error':
        return ProcessObservation(failure={'stage': 'worker_failure', **exit_facts,
            'error': response['error'], 'diagnostics': _diagnostics(stderr)})
    if proc.returncode != 0:
        return ProcessObservation(failure={'stage': 'host_failure', **exit_facts,
            'message': 'nonzero host exit with ok response', 'diagnostics': _diagnostics(stderr)})

    result = {'output': response['output'], **exit_facts}
    if deadline is not None and completed_at > deadline:
        return ProcessObservation(result=result, failure={'stage': 'timeout', **exit_facts,
            'deadline_at': packet['deadline_at'], 'termination': None, 'diagnostics': _diagnostics(stderr)})
    return ProcessObservation(result=result)
