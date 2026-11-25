"""Advisory CI test runner: complete regression evidence or a red check.

Development tooling only. Not part of Ripley One runtime.
Run from the root of a disposable copy of the repository:
    python .github/scripts/ci_tests.py --self-check
    python .github/scripts/ci_tests.py
    python .github/scripts/ci_tests.py --expected-skip TEST_ID [--expected-skip TEST_ID ...]
"""
import contextlib
import io
import ipaddress
import os
import re
import socket
import sys
import unittest


USAGE = 'usage: ci_tests.py [--self-check | --expected-skip TEST_ID ...]'

REFUSED_COMBINED = '--self-check cannot be combined with other arguments'
REFUSED_UNSUPPORTED = 'unsupported argument'
REFUSED_MISSING_VALUE = 'missing value for --expected-skip'
REFUSED_MALFORMED = 'malformed expected skip'
REFUSED_DUPLICATE = 'duplicate expected skip'

# Three or more ASCII identifier parts joined by single full stops; whole value.
TEST_IDENTITY = re.compile(
    r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){2,}')


def parse_args(argv):
    """Classify the command line without side effects.

    Returns ('default', None), ('self-check', None),
    ('configured', [identities]) or ('refused', reason).
    The refused value itself is never part of the result.
    """
    argv = list(argv)
    if not argv:
        return ('default', None)
    if argv == ['--self-check']:
        return ('self-check', None)
    if '--self-check' in argv:
        return ('refused', REFUSED_COMBINED)
    expected = []
    position = 0
    while position < len(argv):
        if argv[position] != '--expected-skip':
            return ('refused', REFUSED_UNSUPPORTED)
        if position + 1 >= len(argv):
            return ('refused', REFUSED_MISSING_VALUE)
        value = argv[position + 1]
        if not isinstance(value, str) or TEST_IDENTITY.fullmatch(value) is None:
            return ('refused', REFUSED_MALFORMED)
        if value in expected:
            return ('refused', REFUSED_DUPLICATE)
        expected.append(value)
        position += 2
    return ('configured', expected)


def skip_difference(skipped, expected):
    """Compare recorded skips with expected identities by exact id() string.

    Returns (missing, unexpected, duplicated), each sorted ascending.
    Skip reasons are never compared.
    """
    observed = [test.id() for test, _ in skipped]
    observed_set = set(observed)
    expected_set = set(expected)
    missing = sorted(identity for identity in expected if identity not in observed_set)
    unexpected = sorted(observed_set - expected_set)
    duplicated = sorted(
        identity for identity in observed_set if observed.count(identity) > 1)
    return missing, unexpected, duplicated


