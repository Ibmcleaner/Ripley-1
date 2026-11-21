"""ADR-012: exact receipt linkage, execution gates and frozen provider pins."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from ripley.capture import capture_file
from ripley.core import Ledger, MockWorker, Ripley, canonical_json, content_hash
from ripley.storage import SQLiteLedger
from ripley.synthetic import InventoryAdapter


SDK_INSTALLED = importlib.util.find_spec('anthropic') is not None
LEGACY_SNAPSHOT_KEYS = {'domain_id', 'inputs', 'observed_at', 'sources',
                        'data_quality', 'domain_version'}
VERIFICATION_KEYS = {'task_id', 'snapshot_id', 'context', 'attempt_number',
                     'passed', 'observations'}
OBSERVATION_KEYS = {'capture_id', 'expected_receipt_hash', 'observed_receipt_hash',
                    'content_sha256', 'size_bytes', 'status', 'reason'}


class CountingWorker(MockWorker):
    def __init__(self, action=None):
        self.calls = 0
        self.action = action

    def produce(self, task, snapshot, adapter):
        self.calls += 1
        if self.action is not None:
            return self.action(self.calls, task, snapshot, adapter)
        return super().produce(task, snapshot, adapter)


class CaptureLinkTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / 'source.txt'
        self.raw = b'10 7 3\n'
        self.source.write_bytes(self.raw)
        self.store = self.root / 'objects'
        self.now = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        self.capture_number = 0
        self.ledger = Ledger()
        self.engine = Ripley(self.ledger, clock=lambda: self.now, capture_store=self.store)
        self.adapter = InventoryAdapter()
        self.inputs = {'stock': 10, 'demand': 7, 'threshold': 3}
        self.worker = CountingWorker()

    def take(self):
        self.capture_number += 1
        return capture_file(self.ledger, self.store, self.source,
            approved_root=self.root, source_id='inventory.fixture',
            source_location='fixture:inventory', supplied_by='test', content_type='text/plain',
            clock=lambda: self.now + timedelta(microseconds=self.capture_number))

    @staticmethod
    def reference(receipt):
        return {'capture_id': receipt.id, 'receipt_hash': receipt.content_hash}

    def object_path(self, receipt):
        digest = receipt.data['sha256']
        return self.store / 'sha256' / digest[:2] / digest

    def records(self, kind):
        return [r for r in self.ledger.records.values() if r.kind == kind]

    def run_linked(self, references, **kwargs):
        kwargs.setdefault('worker', self.worker)
        return self.engine.run(self.adapter, self.inputs,
                               capture_references=references, **kwargs)

    def failed(self, references, reason, status='UNAVAILABLE'):
        run = self.run_linked(references)
        self.assertEqual(run['outcome'], 'blocked_capture_verification')
        self.assertEqual(self.worker.calls, 0)
        self.assertEqual(self.records('execution_attempt'), [])
        self.assertEqual(self.records('evidence'), [])
        self.assertEqual(self.ledger.task_state(run['task'].id), 'blocked')
        verification = run['capture_verification']
        self.assertEqual(set(verification.data), VERIFICATION_KEYS)
        self.assertFalse(verification.data['passed'])
        self.assertEqual(verification.data['task_id'], run['task'].id)
        self.assertEqual(verification.data['snapshot_id'], run['snapshot'].id)
        self.assertEqual(verification.data['context'], 'execution')
        self.assertEqual(verification.data['attempt_number'], 1)
        for observation in verification.data['observations']:
            self.assertEqual(set(observation), OBSERVATION_KEYS)
            self.assertEqual(observation['reason'], reason)
            self.assertEqual(observation['status'], status)
        self.assertEqual(dict(run['failure'].data), {
            'task_id': run['task'].id, 'stage': 'capture_verification', 'attempt_id': None,
            'capture_verification_id': verification.id, 'message': 'capture evidence not verified'})
        order = list(self.ledger.records)
        self.assertLess(order.index(verification.id), order.index(run['failure'].id))
        self.assertEqual(self.records('task_transition')[-1].data['reason'], 'capture_verification')
        return run

    def timed_out(self, receipt):
        class TimedAdapter(InventoryAdapter):
            timeout_seconds = 1

        self.adapter = TimedAdapter()

        def late(call, task, snapshot, adapter):
            self.now += timedelta(seconds=2)
            return adapter.predict(snapshot.data['inputs'])

        run = self.run_linked([self.reference(receipt)], worker=CountingWorker(late))
        self.assertEqual(run['outcome'], 'blocked_timeout')
        return run

    def recover(self, run, **kwargs):
        kwargs.setdefault('worker', self.worker)
        return self.engine.recover(run['task'].id, 'owner', 'retry verified local evidence',
                                   self.adapter, **kwargs)

    @staticmethod
    def provider_inputs():
        path = Path('fixtures/nfl-availability/TB-at-CHI-2026-11-08.json')
        return json.loads(path.read_text('utf-8'))

    def test_cl_01_valid_reference(self):
        receipt = self.take()
        reference = self.reference(receipt)
        run = self.run_linked([reference])
        self.assertEqual(run['outcome'], 'pending_owner_approval')
        self.assertEqual(self.worker.calls, 1)
        self.assertEqual(run['snapshot'].data['capture_references'], (reference,))
        self.assertEqual(dict(run['snapshot'].data['inputs']), self.inputs)
        self.assertNotIn('capture_references', run['snapshot'].data['inputs'])
        verification = run['capture_verification']
        self.assertEqual(dict(verification.data), {
            'task_id': run['task'].id, 'snapshot_id': run['snapshot'].id,
            'context': 'execution', 'attempt_number': 1, 'passed': True,
            'observations': ({'capture_id': receipt.id,
                'expected_receipt_hash': receipt.content_hash,
                'observed_receipt_hash': receipt.content_hash,
                'content_sha256': receipt.data['sha256'], 'size_bytes': len(self.raw),
                'status': 'MATCHED', 'reason': 'verified'},)})
        order = list(self.ledger.records)
        self.assertLess(order.index(run['task'].id), order.index(verification.id))
        self.assertLess(order.index(verification.id), order.index(run['attempt'].id))
        reference['receipt_hash'] = '0' * 64
        self.assertEqual(run['snapshot'].data['capture_references'][0]['receipt_hash'],
                         receipt.content_hash)
        with self.assertRaises(TypeError):
            run['snapshot'].data['capture_references'][0]['receipt_hash'] = '0' * 64

    def test_cl_02_missing_receipt(self):
        references = [{'capture_id': str(uuid.UUID(int=i)), 'receipt_hash': '0' * 64}
                      for i in (1, 2)]
        run = self.failed(references, 'receipt_missing')
        self.assertEqual(len(run['capture_verification'].data['observations']), 2)
        for observation in run['capture_verification'].data['observations']:
            self.assertIsNone(observation['observed_receipt_hash'])
            self.assertIsNone(observation['content_sha256'])
            self.assertIsNone(observation['size_bytes'])

    def test_cl_03_wrong_record_kind(self):
        record = self.ledger.add('source_note', {'text': 'not a capture'})
        run = self.failed([self.reference(record)], 'receipt_wrong_kind')
        observation = run['capture_verification'].data['observations'][0]
        self.assertIsNone(observation['observed_receipt_hash'])
        self.assertIsNone(observation['content_sha256'])
        self.assertIsNone(observation['size_bytes'])

    def test_cl_04_wrong_receipt_hash(self):
        receipt = self.take()
        reference = {'capture_id': receipt.id, 'receipt_hash': '0' * 64}
        with patch('ripley.capture.verify_capture', side_effect=AssertionError('artifact read')) as verify:
            run = self.failed([reference], 'receipt_hash_mismatch', 'MISMATCHED')
        verify.assert_not_called()
        observation = run['capture_verification'].data['observations'][0]
        self.assertEqual(observation['observed_receipt_hash'], receipt.content_hash)
        self.assertIsNone(observation['content_sha256'])
        self.assertIsNone(observation['size_bytes'])

    def test_cl_05_artifact_deleted(self):
        receipt = self.take()
        self.object_path(receipt).unlink()
        self.failed([self.reference(receipt)], 'artifact_unavailable')

    def test_cl_06_artifact_altered(self):
        receipt = self.take()
        self.object_path(receipt).write_bytes(b'X' + self.raw[1:])
        self.failed([self.reference(receipt)], 'artifact_mismatched', 'MISMATCHED')

    def test_cl_07_verifier_raises(self):
        receipt = self.take()
        with patch('ripley.capture.verify_capture', side_effect=RuntimeError('fixture fault')):
            self.failed([self.reference(receipt)], 'verification_error')

    def test_cl_08_malformed_references(self):
        receipt = self.take()
        reference = self.reference(receipt)
        cases = ['not a sequence', {}, [None], [{'capture_id': receipt.id}],
                 [{**reference, 'extra': True}],
                 [{'capture_id': 'AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA', 'receipt_hash': '0' * 64}],
                 [{'capture_id': 'not-a-uuid', 'receipt_hash': '0' * 64}],
                 [{**reference, 'capture_id': 1}],
                 [{**reference, 'receipt_hash': 'g' * 64}],
                 [{**reference, 'receipt_hash': 'A' * 64}],
                 [{**reference, 'receipt_hash': 7}],
                 [{'capture_id': str(uuid.UUID(int=i)), 'receipt_hash': '0' * 64}
                  for i in range(17)]]
        for references in cases:
            with self.subTest(references=references):
                before = tuple(self.ledger.records)
                with self.assertRaisesRegex(ValueError, '^invalid capture references$'):
                    self.run_linked(references)
                self.assertEqual(tuple(self.ledger.records), before)
        without_store = Ripley(self.ledger)
        before = tuple(self.ledger.records)
        with self.assertRaisesRegex(ValueError, '^capture store required$'):
            without_store.run(self.adapter, self.inputs, capture_references=[reference])
        self.assertEqual(tuple(self.ledger.records), before)
        self.assertEqual(self.worker.calls, 0)

    def test_cl_09_duplicate_capture_id(self):
        receipt = self.take()
        before = tuple(self.ledger.records)
        with self.assertRaisesRegex(ValueError, '^duplicate capture reference$'):
            self.run_linked([self.reference(receipt), self.reference(receipt)])
        self.assertEqual(tuple(self.ledger.records), before)
        self.assertEqual(self.worker.calls, 0)

    def test_cl_10_identical_bytes_distinct_receipts(self):
        receipts = [self.take(), self.take()]
        self.assertNotEqual(receipts[0].id, receipts[1].id)
        self.assertNotEqual(receipts[0].content_hash, receipts[1].content_hash)
        run = self.run_linked([self.reference(r) for r in receipts])
        observations = run['capture_verification'].data['observations']
        self.assertEqual(len(observations), 2)
        self.assertEqual({o['capture_id'] for o in observations}, {r.id for r in receipts})
        self.assertEqual({o['status'] for o in observations}, {'MATCHED'})
        self.assertEqual({o['content_sha256'] for o in observations}, {receipts[0].data['sha256']})
        for receipt in receipts:
            self.assertEqual(run['evidence'].data['hashes'][receipt.id], receipt.content_hash)

    def test_cl_11_canonical_order(self):
        receipts = sorted([self.take(), self.take()], key=lambda r: r.id)
        references = [self.reference(r) for r in receipts]
        run = self.run_linked(list(reversed(references)))
        self.assertEqual(run['snapshot'].data['capture_references'], tuple(references))
        duplicate = self.run_linked(references)
        self.assertEqual(duplicate['outcome'], 'duplicate_of_existing_task')
        self.assertEqual(duplicate['task'].id, run['task'].id)
        self.assertIsNone(duplicate['capture_verification'])
        self.assertEqual(len(self.records('duplicate_submission')), 1)
        self.assertEqual(len(self.records('capture_verification')), 1)
        self.assertEqual(self.worker.calls, 1)

    def test_cl_12_evidence_conflict(self):
        a, b = self.reference(self.take()), self.reference(self.take())
        run = self.run_linked([a])
        for submitted in ([b], [a, b], None):
            before = tuple(self.ledger.records)
            with self.assertRaisesRegex(ValueError, '^capture_reference_conflict$'):
                self.run_linked(submitted)
            added = [r for r in self.ledger.records.values() if r.id not in before]
            self.assertEqual(len(added), 1)
            self.assertEqual(added[0].kind, 'capture_reference_conflict')
            self.assertEqual(dict(added[0].data), {'task_key': run['task'].data['task_key'],
                'task_id': run['task'].id, 'existing_capture_references': (a,),
                'submitted_capture_references': tuple(sorted(submitted or [], key=lambda r: r['capture_id']))})
        self.assertEqual(len(self.records('task')), 1)
        self.assertEqual(self.records('duplicate_submission'), [])
        self.assertEqual(self.ledger.task_state(run['task'].id), 'pending_owner_approval')
        self.assertEqual(self.worker.calls, 1)
        other_inputs = {**self.inputs, 'stock': 11}
        unlinked = self.engine.run(self.adapter, other_inputs, worker=self.worker)
        before = tuple(self.ledger.records)
        with self.assertRaisesRegex(ValueError, '^capture_reference_conflict$'):
            self.engine.run(self.adapter, other_inputs, worker=self.worker, capture_references=[a])
        self.assertEqual(len(self.ledger.records), len(before) + 1)
        conflict = self.records('capture_reference_conflict')[-1]
        self.assertEqual(conflict.data['task_id'], unlinked['task'].id)
        self.assertEqual(conflict.data['existing_capture_references'], ())
        self.assertEqual(self.worker.calls, 2)

    def test_cl_13_terminal_resubmission(self):
        first, second = self.take(), self.take()
        run = self.run_linked([self.reference(first)])
        self.engine.decide_approval(run['approval'].id, 'owner', 'rejected', 'new evidence context')
        later = self.run_linked([self.reference(second)])
        self.assertNotEqual(later['task'].id, run['task'].id)
        self.assertEqual(later['task'].data['task_key'], run['task'].data['task_key'])
        self.assertEqual(later['task'].data['previous_task_id'], run['task'].id)
        self.assertEqual(later['snapshot'].data['capture_references'], (self.reference(second),))
        self.assertEqual(self.worker.calls, 2)

    def test_cl_14_durable_reopen(self):
        path = self.root / 'ledger.sqlite'
        self.ledger = SQLiteLedger(path)
        self.engine = Ripley(self.ledger, capture_store=self.store)
        receipt = self.take()
        run = self.run_linked([self.reference(receipt)])
        hashes = {r.id: r.content_hash for r in self.ledger.records.values()}
        reopened = SQLiteLedger(path)
        self.assertEqual({r.id: r.content_hash for r in reopened.records.values()}, hashes)
        for key in ('snapshot', 'capture_verification', 'evidence'):
            self.assertEqual(reopened.records[run[key].id].data, run[key].data)
        self.assertEqual(reopened.records[run['snapshot'].id].data['capture_references'],
                         (self.reference(receipt),))
        self.assertEqual(reopened.task_state(run['task'].id), 'pending_owner_approval')
        approved = Ripley(reopened).decide_approval(run['approval'].id, 'owner', 'approved', 'reviewed')
        self.assertEqual(approved.data['status'], 'approved')

    def test_cl_15_recovery_reverifies(self):
        receipt = self.take()
        original = self.timed_out(receipt)
        before = tuple(self.ledger.records)
        with self.assertRaises(TypeError):
            self.recover(original, capture_references=[self.reference(receipt)])
        self.assertEqual(tuple(self.ledger.records), before)
        with self.assertRaisesRegex(ValueError, '^capture store required$'):
            Ripley(self.ledger).recover(original['task'].id, 'owner', 'retry', self.adapter)
        self.assertEqual(tuple(self.ledger.records), before)
        from ripley.capture import verify_capture
        with patch('ripley.capture.verify_capture', wraps=verify_capture) as verify:
            recovered = self.recover(original)
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(recovered['snapshot'].data['capture_references'],
                         original['snapshot'].data['capture_references'])
        self.assertEqual(recovered['snapshot'].data['replays_snapshot_id'], original['snapshot'].id)
        verifications = self.records('capture_verification')
        self.assertEqual(len(verifications), 2)
        self.assertEqual({v.data['context'] for v in verifications}, {'execution'})
        self.assertNotEqual(original['capture_verification'].id, recovered['capture_verification'].id)
        self.assertEqual(recovered['evidence'].data['capture_verification_id'],
                         recovered['capture_verification'].id)
        self.assertNotIn(original['capture_verification'].id, recovered['evidence'].data['hashes'])

    def test_cl_16_recovery_fails_closed(self):
        receipt = self.take()
        original = self.timed_out(receipt)
        self.object_path(receipt).write_bytes(b'X' + self.raw[1:])
        with self.assertRaisesRegex(ValueError, '^capture evidence not verified$'):
            self.recover(original)
        self.assertEqual(self.worker.calls, 0)
        self.assertEqual(self.records('recovery_authorization'), [])
        self.assertEqual(len(self.records('task')), 1)
        precheck = self.records('capture_verification')[-1]
        self.assertEqual(dict(precheck.data), {'task_id': original['task'].id,
            'snapshot_id': original['snapshot'].id, 'context': 'recovery_precheck',
            'attempt_number': None, 'passed': False,
            'observations': ({'capture_id': receipt.id,
                'expected_receipt_hash': receipt.content_hash,
                'observed_receipt_hash': receipt.content_hash,
                'content_sha256': receipt.data['sha256'], 'size_bytes': len(self.raw),
                'status': 'MISMATCHED', 'reason': 'artifact_mismatched'},)})
        self.assertIn(original['capture_verification'].id, self.ledger.records)
        self.object_path(receipt).write_bytes(self.raw)
        recovered = self.recover(original)
        self.assertEqual(recovered['outcome'], 'pending_owner_approval')
        self.assertEqual(len(self.records('recovery_authorization')), 1)
        self.assertEqual(self.worker.calls, 1)

    def test_cl_17_boundary_after_precheck(self):
        receipt = self.take()
        original = self.timed_out(receipt)
        append = self.ledger.add

        def remove_after_authorization(kind, data, supersedes=None):
            record = append(kind, data, supersedes)
            if kind == 'recovery_authorization':
                self.object_path(receipt).unlink()
            return record

        with patch.object(self.ledger, 'add', side_effect=remove_after_authorization):
            recovered = self.recover(original)
        self.assertEqual(recovered['outcome'], 'blocked_capture_verification')
        self.assertEqual(recovered['capture_verification'].data['observations'][0]['reason'],
                         'artifact_unavailable')
        self.assertEqual(self.worker.calls, 0)
        self.assertEqual(len(self.records('execution_attempt')), 1)
        self.assertEqual(len(self.records('recovery_authorization')), 1)
        self.assertFalse(any(v.data['context'] == 'recovery_precheck'
                             for v in self.records('capture_verification')))

    def test_cl_18_every_attempt(self):
        receipt = self.take()

        def bad_then_good(call, task, snapshot, adapter):
            return {} if call == 1 else adapter.predict(snapshot.data['inputs'])

        worker = CountingWorker(bad_then_good)
        run = self.run_linked([self.reference(receipt)], worker=worker)
        self.assertEqual(run['outcome'], 'pending_owner_approval')
        self.assertEqual(worker.calls, 2)
        verifications = self.records('capture_verification')
        self.assertEqual([v.data['attempt_number'] for v in verifications], [1, 2])
        self.assertEqual(run['capture_verification'].id, verifications[1].id)
        self.assertEqual(run['evidence'].data['capture_verification_id'], verifications[1].id)
        self.assertNotIn(verifications[0].id, run['evidence'].data['hashes'])

        def delete_then_bad(call, task, snapshot, adapter):
            self.object_path(receipt).unlink()
            return {}

        worker = CountingWorker(delete_then_bad)
        later = self.engine.run(self.adapter, {**self.inputs, 'stock': 11}, worker=worker,
                               capture_references=[self.reference(receipt)])
        self.assertEqual(later['outcome'], 'blocked_capture_verification')
        self.assertEqual(worker.calls, 1)
        self.assertEqual(later['capture_verification'].data['attempt_number'], 2)
        self.assertEqual(later['capture_verification'].data['observations'][0]['reason'],
                         'artifact_unavailable')
        self.assertEqual(len(later['results']), 1)

    def test_cl_19_end_to_end_trace(self):
        path = self.root / 'trace.sqlite'
        self.ledger = SQLiteLedger(path)
        self.engine = Ripley(self.ledger, capture_store=self.store)
        receipt = self.take()
        stock, demand, threshold = map(int, self.source.read_text('utf-8').split())
        run = self.engine.run(self.adapter, {'stock': stock, 'demand': demand, 'threshold': threshold},
                              capture_references=[self.reference(receipt)])
        approved = self.engine.decide_approval(run['approval'].id, 'owner', 'approved', 'fixture checked')
        with closing(sqlite3.connect(path)) as db:
            rows = {record_id: json.loads(data) for record_id, data in
                    db.execute('SELECT id, data FROM records').fetchall()}
        approval = rows[approved.id]['data']
        evidence = rows[approval['evidence_id']]['data']
        verification = rows[evidence['capture_verification_id']]['data']
        snapshot = rows[verification['snapshot_id']]['data']
        reference = snapshot['capture_references'][0]
        capture = rows[reference['capture_id']]['data']
        digest = capture['sha256']
        stored = (self.store / 'sha256' / digest[:2] / digest).read_bytes()
        self.assertEqual(stored, self.source.read_bytes())
        self.assertEqual(hashlib.sha256(stored).hexdigest(), digest)
        self.assertEqual(verification['observations'][0]['content_sha256'], digest)
        self.assertEqual(evidence['hashes'][reference['capture_id']], reference['receipt_hash'])
        self.assertEqual(evidence['task_id'], verification['task_id'])
        self.assertEqual(rows[evidence['task_id']]['data']['input_snapshot_id'], verification['snapshot_id'])
        self.assertEqual(rows[evidence['result_id']]['data']['input_snapshot_id'], verification['snapshot_id'])
        self.assertEqual(rows[evidence['validation_id']]['data']['result_id'], evidence['result_id'])
        self.assertEqual(rows[evidence['review_id']]['data']['validation_id'], evidence['validation_id'])

    def test_cl_20_evidence_pins(self):
        receipt = self.take()
        run = self.run_linked([self.reference(receipt)])
        records = [run[k] for k in ('task', 'snapshot', 'result', 'validation', 'review',
                                    'capture_verification')] + [receipt]
        self.assertEqual(dict(run['evidence'].data['hashes']), {r.id: r.content_hash for r in records})
        self.assertEqual(run['evidence'].data['capture_verification_id'], run['capture_verification'].id)
        self.object_path(receipt).unlink()
        with patch('ripley.capture.verify_capture', side_effect=AssertionError('approval reread')):
            approved = self.engine.decide_approval(run['approval'].id, 'owner', 'approved', 'reviewed')
        self.assertEqual(approved.data['status'], 'approved')

    def test_cl_21_legacy_no_references(self):
        for references in (None, [], ()):
            with self.subTest(references=references):
                ledger = Ledger()
                run = Ripley(ledger).run(self.adapter, self.inputs, capture_references=references)
                self.assertEqual(run['outcome'], 'pending_owner_approval')
                self.assertEqual(set(run['snapshot'].data), LEGACY_SNAPSHOT_KEYS)
                self.assertEqual(set(run['evidence'].data), {'task_id', 'snapshot_id', 'result_id',
                    'validation_id', 'review_id', 'hashes'})
                self.assertEqual(len(run['evidence'].data['hashes']), 5)
                self.assertIsNone(run['capture_verification'])
                self.assertFalse(any(r.kind in ('capture_verification', 'capture_reference_conflict')
                                     for r in ledger.records.values()))

    def test_cl_22_task_key(self):
        receipt = self.take()
        run = self.run_linked([self.reference(receipt)])
        expected = content_hash({'domain_id': self.adapter.domain_id,
            'domain_version': self.adapter.version, 'task_type': 'predict', 'inputs': self.inputs})
        self.assertEqual(run['task'].data['task_key'], expected)

    def test_cl_23_provider_refused(self):
        from ripley.nfl_availability import NflAvailabilityAdapter

        receipt = self.take()
        before = tuple(self.ledger.records)
        with patch('ripley.isolation.observe_subprocess', side_effect=AssertionError('launched')) as launch, \
                patch.object(self.engine, '_provider_dispatch_gate',
                             side_effect=AssertionError('dispatch gate')) as gate:
            with self.assertRaisesRegex(ValueError, 'not supported for provider workers'):
                self.engine.run(NflAvailabilityAdapter(), self.provider_inputs(),
                    worker=SimpleNamespace(identity='anthropic-worker'),
                    allowed_workers=('anthropic-worker',), execution='subprocess',
                    capture_references=[self.reference(receipt)])
        launch.assert_not_called()
        gate.assert_not_called()
        self.assertEqual(tuple(self.ledger.records), before)

    def test_cl_24_provider_packet_pin(self):
        from ripley.nfl_availability import NflAvailabilityAdapter

        clean = {k: v for k, v in os.environ.items() if not k.startswith('RIPLEY_')
                 and k != 'ANTHROPIC_API_KEY'}
        with patch.dict(os.environ, clean, clear=True):
            run = self.engine.run(NflAvailabilityAdapter(), self.provider_inputs(),
                worker=SimpleNamespace(identity='anthropic-worker'),
                allowed_workers=('anthropic-worker',), execution='subprocess')
        self.assertEqual(run['failure'].data['error']['type'], 'live_gate_closed')
        packet = self.records('execution_request')[-1].data['packet']
        self.assertEqual(set(packet), {'envelope_version', 'attempt_id', 'task_id', 'task_type',
            'domain_id', 'domain_version', 'worker_identity', 'inputs', 'deadline_at'})
        digest = hashlib.sha256(canonical_json(packet['inputs'])).hexdigest()
        print('CL-24 packet inputs SHA-256:', digest)
        print('CL-24 provider task key:', run['task'].data['task_key'])
        self.assertEqual(digest, '46719653ddac55f020472e4b63ddc78fecce202b0dbb549e9961bf1a50a2f3dd')
        self.assertEqual(run['task'].data['task_key'],
                         'cdbb31d169fef6a0f74d9cf435c05db81b7ea3c7dc2078dc1b122ce9a8486d81')
        self.assertEqual(set(run['snapshot'].data), LEGACY_SNAPSHOT_KEYS)
        self.assertNotIn('capture', canonical_json(packet).decode('utf-8'))

    @unittest.skipUnless(SDK_INSTALLED, 'optional anthropic SDK is not installed')
    def test_cl_25_provider_request_body_pin(self):
        script = r'''
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import httpx2
import ripley.providers as providers
from ripley.nfl_availability import NflAvailabilityAdapter

requests = []
def handler(request):
    requests.append(request.content)
    return httpx2.Response(200, headers={'request-id': 'req_offline'}, json={
        'id': 'msg_offline', 'type': 'message', 'role': 'assistant',
        'model': 'claude-haiku-5-5', 'content': [{'type': 'text', 'text': '{"players":[]}'}],
        'stop_reason': 'end_turn', 'stop_sequence': None,
        'usage': {'input_tokens': 11, 'output_tokens': 5}})
providers._mock_transport = lambda: httpx2.MockTransport(handler)
inputs = json.loads(Path('fixtures/nfl-availability/TB-at-CHI-2026-11-08.json').read_text('utf-8'))
outcome = providers.AnthropicWorker().produce(
    {'deadline_at': (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat()},
    {'inputs': inputs}, NflAvailabilityAdapter())
assert outcome.error is None, outcome.error
assert len(requests) == 1, len(requests)
assert providers.GUARD_ATTEMPTS == 0
print(json.dumps({'requests': len(requests), 'bytes': len(requests[0]),
                  'sha256': hashlib.sha256(requests[0]).hexdigest()}))
'''
        environment = {k: v for k, v in os.environ.items() if not k.startswith('RIPLEY_')
                       and k != 'ANTHROPIC_API_KEY'}
        environment.update(RIPLEY_PROVIDER_TRANSPORT='mock', RIPLEY_ENABLE_TEST_WORKERS='1',
                           RIPLEY_ANTHROPIC_API_KEY='sk-ant-test-synthetic-sprint10-offline')
        child = subprocess.run([sys.executable, '-B', '-c', script], env=environment,
                               capture_output=True, text=True, check=True)
        result = json.loads(child.stdout)
        print('CL-25 provider request:', result)
        self.assertEqual(result, {'requests': 1, 'bytes': 4805,
            'sha256': '037e813693e8bbdd1e6bb6ad0a843c233fa5b8ef3472031f5e2dd5baade737e7'})
