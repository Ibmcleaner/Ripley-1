"""Offline, exact-byte capture receipts for operator-controlled local directories."""
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


CAPTURE_VERSION = '1'
DEFAULT_MAX_BYTES = 10 * 1024 * 1024
_REPOSITORY = Path(__file__).resolve().parents[1]


class CaptureError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _declared_time(value):
    if value is None:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.utcoffset() is None:
            raise ValueError('missing offset')
        return stamp.astimezone(timezone.utc).isoformat()
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise CaptureError('invalid_metadata') from exc


def _local_path(value):
    text = os.fsdecode(value)
    if '://' in text or text.replace('\\', '/').startswith('//'):
        raise ValueError('local path required')
    return Path(text)


def _store_root(directory):
    try:
        root = _local_path(directory).resolve()
        ancestor = root
        while not ancestor.exists():
            ancestor = ancestor.parent
        if (root.is_relative_to(_REPOSITORY) or not ancestor.is_dir()
                or not os.access(ancestor, os.W_OK | os.X_OK)):
            raise CaptureError('store_invalid')
        return root
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise CaptureError('store_invalid') from exc


def _read_source(source_path, approved_root, limit):
    try:
        if isinstance(os.fspath(source_path), bytes):
            raise CaptureError('source_unapproved')
        source = Path(os.path.realpath(_local_path(source_path)))
        approved = _local_path(approved_root).resolve()
        mode = source.stat().st_mode
        if not stat.S_ISREG(mode) or not source.is_relative_to(approved):
            raise CaptureError('source_unapproved')
        stream = source.open('rb')
    except (TypeError, ValueError, RuntimeError) as exc:
        raise CaptureError('source_unapproved') from exc
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise CaptureError('source_missing') from exc
    except OSError as exc:
        raise CaptureError('source_unreadable') from exc
    try:
        with stream:
            size = os.fstat(stream.fileno()).st_size
            data = stream.read(limit + 1)
    except OSError as exc:
        raise CaptureError('read_interrupted') from exc
    if len(data) > limit:
        raise CaptureError('too_large')
    if len(data) != size:
        raise CaptureError('read_interrupted')
    return data


def _object_path(root, digest):
    path = root / 'sha256' / digest[:2] / digest
    # Intermediate links must never redirect a write or verification read.
    if path.resolve() != path or path.is_relative_to(_REPOSITORY):
        raise ValueError('invalid object path')
    return path


def _identity(path):
    if not stat.S_ISREG(path.stat().st_mode):
        raise OSError('object is not a regular file')
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            size += len(block)
            digest.update(block)
    return digest.hexdigest(), size


def _sync_directory(directory):
    # Windows has no portable directory fsync in the standard library.
    if os.name == 'posix':
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _ensure_directory(directory):
    if directory.is_dir():
        return
    _ensure_directory(directory.parent)
    directory.mkdir(exist_ok=True)
    _sync_directory(directory.parent)


def _reuse(path, digest, size):
    if not path.exists():
        return False
    if _identity(path) != (digest, size):
        raise CaptureError('store_corrupt')
    return True


def _persist(root, digest, data):
    try:
        path = _object_path(root, digest)
        _ensure_directory(root)
    except (OSError, ValueError, RuntimeError) as exc:
        raise CaptureError('store_invalid') from exc
    try:
        _ensure_directory(path.parent)
        if _reuse(path, digest, len(data)):
            _sync_directory(path.parent)
            return
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if _identity(temporary) != (digest, len(data)):
                raise OSError('temporary object verification failed')
            os.replace(temporary, path)
            _sync_directory(path.parent)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except OSError as exc:
        raise CaptureError('artifact_write_failed') from exc


def capture_file(ledger, store_dir, source_path, *, approved_root, source_id, source_location,
                 supplied_by, content_type, declared_retrieved_at=None, declared_effective_at=None,
                 clock=None, max_bytes=DEFAULT_MAX_BYTES):
    if (not isinstance(source_id, str) or not re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}', source_id)
            or any(not isinstance(v, str) or not v.strip() or len(v) > 512
                   for v in (source_location, supplied_by, content_type))
            or type(max_bytes) is not int or not 0 <= max_bytes < sys.maxsize):
        raise CaptureError('invalid_metadata')
    retrieved = _declared_time(declared_retrieved_at)
    effective = _declared_time(declared_effective_at)
    root = _store_root(store_dir)
    data = _read_source(source_path, approved_root, max_bytes)
    digest = hashlib.sha256(data).hexdigest()
    stamp = datetime.now(timezone.utc) if clock is None else clock()
    if not isinstance(stamp, datetime) or stamp.utcoffset() != timedelta(0):
        raise CaptureError('invalid_metadata')
    _persist(root, digest, data)
    receipt = {
        'capture_version': CAPTURE_VERSION, 'source_id': source_id,
        'source_location': source_location, 'source_filename': Path(source_path).name,
        'intake_method': 'local-file', 'supplied_by': supplied_by, 'content_type': content_type,
        'sha256': digest, 'size_bytes': len(data), 'captured_at': stamp.isoformat(),
        'declared_retrieved_at': retrieved, 'declared_effective_at': effective,
    }
    try:
        return ledger.add('capture', receipt)
    except Exception as exc:
        raise CaptureError('ledger_write_failed') from exc


def verify_capture(ledger, store_dir, capture_id):
    record = ledger.records.get(capture_id)
    if record is None or record.kind != 'capture':
        return 'UNAVAILABLE', 'capture receipt unavailable'
    digest = record.data.get('sha256')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        return 'UNAVAILABLE', 'invalid object identifier'
    try:
        path = _object_path(_local_path(store_dir).resolve(), digest)
        identity = _identity(path)
    except (OSError, TypeError, ValueError, RuntimeError):
        return 'UNAVAILABLE', 'stored object unavailable'
    if identity != (digest, record.data.get('size_bytes')):
        return 'MISMATCHED', 'stored digest or size differs'
    return 'MATCHED', 'stored digest and size match'
