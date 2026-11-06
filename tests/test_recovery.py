"""ADR-008 acceptance; deterministic clocks, sequential partial-state fixtures."""
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ripley.core import (IndependentValidator, Ledger, MockWorker, Ripley,
                         canonical_json, content_hash)
from ripley.storage import SQLiteLedger
from ripley.synthetic import InventoryAdapter


class Clock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class NoPolicyAdapter:
    domain_id = InventoryAdapter.domain_id
    version = InventoryAdapter.version
    expected_output = InventoryAdapter.expected_output
    predict = InventoryAdapter.predict
    snapshot_metadata = InventoryAdapter.snapshot_metadata


class SlowWorker(MockWorker):
    def __init__(self, clock, seconds=2):
        self.clock, self.seconds = clock, seconds

    def produce(self, task, snapshot, adapter):
        self.clock.advance(self.seconds)
        return super().produce(task, snapshot, adapter)


class BadThenGood(MockWorker):
    def __init__(self):
        self.calls = 0

    def produce(self, task, snapshot, adapter):
        self.calls += 1
        return {} if self.calls == 1 else super().produce(task, snapshot, adapter)


class RecoveryFixtures:
    def setUp(self):
        self.ledger = Ledger()
        self.adapter = InventoryAdapter()
        self.inputs = {'stock': 10, 'demand': 8, 'threshold': 5}
        self.clock = Clock()

    def records(self, kind, task_id=None):
        return [r for r in self.ledger.records.values() if r.kind == kind
                and (task_id is None or r.data.get('task_id') == task_id)]

    def engine(self, **kwargs):
        return Ripley(ledger=self.ledger, clock=self.clock, **kwargs)

    def partial(self, policy='safe', ceiling='no external calls', attempt=True,
                deadline=None, correction=False, state='running'):
        snapshot = self.ledger.add('snapshot', {'domain_id': self.adapter.domain_id,
            'domain_version': self.adapter.version, 'inputs': self.inputs,
            'observed_at': self.clock().isoformat(), 'sources': ['original-observation'],
            'data_quality': 'fixture'})
        data = {'domain_id': self.adapter.domain_id, 'domain_version': self.adapter.version,
            'task_type': 'predict', 'task_key': content_hash({'domain_id': self.adapter.domain_id,
                'domain_version': self.adapter.version, 'task_type': 'predict', 'inputs': self.inputs}),
            'input_snapshot_id': snapshot.id, 'resource_ceiling': ceiling, 'state': 'submitted',
            'previous_task_id': None, 'recovers_task_id': None,
            'allowed_workers': ('mock-worker',)}
        if policy is not None:
            data['replay_policy'] = policy
        task = self.ledger.add('task', data)
        if state == 'submitted':
            return task, None, snapshot
        self.ledger.transition(task.id, 'submitted', 'running', 'ripley', 'fixture start')
        execution = None
        if attempt:
            execution = self.ledger.add('execution_attempt', {'task_id': task.id,
                'worker': 'mock-worker', 'attempt_number': 1, 'deadline_at': deadline,
                'replays_attempt_id': None})
        if correction:
            result = self.ledger.add('result', {'task_id': task.id, 'attempt_id': execution.id,
                'input_snapshot_id': snapshot.id, 'output': {}})
            finding = IndependentValidator().validate(result, self.adapter)
            validation = self.ledger.add('validation', finding)
            review = self.ledger.add('review', {'result_id': result.id,
                'validation_id': validation.id, 'reviewer': 'ripley-review-policy',
                'decision': 'correction_required', 'reason': 'invalid output structure'})
            self.ledger.add('correction_request', {'task_id': task.id,
                'rejected_result_id': result.id, 'rejected_result_hash': result.content_hash,
                'review_id': review.id, 'reviewer': review.data['reviewer'],
                'reason': 'invalid output structure'})
        if state == 'validated':
            self.ledger.transition(task.id, 'running', 'validated', 'ripley', 'fixture validation')
        return task, execution, snapshot

    def interrupt(self, **kwargs):
        task, attempt, snapshot = self.partial(**kwargs)
        if isinstance(self.ledger, SQLiteLedger):
            # Each operation closes its connection; construct a new ledger to reopen.
            self.ledger = SQLiteLedger(self.ledger._path)
        else:
            # Memory has no restart operation: append the equivalent failure fixture.
            self.ledger.add('execution_failure', {'task_id': task.id, 'stage': 'interrupted',
                'attempt_id': attempt.id if attempt else None, 'message': 'interrupted_by_restart'})
            self.ledger.transition(task.id, 'running', 'blocked', 'ripley', 'interrupted_by_restart')
        return task, attempt, snapshot

    def recover(self, task, **kwargs):
        return self.engine().recover(task.id, 'owner', 'explicit test replay',
                                     kwargs.pop('adapter', self.adapter), **kwargs)

    def unchanged_rejection(self, callback, error=ValueError, message=None):
        before = dict(self.ledger.records)
        with self.assertRaises(error) as raised:
            callback()
        if message:
            self.assertEqual(str(raised.exception), message)
        self.assertEqual(dict(self.ledger.records), before)

    @staticmethod
    def record_bytes(record):
        return canonical_json({'id': record.id, 'kind': record.kind, 'at': record.at,
            'data': record.data, 'supersedes': record.supersedes, 'content_hash': record.content_hash})


