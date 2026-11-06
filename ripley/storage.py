"""Single-file, sequential durable ledger under ADR-007."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import uuid

from .core import Ledger, Record, canonical_json, content_hash, freeze


class SQLiteLedger(Ledger):
    def __init__(self, path):
        super().__init__()
        self._path = str(path)
        with closing(sqlite3.connect(self._path)) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS records (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT UNIQUE, kind TEXT, at TEXT, supersedes TEXT NULL,
                content_hash TEXT, data TEXT)''')
            rows = db.execute('SELECT id, kind, at, supersedes, content_hash, data '
                              'FROM records ORDER BY seq').fetchall()
        # Verify the entire store before appending any restart evidence.
        for record_id, kind, at, supersedes, digest, stored in rows:
            raw = stored.encode('utf-8')
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError(f'content hash mismatch: {record_id}')
            envelope = json.loads(raw)
            if (canonical_json(envelope) != raw or envelope['kind'] != kind or
                    envelope['supersedes'] != supersedes):
                raise ValueError(f'canonical record mismatch: {record_id}')
            data = freeze(envelope['data'])
            if kind == 'task' and data.get('task_key') is None:
                raise ValueError('task record requires task_key')
            self._records[record_id] = Record(record_id, kind, at, data, supersedes, digest)
            if kind == 'task':
                self._task_index[data['task_key']] = record_id
        self._opening = True
        try:
            for task in tuple(self._records.values()):
                if task.kind != 'task':
                    continue
                state = self.task_state(task.id)
                if state in ('submitted', 'running', 'validated'):
                    attempts = [r for r in self._ordered('execution_attempt')
                                if r.data['task_id'] == task.id]
                    self.add('execution_failure', {'task_id': task.id, 'stage': 'interrupted',
                        'attempt_id': attempts[-1].id if attempts else None,
                        'message': 'interrupted_by_restart'})
                    self.transition(task.id, state, 'blocked', 'ripley', 'interrupted_by_restart')
        finally:
            self._opening = False

    def _ordered(self, kind):
        with closing(sqlite3.connect(self._path)) as db:
            ids = db.execute('SELECT id FROM records WHERE kind = ? ORDER BY seq',
                             (kind,)).fetchall()
        return [self._records[row[0]] for row in ids]

    def add(self, kind, data, supersedes=None):
        if supersedes:
            previous = self._records[supersedes]
            if previous.kind != kind or kind not in ('review', 'event_assessment', 'classification', 'approval'):
                raise ValueError('only judgments may supersede judgments of the same kind')
        frozen = freeze(data)
        task_key = frozen.get('task_key') if kind == 'task' else None
        if kind == 'task' and task_key is None:
            raise ValueError('task record requires task_key')
        envelope = {'kind': kind, 'data': frozen, 'supersedes': supersedes}
        raw = canonical_json(envelope)
        record = Record(str(uuid.uuid4()), kind, datetime.now(timezone.utc).isoformat(),
                        frozen, supersedes, content_hash(envelope))
        with closing(sqlite3.connect(self._path)) as db:
            with db:
                db.execute('INSERT INTO records (id, kind, at, supersedes, content_hash, data) '
                           'VALUES (?, ?, ?, ?, ?, ?)',
                           (record.id, kind, record.at, supersedes, record.content_hash,
                            raw.decode('utf-8')))
        self._records[record.id] = record
        if kind == 'task':
            self._task_index[task_key] = record.id
        return record

    def _transitions(self, task_id):
        transitions = [r for r in self._ordered('task_transition')
                       if r.data['task_id'] == task_id]
        prior = None
        state = self._records[task_id].data['state']
        for transition in transitions:
            if (transition.data['preceding_transition_id'] != prior or
                    transition.data['from_state'] != state):
                raise ValueError('transition sequence and lineage disagree')
            prior, state = transition.id, transition.data['to_state']
        return transitions

    def task_state(self, task_id):
        task = self._records[task_id]
        if task.kind != 'task':
            raise ValueError('not a task')
        transitions = self._transitions(task_id)
        return transitions[-1].data['to_state'] if transitions else task.data['state']

    def transition(self, task_id, from_state, to_state, actor, reason):
        current = self.task_state(task_id)
        if current != from_state:
            raise ValueError('stale task state')
        # Ordinary execution keeps the Phase 2 transition rules unchanged.
        interrupted = (self._opening and current in ('submitted', 'running', 'validated')
                       and to_state == 'blocked' and actor == 'ripley'
                       and reason == 'interrupted_by_restart')
        allowed = {'submitted': {'running'}, 'running': {'validated', 'blocked'},
                   'validated': {'pending_owner_approval'}, 'blocked': set(),
                   'pending_owner_approval': {'approved', 'rejected'},
                   'approved': set(), 'rejected': set()}
        if not interrupted and to_state not in allowed[current]:
            raise ValueError('invalid state transition')
        transitions = self._transitions(task_id)
        return self.add('task_transition', {'task_id': task_id, 'from_state': from_state,
            'to_state': to_state, 'actor': actor, 'reason': reason,
            'preceding_transition_id': transitions[-1].id if transitions else None})
