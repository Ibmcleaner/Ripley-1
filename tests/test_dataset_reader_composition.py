"""DR-01 through DR-06: composed dataset-to-reader behavior without new runtime code."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import uuid

from ripley.capture import capture_file
from ripley.core import Ledger, Ripley, canonical_json, content_hash, freeze
from ripley.datasets import create_source_dataset, verify_source_dataset
from ripley.storage import SQLiteLedger


class _DatasetReaderCompositionCases:
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.approved = self.root / 'approved'
        self.approved.mkdir()
        self.store = self.root / 'store'
        self.database = self.root / 'ledger.sqlite'
        self.ledger = self._ledger()
        self.engine = Ripley(self.ledger, capture_store=self.store)
        self.first = self._capture('a.txt', b'Crates: 12\nPlace: Dock 4\n')
        self.second = self._capture('b.txt', b'Pallets: 4\n')
        self.references = [self._reference(self.first), self._reference(self.second)]
        self.canonical = sorted(self.references, key=lambda item: item['capture_id'])

    def _ledger(self):
        raise NotImplementedError

    def _reopen(self):
        pass

    def _capture(self, name, raw):
        source = self.approved / name
        source.write_bytes(raw)
        return capture_file(
            self.ledger, self.store, source,
            approved_root=self.approved,
            source_id=name.replace('.txt', ''),
            source_location='synthetic:' + name,
            supplied_by='fixture',
            content_type='text/plain; charset=utf-8')

    @staticmethod
    def _reference(receipt):
        return {'capture_id': receipt.id, 'receipt_hash': receipt.content_hash}

    @staticmethod
    def _plain(references):
        return [{'capture_id': member['capture_id'], 'receipt_hash': member['receipt_hash']}
                for member in references]

    def _member_hash(self, references):
        members = sorted(self._plain(references), key=lambda m: m['capture_id'])
        return hashlib.sha256(canonical_json({
            'contract_version': 1, 'members': members})).hexdigest()

    def _object_path(self, receipt):
        digest = receipt.data['sha256']
        return self.store / 'sha256' / digest[:2] / digest

    def _compose(self, dataset_id, fields=None):
        verification = verify_source_dataset(self.ledger, self.store, dataset_id)
        if verification['outcome'] != 'verified':
            return verification, None
        references = self._plain(verification['members'])
        run = self.engine.run_reader(
            ['Crates', 'Pallets'] if fields is None else fields, references)
        return verification, run

    def _dataset_run(self):
        dataset = create_source_dataset(self.ledger, self.store, self.references)
        verification, run = self._compose(dataset.id)
        self.assertEqual(verification['outcome'], 'verified')
        self.assertEqual(run['outcome'], 'awaiting_semantic_review')
        return dataset, run

    def test_dr_01_dataset_derived_governed_run(self):
        dataset = create_source_dataset(self.ledger, self.store, self.references)
        before = set(self.ledger.records)
        kinds_before = [record.kind for record in self.ledger.records.values()]
        verification, run = self._compose(dataset.id)
        self.assertEqual(verification['outcome'], 'verified')
        self.assertEqual(run['outcome'], 'awaiting_semantic_review')
        self.assertEqual(self.engine.reader_chain(run['reader_proposal'].id)['outcome'],
                         'verified')
        written = [record.kind for key, record in self.ledger.records.items()
                   if key not in before]
        permitted = {
            'snapshot', 'task', 'task_transition', 'capture_verification',
            'reasoning_attempt', 'execution_attempt', 'execution_request',
            'result', 'reasoning_attempt_close', 'proposal',
            'grounding_validation', 'reader_proposal'}
        self.assertTrue(set(written).issubset(permitted), written)
        self.assertNotIn('source_dataset', written)
        self.assertEqual(sum(kind == 'source_dataset' for kind in kinds_before),
                         sum(record.kind == 'source_dataset'
                             for record in self.ledger.records.values()))
        for kind in ('approval', 'semantic_review', 'reader_release'):
            self.assertNotIn(kind, (record.kind for record in self.ledger.records.values()))

    def test_dr_02_restart_and_membership_reconstruction(self):
        dataset, run = self._dataset_run()
        dataset_id = dataset.id
        task_id = run['task'].id
        snapshot_id = run['snapshot'].id
        self._reopen()
        dataset = self.ledger.records[dataset_id]
        snapshot = self.ledger.records[snapshot_id]
        task = self.ledger.records[task_id]
        dataset_members = self._plain(dataset.data['members'])
        snapshot_members = self._plain(snapshot.data['capture_references'])
        input_members = self._plain(snapshot.data['inputs']['sources'])
        self.assertEqual(snapshot_members, dataset_members)
        self.assertEqual(input_members, dataset_members)
        self.assertEqual(
            self._member_hash(snapshot.data['capture_references']),
            dataset.data['membership_sha256'])
        self.assertEqual(task.data['input_snapshot_id'], snapshot.id)
        self.assertEqual(self.ledger.task_state(task.id), 'awaiting_semantic_review')
        before = list(self.ledger.records)
        check = verify_source_dataset(self.ledger, self.store, dataset_id)
        self.assertEqual(check['outcome'], 'verified')
        self.assertEqual(list(self.ledger.records), before)

    def test_dr_03_preserve_reader_task_identity_and_deduplication(self):
        dataset, first = self._dataset_run()
        direct = self.engine.run_reader(
            ['Crates', 'Pallets'], list(reversed(self.references)))
        self.assertEqual(direct['outcome'], 'duplicate_of_existing_task')
        self.assertEqual(direct['task'].id, first['task'].id)
        verification, duplicate = self._compose(dataset.id)
        self.assertEqual(verification['outcome'], 'verified')
        self.assertEqual(duplicate['outcome'], 'duplicate_of_existing_task')
        self.assertEqual(duplicate['task'].id, first['task'].id)
        snapshot_sources = first['snapshot'].data['inputs']['sources']
        expected_key = content_hash({
            'domain_id': 'source-reading', 'domain_version': '1',
            'task_type': 'read',
            'inputs': freeze({
                'fields': ('Crates', 'Pallets'), 'sources': snapshot_sources})})
        self.assertEqual(first['task'].data['task_key'], expected_key)
        changed = self.engine.run_reader(['Place'], self.references)
        self.assertNotEqual(changed['task'].id, first['task'].id)
        self.assertEqual(
            self._member_hash(changed['snapshot'].data['capture_references']),
            dataset.data['membership_sha256'])

    def test_dr_04_unverified_dataset_starts_no_reader(self):
        dataset = create_source_dataset(self.ledger, self.store, self.references)

        def refused(identity, expected_reason):
            before = list(self.ledger.records)
            result, run = self._compose(identity)
            self.assertIsNone(run)
            self.assertEqual(result['outcome'], 'failed')
            self.assertEqual(result['reason'], expected_reason)
            self.assertEqual(list(self.ledger.records), before)

        refused(str(uuid.uuid4()), 'dataset_unavailable')
        malformed = self.ledger.add('source_dataset', {
            'contract_version': 1,
            'membership_sha256': 'a' * 64,
            'members': 'x'})
        refused(malformed.id, 'dataset_malformed')
        path = self._object_path(self.first)
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(b'not the originally captured bytes')
        refused(dataset.id, 'member_failed')
        path.unlink()
        refused(dataset.id, 'member_failed')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original)
        twin = self.ledger.add('source_dataset', dict(dataset.data))
        refused(dataset.id, 'dataset_ambiguous')
        refused(twin.id, 'dataset_ambiguous')

    def test_dr_05_core_blocks_capture_damage_after_preflight(self):
        dataset = create_source_dataset(self.ledger, self.store, self.references)
        verification = verify_source_dataset(self.ledger, self.store, dataset.id)
        self.assertEqual(verification['outcome'], 'verified')
        references = self._plain(verification['members'])
        path = self._object_path(self.first)
        path.chmod(0o600)
        path.write_bytes(b'changed after the pre-run check')
        run = self.engine.run_reader(['Crates', 'Pallets'], references)
        self.assertEqual(run['outcome'], 'blocked_capture_verification')
        self.assertEqual(self.ledger.task_state(run['task'].id), 'blocked')

    def test_dr_06_membership_equality_is_not_dataset_binding(self):
        self.assertFalse(
            any(record.kind == 'source_dataset'
                for record in self.ledger.records.values()))
        run = self.engine.run_reader(['Crates', 'Pallets'], self.references)
        self.assertEqual(run['outcome'], 'awaiting_semantic_review')
        dataset = create_source_dataset(self.ledger, self.store, self.references)
        self.assertEqual(
            self._member_hash(run['snapshot'].data['capture_references']),
            dataset.data['membership_sha256'])
        combined = b'\n'.join(
            canonical_json(record.data) for record in self.ledger.records.values()
            if record.kind != 'source_dataset').decode('utf-8')
        self.assertNotIn(dataset.id, combined)
        self.assertNotIn(dataset.data['membership_sha256'], combined)


class MemoryDatasetReaderCompositionTests(_DatasetReaderCompositionCases, unittest.TestCase):
    def _ledger(self):
        return Ledger()


class SQLiteDatasetReaderCompositionTests(_DatasetReaderCompositionCases, unittest.TestCase):
    def _ledger(self):
        return SQLiteLedger(self.database)

    def _reopen(self):
        self.ledger = SQLiteLedger(self.database)
        self.engine = Ripley(self.ledger, capture_store=self.store)
