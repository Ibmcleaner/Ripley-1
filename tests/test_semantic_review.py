"""SR-01 through SR-17: independent semantic-review boundary evidence."""
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ripley import semantic_review as review
from ripley.capture import capture_file
from ripley.core import Ledger, MockWorker, Ripley
from ripley.grounding import ground_proposal
from ripley.storage import SQLiteLedger
from ripley.synthetic import InventoryAdapter


class _ReviewFixture:
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
        self.raw = b'Stock: 10\nPossible: 12\n'
        source = self.approved / 'inventory.txt'
        source.write_bytes(self.raw)
        self.receipt = capture_file(self.ledger, self.store, source, approved_root=self.approved,
            source_id='semantic-review-fixture', source_location='synthetic:inventory',
            supplied_by='Fixture.Author', content_type='text/plain; charset=utf-8')
        execution = Ripley(self.ledger, capture_store=self.store).run(
            InventoryAdapter(), {'stock': 10, 'demand': 2, 'threshold': 3}, worker=MockWorker(),
            capture_references=[{'capture_id': self.receipt.id,
                                 'receipt_hash': self.receipt.content_hash}])
        self.snapshot, self.task = execution['snapshot'], execution['task']
        self.proposal = {'proposal_version': 1, 'snapshot_id': self.snapshot.id,
            'producer': {'kind': 'fixture', 'identity': 'Fixture.Author'}, 'observations': [
                self._observation('asserted-1', 'asserted', '10', 'Stock: 10'),
                self._observation('uncertain-2', 'uncertain', '12', 'Possible: 12'),
                {'observation_id': 'not-found-3', 'field': 'delivery', 'status': 'not_found',
                 'value': None, 'citations': []},
                self._observation('not-grounded-4', 'asserted', '99', 'Stock: 10', 'Stock: 99')]}
        self.validation = self._ground()

    def _observation(self, identity, status, value, source_quote, quote=None):
        start = self.raw.index(source_quote.encode())
        return {'observation_id': identity, 'field': identity, 'status': status, 'value': value,
                'citations': [{'capture_id': self.receipt.id, 'start': start,
                               'end': start + len(source_quote.encode()),
                               'quote': source_quote if quote is None else quote}]}

    def _ground(self, proposal=None):
        raw = json.dumps(self.proposal if proposal is None else proposal).encode()
        result = ground_proposal(self.ledger, self.store, raw)
        self.assertEqual(result.kind, 'grounding_validation')
        return result

    @staticmethod
    def _decisions(all_acceptable=False):
        decisions = [
            {'observation_id': 'asserted-1', 'verdict': 'acceptable', 'reason': 'The quote supports it.'},
            {'observation_id': 'uncertain-2', 'verdict': 'rejected', 'reason': 'The inference is too strong.'},
            {'observation_id': 'not-found-3', 'verdict': 'needs_clarification',
             'reason': 'The scope needs clarification.', 'unresolved_issues': ['Which delivery period?']}]
        if all_acceptable:
            for decision in decisions:
                decision['verdict'] = 'acceptable'
                decision.pop('unresolved_issues', None)
        return decisions

    def _review(self, decisions=None, validation=None, reviewer='Independent.Reviewer'):
        validation = self.validation if validation is None else validation
        return review.record_semantic_review(self.ledger, validation.id, validation.content_hash,
            reviewer, self._decisions() if decisions is None else decisions)

    def _refuse(self, reason, *, validation=None, validation_id=None, digest=None,
                reviewer='Independent.Reviewer', decisions=None, reviewer_stored=True,
                no_review=True):
        validation = self.validation if validation is None else validation
        identity = validation.id if validation_id is None else validation_id
        digest = validation.content_hash if digest is None else digest
        before = set(self.ledger.records)
        result = review.record_semantic_review(self.ledger, identity, digest, reviewer,
            self._decisions() if decisions is None else decisions)
        added = [r for key, r in self.ledger.records.items() if key not in before]
        self.assertEqual(added, [result])
        self.assertEqual(result.kind, 'semantic_review_refusal')
        self.assertEqual(dict(result.data), {
            'validation_id': identity if 1 <= len(identity) <= 64 else None,
            'reviewer_identity': reviewer if reviewer_stored else None, 'reason': reason})
        if no_review:
            self.assertFalse(any(r.kind == 'semantic_review' and r.data['validation_id'] == identity
                                 for r in self.ledger.records.values()))
        return result


