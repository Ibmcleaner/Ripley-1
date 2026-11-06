from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import tokenize
import unittest

from ripley.core import Ledger, Ripley, canonical_json, content_hash
from ripley.storage import SQLiteLedger
from ripley.synthetic import InventoryAdapter


class DurableTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'ledger.sqlite'
        self.inputs = {'stock': 10, 'demand': 8, 'threshold': 5}

    def partial(self, stage):
        ledger = SQLiteLedger(self.path)
        key = content_hash({'domain_id': 'synthetic-inventory', 'domain_version': '1',
                            'task_type': 'predict', 'inputs': self.inputs})
        task = ledger.add('task', {'task_key': key, 'state': 'submitted'})
        if stage == 'submitted':
            return ledger, task, None
        ledger.transition(task.id, 'submitted', 'running', 'ripley', 'execution started')
        if stage == 'running':
            return ledger, task, None
        attempt = ledger.add('execution_attempt', {'task_id': task.id, 'attempt_number': 1})
        if stage == 'attempt':
            return ledger, task, attempt
        ledger.add('result', {'task_id': task.id, 'attempt_id': attempt.id, 'output': {'value': 1}})
        if stage == 'validated':
            ledger.transition(task.id, 'running', 'validated', 'ripley', 'test check')
        return ledger, task, attempt

    def failure(self, ledger, task):
        return [r for r in ledger.records.values()
                if r.kind == 'execution_failure' and r.data['task_id'] == task.id][-1]

    def test_p3_01_round_trip(self):
        ledger = SQLiteLedger(self.path)
        engine = Ripley(ledger=ledger)
        for stock, decision in ((10, None), (11, 'approved'), (12, 'rejected')):
            run = engine.run(InventoryAdapter(), {**self.inputs, 'stock': stock})
            if decision:
                engine.decide_approval(run['approval'].id, 'owner', decision, 'test')
        before = dict(ledger.records)
        states = {r.id: ledger.task_state(r.id) for r in before.values() if r.kind == 'task'}
        # Connections close after every operation; discard all ledger/engine references.
        del ledger, engine
        reopened = SQLiteLedger(self.path)
        self.assertEqual(before, dict(reopened.records))
        self.assertEqual(states, {t: reopened.task_state(t) for t in states})
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute('SELECT id, data, content_hash FROM records ORDER BY seq').fetchall()
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        self.assertEqual(tables, [('records',)])
        for rid, data, digest in rows:
            record = reopened.records[rid]
            raw = canonical_json({'kind': record.kind, 'data': record.data, 'supersedes': record.supersedes})
            self.assertEqual(data.encode('utf-8'), raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
        for task_id in states:
            prior = None
            for rid, _, _ in rows:
                record = reopened.records[rid]
                if record.kind == 'task_transition' and record.data['task_id'] == task_id:
                    self.assertEqual(record.data['preceding_transition_id'], prior)
                    prior = rid
        self.assertEqual(canonical_json({'b': 2, 'a': 1}), b'{"a":1,"b":2}')
        for backend in (Ledger(), reopened):
            with self.assertRaisesRegex(ValueError, 'task_key'):
                backend.add('task', {'state': 'submitted'})

    def test_p3_02_interrupted_before_attempt(self):
        ledger, task, _ = self.partial('running')
        del ledger
        reopened = SQLiteLedger(self.path)
        self.assertEqual(reopened.task_state(task.id), 'blocked')
        failure = self.failure(reopened, task)
        self.assertEqual(failure.data['stage'], 'interrupted')
        self.assertEqual(failure.data['message'], 'interrupted_by_restart')
        self.assertIsNone(failure.data['attempt_id'])
        self.assertEqual(list(reopened.records.values())[-1].data['reason'], 'interrupted_by_restart')

    def test_p3_03_interrupted_after_attempt(self):
        ledger, task, first = self.partial('attempt')
        latest = ledger.add('execution_attempt', {'task_id': task.id, 'attempt_number': 2})
        del ledger
        reopened = SQLiteLedger(self.path)
        self.assertEqual(reopened.task_state(task.id), 'blocked')
        self.assertEqual(self.failure(reopened, task).data['attempt_id'], latest.id)
        self.assertIn(first.id, reopened.records)

    def test_p3_04_interrupted_after_result(self):
        ledger, task, _ = self.partial('result')
        original = next(r for r in ledger.records.values() if r.kind == 'result')
        del ledger
        reopened = SQLiteLedger(self.path)
        self.assertEqual(reopened.task_state(task.id), 'blocked')
        self.assertEqual(reopened.records[original.id], original)
        self.assertFalse(any(r.kind == 'validation' for r in reopened.records.values()))

    def test_p3_05_pending_owner_untouched(self):
        ledger = SQLiteLedger(self.path)
        run = Ripley(ledger=ledger).run(InventoryAdapter(), self.inputs)
        before = dict(ledger.records)
        del ledger
        reopened = SQLiteLedger(self.path)
        self.assertEqual(dict(reopened.records), before)
        approval = Ripley(ledger=reopened).decide_approval(run['approval'].id, 'owner', 'approved', 'test')
        self.assertEqual(approval.data['status'], 'approved')
        self.assertEqual(reopened.task_state(run['task'].id), 'approved')

    def test_p3_06_second_open_appends_nothing(self):
        # Also exercise the two other interrupted state terms explicitly.
        for stage in ('submitted', 'running', 'validated'):
            with self.subTest(state=stage):
                self.path = Path(self.directory.name) / f'{stage}.sqlite'
                ledger, task, _ = self.partial(stage)
                del ledger
                reopened = SQLiteLedger(self.path)
                self.assertEqual(reopened.task_state(task.id), 'blocked')
                before = dict(reopened.records)
                del reopened
                again = SQLiteLedger(self.path)
                self.assertEqual(dict(again.records), before)

    def test_p3_07_idempotency_across_restart(self):
        ledger = SQLiteLedger(self.path)
        first = Ripley(ledger=ledger).run(InventoryAdapter(), self.inputs)
        del ledger
        reopened = SQLiteLedger(self.path)
        duplicate = Ripley(ledger=reopened).run(InventoryAdapter(), self.inputs)
        self.assertEqual(duplicate['outcome'], 'duplicate_of_existing_task')
        self.assertEqual(duplicate['task'].id, first['task'].id)
        self.path = Path(self.directory.name) / 'interrupted.sqlite'
        ledger, task, _ = self.partial('attempt')
        del ledger
        reopened = SQLiteLedger(self.path)
        run = Ripley(ledger=reopened).run(InventoryAdapter(), self.inputs)
        self.assertEqual(run['outcome'], 'pending_owner_approval')
        self.assertEqual(run['task'].data['previous_task_id'], task.id)
        self.assertNotEqual(run['task'].id, task.id)

    def test_p3_08_index_rebuilt_to_newest_task(self):
        ledger = SQLiteLedger(self.path)
        engine = Ripley(ledger=ledger)
        first = engine.run(InventoryAdapter(), self.inputs)
        engine.decide_approval(first['approval'].id, 'owner', 'rejected', 'test')
        second = engine.run(InventoryAdapter(), self.inputs)
        key = second['task'].data['task_key']
        del ledger, engine
        reopened = SQLiteLedger(self.path)
        self.assertEqual(reopened.task_for_key(key).id, second['task'].id)
        self.assertEqual(second['task'].data['previous_task_id'], first['task'].id)

    def test_p3_09_tamper_refuses_open_without_appends(self):
        ledger, task, _ = self.partial('running')
        del ledger
        with closing(sqlite3.connect(self.path)) as db:
            before = db.execute('SELECT COUNT(*) FROM records').fetchone()[0]
            with db:
                db.execute('UPDATE records SET data = ? WHERE id = ?', ('{}', task.id))
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            SQLiteLedger(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0], before)

    def test_p3_10_insert_only_source(self):
        import ripley.storage as storage
        source = Path(storage.__file__).read_text()
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        without_comments = ' '.join(t.string for t in tokens if t.type != tokenize.COMMENT)
        self.assertIsNone(re.search(r'UPDATE|DELETE|REPLACE', without_comments, re.I))
        self.assertEqual(len(re.findall(r'\bINSERT\b', without_comments, re.I)), 1)
        for module in Path(storage.__file__).parent.glob('*.py'):
            tokens = tokenize.generate_tokens(io.StringIO(module.read_text()).readline)
            sql_strings = ' '.join(t.string for t in tokens if t.type == tokenize.STRING)
            self.assertIsNone(re.search(r'\b(?:UPDATE|DELETE|REPLACE)\b', sql_strings, re.I))

    def test_p3_11_restart_edges_rejected_outside_open(self):
        for backend in (SQLiteLedger(self.path), Ledger()):
            for state in ('submitted', 'validated'):
                with self.subTest(backend=type(backend).__name__, state=state):
                    task = backend.add('task', {'task_key': state, 'state': 'submitted'})
                    if state == 'validated':
                        backend.transition(task.id, 'submitted', 'running', 'ripley', 'test')
                        backend.transition(task.id, 'running', 'validated', 'ripley', 'test')
                    count = len(backend.records)
                    with self.assertRaises(ValueError):
                        backend.transition(task.id, state, 'blocked', 'ripley', 'interrupted_by_restart')
                    self.assertEqual(backend.task_state(task.id), state)
                    self.assertEqual(len(backend.records), count)


if __name__ == '__main__':
    unittest.main()
