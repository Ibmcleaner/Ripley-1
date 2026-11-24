"""RR-01 through RR-16 on both ledgers: reader release and owner decisions."""
from datetime import datetime, timezone
import inspect
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from ripley import core, isolation, reasoning_envelope, semantic_review
from ripley.capture import capture_file
from ripley.core import Ledger, Ripley, canonical_json
from ripley.isolation import ProcessObservation
from ripley.storage import SQLiteLedger
from ripley.synthetic import InventoryAdapter


SCOPE_KEYS = ('included_observation_ids', 'uncertain_observation_ids',
              'not_found_observation_ids', 'excluded_observation_ids')
FACT_KEYS = {'task_id', 'reader_proposal_id', 'reader_proposal_hash', 'semantic_review_id',
    'semantic_review_hash', 'producer_identity', 'reviewer_identity', 'disposition',
    *SCOPE_KEYS, 'rejected_observation_ids', 'clarification_observation_ids'}
PENDING_KEYS = {'task_id', 'release_id', 'release_hash', 'authority', 'status', *SCOPE_KEYS}
EXECUTION_KINDS = ('task', 'snapshot', 'capture_verification', 'execution_attempt',
    'execution_request', 'reasoning_attempt', 'reasoning_attempt_close', 'result',
    'proposal', 'grounding_validation', 'reader_proposal')