class RecoveryContract(RecoveryFixtures):
    def test_p4_01_unknown_policy(self):
        adapter = NoPolicyAdapter()
        normal = self.engine().run(adapter, self.inputs)
        self.assertEqual(normal['task'].data['replay_policy'], 'unknown')
        self.assertIsNone(normal['task'].data['recovers_task_id'])
        self.assertIsNone(normal['attempt'].data['replays_attempt_id'])
        self.assertIsNone(normal['attempt'].data['deadline_at'])
        self.assertIsNone(normal['authorization'])
        for policy in ('unknown', None):
            with self.subTest(policy=policy):
                task, _, _ = self.interrupt(policy=policy)
                self.unchanged_rejection(lambda: self.recover(task, adapter=adapter))
        adapter.replay_policy = 'invalid-policy'
        other = self.engine().run(adapter, {**self.inputs, 'stock': 11})
        self.assertEqual(other['task'].data['replay_policy'], 'unknown')

    def test_p4_02_no_policy(self):
        self.adapter.replay_policy = 'no'
        normal = self.engine().run(self.adapter, self.inputs)
        self.assertEqual(normal['task'].data['replay_policy'], 'no')
        task, _, _ = self.interrupt(policy='no')
        self.unchanged_rejection(lambda: self.recover(task))

    def test_p4_03_external_resource_ceiling(self):
        task, _, _ = self.interrupt(ceiling='external calls allowed')
        self.unchanged_rejection(lambda: self.recover(task))

    def test_p4_04_recovery_lineage_and_gates(self):
        task, attempt, _ = self.interrupt()
        engine = self.engine()
        self.unchanged_rejection(lambda: engine.recover('missing', 'owner', 'reason', self.adapter))
        self.unchanged_rejection(lambda: engine.recover(attempt.id, 'owner', 'reason', self.adapter))
        for attribute, wrong in (('domain_id', 'different-domain'), ('version', 'different-version')):
            with patch.object(self.adapter, attribute, wrong):
                self.unchanged_rejection(lambda: self.recover(task))
        self.unchanged_rejection(lambda: self.recover(task, allowed_workers=()), PermissionError)
        worker = MockWorker()
        worker.identity = engine.validator.identity
        self.unchanged_rejection(lambda: self.recover(task, worker=worker,
            allowed_workers=(worker.identity,)), PermissionError)
        for actor, reason in (('', 'reason'), (None, 'reason'), ('owner', '  '), ('owner', None)):
            self.unchanged_rejection(lambda: engine.recover(task.id, actor, reason, self.adapter))
        for budget in (-1, True, 1.5):
            self.unchanged_rejection(lambda: self.recover(task, correction_budget=budget))
        for timeout in (0, -1, True, '1', float('nan'), float('inf')):
            with patch.object(self.adapter, 'timeout_seconds', timeout, create=True):
                self.unchanged_rejection(lambda: self.recover(task))
        preserved = {r.id: self.record_bytes(r) for r in self.ledger.records.values()}
        run = self.recover(task)
        auth = run['authorization']
        self.assertEqual(dict(auth.data), {'blocked_task_id': task.id,
            'interrupted_attempt_id': attempt.id, 'actor': 'owner', 'reason': 'explicit test replay',
            'replay_policy_cited': 'safe', 'resource_ceiling_cited': 'no external calls'})
        self.assertEqual(run['task'].data['previous_task_id'], task.id)
        self.assertEqual(run['task'].data['recovers_task_id'], task.id)
        self.assertEqual(run['attempt'].data['replays_attempt_id'], attempt.id)
        self.assertEqual(self.ledger.task_state(task.id), 'blocked')
        for rid, raw in preserved.items():
            self.assertEqual(self.record_bytes(self.ledger.records[rid]), raw)
        self.unchanged_rejection(lambda: self.recover(run['task']))
        # ADR-008 explicitly permits recovery when no attempt existed yet.
        before_attempt, _, _ = self.interrupt(attempt=False)
        recovered = self.recover(before_attempt)
        self.assertIsNone(recovered['authorization'].data['interrupted_attempt_id'])
        self.assertIsNone(recovered['attempt'].data['replays_attempt_id'])
        self.assertEqual(recovered['task'].data['recovers_task_id'], before_attempt.id)

    def test_p4_05_same_observation(self):
        task, _, original = self.interrupt()
        with patch.object(self.adapter, 'snapshot_metadata',
                          side_effect=lambda inputs: self.fail('observation repeated')):
            run = self.recover(task)
        self.assertEqual(run['outcome'], 'pending_owner_approval')
        self.assertNotEqual(run['snapshot'].id, original.id)
        for field in ('inputs', 'observed_at', 'sources', 'data_quality', 'domain_version'):
            self.assertEqual(run['snapshot'].data[field], original.data[field])
        self.assertEqual(run['snapshot'].data['replays_snapshot_id'], original.id)
        self.assertEqual(run['approval'].data['status'], 'pending_owner_approval')

    def test_p4_06_ineligible_failures(self):
        class FailedWorker(MockWorker):
            def produce(self, task, snapshot, adapter):
                raise RuntimeError('worker failed')
        class FailedValidator(IndependentValidator):
            def validate(self, result, adapter):
                raise RuntimeError('validator failed')
        class BadWorker(MockWorker):
            def produce(self, task, snapshot, adapter):
                return {}
        for engine, worker in ((self.engine(), FailedWorker()),
                               (self.engine(validator=FailedValidator()), MockWorker()),
                               (self.engine(), BadWorker())):
            run = engine.run(self.adapter, self.inputs, worker=worker, correction_budget=0)
            self.assertEqual(self.ledger.task_state(run['task'].id), 'blocked')
            self.unchanged_rejection(lambda: self.recover(run['task']),
                                    message='recovery not eligible for this failure')
        # An eligible-looking later failure cannot override exhaustion evidence.
        task = run['task']
        self.ledger.add('execution_failure', {'task_id': task.id, 'stage': 'interrupted'})
        self.unchanged_rejection(lambda: self.recover(task),
                                message='recovery not eligible for this failure')

    def test_p4_07_recovery_budget(self):
        task, _, _ = self.interrupt()
        self.adapter.timeout_seconds = 1
        second = self.recover(task, worker=SlowWorker(self.clock))
        self.assertEqual(second['outcome'], 'blocked_timeout')
        before = len(self.ledger.records)
        with self.assertRaisesRegex(ValueError, '^recovery budget exhausted$'):
            self.recover(second['task'])
        self.assertEqual(len(self.ledger.records), before + 1)
        self.assertEqual(len(self.records('task')), 2)
        self.assertEqual(dict(self.records('recovery_budget_exhaustion')[-1].data),
            {'task_id': second['task'].id, 'lineage_root_id': task.id, 'budget': 1, 'consumed': 1})
        # Repeating a request on A also cannot create a sibling replay.
        before = len(self.ledger.records)
        with self.assertRaisesRegex(ValueError, 'recovery budget exhausted'):
            self.recover(task)
        self.assertEqual(len(self.ledger.records), before + 1)
        self.assertEqual(len(self.records('task')), 2)

    def test_p4_08_independent_budgets(self):
        task, original_attempt, _ = self.interrupt(correction=True)
        worker = BadThenGood()
        run = self.recover(task, worker=worker, correction_budget=1)
        self.assertEqual(run['outcome'], 'pending_owner_approval')
        self.assertEqual(worker.calls, 2)
        self.assertEqual(len(run['corrections']), 1)
        attempts = self.records('execution_attempt', run['task'].id)
        self.assertEqual([r.data['attempt_number'] for r in attempts], [1, 2])
        self.assertEqual(attempts[0].data['replays_attempt_id'], original_attempt.id)
        self.assertIsNone(attempts[1].data['replays_attempt_id'])
        self.assertEqual(len(self.records('recovery_authorization')), 1)
        self.assertEqual(len(self.records('correction_request', task.id)), 1)
        self.assertFalse(self.records('recovery_budget_exhaustion'))

    def test_p4_09_post_hoc_timeout(self):
        self.adapter.timeout_seconds = 1
        engine = self.engine()
        start = self.clock()
        run = engine.run(self.adapter, self.inputs, worker=SlowWorker(self.clock))
        self.assertEqual(run['outcome'], 'blocked_timeout')
        self.assertEqual(run['result'].data['output'], self.adapter.predict(self.inputs))
        self.assertEqual(run['failure'].data['stage'], 'timeout')
        self.assertEqual(run['failure'].data['attempt_id'], run['attempt'].id)
        self.assertEqual(run['attempt'].data['deadline_at'], (start + timedelta(seconds=1)).isoformat())
        self.assertEqual(run['failure'].data['deadline_at'], run['attempt'].data['deadline_at'])
        self.assertEqual(run['failure'].data['completed_at'], self.clock().isoformat())
        self.assertEqual(self.ledger.task_state(run['task'].id), 'blocked')
        self.assertEqual(self.records('task_transition')[-1].data['reason'], 'deadline_exceeded')
        self.assertFalse(self.records('validation'))
        self.assertFalse(self.records('review'))
        self.assertFalse(self.records('correction_request'))
        self.assertIsNone(run['validation'])
        self.assertIsNone(run['review'])
        self.assertIsNone(run['authorization'])
        for field in ('results', 'validations', 'reviews', 'corrections'):
            self.assertIsInstance(run[field], tuple)
        self.assertEqual(run['corrections'], ())
        # Strictly greater: finishing at exactly the deadline succeeds.
        on_time = engine.run(self.adapter, self.inputs, worker=SlowWorker(self.clock, 1))
        self.assertEqual(on_time['outcome'], 'pending_owner_approval')
        self.assertEqual(set(run), set(on_time))
        duplicate = engine.run(self.adapter, self.inputs)
        self.assertEqual(set(run), set(duplicate))

    def test_p4_11_timeout_replay_policy(self):
        self.adapter.timeout_seconds = 1
        for policy in ('safe', 'no', 'unknown'):
            with self.subTest(policy=policy):
                self.adapter.replay_policy = policy
                # Distinct inputs avoid an active previously recovered Task.
                inputs = {**self.inputs, 'stock': 10 + len(self.records('task'))}
                run = self.engine().run(self.adapter, inputs, worker=SlowWorker(self.clock))
                self.assertEqual(run['outcome'], 'blocked_timeout')
                if policy == 'safe':
                    recovered = self.recover(run['task'])
                    self.assertEqual(recovered['outcome'], 'pending_owner_approval')
                    self.assertIsNotNone(recovered['authorization'])
                    self.assertEqual(set(recovered), set(run))
                else:
                    self.unchanged_rejection(lambda: self.recover(run['task']))

    def test_p4_13_existing_regression_suites_unchanged(self):
        # Discovery runs these same 73 cases alongside this acceptance suite.
        import test_skeleton
        import test_durable
        loader = unittest.TestLoader()
        self.assertEqual(loader.loadTestsFromModule(test_skeleton).countTestCases(), 62)
        self.assertEqual(loader.loadTestsFromModule(test_durable).countTestCases(), 11)
        expected = {
            'test_skeleton.py': '631675940c3ca16738eceaf0c7c35d38227aeccdc229d682b47f599635b0c0ab',
            'test_durable.py': 'fa252b9806356b573762f7c03742c943ed92450e46f641832ceafc9b35e2bf9a',
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest(), digest)


