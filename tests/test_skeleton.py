import unittest
from ripley.core import Ripley, MockWorker
from ripley.synthetic import InventoryAdapter

class SkeletonTests(unittest.TestCase):
    def setUp(self):
        self.engine = Ripley()
        self.inputs = {'stock': 10, 'demand': 8, 'threshold': 5}
    def test_end_to_end(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        self.assertEqual(len(records), 7)
        self.assertTrue(records['validation'].data['passed'])
        self.assertTrue(records['result'].data['output']['reorder'])
        self.assertEqual(records['approval'].data['status'], 'pending_owner_approval')
    def test_snapshot_frozen(self):
        records = self.engine.run(InventoryAdapter(), self.inputs)
        self.inputs['stock'] = 999
        self.assertEqual(records['snapshot'].data['inputs']['stock'], 10)
        with self.assertRaises(TypeError):
            records['snapshot'].data['inputs']['stock'] = 999
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
    def test_bad_output_fails(self):
        class BadWorker(MockWorker):
            def produce(self, task, snapshot, adapter):
                return {'wrong': True}
        records = self.engine.run(InventoryAdapter(), self.inputs, worker=BadWorker())
        self.assertFalse(records['validation'].data['passed'])
        self.assertEqual(records['review'].data['decision'], 'correction_required')

if __name__ == '__main__':
    unittest.main()
