"""Advisory CI test runner: complete regression evidence or a red check.

Development tooling only. Not part of Ripley One runtime.
Run from the root of a disposable copy of the repository:
    python .github/scripts/ci_tests.py --self-check
    python .github/scripts/ci_tests.py
"""
import ipaddress
import os
import socket
import sys
import unittest


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


def is_loopback(host):
    """True only for the exact name localhost or a numeric loopback IP address."""
    if isinstance(host, (bytes, bytearray)):
        try:
            host = bytes(host).decode('ascii')
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def guard_network():
    """Refuse non-loopback connections made by the test process itself."""
    def guarded(original):
        def call(self, address):
            if isinstance(address, tuple) and not is_loopback(address[0] if address else None):
                raise AssertionError('CI test phase attempted a network connection')
            return original(self, address)
        return call

    socket.socket.connect = guarded(socket.socket.connect)
    socket.socket.connect_ex = guarded(socket.socket.connect_ex)


def self_check():
    """Prove the verdict rule and the loopback rule before trusting them."""
    class Sample(unittest.TestCase):
        def passes(self):
            pass

        def fails(self):
            self.fail('expected')

        def errors(self):
            raise RuntimeError('expected')

        def skips(self):
            self.skipTest('expected')

        @unittest.expectedFailure
        def unexpected(self):
            pass

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
        ('passes', 'unexpected'): ['1 unexpected success(es)'],
    }
    for names, want in expected.items():
        got = run(*names)
        print('self-check %-24s -> %s' % ('+'.join(names) or 'empty', got or 'green'))
        if got != want:
            print('SELF-CHECK FAILED')
            return 1

    hosts = {
        'localhost': True,
        '127.0.0.1': True,
        '127.255.255.254': True,
        '::1': True,
        b'127.0.0.1': True,
        'localhost.example.com': False,
        'localhostx': False,
        '127.example.com': False,
        'LOCALHOST': False,
        '192.0.2.1': False,
        b'192.0.2.1': False,
        '': False,
        None: False,
    }
    for host, want in hosts.items():
        got = is_loopback(host)
        print('self-check loopback %-24r -> %s' % (
            host, 'loopback' if got else 'not loopback'))
        if got != want:
            print('SELF-CHECK FAILED')
            return 1

    guard_network()
    for name in ('connect', 'connect_ex'):
        for host in ('192.0.2.1', 'localhost.example.com', b'192.0.2.1'):
            probe = socket.socket()
            try:
                getattr(probe, name)((host, 9))
            except AssertionError:
                print('self-check guard %-10s %-24r -> refused' % (name, host))
            else:
                print('SELF-CHECK FAILED: guard did not refuse %s to %r' % (
                    name, host))
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
        result.testsRun,
        len(result.failures),
        len(result.errors),
        len(result.skipped),
    ))

    for test, why in result.skipped:
        print('SKIPPED: %s: %s' % (test, why))

    if reasons:
        print('CI RESULT: FAILED (%s)' % '; '.join(reasons))
        return 1

    print('CI RESULT: PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