def verdict(result, expected=None):
    """Return a list of reasons the run is not acceptable. Empty means green.

    Without expected identities any skip is a reason. With them, the skip
    reason is replaced by a reason present only when the skips differ.
    """
    reasons = []
    if result.testsRun == 0:
        reasons.append('zero tests ran')
    if result.failures:
        reasons.append('%d failure(s)' % len(result.failures))
    if result.errors:
        reasons.append('%d error(s)' % len(result.errors))
    if expected is None:
        if result.skipped:
            reasons.append('%d skipped' % len(result.skipped))
    else:
        missing, unexpected, duplicated = skip_difference(result.skipped, expected)
        if missing or unexpected or duplicated:
            reasons.append(
                'skips differ from expected: %d missing, %d unexpected, %d duplicated'
                % (len(missing), len(unexpected), len(duplicated)))
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
    """Prove the verdict, argument and loopback rules before trusting them."""
    skip_reason = ['expected']

    class Sample(unittest.TestCase):
        def passes(self):
            pass

        def fails(self):
            self.fail('expected')

        def errors(self):
            raise RuntimeError('expected')

        def skips(self):
            self.skipTest(skip_reason[0])

        def skips_too(self):
            self.skipTest(skip_reason[0])

        @unittest.expectedFailure
        def unexpected(self):
            pass

    def outcome(names):
        suite = unittest.TestSuite(Sample(name) for name in names)
        with open(os.devnull, 'w') as quiet:
            return unittest.TextTestRunner(stream=quiet).run(suite)

    def run(*names):
        return verdict(outcome(names))

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
                print('SELF-CHECK FAILED')
                return 1
            finally:
                probe.close()

    # Expected-skip verdict cases. Identities come from the sample tests' id().
    a = Sample('skips').id()
    b = Sample('skips_too').id()
    prefix = b.startswith(a) and b != a
    print('self-check identity A is a strict prefix of identity B -> %s' % (
        'yes' if prefix else 'no'))
    if not prefix:
        print('SELF-CHECK FAILED')
        return 1

    def differ(missing, unexpected, duplicated):
        return 'skips differ from expected: %d missing, %d unexpected, %d duplicated' % (
            missing, unexpected, duplicated)

    default_reason = skip_reason[0]
    other_reason = 'a different reason'
    verdict_cases = [
        ('V1', [a, b], ('passes', 'skips', 'skips_too'), default_reason, []),
        ('V2', [a, b], ('passes', 'skips_too', 'skips'), default_reason, []),
        ('V3', [a], ('passes', 'skips', 'skips_too'), default_reason,
         [differ(0, 1, 0)]),
        ('V4', [a, b], ('passes', 'skips'), default_reason, [differ(1, 0, 0)]),
        ('V5', [a], ('passes', 'skips_too'), default_reason, [differ(1, 1, 0)]),
        ('V6', [a], ('passes',), default_reason, [differ(1, 0, 0)]),
        ('V7', [a], ('passes', 'skips', 'skips'), default_reason, [differ(0, 0, 1)]),
        ('V8', [a.upper()], ('passes', 'skips'), default_reason, [differ(1, 1, 0)]),
        ('V9', [a], ('skips', 'fails'), default_reason, ['1 failure(s)']),
        ('V10', [a], ('skips', 'errors'), default_reason, ['1 error(s)']),
        ('V11', [a], ('skips', 'unexpected'), default_reason,
         ['1 unexpected success(es)']),
        ('V12', [a], (), default_reason, ['zero tests ran', differ(1, 0, 0)]),
        ('V13', [a], ('skips_too', 'fails', 'errors', 'unexpected'), default_reason,
         ['1 failure(s)', '1 error(s)', differ(1, 1, 0), '1 unexpected success(es)']),
        ('V14', [b], ('passes', 'skips'), default_reason, [differ(1, 1, 0)]),
        ('V15', [a], ('passes', 'skips'), other_reason, []),
    ]
    if a.upper() == a:
        print('self-check V8 upper-case identity is not distinct')
        print('SELF-CHECK FAILED')
        return 1
    for label, expected_ids, names, reason, want in verdict_cases:
        skip_reason[0] = reason
        try:
            result = outcome(names)
        finally:
            skip_reason[0] = default_reason
        reasons_seen = sorted(set(why for _, why in result.skipped))
        if reasons_seen and reasons_seen != [reason]:
            print('self-check %-4s sample skip reason was not as arranged' % label)
            print('SELF-CHECK FAILED')
            return 1
        got = verdict(result, expected_ids)
        print('self-check %-4s -> %s' % (label, got or 'green'))
        if got != want:
            print('SELF-CHECK FAILED')
            return 1

    # Argument cases. parse_args is called directly; no process, no suite.
    x = 'test_sample.SampleTests.test_one'
    y = 'test_sample.SampleTests.test_two'
    flag = '--expected-skip'
    argument_cases = [
        ('A1', [], ('default', None)),
        ('A2', ['--self-check'], ('self-check', None)),
        ('A3', [flag, x], ('configured', [x])),
        ('A4', [flag, x, flag, y], ('configured', [x, y])),
        ('A5', [flag], ('refused', REFUSED_MISSING_VALUE)),
        ('A6', [flag, x, flag], ('refused', REFUSED_MISSING_VALUE)),
        ('A7', [flag, x, flag, x], ('refused', REFUSED_DUPLICATE)),
        ('A8', ['--verbose'], ('refused', REFUSED_UNSUPPORTED)),
        ('A9', [flag + '=' + x], ('refused', REFUSED_UNSUPPORTED)),
        ('A10', ['--self-check', flag, x], ('refused', REFUSED_COMBINED)),
        ('A11', [flag, x, '--self-check'], ('refused', REFUSED_COMBINED)),
        ('A12', [flag, ''], ('refused', REFUSED_MALFORMED)),
        ('A13', [flag, 'test_sample'], ('refused', REFUSED_MALFORMED)),
        ('A14', [flag, 'test_sample.SampleTests'], ('refused', REFUSED_MALFORMED)),
        ('A15', [flag, x + ' '], ('refused', REFUSED_MALFORMED)),
        ('A16', [flag, x + '\n'], ('refused', REFUSED_MALFORMED)),
        ('A17', [flag, x + ' (i=1)'], ('refused', REFUSED_MALFORMED)),
        ('A18', [flag, 'setUpClass (test_sample.SampleTests)'],
         ('refused', REFUSED_MALFORMED)),
        ('A19', [flag, 'test_sample.SampleTests.test_*'], ('refused', REFUSED_MALFORMED)),
        ('A20', ['--verbose', '--self-check'], ('refused', REFUSED_COMBINED)),
        ('A21', [flag, '--self-check'], ('refused', REFUSED_COMBINED)),
        ('A22', [flag, flag], ('refused', REFUSED_MALFORMED)),
        ('A23', [flag, '--verbose'], ('refused', REFUSED_MALFORMED)),
        ('A24', [flag, ' ' + x], ('refused', REFUSED_MALFORMED)),
        ('A25', [flag, 'test_sample.SampleéTests.test_one'],
         ('refused', REFUSED_MALFORMED)),
        ('A26', [flag, 'test_sample..SampleTests.test_one'],
         ('refused', REFUSED_MALFORMED)),
        # Supplementary: --self-check in an interior position, flag and value.
        ('S1', [flag, x, '--self-check', flag, y], ('refused', REFUSED_COMBINED)),
        ('S2', [flag, '--self-check', flag, x], ('refused', REFUSED_COMBINED)),
    ]
    for label, argv, want in argument_cases:
        got = parse_args(argv)
        mode, detail = got
        if mode == 'refused':
            shown = 'refused: %s' % detail
        elif mode == 'configured':
            shown = 'configured, %d identity(ies)' % len(detail)
        else:
            shown = mode
        print('self-check %-4s -> %s' % (label, shown))
        if got != want:
            print('SELF-CHECK FAILED')
            return 1

    # Refusal output: entry function in-process, output captured, no suite.
    forged = x + '\nCI RESULT: PASSED'
    discovered = []
    loader = unittest.defaultTestLoader
    original_discover = loader.discover

    def no_discover(*args, **kwargs):
        discovered.append(args)
        return unittest.TestSuite()

    loader.discover = no_discover
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            status = main([flag, forged])
    finally:
        loader.discover = original_discover
    text = captured.getvalue()
    want_text = 'ARGUMENT REFUSED: %s\n%s\n' % (REFUSED_MALFORMED, USAGE)
    echoed = forged in text or x in text
    print('self-check R1   -> status %d, exact output %s, value echoed %s, '
          'suite discovered %s' % (
              status, 'yes' if text == want_text else 'no',
              'yes' if echoed else 'no', 'yes' if discovered else 'no'))
    if status != 2 or text != want_text or echoed or discovered:
        print('SELF-CHECK FAILED')
        return 1

    print('SELF-CHECK PASSED')
    return 0


