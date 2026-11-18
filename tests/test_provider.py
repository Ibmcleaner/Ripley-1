"""ADR-010 acceptance against the real SDK and an offline transport."""
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
from unittest.mock import patch

from ripley.core import Ledger, Ripley, canonical_json
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
    def setUp(self):
        factory = patch.dict(globals(), {'Ledger': lambda: SQLiteLedger(self.root / 'ledger.sqlite')})
        factory.start()
        self.addCleanup(factory.stop)
        super().setUp()
