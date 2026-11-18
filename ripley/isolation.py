"""Parent-side observation of one trusted Worker process. Only Ripley writes records."""
from dataclasses import dataclass
from datetime import datetime, timezone
import subprocess
import sys
import os
import re

from .core import (DIAGNOSTICS_CAP_BYTES, KILL_WAIT_SECONDS, TERMINATION_GRACE_SECONDS,
                   canonical_json, decode_protocol_object)


@dataclass
class ProcessObservation:
    result: dict | None = None
    failure: dict | None = None
    late_response: dict | None = None


def redact_patterns(text):
    patterns = (r'sk-ant-[A-Za-z0-9_\-]{8,}', r'sk-[A-Za-z0-9_\-]{8,}',
                r'Bearer\s+\S+', r'(?i)(key|token|authorization)\W{0,3}[A-Za-z0-9+/=_\-]{40,}')
    for pattern in patterns:
        text = re.sub(pattern, '[REDACTED]', text)
    if os.environ.get('RIPLEY_ENABLE_TEST_WORKERS') == '1':
        marker = os.environ.get('RIPLEY_TEST_SECRET_MARKER')
        if marker:
            text = text.replace(marker, '[REDACTED]')
    return text


def _provider_dispatch(dispatch, packet):
    from .workers import spec_for

    fields = {'observation', 'provider', 'model', 'sdk', 'provider_request_id',
              'sent_at', 'usage', 'prompt_ref'}
    if not isinstance(dispatch, dict) or set(dispatch) != fields:
        return False
    spec = spec_for(packet['worker_identity'])
    if (dispatch['observation'] not in ('not_sent', 'sent', 'possibly_sent') or
            dispatch['provider'] != spec.provider or dispatch['model'] != spec.model):
        return False
    sdk, prompt = dispatch['sdk'], dispatch['prompt_ref']
    if (not isinstance(sdk, dict) or set(sdk) != {'package', 'version'} or
            sdk != {'package': 'anthropic', 'version': '2.9.0'} or
            not isinstance(prompt, dict) or set(prompt) != {'name', 'version', 'content_hash'} or
            not all(isinstance(x, str) and x for x in prompt.values())):
        return False
    if dispatch['provider_request_id'] is not None and not isinstance(dispatch['provider_request_id'], str):
        return False
    if dispatch['sent_at'] is not None:
        if not isinstance(dispatch['sent_at'], str):
            return False
        try:
            if datetime.fromisoformat(dispatch['sent_at']).utcoffset() != timezone.utc.utcoffset(None):
                return False
        except ValueError:
            return False
    usage = dispatch['usage']
    if usage is not None:
        if (not isinstance(usage, dict) or
                set(usage) != {'input_tokens', 'output_tokens', 'cache_read_tokens'}):
            return False
        return all((key == 'cache_read_tokens' and value is None) or
                   (type(value) is int and value >= 0) for key, value in usage.items())
    return True


def _response(raw, packet, expected_envelope_version='1'):
    response = decode_protocol_object(raw)
    provider = expected_envelope_version == '1.1'
    if response.get('envelope_version') != expected_envelope_version:
        raise ValueError('unsupported envelope version for worker class')
    identity_fields = ('envelope_version', 'attempt_id', 'worker_identity')
    fields = set(identity_fields) | {'status'}
    if provider:
        fields.add('dispatch')
        if not _provider_dispatch(response.get('dispatch'), packet):
            raise ValueError('unsupported envelope version for worker class')
    status = response.get('status')
    if status == 'ok':
        fields.add('output')
    elif status == 'error':
        fields.add('error')
        error = response.get('error')
        error_fields = {'type', 'message', 'detail'} if provider else {'type', 'message'}
        if (not isinstance(error, dict) or set(error) != error_fields
                or not all(isinstance(value, str) for value in error.values())):
            raise ValueError('invalid worker error')
        if provider:
            from .workers import PROVIDER_ERROR_TYPES

            if error['type'] not in PROVIDER_ERROR_TYPES:
                raise ValueError('invalid provider error')
        for key in error_fields - {'type'}:
            error[key] = redact_patterns(error[key])
    else:
        raise ValueError('invalid response status')
    if set(response) != fields:
        raise ValueError('invalid response fields')
    if any(response[key] != packet[key] for key in ('attempt_id', 'worker_identity')):
        raise ValueError('uncorrelated or unsupported response')
    return response


def _excerpt(raw):
    return redact_patterns(raw[-DIAGNOSTICS_CAP_BYTES:].decode('utf-8', errors='replace'))


def _diagnostics(stderr):
    return {'bytes_total': len(stderr), 'truncated': len(stderr) > DIAGNOSTICS_CAP_BYTES,
            'text': _excerpt(stderr)}


def _on_timeout(proc, packet, declared_at, expected_envelope_version='1'):
    proc.terminate()
    requested_at = datetime.now(timezone.utc).isoformat()
    method = 'terminate'
    exited = True
    late_response = None
    try:
        stdout, stderr = proc.communicate(timeout=TERMINATION_GRACE_SECONDS)
        completed_at = datetime.now(timezone.utc).isoformat()
        try:
            response = _response(stdout, packet, expected_envelope_version)
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


def observe_subprocess(packet, deadline, timeout, wait_strategy, expected_envelope_version='1'):
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
        return _on_timeout(proc, packet, datetime.now(timezone.utc).isoformat(), expected_envelope_version)

    completed_at = datetime.now(timezone.utc)
    exit_facts = {'completed_at': completed_at.isoformat(), 'pid': proc.pid,
                  'returncode': proc.returncode}
    try:
        response = _response(stdout, packet, expected_envelope_version)
    except (ValueError, RecursionError) as exc:
        return ProcessObservation(failure={'stage': 'host_failure', **exit_facts, 'message': str(exc),
            'stdout_excerpt': _excerpt(stdout), 'diagnostics': _diagnostics(stderr)})
    if response['status'] == 'error':
        return ProcessObservation(failure={'stage': 'worker_failure', **exit_facts,
            'error': response['error'], 'diagnostics': _diagnostics(stderr),
            **({'dispatch': response['dispatch']} if expected_envelope_version == '1.1' else {})})
    if proc.returncode != 0:
        return ProcessObservation(failure={'stage': 'host_failure', **exit_facts,
            'message': 'nonzero host exit with ok response', 'diagnostics': _diagnostics(stderr)})

    result = {'output': response['output'], **exit_facts}
    if expected_envelope_version == '1.1':
        result['dispatch'] = response['dispatch']
    if deadline is not None and completed_at > deadline:
        return ProcessObservation(result=result, failure={'stage': 'timeout', **exit_facts,
            'deadline_at': packet['deadline_at'], 'termination': None, 'diagnostics': _diagnostics(stderr)})
    return ProcessObservation(result=result)
