"""Offline preflight contract. Every repository mutation uses a temporary copy."""
from contextlib import redirect_stdout
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import pilot_preflight as preflight

ROOT = Path(__file__).resolve().parents[1]
PACKET = 'fixtures/nfl-availability/TB-at-CHI-2026-11-08.json'
PROMPT = 'ripley/prompts/nfl-availability/1.md'
DIGESTS = {
    'expected-packet-sha256': '1ce3f332e1e8ff7aa113bbb0cd2688583086c29a050be909d9607e1a3c2c0aa6',
    'expected-prompt-sha256': '7d5094d53f2e1f4924b1daa727a7fb7563048743082306908825604d3da06904',
    'expected-schema-sha256': 'bbefc6a8fce78143a8c0ff5eb918db4a43373af7bbe578348fca96f3dd47f41a',
}


class PilotPreflightTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        for directory in ('ripley', 'scripts', 'fixtures'):
            shutil.copytree(ROOT / directory, self.repo / directory,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for filename in ('requirements-providers.txt', '.gitattributes'):
            shutil.copyfile(ROOT / filename, self.repo / filename)
        self.git('init', '-q')
        self.baseline = self.commit()
        self.opts = {'repo': str(self.repo), 'baseline': self.baseline,
                     'packet': str(self.repo / PACKET), **DIGESTS,
                     'expected-interpreter': sys.executable,
                     'expected-python': f'{sys.version_info.major}.{sys.version_info.minor}'}
        version = patch.object(importlib.metadata, 'version', return_value='2.9.0')
        self.version = version.start()
        self.addCleanup(version.stop)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args]).decode().strip()

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def argv(self):
        return [item for k, v in self.opts.items() for item in ('--' + k, v)]

    def check(self, mismatched=(), unavailable=()):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = preflight.main(self.argv())
        output = stream.getvalue()
        expected = ['MISMATCHED' if i in mismatched else 'UNAVAILABLE' if i in unavailable
                    else 'MATCHED' for i in range(1, 13)]
        self.assertEqual(re.findall(r'^\d\d .*? \| (\w+) \|', output, re.M), expected, output)
        self.assertEqual(code, int(bool(mismatched or unavailable)))
        return output

    def append_byte(self, path):
        with (self.repo / path).open('ab') as file:
            file.write(b' ')

    def test_pf_01_correct_identities(self):
        self.opts['expected-head'] = self.baseline
        out = self.check()
        for i, value in enumerate(DIGESTS.values(), 6):
            self.assertRegex(out, rf'(?m)^{i:02} .*? \| MATCHED \| {value}$')
        self.assertTrue(out.endswith('OFFLINE PREFLIGHT: PASSED\n'))

    def test_pf_02_packet_mutation(self):
        path = self.repo / PACKET
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b'Questionable', b'questionable', 1))
        self.opts['baseline'] = self.commit()
        self.check((6,))

    def test_pf_03_prompt_mutation(self):
        path = self.repo / PROMPT
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        self.opts['baseline'] = self.commit()
        self.check((7,))

    def test_pf_04_schema_mutation(self):
        path = self.repo / 'ripley/nfl_availability.py'
        path.write_bytes(path.read_bytes().replace(b"'enum': ['out'", b"'enum': ['other'", 1))
        self.opts['baseline'] = self.commit()
        self.check((8,))

    def test_pf_05_implementation_drift(self):
        self.append_byte('scripts/pilot_dispatch.py')
        self.commit()
        self.assertIn('scripts/pilot_dispatch.py', self.check((3,)))

    def test_pf_06_docs_only(self):
        (self.repo / 'docs').mkdir()
        (self.repo / 'docs/example.md').write_bytes(b'fixture')
        self.commit()
        self.assertIn('non-governed=1 ["docs"]', self.check())

    def test_pf_07_uncommitted(self):
        self.append_byte('scripts/pilot_dispatch.py')
        self.check((4,))
        self.git('add', 'scripts/pilot_dispatch.py')
        self.check((4,))

    def test_pf_08_untracked(self):
        cache = self.repo / 'ripley/__pycache__'
        cache.mkdir(exist_ok=True)
        (cache / 'x.pyc').touch()
        (self.repo / 'pilot').mkdir()
        (self.repo / 'pilot/x.sqlite').touch()
        self.assertIn('non-governed=1 ["pilot"]', self.check())
        (self.repo / 'scripts/added.py').touch()
        self.assertIn('scripts/added.py', self.check((5,)))

    def test_pf_18_ignored_paths(self):
        with (self.repo / '.git/info/exclude').open('a') as rules:
            rules.write('\n/scripts/extra2.py\n/ripley/__pycache__/\n/pilot/\n')
        for directory in ('ripley/__pycache__', 'pilot'):
            path = self.repo / directory
            path.mkdir(exist_ok=True)
            (path / 'entry').touch()
        self.check()
        (self.repo / 'scripts/extra2.py').touch()
        self.assertIn('05 Untracked files | MISMATCHED | governed=1 ["scripts/extra2.py"]',
                      self.check((5,)))

    def test_pf_09_missing_history(self):
        self.opts['baseline'] = '0' * 40
        self.check(unavailable=(2, 3))

    def test_pf_10_missing_files(self):
        self.opts['packet'] = str(self.repo / 'absent.json')
        (self.repo / PROMPT).unlink()
        self.opts['baseline'] = self.commit()
        self.check(unavailable=(6, 7))

    def test_pf_11_malformed_hashes(self):
        for bad in ('a' * 63, 'A' * 64, 'x' * 64):
            with self.subTest(bad=bad):
                self.opts['expected-schema-sha256'] = bad
                self.check(unavailable=(8,))

    def test_pf_12_absent_sdk(self):
        self.version.side_effect = importlib.metadata.PackageNotFoundError()
        self.check(unavailable=(11, 12))

    def test_pf_13_wrong_sdk_version(self):
        self.version.return_value = '0.0.1'
        self.check((12,))

    def test_pf_14_no_sensitive_output(self):
        canary = 'synthetic-preflight-canary'
        packet = json.loads((self.repo / PACKET).read_bytes())
        with patch.dict(os.environ, {'RIPLEY_ANTHROPIC_API_KEY': canary}):
            output = self.check()
        for text in [canary] + [r[k] for r in packet['rows'] for k in ('name', 'text')]:
            self.assertNotIn(text, output)

    def test_pf_15_zero_socket_attempts(self):
        with patch.object(socket.socket, 'connect', side_effect=AssertionError) as connect, \
                patch.object(socket, 'create_connection', side_effect=AssertionError) as create:
            self.check()
        connect.assert_not_called()
        create.assert_not_called()

    def test_pf_16_no_provider_modules(self):
        source = (self.repo / 'scripts/pilot_preflight.py').read_text('utf-8')
        for token in ('RIPLEY_', 'input(', 'sqlite3', 'import anthropic'):
            self.assertNotIn(token, source)
        code = """import runpy, sys
from unittest.mock import patch
module = runpy.run_path('scripts/pilot_preflight.py')
with patch('importlib.metadata.version', return_value='2.9.0'):
    assert module['main'](sys.argv[1:]) == 0
for name in ('anthropic','httpx2','ripley.providers','ripley.storage','ripley.isolation',
             'ripley.worker_host','ripley.workers'):
    assert name not in sys.modules, name
"""
        subprocess.run([sys.executable, '-I', '-B', '-c', code, *self.argv()],
                       cwd=self.repo, check=True, capture_output=True)

    def test_pf_17_no_files_written(self):
        path = self.repo / 'pilot/x.sqlite'
        path.parent.mkdir()
        path.write_bytes(b'evidence sentinel')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        before = self.git('--no-optional-locks', 'status', '--porcelain', '--untracked-files=all')
        self.check()
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        self.assertEqual(list(self.repo.rglob('*.sqlite')), [path])
        self.assertEqual(self.git('--no-optional-locks', 'status', '--porcelain',
                                  '--untracked-files=all'), before)
