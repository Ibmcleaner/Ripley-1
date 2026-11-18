"""ADR-010 acceptance against the real SDK and an offline transport."""
import ast
import importlib.util
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from collections.abc import Mapping
from unittest.mock import patch

from ripley.core import (Ledger, Ripley, canonical_json, dispatches_consumed,
                         provider_attempt_outcome, provider_dispatch_counts)
from ripley.nfl_availability import AvailabilityValidator, NflAvailabilityAdapter
from ripley.storage import SQLiteLedger


SDK_INSTALLED = importlib.util.find_spec('anthropic') is not None


@unittest.skipUnless(SDK_INSTALLED, 'optional anthropic SDK is not installed')
class SdkMockTransportTests(unittest.TestCase):
    def test_p6_16_sdk_mock_transport(self):
        guard_attempts = []

        def forbidden(*args, **kwargs):
            guard_attempts.append(True)
            raise RuntimeError('network forbidden in mock transport mode')

        with patch.object(socket.socket, 'connect', forbidden), \
                patch.object(socket.socket, 'connect_ex', forbidden), \
                patch.object(socket, 'create_connection', forbidden):
            import anthropic
            import httpx2

            self.assertEqual(anthropic.__version__, '2.9.0')
            schema = {'type': 'object', 'properties': {'players': {'type': 'array',
                       'items': {'type': 'object'}}}, 'required': ['players'],
                      'additionalProperties': False}
            format_config = {'format': {'type': 'json_schema', 'schema': schema}}
            observed = []

            def handler(request):
                observed.append(request)
                return httpx2.Response(200, headers={'request-id': 'req_offline'}, json={
                    'id': 'msg_offline', 'type': 'message', 'role': 'assistant',
                    'model': 'claude-haiku-5-5', 'content': [{'type': 'text',
                    'text': '{"players":[]}'}], 'stop_reason': 'end_turn',
                    'stop_sequence': None, 'usage': {'input_tokens': 11, 'output_tokens': 5}})

            with anthropic.Anthropic(api_key='sk-ant-test-synthetic-offline-probe',
                    max_retries=0, timeout=5.0,
                    http_client=httpx2.Client(transport=httpx2.MockTransport(handler))) as client:
                self.assertEqual(client.max_retries, 0)
                response = client.messages.create(model='claude-haiku-5-5', max_tokens=1024,
                    messages=[{'role': 'user', 'content': 'offline fixture'}],
                    output_config=format_config)
            self.assertEqual(json.loads(response.content[0].text), {'players': []})
            self.assertEqual(len(observed), 1)
            request = observed[0]
            self.assertEqual(request.method, 'POST')
            self.assertEqual(request.url.path, '/v1/messages')
            self.assertIn('anthropic-version', request.headers)
            body = json.loads(request.content)
            self.assertEqual(body['model'], 'claude-haiku-5-5')
            self.assertEqual(body['output_config'], format_config)

            observed.clear()

            def limited(request):
                observed.append(request)
                return httpx2.Response(429, headers={'request-id': 'req_limited'}, json={
                    'type': 'error', 'error': {'type': 'rate_limit_error', 'message': 'fixture'}})

            with anthropic.Anthropic(api_key='sk-ant-test-synthetic-offline-probe',
                    max_retries=0, timeout=5.0,
                    http_client=httpx2.Client(transport=httpx2.MockTransport(limited))) as client:
                with self.assertRaises(anthropic.RateLimitError):
                    client.messages.create(model='claude-haiku-5-5', max_tokens=1024,
                        messages=[{'role': 'user', 'content': 'offline fixture'}],
                        output_config=format_config)
            self.assertEqual(len(observed), 1)
            self.assertEqual(guard_attempts, [])

        from test_recovery import normalized_source_hash
        from ripley import worker_host
        from ripley.workers import WORKER_SPECS, spec_for

        isolation = Path(__file__).with_name('test_isolation.py')
        self.assertEqual(normalized_source_hash(isolation),
                         '93f58480d14f91acbe6547ccf5486b5ac43a7dc6b1c425606a4897ea0f713661')
        for identity, worker in worker_host.WORKERS.items():
            self.assertIn(identity, WORKER_SPECS)
            self.assertEqual(worker.identity, identity)
            self.assertEqual(spec_for(identity).response_envelope_version, '1')
        self.assertEqual(spec_for('anthropic-worker').response_envelope_version, '1.1')
        self.assertNotIn('anthropic-worker', worker_host.WORKERS)
        with patch.dict(worker_host.WORKERS):
            worker_class = worker_host._worker_class('anthropic-worker')
            self.assertEqual(worker_class.identity, spec_for(worker_class.identity).identity)
            self.assertEqual(worker_class.model, spec_for(worker_class.identity).model)
            self.assertEqual(worker_class.prompt_ref, spec_for(worker_class.identity).prompt_ref)
            self.assertEqual(worker_class.credentials_ref, spec_for(worker_class.identity).credentials_ref)
        for source in Path('ripley').glob('*.py'):
            if source.name == 'providers.py':
                continue
            for line in source.read_text('utf-8').splitlines():
                stripped = line.strip()
                self.assertFalse(stripped.startswith(('import anthropic', 'from anthropic')), str(source))
                if source.name != 'worker_host.py':
                    self.assertNotIn('import AnthropicWorker', stripped)


        for source in Path('scripts').glob('*.py'):
            for node in ast.walk(ast.parse(source.read_text('utf-8'))):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ''] + [
                        f'{node.module}.{alias.name}' for alias in node.names]
                else:
                    continue
                for module in modules:
                    for forbidden in ('anthropic', 'httpx2', 'ripley.providers'):
                        self.assertFalse(module == forbidden or module.startswith(forbidden + '.'),
                                         f'{source}:{node.lineno} imports {module}')


