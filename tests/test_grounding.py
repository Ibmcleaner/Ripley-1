"""GV-01 through GV-28: grounding trust-boundary detecting tests."""
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from ripley import grounding
from ripley.capture import capture_file
from ripley.core import Ledger, MockWorker, Ripley, canonical_json
from ripley.storage import SQLiteLedger
from ripley.synthetic import InventoryAdapter


class _GroundingFixture:
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
        self.raw = ('Units on hand: 10\r\nUnits on hand: 12\n'
                    'Location: Café — 東\nStatus: accepted\n').encode('utf-8')
        self.capture_count = 0
        self.snapshot_count = 0
        self.receipt = self._capture(self.raw)
        self.snapshot, self.task = self._snapshot([self.receipt])

    def _capture(self, data):
        self.capture_count += 1
        path = self.approved / ('source-%d.txt' % self.capture_count)
        path.write_bytes(data)
        return capture_file(self.ledger, self.store, path, approved_root=self.approved,
                            source_id='grounding-fixture', source_location='synthetic:fixture',
                            supplied_by='fixture-author', content_type='text/plain; charset=utf-8')

    def _snapshot(self, receipts):
        self.snapshot_count += 1
        result = Ripley(self.ledger, capture_store=self.store).run(
            InventoryAdapter(), {'stock': 100 + self.snapshot_count, 'demand': 3, 'threshold': 5},
            worker=MockWorker(), capture_references=[
                {'capture_id': receipt.id, 'receipt_hash': receipt.content_hash}
                for receipt in receipts])
        self.assertEqual(result['outcome'], 'pending_owner_approval')
        return result['snapshot'], result['task']

    def _path(self, receipt=None):
        digest = (self.receipt if receipt is None else receipt).data['sha256']
        return self.store / 'sha256' / digest[:2] / digest

    def _citation(self, quote='Units on hand: 10', receipt=None, data=None):
        receipt = self.receipt if receipt is None else receipt
        data = self.raw if data is None else data
        encoded = quote.encode('utf-8')
        start = data.index(encoded)
        return {'capture_id': receipt.id, 'start': start, 'end': start + len(encoded),
                'quote': quote}

    def _observation(self, identity='obs-1', **changes):
        value = {'observation_id': identity, 'field': 'units', 'status': 'asserted',
                 'value': '10', 'citations': [self._citation()]}
        value.update(changes)
        return value

    def _proposal(self, observations=None, snapshot=None):
        snapshot = self.snapshot if snapshot is None else snapshot
        return {'proposal_version': 1, 'snapshot_id': snapshot.id,
                'producer': {'kind': 'fixture', 'identity': 'fixture-author'},
                'observations': [self._observation()] if observations is None else observations}

    @staticmethod
    def _encode(proposal):
        # ASCII JSON escapes allow a lone-surrogate case to reach schema admission.
        return json.dumps(proposal, separators=(',', ':')).encode('utf-8')

    def _ground(self, proposal=None):
        before = set(self.ledger.records)
        result = grounding.ground_proposal(
            self.ledger, self.store, self._encode(self._proposal() if proposal is None else proposal))
        added = [record for key, record in self.ledger.records.items() if key not in before]
        self.assertEqual([record.kind for record in added], ['proposal', 'grounding_validation'])
        self.assertEqual(result.id, added[-1].id)
        return result

    def _reject(self, raw, reason):
        before = set(self.ledger.records)
        result = grounding.ground_proposal(self.ledger, self.store, raw)
        added = [record for key, record in self.ledger.records.items() if key not in before]
        self.assertEqual([record.kind for record in added], ['grounding_rejection'])
        self.assertEqual(result.id, added[0].id)
        self.assertEqual(dict(result.data), {'proposal_sha256': hashlib.sha256(raw).hexdigest(),
            'proposal_size_bytes': len(raw), 'reason': reason})
        self.assertNotIn(self.raw.decode('utf-8'), canonical_json(result.data).decode('utf-8'))
        self.assertNotIn('Units on hand', canonical_json(result.data).decode('utf-8'))
        return result

    def _blocked(self, result, reason, capture_id=None):
        self.assertEqual(result.data['outcome'], 'blocked_evidence')
        self.assertEqual(result.data['review_state'], 'not_reviewable')
        self.assertEqual(result.data['verdicts'], ())
        self.assertEqual(result.data['multi_observation_fields'], ())
        capture_id = self.receipt.id if capture_id is None else capture_id
        item = next(item for item in result.data['evidence'] if item['capture_id'] == capture_id)
        self.assertEqual(item['reason'], reason)
        package = grounding.review_package(self.ledger, result.id)
        self.assertEqual(package['review_state'], 'not_reviewable')
        self.assertEqual(package['observations'], [])


