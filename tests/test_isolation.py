"""ADR-009 acceptance with real children and append-only evidence."""
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_recovery
from ripley.core import Ledger, MockWorker, canonical_json
from ripley.isolation import _excerpt, _response
from ripley.storage import SQLiteLedger


TEST_ID = 'test-behavior-worker'
BEHAVIOR = 'RIPLEY_TEST_WORKER_BEHAVIOR'
GATE = 'RIPLEY_ENABLE_TEST_WORKERS'
WINDOWS = sys.platform == 'win32'


class IsolationFixtures(test_recovery.RecoveryFixtures):
    def setUp(self):
        super().setUp()
        environment = patch.dict(os.environ, {GATE: '1', BEHAVIOR: 'ok'})
        environment.start()
        self.addCleanup(environment.stop)
        self.worker = MockWorker()
        self.worker.identity = TEST_ID

    def isolated(self, behavior='ok', timeout=None, engine=None, **kwargs):
        os.environ[BEHAVIOR] = behavior
        self.adapter.timeout_seconds = timeout
        return (engine or self.engine()).run(self.adapter, self.inputs, worker=self.worker,
            allowed_workers=(TEST_ID,), execution='subprocess', **kwargs)

    def kinds(self, ledger=None):
        return [r.kind for r in (ledger or self.ledger).records.values()]

    def partial_subprocess(self, deadline=None, requested=True):
        task, _, _ = self.partial(attempt=False)
        attempt = self.ledger.add('execution_attempt', {'task_id': task.id,
            'worker': 'mock-worker', 'attempt_number': 1, 'replays_attempt_id': None,
            'execution': 'subprocess', 'started_at': datetime.now(timezone.utc).isoformat(),
            'deadline_at': deadline.isoformat() if deadline else None})
        if requested:
            packet = {'envelope_version': '1', 'attempt_id': attempt.id, 'task_id': task.id,
                'task_type': 'predict', 'domain_id': self.adapter.domain_id,
                'domain_version': self.adapter.version, 'worker_identity': 'mock-worker',
                'inputs': self.inputs, 'deadline_at': attempt.data['deadline_at']}
            self.ledger.add('execution_request', {'attempt_id': attempt.id, 'packet': packet})
        return task, attempt

    def forbid_promotion(self):
        for kind in ('validation', 'review', 'evidence', 'approval', 'correction_request',
                     'correction_budget_exhaustion', 'recovery_authorization', 'recovery_budget_exhaustion'):
            self.assertFalse(self.records(kind), kind)