DAY1, DAY2 = '2026-11-15', '2026-11-16'
T1, T2 = DAY1 + 'T18:00:00+00:00', DAY2 + 'T18:00:00+00:00'


def availability_fixture():
    names = {'A': 'Alex Allen', 'B': 'Ben Brown', 'C': 'Chris Clark', 'D': 'Devon Dean'}
    players = [{'player_id': i, 'name': name, 'team': 'TST', 'position': 'WR'}
               for i, name in names.items()]
    rows = []

    def row(row_id, player_id, text, published=T2, report_date=DAY1):
        rows.append({**next(p for p in players if p['player_id'] == player_id),
                     'row_id': row_id, 'text': text, 'published_at': published,
                     'report_date': report_date, 'source': 'nfl.com-injury-report'})

    row('a_old', 'A', 'Designation D', T1)
    row('a_new', 'A', 'Designation Q; practice limited')
    row('b_out', 'B', 'Designation O')
    row('b_q', 'B', 'Designation Q')
    row('c_full', 'C', 'Practice full')
    row('c_dnp', 'C', 'Practice did not practice')
    row('c_day2', 'C', 'Practice limited', report_date=DAY2)
    row('d_old', 'D', 'Designation Q', T1)
    row('d_new', 'D', 'Designation O')
    row('d_full', 'D', 'Practice full')
    row('d_dnp', 'D', 'Practice dnp')

    def entry(player_id, value, support, practice=(), supersession=(), conflict=(), note=''):
        return {'player_id': player_id, 'designation': {'value': value, 'support': support},
                'practice': list(practice), 'supersession': list(supersession),
                'conflict': {'flag': bool(conflict), 'support': list(conflict), 'note': note},
                'as_of': T2}

    output = {'players': [
        entry('A', 'questionable', ['a_new'],
              practice=[{'date': DAY1, 'status': 'limited', 'support': ['a_new']}],
              supersession=[{'field': 'designation', 'governing': 'a_new', 'superseded': ['a_old']}]),
        entry('B', 'unknown', [], conflict=['b_out', 'b_q'], note='designation'),
        entry('C', 'unlisted', ['c_day2'],
              practice=[{'date': DAY2, 'status': 'limited', 'support': ['c_day2']}],
              conflict=['c_full', 'c_dnp'], note='practice:' + DAY1),
        entry('D', 'out', ['d_new'],
              supersession=[{'field': 'designation', 'governing': 'd_new', 'superseded': ['d_old']}],
              conflict=['d_full', 'd_dnp'], note='practice:' + DAY1),
    ]}
    return {'game_id': 'fixture-game', 'team': 'TST', 'cutoff_at': '2026-11-17T12:00:00+00:00',
            'expected_players': players, 'rows': rows}, output


