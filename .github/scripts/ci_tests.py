"""Advisory CI test runner: complete regression evidence or a red check.

Development tooling only. Not part of Ripley One runtime.
Run from the root of a disposable copy of the repository:
    python .github/scripts/ci_tests.py --self-check
    python .github/scripts/ci_tests.py
"""
import os
import socket
import sys
import unittest

LOOPBACK = ('127.', 'localhost', '::1')


def verdict(result):
    """Return a list of reasons the run is not acceptable. Empty means green."""
    reasons = []
    if result.testsRun == 0:
        reasons.append('zero tests ran')
    if result.failures:
        reasons.append('%d failure(s)' % len(result.failures))
    if result.errors:
        reasons.append('%d error(s)' % len(result.errors))
    if result.skipped:
        reasons.append('%d skipped' % len(result.skipped))
    if result.unexpectedSuccesses:
        reasons.append('%d unexpected success(es)' % len(result.unexpectedSuccesses))
    return reasons


def guard_network():
    """Refuse non-loopback connections made by the test process itself."""
    def guarded(original):
        def call(self, address):
            host = address[0] if isinstance(address, tuple) else None
            if isinstance(host, str) and not host.startswith(LOOPBACK):
                raise AssertionError('CI test phase attempted a network connection')
            return original(self, address)
        return call

    socket.socket.connect = guarded(socket.socket.connect)
    socket.socket.connect_ex = guarded(socket.socket.connect_ex)


def self_check():
    """Prove the verdict rule on tiny suites before trusting it on the real one."""
    class Sample(unittest.TestCase):
        def passes(self):
            pass

        def fails(self):
            self.fail('expected')

        def errors(self):
            raise RuntimeError('expected')

        def skips(self):
            self.skipTest('expected')

    def run(*names):
        suite = unittest.TestSuite(Sample(name) for name in names)
        with open(os.devnull, 'w') as quiet:
            return verdict(unittest.TextTestRunner(stream=quiet).run(suite))

    expected = {
        (): ['zero tests ran'],
        ('passes',): [],
        ('passes', 'fails'): ['1 failure(s)'],
        ('passes', 'errors'): ['1 error(s)'],
        ('passes', 'skips'): ['1 skipped'],
    }
    for names, want in expected.items():
        got = run(*names)
        print('self-check %-24s -> %s' % ('+'.join(names) or 'empty', got or 'green'))
        if got != want:
            print('SELF-CHECK FAILED')
            return 1
    guard_network()
    for name in ('connect', 'connect_ex'):
        probe = socket.socket()
        try:
            getattr(probe, name)(('192.0.2.1', 9))
        except AssertionError:
            print('self-check network guard %-7s -> refused' % name)
        else:
            print('SELF-CHECK FAILED: network guard did not refuse %s' % name)
            return 1
        finally:
            probe.close()
    print('SELF-CHECK PASSED')
    return 0


def main(argv):
    if argv == ['--self-check']:
        return self_check()
    if argv:
        print('usage: ci_tests.py [--self-check]')
        return 2
    guard_network()
    sys.path.insert(0, os.getcwd())
    suite = unittest.defaultTestLoader.discover('tests')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    reasons = verdict(result)
    print('CI SUMMARY: run=%d failures=%d errors=%d skipped=%d' % (
        result.testsRun, len(result.failures), len(result.errors), len(result.skipped)))
    for test, why in result.skipped:
        print('SKIPPED: %s: %s' % (test, why))
    if reasons:
        print('CI RESULT: FAILED (%s)' % '; '.join(reasons))
        return 1
    print('CI RESULT: PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
