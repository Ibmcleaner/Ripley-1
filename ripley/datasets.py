"""Immutable source evidence membership."""
import hashlib as _hashlib
import uuid as _uuid
from collections.abc import Mapping as _Mapping
from .capture import verify_capture as _verify_capture
from .core import MAX_CAPTURE_REFERENCES as _MAX_MEMBERS
from .core import canonical_json as _canonical_json

CONTRACT_VERSION = 1
NOTICE = "A source dataset records which captured evidence belongs to a collection. A verified Source Dataset is an integrity result, not a trust, quality, approval, interpretation, availability-time, consent, or fitness-for-use result."
_KEYS = {'contract_version', 'membership_sha256', 'members'}
_STATUSES = {'MATCHED': 'verified', 'MISMATCHED': 'artifact_mismatched',
             'UNAVAILABLE': 'artifact_unavailable'}

class DatasetError(Exception):
    def __init__(self, reason, capture_id=None):
        self.reason = reason
        self.capture_id = capture_id
        super().__init__(reason)

def _canonical(references):
    if not isinstance(references, (list, tuple)):
        raise DatasetError('invalid_call')
    if not references:
        raise DatasetError('empty_membership')
    if len(references) > _MAX_MEMBERS:
        raise DatasetError('too_many_members')
    seen, members = set(), []
    for reference in references:
        if not isinstance(reference, _Mapping) or set(reference) != {'capture_id', 'receipt_hash'}:
            raise DatasetError('malformed_member')
        capture_id, digest = reference['capture_id'], reference['receipt_hash']
        try:
            valid = isinstance(capture_id, str) and str(_uuid.UUID(capture_id)) == capture_id
        except ValueError:
            valid = False
        if (not valid or not isinstance(digest, str) or len(digest) != 64
                or any(ch not in '0123456789abcdef' for ch in digest)):
            raise DatasetError('malformed_member')
        if capture_id in seen:
            raise DatasetError('duplicate_member')
        seen.add(capture_id)
        members.append({'capture_id': capture_id, 'receipt_hash': digest})
    return sorted(members, key=lambda m: m['capture_id'])

def _membership_hash(members):
    return _hashlib.sha256(_canonical_json(
        {'contract_version': CONTRACT_VERSION, 'members': members})).hexdigest()

def _member_reason(ledger, store_dir, member):
    receipt = ledger.records.get(member['capture_id'])
    if receipt is None:
        return 'receipt_missing'
    if receipt.kind != 'capture':
        return 'receipt_wrong_kind'
    if receipt.content_hash != member['receipt_hash']:
        return 'receipt_hash_mismatch'
    try:
        return _STATUSES[_verify_capture(ledger, store_dir, receipt.id)[0]]
    except Exception:
        return 'verification_error'

def _same_membership(ledger, digest):
    return [r for r in ledger.records.values()
            if r.kind == 'source_dataset' and isinstance(r.data, _Mapping)
            and r.data.get('membership_sha256') == digest]

def create_source_dataset(ledger, store_dir, references):
    members = _canonical(references)
    for member in members:
        reason = _member_reason(ledger, store_dir, member)
        if reason != 'verified':
            raise DatasetError(reason, member['capture_id'])
    digest = _membership_hash(members)
    data = {'contract_version': CONTRACT_VERSION, 'membership_sha256': digest,
            'members': members}
    existing = _same_membership(ledger, digest)
    if len(existing) > 1:
        raise DatasetError('dataset_ambiguous')
    if existing:
        try:
            same = _canonical_json(existing[0].data) == _canonical_json(data)
        except Exception:
            same = False
        if not same:
            raise DatasetError('dataset_ambiguous')
        return existing[0]
    try:
        return ledger.add('source_dataset', data)
    except Exception:
        raise DatasetError('ledger_write_failed') from None

def verify_source_dataset(ledger, store_dir, dataset_id):
    result = {'notice': NOTICE, 'outcome': 'failed', 'reason': None,
              'dataset_id': dataset_id, 'membership_sha256': None, 'members': []}
    def _failed(reason):
        result['reason'] = reason
        return result
    try:
        record = ledger.records.get(dataset_id)
    except TypeError:
        record = None
    if record is None or record.kind != 'source_dataset':
        return _failed('dataset_unavailable')
    try:
        data = record.data
        if (not isinstance(data, _Mapping) or set(data) != _KEYS
                or type(data['contract_version']) is not int):
            return _failed('dataset_malformed')
        if data['contract_version'] != CONTRACT_VERSION:
            return _failed('contract_unsupported')
        canonical = _canonical(data['members'])
        stored = [dict(member) for member in data['members']]
        if type(data['membership_sha256']) is not str or canonical != stored:
            return _failed('dataset_malformed')
        if _membership_hash(stored) != data['membership_sha256']:
            return _failed('membership_hash_mismatch')
    except (DatasetError, KeyError, TypeError, AttributeError, ValueError):
        return _failed('dataset_malformed')
    result['membership_sha256'] = data['membership_sha256']
    if len(_same_membership(ledger, data['membership_sha256'])) != 1:
        return _failed('dataset_ambiguous')
    result['members'] = [dict(member, reason=_member_reason(ledger, store_dir, member))
                         for member in stored]
    if any(m['reason'] != 'verified' for m in result['members']):
        return _failed('member_failed')
    result['outcome'] = 'verified'
    return result