class ValidatorContractTests(unittest.TestCase):
    def check(self, inputs, output):
        ledger = Ledger()
        snapshot = ledger.add('snapshot', {'inputs': inputs})
        result = ledger.add('result', {'output': output})
        return AvailabilityValidator().validate(result, NflAvailabilityAdapter(), snapshot)

    def test_p6_13_nine_validation_rules(self):
        inputs, output = availability_fixture()
        self.assertTrue(self.check(inputs, output)['passed'])
        mutations = [
            (1, lambda x: x['players'].pop()),
            (1, lambda x: x['players'].append(copy.deepcopy(x['players'][0]))),
            (1, lambda x: x['players'][0].update(player_id='extra-player')),
            (2, lambda x: x['players'][0]['designation']['support'].append('missing')),
            (3, lambda x: x['players'][0]['designation'].update(support=['b_out'])),
            (4, lambda x: x['players'][0]['designation'].update(value='out')),
            (4, lambda x: x['players'][0]['designation'].update(support=[])),
            (5, lambda x: x['players'][0]['practice'][0].update(support=[])),
            (5, lambda x: x['players'][2]['practice'].append(
                {'date': DAY1, 'status': 'full', 'support': ['c_full']})),
            (6, lambda x: x['players'][0].update(supersession=[])),
            (7, lambda x: x['players'][0].update(as_of=T1)),
            (8, lambda x: x['players'][0]['designation'].update(value='unknown', support=[])),
            (9, lambda x: x['players'][3]['conflict'].update(flag=False)),
            (9, lambda x: x['players'][1]['conflict'].update(note='')),
        ]
        for rule, mutate in mutations:
            with self.subTest(rule=rule, mutation=mutate):
                changed = copy.deepcopy(output)
                mutate(changed)
                finding = self.check(inputs, changed)
                self.assertFalse(finding['passed'])
                self.assertIn(rule, [failure['rule'] for failure in finding['failures']])

        changed_inputs = copy.deepcopy(inputs)
        # An old agreeing row alone cannot support the governing timestamp.
        old = changed_inputs['rows'][0]
        old['text'] = 'Designation Q'
        changed_output = copy.deepcopy(output)
        changed_output['players'][0]['supersession'] = []
        changed_output['players'][0]['designation']['support'] = ['a_old']
        self.assertFalse(self.check(changed_inputs, changed_output)['passed'])
        changed_output['players'][0]['designation']['support'].append('a_new')
        self.assertTrue(self.check(changed_inputs, changed_output)['passed'])

        # Ownership fails even when a different player's text names the target.
        cross = copy.deepcopy(inputs)
        cross['rows'][2]['text'] = 'Alex Allen out'
        wrong = copy.deepcopy(output)
        wrong['players'][0]['designation'] = {'value': 'out', 'support': ['b_out']}
        self.assertIn(3, [f['rule'] for f in self.check(cross, wrong)['failures']])

        future = copy.deepcopy(inputs)
        future['rows'] = [r for r in future['rows'] if r['player_id'] == 'A']
        future['expected_players'] = future['expected_players'][:1]
        for row in future['rows']:
            row['published_at'] = '2026-11-18T12:00:00+00:00'
        absent = {'players': [{'player_id': 'A', 'designation': {'value': 'unknown', 'support': []},
            'practice': [], 'supersession': [], 'conflict': {'flag': False, 'support': [], 'note': ''},
            'as_of': None}]}
        self.assertTrue(self.check(future, absent)['passed'])
        absent['players'][0]['as_of'] = T2
        self.assertFalse(self.check(future, absent)['passed'])

        newer_practice = copy.deepcopy(inputs)
        newer_practice['rows'].append({**newer_practice['rows'][1], 'row_id': 'a_practice',
            'text': 'Practice full', 'report_date': DAY2,
            'published_at': '2026-11-17T10:00:00+00:00'})
        self.assertTrue(self.check(newer_practice, output)['passed'])


class ProviderFixtures:
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.inputs, self.output = availability_fixture()
        self.output_path = self.root / 'output.json'
        self.output_path.write_text(json.dumps(self.output), encoding='utf-8')
        self.ledger = Ledger()
        self.adapter = NflAvailabilityAdapter()
        self.worker = SimpleNamespace(identity='anthropic-worker')
        self.engine = Ripley(self.ledger, validator=AvailabilityValidator())
        env = patch.dict(os.environ, {'RIPLEY_ENABLE_TEST_WORKERS': '1',
            'RIPLEY_PROVIDER_TRANSPORT': 'mock', 'RIPLEY_ANTHROPIC_API_KEY': 'sk-ant-test-synthetic-fixture',
            'RIPLEY_PILOT_DISPATCH_BUDGET': '25', 'RIPLEY_MOCK_PROVIDER_SCRIPT': '200:valid',
            'RIPLEY_MOCK_PROVIDER_OUTPUT_FILE': str(self.output_path)})
        env.start()
        self.addCleanup(env.stop)

    def run_provider(self, **kwargs):
        return self.engine.run(self.adapter, self.inputs, worker=self.worker,
            allowed_workers=(self.worker.identity,), execution='subprocess', **kwargs)

    def records(self, kind):
        return [r for r in self.ledger.records.values() if r.kind == kind]

    def unchanged(self, operation, error, message):
        before = len(self.ledger.records)
        with self.assertRaisesRegex(error, message):
            operation()
        self.assertEqual(before, len(self.ledger.records))

    def blocked_local(self, *, worker='mock-worker', ceiling='no external calls'):
        from ripley.synthetic import InventoryAdapter

        adapter = InventoryAdapter()
        snapshot = self.ledger.add('snapshot', {'inputs': {'stock': 1, 'demand': 0, 'threshold': 0}})
        task = self.ledger.add('task', {'task_key': 'fixture-' + ceiling, 'state': 'submitted',
            'domain_id': adapter.domain_id, 'domain_version': adapter.version, 'replay_policy': 'safe',
            'resource_ceiling': ceiling, 'input_snapshot_id': snapshot.id})
        self.ledger.transition(task.id, 'submitted', 'running', 'ripley', 'fixture')
        attempt = self.ledger.add('execution_attempt', {'task_id': task.id, 'worker': worker,
            'execution': 'subprocess', 'deadline_at': None})
        self.ledger.add('execution_failure', {'task_id': task.id, 'attempt_id': attempt.id,
                                          'stage': 'interrupted'})
        self.ledger.transition(task.id, 'running', 'blocked', 'ripley', 'fixture')
        return task, adapter


