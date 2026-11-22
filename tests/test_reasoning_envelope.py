"""RE-01 through RE-17: passive envelope admission and durable accounting."""
from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ripley import reasoning_envelope as envelope
from ripley.capture import capture_file
from ripley.core import Ledger, MockWorker, Ripley
from ripley.storage import SQLiteLedger
from ripley.synthetic import InventoryAdapter


class _EnvelopeFixture:
    sqlite = False

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.approved = self.root / 'approved'
        self.approved.mkdir()
        self.store = self.root / 'store'
        self.database = self.root / 'ledger.sqlite'
        self.ledger = SQLiteLedger(self.database) if self.sqlite else Ledger()
        self.sequence = 0
        self.stamp = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)
        self.snapshot = self._snapshot()

    def _snapshot(self):
        self.sequence += 1
        source = self.approved / ('inventory-%d.txt' % self.sequence)
        source.write_text('Stock: %d\n' % (10 + self.sequence))
        receipt = capture_file(self.ledger, self.store, source, approved_root=self.approved,
            source_id='envelope-fixture', source_location='synthetic:inventory',
            supplied_by='Fixture.Author', content_type='text/plain; charset=utf-8')
        execution = Ripley(self.ledger, capture_store=self.store).run(
            InventoryAdapter(), {'stock': 10 + self.sequence, 'demand': 2, 'threshold': 3},
            worker=MockWorker(), capture_references=[
                {'capture_id': receipt.id, 'receipt_hash': receipt.content_hash}])
        self.assertEqual(execution['outcome'], 'pending_owner_approval')
        return execution['snapshot']

    @staticmethod
    def _limits():
        return {'max_attempts_per_operation': 1, 'max_input_bytes': 262144,
                'max_output_bytes': 65536, 'deadline_seconds': 120,
                'max_budget_microdollars': 500000, 'automatic_retries': 0}

    def _open(self, snapshot=None, input_bytes=12, budget=100, stamp=None):
        snapshot = self.snapshot if snapshot is None else snapshot
        stamp = self.stamp if stamp is None else stamp
        return envelope.open_attempt(self.ledger, snapshot.id, input_bytes, budget, clock=lambda: stamp)

    def _close(self, attempt, status='completed', output=10, cost=100, stamp=None):
        stamp = self.stamp + timedelta(seconds=60) if stamp is None else stamp
        return envelope.close_attempt(self.ledger, attempt.id, status, output, cost, clock=lambda: stamp)

    def _open_refusal(self, reason, *, snapshot_id=None, input_bytes=12, budget=100, stamp=None):
        identity = self.snapshot.id if snapshot_id is None else snapshot_id
        stamp = self.stamp if stamp is None else stamp
        before = set(self.ledger.records)
        record = envelope.open_attempt(self.ledger, identity, input_bytes, budget, clock=lambda: stamp)
        self.assertEqual([r for key, r in self.ledger.records.items() if key not in before], [record])
        self.assertEqual(record.kind, 'reasoning_attempt_refusal')
        self.assertEqual(dict(record.data), {
            'snapshot_id': identity if 1 <= len(identity) <= 64 else None,
            'envelope_id': 'reasoning-envelope-v1',
            'envelope_sha256': '0ef7f6be571dc111d359202471d6c8ab9b12193adaf879b66664b3b26fd99224',
            'reason': reason})
        return record

    def _close_refusal(self, reason, *, attempt_id, status='completed', output=10, cost=100):
        before = set(self.ledger.records)
        record = envelope.close_attempt(self.ledger, attempt_id, status, output, cost,
                                        clock=lambda: self.stamp + timedelta(seconds=60))
        self.assertEqual([r for key, r in self.ledger.records.items() if key not in before], [record])
        self.assertEqual(record.kind, 'reasoning_close_refusal')
        self.assertEqual(dict(record.data), {
            'attempt_id': attempt_id if 1 <= len(attempt_id) <= 64 else None, 'reason': reason})
        return record