class _ReviewCases(_ReviewFixture):
    def test_sr_01_valid_review(self):
        before = {r.id: r.content_hash for r in self.ledger.records.values()}
        state = self.ledger.task_state(self.task.id)
        supplied = self._decisions()
        result = self._review(supplied)
        proposal = self.ledger.records[self.validation.data['proposal_id']]
        self.assertEqual(result.kind, 'semantic_review')
        self.assertEqual(set(result.data), {'validation_id', 'validation_hash', 'proposal_id',
            'proposal_hash', 'snapshot_id', 'snapshot_hash', 'producer_identity', 'reviewer_kind',
            'reviewer_identity', 'criteria_id', 'criteria_sha256', 'decisions'})
        for name, record in [('validation', self.validation), ('proposal', proposal),
                             ('snapshot', self.snapshot)]:
            self.assertEqual(result.data[name + '_id'], record.id)
            self.assertEqual(result.data[name + '_hash'], record.content_hash)
        self.assertEqual(result.data['producer_identity'], 'Fixture.Author')
        self.assertEqual(result.data['reviewer_kind'], 'human')
        self.assertEqual(result.data['reviewer_identity'], 'Independent.Reviewer')
        self.assertEqual(result.data['criteria_id'], 'semantic-review-criteria-v1')
        self.assertEqual(result.data['criteria_sha256'],
                         '50fca7d3f9064bfcaeac785064ec35b13475f7f5881f9d543371b5028d747a38')
        expected_pairs = [('asserted', 'grounded'), ('uncertain', 'grounded'),
                          ('not_found', 'no_evidence_claimed')]
        for stored, decision, (status, verdict) in zip(result.data['decisions'], supplied, expected_pairs):
            self.assertEqual(dict(stored), {'observation_id': decision['observation_id'],
                'status': status, 'grounding_verdict': verdict, 'verdict': decision['verdict'],
                'reason': decision['reason'],
                'unresolved_issues': tuple(decision.get('unresolved_issues', []))})
        self.assertEqual(len(result.data['decisions']), 3)
        self.assertEqual(set(self.ledger.records) - set(before), {result.id})
        self.assertTrue(all(self.ledger.records[key].content_hash == digest
                            for key, digest in before.items()))
        self.assertEqual(self.ledger.task_state(self.task.id), state)
        self.assertIs(result, self.ledger.records[result.id])

    def test_sr_02_validation_resolution(self):
        for identity in ['missing-validation', self.receipt.id, 'x' * 65]:
            with self.subTest(identity=identity):
                self._refuse('validation_unavailable', validation_id=identity)

    def test_sr_03_validation_hash(self):
        other = self._ground()
        self.assertNotEqual(other.content_hash, self.validation.content_hash)
        for digest in [other.content_hash, self.validation.content_hash.upper(), '']:
            with self.subTest(digest=digest):
                self._refuse('validation_hash_mismatch', digest=digest)

    def test_sr_04_blocked_evidence(self):
        digest = self.receipt.data['sha256']
        (self.store / 'sha256' / digest[:2] / digest).unlink()
        blocked = self._ground()
        self.assertEqual(blocked.data['review_state'], 'not_reviewable')
        self._refuse('not_reviewable', validation=blocked)

    def test_sr_05_proposal_link(self):
        for changes in [{'proposal_id': 'missing'}, {'proposal_id': self.receipt.id},
                        {'proposal_hash': '0' * 64}]:
            with self.subTest(changes=changes):
                target = self.ledger.add('grounding_validation', dict(self.validation.data, **changes))
                self._refuse('proposal_unavailable', validation=target)

    def test_sr_06_reviewer_format(self):
        for identity in ['', 'two words', 'x' * 129, '-reviewer']:
            with self.subTest(identity=identity):
                self._refuse('reviewer_invalid', reviewer=identity, reviewer_stored=False)

    def test_sr_07_producer_separation(self):
        for identity in ['Fixture.Author', 'fixture.author', 'FIXTURE.AUTHOR']:
            with self.subTest(identity=identity):
                self._refuse('reviewer_is_producer', reviewer=identity)
        human = dict(self.proposal, producer={'kind': 'human', 'identity': 'Human.Author'})
        target = self._ground(human)
        self._refuse('reviewer_is_producer', validation=target, reviewer='Human.Author')
        self.assertEqual(self._review(validation=target, reviewer='Another.Human').kind,
                         'semantic_review')

    def test_sr_08_fixed_criteria(self):
        literal = '50fca7d3f9064bfcaeac785064ec35b13475f7f5881f9d543371b5028d747a38'
        self.assertEqual(review.CRITERIA_ID, 'semantic-review-criteria-v1')
        self.assertEqual(review.CRITERIA_SHA256, literal)
        self.assertEqual(hashlib.sha256(review.CRITERIA_TEXT.encode()).hexdigest(), literal)
        self.assertEqual(len(review.CRITERIA_TEXT.encode()), 578)
        self.assertEqual(tuple(inspect.signature(review.record_semantic_review).parameters),
                         ('ledger', 'validation_id', 'validation_hash', 'reviewer_identity', 'decisions'))
        before = len(self.ledger.records)
        with self.assertRaises(TypeError):
            review.record_semantic_review(self.ledger, self.validation.id, self.validation.content_hash,
                'Independent.Reviewer', self._decisions(), criteria='producer-controlled')
        self.assertEqual(len(self.ledger.records), before)
        decisions = self._decisions()
        decisions[0]['criteria_id'] = 'producer-controlled'
        self._refuse('decision_schema_invalid', decisions=decisions)
        stored = self._review()
        self.assertEqual(stored.data['criteria_id'], 'semantic-review-criteria-v1')
        self.assertEqual(stored.data['criteria_sha256'], literal)

    def test_sr_09_complete_unique_ordered_decisions(self):
        self._refuse('decision_missing', decisions=self._decisions()[:2])
        self._refuse('decision_missing', decisions=[])
        decisions = self._decisions()
        self._refuse('decision_duplicate', decisions=decisions + [dict(decisions[0])])
        stored = self._review(list(reversed(self._decisions())))
        self.assertEqual([d['observation_id'] for d in stored.data['decisions']],
                         ['asserted-1', 'uncertain-2', 'not-found-3'])

    def test_sr_10_eligibility(self):
        for identity in ['not-grounded-4', 'not-in-proposal']:
            decisions = self._decisions() + [
                {'observation_id': identity, 'verdict': 'acceptable', 'reason': 'Must be refused.'}]
            self._refuse('decision_not_eligible', decisions=decisions)
        target = self._ground(dict(self.proposal, observations=[self.proposal['observations'][3]]))
        self._refuse('no_eligible_observations', validation=target, decisions=[])
        self._refuse('no_eligible_observations', validation=target, decisions=self._decisions())

    def test_sr_11_decision_schema_and_verdicts(self):
        variants = [dict(self._decisions()[0], verdict=v) for v in ['approved', 'accepted', None]]
        variants += [dict(self._decisions()[0], reason=v) for v in ['', 'r' * 513, None]]
        variants += [dict(self._decisions()[0], observation_id=1),
                     dict(self._decisions()[0], extra='not allowed'), 'not a decision',
                     {'observation_id': 'asserted-1', 'verdict': 'acceptable'}]
        for variant in variants:
            with self.subTest(variant=variant):
                self._refuse('decision_schema_invalid', decisions=[variant] + self._decisions()[1:])
        boundary = self._decisions()
        boundary[0]['reason'] = 'r' * 512
        fresh = self._ground()
        self.assertEqual(self._review(boundary, validation=fresh).data['decisions'][0]['reason'], 'r' * 512)
        supplied = self._decisions()
        stored = self._review(supplied)
        self.assertEqual([d['verdict'] for d in stored.data['decisions']],
                         ['acceptable', 'rejected', 'needs_clarification'])
        self.assertEqual([d['reason'] for d in stored.data['decisions']],
                         [d['reason'] for d in supplied])

    def test_sr_12_unresolved_issues(self):
        base = dict(self._decisions()[0], verdict='needs_clarification')
        variants = [base] + [dict(base, unresolved_issues=v)
                            for v in [[], ['x'] * 9, [''], ['x' * 257], 'not a list']]
        variants += [dict(self._decisions()[0], unresolved_issues=['not allowed']),
                     dict(self._decisions()[0], verdict='rejected', unresolved_issues=[])]
        for variant in variants:
            with self.subTest(variant=variant):
                self._refuse('decision_schema_invalid', decisions=[variant] + self._decisions()[1:])
        supplied = self._decisions()
        supplied[2]['unresolved_issues'] = ['Which delivery period?', 'Is the source complete?']
        stored = self._review(supplied)
        self.assertEqual(stored.data['decisions'][2]['unresolved_issues'],
                         tuple(supplied[2]['unresolved_issues']))
        self.assertEqual([d['unresolved_issues'] for d in stored.data['decisions'][:2]], [(), ()])

    def test_sr_13_declared_status_preserved(self):
        stored = self._review(self._decisions(all_acceptable=True))
        self.assertEqual([(d['status'], d['grounding_verdict']) for d in stored.data['decisions']],
                         [('asserted', 'grounded'), ('uncertain', 'grounded'),
                          ('not_found', 'no_evidence_claimed')])
        self.assertTrue(all(d['verdict'] == 'acceptable' for d in stored.data['decisions']))

    def test_sr_14_one_review_per_validation(self):
        stored = self._review()
        digest = stored.content_hash
        for reviewer in ['Independent.Reviewer', 'Different.Reviewer']:
            self._refuse('already_reviewed', reviewer=reviewer, no_review=False)
        self.assertEqual(sum(r.kind == 'semantic_review' for r in self.ledger.records.values()), 1)
        self.assertEqual(self.ledger.records[stored.id].content_hash, digest)
        target = self._ground()
        self.assertNotEqual(target.id, self.validation.id)
        self.assertEqual(self._review(validation=target).kind, 'semantic_review')

    def test_sr_15_no_authority(self):
        source = inspect.getsource(review)
        for forbidden in ['socket', 'subprocess', 'providers', 'anthropic', 'urllib', 'http']:
            self.assertNotIn(forbidden, source)
        self.assertFalse(hasattr(review, 'Ripley'))
        public = {name for name, value in vars(review).items()
                  if not name.startswith('_') and callable(value)}
        self.assertEqual(public, {'SemanticReviewError', 'record_semantic_review'})
        self.assertEqual({name for name in vars(review) if not name.startswith('_')}, public | {
            'CRITERIA_ID', 'CRITERIA_LINES', 'CRITERIA_TEXT', 'CRITERIA_SHA256', 'REVIEWER_KIND',
            'VERDICTS', 'MAX_REASON_CHARS', 'MAX_UNRESOLVED_ISSUES', 'MAX_ISSUE_CHARS'})
        kinds = ('task', 'task_transition', 'result', 'review', 'evidence', 'approval',
                 'execution_attempt', 'snapshot', 'proposal', 'grounding_validation', 'reasoning_attempt')
        before = {kind: sum(r.kind == kind for r in self.ledger.records.values()) for kind in kinds}
        ids = set(self.ledger.records)
        state = self.ledger.task_state(self.task.id)
        self._review(self._decisions(all_acceptable=True))
        self.assertEqual(before, {kind: sum(r.kind == kind for r in self.ledger.records.values())
                                  for kind in kinds})
        self.assertEqual(self.ledger.task_state(self.task.id), state)
        self.assertEqual({r.kind for key, r in self.ledger.records.items() if key not in ids},
                         {'semantic_review'})

    def test_sr_16_call_and_write_errors(self):
        valid = [self.ledger, self.validation.id, self.validation.content_hash,
                 'Independent.Reviewer', self._decisions()]
        cases = [(index, value) for index in [1, 2, 3] for value in [None, b'bytes', 1]]
        cases += [(4, tuple(self._decisions())), (4, None)]
        for index, value in cases:
            with self.subTest(index=index, value=value):
                args = list(valid)
                args[index] = value
                before = len(self.ledger.records)
                with self.assertRaises(review.SemanticReviewError) as error:
                    review.record_semantic_review(*args)
                self.assertEqual(error.exception.reason, 'invalid_call')
                self.assertEqual(len(self.ledger.records), before)
        for reviewer in ['Independent.Reviewer', '']:
            before = len(self.ledger.records)
            with patch.object(self.ledger, 'add', side_effect=OSError('write refused')):
                with self.assertRaises(review.SemanticReviewError) as error:
                    self._review(reviewer=reviewer)
            self.assertEqual(error.exception.reason, 'ledger_write_failed')
            self.assertEqual(len(self.ledger.records), before)


