import unittest
from ripley.core import Ripley, MockWorker, IndependentValidator, content_hash
from ripley.synthetic import InventoryAdapter


class SkeletonTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
