"""ADR-011: one offline receipt and its separately retained bytes."""
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from ripley import capture
from ripley.core import Ledger
from ripley.storage import SQLiteLedger


class CaptureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / 'approved'
        self.root.mkdir()
        self.source = self.root / 'example.bin'
        self.raw = b'example\x00\r\n\xff'
        self.source.write_bytes(self.raw)
        self.store = self.base / 'store'
        self.ledger = Ledger()
        self.now = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
        self.args = dict(approved_root=self.root, source_id='sample.1', source_location='fixture:1',
                         supplied_by='test', content_type='application/octet-stream',
                         clock=lambda: self.now)

    def take(self, **changes):
        return capture.capture_file(self.ledger, self.store, self.source, **(self.args | changes))

    def refused(self, reason, **changes):
        with self.assertRaises(capture.CaptureError) as raised:
            self.take(**changes)
        self.assertEqual(raised.exception.reason, reason)
        self.assertFalse(self.ledger.records)

    def files(self):
        return sorted(p for p in self.store.rglob('*') if p.is_file())

    def object(self, data):
        digest = hashlib.sha256(data).hexdigest()
        return self.store / 'sha256' / digest[:2] / digest

    def test_cap_01_receipt(self):
        record = self.take()
        self.assertEqual(list(self.ledger.records), [record.id])
        self.assertEqual(record.kind, 'capture')
        self.assertEqual(dict(record.data), {
            'capture_version': '1', 'source_id': 'sample.1', 'source_location': 'fixture:1',
            'source_filename': 'example.bin', 'intake_method': 'local-file', 'supplied_by': 'test',
            'content_type': 'application/octet-stream', 'sha256': hashlib.sha256(self.raw).hexdigest(),
            'size_bytes': len(self.raw), 'captured_at': self.now.isoformat(),
            'declared_retrieved_at': None, 'declared_effective_at': None,
        })

    def test_cap_02_exact_bytes(self):
        record = self.take()
        self.assertEqual(self.object(self.raw).read_bytes(), self.source.read_bytes())
        self.assertEqual(record.data['sha256'], hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_cap_03_restart(self):
        db = self.base / 'ledger.sqlite'
        self.ledger = SQLiteLedger(db)
        record = self.take()
        reopened = SQLiteLedger(db)
        self.assertEqual(reopened.records[record.id].content_hash, record.content_hash)
        self.assertEqual(capture.verify_capture(reopened, self.store, record.id)[0], 'MATCHED')

    def test_cap_04_repeat(self):
        first = self.take()
        with patch.object(os, 'replace', side_effect=AssertionError('rewrote object')):
            second = self.take()
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.data['sha256'], second.data['sha256'])
        self.assertEqual(len(self.ledger.records), 2)
        self.assertEqual(self.files(), [self.object(self.raw)])

    def test_cap_05_mutation(self):
        first = self.take()
        self.source = self.root / 'second.bin'
        self.source.write_bytes(self.raw[:-1] + b'!')
        second = self.take()
        self.assertNotEqual(first.data['sha256'], second.data['sha256'])
        self.assertEqual(len(self.files()), 2)

    def test_cap_06_missing(self):
        self.source.unlink()
        self.refused('source_missing')
        self.assertFalse(self.files())

    def test_cap_07_unapproved(self):
        outside = self.base / 'outside'
        outside.write_bytes(self.raw)
        for self.source in (outside, self.root / '..' / 'outside', self.root,
                            'scheme://remote/source', '//remote/share/file'):
            with self.subTest(source=self.source):
                self.refused('source_unapproved')
                self.assertFalse(self.files())

    def test_cap_08_invalid_metadata(self):
        for change in [dict(source_id='bad id'), dict(supplied_by=''),
                       dict(declared_effective_at='2026-01-02T12:00:00')]:
            with self.subTest(change=change):
                self.refused('invalid_metadata', **change)
        self.assertFalse(self.files())

    def test_cap_09_too_large(self):
        self.refused('too_large', max_bytes=len(self.raw) - 1)
        self.assertFalse(self.files())

    def test_cap_10_read_interrupted(self):
        original = Path.open
        def broken_open(path, mode):
            stream = original(path, mode)
            read = stream.read
            def interrupted(limit):
                read(1)
                raise OSError('interrupted')
            stream.read = interrupted
            return stream
        with patch.object(Path, 'open', broken_open):
            self.refused('read_interrupted')
        with patch.object(os, 'fstat', return_value=Mock(st_size=len(self.raw) + 1)):
            self.refused('read_interrupted')
        with patch.object(Path, 'open', side_effect=PermissionError()):
            self.refused('source_unreadable')
        self.assertFalse(self.files())

    def test_cap_11_artifact_failure(self):
        with patch.object(os, 'replace', side_effect=OSError('replace failed')):
            self.refused('artifact_write_failed')
        self.assertFalse(self.files())
        path = self.object(self.raw)
        path.write_bytes(b'corrupt')
        self.refused('store_corrupt')
        self.assertEqual(path.read_bytes(), b'corrupt')

    def test_cap_12_ledger_failure(self):
        with patch.object(self.ledger, 'add', side_effect=OSError('append failed')):
            self.refused('ledger_write_failed')
        self.assertEqual(self.object(self.raw).read_bytes(), self.raw)

    def test_cap_13_verify(self):
        record = self.take()
        def status(key):
            return capture.verify_capture(self.ledger, self.store, key)[0]
        self.assertEqual(status(record.id), 'MATCHED')
        wrong_size = self.ledger.add('capture', dict(record.data) | {'size_bytes': 0})
        self.assertEqual(status(wrong_size.id), 'MISMATCHED')
        path = self.object(self.raw)
        path.write_bytes(self.raw[:-1] + b'!')
        self.assertEqual(status(record.id), 'MISMATCHED')
        path.unlink()
        self.assertEqual(status(record.id), 'UNAVAILABLE')
        self.assertEqual(status('unknown'), 'UNAVAILABLE')
        self.assertEqual(status(self.ledger.add('note', {}).id), 'UNAVAILABLE')

    def test_cap_14_capture_time(self):
        self.refused('invalid_metadata', clock=lambda: self.now.replace(tzinfo=None))
        events = []
        original = Path.open
        def observed_open(path, *args, **kwargs):
            stream = original(path, *args, **kwargs)
            if path == self.source:
                read = stream.read
                def observed_read(limit):
                    data = read(limit)
                    events.append('read complete')
                    return data
                stream.read = observed_read
            return stream
        def clock():
            events.append('clock')
            self.assertFalse(self.store.exists())
            return self.now
        replace = os.replace
        def publish(src, dest):
            events.append('publish')
            return replace(src, dest)
        with patch.object(Path, 'open', observed_open), patch.object(os, 'replace', publish):
            record = self.take(clock=clock, declared_retrieved_at='2025-12-03T06:00:00-06:00',
                               declared_effective_at='2025-12-01T09:30:00+02:00')
        self.assertEqual(events, ['read complete', 'clock', 'publish'])
        self.assertEqual(record.data['captured_at'], self.now.isoformat())
        self.assertEqual(record.data['declared_retrieved_at'], '2025-12-03T12:00:00+00:00')
        self.assertEqual(record.data['declared_effective_at'], '2025-12-01T07:30:00+00:00')

    def test_cap_15_store_location(self):
        self.store = Path(capture.__file__).resolve().parents[1] / 'cap-15-invalid-store'
        self.assertFalse(self.store.exists())
        self.refused('store_invalid')
        self.assertFalse(self.store.exists())

    def test_cap_16_zero_network(self):
        with patch('socket.socket.connect', side_effect=AssertionError) as connect, \
                patch('socket.create_connection', side_effect=AssertionError) as create:
            record = self.take()
            self.assertEqual(capture.verify_capture(self.ledger, self.store, record.id)[0], 'MATCHED')
        connect.assert_not_called()
        create.assert_not_called()

    def test_cap_17_zero_provider(self):
        text = Path(capture.__file__).read_text(encoding='utf-8')
        for forbidden in ('RIPLEY_', 'import socket', 'urllib', 'http', 'anthropic', 'nfl'):
            self.assertNotIn(forbidden, text)
        script = """
import sys
from datetime import datetime, timezone
from pathlib import Path
from ripley.capture import capture_file, verify_capture
from ripley.core import Ledger
source, store = map(Path, sys.argv[1:])
ledger = Ledger()
record = capture_file(ledger, store, source, approved_root=source.parent, source_id='test',
                      source_location='fixture', supplied_by='test', content_type='binary',
                      clock=lambda: datetime(2026, 1, 2, tzinfo=timezone.utc))
assert verify_capture(ledger, store, record.id)[0] == 'MATCHED'
unexpected = set(sys.modules).intersection(['anthropic', 'httpx2', 'ripley.providers',
    'ripley.workers', 'ripley.worker_host', 'ripley.isolation', 'ripley.nfl_availability'])
assert not unexpected, unexpected
"""
        subprocess.run([sys.executable, '-B', '-c', script, str(self.source), str(self.store)],
                       cwd=Path(capture.__file__).resolve().parents[1], check=True)
