"""One trusted provider Worker. SDK imports and credentials stay in its child."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import threading
import time

from .core import (MIN_SDK_TIMEOUT_SECONDS, PARENT_CONTROL_RESERVE_SECONDS,
                   canonical_json, decode_protocol_object)
from .isolation import redact_patterns


PROVIDER_MESSAGE_CAP_CHARS = 500
GUARD_ATTEMPTS = 0
MOCK_REQUESTS_SEEN = 0
_GUARD_INSTALLED = False


def install_socket_guard():
    global _GUARD_INSTALLED
    if _GUARD_INSTALLED:
        return

    def forbidden(*args, **kwargs):
        global GUARD_ATTEMPTS
        GUARD_ATTEMPTS += 1
        raise RuntimeError('network forbidden in mock transport mode')

    socket.socket.connect = forbidden
    socket.socket.connect_ex = forbidden
    socket.create_connection = forbidden
    _GUARD_INSTALLED = True


def sanitize(text, secret, canaries):
    if secret:
        text = text.replace(secret, '[REDACTED]')
    for canary in canaries:
        if len(canary) >= 8:
            text = text.replace(canary, '[REDACTED]')
    text = re.sub(r'(?im)^.*authorization\s*:.*$', '[REDACTED]', text)
    return redact_patterns(text)


@dataclass
class ProviderOutcome:
    dispatch: dict
    output: object = None
    error: dict | None = None


def classify(stage, exc):
    """Only call location and HTTP evidence can establish a dispatch."""
    if stage != 'after_call':
        return 'invalid_request', 'not_sent'
    status = getattr(exc, 'status_code', None)
    if status is not None or getattr(exc, 'request_id', None) is not None:
        if status in (401, 403):
            return 'auth_rejected', 'sent'
        if status in (400, 422):
            return 'invalid_request', 'sent'
        if status == 429:
            return 'rate_limited', 'sent'
        return 'provider_unavailable', 'sent'
    import anthropic

    if isinstance(exc, anthropic.APITimeoutError):
        return 'provider_timeout', 'possibly_sent'
    return 'provider_unavailable', 'possibly_sent'


def schema_violations(schema) -> list[str]:
    violations = []
    allowed = {'type', 'properties', 'required', 'additionalProperties', 'items', 'enum', 'anyOf'}

    def visit(node, path):
        if not isinstance(node, Mapping):
            violations.append(f'{path}: expected a schema object')
            return
        for key in sorted(node.keys() - allowed):
            violations.append(f'{path}: unsupported keyword {key}')
        properties = node.get('properties', {})
        if node.get('type') == 'object':
            if node.get('additionalProperties') is not False:
                violations.append(f'{path}: additionalProperties must be false')
            if not isinstance(properties, Mapping) or not properties:
                violations.append(f'{path}: properties must be a non-empty object')
            required = node.get('required')
            if (not isinstance(required, list) or not isinstance(properties, Mapping)
                    or not all(isinstance(k, str) for k in required)
                    or len(required) != len(properties) or set(required) != set(properties)):
                violations.append(f'{path}: required must list exactly the property names')
        if isinstance(properties, Mapping):
            for key, child in properties.items():
                visit(child, f'{path}.properties.{key}')
        if 'items' in node:
            visit(node['items'], path + '.items')
        if 'anyOf' in node:
            if len(node) != 1:
                violations.append(f'{path}: anyOf must have no siblings')
            if not isinstance(node['anyOf'], list) or not node['anyOf']:
                violations.append(f'{path}: anyOf must be a non-empty list')
            else:
                for index, child in enumerate(node['anyOf']):
                    visit(child, f'{path}.anyOf[{index}]')

    visit(schema, '$')
    return violations


def _mock_transport():
    import httpx2

    def handler(request):
        global MOCK_REQUESTS_SEEN
        MOCK_REQUESTS_SEEN += 1
        scripts = os.environ.get('RIPLEY_MOCK_PROVIDER_SCRIPT', '200:valid').split('+')
        if not any(s in ('200:valid', '200:malformed', '400:straddle', '500:leaky', 'reset_after_write',
                         'read_timeout') or s.isdigit() for s in scripts):
            scripts.append('200:valid')
        if 'hang_after_send' in scripts:
            threading.Event().wait()
        if 'reset_after_write' in scripts:
            raise httpx2.RemoteProtocolError('offline reset after request write')
        if 'read_timeout' in scripts:
            raise httpx2.ReadTimeout('offline read timeout', request=request)
        headers = {'request-id': 'req_offline_provider'}
        if any(script.startswith('200:') for script in scripts):
            body = json.loads(request.content)
            violations = schema_violations(body['output_config']['format']['schema'])
            if violations:
                return httpx2.Response(400, headers=headers, json={'type': 'error', 'error': {
                    'type': 'invalid_request_error',
                    'message': 'output_config.format.schema: ' + violations[0]}})
        if '200:malformed' in scripts:
            return httpx2.Response(200, headers=headers, content=b'not a provider response')
        if '200:valid' in scripts:
            output = json.loads(Path(os.environ['RIPLEY_MOCK_PROVIDER_OUTPUT_FILE']).read_text('utf-8'))
            return httpx2.Response(200, headers=headers, json={
                'id': 'msg_offline_provider', 'type': 'message', 'role': 'assistant',
                'model': 'claude-haiku-5-5', 'content': [{'type': 'text',
                'text': canonical_json(output).decode('utf-8')}],
                'stop_reason': 'end_turn', 'stop_sequence': None,
                'usage': {'input_tokens': 100, 'output_tokens': 60, 'cache_read_input_tokens': 0}})
        message = 'offline fixture'
        if '400:straddle' in scripts:
            status = 400
            message = 'x' * (PROVIDER_MESSAGE_CAP_CHARS - 10) + os.environ['RIPLEY_ANTHROPIC_API_KEY']
        elif '500:leaky' in scripts:
            secret = os.environ['RIPLEY_ANTHROPIC_API_KEY']
            message = '\n'.join([secret, *os.environ.get('RIPLEY_TEST_CANARIES', '').split('|'),
                                 'Authorization: Bearer ' + secret])
            headers['authorization'] = 'Bearer ' + secret
            status = 500
        else:
            status = int(next(s for s in scripts if s.isdigit()))
        error_type = {400: 'invalid_request_error', 401: 'authentication_error',
                      429: 'rate_limit_error', 500: 'api_error'}[status]
        return httpx2.Response(status, headers=headers, json={
            'type': 'error', 'error': {'type': error_type, 'message': message}})

    return httpx2.MockTransport(handler)


class ProviderWorker:
    """Produces a response fact. Parent alone validates and writes the ledger."""
    def sanitize_response(self, value):
        if isinstance(value, str):
            return sanitize(value, self._secret, self._canaries)
        if isinstance(value, dict):
            return {self.sanitize_response(key): self.sanitize_response(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.sanitize_response(item) for item in value]
        return value

    def produce(self, task, snapshot, adapter):
        mode = os.environ.get('RIPLEY_PROVIDER_TRANSPORT')
        mock = mode == 'mock' and os.environ.get('RIPLEY_ENABLE_TEST_WORKERS') == '1'
        scripts = os.environ.get('RIPLEY_MOCK_PROVIDER_SCRIPT', '200:valid').split('+') if mock else []
        for script in scripts:
            if script.startswith('startup_delay:'):
                time.sleep(float(script.partition(':')[2]))
        stage = 'before_client'
        self._secret = None
        self._canaries = []
        if os.environ.get('RIPLEY_ENABLE_TEST_WORKERS') == '1':
            self._canaries = os.environ.get('RIPLEY_TEST_CANARIES', '').split('|')
        path = Path(__file__).parent / 'prompts' / self.prompt_ref['name'] / (self.prompt_ref['version'] + '.md')
        template = path.read_bytes()
        prompt_ref = {**self.prompt_ref, 'content_hash': hashlib.sha256(template).hexdigest()}
        dispatch = {'observation': 'not_sent', 'provider': self.provider, 'model': self.model,
                    'sdk': {'package': 'anthropic', 'version': '2.9.0'},
                    'provider_request_id': None, 'sent_at': None, 'usage': None,
                    'prompt_ref': prompt_ref}

        def error(kind, message, detail=''):
            if mode == 'mock' or os.environ.get('RIPLEY_ENABLE_TEST_WORKERS') == '1':
                detail += (f' mock_requests_seen={MOCK_REQUESTS_SEEN}'
                           f' sdk_invoked={str(stage == "after_call").lower()}')
            return ProviderOutcome(dispatch, error={'type': kind, 'message': message, 'detail': detail})

        live = mode == 'live' and os.environ.get('RIPLEY_LIVE_DISPATCH') == '1'
        if not (mock or live):
            return error('live_gate_closed', 'provider transport gate closed')
        if mock:
            install_socket_guard()
        self._secret = os.environ.get(self.credentials_ref)
        if not self._secret:
            return error('auth_unavailable', 'provider credential unavailable')
        remaining = (datetime.fromisoformat(task['deadline_at']) - datetime.now(timezone.utc)).total_seconds()
        sdk_timeout = remaining - PARENT_CONTROL_RESERVE_SECONDS
        if sdk_timeout < MIN_SDK_TIMEOUT_SECONDS:
            return error('insufficient_time', 'insufficient provider time budget')

        import anthropic
        import httpx2

        stage = 'before_client'
        raw = None
        try:
            options = {'api_key': self._secret, 'max_retries': 0, 'timeout': sdk_timeout}
            if mock and 'bypass_transport' not in scripts:
                options['http_client'] = httpx2.Client(transport=_mock_transport())
            with anthropic.Anthropic(**options) as client:
                stage = 'before_call'
                schema = adapter.output_schema
                if schema_violations(schema):
                    raise ValueError('output_schema violates provider structured-output rules')
                content = template.decode('utf-8') + '\n---\n' + canonical_json(snapshot['inputs']).decode('utf-8')
                if 'leak_stderr' in scripts:
                    sys.stderr.write('\n'.join(['Traceback (synthetic fixture):', self._secret,
                        *self._canaries, 'Authorization: Bearer ' + self._secret]) + '\n')
                stage = 'after_call'
                dispatch['sent_at'] = datetime.now(timezone.utc).isoformat()
                raw = client.messages.with_raw_response.create(model=self.model,
                    max_tokens=self.max_output_tokens, messages=[{'role': 'user', 'content': content}],
                    output_config={'format': {'type': 'json_schema', 'schema': schema}})
                dispatch['observation'] = 'sent'
                dispatch['provider_request_id'] = raw.headers.get('request-id')
                message = raw.parse()
                usage = message.usage
                dispatch['usage'] = {'input_tokens': usage.input_tokens, 'output_tokens': usage.output_tokens,
                                    'cache_read_tokens': getattr(usage, 'cache_read_input_tokens', None)}
                text = ''.join(block.text for block in message.content if block.type == 'text')
                try:
                    output = decode_protocol_object(text.encode('utf-8'))
                except (ValueError, TypeError):
                    # Refusals and off-schema model answers are facts for independent validation.
                    output = text
                return ProviderOutcome(dispatch, output=output)
        except Exception as exc:
            kind, observation = classify(stage, exc)
            if raw is not None:
                kind, observation = 'malformed_provider_response', 'sent'
            dispatch['observation'] = observation
            dispatch['provider_request_id'] = dispatch['provider_request_id'] or getattr(exc, 'request_id', None)
            if observation == 'not_sent':
                dispatch['sent_at'] = None
            detail = f'{type(exc).__name__} status={getattr(exc, "status_code", None)}'
            body = getattr(exc, 'body', None)
            if isinstance(body, Mapping) and isinstance(body.get('error'), Mapping):
                for field, cap in [('type', 100), ('message', PROVIDER_MESSAGE_CAP_CHARS)]:
                    value = body['error'].get(field)
                    if isinstance(value, str):
                        safe = sanitize(value, self._secret, self._canaries)[:cap]
                        detail += f' provider_{field}={safe}'
            return error(kind, 'provider request failed', detail)


class AnthropicWorker(ProviderWorker):
    identity = 'anthropic-worker'
    provider = 'anthropic'
    model = 'claude-haiku-5-5'
    max_output_tokens = 1024
    credentials_ref = 'RIPLEY_ANTHROPIC_API_KEY'
    prompt_ref = {'name': 'nfl-availability', 'version': '1'}