class _GroundingCases(_GroundingFixture):
    def test_gv_01_grounded(self):
        before = tuple(self.ledger.records.values())
        state = self.ledger.task_state(self.task.id)
        proposal = self._proposal()
        raw = self._encode(proposal)
        result = self._ground(proposal)
        stored = self.ledger.records[result.data['proposal_id']]
        self.assertEqual(set(stored.data), {'proposal_sha256', 'proposal_size_bytes',
                                          'snapshot_hash', 'proposal'})
        self.assertEqual(stored.data['proposal_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(stored.data['proposal_size_bytes'], len(raw))
        self.assertEqual(stored.data['snapshot_hash'], self.snapshot.content_hash)
        self.assertEqual(canonical_json(stored.data['proposal']), canonical_json(proposal))
        self.assertEqual(set(result.data), {'proposal_id', 'proposal_hash', 'snapshot_id',
            'snapshot_hash', 'outcome', 'evidence', 'verdicts', 'multi_observation_fields', 'review_state'})
        self.assertEqual(result.data['proposal_hash'], stored.content_hash)
        self.assertEqual(result.data['snapshot_id'], self.snapshot.id)
        self.assertEqual(result.data['snapshot_hash'], self.snapshot.content_hash)
        self.assertEqual(result.data['outcome'], 'evaluated')
        self.assertEqual(result.data['review_state'], 'awaiting_semantic_review')
        self.assertEqual(dict(result.data['evidence'][0]), {
            'capture_id': self.receipt.id, 'expected_receipt_hash': self.receipt.content_hash,
            'observed_receipt_hash': self.receipt.content_hash,
            'content_sha256': self.receipt.data['sha256'], 'size_bytes': len(self.raw), 'reason': 'verified'})
        verdict = result.data['verdicts'][0]
        self.assertEqual(set(verdict), {'observation_id', 'verdict', 'reason', 'citations'})
        self.assertEqual(verdict['verdict'], 'grounded')
        self.assertEqual(verdict['reason'], 'all_citations_matched')
        self.assertEqual(set(verdict['citations'][0]), {'capture_id', 'start', 'end', 'result'})
        self.assertEqual(verdict['citations'][0]['result'], 'matched')
        self.assertEqual(self.ledger.task_state(self.task.id), state)
        for kind in ('review', 'approval', 'evidence', 'task_transition'):
            self.assertEqual(sum(r.kind == kind for r in before),
                             sum(r.kind == kind for r in self.ledger.records.values()))

    def test_gv_02_multibyte(self):
        citation = self._citation('Café — 東')
        self.assertNotEqual(citation['end'] - citation['start'], len(citation['quote']))
        result = self._ground(self._proposal([self._observation(citations=[citation])]))
        self.assertEqual(result.data['verdicts'][0]['verdict'], 'grounded')
        self.assertEqual(result.data['verdicts'][0]['citations'][0]['result'], 'matched')

    def test_gv_03_crlf(self):
        citation = self._citation('Units on hand: 10\r\n')
        for quote, want in [(citation['quote'], 'matched'),
                            (citation['quote'].replace('\r\n', '\n'), 'quote_mismatch')]:
            with self.subTest(quote=quote):
                changed = dict(citation, quote=quote)
                result = self._ground(self._proposal([self._observation(citations=[changed])]))
                self.assertEqual(result.data['verdicts'][0]['citations'][0]['result'], want)

    def test_gv_04_quote_mismatch(self):
        for quote in ['units on hand: 10', 'Units on hand: 99', 'Units on hand: 1']:
            with self.subTest(quote=quote):
                citation = dict(self._citation(), quote=quote)
                result = self._ground(self._proposal([self._observation(citations=[citation])]))
                self.assertEqual(result.data['verdicts'][0]['citations'][0]['result'], 'quote_mismatch')
                self.assertEqual(result.data['verdicts'][0]['verdict'], 'not_grounded')

    def test_gv_05_bounds(self):
        length = len(self.raw)
        cases = [(length - 1, length, '\n', 'matched'),
                 (length - 1, length + 1, '\n', 'out_of_bounds'),
                 (length + 1, length + 2, 'x', 'out_of_bounds')]
        for start, end, quote, want in cases:
            with self.subTest(start=start, end=end):
                citation = dict(self._citation(), start=start, end=end, quote=quote)
                result = self._ground(self._proposal([self._observation(citations=[citation])]))
                self.assertEqual(result.data['verdicts'][0]['citations'][0]['result'], want)

    def test_gv_06_character_boundaries(self):
        offset = self.raw.index('é'.encode())
        for start, end in [(offset + 1, offset + 2), (offset, offset + 1)]:
            with self.subTest(start=start, end=end):
                citation = dict(self._citation(), start=start, end=end, quote='x')
                result = self._ground(self._proposal([self._observation(citations=[citation])]))
                self.assertEqual(result.data['verdicts'][0]['citations'][0]['result'], 'splits_character')

    def test_gv_07_capture_not_on_snapshot(self):
        other = self._capture(self.raw)
        for identity in [other.id, 'no-such-capture']:
            with self.subTest(identity=identity):
                citation = dict(self._citation(), capture_id=identity)
                result = self._ground(self._proposal([self._observation(citations=[citation])]))
                self.assertEqual(result.data['verdicts'][0]['citations'][0]['result'], 'capture_not_on_snapshot')
                self.assertEqual(result.data['verdicts'][0]['verdict'], 'not_grounded')

    def test_gv_08_citation_missing(self):
        result = self._ground(self._proposal([self._observation(citations=[])]))
        self.assertEqual(result.data['verdicts'][0]['verdict'], 'not_grounded')
        self.assertEqual(result.data['verdicts'][0]['reason'], 'citation_missing')

    def test_gv_09_not_found(self):
        observation = self._observation(status='not_found', value=None, citations=[])
        result = self._ground(self._proposal([observation]))
        self.assertEqual(result.data['verdicts'][0]['verdict'], 'no_evidence_claimed')
        self.assertEqual(result.data['verdicts'][0]['reason'], 'declared_not_found')

    def test_gv_10_all_citations(self):
        citations = [self._citation(), dict(self._citation(), quote='Units on hand: 99')]
        result = self._ground(self._proposal([self._observation(citations=citations)]))
        verdict = result.data['verdicts'][0]
        self.assertEqual(verdict['verdict'], 'not_grounded')
        self.assertEqual(verdict['reason'], 'citation_failed')
        self.assertEqual([c['result'] for c in verdict['citations']], ['matched', 'quote_mismatch'])

    def test_gv_11_schema(self):
        cases = []

        def change(label, target, key, value=None, delete=False):
            proposal = self._proposal()
            obj = proposal
            for part in target:
                obj = obj[part]
            if delete:
                del obj[key]
            else:
                obj[key] = value
            cases.append((label, proposal))

        observation = ['observations', 0]
        citation = observation + ['citations', 0]
        for label, target in [('proposal-extra', []), ('producer-extra', ['producer']),
                              ('observation-extra', observation), ('citation-extra', citation)]:
            change(label, target, 'extra', 'fixture-content')
        change('missing-observation-field', observation, 'field', delete=True)
        change('missing-citation-field', citation, 'end', delete=True)
        for value in [2, True]:
            change('version-' + repr(value), [], 'proposal_version', value)
        for value in [True, 1.0, -1]:
            change('start-' + repr(value), citation, 'start', value)
        change('equal-range', citation, 'end', self._citation()['start'])
        change('long-range', citation, 'end', self._citation()['start'] + 4097)
        for label, quote in [('empty-quote', ''), ('byte-overflow', 'é' * 2049),
                              ('surrogate', '\ud800')]:
            change(label, citation, 'quote', quote)
        for value in [None, 'x' * 65]:
            change('capture-id-' + repr(value), citation, 'capture_id', value)
        for value in [None, 10]:
            change('value-' + repr(value), observation, 'value', value)
        change('status', observation, 'status', 'unsupported')
        change('producer-kind', ['producer'], 'kind', 'model')
        change('producer-identity', ['producer'], 'identity', '')
        change('observation-id', observation, 'observation_id', 'has space')
        change('zero-observations', [], 'observations', [])
        change('many-observations', [], 'observations',
               [self._observation('obs-%d' % i) for i in range(65)])
        change('many-citations', observation, 'citations', [self._citation()] * 9)
        for label, obs in [('not-found-value', self._observation(status='not_found', citations=[])),
                           ('not-found-citation', self._observation(status='not_found', value=None))]:
            change(label, [], 'observations', [obs])
        change('long-note', observation, 'note', 'x' * 513)
        for value in [None, '']:
            change('snapshot-id-' + repr(value), [], 'snapshot_id', value)
        for label, proposal in cases:
            with self.subTest(case=label):
                self._reject(self._encode(proposal), 'proposal_schema_invalid')

    def test_gv_12_duplicate_ids(self):
        proposal = self._proposal([self._observation(), self._observation()])
        self._reject(self._encode(proposal), 'duplicate_observation_id')
        proposal['proposal_version'] = 2
        self._reject(self._encode(proposal), 'proposal_schema_invalid')

    def test_gv_13_strict_json(self):
        self._reject(b'x' * (grounding.MAX_PROPOSAL_BYTES + 1), 'proposal_too_large')
        self._reject(b'\xff', 'proposal_not_utf8')
        depth = 10000
        malformed = [b'[]', b'{', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}',
                     b'{"x":1e999}', b'{"x":1,"x":2}',
                     b'{"observations":[{"x":1,"x":2}]}',
                     b'{"x":' + b'[' * depth + b'0' + b']' * depth + b'}',
                     b'{} trailing']
        for index, raw in enumerate(malformed):
            with self.subTest(case=index):
                self._reject(raw, 'proposal_not_json')
        result = self._reject(b'{}', 'proposal_schema_invalid')
        self.assertEqual(result.data['proposal_size_bytes'], 2)

    def test_gv_14_snapshot(self):
        empty = self.ledger.add('snapshot', {'inputs': {}})
        for identity in ['missing-snapshot', self.task.id, empty.id]:
            with self.subTest(identity=identity):
                proposal = self._proposal()
                proposal['snapshot_id'] = identity
                self._reject(self._encode(proposal), 'snapshot_unavailable')

    def test_gv_15_artifact_unavailable(self):
        self._path().unlink()
        result = self._ground()
        self._blocked(result, 'artifact_unavailable')
        self.assertEqual(self.ledger.records[result.data['proposal_id']].kind, 'proposal')

    def test_gv_16_artifact_hash(self):
        changed = self.raw.replace(b'Status: accepted', b'Status: Accepted')
        self.assertEqual(len(changed), len(self.raw))
        self._path().write_bytes(changed)
        self._blocked(self._ground(), 'artifact_mismatched')

    def test_gv_17_artifact_size(self):
        grown = self.raw + b'!'
        self._path().write_bytes(grown)
        self._blocked(self._ground(), 'artifact_mismatched')
        # Isolate the size gate from the independently tested digest gate (M07).
        real_sha256 = hashlib.sha256

        def controlled_digest(data=b'', *args, **kwargs):
            return real_sha256(self.raw if data == grown else data, *args, **kwargs)

        with patch('hashlib.sha256', side_effect=controlled_digest):
            self._blocked(self._ground(), 'artifact_mismatched')

    def test_gv_18_artifact_utf8(self):
        receipt = self._capture(b'Units on hand: 10\n\xff')
        snapshot, _ = self._snapshot([receipt])
        citation = self._citation(receipt=receipt)
        proposal = self._proposal([self._observation(citations=[citation])], snapshot)
        self._blocked(self._ground(proposal), 'artifact_not_utf8', receipt.id)

    def test_gv_19_artifact_limit(self):
        with patch.object(grounding, 'MAX_ARTIFACT_BYTES', len(self.raw) - 1), \
                patch.object(grounding, '_read_object', side_effect=AssertionError('must not read')) as reader:
            self._blocked(self._ground(), 'artifact_too_large')
            reader.assert_not_called()

    def test_gv_20_one_read(self):
        original = grounding._read_object
        calls = []

        def change_after_read(path, limit):
            data = original(path, limit)
            calls.append((path, limit))
            path.write_bytes(self.raw.replace(b'10', b'99', 1))
            return data

        with patch.object(grounding, '_read_object', side_effect=change_after_read):
            result = self._ground()
        self.assertEqual(calls, [(self._path(), grounding.MAX_ARTIFACT_BYTES)])
        self.assertEqual(result.data['evidence'][0]['reason'], 'verified')
        self.assertEqual(result.data['verdicts'][0]['citations'][0]['result'], 'matched')
        self.assertEqual(result.data['verdicts'][0]['verdict'], 'grounded')

    def test_gv_21_multiple_observations(self):
        observations = [self._observation(), self._observation('obs-2', value='12',
            citations=[self._citation('Units on hand: 12')]),
            self._observation('obs-3', field='location', status='uncertain', value='Café',
                              note='Needs human interpretation', citations=[self._citation('Café — 東')])]
        result = self._ground(self._proposal(observations))
        self.assertEqual([item['verdict'] for item in result.data['verdicts']], ['grounded'] * 3)
        self.assertEqual(canonical_json(result.data['multi_observation_fields']),
                         canonical_json([{'field': 'units', 'observation_ids': ['obs-1', 'obs-2']}]))
        package = grounding.review_package(self.ledger, result.id)
        self.assertEqual(package['observations'][2]['status'], 'uncertain')
        self.assertEqual(package['observations'][2]['note'], observations[2]['note'])

    def test_gv_22_review_package(self):
        observations = [self._observation(), self._observation('obs-2',
            citations=[dict(self._citation(), quote='Units on hand: 99')]),
            self._observation('obs-3', status='not_found', value=None, citations=[])]
        result = self._ground(self._proposal(observations))
        shutil.rmtree(self.store)
        before = len(self.ledger.records)
        package = grounding.review_package(self.ledger, result.id)
        self.assertEqual(len(self.ledger.records), before)
        self.assertEqual(set(package), {'notice', 'validation_id', 'validation_hash', 'proposal_id',
            'proposal_hash', 'snapshot_id', 'producer', 'outcome', 'review_state', 'evidence',
            'multi_observation_fields', 'observations'})
        self.assertEqual(package['notice'], grounding.NOTICE)
        self.assertEqual(package['producer'], {'kind': 'fixture', 'identity': 'fixture-author'})
        self.assertEqual(package['validation_id'], result.id)
        self.assertEqual(package['validation_hash'], result.content_hash)
        self.assertEqual(package['proposal_id'], result.data['proposal_id'])
        self.assertEqual(package['proposal_hash'], result.data['proposal_hash'])
        self.assertEqual(package['snapshot_id'], self.snapshot.id)
        self.assertEqual([o['eligible_for_semantic_review'] for o in package['observations']],
                         [True, False, True])
        for observation in package['observations']:
            self.assertEqual(set(observation), {'observation_id', 'field', 'status', 'value', 'note',
                                               'verdict', 'reason', 'citations', 'eligible_for_semantic_review'})
            self.assertIsNone(observation['note'])
        self.assertEqual(package['observations'][0]['citations'][0],
                         dict(self._citation(), result='matched'))
        json.dumps(package)
        for identity in ['no-such-validation', self.receipt.id]:
            with self.subTest(identity=identity), self.assertRaises(grounding.GroundingError) as error:
                grounding.review_package(self.ledger, identity)
            self.assertEqual(error.exception.reason, 'validation_unavailable')
        for changes in [{'proposal_id': 'missing'}, {'proposal_id': self.receipt.id},
                        {'proposal_hash': '0' * 64}]:
            forged = self.ledger.add('grounding_validation', dict(result.data, **changes))
            with self.subTest(changes=changes), self.assertRaises(grounding.GroundingError) as error:
                grounding.review_package(self.ledger, forged.id)
            self.assertEqual(error.exception.reason, 'proposal_unavailable')

    def test_gv_23_no_authority(self):
        source = inspect.getsource(grounding)
        for forbidden in ['socket', 'subprocess', 'providers', 'anthropic', 'urllib', 'http']:
            self.assertNotIn(forbidden, source)
        public = {name for name, value in vars(grounding).items()
                  if not name.startswith('_') and callable(value)}
        self.assertEqual(public, {'GroundingError', 'ground_proposal', 'review_package'})
        self.assertEqual({name for name in vars(grounding) if not name.startswith('_')},
                         public | {'PROPOSAL_VERSION', 'MAX_PROPOSAL_BYTES', 'MAX_ARTIFACT_BYTES',
                                   'MAX_OBSERVATIONS', 'MAX_CITATIONS', 'MAX_CITATION_BYTES',
                                   'PRODUCER_KINDS', 'NOTICE'})
        observation = self._observation(value='accepted', note='The source says accepted',
                                        citations=[self._citation('Status: accepted')])
        package = grounding.review_package(self.ledger, self._ground(self._proposal([observation])).id)
        item = package['observations'][0]
        self.assertEqual(item['value'], observation['value'])
        self.assertEqual(item['note'], observation['note'])
        self.assertEqual(item['citations'][0]['quote'], observation['citations'][0]['quote'])
        self.assertEqual(item['verdict'], 'grounded')
        self.assertEqual(package['outcome'], 'evaluated')
        self.assertEqual(package['review_state'], 'awaiting_semantic_review')
        self.assertIn(item['verdict'], ('grounded', 'not_grounded', 'no_evidence_claimed'))

    def test_gv_24_repeated_proposal(self):
        raw = self._encode(self._proposal())
        first = grounding.ground_proposal(self.ledger, self.store, raw)
        second = grounding.ground_proposal(self.ledger, self.store, raw)
        self.assertNotEqual(first.data['proposal_id'], second.data['proposal_id'])
        self.assertEqual(sum(r.kind == 'proposal' for r in self.ledger.records.values()), 2)
        self.assertEqual(sum(r.kind == 'grounding_validation' for r in self.ledger.records.values()), 2)
        a, b = dict(first.data), dict(second.data)
        a.pop('proposal_id')
        b.pop('proposal_id')
        self.assertEqual(a, b)

    def test_gv_25_call_and_writes(self):
        for value in ['{}', None, bytearray(b'{}'), {}]:
            before = len(self.ledger.records)
            with self.subTest(value=type(value).__name__), self.assertRaises(grounding.GroundingError) as error:
                grounding.ground_proposal(self.ledger, self.store, value)
            self.assertEqual(error.exception.reason, 'invalid_call')
            self.assertEqual(len(self.ledger.records), before)
        for raw in [b'{}', self._encode(self._proposal())]:
            with patch.object(self.ledger, 'add', side_effect=RuntimeError('write failed')):
                with self.subTest(raw=raw[:2]), self.assertRaises(grounding.GroundingError) as error:
                    grounding.ground_proposal(self.ledger, self.store, raw)
                self.assertEqual(error.exception.reason, 'ledger_write_failed')
        original_add = self.ledger.add

        def fail_validation(kind, data, supersedes=None):
            if kind == 'grounding_validation':
                raise RuntimeError('write failed')
            return original_add(kind, data, supersedes)

        with patch.object(self.ledger, 'add', side_effect=fail_validation):
            with self.assertRaises(grounding.GroundingError) as error:
                grounding.ground_proposal(self.ledger, self.store, self._encode(self._proposal()))
            self.assertEqual(error.exception.reason, 'ledger_write_failed')

    def test_gv_26_offsets_and_multiple_captures(self):
        quote = 'Status: accepted'
        start = self.raw.decode('utf-8').index(quote)
        citation = dict(self._citation(quote), start=start, end=start + len(quote))
        result = self._ground(self._proposal([self._observation(citations=[citation])]))
        self.assertEqual(result.data['verdicts'][0]['verdict'], 'not_grounded')
        self.assertNotEqual(result.data['verdicts'][0]['citations'][0]['result'], 'matched')
        other_data = b'Different opening padding\nSecond item: 73\n'
        other = self._capture(other_data)
        snapshot, _ = self._snapshot([self.receipt, other])
        citations = [self._citation(), self._citation('73', other, other_data)]
        observations = [self._observation('obs-%d' % index, citations=[cite])
                        for index, cite in enumerate(citations)]
        result = self._ground(self._proposal(observations, snapshot))
        self.assertEqual([v['verdict'] for v in result.data['verdicts']], ['grounded', 'grounded'])
        self.assertEqual([e['capture_id'] for e in result.data['evidence']],
                         [r['capture_id'] for r in snapshot.data['capture_references']])
        self.assertEqual(len(result.data['evidence']), 2)
        wrong = dict(citations[1], capture_id=self.receipt.id)
        result = self._ground(self._proposal([self._observation(citations=[wrong])], snapshot))
        self.assertEqual(result.data['verdicts'][0]['verdict'], 'not_grounded')
        self._path(other).unlink()
        self._blocked(self._ground(self._proposal(observations, snapshot)), 'artifact_unavailable', other.id)


class MemoryGroundingTests(_GroundingCases, unittest.TestCase):
    pass


class SQLiteGroundingTests(_GroundingCases, unittest.TestCase):
    sqlite = True

    def test_gv_27_reopen(self):
        result = self._ground()
        package = grounding.review_package(self.ledger, result.id)
        count = len(self.ledger.records)
        self.ledger = SQLiteLedger(self.database)
        self.assertEqual(len(self.ledger.records), count)
        self.assertEqual(grounding.review_package(self.ledger, result.id), package)


class ForgedSnapshotTests(_GroundingFixture, unittest.TestCase):
    def test_gv_28_receipt_failures(self):
        cases = [('missing-capture', '0' * 64, 'receipt_missing'),
                 (self.task.id, self.task.content_hash, 'receipt_wrong_kind'),
                 (self.receipt.id, '0' * 64, 'receipt_hash_mismatch')]
        for capture_id, digest, reason in cases:
            snapshot = self.ledger.add('snapshot', {'capture_references': [
                {'capture_id': capture_id, 'receipt_hash': digest}]})
            with self.subTest(reason=reason), patch.object(grounding, '_read_object') as reader:
                result = self._ground(self._proposal(snapshot=snapshot))
                self._blocked(result, reason, capture_id)
                reader.assert_not_called()
            item = result.data['evidence'][0]
            self.assertIsNone(item['content_sha256'])
            self.assertIsNone(item['size_bytes'])
            self.assertEqual(item['observed_receipt_hash'],
                             self.receipt.content_hash if reason == 'receipt_hash_mismatch' else None)
