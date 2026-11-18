"""6D-prep runner contracts. All subprocess environments select mock transport."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from ripley.core import Ledger, Ripley, dispatches_consumed
from ripley.nfl_availability import AvailabilityValidator, NflAvailabilityAdapter
from ripley.storage import SQLiteLedger
from scripts.pilot_dispatch import preconditions
from test_provider import SDK_INSTALLED, single_capture_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'fixtures' / 'nfl-availability'


@unittest.skipUnless(SDK_INSTALLED, 'optional anthropic SDK is not installed')
class PilotRunnerTests(unittest.TestCase):
    def frozen_packet(self):
        packets = [p for p in FIXTURES.glob('*.json') if not p.name.endswith('.expected.json')]
        self.assertEqual(len(packets), 1, 'the pilot requires one frozen packet')
        return packets[0]

    def test_p6d_01_packet_is_frozen_and_valid(self):
        path = self.frozen_packet()
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        provenance = path.with_suffix('.provenance.md').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'\b[0-9a-f]{64}\b', provenance), [digest])
        packet = json.loads(raw)
        adapter = NflAvailabilityAdapter()
        adapter.snapshot_metadata(packet)
        self.assertEqual(packet['game_id'], path.stem)
        self.assertIsNone(packet['source_published_at'])
        self.assertEqual(packet['observed_at'], '2026-11-18T18:49:07+00:00')
        self.assertEqual(packet['evidence_at_basis'], 'observed_at')
        self.assertEqual(packet['cutoff_at'], packet[packet['evidence_at_basis']])
        self.assertEqual(len(packet['rows']), 3)
        self.assertEqual(len(packet['expected_players']), 3)
        forbidden = r'\b(?:O|D|Q|out|doubtful|questionable|full|limited|dnp|did not practice)\b|\d{4}-\d\d-\d\d'
        for row in packet['rows']:
            self.assertEqual(row['evidence_at'], packet['cutoff_at'])
            self.assertEqual(row['report_date'], '2026-11-18')
            status = re.fullmatch(r'Injury: ([^;\r\n]+); Game status: (Out|Doubtful|Questionable)', row['text'])
            self.assertIsNotNone(status, 'the frozen pilot contains designation rows only')
            self.assertNotRegex(status[1], re.compile(forbidden, re.IGNORECASE))
            self.assertEqual(row['row_id'], f"{row['player_id']}-{row['report_date']}-status")
        output = json.loads(path.with_suffix('.expected.json').read_bytes())
        for player in output['players']:
            self.assertEqual(player['practice'], [])
        ledger = Ledger()
        snapshot = ledger.add('snapshot', {'inputs': packet})
        result = ledger.add('result', {'output': output})
        finding = AvailabilityValidator().validate(result, adapter, snapshot)
        self.assertTrue(finding['passed'], finding['failures'])

        for changed in ({'evidence_at_basis': 'source_published_at'},
                        {'evidence_at_basis': 'cutoff_at'},
                        {'observed_at': None},
                        {'source_published_at': '2026-11-18T12:49:07-06:00'},
                        {'cutoff_at': '2026-11-18T18:49:08+00:00'},
                        {'rows': [{**row, 'evidence_at': '2026-11-18T18:49:08+00:00'}
                                  for row in packet['rows']]}):
            with self.subTest(field=next(iter(changed))), self.assertRaises(ValueError):
                adapter.snapshot_metadata({**packet, **changed})
        published = '2026-11-18T18:00:00+00:00'
        source_based = {**packet, 'source_published_at': published,
                        'evidence_at_basis': 'source_published_at', 'cutoff_at': published,
                        'rows': [{**row, 'evidence_at': published} for row in packet['rows']]}
        self.assertEqual(adapter.snapshot_metadata(source_based)['observed_at'], packet['observed_at'])

    def exercise_runner(self, packet, output, root):
        path = root / 'pilot.sqlite'
        key = 'sk-ant-test-synthetic-runner-0123456789'
        env = {k: os.environ[k] for k in os.environ if not k.startswith('RIPLEY_')}
        env.update(RIPLEY_PROVIDER_TRANSPORT='mock', RIPLEY_ENABLE_TEST_WORKERS='1',
                   RIPLEY_MOCK_PROVIDER_SCRIPT='200:valid', RIPLEY_MOCK_PROVIDER_OUTPUT_FILE=str(output),
                   RIPLEY_ANTHROPIC_API_KEY=key, RIPLEY_PILOT_DISPATCH_BUDGET='1')

        def invoke(status, message, *args, database=path, budget='1'):
            child_env = {**env, 'RIPLEY_PILOT_DISPATCH_BUDGET': budget}
            self.assertEqual(child_env['RIPLEY_PROVIDER_TRANSPORT'], 'mock')
            self.assertNotIn('RIPLEY_LIVE_DISPATCH', child_env)
            proc = subprocess.run([sys.executable, 'scripts/pilot_dispatch.py', '--packet', str(packet),
                                   '--ledger', str(database), *args], cwd=ROOT, env=child_env,
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
            for forbidden in (key, key[-10:], 'players'):
                self.assertNotIn(forbidden, proc.stdout + proc.stderr)
            self.assertEqual(proc.returncode, status, proc.stdout + proc.stderr)
            self.assertIn(message, proc.stdout)
            return proc.stdout

        auth_file = root / 'authorization.txt'
        invoke(2, 'authorization file', '--authorization', str(auth_file))
        auth_file.write_text('different digest', encoding='utf-8')
        invoke(2, 'authorization file', '--authorization', str(auth_file))
        self.assertFalse(path.exists())
        auth_file.write_text(hashlib.sha256(packet.read_bytes()).hexdigest(), encoding='utf-8')
        stdout = invoke(0, 'pending_owner_approval', '--authorization', str(auth_file))
        for expected in ('observation: sent', 'remote_outcome: completed', "'budget_slots_consumed': 1"):
            self.assertIn(expected, stdout)
        ledger = SQLiteLedger(path)
        records = tuple(ledger.records.values())
        self.assertEqual(Counter(r.kind for r in records), Counter(
            snapshot=1, task=1, task_transition=3, execution_attempt=1, execution_request=1,
            result=1, validation=1, review=1, evidence=1, approval=1))
        first = next(r for r in records if r.kind == 'execution_attempt')
        self.assertEqual(first.data['transport_mode'], 'mock')
        task = ledger.records[first.data['task_id']]
        task_key = task.data['task_key']
        self.assertEqual(ledger.task_state(task.id), 'pending_owner_approval')
        self.assertEqual(dispatches_consumed(ledger, task_key), 1)

        def appended(before):
            reopened = SQLiteLedger(path)
            self.assertEqual(tuple(reopened.records)[:len(before)], before)
            return reopened, tuple(reopened.records.values())[len(before):]

        before = tuple(ledger.records)
        invoke(1, 'duplicate_of_existing_task')
        ledger, added = appended(before)
        self.assertEqual([r.kind for r in added], ['duplicate_submission'])
        self.assertEqual(added[0].data['task_id'], task.id)
        self.assertEqual(dispatches_consumed(ledger, task_key), 1)
        pending = next(r for r in records if r.kind == 'approval')
        Ripley(ledger).decide_approval(pending.id, 'owner', 'approved', 'dry-run fixture')
        self.assertEqual(ledger.task_state(task.id), 'approved')

        before = tuple(ledger.records)
        invoke(2, 'second paid dispatch requires owner')
        ledger, added = appended(before)
        self.assertFalse(added)
        authorization = ledger.add('dispatch_authorization', {
            'task_key': task_key, 'prior_attempt_id': first.id, 'prior_remote_outcome': 'completed',
            'actor': 'owner', 'reason': 'temporary mock ledger test'})
        before = tuple(ledger.records)
        invoke(0, 'pending_owner_approval', budget='2')
        ledger, added = appended(before)
        attempts = [r for r in added if r.kind == 'execution_attempt']
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].data['dispatch_authorization_id'], authorization.id)
        self.assertEqual(dispatches_consumed(ledger, task_key), 2)
        second = next(r for r in added if r.kind == 'approval')
        Ripley(ledger).decide_approval(second.id, 'owner', 'approved', 'dry-run fixture')
        before = tuple(ledger.records)
        invoke(2, 'second paid dispatch requires owner', budget='2')
        _, added = appended(before)
        self.assertFalse(added)

        exhausted_path = root / 'exhausted.sqlite'
        exhausted = SQLiteLedger(exhausted_path)
        bare = exhausted.add('execution_attempt', {
            'task_id': 'unresolved-mock', 'worker': 'anthropic-worker', 'transport_mode': 'mock'})
        invoke(2, 'pilot dispatch budget exhausted', database=exhausted_path)
        original, refusal = SQLiteLedger(exhausted_path).records.values()
        self.assertEqual(original.id, bare.id)
        self.assertEqual(refusal.kind, 'pilot_budget_exhausted')
        self.assertEqual(dict(refusal.data), {'budget': 1, 'consumed': 1, 'transport_mode': 'mock'})

    def test_p6d_02_runner_mock_dry_run(self):
        with self.subTest(packet='existing synthetic Phase 6 control'), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet, output = single_capture_fixture()
            packet_file, output_file = root / 'synthetic.json', root / 'synthetic.expected.json'
            packet_file.write_text(json.dumps(packet), encoding='utf-8')
            output_file.write_text(json.dumps(output), encoding='utf-8')
            self.exercise_runner(packet_file, output_file, root)
        with self.subTest(packet='owner frozen report'), tempfile.TemporaryDirectory() as tmp:
            path = self.frozen_packet()
            self.exercise_runner(path, path.with_suffix('.expected.json'), Path(tmp))

    def test_p6d_03_preconditions_are_pure(self):
        mock = {'RIPLEY_PROVIDER_TRANSPORT': 'mock', 'RIPLEY_ENABLE_TEST_WORKERS': '1',
                'RIPLEY_MOCK_PROVIDER_OUTPUT_FILE': 'fixture.json'}
        live = {'RIPLEY_PROVIDER_TRANSPORT': 'live', 'RIPLEY_LIVE_DISPATCH': '1',
                'RIPLEY_PILOT_DISPATCH_BUDGET': '1'}
        cases = [
            ({}, None, 'RIPLEY_PROVIDER_TRANSPORT'),
            ({'RIPLEY_PROVIDER_TRANSPORT': 'mock'}, None, 'RIPLEY_ENABLE_TEST_WORKERS'),
            ({**mock, 'RIPLEY_MOCK_PROVIDER_OUTPUT_FILE': ''}, None, 'RIPLEY_MOCK_PROVIDER_OUTPUT_FILE'),
            (mock, None, None),
            ({'RIPLEY_PROVIDER_TRANSPORT': 'live'}, None, 'RIPLEY_LIVE_DISPATCH'),
            ({**live, 'RIPLEY_ENABLE_TEST_WORKERS': ''}, 'file', 'RIPLEY_ENABLE_TEST_WORKERS'),
            (live, None, '--authorization'), (live, 'file', None)]
        for budget in ('', '0', '26', 'invalid'):
            cases.append(({**live, 'RIPLEY_PILOT_DISPATCH_BUDGET': budget}, 'file', 'BUDGET'))
        for env, path, expected in cases:
            with self.subTest(env=env, path=path):
                before = env.copy()
                refusal = preconditions(env, path)
                if expected is None:
                    self.assertIsNone(refusal)
                else:
                    self.assertIn(expected, refusal)
                self.assertEqual(env, before)