class ProviderContract(ProviderFixtures):
    def assert_no_secrets(self, forbidden):
        def walk(value):
            if isinstance(value, Mapping):
                for key, item in value.items():
                    walk(key)
                    walk(item)
            elif isinstance(value, (tuple, list)):
                for item in value:
                    walk(item)
            elif isinstance(value, str):
                for secret in forbidden:
                    self.assertNotIn(secret, value)
        for record in self.ledger.records.values():
            walk(record.data)

    def test_p6_02_missing_credential_and_record_scan(self):
        with patch.dict(os.environ):
            del os.environ['RIPLEY_ANTHROPIC_API_KEY']
            first = self.run_provider()
            failure = first['failure'].data
            self.assertEqual(first['outcome'], 'blocked_worker_failure')
            self.assertEqual(failure['provider_error'], 'auth_unavailable')
            self.assertEqual(failure['remote_outcome'], 'failed_before_send')
            self.assertEqual(failure['dispatch']['observation'], 'not_sent')
            self.assertIsNone(failure['dispatch']['sent_at'])
            self.assertIsNone(failure['dispatch']['provider_request_id'])
            self.assertIn('mock_requests_seen=0', failure['error']['detail'])
            self.assertIn('sdk_invoked=false', failure['error']['detail'])
            self.assertEqual(dispatches_consumed(self.ledger, first['task'].data['task_key']), 0)
            second = self.run_provider()
            self.assertEqual(second['outcome'], 'blocked_worker_failure')
            self.assertNotEqual(first['attempt'].id, second['attempt'].id)
            self.assertEqual(len(self.records('execution_attempt')), 2)
        secret = 'sk-ant-test-synthetic-LEAKCHECK-0123456789'
        canaries = ('CANARYFRAG1', 'CANARYFRAG2')
        with patch.dict(os.environ, {'RIPLEY_ANTHROPIC_API_KEY': secret,
                                    'RIPLEY_TEST_CANARIES': '|'.join(canaries)}):
            self.assertEqual(self.run_provider()['outcome'], 'pending_owner_approval')
            self.assert_no_secrets((secret, *canaries))

    def test_p6_06_sdk_timeout(self):
        os.environ['RIPLEY_MOCK_PROVIDER_SCRIPT'] = 'read_timeout'
        run = self.run_provider()
        failure = run['failure'].data
        self.assertEqual(run['outcome'], 'blocked_worker_failure')
        self.assertEqual(failure['provider_error'], 'provider_timeout')
        self.assertEqual(failure['dispatch']['observation'], 'possibly_sent')
        self.assertEqual(failure['remote_outcome'], 'unknown')
        self.assertIn('mock_requests_seen=1', failure['error']['detail'])
        self.assertIn('sdk_invoked=true', failure['error']['detail'])
        self.assertNotIn('termination', failure)
        self.unchanged(self.run_provider, PermissionError, 'second paid dispatch requires owner')

    def test_p6_07_parent_kills_hung_provider(self):
        os.environ['RIPLEY_MOCK_PROVIDER_SCRIPT'] = 'hang_after_send'
        self.engine._subprocess_wait = lambda seconds: 2.0
        try:
            run = self.run_provider()
        finally:
            self.engine._subprocess_wait = None
        failure = run['failure'].data
        self.assertEqual(run['outcome'], 'blocked_timeout')
        self.assertIn(failure['termination']['method'], ('terminate', 'kill'))
        self.assertIs(failure['termination']['exited'], True)
        self.assertIsNone(failure['dispatch'])
        self.assertEqual(failure['remote_outcome'], 'unknown')
        self.assertFalse(self.records('late_result'))
        self.assertIsNone(run['late_result'])
        self.assertEqual(dispatches_consumed(self.ledger, run['task'].data['task_key']), 1)
        self.assertEqual(provider_dispatch_counts(self.ledger, 'mock'),
                         {'confirmed_sent': 0, 'uncertain_dispatch': 1, 'budget_slots_consumed': 1})

    def test_p6_12_child_and_parent_redaction(self):
        from ripley.isolation import redact_patterns
        from ripley.synthetic import InventoryAdapter

        secret = 'sk-ant-test-synthetic-LEAKCHECK-0123456789'
        canaries = ('CANARYFRAG1', 'CANARYFRAG2')
        with patch.dict(os.environ, {'RIPLEY_ANTHROPIC_API_KEY': secret,
                'RIPLEY_TEST_CANARIES': '|'.join(canaries),
                'RIPLEY_TEST_SECRET_MARKER': 'PLANTEDMARKER99',
                'RIPLEY_MOCK_PROVIDER_SCRIPT': '500:leaky+leak_stderr'}):
            run = self.run_provider()
            failure = run['failure'].data
            self.assertEqual(run['outcome'], 'blocked_worker_failure')
            self.assertEqual(failure['provider_error'], 'provider_unavailable')
            self.assertEqual(failure['dispatch']['observation'], 'sent')
            self.assertEqual(failure['remote_outcome'], 'failed_after_send')
            self.assertTrue(failure['diagnostics']['text'])
            self.assert_no_secrets((secret, *canaries, 'Authorization:'))
            local_worker = SimpleNamespace(identity='test-behavior-worker')
            with patch.dict(os.environ, {'RIPLEY_TEST_WORKER_BEHAVIOR':
                                         'stderr_text:sk-ant-PLANTED0000000000+raise'}):
                local = Ripley(self.ledger).run(InventoryAdapter(),
                    {'stock': 1, 'demand': 0, 'threshold': 0}, worker=local_worker,
                    allowed_workers=(local_worker.identity,), execution='subprocess')
            self.assertEqual(local['outcome'], 'blocked_worker_failure')
            diagnostics = local['failure'].data['diagnostics']['text']
            self.assertIn('[REDACTED]', diagnostics)
            self.assertNotIn('sk-ant-PLANTED', diagnostics)
            for text in ('token=' + 'A' * 48, 'Bearer abc.def', 'PLANTEDMARKER99'):
                self.assertIn('[REDACTED]', redact_patterns(text))
            with patch.dict(os.environ):
                del os.environ['RIPLEY_ENABLE_TEST_WORKERS']
                self.assertEqual(redact_patterns('PLANTEDMARKER99'), 'PLANTEDMARKER99')

    def test_p6_14_socket_guard_gates_and_budgets(self):
        guard_attempts = []

        def forbidden(*args, **kwargs):
            guard_attempts.append(True)
            raise RuntimeError('network forbidden in mock transport mode')

        with patch.dict(os.environ, {'RIPLEY_MOCK_PROVIDER_SCRIPT': 'bypass_transport'}), \
                patch.object(socket.socket, 'connect', forbidden), \
                patch.object(socket.socket, 'connect_ex', forbidden), \
                patch.object(socket, 'create_connection', forbidden):
            run = self.run_provider()
        self.assertEqual(run['outcome'], 'blocked_host_failure')
        self.assertEqual(run['failure'].data['returncode'], 3)
        self.assertIsNone(run['failure'].data['dispatch'])
        self.assertEqual(run['failure'].data['remote_outcome'], 'unknown')
        self.assertEqual(dispatches_consumed(self.ledger, run['task'].data['task_key']), 1)
        self.assertEqual(guard_attempts, [])

        for missing in ('RIPLEY_PROVIDER_TRANSPORT', 'RIPLEY_ENABLE_TEST_WORKERS'):
            self.inputs['game_id'] = 'gate-' + missing
            with patch.dict(os.environ):
                del os.environ[missing]
                run = self.run_provider()
            failure = run['failure'].data
            self.assertEqual(run['outcome'], 'blocked_worker_failure')
            self.assertEqual(failure['provider_error'], 'live_gate_closed')
            self.assertEqual(failure['dispatch']['observation'], 'not_sent')
            self.assertEqual(failure['remote_outcome'], 'failed_before_send')
            self.assertIn('mock_requests_seen=0', failure['error']['detail'])
            gates = {g['name']: g['present'] for g in run['attempt'].data['gates']}
            self.assertIs(gates['RIPLEY_LIVE_DISPATCH'], False)
            if missing == 'RIPLEY_PROVIDER_TRANSPORT':
                self.assertIsNone(run['attempt'].data['transport_mode'])

        # Each budget scenario starts with an empty ledger of the fixture's type.
        def fresh_ledger(name):
            return SQLiteLedger(self.root / name) if isinstance(self.ledger, SQLiteLedger) else Ledger()

        self.ledger = fresh_ledger('budget.sqlite')
        self.engine = Ripley(self.ledger, validator=AvailabilityValidator())
        with patch.dict(os.environ, {'RIPLEY_PILOT_DISPATCH_BUDGET': '2'}):
            for game in ('budget-one', 'budget-two'):
                self.inputs['game_id'] = game
                self.assertEqual(self.run_provider()['outcome'], 'pending_owner_approval')
            self.inputs['game_id'] = 'budget-three'
            before = tuple(self.ledger.records)
            with self.assertRaisesRegex(ValueError, '^pilot dispatch budget exhausted$'):
                self.run_provider()
            appended = tuple(self.ledger.records.values())[len(before):]
            self.assertEqual(tuple(self.ledger.records)[:len(before)], before)
            self.assertEqual(len(appended), 1)
            self.assertEqual(appended[0].kind, 'pilot_budget_exhausted')
            self.assertEqual(dict(appended[0].data),
                             {'budget': 2, 'consumed': 2, 'transport_mode': 'mock'})

        self.ledger = fresh_ledger('separation.sqlite')
        self.engine = Ripley(self.ledger, validator=AvailabilityValidator())
        # Ledger fixture only; no live execution or live environment selection.
        self.ledger.add('execution_attempt', {'task_id': 'unresolved-fixture',
                         'worker': self.worker.identity, 'transport_mode': 'live'})
        with patch.dict(os.environ, {'RIPLEY_PILOT_DISPATCH_BUDGET': '1'}):
            self.inputs['game_id'] = 'separate-mock'
            self.assertEqual(self.run_provider()['outcome'], 'pending_owner_approval')
        self.assertEqual(provider_dispatch_counts(self.ledger, 'live'),
                         {'confirmed_sent': 0, 'uncertain_dispatch': 1, 'budget_slots_consumed': 1})
        self.assertEqual(provider_dispatch_counts(self.ledger, 'mock'),
                         {'confirmed_sent': 1, 'uncertain_dispatch': 0, 'budget_slots_consumed': 1})

    def test_p6_15_startup_budget(self):
        self.adapter.timeout_seconds = 10
        with patch.dict(os.environ, {'RIPLEY_MOCK_PROVIDER_SCRIPT': 'startup_delay:3'}):
            run = self.run_provider()
        failure = run['failure'].data
        self.assertEqual(run['outcome'], 'blocked_worker_failure')
        self.assertEqual(failure['provider_error'], 'insufficient_time')
        self.assertEqual(failure['dispatch']['observation'], 'not_sent')
        self.assertEqual(failure['remote_outcome'], 'failed_before_send')
        self.assertIsNone(failure['dispatch']['sent_at'])
        self.assertIn('sdk_invoked=false', failure['error']['detail'])
        self.assertIn('mock_requests_seen=0', failure['error']['detail'])
        self.assertEqual(dispatches_consumed(self.ledger, run['task'].data['task_key']), 0)
        self.assertEqual(self.run_provider()['outcome'], 'pending_owner_approval')

    def test_p6_01_provider_preconditions(self):
        for timeout in (None, 0.1, 9):
            self.adapter.timeout_seconds = timeout
            self.unchanged(self.run_provider, ValueError, 'provider workers require timeout_seconds >= 10')
        self.adapter.timeout_seconds = 45
        self.inputs['rows'][0]['text'] = 'X' * 24001
        self.unchanged(self.run_provider, ValueError, 'row text exceeds 24000 characters')

    def test_p6_03_success(self):
        run = self.run_provider()
        self.assertEqual(run['outcome'], 'pending_owner_approval')
        self.assertEqual(canonical_json(run['result'].data['output']), canonical_json(self.output))
        self.assertEqual(run['task'].data['task_type'], 'extract')
        self.assertEqual(run['task'].data['resource_ceiling'], 'provider')
        self.assertEqual(run['result'].data['execution'], 'provider')
        self.assertIsNone(run['result'].data['cost'])
        self.assertEqual(run['result'].data['remote_outcome'], 'completed')
        dispatch = run['result'].data['dispatch']
        self.assertEqual(dispatch['observation'], 'sent')
        self.assertEqual(dispatch['usage']['input_tokens'], 100)
        self.assertEqual(dispatch['provider_request_id'], 'req_offline_provider')
        self.assertTrue(run['validation'].data['passed'])
        self.assertEqual(run['review'].data['purpose'], 'policy')

    def test_p6_04_http_failures(self):
        for status, kind in [('401', 'auth_rejected'), ('400', 'invalid_request'),
                             ('429', 'rate_limited'), ('500', 'provider_unavailable')]:
            with self.subTest(status=status):
                self.inputs['game_id'] = status
                os.environ['RIPLEY_MOCK_PROVIDER_SCRIPT'] = status
                run = self.run_provider()
                self.assertEqual(run['outcome'], 'blocked_worker_failure')
                failure = run['failure'].data
                self.assertEqual(failure['provider_error'], kind)
                self.assertEqual(failure['remote_outcome'], 'failed_after_send')
                self.assertEqual(failure['dispatch']['observation'], 'sent')
                self.assertIn('mock_requests_seen=1', failure['error']['detail'])
                self.assertIn('status=' + status, failure['error']['detail'])
                self.assertIsNone(run['result'])

    def test_p6_05_uncertain_dispatch(self):
        os.environ['RIPLEY_MOCK_PROVIDER_SCRIPT'] = 'reset_after_write'
        run = self.run_provider()
        self.assertEqual(run['outcome'], 'blocked_worker_failure')
        self.assertEqual(run['failure'].data['remote_outcome'], 'unknown')
        self.assertEqual(run['failure'].data['dispatch']['observation'], 'possibly_sent')
        self.assertIn('mock_requests_seen=1', run['failure'].data['error']['detail'])
        self.unchanged(self.run_provider, PermissionError, 'second paid dispatch requires owner')

    def test_p6_08_owner_authorized_redispatch(self):
        from ripley.core import dispatches_consumed

        first = self.run_provider()
        task_key = first['task'].data['task_key']
        self.assertEqual(first['outcome'], 'pending_owner_approval')
        self.assertEqual(len(self.records('execution_attempt')), 1)
        self.assertEqual(dispatches_consumed(self.ledger, task_key), 1)
        before_duplicate = len(self.ledger.records)
        duplicate = self.run_provider()
        self.assertEqual(duplicate['outcome'], 'duplicate_of_existing_task')
        self.assertEqual(duplicate['task'].id, first['task'].id)
        self.assertEqual(len(self.ledger.records), before_duplicate + 1)
        submission = tuple(self.ledger.records.values())[-1]
        self.assertEqual(submission.kind, 'duplicate_submission')
        self.assertEqual(submission.data['task_id'], first['task'].id)
        self.assertEqual(len(self.records('execution_attempt')), 1)
        self.assertEqual(dispatches_consumed(self.ledger, task_key), 1)

        self.engine.decide_approval(first['approval'].id, 'owner', 'approved', 'fixture approval')
        self.assertEqual(self.ledger.task_state(first['task'].id), 'approved')
        self.unchanged(self.run_provider, PermissionError, 'second paid dispatch requires owner')
        self.assertEqual(len(self.records('execution_attempt')), 1)
        self.assertEqual(dispatches_consumed(self.ledger, task_key), 1)
        auth = self.ledger.add('dispatch_authorization', {
            'task_key': task_key, 'prior_attempt_id': first['attempt'].id,
            'prior_remote_outcome': 'completed', 'actor': 'owner', 'reason': 'fixture permission'})
        second = self.run_provider()
        self.assertEqual(second['outcome'], 'pending_owner_approval')
        self.assertEqual(len(self.records('execution_attempt')), 2)
        self.assertEqual(second['attempt'].data['dispatch_authorization_id'], auth.id)
        self.assertEqual(sum(r.data.get('dispatch_authorization_id') == auth.id
                             for r in self.records('execution_attempt')), 1)
        self.assertEqual(dispatches_consumed(self.ledger, task_key), 2)

        self.engine.decide_approval(second['approval'].id, 'owner', 'approved', 'fixture approval')
        self.assertEqual(self.ledger.task_state(second['task'].id), 'approved')
        self.unchanged(self.run_provider, PermissionError, 'second paid dispatch requires owner')
        self.assertEqual(len(self.records('execution_attempt')), 2)
        self.assertEqual(dispatches_consumed(self.ledger, task_key), 2)

    def test_p6_09_correction_recovery_and_execution_authority(self):
        self.output_path.write_text('{"players":[]}', encoding='utf-8')
        run = self.run_provider(correction_budget=7)
        self.assertEqual(self.ledger.task_state(run['task'].id), 'blocked')
        self.assertTrue(run['attempt'].data['correction_budget_forced'])
        self.assertEqual(len(self.records('execution_attempt')), 1)
        self.assertFalse(self.records('correction_request'))
        self.unchanged(lambda: self.engine.run(self.adapter, self.inputs, worker=self.worker,
            allowed_workers=(self.worker.identity,)), ValueError, 'provider workers run only in subprocess')
        task, adapter = self.blocked_local()
        self.unchanged(lambda: self.engine.recover(task.id, 'owner', 'fixture', adapter,
            worker=self.worker, allowed_workers=(self.worker.identity,)), ValueError,
            'recovery may not change worker kind')
        task, adapter = self.blocked_local(worker='anthropic-worker', ceiling='provider')
        self.unchanged(lambda: self.engine.recover(task.id, 'owner', 'fixture', adapter),
                       ValueError, 'recovery requires no external calls')

    def test_p6_10_strict_response_versions(self):
        from ripley.isolation import _response

        run = self.run_provider()
        packet = self.records('execution_request')[0].data['packet']
        response = {'envelope_version': '1.1', 'attempt_id': run['attempt'].id,
                    'worker_identity': self.worker.identity, 'status': 'ok',
                    'output': self.output, 'dispatch': run['result'].data['dispatch']}
        self.assertEqual(_response(canonical_json(response), packet, '1.1')['status'], 'ok')
        for changes in ({'envelope_version': '1'}, {'dispatch': {}}, {'dispatch': None}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError,
                    'unsupported envelope version for worker class'):
                _response(canonical_json({**response, **changes}), packet, '1.1')
        with self.assertRaisesRegex(ValueError, 'unsupported envelope version for worker class'):
            _response(canonical_json(response), packet)

        # Corrupt bytes only after a real offline child has completed its request.
        # Keep Popen, SDK execution, and parent failure classification real.
        def corrupt(raw, request_packet, expected_version='1'):
            parsed = json.loads(raw)
            parsed['envelope_version'] = '1'
            return _response(canonical_json(parsed), request_packet, expected_version)

        self.inputs['game_id'] = 'wrong-version'
        with patch('ripley.isolation._response', side_effect=corrupt):
            failed = self.run_provider()
        self.assertEqual(failed['outcome'], 'blocked_host_failure')
        self.assertEqual(failed['failure'].data['remote_outcome'], 'unknown')
        self.assertIsNone(failed['result'])

    def test_p6_11_parent_and_child_prompt_hashes(self):
        template = Path('ripley/prompts/nfl-availability/1.md')
        digest = hashlib.sha256(template.read_bytes()).hexdigest()
        run = self.run_provider()
        self.assertEqual(run['attempt'].data['prompt_ref']['content_hash'], digest)
        self.assertEqual(run['result'].data['dispatch']['prompt_ref']['content_hash'], digest)
        self.inputs['game_id'] = 'changed-template'
        original = template.read_bytes()

        def change_template(wait_seconds):
            template.write_bytes(original + b'\n')
            return wait_seconds

        self.engine._subprocess_wait = change_template
        try:
            failed = self.run_provider()
        finally:
            template.write_bytes(original)
            self.engine._subprocess_wait = None
        self.assertEqual(failed['outcome'], 'blocked_host_failure')
        self.assertEqual(failed['failure'].data['message'], 'prompt_ref hash mismatch')
        self.assertEqual(failed['failure'].data['remote_outcome'], 'unknown')
        self.assertIsNone(failed['failure'].data['dispatch'])
        self.assertIsNone(failed['result'])
        from ripley.core import dispatches_consumed
        self.assertEqual(dispatches_consumed(self.ledger, failed['task'].data['task_key']), 1)


