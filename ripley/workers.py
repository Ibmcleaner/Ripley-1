"""Trusted Worker descriptors, independent of provider implementation imports."""
from collections import namedtuple
from types import MappingProxyType

from .core import freeze


WorkerSpec = namedtuple('WorkerSpec', 'identity kind response_envelope_version external_calls '
                        'paid_correction_allowed provider model credentials_ref prompt_ref')

# Preserve the immutable namedtuple descriptors. freeze() deliberately converts
# sequences into plain tuples, so freeze their nested metadata individually.
WORKER_SPECS = MappingProxyType({
    'mock-worker': WorkerSpec('mock-worker', 'local', '1', 'no external calls',
                            True, None, None, None, None),
    'test-behavior-worker': WorkerSpec('test-behavior-worker', 'local', '1', 'no external calls',
                                     True, None, None, None, None),
    'anthropic-worker': WorkerSpec('anthropic-worker', 'provider', '1.1', 'provider', False,
        'anthropic', 'claude-haiku-5-5', 'RIPLEY_ANTHROPIC_API_KEY',
        freeze({'name': 'nfl-availability', 'version': '1'})),
})
PROVIDER_ENVELOPE_VERSION = '1.1'
PILOT_DISPATCH_BUDGET_ENV = 'RIPLEY_PILOT_DISPATCH_BUDGET'
PROVIDER_ERROR_TYPES = frozenset((
    'live_gate_closed', 'auth_unavailable', 'insufficient_time', 'auth_rejected',
    'rate_limited', 'invalid_request', 'provider_unavailable', 'provider_timeout',
    'malformed_provider_response'))


def spec_for(identity):
    try:
        return WORKER_SPECS[identity]
    except KeyError:
        raise ValueError('no worker spec for identity') from None
