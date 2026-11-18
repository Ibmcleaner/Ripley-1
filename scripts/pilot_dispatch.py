"""Owner-operated, single-attempt entry point. Run from the repository root."""
import argparse
from collections.abc import Mapping
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ripley.core import Ripley, dispatches_consumed, provider_dispatch_counts
from ripley.isolation import redact_patterns
from ripley.nfl_availability import AvailabilityValidator, NflAvailabilityAdapter
from ripley.storage import SQLiteLedger


def preconditions(env: Mapping, authorization_path: str | None) -> str | None:
    mode = env.get('RIPLEY_PROVIDER_TRANSPORT')
    if mode == 'mock':
        if env.get('RIPLEY_ENABLE_TEST_WORKERS') != '1':
            return 'mock mode requires RIPLEY_ENABLE_TEST_WORKERS=1'
        if not env.get('RIPLEY_MOCK_PROVIDER_OUTPUT_FILE'):
            return 'mock mode requires RIPLEY_MOCK_PROVIDER_OUTPUT_FILE'
        return None
    if mode != 'live':
        return 'RIPLEY_PROVIDER_TRANSPORT must select mock or live'
    if 'RIPLEY_ENABLE_TEST_WORKERS' in env:
        return 'live mode requires RIPLEY_ENABLE_TEST_WORKERS to be absent'
    if env.get('RIPLEY_LIVE_DISPATCH') != '1':
        return 'live mode requires RIPLEY_LIVE_DISPATCH'
    try:
        budget = int(env.get('RIPLEY_PILOT_DISPATCH_BUDGET', ''))
    except (ValueError, TypeError):
        budget = 0
    if not 1 <= budget <= 25:
        return 'live mode requires RIPLEY_PILOT_DISPATCH_BUDGET between 1 and 25'
    if not authorization_path:
        return 'live mode requires --authorization'
    return None


def report(ledger, run, mode):
    print('outcome:', run['outcome'])
    for key in ('task', 'attempt', 'result', 'failure'):
        record = run[key]
        print(f'{key}_id:', record.id if record else '-')

    # Core accounts a preserved Result before any later local failure.
    fact = run['result'] or run['failure']
    data = fact.data if fact else {}
    dispatch = data.get('dispatch') or {}
    print('observation:', dispatch.get('observation') or '-')
    print('remote_outcome:', data.get('remote_outcome') or '-')
    print('provider_error:', data.get('provider_error') or '-')
    usage = dispatch.get('usage')
    print('usage:', dict(usage) if usage is not None else '-')
    request_id = dispatch.get('provider_request_id')
    if request_id and not re.fullmatch(r'[A-Za-z0-9._:-]+', request_id):
        request_id = '[REDACTED]'
    print('provider_request_id:', redact_patterns(request_id) if request_id else '-')
    print('dispatches_consumed:', dispatches_consumed(ledger, run['task'].data['task_key']))
    print(f'pilot counts ({mode}):', provider_dispatch_counts(ledger, mode))


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--authorization')
    args = parser.parse_args()
    adapter = NflAvailabilityAdapter()
    try:
        raw = args.packet.read_bytes()
        packet = json.loads(raw.decode('utf-8'))
        adapter.snapshot_metadata(packet)
    except (OSError, TypeError, ValueError):
        print('cannot read a valid availability packet')
        return 2

    digest = hashlib.sha256(raw).hexdigest()
    print('packet_sha256:', digest)
    print('player_count:', len(packet['expected_players']))
    print('row_count:', len(packet['rows']))
    env = os.environ
    refusal = preconditions(env, args.authorization)
    if refusal:
        print(refusal)
        return 2
    if args.authorization is not None:
        try:
            authorized = digest in Path(args.authorization).read_text(encoding='utf-8')
        except (OSError, ValueError):
            authorized = False
        if not authorized:
            print('authorization file missing, unreadable, or missing the packet SHA-256')
            return 2
    if importlib.util.find_spec('anthropic') is None:
        print('required provider SDK is not installed')
        return 2

    mode = env['RIPLEY_PROVIDER_TRANSPORT']
    try:
        budget = int(env.get('RIPLEY_PILOT_DISPATCH_BUDGET', '25'))
    except ValueError:
        print('RIPLEY_PILOT_DISPATCH_BUDGET must be an integer')
        return 2
    print('transport_mode:', mode)
    names = set(iter(env))  # Presence only, including for the credential.
    for name in ('RIPLEY_LIVE_DISPATCH', 'RIPLEY_ENABLE_TEST_WORKERS', 'RIPLEY_ANTHROPIC_API_KEY'):
        print(f'{name} present:', name in names)
    print('budget:', budget)
    print('ledger:', redact_patterns(ascii(str(args.ledger))[1:-1]))
    if mode == 'live':
        print('LIVE MODE — one provider dispatch will leave this machine')
        if not sys.stdin.isatty() or input_confirmation() != 'DISPATCH':
            print('interactive DISPATCH confirmation required')
            return 2

    try:
        ledger = SQLiteLedger(args.ledger)
        engine = Ripley(ledger, validator=AvailabilityValidator())
        worker = SimpleNamespace(identity='anthropic-worker')
        run = engine.run(adapter, packet, worker=worker, allowed_workers=(worker.identity,),
                         execution='subprocess')
    except Exception as exc:
        # Only these parent-generated messages are safe to expose to the operator.
        if str(exc) in ('second paid dispatch requires owner dispatch_authorization',
                        'pilot dispatch budget exhausted'):
            print(str(exc))
        else:
            print('unable to open the ledger or complete the run')
        return 2
    report(ledger, run, mode)
    return 0 if run['outcome'] == 'pending_owner_approval' else 1


def input_confirmation():
    try:
        return input('Type DISPATCH to confirm: ')
    except (EOFError, KeyboardInterrupt):
        return None


if __name__ == '__main__':
    sys.exit(main())