class MemorySemanticReviewTests(_ReviewCases, unittest.TestCase):
    pass


class SQLiteSemanticReviewTests(_ReviewCases, unittest.TestCase):
    sqlite = True

    def test_sr_17_reopen_and_provenance(self):
        stored = self._review()
        identity, digest = stored.id, stored.content_hash
        del self.ledger
        self.ledger = SQLiteLedger(self.database)
        reopened = self.ledger.records[identity]
        self.assertEqual(reopened.content_hash, digest)
        validation = self.ledger.records[reopened.data['validation_id']]
        proposal = self.ledger.records[reopened.data['proposal_id']]
        snapshot = self.ledger.records[reopened.data['snapshot_id']]
        for name, record in [('validation', validation), ('proposal', proposal), ('snapshot', snapshot)]:
            self.assertEqual(record.content_hash, reopened.data[name + '_hash'])
        self.assertEqual(proposal.content_hash, validation.data['proposal_hash'])
        self.assertEqual(snapshot.content_hash, validation.data['snapshot_hash'])
        self.assertEqual(proposal.data['proposal']['producer']['identity'],
                         reopened.data['producer_identity'])
        reference = snapshot.data['capture_references'][0]
        receipt = self.ledger.records[reference['capture_id']]
        self.assertEqual(receipt.content_hash, reference['receipt_hash'])
        self.assertEqual(receipt.kind, 'capture')
        self.assertEqual(receipt.data['sha256'], hashlib.sha256(self.raw).hexdigest())
        self._refuse('already_reviewed', validation=validation, no_review=False)
