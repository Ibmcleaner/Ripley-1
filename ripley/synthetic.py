"""Small non-NFL adapter: synthetic inventory reorder decision."""
from datetime import datetime, timezone


class InventoryAdapter:
    domain_id = 'synthetic-inventory'
    version = '1'
    replay_policy = 'safe'
    expected_output = {'reorder': bool, 'projected_stock': int}

    def snapshot_metadata(self, inputs):
        return {'observed_at': datetime.now(timezone.utc).isoformat(),
                'sources': ['synthetic-inventory-fixture'],
                'data_quality': 'synthetic'}

    def predict(self, inputs):
        stock, demand, threshold = (inputs[k] for k in ('stock', 'demand', 'threshold'))
        if not all(type(x) is int and x >= 0 for x in (stock, demand, threshold)):
            raise ValueError('nonnegative integers required')
        remaining = stock - demand
        return {'reorder': remaining < threshold, 'projected_stock': remaining}


class TestBehaviorWorker:
    """Fault fixtures selected only by the explicitly test-enabled host."""
    identity = 'test-behavior-worker'

    def __init__(self):
        import os
        self.behaviors = os.environ.get('RIPLEY_TEST_WORKER_BEHAVIOR', 'ok').split('+')

    def produce(self, task, snapshot, adapter):
        import signal
        import sys
        import time

        for behavior in self.behaviors:
            name, _, argument = behavior.partition(':')
            if name in ('trap_sigterm_and_sleep', 'trap_sigterm_then_complete'):
                signal.signal(signal.SIGTERM, lambda *_: None)
            if name in ('sleep', 'trap_sigterm_and_sleep'):
                time.sleep(float(argument))
            elif name == 'stderr':
                count = int(argument)
                sys.stderr.buffer.write(b'A' * (count // 2) + b'Z' * (count - count // 2))
                sys.stderr.buffer.flush()
            elif name == 'raise':
                raise RuntimeError('test worker raised')
            elif name == 'stderr_text':
                from urllib.parse import unquote
                sys.stderr.write(unquote(argument))
                sys.stderr.flush()
            elif name == 'bad_output':
                return {}
        return adapter.predict(snapshot['inputs'])

    def write_test_response(self, response, stream):
        import time
        from ripley.core import canonical_json

        if 'exit_zero_no_output' in self.behaviors:
            return
        if 'garbage_stdout' in self.behaviors:
            stream.write(b'garbage')
            return
        if 'partial_json' in self.behaviors:
            stream.write(b'{"attempt_id":')
            return
        if 'wrong_attempt_id' in self.behaviors:
            response['attempt_id'] = 'incorrect-attempt'
            response['output'] = {'discarded': 'uncorrelated-output-marker'}
        raw = canonical_json(response)
        for behavior in self.behaviors:
            name, _, seconds = behavior.partition(':')
            if name == 'trap_sigterm_then_complete':
                # The same partial envelope either completes during grace or
                # remains the only available bytes when the parent kills us.
                stream.write(raw[:1])
                stream.flush()
                time.sleep(float(seconds))
                raw = raw[1:]
        stream.write(raw)