@unittest.skipUnless(SDK_INSTALLED, 'optional anthropic SDK is not installed')
class MemoryProviderTests(ProviderContract, unittest.TestCase):
    pass


@unittest.skipUnless(SDK_INSTALLED, 'optional anthropic SDK is not installed')
class SQLiteProviderTests(ProviderContract, unittest.TestCase):
    def test_p6_17_restart_accounting(self):
        run = self.run_provider()
        # A separate file isolates the one unresolved attempt's counts from the completed control.
        path = self.root / 'restart.sqlite'
        ledger = SQLiteLedger(path)
        task = ledger.add('task', {**run['task'].data, 'task_key': 'restart-provider-fixture'})
        ledger.transition(task.id, 'submitted', 'running', 'ripley', 'fixture')
        attempt = ledger.add('execution_attempt', {**run['attempt'].data, 'task_id': task.id})
        expected = {'confirmed_sent': 0, 'uncertain_dispatch': 1, 'budget_slots_consumed': 1}
        self.assertEqual(provider_attempt_outcome(ledger, attempt), 'unknown')
        self.assertEqual(provider_dispatch_counts(ledger, 'mock'), expected)
        self.assertFalse(any(r.kind in ('execution_request', 'result', 'execution_failure')
                             for r in ledger.records.values()))
        # SQLiteLedger closes each connection internally; reopening reloads the file.
        ledger = SQLiteLedger(path)
        failure = next(r for r in ledger.records.values() if r.kind == 'execution_failure')
        self.assertEqual(failure.data['stage'], 'interrupted')
        self.assertEqual(failure.data['remote_outcome'], 'unknown')
        self.assertIsNone(failure.data['dispatch'])
        self.assertEqual(failure.data['attempt_id'], attempt.id)
        self.assertEqual(ledger.task_state(task.id), 'blocked')
        self.assertEqual(dispatches_consumed(ledger, task.data['task_key']), 1)
        self.assertEqual(provider_dispatch_counts(ledger, 'mock'), expected)
        before = tuple(ledger.records.values())
        with self.assertRaises(ValueError):
            Ripley(ledger, validator=AvailabilityValidator()).recover(
                task.id, 'owner', 'fixture', self.adapter, worker=self.worker,
                allowed_workers=(self.worker.identity,), execution='subprocess')
        self.assertEqual(tuple(ledger.records.values()), before)
        self.assertEqual(dispatches_consumed(ledger, task.data['task_key']), 1)
        self.assertEqual(provider_dispatch_counts(ledger, 'mock'), expected)
        self.assertEqual(tuple(SQLiteLedger(path).records.values()), before)

    def setUp(self):
        factory = patch.dict(globals(), {'Ledger': lambda: SQLiteLedger(self.root / 'ledger.sqlite')})
        factory.start()
        self.addCleanup(factory.stop)
        super().setUp()
