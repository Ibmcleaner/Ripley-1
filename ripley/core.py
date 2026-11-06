"""Domain-neutral, in-memory append-only execution skeleton; not persistent storage."""
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from collections.abc import Mapping
import copy
import uuid

def freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
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
    def __init__(self):
        self.records = {}
    def add(self, kind, data, supersedes=None):
        if supersedes:
            previous = self.records[supersedes]
            if previous.kind != kind or kind not in ('review', 'event_assessment', 'classification', 'approval'):
                raise ValueError('only judgments may supersede judgments of the same kind')
        record = Record(str(uuid.uuid4()), kind, datetime.now(timezone.utc).isoformat(), freeze(data), supersedes)
        self.records[record.id] = record
        return record

class MockWorker:
    identity = 'mock-worker'
    def produce(self, task, snapshot, adapter):
        return adapter.predict(snapshot.data['inputs'])

class IndependentValidator:
    identity = 'independent-validator'
    def validate(self, result, adapter):
        output = result.data['output']
        expected = adapter.expected_output
        passed = isinstance(output, Mapping) and set(output) == set(expected) and all(
            isinstance(output[k], t) for k, t in expected.items())
        return {'result_id': result.id, 'validator': self.identity, 'passed': passed}

class Ripley:
    def __init__(self, ledger=None, validator=None):
        self.ledger = ledger if ledger is not None else Ledger()
        self.validator = validator if validator is not None else IndependentValidator()
    def run(self, adapter, inputs, worker=None, allowed_workers=('mock-worker',)):
        worker = worker if worker is not None else MockWorker()
        if worker.identity not in allowed_workers:
            raise PermissionError('worker not allowed')
        if worker is self.validator or worker.identity == self.validator.identity:
            raise PermissionError('worker cannot independently validate its own result')
        snapshot = self.ledger.add('snapshot', {'domain_id': adapter.domain_id, 'inputs': inputs,
            'observed_at': datetime.now(timezone.utc).isoformat(), 'sources': ['synthetic'],
            'data_quality': 'synthetic', 'domain_version': adapter.version})
        task = self.ledger.add('task', {'domain_id': adapter.domain_id, 'task_type': 'predict',
            'input_snapshot_id': snapshot.id, 'dependencies': [], 'allowed_workers': allowed_workers,
            'expected_output': tuple(adapter.expected_output), 'validation_requirements': ('independent',),
            'evidence_requirements': ('linked-records',), 'resource_ceiling': 'no external calls',
            'state': 'submitted'})
        output = worker.produce(task, snapshot, adapter)
        result = self.ledger.add('result', {'task_id': task.id, 'input_snapshot_id': snapshot.id,
            'worker': worker.identity, 'output': output, 'evidence': (), 'warnings': (),
            'execution': 'deterministic', 'cost': 0})
        finding = self.validator.validate(result, adapter)
        if finding.get('result_id') != result.id or finding.get('validator') != self.validator.identity:
            raise ValueError('validation provenance mismatch')
        validation = self.ledger.add('validation', finding)
        review = self.ledger.add('review', {'result_id': result.id, 'validation_id': validation.id,
            'reviewer': 'ripley-review-policy',
            'decision': 'acceptable' if finding['passed'] else 'correction_required'})
        evidence = self.ledger.add('evidence', {'task_id': task.id, 'snapshot_id': snapshot.id,
            'result_id': result.id, 'validation_id': validation.id, 'review_id': review.id})
        approval = self.ledger.add('approval', {'evidence_id': evidence.id,
            'authority': 'owner', 'status': 'pending_owner_approval'})
        return {'task': task, 'snapshot': snapshot, 'result': result,
                'validation': validation, 'review': review, 'evidence': evidence, 'approval': approval}
    def revise_review(self, prior_id, reviewer, decision, reason):
        prior = self.ledger.records[prior_id]
        if prior.kind != 'review':
            raise ValueError('not a review')
        return self.ledger.add('review', {'result_id': prior.data['result_id'],
            'validation_id': prior.data['validation_id'], 'reviewer': reviewer,
            'decision': decision, 'reason': reason}, supersedes=prior_id)