class IsolationContract(IsolationFixtures):
    def test_p5_01_equivalent_success(self):
        before = datetime.now(timezone.utc)
        run = self.isolated()
        after = datetime.now(timezone.utc)
        inline_ledger = Ledger()
        inline = test_recovery.Ripley(inline_ledger).run(self.adapter, self.inputs)
        self.assertEqual(run['outcome'], 'pending_owner_approval')
        self.assertEqual(run['result'].data['output'], inline['result'].data['output'])
        self.assertEqual(self.kinds().count('execution_request'), 1)
        self.assertEqual([k for k in self.kinds() if k != 'execution_request'], self.kinds(inline_ledger))
        self.assertEqual(run['attempt'].data['execution'], 'subprocess')
        start = datetime.fromisoformat(run['attempt'].data['started_at'])
        end = datetime.fromisoformat(run['result'].data['completed_at'])
        self.assertLessEqual(before, start)
        self.assertLessEqual(start, end)
        self.assertLessEqual(end, after)
        self.assertGreater(run['result'].data['pid'], 0)
        self.assertEqual(run['result'].data['returncode'], 0)
        self.assertNotIn('diagnostics', run['result'].data)
        self.assertEqual(set(run), set(inline))

    def test_p5_02_worker_exception(self):
        run = self.isolated('raise')
        failure = run['failure'].data
        self.assertEqual(run['outcome'], 'blocked_worker_failure')
        self.assertEqual(failure['stage'], 'worker_failure')
        self.assertEqual(dict(failure['error']), {'type': 'RuntimeError', 'message': 'test worker raised'})
        self.assertEqual(failure['returncode'], 0)
        self.assertEqual(failure['diagnostics']['bytes_total'], 0)
        self.assertFalse(self.records('result'))

    def test_p5_03_deadline_terminates(self):
        run = self.isolated('sleep:5', timeout=0.5)
        failure = run['failure'].data
        termination = failure['termination']
        self.assertEqual(run['outcome'], 'blocked_timeout')
        self.assertEqual(failure['stage'], 'timeout')
        self.assertEqual(termination['method'], 'terminate')
        self.assertIs(termination['exited'], True)
        self.assertIsNotNone(termination['returncode'])
        self.assertLessEqual(failure['deadline_at'], failure['declared_at'])
        self.assertLessEqual(failure['declared_at'], termination['requested_at'])
        self.assertLessEqual(termination['requested_at'], failure['completed_at'])
        self.assertFalse(self.records('result'))
        self.assertFalse(self.records('late_result'))
        self.assertIsNone(run['late_result'])
        self.assertEqual(self.ledger.task_state(run['task'].id), 'blocked')

    @unittest.skipIf(WINDOWS, 'graceful-termination signal not supported on Windows')
    def test_p5_04_parent_kills_unresponsive_child(self):
        run = self.isolated('trap_sigterm_and_sleep:10', timeout=0.5)
        termination = run['failure'].data['termination']
        self.assertEqual(termination['method'], 'kill')
        self.assertIs(termination['exited'], True)
        self.assertEqual(termination['returncode'], -signal.SIGKILL)
        self.assertEqual(run['outcome'], 'blocked_timeout')

    def test_p5_05_host_protocol_failures(self):
        for behavior, excerpt in [('garbage_stdout', 'garbage'), ('partial_json', '{"attempt_id":'),
                                  ('exit_zero_no_output', '')]:
            with self.subTest(behavior=behavior):
                run = self.isolated(behavior)
                self.assertEqual(run['outcome'], 'blocked_host_failure')
                self.assertEqual(run['failure'].data['stage'], 'host_failure')
                self.assertEqual(run['failure'].data['stdout_excerpt'], excerpt)
                self.assertEqual(run['failure'].data['returncode'], 0)
                self.assertFalse(self.records('result'))

        # Test the strict parser on inputs a correctly bound host never emits.
        packet = self.records('execution_request')[0].data['packet']
        identity = {k: packet[k] for k in ('envelope_version', 'attempt_id', 'worker_identity')}
        good = canonical_json({**identity, 'status': 'ok', 'output': None})
        self.assertIsNone(_response(good + b'\n\t', packet)['output'])
        for raw in (b' ' + good, good + b'{}', good + b'\xff', good[:-1] + b',"status":"ok"}',
                    good[:-1] + b',"extra":1}', good.replace(b'null', b'1e999'),
                    canonical_json({**identity, 'status': 'error', 'error': {'message': 'oops'}})):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                _response(raw, packet)
        with patch.object(sys, 'executable', str(Path(tempfile.gettempdir()) / 'missing-ripley-p5/python')):
            failed = self.isolated()
        self.assertEqual(failed['outcome'], 'blocked_host_failure')
        launch = failed['failure'].data
        self.assertEqual(launch['launch_error']['type'], 'FileNotFoundError')
        self.assertIsNone(launch['termination'])
        self.assertIsNone(launch['diagnostics'])

    def test_p5_06_discard_wrong_correlation(self):
        run = self.isolated('wrong_attempt_id')
        self.assertEqual(run['outcome'], 'blocked_host_failure')
        self.assertIsNone(run['result'])
        self.assertIn('uncorrelated-output-marker', run['failure'].data['stdout_excerpt'])
        for record in self.ledger.records.values():
            other = dict(record.data)
            other.pop('stdout_excerpt', None)
            self.assertNotIn(b'uncorrelated-output-marker', canonical_json(other))
        packet = self.records('execution_request')[0].data['packet']
        response = {k: packet[k] for k in ('envelope_version', 'attempt_id', 'worker_identity')}
        for change in ({'worker_identity': 'another-worker'}, {'envelope_version': '2'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                _response(canonical_json({**response, **change, 'status': 'ok', 'output': 1}), packet)

    def test_p5_07_completed_after_deadline(self):
        def widen(seconds):
            self.assertEqual(seconds, 0.5)
            return 2.0

        run = self.isolated('sleep:0.6', 0.5, engine=self.engine(_subprocess_wait=widen))
        self.assertEqual(run['outcome'], 'blocked_timeout')
        self.assertEqual(run['result'].data['output'], self.adapter.predict(self.inputs))
        failure = run['failure'].data
        self.assertIsNone(failure['termination'])
        self.assertGreater(failure['completed_at'], failure['deadline_at'])
        self.assertIsNone(run['late_result'])
        self.forbid_promotion()
        self.adapter.timeout_seconds = None
        self.assertEqual(self.recover(run['task'])['outcome'], 'pending_owner_approval')

    @unittest.skipIf(WINDOWS, 'graceful termination signal not available')
    def test_p5_08_grace_response_and_post_kill_drain(self):
        run = self.isolated('trap_sigterm_then_complete:1.0', 0.5)
        failure, late = run['failure'], run['late_result']
        self.assertEqual(failure.data['stage'], 'timeout')
        self.assertEqual(failure.data['termination']['method'], 'terminate')
        self.assertIs(failure.data['termination']['exited'], True)
        self.assertEqual(dict(late.data), {'failure_id': failure.id, 'attempt_id': run['attempt'].id,
            'worker_identity': TEST_ID, 'output': self.adapter.predict(self.inputs)})
        order = list(self.ledger.records)
        self.assertEqual(order.index(failure.id) + 1, order.index(late.id))
        self.assertEqual(self.ledger.task_state(run['task'].id), 'blocked')
        killed = self.isolated('trap_sigterm_then_complete:4.0', 0.5)
        self.assertIsNone(killed['late_result'])
        self.assertEqual(len(self.records('late_result')), 1)
        self.assertEqual(killed['failure'].data['termination']['method'], 'kill')
        self.assertEqual(killed['failure'].data['diagnostics']['stdout_excerpt'], '{')
        self.assertEqual(self.ledger.task_state(killed['task'].id), 'blocked')
        self.assertFalse(self.records('result'))
        self.forbid_promotion()

    def test_p5_09_proof_from_termination(self):
        for exited in (False, True):
            with self.subTest(exited=exited):
                task, attempt = self.partial_subprocess()
                self.ledger.add('execution_failure', {'task_id': task.id, 'attempt_id': attempt.id,
                    'stage': 'timeout', 'termination': {'exited': exited}})
                self.ledger.transition(task.id, 'running', 'blocked', 'ripley', 'deadline_exceeded')
                if exited:
                    self.assertEqual(self.recover(task)['outcome'], 'pending_owner_approval')
                else:
                    self.unchanged_rejection(lambda: self.recover(task, execution='inline'),
                                             message='prior execution not confirmed exited')

    def test_p5_10_diagnostics_tail(self):
        run = self.isolated('stderr:20000+raise')
        self.assertEqual(run['outcome'], 'blocked_worker_failure')
        diagnostics = run['failure'].data['diagnostics']
        self.assertEqual(dict(diagnostics), {'bytes_total': 20000, 'truncated': True, 'text': 'Z' * 8192})
        self.assertEqual(_excerpt(b'A' + b'\xc3\xa9' + b'Z' * 8191), '\ufffd' + 'Z' * 8191)
        success = self.isolated('stderr:20000')
        self.assertEqual(success['outcome'], 'pending_owner_approval')
        self.assertNotIn('diagnostics', success['result'].data)

    def test_p5_11_canonical_bytes_on_stdin(self):
        # Tee writes to the actual child's stdin. POSIX communicate uses os.write,
        # Windows uses the buffered stream. Both paths forward the actual write.
        sent = bytearray()
        real_communicate = subprocess.Popen.communicate

        def tee(proc, *args, **kwargs):
            if WINDOWS:
                original_write = proc.stdin.write
                def stream_write(data):
                    count = original_write(data)
                    sent.extend(data[:count])
                    return count
                with patch.object(proc.stdin, 'write', stream_write):
                    return real_communicate(proc, *args, **kwargs)
            fd = proc.stdin.fileno()
            original_write = os.write
            def fd_write(target, data):
                count = original_write(target, data)
                if target == fd:
                    sent.extend(data[:count])
                return count
            with patch.object(os, 'write', fd_write):
                return real_communicate(proc, *args, **kwargs)

        self.inputs['nested'] = {'z': 'é' * 2000, 'a': [True, None]}
        with patch.object(subprocess.Popen, 'communicate', tee):
            run = self.isolated()
        self.assertEqual(run['outcome'], 'pending_owner_approval')
        request = self.records('execution_request')[0]
        self.assertEqual(request.data['attempt_id'], run['attempt'].id)
        self.assertEqual(bytes(sent), canonical_json(request.data['packet']))
        self.assertEqual(set(request.data['packet']), {'envelope_version', 'attempt_id', 'task_id',
            'task_type', 'domain_id', 'domain_version', 'worker_identity', 'inputs', 'deadline_at'})

    def test_p5_12_modes_regressions_corrections_and_recovery(self):
        recovery_file = Path(__file__).with_name('test_recovery.py')
        self.assertEqual(hashlib.sha256(recovery_file.read_bytes()).hexdigest(),
                         'b0548e433be11c9988d0338b4e41250edfdaf2fe4bf3cfb026a8e420b57861ae')
        engine = self.engine()
        self.unchanged_rejection(lambda: engine.run(self.adapter, self.inputs, execution='remote'))
        inline = engine.run(self.adapter, self.inputs)
        self.assertEqual(inline['attempt'].data['execution'], 'inline')
        self.assertFalse(self.records('execution_request'))
        baseline = self.kinds()
        self.inputs['stock'] += 1
        ok = self.isolated()
        self.assertEqual(ok['outcome'], 'pending_owner_approval')
        isolated_kinds = self.kinds()[len(baseline):]
        self.assertEqual([kind for kind in isolated_kinds if kind != 'execution_request'], baseline)
        self.assertEqual(isolated_kinds.count('execution_request'), 1)
        self.inputs['stock'] += 1
        self.assertEqual(self.isolated('raise')['outcome'], 'blocked_worker_failure')
        bad = self.isolated('bad_output', correction_budget=1)
        self.assertEqual(bad['outcome'], 'blocked_budget_exhausted')
        self.assertEqual(len(bad['corrections']), 1)
        self.assertEqual(len(self.records('execution_attempt', bad['task'].id)), 2)
        self.assertEqual(len(self.records('correction_budget_exhaustion', bad['task'].id)), 1)
        self.assertEqual(self.ledger.task_state(bad['task'].id), 'blocked')
        attempts = self.records('execution_attempt', bad['task'].id)
        self.assertEqual([r.data['attempt_number'] for r in attempts], [1, 2])
        self.assertTrue(all(r.data['execution'] == 'subprocess' for r in attempts))
        timed = self.isolated('sleep:5', 0.5)
        self.assertIs(timed['failure'].data['termination']['exited'], True)
        self.unchanged_rejection(lambda: self.recover(timed['task'], execution='remote'))
        # Replay with the same slow worker so the second task is eligible
        # for the budget check instead of awaiting owner approval.
        recovered = self.recover(timed['task'], worker=self.worker, allowed_workers=(TEST_ID,))
        self.assertEqual(recovered['outcome'], 'blocked_timeout')
        self.assertEqual(recovered['authorization'].data['blocked_task_id'], timed['task'].id)
        self.assertEqual(recovered['task'].data['recovers_task_id'], timed['task'].id)
        self.assertEqual(recovered['task'].data['previous_task_id'], timed['task'].id)
        self.assertEqual(recovered['attempt'].data['execution'], 'subprocess')
        self.assertEqual(recovered['attempt'].data['replays_attempt_id'], timed['attempt'].id)
        before = len(self.ledger.records)
        with self.assertRaisesRegex(ValueError, 'recovery budget exhausted'):
            self.recover(recovered['task'])
        self.assertEqual(self.kinds()[before:], ['recovery_budget_exhaustion'])

    def test_p5_13_platform_and_registry_boundary(self):
        for name, test in IsolationContract.__dict__.items():
            if name.startswith('test_p5_'):
                self.assertEqual(bool(getattr(test, '__unittest_skip__', False)),
                                 WINDOWS and name.startswith(('test_p5_04', 'test_p5_08')), name)
        run = self.isolated()
        request = self.records('execution_request')[0].data['packet']
        def host(raw):
            return subprocess.run([sys.executable, '-m', 'ripley.worker_host'], input=raw,
                                  capture_output=True, timeout=5)
        self.assertEqual(run['outcome'], 'pending_owner_approval')
        with patch.dict(os.environ, {GATE: '0', BEHAVIOR: 'raise'}):
            for fields in ({}, {'worker_identity': 'unregistered'},
                           {'worker_identity': 'mock-worker', 'domain_id': 'unknown'},
                           {'worker_identity': 'mock-worker', 'domain_version': '2'}):
                reply = host(canonical_json({**request, **fields}))
                self.assertEqual((reply.returncode, reply.stdout), (3, b''))
            reply = host(canonical_json({**request, 'worker_identity': 'mock-worker'}))
            self.assertEqual(reply.returncode, 0)
            self.assertEqual(_response(reply.stdout, {**request, 'worker_identity': 'mock-worker'})['status'], 'ok')
        # A host orphan would reach this same deadline without any parent signal.
        expired = datetime.now(timezone.utc) - timedelta(seconds=3.1)
        with patch.dict(os.environ, {BEHAVIOR: 'sleep:5'}):
            reply = host(canonical_json({**request, 'deadline_at': expired.isoformat()}))
        self.assertEqual((reply.returncode, reply.stdout), (124, b''))
        for raw in (b'{}', b'not json', canonical_json({**request, 'extra': None}),
                    canonical_json(request)[:-1] + b',"inputs":{}}'):
            reply = host(raw)
            self.assertEqual((reply.returncode, reply.stdout), (2, b''))


class MemoryIsolationTests(IsolationContract, unittest.TestCase):
    pass


class SQLiteFixture:
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'ledger.sqlite'
        factories = patch.dict(vars(test_recovery), {'Ledger': lambda: SQLiteLedger(self.path)})
        factories.start()
        self.addCleanup(factories.stop)
        super().setUp()


class SQLiteIsolationTests(SQLiteFixture, IsolationContract, unittest.TestCase):
    pass


class SQLiteRestartTests(SQLiteFixture, IsolationFixtures, unittest.TestCase):
    def test_p5_14_restart_with_execution_request(self):
        now = datetime.now(timezone.utc)
        for deadline, stage in ((now + timedelta(minutes=5), 'interrupted'),
                                (now - timedelta(minutes=5), 'timeout'), (None, 'interrupted')):
            with self.subTest(stage=stage, deadline=deadline):
                self.inputs['stock'] += 1
                task, _ = self.partial_subprocess(deadline)
                self.ledger = SQLiteLedger(self.path)
                failure = self.records('execution_failure', task.id)[-1].data
                self.assertEqual(failure['stage'], stage)
                self.assertNotIn('termination', failure)
                if stage == 'timeout':
                    self.assertEqual(failure['message'], 'deadline_exceeded_before_restart')
                if deadline is None:
                    self.clock.now = now + timedelta(days=1000)
                    self.unchanged_rejection(lambda: self.recover(task),
                                             message='prior execution not confirmed exited')
                    continue
                threshold = deadline + timedelta(seconds=4)
                for delta in (-1, 0):
                    self.clock.now = threshold + timedelta(microseconds=delta)
                    self.unchanged_rejection(lambda: self.recover(task),
                                             message='prior execution not confirmed exited')
                self.clock.now = threshold + timedelta(microseconds=1)
                self.assertEqual(self.recover(task)['outcome'], 'pending_owner_approval')

    def test_p5_15_restart_before_execution_request(self):
        task, attempt = self.partial_subprocess(requested=False)
        self.ledger = SQLiteLedger(self.path)
        self.assertEqual(self.records('execution_failure', task.id)[-1].data['stage'], 'interrupted')
        run = self.recover(task)
        self.assertEqual(run['outcome'], 'pending_owner_approval')
        self.assertEqual(run['attempt'].data['execution'], 'subprocess')
        self.assertEqual(run['attempt'].data['replays_attempt_id'], attempt.id)
