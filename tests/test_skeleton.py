import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from ripley.storage import SQLiteLedger
from ripley.core import Ripley, MockWorker, IndependentValidator, content_hash, Ledger
from ripley.synthetic import InventoryAdapter


class SkeletonContract:
    def setUp(self):
        self.engine = Ripley()
        self.inputs = {'stock': 10, 'demand': 8, 'threshold': 5}

    def test_end_to_end(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        self.assertTrue(records['validation'].data['passed'])
        self.assertTrue(records['result'].data['output']['reorder'])
        self.assertEqual(records['approval'].data['status'], 'pending_owner_approval')
        self.assertEqual(self.engine.ledger.task_state(records['task'].id),
                         'pending_owner_approval')

    def test_snapshot_frozen(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        self.inputs['stock'] = 999
        self.assertEqual(records['snapshot'].data['inputs']['stock'], 10)
        with self.assertRaises(TypeError):
            records['snapshot'].data['inputs']['stock'] = 999

    def test_snapshot_metadata_from_adapter(self):
        class OtherAdapter(InventoryAdapter):
            domain_id = 'other-domain'
            def snapshot_metadata(self, inputs):
                return {'observed_at': '2026-01-01T00:00:00+00:00',
                        'sources': ['other-source'], 'data_quality': 'verified'}
        record = self.engine.run(OtherAdapter(), self.inputs)['snapshot']
        self.assertEqual(record.data['sources'], ('other-source',))
        self.assertEqual(record.data['data_quality'], 'verified')
        self.assertEqual(record.data['observed_at'], '2026-01-01T00:00:00+00:00')

    def test_worker_allowlist(self):
        with self.assertRaises(PermissionError):
            self.engine.run(InventoryAdapter(), self.inputs, allowed_workers=('other',))

    def test_self_validation_rejected(self):
        worker = MockWorker()
        worker.identity = 'independent-validator'
        with self.assertRaises(PermissionError):
            self.engine.run(InventoryAdapter(), self.inputs, worker=worker,
                            allowed_workers=(worker.identity,))

    def test_review_revision_preserves_original(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        revised = self.engine.revise_review(records['review'].id, 'reviewer-2', 'recheck', 'new evidence')
        self.assertEqual(revised.supersedes, records['review'].id)
        self.assertEqual(self.engine.ledger.records[records['review'].id].data['decision'], 'acceptable')

    def test_facts_not_rewritten(self):
        event = self.engine.ledger.add('event', {'observed': 'A'})
        with self.assertRaises(ValueError):
            self.engine.ledger.add('event', {'observed': 'B'}, supersedes=event.id)
        check = self.engine.ledger.add('validation', {'result_id': 'x', 'passed': False})
        with self.assertRaises(ValueError):
            self.engine.ledger.add('validation', {'result_id': 'x', 'passed': True},
                                   supersedes=check.id)

    def test_bad_output_fails(self):
        class BadWorker(MockWorker):
            def produce(self, task, snapshot, adapter):
                return {'wrong': True}
        records = self.engine.run(InventoryAdapter(), self.inputs,
                                  worker=BadWorker(), correction_budget=0)
        self.assertFalse(records['validation'].data['passed'])
        self.assertEqual(records['review'].data['decision'], 'correction_required')
        self.assertEqual(self.engine.ledger.task_state(records['task'].id), 'blocked')

    def test_transitions_are_append_only(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        transitions = [r for r in self.engine.ledger.records.values()
                       if r.kind == 'task_transition']
        self.assertEqual([r.data['to_state'] for r in transitions],
                         ['running', 'validated', 'pending_owner_approval'])
        self.assertEqual(transitions[1].data['preceding_transition_id'], transitions[0].id)
        self.assertEqual(transitions[0].data['to_state'], 'running')
        with self.assertRaises(ValueError):
            self.engine.ledger.transition(records['task'].id, 'running', 'blocked',
                                          'actor', 'stale')

    def test_worker_failure_is_recorded(self):
        class ExplodingWorker(MockWorker):
            def produce(self, task, snapshot, adapter):
                raise RuntimeError('intentional failure')
        records = self.engine.run(InventoryAdapter(), self.inputs, worker=ExplodingWorker())
        self.assertEqual(records['failure'].data['exception_type'], 'RuntimeError')
        self.assertEqual(records['failure'].data['attempt_id'], records['attempt'].id)
        self.assertEqual(self.engine.ledger.task_state(records['task'].id), 'blocked')
        self.assertFalse(any(r.kind == 'result' for r in self.engine.ledger.records.values()))

    def test_correction_creates_new_result_preserves_prior(self):
        class CorrectingWorker(MockWorker):
            def __init__(self):
                self.calls = 0
            def produce(self, task, snapshot, adapter):
                self.calls += 1
                return {'bad': 1} if self.calls == 1 else super().produce(task, snapshot, adapter)
        records = self.engine.run(InventoryAdapter(), self.inputs, worker=CorrectingWorker(),
                                  correction_budget=1)
        self.assertEqual(len(records['results']), 2)
        self.assertNotEqual(records['results'][0].id, records['results'][1].id)
        self.assertEqual(records['results'][0].data['output']['bad'], 1)
        self.assertEqual(records['corrections'][0].data['rejected_result_id'],
                         records['results'][0].id)
        self.assertTrue(records['validations'][1].data['passed'])

    def test_budget_exhaustion_blocks(self):
        class BadWorker(MockWorker):
            def produce(self, task, snapshot, adapter):
                return {'bad': True}
        records = self.engine.run(InventoryAdapter(), self.inputs,
                                  worker=BadWorker(), correction_budget=1)
        self.assertEqual(len(records['results']), 2)
        self.assertEqual(len(records['corrections']), 1)
        self.assertEqual(records['blocked'].kind, 'correction_budget_exhaustion')
        self.assertEqual(self.engine.ledger.task_state(records['task'].id), 'blocked')
        self.assertFalse(any(r.kind == 'approval' for r in self.engine.ledger.records.values()))

    def test_ledger_records_read_only(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        with self.assertRaises(TypeError):
            self.engine.ledger.records[records['task'].id] = records['result']
        with self.assertRaises(TypeError):
            del self.engine.ledger.records[records['task'].id]

    def test_evidence_traceability(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        evidence = records['evidence'].data
        for field, kind in [('task_id', 'task'), ('snapshot_id', 'snapshot'),
                            ('result_id', 'result'), ('validation_id', 'validation'),
                            ('review_id', 'review')]:
            self.assertEqual(self.engine.ledger.records[evidence[field]].kind, kind)
        self.assertEqual(records['result'].data['task_id'], evidence['task_id'])
        self.assertEqual(records['result'].data['input_snapshot_id'], evidence['snapshot_id'])
        self.assertEqual(records['validation'].data['result_id'], evidence['result_id'])
        self.assertEqual(records['review'].data['validation_id'], evidence['validation_id'])

    def test_validation_check_version_and_recheck(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        first = records['validation']
        self.assertEqual(first.data['validator_version'], '1')
        self.assertEqual(first.data['ruleset'], 'output-shape-v1')
        new = self.engine.ledger.add('validation', {'result_id': records['result'].id,
            'validator': 'independent-validator', 'validator_version': '2',
            'ruleset': 'output-shape-v2', 'passed': True})
        self.assertNotEqual(first.id, new.id)
        self.assertEqual(self.engine.ledger.records[first.id].data['validator_version'], '1')

    def test_validation_deterministic_and_bound_to_result(self):
        adapter = InventoryAdapter()
        result = self.engine.run(adapter, self.inputs)['result']
        validator = IndependentValidator()
        first = validator.validate(result, adapter)
        self.assertEqual(first, validator.validate(result, adapter))
        self.assertEqual(first['result_hash'], result.content_hash)
        class DifferentContract(InventoryAdapter):
            expected_output = {'reorder': int, 'projected_stock': int}
        changed = validator.validate(result, DifferentContract())
        self.assertFalse(changed['passed'])
        self.assertNotEqual(first['contract_hash'], changed['contract_hash'])
        old_check = self.engine.ledger.add('validation', first)
        new_check = self.engine.ledger.add('validation', changed)
        self.assertTrue(old_check.data['passed'])
        self.assertFalse(new_check.data['passed'])

    def test_hashes_cover_content_and_survive_input_mutation(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        evidence = records['evidence']
        for record_id, digest in evidence.data['hashes'].items():
            record = self.engine.ledger.records[record_id]
            self.assertEqual(digest, content_hash({'kind': record.kind,
                'data': record.data, 'supersedes': record.supersedes}))
        original = records['snapshot'].content_hash
        self.inputs['stock'] = 999
        self.assertEqual(original, records['snapshot'].content_hash)
        self.assertEqual(content_hash({'a': 1, 'b': 2}), content_hash({'b': 2, 'a': 1}))
        self.assertNotEqual(content_hash({'a': 1}), content_hash({'a': 2}))
        with self.assertRaises(TypeError):
            evidence.data['hashes']['new'] = 'forged'

    def test_correction_links_original_and_corrected_hashes(self):
        class CorrectingWorker(MockWorker):
            calls = 0
            def produce(self, task, snapshot, adapter):
                self.calls += 1
                return {'bad': 1} if self.calls == 1 else adapter.predict(snapshot.data['inputs'])
        records = self.engine.run(InventoryAdapter(), self.inputs, worker=CorrectingWorker())
        correction = next(r for r in self.engine.ledger.records.values() if r.kind == 'correction')
        first, second = records['results']
        self.assertEqual(correction.data['original_result_hash'], first.content_hash)
        self.assertEqual(correction.data['corrected_result_hash'], second.content_hash)
        self.assertEqual(correction.data['request_id'], records['corrections'][0].id)
        self.assertTrue(correction.data['reason'])
        self.assertTrue(correction.data['reviewer'])
        self.assertFalse(records['validations'][0].data['passed'])
        with self.assertRaises(TypeError):
            first.data['output']['bad'] = 2

    def test_validation_never_implicitly_approves(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        pending = records['approval']
        self.assertEqual(pending.data['status'], 'pending_owner_approval')
        with self.assertRaises(ValueError):
            self.engine.decide_approval(pending.id, 'mock-worker', 'approved', 'self approval')
        approved = self.engine.decide_approval(pending.id, 'owner', 'approved', 'reviewed evidence')
        self.assertEqual(approved.supersedes, pending.id)
        self.assertEqual(approved.data['result_hash'], records['result'].content_hash)
        self.assertEqual(pending.data['status'], 'pending_owner_approval')
        self.assertEqual(self.engine.ledger.task_state(records['task'].id), 'approved')
        with self.assertRaises(ValueError):
            self.engine.decide_approval(pending.id, 'owner', 'approved', 'repeat')

    def test_owner_rejection_is_separate_record(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        decision = self.engine.decide_approval(records['approval'].id,
                                              'owner', 'rejected', 'insufficient evidence')
        self.assertEqual(decision.data['status'], 'rejected')
        self.assertEqual(self.engine.ledger.task_state(records['task'].id), 'rejected')
        self.assertTrue(records['validation'].data['passed'])

    def test_superseded_review_cannot_authorize_approval(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        self.engine.revise_review(records['review'].id, 'reviewer-2', 'recheck', 'new concern')
        with self.assertRaises(ValueError):
            self.engine.decide_approval(records['approval'].id, 'owner', 'approved', 'old evidence')
        self.assertEqual(self.engine.ledger.task_state(records['task'].id), 'pending_owner_approval')

    def test_mutable_custom_objects_and_nonfinite_values_rejected(self):
        for value in (set([1]), object(), float('nan')):
            with self.assertRaises((TypeError, ValueError)):
                self.engine.ledger.add('event', {'value': value})
        self.assertEqual(len(self.engine.ledger.records), 0)

    def test_validation_result_hash_mismatch_rejected(self):
        class WrongHash(IndependentValidator):
            def validate(self, result, adapter):
                finding = super().validate(result, adapter)
                finding['result_hash'] = 'wrong'
                return finding
        engine = Ripley(validator=WrongHash())
        records = engine.run(InventoryAdapter(), self.inputs)
        self.assertEqual(records['outcome'], 'blocked_validation_failure')
        self.assertEqual(records['failure'].data['exception_type'], 'ValueError')
        self.assertFalse(any(r.kind == 'approval' for r in engine.ledger.records.values()))

    def test_validator_exception_is_recorded(self):
        class RaisingValidator(IndependentValidator):
            def validate(self, result, adapter):
                raise RuntimeError('validator unavailable')
        engine = Ripley(validator=RaisingValidator())
        records = engine.run(InventoryAdapter(), self.inputs)
        self.assertEqual(records['outcome'], 'blocked_validation_failure')
        self.assertEqual(records['failure'].data['stage'], 'validation')
        self.assertEqual(records['failure'].data['attempt_id'], records['attempt'].id)
        self.assertEqual(records['failure'].data['exception_type'], 'RuntimeError')
        self.assertEqual(records['failure'].data['message'], 'validator unavailable')
        self.assertEqual(engine.ledger.task_state(records['task'].id), 'blocked')
        self.assertEqual(len(records['results']), 1)
        for name in ('validations', 'reviews', 'corrections'):
            self.assertEqual(records[name], ())
        transition = list(engine.ledger.records.values())[-1]
        self.assertEqual(transition.data['reason'], 'validation_failure')
        self.assertIsNone(records['approval'])

    def test_pending_duplicate_creates_only_submission_record(self):
        adapter = InventoryAdapter()
        first = self.engine.run(adapter, self.inputs)
        count = len(self.engine.ledger.records)
        # Duplicate detection must precede timestamp-bearing snapshot metadata.
        adapter.snapshot_metadata = lambda inputs: self.fail('duplicate created snapshot metadata')
        second = self.engine.run(adapter, dict(reversed(list(self.inputs.items()))))
        self.assertEqual(second['outcome'], 'duplicate_of_existing_task')
        self.assertIs(second['task'], first['task'])
        self.assertEqual(len(self.engine.ledger.records), count + 1)
        self.assertEqual(sum(r.kind == 'task' for r in self.engine.ledger.records.values()), 1)
        self.assertEqual(sum(r.kind == 'snapshot' for r in self.engine.ledger.records.values()), 1)
        duplicate = list(self.engine.ledger.records.values())[-1]
        self.assertEqual(duplicate.kind, 'duplicate_submission')
        self.assertEqual(duplicate.data['task_id'], first['task'].id)
        self.assertIsNone(second['snapshot'])
        for name in ('results', 'validations', 'reviews', 'corrections'):
            self.assertEqual(second[name], ())
        self.assertEqual(set(first), set(second))

    def test_blocked_task_allows_new_task_and_attempt_lineage(self):
        class FailingWorker(MockWorker):
            def produce(self, task, snapshot, adapter):
                raise RuntimeError('blocked')
        first = self.engine.run(InventoryAdapter(), self.inputs, worker=FailingWorker())
        second = self.engine.run(InventoryAdapter(), self.inputs)
        self.assertEqual(first['outcome'], 'blocked_worker_failure')
        self.assertEqual(second['outcome'], 'pending_owner_approval')
        self.assertNotEqual(first['task'].id, second['task'].id)
        self.assertEqual(first['task'].data['task_key'], second['task'].data['task_key'])
        self.assertEqual(second['task'].data['previous_task_id'], first['task'].id)
        self.assertNotEqual(first['attempt'].id, second['attempt'].id)
        self.assertEqual(second['attempt'].data['task_id'], second['task'].id)
        self.assertEqual(self.engine.ledger.task_state(first['task'].id), 'blocked')
        self.assertEqual(sum(r.kind == 'task' for r in self.engine.ledger.records.values()), 2)
        third = self.engine.run(InventoryAdapter(), self.inputs)
        self.assertEqual(third['task'].id, second['task'].id)
        self.assertEqual(third['outcome'], 'duplicate_of_existing_task')

    def test_different_inputs_and_domain_versions_have_different_keys(self):
        first = self.engine.run(InventoryAdapter(), self.inputs)
        second = self.engine.run(InventoryAdapter(), {**self.inputs, 'stock': 11})
        class V2(InventoryAdapter):
            version = '2'
        third = self.engine.run(V2(), self.inputs)
        self.assertEqual(len({r['task'].data['task_key'] for r in (first, second, third)}), 3)
        self.assertEqual(first['task'].data['task_key'], content_hash({
            'domain_id': 'synthetic-inventory', 'domain_version': '1',
            'task_type': 'predict', 'inputs': self.inputs}))

    def test_nested_mapping_order_does_not_change_task_key(self):
        first = self.engine.run(InventoryAdapter(), {**self.inputs, 'extra': {'a': 1, 'b': 2}})
        second = self.engine.run(InventoryAdapter(), {'extra': {'b': 2, 'a': 1}, **self.inputs})
        self.assertEqual(second['outcome'], 'duplicate_of_existing_task')
        self.assertEqual(first['task'].data['task_key'], second['task'].data['task_key'])

    def test_approved_and_rejected_tasks_allow_resubmission(self):
        for decision in ('approved', 'rejected'):
            with self.subTest(decision=decision):
                engine = Ripley()
                first = engine.run(InventoryAdapter(), self.inputs)
                engine.decide_approval(first['approval'].id, 'owner', decision, 'test decision')
                second = engine.run(InventoryAdapter(), self.inputs)
                self.assertEqual(second['outcome'], 'pending_owner_approval')
                self.assertNotEqual(first['task'].id, second['task'].id)
                self.assertEqual(second['task'].data['previous_task_id'], first['task'].id)

    def test_all_run_returns_have_same_keys_and_tuple_collections(self):
        class BadWorker(MockWorker):
            def produce(self, task, snapshot, adapter):
                return {'bad': True}
        class FailedWorker(MockWorker):
            def produce(self, task, snapshot, adapter):
                raise RuntimeError('worker failed')
        class FailedValidator(IndependentValidator):
            def validate(self, result, adapter):
                raise RuntimeError('validation failed')
        pending = self.engine.run(InventoryAdapter(), self.inputs)
        cases = [pending, self.engine.run(InventoryAdapter(), self.inputs),
                 Ripley().run(InventoryAdapter(), self.inputs, worker=BadWorker()),
                 Ripley().run(InventoryAdapter(), self.inputs, worker=FailedWorker()),
                 Ripley(validator=FailedValidator()).run(InventoryAdapter(), self.inputs)]
        self.assertEqual({r['outcome'] for r in cases}, {'pending_owner_approval',
            'duplicate_of_existing_task', 'blocked_budget_exhausted',
            'blocked_worker_failure', 'blocked_validation_failure'})
        for result in cases:
            self.assertEqual(set(result), set(pending))
            for name in ('results', 'validations', 'reviews', 'corrections'):
                self.assertIsInstance(result[name], tuple)

    def test_review_creation_exception_preserves_completed_validation(self):
        class ReviewFailureLedger(Ledger):
            def add(self, kind, data, supersedes=None):
                if kind == 'review':
                    raise RuntimeError('review unavailable')
                return super().add(kind, data, supersedes)
        engine = Ripley(ledger=ReviewFailureLedger())
        records = engine.run(InventoryAdapter(), self.inputs)
        self.assertEqual(records['outcome'], 'blocked_validation_failure')
        self.assertEqual(records['failure'].data['stage'], 'validation')
        self.assertEqual(records['failure'].data['message'], 'review unavailable')
        self.assertEqual(len(records['validations']), 1)
        self.assertTrue(records['validations'][0].data['passed'])
        self.assertEqual(records['reviews'], ())
        self.assertEqual(engine.ledger.task_state(records['task'].id), 'blocked')


class MemorySkeletonTests(SkeletonContract, unittest.TestCase):
    pass


class SQLiteSkeletonTests(SkeletonContract, unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        paths = iter(range(100))
        original_ripley = Ripley

        class TestLedger(SQLiteLedger):
            def __init__(self):
                super().__init__(Path(directory.name) / f'ledger-{next(paths)}.sqlite')

        class TestRipley(original_ripley):
            def __init__(self, ledger=None, validator=None):
                super().__init__(ledger=ledger if ledger is not None else TestLedger(),
                                 validator=validator)

        replacements = patch.dict(globals(), {'Ledger': TestLedger, 'Ripley': TestRipley})
        replacements.start()
        self.addCleanup(replacements.stop)
        super().setUp()


if __name__ == '__main__':
    unittest.main()