class MemoryRecoveryTests(RecoveryContract, unittest.TestCase):
    pass


class SQLiteFixture:
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        paths = iter(range(100))
        original_ripley = Ripley

        class TestLedger(SQLiteLedger):
            def __init__(self):
                super().__init__(Path(directory.name) / f'ledger-{next(paths)}.sqlite')

        class TestRipley(original_ripley):
            def __init__(self, ledger=None, validator=None, clock=None):
                super().__init__(ledger=ledger if ledger is not None else TestLedger(),
                                 validator=validator, clock=clock)

        # Shared bodies resolve Ledger/Ripley to SQLite-backed variants per test.
        replacements = patch.dict(globals(), {'Ledger': TestLedger, 'Ripley': TestRipley})
        replacements.start()
        self.addCleanup(replacements.stop)
        super().setUp()


class SQLiteRecoveryTests(SQLiteFixture, RecoveryContract, unittest.TestCase):
    pass


class SQLiteOnlyRecoveryTests(SQLiteFixture, RecoveryFixtures, unittest.TestCase):
    def test_p4_10_open_time_classification(self):
        past = (self.clock() - timedelta(seconds=1)).isoformat()
        future = (self.clock() + timedelta(seconds=1)).isoformat()
        cases = [('running', past, 'timeout'), ('running', None, 'interrupted'),
                 ('running', future, 'interrupted'), ('running', self.clock().isoformat(), 'interrupted'),
                 ('validated', past, 'interrupted'), ('submitted', past, 'interrupted')]
        tasks = []
        for state, deadline, expected in cases:
            task, _, _ = self.partial(state=state, deadline=deadline)
            tasks.append((task, expected))
        # Latest attempt controls the classification, not an older expired attempt.
        task, _, _ = self.partial(deadline=past)
        self.ledger.add('execution_attempt', {'task_id': task.id, 'deadline_at': None})
        tasks.append((task, 'interrupted'))
        clock = self.clock
        class OpenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return clock()
        path = self.ledger._path
        with patch('ripley.storage.datetime', OpenDateTime):
            self.ledger = SQLiteLedger(path)
        for task, expected in tasks:
            failure = self.records('execution_failure', task.id)[-1]
            self.assertEqual(failure.data['stage'], expected)
            self.assertEqual(failure.data['message'], 'deadline_exceeded_before_restart'
                             if expected == 'timeout' else 'interrupted_by_restart')
            self.assertEqual(self.ledger.task_state(task.id), 'blocked')
            self.assertEqual(self.records('task_transition', task.id)[-1].data['reason'],
                             'interrupted_by_restart')
        before = dict(self.ledger.records)
        self.ledger = SQLiteLedger(path)
        self.assertEqual(dict(self.ledger.records), before)

    def test_p4_12_recovery_survives_reopen(self):
        task, attempt, snapshot = self.interrupt()
        run = self.recover(task)
        before = dict(self.ledger.records)
        path = self.ledger._path
        self.ledger = SQLiteLedger(path)
        self.assertEqual(dict(self.ledger.records), before)
        self.assertEqual(self.ledger.task_for_key(task.data['task_key']).id, run['task'].id)
        self.assertEqual(self.ledger.task_state(task.id), 'blocked')
        self.assertEqual(self.ledger.task_state(run['task'].id), 'pending_owner_approval')
        self.assertEqual(self.ledger.records[run['task'].id].data['recovers_task_id'], task.id)
        self.assertEqual(self.ledger.records[run['attempt'].id].data['replays_attempt_id'], attempt.id)
        self.assertEqual(self.ledger.records[run['snapshot'].id].data['replays_snapshot_id'], snapshot.id)

    def test_p4_14_authorization_then_crash(self):
        task, attempt, _ = self.interrupt()
        self.ledger.add('recovery_authorization', {'blocked_task_id': task.id,
            'interrupted_attempt_id': attempt.id, 'actor': 'owner', 'reason': 'fixture crash',
            'replay_policy_cited': 'safe', 'resource_ceiling_cited': 'no external calls'})
        before = dict(self.ledger.records)
        self.ledger = SQLiteLedger(self.ledger._path)
        self.assertEqual(dict(self.ledger.records), before)
        self.assertEqual(self.ledger.task_state(task.id), 'blocked')
        self.assertFalse(any(r.data.get('recovers_task_id') == task.id for r in self.records('task')))
        count = len(self.ledger.records)
        with self.assertRaisesRegex(ValueError, '^recovery budget exhausted$'):
            self.recover(task)
        self.assertEqual(len(self.ledger.records), count + 1)
        self.assertEqual(len(self.records('task')), 1)
        self.assertEqual(dict(self.records('recovery_budget_exhaustion')[0].data),
            {'task_id': task.id, 'lineage_root_id': task.id, 'budget': 1, 'consumed': 1})
        self.assertEqual(self.ledger.records[task.id], task)


if __name__ == '__main__':
    unittest.main()