def main(argv):
    mode, detail = parse_args(argv)
    if mode == 'refused':
        print('ARGUMENT REFUSED: %s' % detail)
        print(USAGE)
        return 2
    if mode == 'self-check':
        return self_check()
    expected = detail

    guard_network()
    sys.path.insert(0, os.getcwd())
    suite = unittest.defaultTestLoader.discover('tests')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    reasons = verdict(result, expected)

    print('CI SUMMARY: run=%d failures=%d errors=%d skipped=%d' % (
        result.testsRun,
        len(result.failures),
        len(result.errors),
        len(result.skipped),
    ))

    for test, why in result.skipped:
        print('SKIPPED: %s: %s' % (test, why))

    if expected is not None:
        missing, unexpected, duplicated = skip_difference(result.skipped, expected)
        for identity in sorted(expected):
            print('EXPECTED SKIP: %s' % identity)
        for identity in missing:
            print('MISSING EXPECTED SKIP: %s' % identity)
        for identity in unexpected:
            print('UNEXPECTED SKIP: %s' % identity)
        for identity in duplicated:
            print('DUPLICATE SKIP: %s' % identity)

    if reasons:
        print('CI RESULT: FAILED (%s)' % '; '.join(reasons))
        return 1

    if expected is None:
        print('CI RESULT: PASSED')
    else:
        print('CI RESULT: PASSED (%d expected skips)' % len(expected))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
