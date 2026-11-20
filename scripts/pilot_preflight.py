"""Read-only, point-in-time checks of a local pilot checkout."""
import argparse
import fnmatch
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

NOTICE = '''"Offline preflight checks passed" does not mean:
- dispatch authorized;
- provider acceptance established;
- live compatibility verified;
- recovery verified;
- files cannot change after verification.'''

CHILD = """import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from ripley.nfl_availability import NflAvailabilityAdapter
print(json.dumps(NflAvailabilityAdapter.output_schema, sort_keys=True, separators=(',', ':')))
"""


def matched(detail):
    return 'MATCHED', detail


def unavailable(reason):
    return 'UNAVAILABLE', reason


def compare(actual, expected):
    if actual == expected:
        return matched(actual)
    return 'MISMATCHED', f'actual={actual} expected={expected}'


def hex_value(value, size):
    return re.fullmatch('[0-9a-f]{%d}' % size, value) is not None


def git(repo, *args):
    try:
        return subprocess.run(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false',
                               '-C', str(repo), *args],
                              capture_output=True, stdin=subprocess.DEVNULL)
    except OSError:
        return None


def ok(proc):
    return proc is not None and proc.returncode == 0


def paths_result(paths):
    governed, other = [], []
    for name in sorted(set(paths)):
        parts = PurePosixPath(name).parts
        if '__pycache__' in parts or name.endswith('.pyc'):
            continue
        root_file = len(parts) == 1 and (fnmatch.fnmatchcase(name, 'requirements*.txt')
                    or name in {'.gitattributes', 'setup.cfg', 'setup.py', 'pyproject.toml'})
        target = governed if root_file or parts[0] in {'ripley', 'tests', 'scripts', 'fixtures'} else other
        target.append(name)
    detail = (f'governed={len(governed)} {json.dumps(governed)} '
              f'non-governed={len(other)} {json.dumps(other)}')
    return ('MISMATCHED' if governed else 'MATCHED'), detail


def git_checks(repo, baseline, expected_head):
    root = git(repo, 'rev-parse', '--show-prefix')
    if not ok(root) or root.stdout.strip():
        return [unavailable('repository root unavailable')] * 5
    proc = git(repo, 'rev-parse', '--verify', 'HEAD^{commit}')
    head = proc.stdout.decode('ascii').strip() if ok(proc) else ''
    if not hex_value(head, 40):
        return [unavailable('Git HEAD unavailable')] * 5
    first = matched(head)
    if expected_head is not None:
        first = (compare(head, expected_head) if hex_value(expected_head, 40)
                 else unavailable('expected HEAD must be 40 lowercase hex characters'))
    base = unavailable('baseline must be 40 lowercase hex characters')
    if hex_value(baseline, 40):
        kind = git(repo, 'cat-file', '-t', baseline)
        base = unavailable('baseline commit unavailable')
        if ok(kind) and kind.stdout.strip() == b'commit':
            ancestry = git(repo, 'merge-base', '--is-ancestor', baseline, head)
            if ok(ancestry):
                base = matched(baseline)
            elif ancestry is not None and ancestry.returncode == 1:
                base = 'MISMATCHED', 'baseline is not an ancestor: ' + baseline
    diff = unavailable('reviewed baseline unavailable or not matched')
    if base[0] == 'MATCHED':
        proc = git(repo, 'diff', '--name-only', '--no-renames', '-z', baseline, head, '--')
        diff = (paths_result(os.fsdecode(proc.stdout).split('\0')[:-1]) if ok(proc)
                else unavailable('Git diff unavailable'))
    status = git(repo, 'status', '--porcelain=v1', '--untracked-files=all', '-z')
    if not ok(status):
        return [first, base, diff] + [unavailable('Git status unavailable')] * 2
    tracked, untracked = [], []
    fields = iter(os.fsdecode(status.stdout).split('\0')[:-1])
    for entry in fields:
        flag = entry[:2]
        (untracked if flag == '??' else tracked).append(entry[3:])
        if 'R' in flag or 'C' in flag:
            tracked.append(next(fields))
    return [first, base, diff, paths_result(tracked), paths_result(untracked)]


def digest_check(expected, read):
    if not hex_value(expected, 64):
        return unavailable('expected SHA-256 must be 64 lowercase hex characters')
    try:
        data = read()
    except (OSError, ValueError, subprocess.SubprocessError):
        return unavailable('input unreadable or schema child failed')
    return compare(hashlib.sha256(data).hexdigest(), expected)


def schema_bytes(repo):
    output = subprocess.run([sys.executable, '-I', '-c', CHILD, str(repo)],
                            capture_output=True, check=True, stdin=subprocess.DEVNULL).stdout
    # Consume the print terminator and validate stdout before using it as evidence.
    value = json.loads(output)
    if not isinstance(value, dict):
        raise ValueError('schema object required')
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for name in ('baseline', 'packet', 'expected-packet-sha256', 'expected-prompt-sha256',
                 'expected-schema-sha256', 'expected-interpreter', 'expected-python'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--expected-head')
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    print(NOTICE)
    repo = args.repo.absolute()
    checks = git_checks(repo, args.baseline, args.expected_head)
    prompt = repo / 'ripley/prompts/nfl-availability/1.md'
    checks.extend([digest_check(args.expected_packet_sha256, Path(args.packet).read_bytes),
                   digest_check(args.expected_prompt_sha256, prompt.read_bytes),
                   digest_check(args.expected_schema_sha256, lambda: schema_bytes(repo))])
    def path_name(path):
        return os.path.normcase(os.path.abspath(path))
    checks.append(compare(path_name(sys.executable), path_name(args.expected_interpreter))
                  if args.expected_interpreter else unavailable('expected interpreter path empty'))
    version = f'{sys.version_info.major}.{sys.version_info.minor}'
    checks.append(compare(version, args.expected_python)
                  if re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', args.expected_python)
                  else unavailable('expected Python must be MAJOR.MINOR'))
    try:
        installed = importlib.metadata.version('anthropic')
    except (importlib.metadata.PackageNotFoundError, OSError, ValueError):
        installed = None
    checks.append(matched(installed) if installed else unavailable('distribution metadata unavailable'))
    pin = unavailable('distribution metadata unavailable')
    if installed:
        pin = unavailable('exact single-line repository pin unavailable')
        try:
            lines = (repo / 'requirements-providers.txt').read_text('utf-8').splitlines()
            if len(lines) == 1 and (m := re.fullmatch(r'anthropic==([a-zA-Z0-9][a-zA-Z0-9.!+_-]*)', lines[0])):
                pin = compare(installed, m[1])
        except (OSError, ValueError):
            pass
    checks.append(pin)
    names = ('Git HEAD', 'Reviewed baseline', 'Tracked differences from baseline',
             'Uncommitted changes', 'Untracked files', 'Packet SHA-256', 'Prompt-template SHA-256',
             'Canonical output-schema SHA-256', 'Interpreter path', 'Python version',
             'Installed Anthropic distribution version', 'SDK version against the repository pin')
    for i, (name, (status, detail)) in enumerate(zip(names, checks), 1):
        print(f'{i:02} {name} | {status} | {detail}')
    failed = sum(status != 'MATCHED' for status, _ in checks)
    print('OFFLINE PREFLIGHT: ' + (f'FAILED ({failed} of 12 not matched)' if failed else 'PASSED'))
    return int(bool(failed))


if __name__ == '__main__':
    sys.exit(main())
