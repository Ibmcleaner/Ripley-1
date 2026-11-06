"""Domain-neutral in-memory execution; not durable storage or secure authorization."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
import copy
import uuid


def freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(v) for v in value)
    return copy.deepcopy(value)


@dataclass(frozen=True)
class Record:
    id: str
    kind: str
    at: str
    data: object
    supersedes: str | None = None


class Ledger:
    """Append-only through public methods; read-only view prevents direct replacement."""
    def __init__(self):
        self._records = {}

    @property
    def records(self):
        return MappingProxyType(self._records)

    def add(self, kind, data, supersedes=None):
        if supersedes:
            previous = self._records[supersedes]
            if previous.kind != kind or kind not in ('review', 'event_assessment', 'classification', 'approval'):
                raise ValueError('only judgments may supersede judgments of the same kind')
        record = Record(str(uuid.uuid4()), kind, datetime.now(timezone.utc).isoformat(),
                        freeze(data), supersedes)
        self._records[record.id] = record
        return record

    def task_state(self, task_id):
        task = self._records[task_id]
        if task.kind != 'task':
            raise ValueError('not a task')
        transitions = [r for r in self._records.values()
                       if r.kind == 'task_transition' and r.data['task_id'] == task_id]
        return transitions[-1].data['to_state'] if transitions else task.data['state']

    def transition(self, task_id, from_state, to_state, actor, reason):
        current = self.task_state(task_id)
        if current != from_state:
            raise ValueError('stale task state')
        allowed = {'submitted': {'running'}, 'running': {'validated', 'blocked'},
                   'validated': {'pending_owner_approval'}, 'blocked': set(),
                   'pending_owner_approval': set()}
        if to_state not in allowed[current]:
            raise ValueError('invalid state transition')
        prior = next((r.id for r in reversed(tuple(self._records.values()))
                      if r.kind == 'task_transition' and r.data['task_id'] == task_id), None)
        return self.add('task_transition', {'task_id': task_id, 'from_state': from_state,
                        'to_state': to_state, 'actor': actor, 'reason': reason,
                        'preceding_transition_id': prior})


class MockWorker:
    identity = 'mock-worker'
    def produce(self, task, snapshot, adapter):
        return adapter.predict(snapshot.data['inputs'])


class IndependentValidator:
    identity = 'independent-validator'
    version = '1'
    ruleset = 'output-shape-v1'

    def validate(self, result, adapter):
        output = result.data['output']
        expected = adapter.expected_output
        passed = isinstance(output, Mapping) and set(output) == set(expected) and all(
            type(output[k]) is t for k, t in expected.items())
        return {'result_id': result.id, 'validator': self.identity,
                'validator_version': self.version, 'ruleset': self.ruleset,
                'passed': passed}


class Ripley:
    def __init__(self, ledger=None, validator=None):
        self.ledger = ledger if ledger is not None else Ledger()
        self.validator = validator if validator is not None else IndependentValidator()

    def run(self, adapter, inputs, worker=None, allowed_workers=('mock-worker',),
            correction_budget=1):
        if type(correction_budget) is not int or correction_budget < 0:
            raise ValueError('correction_budget must be a nonnegative integer')
        worker = worker if worker is not None else MockWorker()
        if worker.identity not in allowed_workers:
            raise PermissionError('worker not allowed')
        if worker is self.validator or worker.identity == self.validator.identity:
            raise PermissionError('worker cannot independently validate its own result')
        # Domain adapter owns snapshot provenance and data-quality declarations.
        metadata = adapter.snapshot_metadata(inputs)
        snapshot = self.ledger.add('snapshot', {'domain_id': adapter.domain_id, 'inputs': inputs,
            'observed_at': metadata['observed_at'], 'sources': metadata['sources'],
            'data_quality': metadata['data_quality'], 'domain_version': adapter.version})
        task = self.ledger.add('task', {'domain_id': adapter.domain_id, 'task_type': 'predict',
            'input_snapshot_id': snapshot.id, 'dependencies': [], 'allowed_workers': allowed_workers,
            'expected_output': tuple(adapter.expected_output), 'validation_requirements': ('independent',),
            'evidence_requirements': ('linked-records',), 'resource_ceiling': 'no external calls',
            'state': 'submitted'})
        self.ledger.transition(task.id, 'submitted', 'running', 'ripley', 'execution started')
        results = []
        validations = []
        reviews = []
        corrections = []
        for attempt_number in range(correction_budget + 1):
            attempt = self.ledger.add('execution_attempt', {'task_id': task.id,
                'worker': worker.identity, 'attempt_number': attempt_number + 1})
            try:
                output = worker.produce(task, snapshot, adapter)
            except Exception as exc:
                failure = self.ledger.add('execution_failure', {'task_id': task.id,
                    'attempt_id': attempt.id, 'exception_type': type(exc).__name__,
                    'message': str(exc)})
                self.ledger.transition(task.id, 'running', 'blocked', 'ripley', 'worker_failure')
                return {'task': task, 'snapshot': snapshot, 'attempt': attempt,
                        'failure': failure, 'results': tuple(results)}
            result = self.ledger.add('result', {'task_id': task.id, 'attempt_id': attempt.id,
                'input_snapshot_id': snapshot.id, 'worker': worker.identity, 'output': output,
                'evidence': (), 'warnings': (), 'execution': 'deterministic', 'cost': 0})
            results.append(result)
            finding = self.validator.validate(result, adapter)
            if finding.get('result_id') != result.id or finding.get('validator') != self.validator.identity:
                raise ValueError('validation provenance mismatch')
            validation = self.ledger.add('validation', finding)
            validations.append(validation)
            review = self.ledger.add('review', {'result_id': result.id, 'validation_id': validation.id,
                'reviewer': 'ripley-review-policy',
                'decision': 'acceptable' if finding['passed'] else 'correction_required'})
            reviews.append(review)
            if finding['passed']:
                self.ledger.transition(task.id, 'running', 'validated', 'ripley', 'review accepted')
                evidence = self.ledger.add('evidence', {'task_id': task.id, 'snapshot_id': snapshot.id,
                    'result_id': result.id, 'validation_id': validation.id, 'review_id': review.id})
                approval = self.ledger.add('approval', {'evidence_id': evidence.id,
                    'authority': 'owner', 'status': 'pending_owner_approval'})
                self.ledger.transition(task.id, 'validated', 'pending_owner_approval',
                                       'ripley', 'awaiting owner')
                return {'task': task, 'snapshot': snapshot, 'attempt': attempt, 'result': result,
                        'validation': validation, 'review': review, 'evidence': evidence,
                        'approval': approval, 'results': tuple(results),
                        'validations': tuple(validations), 'reviews': tuple(reviews),
                        'corrections': tuple(corrections)}
            if attempt_number < correction_budget:
                corrections.append(self.ledger.add('correction_request', {
                    'task_id': task.id, 'rejected_result_id': result.id,
                    'review_id': review.id, 'reason': 'invalid output structure'}))
            else:
                blocked = self.ledger.add('correction_budget_exhaustion', {
                    'task_id': task.id, 'last_result_id': result.id, 'budget': correction_budget})
                self.ledger.transition(task.id, 'running', 'blocked', 'ripley',
                                       'correction_budget_exhausted')
                return {'task': task, 'snapshot': snapshot, 'result': result,
                        'validation': validation, 'review': review, 'blocked': blocked,
                        'results': tuple(results), 'validations': tuple(validations),
                        'reviews': tuple(reviews), 'corrections': tuple(corrections)}

    def revise_review(self, prior_id, reviewer, decision, reason):
        prior = self.ledger.records[prior_id]
        if prior.kind != 'review':
            raise ValueError('not a review')
        return self.ledger.add('review', {'result_id': prior.data['result_id'],
            'validation_id': prior.data['validation_id'], 'reviewer': reviewer,
            'decision': decision, 'reason': reason}, supersedes=prior_id)
