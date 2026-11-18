"""Domain-neutral in-memory execution; not durable storage or secure authorization."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from pathlib import Path
import hashlib
import json
import math
import os
import uuid


TERMINATION_GRACE_SECONDS = 2.0
WATCHDOG_MARGIN_SECONDS = 1.0
KILL_WAIT_SECONDS = 5.0
DIAGNOSTICS_CAP_BYTES = 8192
ENVELOPE_VERSION = '1'
PARENT_CONTROL_RESERVE_SECONDS = 3.0
MIN_SDK_TIMEOUT_SECONDS = 5.0
MIN_PROVIDER_TIMEOUT_SECONDS = 10
MAX_ROW_TEXT_CHARS = 24000


# → blocked from submitted/validated is restart-only; gated by SQLiteLedger.transition
ALLOWED_TRANSITIONS = {
    'submitted': {'running', 'blocked'},
    'running': {'validated', 'blocked'},
    'validated': {'pending_owner_approval', 'blocked'},
    'blocked': set(),
    'pending_owner_approval': {'approved', 'rejected'},
    'approved': set(),
    'rejected': set(),
}


def freeze(value):
    if isinstance(value, Mapping):
        if not all(isinstance(k, str) for k in value):
            raise TypeError('record keys must be strings')
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(v) for v in value)
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError('records require JSON-compatible values')


def canonical_json(value) -> bytes:
    def plain(v):
        if isinstance(v, Mapping):
            return {k: plain(x) for k, x in v.items()}
        if isinstance(v, (tuple, list)):
            return [plain(x) for x in v]
        return v
    return json.dumps(plain(value), sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def decode_protocol_object(raw):
    """Decode one UTF-8 JSON object. Only trailing JSON whitespace is allowed."""
    def unique_keys(pairs):
        fields = {}
        for key, value in pairs:
            if key in fields:
                raise ValueError('duplicate protocol field')
            fields[key] = value
        return fields

    def finite_number(token):
        value = float(token)
        if not math.isfinite(value):
            raise ValueError('nonfinite protocol number')
        return value

    if not raw.startswith(b'{'):
        raise ValueError('expected a JSON object')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_keys,
                      parse_float=finite_number, parse_constant=finite_number)


def content_hash(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def provider_attempt_outcome(ledger, attempt):
    records = tuple(ledger.records.values())
    if any(r.kind == 'result' and r.data.get('attempt_id') == attempt.id for r in records):
        return 'completed'
    failure = next((r for r in reversed(records) if r.kind == 'execution_failure'
                    and r.data.get('attempt_id') == attempt.id), None)
    if failure is None or 'remote_outcome' not in failure.data:
        return 'unknown'
    return failure.data['remote_outcome']


def provider_dispatch_counts(ledger, transport_mode):
    """Derive only the three dispatch counts required by Phase 6C."""
    from .workers import spec_for

    counts = {'confirmed_sent': 0, 'uncertain_dispatch': 0, 'budget_slots_consumed': 0}
    records = tuple(ledger.records.values())
    for attempt in records:
        if (attempt.kind != 'execution_attempt'
                or attempt.data.get('transport_mode') != transport_mode
                or spec_for(attempt.data['worker']).kind != 'provider'):
            continue
        outcome = provider_attempt_outcome(ledger, attempt)
        result = next((r for r in records if r.kind == 'result'
                       and r.data.get('attempt_id') == attempt.id), None)
        fact = result or next((r for r in reversed(records) if r.kind == 'execution_failure'
                              and r.data.get('attempt_id') == attempt.id), None)
        dispatch = fact.data.get('dispatch') if fact else None
        observation = dispatch.get('observation') if dispatch else None
        counts['confirmed_sent'] += observation == 'sent'
        counts['uncertain_dispatch'] += (observation == 'possibly_sent'
                                        or (outcome == 'unknown' and observation is None))
        counts['budget_slots_consumed'] += outcome != 'failed_before_send'
    return counts


def dispatches_consumed(ledger, task_key):
    """Derive charged provider Attempts across both preserved lineage links."""
    from .workers import spec_for

    newest = ledger.task_for_key(task_key)
    pending = [newest.id] if newest is not None else []
    lineage = set()
    while pending:
        task_id = pending.pop()
        if task_id in lineage:
            continue
        lineage.add(task_id)
        task = ledger.records[task_id]
        pending.extend(task.data[key] for key in ('previous_task_id', 'recovers_task_id')
                       if task.data.get(key) is not None)
    return sum(1 for r in ledger.records.values() if r.kind == 'execution_attempt'
               and r.data['task_id'] in lineage and spec_for(r.data['worker']).kind == 'provider'
               and provider_attempt_outcome(ledger, r) != 'failed_before_send')


@dataclass(frozen=True)
class Record:
    id: str
    kind: str
    at: str
    data: object
    supersedes: str | None = None
    content_hash: str = ""


class Ledger:
    """Append-only through public methods; read-only view prevents direct replacement."""
    def __init__(self):
        self._records = {}
        self._task_index = {}

    @property
    def records(self):
        return MappingProxyType(self._records)

    def add(self, kind, data, supersedes=None):
        if supersedes:
            previous = self._records[supersedes]
            if previous.kind != kind or kind not in ('review', 'event_assessment', 'classification', 'approval'):
                raise ValueError('only judgments may supersede judgments of the same kind')
        frozen = freeze(data)
        task_key = frozen.get('task_key') if kind == 'task' else None
        if kind == 'task' and task_key is None:
            raise ValueError('task record requires task_key')
        digest = content_hash({'kind': kind, 'data': frozen, 'supersedes': supersedes})
        record = Record(str(uuid.uuid4()), kind, datetime.now(timezone.utc).isoformat(),
                        frozen, supersedes, digest)
        self._records[record.id] = record
        if kind == 'task':
            self._task_index[task_key] = record.id
        return record

    def task_for_key(self, task_key):
        task_id = self._task_index.get(task_key)
        return self._records[task_id] if task_id is not None else None

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
        if (to_state not in ALLOWED_TRANSITIONS[current] or
                (current in ('submitted', 'validated') and to_state == 'blocked')):
            raise ValueError('invalid state transition')
        prior = next((r.id for r in reversed(tuple(self._records.values()))
                      if r.kind == 'task_transition' and r.data['task_id'] == task_id), None)
        return self.add('task_transition', {'task_id': task_id, 'from_state': from_state,
                        'to_state': to_state, 'actor': actor, 'reason': reason,
                        'preceding_transition_id': prior})


class MockWorker:
    identity = 'mock-worker'
    def produce(self, task, snapshot, adapter):
        data = snapshot if isinstance(snapshot, Mapping) else snapshot.data
        return adapter.predict(data['inputs'])


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
                'result_hash': result.content_hash,
                'contract_hash': content_hash({k: t.__name__ for k, t in expected.items()}),
                'passed': passed}


class Ripley:
    def __init__(self, ledger=None, validator=None, clock=None, *, _subprocess_wait=None):
        self._subprocess_wait = _subprocess_wait
        self.ledger = ledger if ledger is not None else Ledger()
        self.validator = validator if validator is not None else IndependentValidator()
        self.clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def run(self, adapter, inputs, worker=None, allowed_workers=('mock-worker',),
            correction_budget=1, execution='inline'):
        self._check_execution(execution)
        self._check_correction_budget(correction_budget)
        worker, spec = self._checked_worker(worker, allowed_workers)
        timeout = self._timeout(adapter)
        self._check_provider(spec, execution, timeout)
        inputs = freeze(inputs)
        task_type = getattr(adapter, 'task_type', 'predict')
        task_key = content_hash({'domain_id': adapter.domain_id,
            'domain_version': adapter.version, 'task_type': task_type, 'inputs': inputs})
        existing = self.ledger.task_for_key(task_key)
        if existing is not None and self.ledger.task_state(existing.id) not in ('blocked', 'approved', 'rejected'):
            self.ledger.add('duplicate_submission', {'task_key': task_key, 'task_id': existing.id})
            return self._run_return('duplicate_of_existing_task', task=existing)
        dispatch_authorization = None
        if spec.kind == 'provider':
            dispatch_authorization = self._provider_dispatch_gate(task_key)
        return self._execute(adapter, inputs, worker, allowed_workers, correction_budget,
                             timeout, task_key, existing, execution=execution,
                             dispatch_authorization_id=dispatch_authorization)

    @staticmethod
    def _check_execution(execution):
        if execution not in ('inline', 'subprocess'):
            raise ValueError('execution must be inline or subprocess')

    @staticmethod
    def _check_correction_budget(correction_budget):
        if type(correction_budget) is not int or correction_budget < 0:
            raise ValueError('correction_budget must be a nonnegative integer')

    def _checked_worker(self, worker, allowed_workers):
        worker = worker if worker is not None else MockWorker()
        if worker.identity not in allowed_workers:
            raise PermissionError('worker not allowed')
        if worker is self.validator or worker.identity == self.validator.identity:
            raise PermissionError('worker cannot independently validate its own result')
        from .workers import spec_for

        return worker, spec_for(worker.identity)

    @staticmethod
    def _check_provider(spec, execution, timeout):
        if spec.kind == 'provider':
            if execution != 'subprocess':
                raise ValueError('provider workers run only in subprocess execution')
            if timeout is None or timeout.total_seconds() < MIN_PROVIDER_TIMEOUT_SECONDS:
                raise ValueError('provider workers require timeout_seconds >= 10')

    def _provider_dispatch_gate(self, task_key):
        from .workers import PILOT_DISPATCH_BUDGET_ENV, spec_for

        authorization_id = None
        records = tuple(self.ledger.records.values())
        if dispatches_consumed(self.ledger, task_key) >= 1:
            consumed = {r.data.get('dispatch_authorization_id') for r in records
                        if r.kind == 'execution_attempt'}
            authorization = next((r for r in records if r.kind == 'dispatch_authorization'
                and r.data.get('task_key') == task_key and r.data.get('actor') == 'owner'
                and isinstance(r.data.get('reason'), str) and r.data['reason'].strip()
                and r.id not in consumed), None)
            if authorization is None:
                raise PermissionError('second paid dispatch requires owner dispatch_authorization')
            authorization_id = authorization.id
        mode = os.environ.get('RIPLEY_PROVIDER_TRANSPORT')
        budget = int(os.environ.get(PILOT_DISPATCH_BUDGET_ENV, '25'))
        count = sum(1 for r in records if r.kind == 'execution_attempt'
                    and spec_for(r.data['worker']).kind == 'provider'
                    and r.data.get('transport_mode') == mode
                    and provider_attempt_outcome(self.ledger, r) != 'failed_before_send')
        if count >= budget:
            self.ledger.add('pilot_budget_exhausted', {'budget': budget, 'consumed': count,
                                                    'transport_mode': mode})
            raise ValueError('pilot dispatch budget exhausted')
        return authorization_id

    @staticmethod
    def _timeout(adapter):
        seconds = getattr(adapter, 'timeout_seconds', None)
        if seconds is None:
            return None
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('timeout_seconds must be a positive finite number')
        return timedelta(seconds=seconds)

    def _confirmed_exit(self, attempt, failure, records):
        requested = any(r.kind == 'execution_request' and r.data['attempt_id'] == attempt.id
                        for r in records)
        if not requested:
            return True
        termination = failure.get('termination')
        if termination is not None:
            return termination.get('exited') is True
        if failure.get('completed_at') is not None:
            return True
        restart = (failure['stage'] == 'interrupted' or
                   (failure['stage'] == 'timeout' and
                    failure.get('message') == 'deadline_exceeded_before_restart'))
        deadline = attempt.data.get('deadline_at')
        if not restart or deadline is None:
            return False
        margin = timedelta(seconds=TERMINATION_GRACE_SECONDS + WATCHDOG_MARGIN_SECONDS + 1)
        return self.clock() > datetime.fromisoformat(deadline) + margin

    def recover(self, blocked_task_id, actor, reason, adapter, worker=None,
                allowed_workers=('mock-worker',), correction_budget=1, execution=None):
        task = self.ledger.records.get(blocked_task_id)
        if task is None or task.kind != 'task' or self.ledger.task_state(task.id) != 'blocked':
            raise ValueError('blocked task required')
        current = self.ledger.task_for_key(task.data['task_key'])
        if current is not None and self.ledger.task_state(current.id) not in ('blocked', 'approved', 'rejected'):
            raise ValueError('active task exists for this key')
        records = tuple(self.ledger.records.values())
        failures = [r for r in records if r.kind == 'execution_failure'
                    and r.data['task_id'] == task.id]
        if (not failures or failures[-1].data.get('stage') not in ('interrupted', 'timeout') or
                any(r.kind == 'correction_budget_exhaustion' and r.data['task_id'] == task.id
                    for r in records)):
            raise ValueError('recovery not eligible for this failure')
        attempt = next((r for r in reversed(records) if r.kind == 'execution_attempt'
                        and r.data['task_id'] == task.id), None)
        prior_mode = attempt.data.get('execution', 'inline') if attempt else 'inline'
        if prior_mode == 'subprocess' and not self._confirmed_exit(attempt, failures[-1].data, records):
            raise ValueError('prior execution not confirmed exited')
        execution = prior_mode if execution is None else execution
        self._check_execution(execution)
        if task.data.get('replay_policy') != 'safe':
            raise ValueError('safe replay policy required')
        if task.data['resource_ceiling'] != 'no external calls':
            raise ValueError('recovery requires no external calls')
        if adapter.domain_id != task.data['domain_id'] or adapter.version != task.data['domain_version']:
            raise ValueError('adapter domain and version must match task')
        worker, spec = self._checked_worker(worker, allowed_workers)
        from .workers import spec_for

        original_kind = spec_for(attempt.data['worker']).kind if attempt else 'local'
        if spec.kind != original_kind:
            raise ValueError('recovery may not change worker kind')
        if not isinstance(actor, str) or not actor or not isinstance(reason, str) or not reason.strip():
            raise ValueError('actor and reason required')
        # Argument checks precede any authorization or exhaustion write.
        self._check_correction_budget(correction_budget)
        timeout = self._timeout(adapter)
        self._check_provider(spec, execution, timeout)
        lineage = set()
        ancestor = task
        while True:
            lineage.add(ancestor.id)
            previous_id = ancestor.data.get('recovers_task_id')
            if previous_id is None:
                break
            ancestor = self.ledger.records[previous_id]
        consumed = sum(r.kind == 'recovery_authorization' and
                       r.data['blocked_task_id'] in lineage for r in records)
        if consumed >= 1:
            self.ledger.add('recovery_budget_exhaustion', {'task_id': task.id,
                'lineage_root_id': ancestor.id, 'budget': 1, 'consumed': consumed})
            raise ValueError('recovery budget exhausted')
        replay_attempt_id = attempt.id if attempt else None
        authorization = self.ledger.add('recovery_authorization', {
            'blocked_task_id': task.id, 'interrupted_attempt_id': replay_attempt_id,
            'actor': actor, 'reason': reason, 'replay_policy_cited': 'safe',
            'resource_ceiling_cited': task.data['resource_ceiling']})
        snapshot = self.ledger.records[task.data['input_snapshot_id']]
        outcome = self._execute(adapter, snapshot.data['inputs'], worker, allowed_workers,
                                correction_budget, timeout, task.data['task_key'], current,
                                replay_snapshot=snapshot, replay_attempt_id=replay_attempt_id,
                                recovers_task_id=task.id, execution=execution)
        outcome['authorization'] = authorization
        return outcome

    def _execute(self, adapter, inputs, worker, allowed_workers, correction_budget,
                 timeout, task_key, existing, replay_snapshot=None, replay_attempt_id=None,
                 recovers_task_id=None, execution='inline', dispatch_authorization_id=None):
        from .workers import spec_for

        spec = spec_for(worker.identity)
        provider = spec.kind == 'provider'
        if spec.paid_correction_allowed is False:
            correction_budget = 0
        if replay_snapshot is None:
            # Domain adapter owns snapshot provenance and data-quality declarations.
            metadata = adapter.snapshot_metadata(inputs)
            snapshot_data = {'domain_id': adapter.domain_id, 'inputs': inputs,
                'observed_at': metadata['observed_at'], 'sources': metadata['sources'],
                'data_quality': metadata['data_quality'], 'domain_version': adapter.version}
        else:
            snapshot_data = {name: replay_snapshot.data[name] for name in
                             ('domain_id', 'inputs', 'observed_at', 'sources',
                              'data_quality', 'domain_version')}
            snapshot_data['replays_snapshot_id'] = replay_snapshot.id
        snapshot = self.ledger.add('snapshot', snapshot_data)
        policy = getattr(adapter, 'replay_policy', None)
        policy = policy if policy in ('safe', 'no') else 'unknown'
        task_type = getattr(adapter, 'task_type', 'predict')
        task = self.ledger.add('task', {'domain_id': adapter.domain_id, 'task_type': task_type,
            'domain_version': adapter.version, 'task_key': task_key,
            'previous_task_id': existing.id if existing is not None else None,
            'recovers_task_id': recovers_task_id,
            'replay_policy': policy,
            'input_snapshot_id': snapshot.id, 'dependencies': [], 'allowed_workers': allowed_workers,
            'expected_output': tuple(adapter.expected_output), 'validation_requirements': ('independent',),
            'evidence_requirements': ('linked-records',), 'resource_ceiling': spec.external_calls,
            'dispatch_policy': {'max_dispatches_per_attempt': 1,
                                'paid_correction_allowed': False} if provider else None,
            'state': 'submitted'})
        self.ledger.transition(task.id, 'submitted', 'running', 'ripley', 'execution started')
        results = []
        validations = []
        reviews = []
        corrections = []
        for attempt_number in range(correction_budget + 1):
            isolated = execution == 'subprocess'
            started_at = datetime.now(timezone.utc) if isolated else self.clock().astimezone(timezone.utc)
            deadline = started_at + timeout if timeout is not None else None
            provider_fields = {}
            if provider:
                prompt = dict(spec.prompt_ref)
                template = Path(__file__).parent / 'prompts' / prompt['name'] / (prompt['version'] + '.md')
                prompt['content_hash'] = hashlib.sha256(template.read_bytes()).hexdigest()
                provider_fields = {'correction_budget_forced': True,
                    'transport_mode': os.environ.get('RIPLEY_PROVIDER_TRANSPORT'),
                    'gates': [{'name': name, 'present': name in os.environ} for name in
                              ('RIPLEY_PROVIDER_TRANSPORT', 'RIPLEY_LIVE_DISPATCH',
                               'RIPLEY_ENABLE_TEST_WORKERS')],
                    'credential_source': {'ref': spec.credentials_ref, 'kind': 'env'},
                    'sdk': {'package': 'anthropic', 'version': '2.9.0'},
                    'provider': spec.provider, 'model': spec.model, 'prompt_ref': prompt,
                    'dispatch_authorization_id': dispatch_authorization_id}
            attempt = self.ledger.add('execution_attempt', {'task_id': task.id,
                'worker': worker.identity, 'attempt_number': attempt_number + 1, 'execution': execution,
                **({'started_at': started_at.isoformat()} if isolated else {}),
                'deadline_at': deadline.isoformat() if deadline is not None else None,
                'replays_attempt_id': replay_attempt_id if attempt_number == 0 else None,
                **provider_fields})
            if isolated:
                from .isolation import observe_subprocess

                packet = {'envelope_version': ENVELOPE_VERSION, 'attempt_id': attempt.id,
                          'task_id': task.id, 'task_type': task_type, 'domain_id': task.data['domain_id'],
                          'domain_version': task.data['domain_version'], 'worker_identity': worker.identity,
                          'inputs': snapshot.data['inputs'], 'deadline_at': attempt.data['deadline_at']}
                self.ledger.add('execution_request', {'attempt_id': attempt.id, 'packet': packet})
                observation = observe_subprocess(packet, deadline, timeout, self._subprocess_wait,
                                                 spec.response_envelope_version)
                result_fields = observation.result
                failure_fields = observation.failure
                late_response = observation.late_response
            else:
                result_fields, failure_fields = self._observe_inline(worker, task, snapshot, adapter, deadline)
                late_response = None

            if provider:
                response_fields = result_fields if result_fields is not None else failure_fields
                dispatch = response_fields.get('dispatch') if response_fields else None
                if dispatch is None and late_response is not None:
                    dispatch = late_response.get('dispatch')
                if dispatch is not None and dispatch['prompt_ref'] != attempt.data['prompt_ref']:
                    result_fields, late_response = None, None
                    failure_fields = {'stage': 'host_failure', 'message': 'prompt_ref hash mismatch',
                                      'dispatch': None, 'remote_outcome': 'unknown'}
                elif result_fields is not None:
                    result_fields['remote_outcome'] = 'completed'
                if failure_fields is not None:
                    if failure_fields['stage'] == 'worker_failure' and dispatch is not None:
                        failure_fields['provider_error'] = failure_fields['error']['type']
                        failure_fields['remote_outcome'] = {'not_sent': 'failed_before_send',
                            'sent': 'failed_after_send', 'possibly_sent': 'unknown'}[dispatch['observation']]
                    else:
                        failure_fields.update(dispatch=None, remote_outcome='unknown')

            result = None
            if result_fields is not None:
                result = self.ledger.add('result', {'task_id': task.id, 'attempt_id': attempt.id,
                    'input_snapshot_id': snapshot.id, 'worker': worker.identity, **result_fields,
                    'evidence': (), 'warnings': (),
                    'execution': 'provider' if provider else 'deterministic',
                    'cost': None if provider else 0})
                results.append(result)
            if failure_fields is not None:
                failure = self.ledger.add('execution_failure', {'task_id': task.id,
                    'attempt_id': attempt.id, **failure_fields})
                late_result = None
                if late_response is not None:
                    late_result = self.ledger.add('late_result', {'attempt_id': attempt.id,
                        'failure_id': failure.id, 'worker_identity': late_response['worker_identity'],
                        'output': late_response['output']})
                stage = failure_fields.get('stage', 'worker_failure')
                reason = 'deadline_exceeded' if stage == 'timeout' else stage
                self.ledger.transition(task.id, 'running', 'blocked', 'ripley', reason)
                return self._run_return('blocked_' + stage, task=task, snapshot=snapshot,
                    attempt=attempt, result=result, failure=failure, late_result=late_result,
                    results=results, validations=validations, reviews=reviews, corrections=corrections)
            if corrections:
                request = corrections[-1]
                previous = results[-2]
                self.ledger.add('correction', {'task_id': task.id,
                    'request_id': request.id, 'reviewer': request.data['reviewer'],
                    'reason': request.data['reason'], 'original_result_id': previous.id,
                    'original_result_hash': previous.content_hash,
                    'corrected_result_id': result.id, 'corrected_result_hash': result.content_hash})
            try:
                if getattr(self.validator, 'requires_snapshot', False):
                    finding = self.validator.validate(result, adapter, snapshot=snapshot)
                else:
                    finding = self.validator.validate(result, adapter)
                if (finding.get('result_id') != result.id or
                        finding.get('result_hash') != result.content_hash or
                        finding.get('validator') != self.validator.identity):
                    raise ValueError('validation provenance mismatch')
                validation = self.ledger.add('validation', finding)
                validations.append(validation)
                review = self.ledger.add('review', {'result_id': result.id, 'validation_id': validation.id,
                    'reviewer': 'ripley-review-policy', 'purpose': 'policy',
                    'result_hash': result.content_hash, 'validation_hash': validation.content_hash,
                    'reason': 'output shape passed' if finding['passed'] else 'invalid output structure',
                    'decision': 'acceptable' if finding['passed'] else 'correction_required'})
                reviews.append(review)
            except Exception as exc:
                failure = self.ledger.add('execution_failure', {'task_id': task.id,
                    'stage': 'validation', 'attempt_id': attempt.id,
                    'exception_type': type(exc).__name__, 'message': str(exc)})
                self.ledger.transition(task.id, 'running', 'blocked', 'ripley', 'validation_failure')
                return self._run_return('blocked_validation_failure', task=task,
                    snapshot=snapshot, attempt=attempt, result=result, failure=failure,
                    results=results, validations=validations, reviews=reviews, corrections=corrections)
            if finding['passed']:
                self.ledger.transition(task.id, 'running', 'validated', 'ripley', 'review accepted')
                evidence = self.ledger.add('evidence', {'task_id': task.id, 'snapshot_id': snapshot.id,
                    'result_id': result.id, 'validation_id': validation.id, 'review_id': review.id,
                    'hashes': {r.id: r.content_hash for r in
                               (task, snapshot, result, validation, review)}})
                approval = self.ledger.add('approval', {'evidence_id': evidence.id,
                    'evidence_hash': evidence.content_hash, 'task_id': task.id,
                    'result_hash': result.content_hash,
                    'authority': 'owner', 'status': 'pending_owner_approval'})
                self.ledger.transition(task.id, 'validated', 'pending_owner_approval',
                                       'ripley', 'awaiting owner')
                return self._run_return('pending_owner_approval', task=task,
                    snapshot=snapshot, attempt=attempt, result=result, validation=validation,
                    review=review, evidence=evidence, approval=approval,
                    results=results, validations=validations, reviews=reviews, corrections=corrections)
            if attempt_number < correction_budget:
                corrections.append(self.ledger.add('correction_request', {
                    'task_id': task.id, 'rejected_result_id': result.id,
                    'review_id': review.id, 'reviewer': review.data['reviewer'],
                    'rejected_result_hash': result.content_hash,
                    'reason': 'invalid output structure'}))
            else:
                blocked = self.ledger.add('correction_budget_exhaustion', {
                    'task_id': task.id, 'last_result_id': result.id, 'budget': correction_budget})
                self.ledger.transition(task.id, 'running', 'blocked', 'ripley',
                                       'correction_budget_exhausted')
                return self._run_return('blocked_budget_exhausted', task=task,
                    snapshot=snapshot, attempt=attempt, result=result, validation=validation,
                    review=review, blocked=blocked,
                    results=results, validations=validations, reviews=reviews, corrections=corrections)

    def _observe_inline(self, worker, task, snapshot, adapter, deadline):
        try:
            output = worker.produce(task, snapshot, adapter)
        except Exception as exc:
            return None, {'exception_type': type(exc).__name__, 'message': str(exc)}
        completed_at = self.clock().astimezone(timezone.utc)
        failure = None
        if deadline is not None and completed_at > deadline:
            failure = {'stage': 'timeout', 'deadline_at': deadline.isoformat(),
                       'completed_at': completed_at.isoformat()}
        return {'output': output}, failure

    @staticmethod
    def _run_return(outcome, *, task, snapshot=None, attempt=None, result=None,
                    validation=None, review=None, evidence=None, approval=None,
                    failure=None, blocked=None, authorization=None, late_result=None,
                    results=(), validations=(), reviews=(), corrections=()):
        return {'outcome': outcome, 'task': task, 'snapshot': snapshot, 'attempt': attempt,
                'result': result, 'validation': validation, 'review': review,
                'evidence': evidence, 'approval': approval, 'failure': failure, 'blocked': blocked,
                'authorization': authorization, 'late_result': late_result,
                'results': tuple(results), 'validations': tuple(validations),
                'reviews': tuple(reviews), 'corrections': tuple(corrections)}

    def revise_review(self, prior_id, reviewer, decision, reason):
        prior = self.ledger.records[prior_id]
        if prior.kind != 'review':
            raise ValueError('not a review')
        return self.ledger.add('review', {'result_id': prior.data['result_id'],
            'validation_id': prior.data['validation_id'], 'reviewer': reviewer,
            'purpose': prior.data.get('purpose', 'policy'),
            'result_hash': prior.data['result_hash'],
            'validation_hash': prior.data['validation_hash'],
            'decision': decision, 'reason': reason}, supersedes=prior_id)

    def decide_approval(self, pending_id, actor, decision, reason):
        """Explicit local decision record; actor labels are not authenticated identities."""
        if actor != 'owner' or decision not in ('approved', 'rejected') or not reason.strip():
            raise ValueError('owner, explicit decision and reason required')
        pending = self.ledger.records[pending_id]
        if pending.kind != 'approval' or pending.data['status'] != 'pending_owner_approval':
            raise ValueError('pending approval required')
        task_id = pending.data['task_id']
        if self.ledger.task_state(task_id) != 'pending_owner_approval':
            raise ValueError('task is not awaiting approval')
        evidence = self.ledger.records[pending.data['evidence_id']]
        if evidence.content_hash != pending.data['evidence_hash']:
            raise ValueError('evidence mismatch')
        for record_id, digest in evidence.data['hashes'].items():
            if self.ledger.records[record_id].content_hash != digest:
                raise ValueError('linked content mismatch')
        if decision == 'approved':
            validation = self.ledger.records[evidence.data['validation_id']]
            review = self.ledger.records[evidence.data['review_id']]
            if (not validation.data['passed'] or review.data['decision'] != 'acceptable' or
                    any(r.supersedes == review.id for r in self.ledger.records.values())):
                raise ValueError('current accepted review and passing check required')
        approval = self.ledger.add('approval', {
            **dict(pending.data), 'authority': actor, 'status': decision, 'reason': reason},
            supersedes=pending.id)
        self.ledger.transition(task_id, 'pending_owner_approval', decision, actor, reason)
        return approval
