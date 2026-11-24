"""Source-dataset membership acceptance tests on both supported ledgers."""
import hashlib
import inspect
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

import ripley.datasets as datasets
from ripley.capture import capture_file
from ripley.core import Ledger, Ripley, canonical_json
from ripley.storage import SQLiteLedger
from ripley.synthetic import InventoryAdapter


class _SourceDatasetCases:
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.approved = self.root / 'approved'
        self.approved.mkdir()
        self.store = self.root / 'store'
        self.ledger = self._ledger()
        self.first = self._capture('first.txt', b'Crates: 12\n')
        self.second = self._capture('second.txt', b'Pallets: 4\n')
        self.refs = [self._ref(self.first), self._ref(self.second)]
        self.ordered = sorted(self.refs, key=lambda m: m['capture_id'])

    def _ledger(self):
        raise NotImplementedError

    def _reopen(self):
        pass

    def _capture(self, name, content):
        source = self.approved / name
        source.write_bytes(content)
        return capture_file(self.ledger, self.store, source,
                            approved_root=self.approved, source_id=name.replace('.txt', ''),
                            source_location='fixture:' + name, supplied_by='test',
                            content_type='text/plain; charset=utf-8')

    def _ref(self, record):
        return {'capture_id': record.id, 'receipt_hash': record.content_hash}

    def _object(self, receipt):
        digest = receipt.data['sha256']
        return self.store / 'sha256' / digest[:2] / digest

    def _ids(self):
        return list(self.ledger.records)

    def _membership(self, refs):
        members = sorted([dict(m) for m in refs], key=lambda m: m['capture_id'])
        return hashlib.sha256(canonical_json(
            {'contract_version': 1, 'members': members})).hexdigest()

    def _refused(self, reason, references, capture_id=None):
        before = self._ids()
        with self.assertRaises(datasets.DatasetError) as caught:
            datasets.create_source_dataset(self.ledger, self.store, references)
        self.assertEqual(str(caught.exception), reason)
        self.assertEqual(caught.exception.reason, reason)
        self.assertEqual(caught.exception.capture_id, capture_id)
        self.assertEqual(self._ids(), before)

    def _failed(self, dataset_id, reason):
        before = self._ids()
        response = datasets.verify_source_dataset(self.ledger, self.store, dataset_id)
        self.assertEqual(set(response), {'notice', 'outcome', 'reason', 'dataset_id',
                                         'membership_sha256', 'members'})
        self.assertEqual(response['notice'], datasets.NOTICE)
        self.assertEqual(response['outcome'], 'failed')
        self.assertEqual(response['reason'], reason)
        self.assertEqual(self._ids(), before)
        return response

    def test_sd_01_record_and_identity(self):
        before = self._ids()
        saved = {r.id: r.content_hash for r in (self.first, self.second)}
        dataset = datasets.create_source_dataset(self.ledger, self.store, self.refs)
        self.assertEqual(dataset.kind, 'source_dataset')
        self.assertIsNone(dataset.supersedes)
        self.assertEqual(set(dataset.data), {'contract_version', 'membership_sha256', 'members'})
        self.assertEqual(dataset.data['contract_version'], datasets.CONTRACT_VERSION)
        self.assertEqual(dataset.data['contract_version'], 1)
        self.assertEqual(dataset.data['members'], Ripley._canonical_capture_references(self.refs))
        self.assertEqual([m['capture_id'] for m in dataset.data['members']],
                         sorted(m['capture_id'] for m in self.refs))
        self.assertEqual(dataset.data['membership_sha256'], self._membership(self.refs))
        no_version = hashlib.sha256(canonical_json({'members': self.ordered})).hexdigest()
        self.assertNotEqual(dataset.data['membership_sha256'], no_version)
        self.assertNotEqual(dataset.data['membership_sha256'], dataset.id)
        self.assertNotEqual(dataset.data['membership_sha256'], dataset.content_hash)
        self.assertEqual(self._ids(), before + [dataset.id])
        self.assertEqual([r.kind for r in self.ledger.records.values()].count('source_dataset'), 1)
        for rid, digest in saved.items():
            self.assertEqual(self.ledger.records[rid].content_hash, digest)

    def test_sd_02_order_and_repeat(self):
        dataset = datasets.create_source_dataset(self.ledger, self.store, self.refs)
        self._reopen()
        before = self._ids()
        reverse = tuple({'receipt_hash': m['receipt_hash'], 'capture_id': m['capture_id']}
                        for m in reversed(self.refs))
        again = datasets.create_source_dataset(self.ledger, self.store, reverse)
        self.assertEqual((dataset.id, dataset.content_hash), (again.id, again.content_hash))
        self.assertEqual(before, self._ids())
        self.assertEqual(sum(r.kind == 'source_dataset' for r in self.ledger.records.values()), 1)

    def test_sd_03_membership_not_content(self):
        twin = self._capture('twin.txt', b'Crates: 12\n')
        self.assertEqual(self.first.data['sha256'], twin.data['sha256'])
        self.assertNotEqual(self.first.id, twin.id)
        twin_ref = self._ref(twin)
        sets = [self.refs, [self.refs[0]], [twin_ref, self.refs[1]],
                [self.refs[0], self.refs[1], twin_ref]]
        records = [datasets.create_source_dataset(self.ledger, self.store, refs)
                   for refs in sets]
        self.assertEqual(len({r.data['membership_sha256'] for r in records}), 4)
        self.assertEqual(len({r.id for r in records}), 4)
        self.assertEqual(records[2].data['membership_sha256'], self._membership(sets[2]))
        self.assertEqual(len(records[3].data['members']), 3)
        self.assertEqual(sum(r.kind == 'source_dataset' for r in self.ledger.records.values()), 4)

    def test_sd_04_call_and_member_refusals(self):
        for value in (None, 'text', {}, 7, iter(self.refs)):
            with self.subTest(value=str(value)):
                self._refused('invalid_call', value)
        for value in ([], ()):
            self._refused('empty_membership', value)
        seventeen = [{'capture_id': str(uuid.uuid4()), 'receipt_hash': '0' * 64}
                     for _ in range(17)]
        self._refused('too_many_members', seventeen)
        malformed = ['text', None, 7, [self.refs[0]['capture_id'], self.refs[0]['receipt_hash']],
                     {'capture_id': self.refs[0]['capture_id']},
                     {'receipt_hash': self.refs[0]['receipt_hash']},
                     {**self.refs[0], 'extra': 1},
                     {**self.refs[0], 'capture_id': 'not-uuid'},
                     {**self.refs[0], 'capture_id': 7},
                     {**self.refs[0], 'capture_id': self.refs[0]['capture_id'].upper()},
                     {**self.refs[0], 'receipt_hash': 'a' * 63},
                     {**self.refs[0], 'receipt_hash': 'A' * 64},
                     {**self.refs[0], 'receipt_hash': 7},
                     {**self.refs[0], 'receipt_hash': None}]
        for value in malformed:
            with self.subTest(value=str(value)):
                self._refused('malformed_member', [self.refs[1], value])
        self._refused('duplicate_member', [self.refs[0], self.refs[0]])
        self._refused('duplicate_member',
                      [self.refs[0], {**self.refs[0], 'receipt_hash': '0' * 64}])
        self.assertFalse(any(r.kind == 'source_dataset' for r in self.ledger.records.values()))

    def test_sd_05_all_members_and_bounded_verification(self):
        existing = self.refs[0]
        absent = {'capture_id': str(uuid.uuid4()), 'receipt_hash': '0' * 64}
        self._refused('receipt_missing', [existing, absent], absent['capture_id'])
        foreign = Ledger().add('capture', {'irrelevant': 'fixture'})
        foreign_ref = self._ref(foreign)
        self._refused('receipt_missing', [existing, foreign_ref], foreign.id)
        wrong = self.ledger.add('non_capture', {'example': 1})
        self._refused('receipt_wrong_kind', [existing, self._ref(wrong)], wrong.id)
        mismatch = {**self.refs[0], 'receipt_hash': self.refs[1]['receipt_hash']}
        self._refused('receipt_hash_mismatch', [mismatch, self.refs[1]], mismatch['capture_id'])
        first = self.ordered[0]
        for replacement in (RuntimeError('failed verification'), None):
            if replacement is None:
                with patch.object(datasets, '_verify_capture', return_value=('UNKNOWN', 'x')):
                    self._refused('verification_error', self.refs, first['capture_id'])
            else:
                with patch.object(datasets, '_verify_capture', side_effect=replacement):
                    self._refused('verification_error', self.refs, first['capture_id'])
        target = self.first
        path = self._object(target)
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(b'ALTERED DATA')
        self._refused('artifact_mismatched', self.refs, target.id)
        self._refused('artifact_mismatched', [self._ref(target)], target.id)
        path.unlink()
        self._refused('artifact_unavailable', self.refs, target.id)
        self._refused('artifact_unavailable', [self._ref(target)], target.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original)
        dataset = datasets.create_source_dataset(self.ledger, self.store, self.refs)
        self.assertEqual(len(dataset.data['members']), 2)

    def test_sd_06_reopen_and_read_only(self):
        dataset = datasets.create_source_dataset(self.ledger, self.store, self.refs)
        self._reopen()
        before = self._ids()
        result = datasets.verify_source_dataset(self.ledger, self.store, dataset.id)
        expected_members = [dict(m, reason='verified') for m in self.ordered]
        self.assertEqual(result, {'notice': datasets.NOTICE, 'outcome': 'verified',
                                  'reason': None, 'dataset_id': dataset.id,
                                  'membership_sha256': self._membership(self.refs),
                                  'members': expected_members})
        self.assertEqual(before, self._ids())
        record = self.ledger.records[dataset.id]
        self.assertEqual((record.content_hash, record.kind),
                         (dataset.content_hash, 'source_dataset'))
        self.assertEqual(datasets.NOTICE, 'A source dataset records which captured evidence belongs to a collection. A verified Source Dataset is an integrity result, not a trust, quality, approval, interpretation, availability-time, consent, or fitness-for-use result.')

    def test_sd_07_later_damage_and_repeat_reverification(self):
        dataset = datasets.create_source_dataset(self.ledger, self.store, self.refs)
        path = self._object(self.second)
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(b'BAD')
        self._reopen()
        failure = self._failed(dataset.id, 'member_failed')
        reasons = {m['capture_id']: m['reason'] for m in failure['members']}
        self.assertEqual(reasons, {self.first.id: 'verified',
                                   self.second.id: 'artifact_mismatched'})
        self.assertEqual(failure['membership_sha256'], dataset.data['membership_sha256'])
        self._refused('artifact_mismatched', self.refs, self.second.id)
        path.unlink()
        reasons = {m['capture_id']: m['reason']
                   for m in self._failed(dataset.id, 'member_failed')['members']}
        self.assertEqual(reasons[self.second.id], 'artifact_unavailable')
        path.write_bytes(original)
        self.assertEqual(datasets.verify_source_dataset(self.ledger, self.store, dataset.id)['outcome'],
                         'verified')

    def test_sd_08_malformed_stored_records_and_ambiguity(self):
        dataset = datasets.create_source_dataset(self.ledger, self.store, self.refs)
        good = {'contract_version': 1, 'membership_sha256': dataset.data['membership_sha256'],
                'members': [dict(m) for m in dataset.data['members']]}
        for value in (str(uuid.uuid4()), self.first.id, None, 7, (), [], {}):
            self._failed(value, 'dataset_unavailable')
        self.assertEqual(datasets.verify_source_dataset(self.ledger, self.store, dataset.id)['outcome'],
                         'verified')
        bad_data = [None, 7, 'text', [], [1, 2]]
        for key in good:
            bad_data.append({k: v for k, v in good.items() if k != key})
        bad_data += [{**good, 'extra': True},
                     {**good, 'contract_version': '1'},
                     {**good, 'membership_sha256': 7},
                     {**good, 'membership_sha256': None}]
        bad_members = ['text', None, 7, {}, [],
                       [good['members'][0], 'text'],
                       [good['members'][0], {'capture_id': self.second.id}],
                       [good['members'][0], {**good['members'][1], 'extra': 1}],
                       list(reversed(good['members'])),
                       [good['members'][0], good['members'][0]]]
        bad_data += [{**good, 'members': members} for members in bad_members]
        for data in bad_data:
            with self.subTest(data=str(data)):
                record = self.ledger.add('source_dataset', data)
                response = self._failed(record.id, 'dataset_malformed')
                self.assertIsNone(response['membership_sha256'])
                self.assertEqual(response['members'], [])
        for version in (2, 0):
            record = self.ledger.add('source_dataset', {**good, 'contract_version': version})
            self._failed(record.id, 'contract_unsupported')
        for bad in ({**good, 'membership_sha256': 'a' * 64},
                    {**good, 'members': [good['members'][0]]}):
            record = self.ledger.add('source_dataset', bad)
            self._failed(record.id, 'membership_hash_mismatch')
        self._failed(dataset.id, 'dataset_ambiguous')
        twin = self.ledger.add('source_dataset', good)
        self._reopen()
        self._failed(dataset.id, 'dataset_ambiguous')
        self._failed(twin.id, 'dataset_ambiguous')
        self._refused('dataset_ambiguous', self.refs)
        second_only = [self._ref(self.second)]
        pairs = [[['capture_id', self.second.id],
                  ['receipt_hash', self.second.content_hash]]]
        bad = self.ledger.add('source_dataset', {
            'contract_version': 1, 'membership_sha256': self._membership(second_only),
            'members': pairs})
        self._reopen()
        response = self._failed(bad.id, 'dataset_malformed')
        self.assertIsNone(response['membership_sha256'])
        self.assertEqual(response['members'], [])
        self._refused('dataset_ambiguous', second_only)
        first_only = [self._ref(self.first)]
        self.ledger.add('source_dataset', {
            'contract_version': 1, 'membership_sha256': self._membership(first_only),
            'members': first_only, 'extra': True})
        self._refused('dataset_ambiguous', first_only)

    def test_sd_09_failed_append_and_reopen(self):
        before = self._ids()
        owner = type(self.ledger)
        original = owner.add
        def broken(instance, kind, data, supersedes=None):
            if kind == 'source_dataset':
                raise RuntimeError('synthetic append failure')
            return original(instance, kind, data, supersedes)
        with patch.object(owner, 'add', new=broken):
            self._refused('ledger_write_failed', self.refs)
        self._reopen()
        self.assertEqual(self._ids(), before)
        dataset = datasets.create_source_dataset(self.ledger, self.store, self.refs)
        self.assertEqual(datasets.verify_source_dataset(self.ledger, self.store, dataset.id)['outcome'],
                         'verified')
        self.assertEqual(sum(r.kind == 'source_dataset' for r in self.ledger.records.values()), 1)

    def test_sd_10_no_authority_and_source_restrictions(self):
        import ripley.isolation
        import ripley.reasoning_envelope
        import ripley.grounding
        before = self._ids()
        with ExitStack() as stack:
            for name in ('ripley.isolation.observe_subprocess',
                         'ripley.reasoning_envelope.open_attempt',
                         'ripley.grounding.ground_proposal',
                         'ripley.core.Ripley.run',
                         'ripley.core.Ripley.run_reader',
                         'ripley.core.Ledger.transition',
                         'ripley.storage.SQLiteLedger.transition'):
                stack.enter_context(patch(name, side_effect=AssertionError(name)))
            dataset = datasets.create_source_dataset(self.ledger, self.store, self.refs)
            self.assertEqual(datasets.verify_source_dataset(
                self.ledger, self.store, dataset.id)['outcome'], 'verified')
        self.assertEqual(set(self._ids()) - set(before), {dataset.id})
        self.assertEqual(self.ledger.records[dataset.id].kind, 'source_dataset')
        forbidden_kinds = {'task', 'snapshot', 'task_transition', 'execution_attempt',
                           'reasoning_attempt', 'proposal', 'grounding_validation',
                           'semantic_review', 'reader_release', 'approval',
                           'capture_verification'}
        self.assertFalse(forbidden_kinds.intersection(r.kind for r in self.ledger.records.values()))
        source = inspect.getsource(datasets)
        banned = ('socket', 'subprocess', 'urllib', 'http', 'anthropic', 'providers',
                  'isolation', 'reasoning_envelope', 'grounding', 'semantic_review',
                  'transition', 'Ripley', 'datetime', 'time.')
        self.assertFalse([token for token in banned if token in source])
        self.assertEqual({name for name in vars(datasets) if not name.startswith('_')},
                         {'CONTRACT_VERSION', 'NOTICE', 'DatasetError',
                          'create_source_dataset', 'verify_source_dataset'})
        self.assertEqual(tuple(inspect.signature(datasets.create_source_dataset).parameters),
                         ('ledger', 'store_dir', 'references'))
        self.assertEqual(tuple(inspect.signature(datasets.verify_source_dataset).parameters),
                         ('ledger', 'store_dir', 'dataset_id'))

    def test_sd_11_snapshot_is_not_dataset(self):
        adapter = InventoryAdapter()
        engine = Ripley(self.ledger, capture_store=self.store)
        first = engine.run(adapter, {'stock': 9, 'demand': 2, 'threshold': 3},
                           capture_references=self.refs)
        second = engine.run(adapter, {'stock': 8, 'demand': 2, 'threshold': 3},
                            capture_references=self.refs)
        self.assertEqual(first['snapshot'].data['capture_references'],
                         second['snapshot'].data['capture_references'])
        self.assertNotEqual(first['snapshot'].content_hash, second['snapshot'].content_hash)
        self.assertNotEqual(first['snapshot'].id, second['snapshot'].id)
        watched = ('task', 'snapshot', 'approval')
        before = {kind: sum(r.kind == kind for r in self.ledger.records.values())
                  for kind in watched}
        dataset = datasets.create_source_dataset(self.ledger, self.store, self.refs)
        self.assertEqual(dataset.data['members'], first['snapshot'].data['capture_references'])
        self.assertEqual({kind: sum(r.kind == kind for r in self.ledger.records.values())
                          for kind in watched}, before)
        self.assertEqual(self.ledger.task_state(first['task'].id), 'pending_owner_approval')


class MemorySourceDatasetTests(_SourceDatasetCases, unittest.TestCase):
    def _ledger(self):
        return Ledger()


class SQLiteSourceDatasetTests(_SourceDatasetCases, unittest.TestCase):
    def _ledger(self):
        self.db = self.root / 'ledger.sqlite'
        return SQLiteLedger(self.db)

    def _reopen(self):
        self.ledger = SQLiteLedger(self.db)