class _EnvelopeCases(_EnvelopeFixture):
    def test_re_01_open_identity_limits_and_clock(self):
        clock = Mock(return_value=self.stamp)
        record = envelope.open_attempt(self.ledger, self.snapshot.id, 12, 100, clock=clock)
        clock.assert_called_once_with()
        literal = '0ef7f6be571dc111d359202471d6c8ab9b12193adaf879b66664b3b26fd99224'
        self.assertEqual(record.kind, 'reasoning_attempt')
        self.assertEqual(dict(record.data), {
            'snapshot_id': self.snapshot.id, 'snapshot_hash': self.snapshot.content_hash,
            'attempt_number': 1, 'envelope_id': 'reasoning-envelope-v1', 'envelope_sha256': literal,
            'limits': self._limits(), 'input_bytes': 12, 'required_budget_microdollars': 100,
            'paid_authority_microdollars': 0, 'opened_at': self.stamp.isoformat(),
            'deadline_at': (self.stamp + timedelta(seconds=120)).isoformat()})
        self.assertEqual(envelope.ENVELOPE_SHA256, literal)
        self.assertEqual(envelope.remaining_attempts(self.ledger, self.snapshot.id), 0)

    def test_re_02_one_attempt_per_snapshot(self):
        self.assertEqual(envelope.remaining_attempts(self.ledger, self.snapshot.id), 1)
        snapshots = sum(r.kind == 'snapshot' for r in self.ledger.records.values())
        self._open()
        self._open_refusal('attempt_already_consumed', input_bytes=1, budget=0)
        self.assertEqual(sum(r.kind == 'reasoning_attempt' for r in self.ledger.records.values()), 1)
        self.assertEqual(sum(r.kind == 'snapshot' for r in self.ledger.records.values()), snapshots)
        other = self._snapshot()
        self.assertEqual(envelope.remaining_attempts(self.ledger, other.id), 1)
        self.assertEqual(self._open(snapshot=other).data['attempt_number'], 1)
        self.assertEqual(envelope.remaining_attempts(self.ledger, other.id), 0)

    def test_re_03_open_write_failure(self):
        before = set(self.ledger.records)
        with patch.object(self.ledger, 'add', side_effect=OSError('write refused')):
            with self.assertRaises(envelope.EnvelopeError) as error:
                self._open()
        self.assertEqual(error.exception.reason, 'ledger_write_failed')
        self.assertEqual(set(self.ledger.records), before)
        self.assertFalse(any(r.kind == 'reasoning_attempt' for r in self.ledger.records.values()))
        self.assertEqual(envelope.remaining_attempts(self.ledger, self.snapshot.id), 1)
        record = self._open()
        self.assertIs(record, self.ledger.records[record.id])

    def test_re_04_input_bounds(self):
        for size, reason in [(262145, 'input_too_large'), (0, 'input_invalid'), (-1, 'input_invalid')]:
            with self.subTest(size=size):
                self._open_refusal(reason, input_bytes=size)
                self.assertEqual(envelope.remaining_attempts(self.ledger, self.snapshot.id), 1)
        self.assertEqual(self._open(input_bytes=262144).kind, 'reasoning_attempt')

    def test_re_05_budget_admission(self):
        for budget, reason in [(500001, 'budget_too_large'), (-1, 'budget_invalid')]:
            with self.subTest(budget=budget):
                self._open_refusal(reason, budget=budget)
                self.assertEqual(envelope.remaining_attempts(self.ledger, self.snapshot.id), 1)
        record = self._open(budget=500000)
        self.assertEqual(record.data['required_budget_microdollars'], 500000)
        self.assertEqual(record.data['paid_authority_microdollars'], 0)
        other = self._open(snapshot=self._snapshot(), budget=0)
        self.assertEqual(other.data['required_budget_microdollars'], 0)
        self.assertEqual(other.data['paid_authority_microdollars'], 0)

    def test_re_06_operation_resolution(self):
        receipt = next(r for r in self.ledger.records.values() if r.kind == 'capture')
        empty = self.ledger.add('snapshot', {'capture_references': []})
        absent = self.ledger.add('snapshot', {'inputs': {}})
        for identity in ['missing-snapshot', receipt.id, empty.id, absent.id, 'x' * 65]:
            with self.subTest(identity=identity):
                self._open_refusal('operation_unavailable', snapshot_id=identity)
        self.assertFalse(any(r.kind == 'reasoning_attempt' for r in self.ledger.records.values()))

    def test_re_07_close_at_all_limits(self):
        attempt = self._open(budget=500000)
        closed_at = self.stamp + timedelta(seconds=120)
        clock = Mock(return_value=closed_at)
        record = envelope.close_attempt(self.ledger, attempt.id, 'completed', 65536, 500000, clock=clock)
        clock.assert_called_once_with()
        self.assertEqual(record.kind, 'reasoning_attempt_close')
        self.assertEqual(dict(record.data), {
            'attempt_id': attempt.id, 'attempt_hash': attempt.content_hash,
            'snapshot_id': self.snapshot.id, 'envelope_id': 'reasoning-envelope-v1',
            'envelope_sha256': '0ef7f6be571dc111d359202471d6c8ab9b12193adaf879b66664b3b26fd99224',
            'status': 'completed', 'output_bytes': 65536, 'reported_cost_microdollars': 500000,
            'closed_at': closed_at.isoformat(), 'violations': (), 'outcome': 'completed_within_limits'})

    def test_re_08_output_violation(self):
        record = self._close(self._open(), output=65537)
        self.assertEqual(record.data['violations'], ('output_too_large',))
        self.assertEqual(record.data['outcome'], 'completed_with_violation')

    def test_re_09_cost_violation(self):
        record = self._close(self._open(), cost=500001)
        self.assertEqual(record.data['violations'], ('budget_exceeded',))
        self.assertEqual(record.data['outcome'], 'completed_with_violation')

    def test_re_10_deadline_and_ordered_violations(self):
        late = self.stamp + timedelta(seconds=120, microseconds=1)
        record = self._close(self._open(), stamp=late)
        self.assertEqual(record.data['violations'], ('deadline_exceeded',))
        self.assertEqual(record.data['outcome'], 'completed_with_violation')
        combined = self._close(self._open(snapshot=self._snapshot()), output=65537, cost=500001, stamp=late)
        self.assertEqual(combined.data['violations'],
                         ('budget_exceeded', 'deadline_exceeded', 'output_too_large'))
        self.assertEqual(combined.data['outcome'], 'completed_with_violation')

    def test_re_11_failed_uncertain_stay_consumed(self):
        for status in ['uncertain', 'failed']:
            with self.subTest(status=status):
                snapshot = self._snapshot()
                record = self._close(self._open(snapshot=snapshot), status=status, output=None, cost=None)
                self.assertEqual(record.data['outcome'], status)
                self.assertEqual(record.data['violations'], ())
                self.assertIsNone(record.data['output_bytes'])
                self.assertIsNone(record.data['reported_cost_microdollars'])
                self.assertEqual(envelope.remaining_attempts(self.ledger, snapshot.id), 0)
                self._open_refusal('attempt_already_consumed', snapshot_id=snapshot.id)
                late = self._close(self._open(snapshot=self._snapshot()), status=status,
                                   output=None, cost=None, stamp=self.stamp + timedelta(seconds=121))
                self.assertEqual(late.data['outcome'], status)
                self.assertEqual(late.data['violations'], ('deadline_exceeded',))

    def test_re_12_close_refusals(self):
        attempt = self._open()
        for identity in ['missing-attempt', self.snapshot.id, 'x' * 65]:
            self._close_refusal('attempt_unavailable', attempt_id=identity)
        for status in ['succeeded', 'completed_within_limits']:
            self._close_refusal('status_invalid', attempt_id=attempt.id, status=status)
        for output, cost in [(None, 1), (1, None), (-1, 1), (1, -1)]:
            self._close_refusal('report_invalid', attempt_id=attempt.id, output=output, cost=cost)
        for status in ['uncertain', 'failed']:
            for output, cost in [(1, None), (None, 1)]:
                self._close_refusal('report_invalid', attempt_id=attempt.id, status=status,
                                    output=output, cost=cost)
        self.assertFalse(any(r.kind == 'reasoning_attempt_close' for r in self.ledger.records.values()))
        self._close(attempt)
        for status in ['completed', 'uncertain', 'failed', 'succeeded']:
            self._close_refusal('attempt_already_closed', attempt_id=attempt.id, status=status)
        self.assertEqual(sum(r.kind == 'reasoning_attempt_close' for r in self.ledger.records.values()), 1)

    def test_re_13_unclosed_never_refunded(self):
        self._open()
        self.assertEqual(envelope.remaining_attempts(self.ledger, self.snapshot.id), 0)
        self._open_refusal('attempt_already_consumed', stamp=self.stamp + timedelta(days=30))
        self.assertFalse(any(r.kind == 'reasoning_attempt_close' for r in self.ledger.records.values()))

    def test_re_14_pinned_limits_and_api(self):
        opened_signature = inspect.signature(envelope.open_attempt)
        closed_signature = inspect.signature(envelope.close_attempt)
        self.assertEqual(tuple(opened_signature.parameters),
                         ('ledger', 'snapshot_id', 'input_bytes', 'required_budget_microdollars', 'clock'))
        self.assertEqual(tuple(closed_signature.parameters),
                         ('ledger', 'attempt_id', 'status', 'output_bytes', 'reported_cost_microdollars', 'clock'))
        for signature in [opened_signature, closed_signature]:
            self.assertEqual(signature.parameters['clock'].kind, inspect.Parameter.KEYWORD_ONLY)
            self.assertIsNone(signature.parameters['clock'].default)
        before = len(self.ledger.records)
        with self.assertRaises(TypeError):
            envelope.open_attempt(self.ledger, self.snapshot.id, 1, 0,
                                  clock=lambda: self.stamp, max_input_bytes=999999)
        self.assertEqual(len(self.ledger.records), before)
        self.assertEqual((envelope.MAX_ATTEMPTS_PER_OPERATION, envelope.MAX_INPUT_BYTES,
                          envelope.MAX_OUTPUT_BYTES, envelope.DEADLINE_SECONDS,
                          envelope.MAX_BUDGET_MICRODOLLARS, envelope.AUTOMATIC_RETRIES),
                         (1, 262144, 65536, 120, 500000, 0))
        self.assertEqual(envelope.PAID_AUTHORITY_MICRODOLLARS, 0)
        attempt = self._open()
        with patch.multiple(envelope, MAX_OUTPUT_BYTES=1000000,
                            MAX_BUDGET_MICRODOLLARS=10000000, DEADLINE_SECONDS=12000):
            record = self._close(attempt, output=65537, cost=500001,
                                 stamp=self.stamp + timedelta(seconds=121))
        self.assertEqual(record.data['violations'],
                         ('budget_exceeded', 'deadline_exceeded', 'output_too_large'))
        self.assertEqual(record.data['envelope_sha256'],
                         '0ef7f6be571dc111d359202471d6c8ab9b12193adaf879b66664b3b26fd99224')
        self.assertEqual(dict(attempt.data['limits']), self._limits())

    def test_re_15_no_authority(self):
        source = inspect.getsource(envelope)
        for forbidden in ['socket', 'subprocess', 'providers', 'anthropic', 'urllib', 'http']:
            self.assertNotIn(forbidden, source)
        self.assertFalse(hasattr(envelope, 'Ripley'))
        public = {name for name, value in vars(envelope).items()
                  if not name.startswith('_') and callable(value)}
        self.assertEqual(public, {'EnvelopeError', 'open_attempt', 'close_attempt', 'remaining_attempts'})
        self.assertEqual({name for name in vars(envelope) if not name.startswith('_')}, public | {
            'ENVELOPE_ID', 'MAX_ATTEMPTS_PER_OPERATION', 'MAX_INPUT_BYTES', 'MAX_OUTPUT_BYTES',
            'DEADLINE_SECONDS', 'MAX_BUDGET_MICRODOLLARS', 'AUTOMATIC_RETRIES',
            'PAID_AUTHORITY_MICRODOLLARS', 'STATUSES', 'ENVELOPE_SHA256'})
        before = {r.id: r.content_hash for r in self.ledger.records.values()}
        states = {r.id: self.ledger.task_state(r.id) for r in self.ledger.records.values() if r.kind == 'task'}
        attempt = self._open()
        self._close(attempt)
        self._open_refusal('attempt_already_consumed')
        self._close_refusal('attempt_already_closed', attempt_id=attempt.id)
        added = [r for key, r in self.ledger.records.items() if key not in before]
        self.assertEqual(len(added), 4)
        self.assertEqual({r.kind for r in added}, {'reasoning_attempt', 'reasoning_attempt_close',
                                                 'reasoning_attempt_refusal', 'reasoning_close_refusal'})
        self.assertTrue(all(self.ledger.records[key].content_hash == digest
                            for key, digest in before.items()))
        self.assertEqual(states, {identity: self.ledger.task_state(identity) for identity in states})

    def test_re_16_call_clock_and_write_errors(self):
        attempt = self._open()
        cases = [
            (envelope.open_attempt, (self.ledger, None, 1, 0)),
            (envelope.open_attempt, (self.ledger, self.snapshot.id, True, 0)),
            (envelope.open_attempt, (self.ledger, self.snapshot.id, 1.0, 0)),
            (envelope.open_attempt, (self.ledger, self.snapshot.id, 1, '0')),
            (envelope.close_attempt, (self.ledger, None, 'completed', 1, 0)),
            (envelope.close_attempt, (self.ledger, attempt.id, None, 1, 0)),
            (envelope.close_attempt, (self.ledger, attempt.id, 'completed', True, 0)),
            (envelope.close_attempt, (self.ledger, attempt.id, 'completed', 1, 0.0)),
            (envelope.remaining_attempts, (self.ledger, None))]
        for function, args in cases:
            with self.subTest(function=function.__name__, args=args[1:]):
                before = len(self.ledger.records)
                clock = Mock(return_value=self.stamp)
                with self.assertRaises(envelope.EnvelopeError) as error:
                    if function is envelope.remaining_attempts:
                        function(*args)
                    else:
                        function(*args, clock=clock)
                self.assertEqual(error.exception.reason, 'invalid_call')
                clock.assert_not_called()
                self.assertEqual(len(self.ledger.records), before)
        for value in [self.stamp.replace(tzinfo=None), 'not a datetime',
                      self.stamp.astimezone(timezone(timedelta(hours=1)))]:
            for function, args in [(envelope.open_attempt, (self.ledger, self.snapshot.id, 1, 0)),
                                   (envelope.close_attempt, (self.ledger, attempt.id, 'completed', 1, 0))]:
                clock = Mock(return_value=value)
                before = len(self.ledger.records)
                with self.assertRaises(envelope.EnvelopeError) as error:
                    function(*args, clock=clock)
                self.assertEqual(error.exception.reason, 'invalid_clock')
                clock.assert_called_once_with()
                self.assertEqual(len(self.ledger.records), before)
        before = len(self.ledger.records)
        with patch.object(self.ledger, 'add', side_effect=OSError('write refused')):
            with self.assertRaises(envelope.EnvelopeError) as error:
                self._close(attempt)
        self.assertEqual(error.exception.reason, 'ledger_write_failed')
        self.assertEqual(len(self.ledger.records), before)
        self.assertEqual(self._close(attempt).kind, 'reasoning_attempt_close')