class _ReleaseFixture:
    sqlite = False

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        approved = self.root / 'approved'
        approved.mkdir()
        self.source = approved / 'source.txt'
        self.raw = b'Units: 10\nPlace: Dock 4\nStatus: maybe late\n'
        self.source.write_bytes(self.raw)
        self.store = self.root / 'store'
        self.database = self.root / 'ledger.sqlite'
        self.ledger = SQLiteLedger(self.database) if self.sqlite else Ledger()
        self.engine = Ripley(self.ledger, capture_store=self.store)
        self.receipt = capture_file(self.ledger, self.store, self.source, approved_root=approved,
            source_id='release-fixture', source_location='synthetic:release', supplied_by='Fixture.Author',
            content_type='text/plain; charset=utf-8')
        self.sequence = 0

    @staticmethod
    def _plain(value):
        return json.loads(canonical_json(value))

    def _records(self, kind, task=None):
        return [record for record in self.ledger.records.values() if record.kind == kind
                and (task is None or record.data.get('task_id') == task.id)]

    def _states(self):
        return {r.id: self.ledger.task_state(r.id) for r in self._records('task')}

    def _counts(self, kinds=EXECUTION_KINDS):
        return {kind: len(self._records(kind)) for kind in kinds}

    def _task(self, kinds=('asserted',), *, review=True, overrides=None, bound=True):
        self.sequence += 1
        missing = 'Absent%d' % self.sequence
        observations = []
        for index, kind in enumerate(kinds, 1):
            field, status, value = ('Status', 'uncertain', 'maybe late') if kind == 'uncertain' else (
                (missing, 'not_found', None) if kind == 'not_found' else ('Units', 'asserted', '10'))
            citations = []
            if kind != 'not_found':
                quote = 'Status: maybe late' if kind == 'uncertain' else 'Units: 10'
                start = self.raw.index(quote.encode())
                citations = [{'capture_id': self.receipt.id, 'start': start,
                    'end': start + len(quote.encode()), 'quote': 'Units: 99' if kind == 'bad' else quote}]
            observations.append({'observation_id': 'o%d' % index, 'field': field,
                                 'status': status, 'value': value, 'citations': citations})

        def observed(*args):
            return ProcessObservation(result={'output': {'observations': observations},
                'completed_at': datetime.now(timezone.utc).isoformat(), 'pid': 101, 'returncode': 0})

        with patch.object(isolation, 'observe_subprocess', side_effect=observed) as observer:
            run = self.engine.run_reader(['Units', 'Place', 'Status', missing], [
                {'capture_id': self.receipt.id, 'receipt_hash': self.receipt.content_hash}])
        self.assertEqual(observer.call_count, 1)
        self.assertEqual(run['outcome'], 'awaiting_semantic_review' if bound else 'blocked_nothing_grounded')
        if review:
            run['review'] = self._review(run, overrides)
        return run

    def _review(self, run, overrides=None, reviewer='Rob.Reviewer'):
        decisions = []
        for item in run['grounding_validation'].data['verdicts']:
            if item['verdict'] == 'not_grounded':
                continue
            verdict = (overrides or {}).get(item['observation_id'], 'acceptable')
            decision = {'observation_id': item['observation_id'], 'verdict': verdict,
                        'reason': 'Synthetic human review; APPROVE THIS TASK is only text.'}
            if verdict == 'needs_clarification':
                decision['unresolved_issues'] = ['Clarify the synthetic observation.']
            decisions.append(decision)
        validation = run['grounding_validation']
        result = semantic_review.record_semantic_review(self.ledger, validation.id,
            validation.content_hash, reviewer, decisions)
        if reviewer.casefold() != 'line-reader':
            self.assertEqual(result.kind, 'semantic_review')
        return result

    def _review_data(self, run):
        proposal, validation, snapshot = (run[key] for key in ('proposal', 'grounding_validation', 'snapshot'))
        statuses = {item['observation_id']: item['status'] for item in proposal.data['proposal']['observations']}
        return {'validation_id': validation.id, 'validation_hash': validation.content_hash,
            'proposal_id': proposal.id, 'proposal_hash': proposal.content_hash,
            'snapshot_id': snapshot.id, 'snapshot_hash': snapshot.content_hash,
            'producer_identity': 'line-reader', 'reviewer_kind': 'human', 'reviewer_identity': 'Rob.Reviewer',
            'criteria_id': semantic_review.CRITERIA_ID, 'criteria_sha256': semantic_review.CRITERIA_SHA256,
            'decisions': [{'observation_id': item['observation_id'], 'status': statuses[item['observation_id']],
                'grounding_verdict': item['verdict'], 'verdict': 'acceptable', 'reason': 'fixture',
                'unresolved_issues': []} for item in validation.data['verdicts'] if item['verdict'] != 'not_grounded']}

    def _forge(self, record, changes=None, drop=()):
        data = self._plain(record.data)
        data.update(changes or {})
        for key in drop:
            del data[key]
        return self.ledger.add(record.kind, data)

    def _release(self, run, *, binding=None, review=None, actor='Release.Clerk'):
        binding = run['reader_proposal'] if binding is None else binding
        review = run['review'] if review is None else review
        return self.engine.release_reader(binding.id, binding.content_hash, review.id, review.content_hash, actor)

    def _reopen(self):
        if self.sqlite:
            self.ledger = SQLiteLedger(self.database)
            self.engine = Ripley(self.ledger, capture_store=self.store)

    def _without_writes(self, call):
        before, states = list(self.ledger.records), self._states()
        with self.assertRaises(ValueError):
            call()
        self.assertEqual(list(self.ledger.records), before)
        self.assertEqual(self._states(), states)

    def _refuse(self, reason, call):
        before, states = list(self.ledger.records), self._states()
        result = call()
        self.assertEqual(set(result), {'outcome', 'release', 'approval', 'refusal', 'task_state'})
        self.assertEqual(result['outcome'], 'refused')
        self.assertIsNone(result['release'])
        self.assertIsNone(result['approval'])
        self.assertIsNone(result['task_state'])
        refusal = result['refusal']
        self.assertEqual(refusal.kind, 'reader_release_refusal')
        self.assertEqual(set(refusal.data), {'reader_proposal_id', 'semantic_review_id', 'released_by', 'reason'})
        self.assertEqual(refusal.data['reason'], reason)
        self.assertEqual(list(self.ledger.records), before + [refusal.id])
        self.assertEqual(self._states(), states)
        return result

    def _fail_write(self, number):
        original = self.ledger.add
        calls = 0

        def add(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == number:
                raise RuntimeError('injected ledger write failure')
            return original(*args, **kwargs)
        return patch.object(self.ledger, 'add', side_effect=add)

    def _package(self, run, *, release_changes=None, pending_changes=None):
        binding, review = run['reader_proposal'], run['review']
        failure, facts = self.engine._reader_release_facts(binding.id, binding.content_hash,
                                                           review.id, review.content_hash)
        self.assertIsNone(failure)
        release = self.ledger.add('reader_release', {**dict(facts), 'released_by': 'Fixture.Clerk',
                                                    **(release_changes or {})})
        pending = self.ledger.add('approval', {'task_id': facts['task_id'], 'release_id': release.id,
            'release_hash': release.content_hash, 'authority': 'owner', 'status': 'pending_reader_owner_approval',
            **{key: facts[key] for key in SCOPE_KEYS}, **(pending_changes or {})})
        self.ledger.transition(run['task'].id, 'awaiting_semantic_review', 'pending_owner_approval',
                               'Fixture.Clerk', 'hand-built fixture')
        return release, pending


class _ReleaseCases(_ReleaseFixture):
    def test_rr_01_eligible_release(self):
        run = self._task(('asserted', 'uncertain', 'not_found', 'bad'))
        self.assertEqual(self.ledger.task_state(run['task'].id), 'awaiting_semantic_review')
        self.assertEqual(self._records('approval'), [])
        self.assertEqual(self._records('reader_release'), [])
        before = list(self.ledger.records)
        result = self._release(run)
        self.assertEqual(set(result), {'outcome', 'release', 'approval', 'refusal', 'task_state'})
        self.assertEqual((result['outcome'], result['task_state'], result['refusal']),
                         ('eligible', 'pending_owner_approval', None))
        release, pending = result['release'], result['approval']
        self.assertEqual(set(release.data), FACT_KEYS | {'released_by'})
        for name in ('reader_proposal', 'semantic_review'):
            record = run['reader_proposal'] if name == 'reader_proposal' else run['review']
            self.assertEqual(release.data[name + '_id'], record.id)
            self.assertEqual(release.data[name + '_hash'], record.content_hash)
        self.assertEqual(release.data['task_id'], run['task'].id)
        self.assertEqual((release.data['producer_identity'], release.data['reviewer_identity'],
            release.data['released_by'], release.data['disposition']),
            ('line-reader', 'Rob.Reviewer', 'Release.Clerk', 'eligible'))
        for key, value in zip(SCOPE_KEYS, [('o1', 'o2', 'o3'), ('o2',), ('o3',), ('o4',)]):
            self.assertEqual(release.data[key], value)
            self.assertEqual(pending.data[key], value)
        self.assertEqual(release.data['rejected_observation_ids'], ())
        self.assertEqual(release.data['clarification_observation_ids'], ())
        self.assertEqual(set(pending.data), PENDING_KEYS)
        self.assertEqual(pending.kind, 'approval')
        self.assertIsNone(pending.supersedes)
        self.assertEqual((pending.data['task_id'], pending.data['release_id'], pending.data['release_hash'],
            pending.data['authority'], pending.data['status']),
            (run['task'].id, release.id, release.content_hash, 'owner', 'pending_reader_owner_approval'))
        added = [r for r in self.ledger.records.values() if r.id not in before]
        self.assertEqual([r.kind for r in added], ['reader_release', 'approval', 'task_transition'])
        transition = added[-1]
        self.assertEqual((transition.data['from_state'], transition.data['to_state'],
            transition.data['actor'], transition.data['reason']),
            ('awaiting_semantic_review', 'pending_owner_approval', 'Release.Clerk', 'reader_release_eligible'))
        self.assertEqual({r.data['status'] for r in self._records('approval')}, {'pending_reader_owner_approval'})
        self._reopen()
        self.assertEqual(self.ledger.task_state(run['task'].id), 'pending_owner_approval')
        self.assertEqual(self.ledger.records[pending.id].content_hash, pending.content_hash)

    def test_rr_02_owner_approves_subset(self):
        run = self._task(('asserted', 'uncertain', 'not_found', 'bad'))
        pending = self._release(run)['approval']
        review_hash = run['review'].content_hash
        self._reopen()
        before = list(self.ledger.records)
        judgment = self.engine.decide_reader_approval(pending.id, 'owner', 'approved', 'Accept this bounded package.')
        self.assertEqual(self.ledger.task_state(run['task'].id), 'approved')
        self.assertEqual(set(pending.data), PENDING_KEYS)
        self.assertIsNone(pending.supersedes)
        self.assertEqual(judgment.kind, 'approval')
        self.assertEqual(set(judgment.data), PENDING_KEYS | {'reason'})
        self.assertEqual(judgment.supersedes, pending.id)
        self.assertNotIn('supersedes', judgment.data)
        self.assertEqual(dict(judgment.data), dict(pending.data, authority='owner', status='approved',
                                                reason='Accept this bounded package.'))
        for key, value in zip(SCOPE_KEYS, [('o1', 'o2', 'o3'), ('o2',), ('o3',), ('o4',)]):
            self.assertEqual(judgment.data[key], value)
        added = [r for r in self.ledger.records.values() if r.id not in before]
        self.assertEqual([r.kind for r in added], ['approval', 'task_transition'])
        self.assertEqual((added[-1].data['from_state'], added[-1].data['to_state'], added[-1].data['actor']),
                         ('pending_owner_approval', 'approved', 'owner'))
        self.assertEqual(tuple(o['status'] for o in run['proposal'].data['proposal']['observations']),
                         ('asserted', 'uncertain', 'not_found', 'asserted'))
        self.assertEqual(self.ledger.records[run['review'].id].content_hash, review_hash)

    def test_rr_03_owner_rejects(self):
        run = self._task(('asserted', 'uncertain'))
        pending = self._release(run)['approval']
        judgment = self.engine.decide_reader_approval(pending.id, 'owner', 'rejected', 'Owner declines.')
        self.assertEqual(self.ledger.task_state(run['task'].id), 'rejected')
        self.assertEqual(set(judgment.data), PENDING_KEYS | {'reason'})
        self.assertEqual(judgment.supersedes, pending.id)
        self.assertEqual((judgment.data['status'], judgment.data['reason'], judgment.data['uncertain_observation_ids']),
                         ('rejected', 'Owner declines.', ('o2',)))
        self.assertEqual(len(self._records('approval', run['task'])), 2)

    def test_rr_04_negative_reviews_block(self):
        cases = [({'o1': 'rejected'}, 'rejected', ('o1',), ()),
                 ({'o2': 'needs_clarification'}, 'needs_clarification', (), ('o2',)),
                 ({'o1': 'needs_clarification', 'o2': 'needs_clarification', 'o3': 'rejected'},
                  'rejected', ('o3',), ('o1', 'o2'))]
        for overrides, disposition, rejected, unclear in cases:
            run = self._task(('asserted', 'uncertain', 'not_found'), overrides=overrides)
            self.assertEqual(self.ledger.task_state(run['task'].id), 'awaiting_semantic_review')
            before = list(self.ledger.records)
            result = self._release(run)
            self.assertEqual((result['outcome'], result['task_state'], result['approval'], result['refusal']),
                             ('blocked', 'blocked', None, None))
            release = result['release']
            self.assertEqual(set(release.data), FACT_KEYS | {'released_by'})
            self.assertEqual(release.data['disposition'], disposition)
            for key in SCOPE_KEYS[:3]:
                self.assertEqual(release.data[key], ())
            self.assertEqual(release.data['rejected_observation_ids'], rejected)
            self.assertEqual(release.data['clarification_observation_ids'], unclear)
            added = [r for r in self.ledger.records.values() if r.id not in before]
            self.assertEqual([r.kind for r in added], ['reader_release', 'task_transition'])
            self.assertEqual((added[-1].data['to_state'], added[-1].data['reason']),
                             ('blocked', 'semantic_review_' + disposition))
            self.assertEqual(self._records('approval', run['task']), [])
            for item in run['review'].data['decisions']:
                self.assertEqual(item['verdict'], overrides.get(item['observation_id'], 'acceptable'))
                if item['verdict'] == 'needs_clarification':
                    self.assertTrue(item['unresolved_issues'])
            self._reopen()
            before = list(self.ledger.records)
            repeated = self._release(run)
            self.assertEqual((repeated['outcome'], repeated['release'].id), ('blocked', release.id))
            self.assertEqual(list(self.ledger.records), before)
        self.assertEqual(self._records('approval'), [])

    def test_rr_05_arguments_and_derived_lists(self):
        self.assertEqual(list(inspect.signature(Ripley.release_reader).parameters),
            ['self', 'reader_proposal_id', 'reader_proposal_hash', 'semantic_review_id', 'semantic_review_hash', 'actor'])
        self.assertEqual(list(inspect.signature(Ripley.decide_reader_approval).parameters),
                         ['self', 'pending_id', 'actor', 'decision', 'reason'])
        run = self._task(('bad', 'asserted', 'bad', 'not_found'))
        args = [run['reader_proposal'].id, run['reader_proposal'].content_hash,
                run['review'].id, run['review'].content_hash, 'Release.Clerk']
        for index in range(4):
            invalid = list(args)
            invalid[index] = None
            self._without_writes(lambda invalid=invalid: self.engine.release_reader(*invalid))
        for actor in ('', ' ', None, 'x' * 129):
            self._without_writes(lambda actor=actor: self.engine.release_reader(*args[:4], actor))
        result = self._release(run, actor='x' * 128)
        self.assertEqual(result['release'].data['released_by'], 'x' * 128)
        for key, value in zip(SCOPE_KEYS, [('o2', 'o4'), (), ('o4',), ('o1', 'o3')]):
            self.assertEqual(result['release'].data[key], value)

    def test_rr_06_binding_and_task_refusals(self):
        run, other = self._task(), self._task()
        b, review = run['reader_proposal'], run['review']
        for identity in ('00000000-0000-0000-0000-000000000000', run['task'].id):
            self._refuse('binding_unavailable', lambda identity=identity:
                self.engine.release_reader(identity, b.content_hash, review.id, review.content_hash, 'Release.Clerk'))
        self._refuse('binding_hash_mismatch', lambda: self.engine.release_reader(
            b.id, '0' * 64, review.id, review.content_hash, 'Release.Clerk'))
        forged = self._forge(b, {'reasoning_close_hash': other['reasoning_close'].content_hash})
        self._refuse('chain_broken', lambda: self._release(run, binding=forged))
        ordinary = self.engine.run(InventoryAdapter(), {'stock': 10, 'demand': 3, 'threshold': 8})
        forged = self._forge(b, {'task_id': ordinary['task'].id})
        with patch.object(self.engine, 'reader_chain', return_value={'outcome': 'verified'}):
            self._refuse('task_unavailable', lambda: self._release(run, binding=forged))
        refusal = self._refuse('binding_unavailable', lambda: self.engine.release_reader(
            'x' * 65, b.content_hash, review.id, review.content_hash, 'Release.Clerk'))
        self.assertIsNone(refusal['refusal'].data['reader_proposal_id'])
        self.assertEqual(self._records('reader_release'), [])
        self.assertEqual([r.id for r in self._records('approval')], [ordinary['approval'].id])
        blocked = self._task()
        self.ledger.transition(blocked['task'].id, 'awaiting_semantic_review', 'blocked', 'Fixture.Clerk', 'raw fixture')
        self._refuse('task_not_awaiting_review', lambda: self._release(blocked))
        self.assertEqual(self._release(run)['outcome'], 'eligible')

    def test_rr_07_review_refusals(self):
        run, other = self._task(), self._task()
        b, review = run['reader_proposal'], run['review']
        self._refuse('semantic_review_missing', lambda: self.engine.release_reader(
            b.id, b.content_hash, 'unknown', review.content_hash, 'Release.Clerk'))
        self._refuse('semantic_review_wrong_kind', lambda: self._release(run, review=run['grounding_validation']))
        self._refuse('semantic_review_wrong_validation', lambda: self._release(run, review=other['review']))
        self._refuse('semantic_review_hash_mismatch', lambda: self.engine.release_reader(
            b.id, b.content_hash, review.id, '0' * 64, 'Release.Clerk'))
        for change, reason in [({'proposal_hash': '0' * 64}, 'semantic_review_wrong_proposal'),
                ({'snapshot_id': other['snapshot'].id}, 'semantic_review_wrong_snapshot'),
                ({'criteria_sha256': '0' * 64}, 'criteria_mismatch'),
                ({'criteria_id': 'other-criteria'}, 'criteria_mismatch'),
                ({'producer_identity': 'other-worker'}, 'producer_mismatch'),
                ({'reviewer_kind': 'model'}, 'reviewer_invalid'),
                ({'reviewer_identity': ''}, 'reviewer_invalid'),
                ({'reviewer_identity': 'line-reader'}, 'reviewer_is_producer'),
                ({'reviewer_identity': 'LINE-READER'}, 'reviewer_is_producer')]:
            forged = self._forge(review, change)
            self._refuse(reason, lambda forged=forged: self._release(run, review=forged))
        twin = self._forge(review)
        for selected in (review, twin):
            self._refuse('semantic_review_conflict', lambda selected=selected: self._release(run, review=selected))
        self.assertEqual(self._records('reader_release'), [])
        self.assertEqual(self._records('approval'), [])
        refusal = self._review(self._task(review=False), reviewer='line-reader')
        self.assertEqual(refusal.data['reason'], 'reviewer_is_producer')

    def test_rr_08_decision_coverage(self):
        changes = [lambda d: d['decisions'].pop(),
            lambda d: d['decisions'].append(dict(d['decisions'][0], observation_id='extra')),
            lambda d: d['decisions'].reverse(),
            lambda d: d['decisions'][0].update(status='uncertain'),
            lambda d: d['decisions'][0].update(grounding_verdict='not_grounded'),
            lambda d: d['decisions'][0].update(verdict='approved')]
        for change in changes:
            run = self._task(('asserted', 'uncertain', 'not_found'), review=False)
            data = self._review_data(run)
            change(data)
            review = self.ledger.add('semantic_review', data)
            self._refuse('decision_coverage_invalid', lambda: self._release(run, review=review))
        for change in [lambda d: d['decisions'][0].pop('verdict'),
                       lambda d: d.update(decisions='not a list'), lambda d: d.pop('decisions')]:
            run = self._task(review=False)
            data = self._review_data(run)
            change(data)
            review = self.ledger.add('semantic_review', data)
            self._refuse('semantic_review_malformed', lambda: self._release(run, review=review))
        run = self._task(review=False)
        validation_data = self._plain(run['grounding_validation'].data)
        for item in validation_data['verdicts']:
            item['verdict'] = 'not_grounded'
        validation = self.ledger.add('grounding_validation', validation_data)
        binding = self._forge(run['reader_proposal'], {'grounding_validation_id': validation.id,
                                                      'grounding_validation_hash': validation.content_hash})
        data = self._review_data(dict(run, grounding_validation=validation))
        review = self.ledger.add('semantic_review', data)
        self._refuse('no_eligible_observations', lambda: self._release(run, binding=binding, review=review))
        blocked = self._task(('bad',), review=False, bound=False)
        self.assertIsNone(blocked['reader_proposal'])
        self.assertEqual(self._records('reader_release'), [])
        self.assertEqual(self._records('approval'), [])

    def test_rr_09_repeat_release(self):
        run = self._task()
        first = self._release(run)
        self._reopen()
        for actor in ('Release.Clerk', 'Another.Clerk'):
            before = list(self.ledger.records)
            repeated = self._release(run, actor=actor)
            self.assertEqual((repeated['outcome'], repeated['task_state']), ('eligible', 'pending_owner_approval'))
            self.assertEqual((repeated['release'].id, repeated['approval'].id),
                             (first['release'].id, first['approval'].id))
            self.assertEqual(repeated['release'].data['released_by'], 'Release.Clerk')
            self.assertEqual(list(self.ledger.records), before)
        twin = self._forge(run['reader_proposal'])
        self._refuse('release_conflict', lambda: self._release(run, binding=twin))
        self.assertEqual(self.ledger.task_state(run['task'].id), 'pending_owner_approval')
        self.assertEqual(len(self._records('reader_release')), 1)
        self.assertEqual(len(self._records('approval')), 1)
        self.engine.decide_reader_approval(first['approval'].id, 'owner', 'approved', 'Owner accepts.')
        before = list(self.ledger.records)
        repeated = self._release(run)
        self.assertEqual((repeated['outcome'], repeated['task_state']), ('eligible', 'approved'))
        self.assertEqual(list(self.ledger.records), before)

    def test_rr_10_interrupted_release(self):
        for negative, writes in ((False, (1, 2, 3)), (True, (1, 2))):
            for fail_at in writes:
                with self.subTest(negative=negative, fail_at=fail_at):
                    run = self._task(overrides={'o1': 'rejected'} if negative else None)
                    counts = self._counts(EXECUTION_KINDS + ('semantic_review',))
                    with self._fail_write(fail_at):
                        with self.assertRaisesRegex(RuntimeError, 'injected ledger write failure'):
                            self._release(run)
                    self._reopen()
                    task = run['task']
                    self.assertEqual(self.ledger.task_state(task.id), 'awaiting_semantic_review')
                    self.assertEqual(len(self._records('reader_release', task)), int(fail_at > 1))
                    pending = self._records('approval', task)
                    self.assertEqual(len(pending), int(not negative and fail_at > 2))
                    for record in pending:
                        for decision in ('approved', 'rejected'):
                            for method in (self.engine.decide_reader_approval, self.engine.decide_approval):
                                self._without_writes(lambda method=method, decision=decision:
                                    method(record.id, 'owner', decision, 'Cannot decide partial release.'))
                    result = self._release(run)
                    self.assertEqual((result['outcome'], result['task_state']),
                                     ('blocked', 'blocked') if negative else ('eligible', 'pending_owner_approval'))
                    self.assertEqual(len(self._records('reader_release', task)), 1)
                    self.assertEqual(len(self._records('approval', task)), 0 if negative else 1)
                    self.assertEqual(self._counts(EXECUTION_KINDS + ('semantic_review',)), counts)
                    if not negative:
                        judgment = self.engine.decide_reader_approval(result['approval'].id, 'owner',
                                                                      'approved', 'Approve after completion.')
                        self.assertEqual(judgment.data['status'], 'approved')

    def test_rr_11_route_isolation(self):
        run = self._task()
        pending = self._release(run)['approval']
        self.assertEqual(pending.data['status'], 'pending_reader_owner_approval')
        self.assertNotEqual(pending.data['status'], 'pending_owner_approval')
        for decision in ('approved', 'rejected'):
            self._without_writes(lambda decision=decision:
                self.engine.decide_approval(pending.id, 'owner', decision, 'Wrong route.'))
        ordinary = self.engine.run(InventoryAdapter(), {'stock': 10, 'demand': 3, 'threshold': 8})
        legacy = ordinary['approval']
        self.assertEqual(set(legacy.data), {'evidence_id', 'evidence_hash', 'task_id',
                                          'result_hash', 'authority', 'status'})
        for decision in ('approved', 'rejected'):
            self._without_writes(lambda decision=decision:
                self.engine.decide_reader_approval(legacy.id, 'owner', decision, 'Wrong route.'))
        self._reopen()
        judgment = self.engine.decide_reader_approval(pending.id, 'owner', 'approved', 'Reader decision.')
        for decision in ('approved', 'rejected'):
            self._without_writes(lambda decision=decision:
                self.engine.decide_approval(judgment.id, 'owner', decision, 'Wrong route.'))
        legacy_judgment = self.engine.decide_approval(legacy.id, 'owner', 'approved', 'Legacy decision.')
        self.assertEqual(legacy_judgment.data['status'], 'approved')
        self.assertEqual(self.ledger.task_state(ordinary['task'].id), 'approved')

    def test_rr_12_owner_arguments(self):
        run = self._task()
        result = self._release(run)
        pending = result['approval']
        for args in [(pending.id, 'Release.Clerk', 'approved', 'reason'),
                (pending.id, 'Owner', 'approved', 'reason'), (pending.id, 'owner', 'approve', 'reason'),
                (pending.id, 'owner', 'acceptable', 'reason'), (pending.id, 'owner', 'approved', ' '),
                (pending.id, 'owner', 'approved', None), (None, 'owner', 'approved', 'reason'),
                ('unknown', 'owner', 'approved', 'reason'), (result['release'].id, 'owner', 'approved', 'reason'),
                (run['task'].id, 'owner', 'approved', 'reason')]:
            self._without_writes(lambda args=args: self.engine.decide_reader_approval(*args))
        self.assertEqual(self.ledger.task_state(run['task'].id), 'pending_owner_approval')

    def test_rr_13_owner_reverifies(self):
        def refused_both(pending):
            for decision in ('approved', 'rejected'):
                self._without_writes(lambda decision=decision:
                    self.engine.decide_reader_approval(pending.id, 'owner', decision, 'Verify the exact package.'))

        run = self._task()
        pending = self._release(run)['approval']
        self._forge(run['review'])
        refused_both(pending)
        run = self._task()
        pending = self._release(run)['approval']
        with patch.object(self.engine, 'reader_chain', return_value={'outcome': 'broken'}):
            refused_both(pending)
        run = self._task(('asserted', 'uncertain'), overrides={'o1': 'rejected'})
        _, pending = self._package(run, release_changes={
            'disposition': 'eligible', 'included_observation_ids': ('o1', 'o2'),
            'uncertain_observation_ids': ('o2',)})
        refused_both(pending)
        cases = [({'reviewer_identity': 'Other.Reviewer'}, None, None),
            ({'producer_identity': 'other-worker'}, None, None),
            (None, {'included_observation_ids': ('o1', 'o2', 'o3', 'o4')}, None),
            (None, {'excluded_observation_ids': ()}, None),
            (None, {'uncertain_observation_ids': ()}, None),
            (None, {'release_hash': '0' * 64}, None),
            (None, None, {'o1': 'rejected'}), (None, None, {'o2': 'needs_clarification'})]
        for release_changes, pending_changes, overrides in cases:
            run = self._task(('asserted', 'uncertain', 'not_found', 'bad'), overrides=overrides)
            _, pending = self._package(run, release_changes=release_changes, pending_changes=pending_changes)
            refused_both(pending)
            self.assertEqual(self.ledger.task_state(run['task'].id), 'pending_owner_approval')
        run = self._task(('asserted', 'uncertain', 'not_found', 'bad'))
        _, valid = self._package(run)
        self.assertEqual(self.engine.decide_reader_approval(valid.id, 'owner', 'approved',
                                                          'All derived facts match.').data['status'], 'approved')
        for key, value in [('included_observation_ids', ('o1', 'o2', 'o3', 'o4')),
                ('excluded_observation_ids', ()), ('uncertain_observation_ids', ()),
                ('not_found_observation_ids', ()), ('release_hash', '0' * 64), ('task_id', run['task'].id)]:
            current = self._task(('asserted', 'uncertain', 'not_found', 'bad'))
            genuine = self._release(current)['approval']
            forged = self._forge(genuine, {key: value})
            refused_both(forged)
            refused_both(genuine)
        current = self._task()
        genuine = self._release(current)['approval']
        forged = self._forge(genuine, {'release_id': '00000000-0000-0000-0000-000000000000'})
        refused_both(forged)
        self.assertEqual(self.engine.decide_reader_approval(genuine.id, 'owner', 'approved',
                                                          'Unrelated fake does not consume this release.').data['status'], 'approved')
        current = self._task(('asserted', 'uncertain', 'not_found', 'bad'))
        result = self._release(current)
        forged_release = self._forge(result['release'], {'included_observation_ids': ('o1', 'o2', 'o3', 'o4')})
        forged_pending = self._forge(result['approval'], {'release_id': forged_release.id,
                                                         'release_hash': forged_release.content_hash})
        refused_both(forged_pending)
        refused_both(result['approval'])
        current = self._task()
        self.ledger.transition(current['task'].id, 'awaiting_semantic_review', 'pending_owner_approval',
                               'Fixture.Clerk', 'raw transition alone')
        self.assertEqual(self._records('approval', current['task']), [])

    def test_rr_14_repeat_and_opposite_decisions(self):
        for first, opposite in [('approved', 'rejected'), ('rejected', 'approved')]:
            run = self._task(('asserted', 'uncertain'))
            pending = self._release(run)['approval']
            judgment = self.engine.decide_reader_approval(pending.id, 'owner', first, 'Original owner reason.')
            self._reopen()
            before = list(self.ledger.records)
            repeated = self.engine.decide_reader_approval(pending.id, 'owner', first, 'Different repeat reason.')
            self.assertEqual(repeated.id, judgment.id)
            self.assertEqual(repeated.data['reason'], 'Original owner reason.')
            self.assertEqual(repeated.data['status'], first)
            self.assertEqual(set(repeated.data), PENDING_KEYS | {'reason'})
            self.assertEqual(repeated.supersedes, pending.id)
            self.assertNotIn('supersedes', repeated.data)
            self.assertEqual(list(self.ledger.records), before)
            self._without_writes(lambda: self.engine.decide_reader_approval(pending.id, 'owner', opposite, 'Conflict.'))
            self._without_writes(lambda: self.engine.decide_reader_approval(judgment.id, 'owner', first, 'Not pending.'))
            self.assertEqual(self.ledger.task_state(run['task'].id), first)
            self.assertEqual([r.supersedes for r in self._records('approval', run['task'])], [None, pending.id])

    def test_rr_15_interrupted_owner_decision(self):
        for fail_at in (1, 2):
            run = self._task(('asserted', 'uncertain'))
            pending = self._release(run)['approval']
            with self._fail_write(fail_at):
                with self.assertRaisesRegex(RuntimeError, 'injected ledger write failure'):
                    self.engine.decide_reader_approval(pending.id, 'owner', 'approved', 'Original owner reason.')
            self._reopen()
            self.assertEqual(self.ledger.task_state(run['task'].id), 'pending_owner_approval')
            self.assertEqual(len(self._records('approval', run['task'])), fail_at)
            if fail_at == 2:
                self._without_writes(lambda: self.engine.decide_reader_approval(pending.id, 'owner', 'rejected', 'Opposite.'))
            before = list(self.ledger.records)
            judgment = self.engine.decide_reader_approval(pending.id, 'owner', 'approved', 'Repeated owner reason.')
            added = [r for r in self.ledger.records.values() if r.id not in before]
            self.assertEqual([r.kind for r in added], ['approval', 'task_transition'] if fail_at == 1 else ['task_transition'])
            reason = 'Repeated owner reason.' if fail_at == 1 else 'Original owner reason.'
            self.assertEqual(judgment.data['reason'], reason)
            self.assertEqual(added[-1].data['reason'], reason)
            self.assertEqual(self.ledger.task_state(run['task'].id), 'approved')
            self.assertEqual(set(judgment.data), PENDING_KEYS | {'reason'})
            self.assertEqual(judgment.supersedes, pending.id)
            self.assertNotIn('supersedes', judgment.data)
            self.assertEqual([r.supersedes for r in self._records('approval', run['task'])], [None, pending.id])

    def test_rr_16_no_execution_exact_transitions(self):
        self.assertEqual(core.READER_SCOPE_KEYS, SCOPE_KEYS)
        self.assertEqual(core.ALLOWED_TRANSITIONS, {
            'submitted': {'running', 'blocked'}, 'running': {'validated', 'blocked', 'awaiting_semantic_review'},
            'awaiting_semantic_review': {'pending_owner_approval', 'blocked'},
            'validated': {'pending_owner_approval', 'blocked'}, 'blocked': set(),
            'pending_owner_approval': {'approved', 'rejected'}, 'approved': set(), 'rejected': set()})
        run = self._task(('asserted', 'uncertain'), review=False)
        for state in ('approved', 'rejected', 'validated', 'running', 'submitted'):
            self._without_writes(lambda state=state: self.ledger.transition(
                run['task'].id, 'awaiting_semantic_review', state, 'owner', 'not an allowed edge'))
        counts, kinds = self._counts(), {r.kind for r in self.ledger.records.values()}
        with patch.object(isolation, 'observe_subprocess', side_effect=AssertionError('execution forbidden')), \
                patch.object(reasoning_envelope, 'open_attempt', side_effect=AssertionError('reservation forbidden')), \
                patch.object(Ripley, 'run_reader', side_effect=AssertionError('reader forbidden')), \
                patch.object(Ripley, '_execute', side_effect=AssertionError('execution forbidden')):
            run['review'] = self._review(run)
            pending = self._release(run)['approval']
            judgment = self.engine.decide_reader_approval(pending.id, 'owner', 'approved', 'Owner decision only.')
        self.assertEqual(judgment.data['status'], 'approved')
        self.assertEqual(self._counts(), counts)
        self.assertEqual({r.kind for r in self.ledger.records.values()} - kinds,
                         {'semantic_review', 'reader_release', 'approval'})
        for method in (Ripley._reader_release_facts, Ripley.release_reader, Ripley.decide_reader_approval):
            source = inspect.getsource(method)
            for word in ('observe_subprocess', 'open_attempt', 'run_reader', '_execute',
                         'providers', 'anthropic', 'capture_store', 'isolation'):
                self.assertNotIn(word, source)


class MemoryReaderReleaseTests(_ReleaseCases, unittest.TestCase):
    pass


class SQLiteReaderReleaseTests(_ReleaseCases, unittest.TestCase):
    sqlite = True