class MemoryReasoningEnvelopeTests(_EnvelopeCases, unittest.TestCase):
    pass


class SQLiteReasoningEnvelopeTests(_EnvelopeCases, unittest.TestCase):
    sqlite = True

    def test_re_17_restart_consumption(self):
        unclosed = self._open()
        other_snapshot = self._snapshot()
        uncertain = self._open(snapshot=other_snapshot)
        closed = self._close(uncertain, status='uncertain', output=None, cost=None)
        digest = unclosed.content_hash
        del self.ledger
        self.ledger = SQLiteLedger(self.database)
        for snapshot in [self.snapshot, other_snapshot]:
            self.assertEqual(envelope.remaining_attempts(self.ledger, snapshot.id), 0)
            self._open_refusal('attempt_already_consumed', snapshot_id=snapshot.id)
        reopened = self.ledger.records[unclosed.id]
        self.assertEqual(reopened.content_hash, digest)
        self.assertEqual(reopened.data['envelope_sha256'],
                         '0ef7f6be571dc111d359202471d6c8ab9b12193adaf879b66664b3b26fd99224')
        self.assertEqual(dict(reopened.data['limits']), self._limits())
        self.assertEqual(self.ledger.records[closed.id].data['outcome'], 'uncertain')
        self.assertEqual(self._close(reopened).data['outcome'], 'completed_within_limits')
        self.assertEqual(sum(r.kind == 'reasoning_attempt' for r in self.ledger.records.values()), 2)
