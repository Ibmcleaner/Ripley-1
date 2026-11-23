"""Deterministic proposal grounding against Snapshot-bound captured bytes."""
import hashlib as _hashlib
import re as _re

from .capture import _local_path, _object_path
from .core import decode_protocol_object as _decode_protocol_object


PROPOSAL_VERSION = 1
MAX_PROPOSAL_BYTES = 65536
MAX_ARTIFACT_BYTES = 1048576
MAX_OBSERVATIONS = 64
MAX_CITATIONS = 8
MAX_CITATION_BYTES = 4096
PRODUCER_KINDS = ('fixture', 'human')
_WORKER_PRODUCER_KIND = 'worker'
NOTICE = ('Grounding shows only that each cited quote exists at the cited bytes of '
          'the captured source. It does not show that the interpretation is correct, '
          'that the source is authentic or truthful, or that anything is approved.')


class GroundingError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _read_object(path, limit):
    if not path.is_file():
        raise OSError('object is not a regular file')
    with path.open('rb') as stream:
        return stream.read(limit + 1)


def _add(ledger, kind, data):
    try:
        return ledger.add(kind, data)
    except Exception:
        raise GroundingError('ledger_write_failed') from None


def _string(value, minimum, maximum):
    if type(value) is not str or not minimum <= len(value) <= maximum:
        return False
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        return False
    return True


def _identifier(value, maximum, colon=False):
    pattern = r'[A-Za-z0-9][A-Za-z0-9._:-]*' if colon else r'[A-Za-z0-9][A-Za-z0-9._-]*'
    return _string(value, 1, maximum) and _re.fullmatch(pattern, value) is not None


def _schema(proposal, producer_kinds=PRODUCER_KINDS):
    if type(proposal) is not dict or set(proposal) != {
            'proposal_version', 'snapshot_id', 'producer', 'observations'}:
        return False
    if (type(proposal['proposal_version']) is not int
            or proposal['proposal_version'] != PROPOSAL_VERSION
            or not _string(proposal['snapshot_id'], 1, 64)):
        return False
    producer = proposal['producer']
    if (type(producer) is not dict or set(producer) != {'kind', 'identity'}
            or type(producer['kind']) is not str or producer['kind'] not in producer_kinds
            or not _identifier(producer['identity'], 128, colon=True)):
        return False
    observations = proposal['observations']
    if type(observations) is not list or not 1 <= len(observations) <= MAX_OBSERVATIONS:
        return False
    required = {'observation_id', 'field', 'status', 'value', 'citations'}
    for observation in observations:
        if (type(observation) is not dict
                or set(observation) not in (required, required | {'note'})
                or not _identifier(observation['observation_id'], 64)
                or not _string(observation['field'], 1, 128)
                or type(observation['status']) is not str
                or observation['status'] not in ('asserted', 'uncertain', 'not_found')
                or ('note' in observation and not _string(observation['note'], 1, 512))):
            return False
        citations = observation['citations']
        if type(citations) is not list or len(citations) > MAX_CITATIONS:
            return False
        if observation['status'] == 'not_found':
            if observation['value'] is not None or citations:
                return False
        elif not _string(observation['value'], 0, 1024):
            return False
        for citation in citations:
            if (type(citation) is not dict
                    or set(citation) != {'capture_id', 'start', 'end', 'quote'}
                    or not _string(citation['capture_id'], 1, 64)
                    or type(citation['start']) is not int or type(citation['end']) is not int
                    or not 0 <= citation['start'] < citation['end']
                    or citation['end'] - citation['start'] > MAX_CITATION_BYTES
                    or not _string(citation['quote'], 1, MAX_CITATION_BYTES)
                    or len(citation['quote'].encode('utf-8')) > MAX_CITATION_BYTES):
                return False
    return True


def _capture_evidence(ledger, store_dir, reference):
    capture_id = reference['capture_id']
    item = {'capture_id': capture_id, 'expected_receipt_hash': reference['receipt_hash'],
            'observed_receipt_hash': None, 'content_sha256': None,
            'size_bytes': None, 'reason': 'receipt_missing'}
    receipt = ledger.records.get(capture_id)
    if receipt is None:
        return item, None
    if receipt.kind != 'capture':
        item['reason'] = 'receipt_wrong_kind'
        return item, None
    item['observed_receipt_hash'] = receipt.content_hash
    if receipt.content_hash != reference['receipt_hash']:
        item['reason'] = 'receipt_hash_mismatch'
        return item, None
    digest, size = receipt.data['sha256'], receipt.data['size_bytes']
    item.update(content_sha256=digest, size_bytes=size)
    if size > MAX_ARTIFACT_BYTES:
        item['reason'] = 'artifact_too_large'
        return item, None
    try:
        if type(digest) is not str or _re.fullmatch('[0-9a-f]{64}', digest) is None:
            raise ValueError('invalid object identifier')
        path = _object_path(_local_path(store_dir).resolve(), digest)
        data = _read_object(path, MAX_ARTIFACT_BYTES)
    except Exception:
        item['reason'] = 'artifact_unavailable'
        return item, None
    if len(data) != size:
        item['reason'] = 'artifact_mismatched'
        return item, None
    if _hashlib.sha256(data).hexdigest() != digest:
        item['reason'] = 'artifact_mismatched'
        return item, None
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        item['reason'] = 'artifact_not_utf8'
        return item, None
    item['reason'] = 'verified'
    return item, data


def _citation_result(citation, sources):
    capture_id = citation['capture_id']
    if capture_id not in sources:
        return 'capture_not_on_snapshot'
    data = sources[capture_id]
    start, end = citation['start'], citation['end']
    if end > len(data):
        return 'out_of_bounds'
    if any(offset < len(data) and data[offset] & 0xc0 == 0x80 for offset in (start, end)):
        return 'splits_character'
    if data[start:end] != citation['quote'].encode('utf-8'):
        return 'quote_mismatch'
    return 'matched'


def _verdict(observation, sources):
    citations = [{name: citation[name] for name in ('capture_id', 'start', 'end')}
                 | {'result': _citation_result(citation, sources)}
                 for citation in observation['citations']]
    if observation['status'] == 'not_found':
        verdict, reason = 'no_evidence_claimed', 'declared_not_found'
    elif not citations:
        verdict, reason = 'not_grounded', 'citation_missing'
    elif all(citation['result'] == 'matched' for citation in citations):
        verdict, reason = 'grounded', 'all_citations_matched'
    else:
        verdict, reason = 'not_grounded', 'citation_failed'
    return {'observation_id': observation['observation_id'], 'verdict': verdict,
            'reason': reason, 'citations': citations}


def ground_proposal(ledger, store_dir, proposal_bytes):
    return _ground(ledger, store_dir, proposal_bytes, PRODUCER_KINDS)


def _ground(ledger, store_dir, proposal_bytes, producer_kinds):
    if type(proposal_bytes) is not bytes:
        raise GroundingError('invalid_call')
    identity = {'proposal_sha256': _hashlib.sha256(proposal_bytes).hexdigest(),
                'proposal_size_bytes': len(proposal_bytes)}

    def reject(reason):
        return _add(ledger, 'grounding_rejection', dict(identity, reason=reason))

    if len(proposal_bytes) > MAX_PROPOSAL_BYTES:
        return reject('proposal_too_large')
    try:
        proposal_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return reject('proposal_not_utf8')
    try:
        proposal = _decode_protocol_object(proposal_bytes)
    except (ValueError, RecursionError):
        return reject('proposal_not_json')
    if not _schema(proposal, producer_kinds):
        return reject('proposal_schema_invalid')
    identifiers = [observation['observation_id'] for observation in proposal['observations']]
    if len(set(identifiers)) != len(identifiers):
        return reject('duplicate_observation_id')
    snapshot = ledger.records.get(proposal['snapshot_id'])
    if snapshot is None or snapshot.kind != 'snapshot' or not snapshot.data.get('capture_references'):
        return reject('snapshot_unavailable')
    proposal_record = _add(ledger, 'proposal', dict(identity,
        snapshot_hash=snapshot.content_hash, proposal=proposal))
    evidence, sources = [], {}
    for reference in snapshot.data['capture_references']:
        item, data = _capture_evidence(ledger, store_dir, reference)
        evidence.append(item)
        if item['reason'] == 'verified':
            sources[reference['capture_id']] = data
    passed = all(item['reason'] == 'verified' for item in evidence)
    verdicts, multiple = [], []
    if passed:
        verdicts = [_verdict(observation, sources) for observation in proposal['observations']]
        fields = {}
        for observation in proposal['observations']:
            fields.setdefault(observation['field'], []).append(observation['observation_id'])
        multiple = [{'field': field, 'observation_ids': fields[field]}
                    for field in sorted(fields) if len(fields[field]) > 1]
    return _add(ledger, 'grounding_validation', {
        'proposal_id': proposal_record.id, 'proposal_hash': proposal_record.content_hash,
        'snapshot_id': snapshot.id, 'snapshot_hash': snapshot.content_hash,
        'outcome': 'evaluated' if passed else 'blocked_evidence', 'evidence': evidence,
        'verdicts': verdicts, 'multi_observation_fields': multiple,
        'review_state': 'awaiting_semantic_review' if passed else 'not_reviewable'})


def _plain(value):
    if hasattr(value, 'items'):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def review_package(ledger, validation_id):
    validation = ledger.records.get(validation_id)
    if validation is None or validation.kind != 'grounding_validation':
        raise GroundingError('validation_unavailable')
    data = validation.data
    proposal_record = ledger.records.get(data['proposal_id'])
    if (proposal_record is None or proposal_record.kind != 'proposal'
            or proposal_record.content_hash != data['proposal_hash']):
        raise GroundingError('proposal_unavailable')
    proposal = proposal_record.data['proposal']
    observations = []
    if data['outcome'] != 'blocked_evidence':
        for observation, verdict in zip(proposal['observations'], data['verdicts']):
            citations = [dict(_plain(citation), result=result['result'])
                         for citation, result in zip(observation['citations'], verdict['citations'])]
            observations.append({
                'observation_id': observation['observation_id'], 'field': observation['field'],
                'status': observation['status'], 'value': observation['value'],
                'note': observation.get('note'), 'verdict': verdict['verdict'],
                'reason': verdict['reason'], 'citations': citations,
                'eligible_for_semantic_review': verdict['verdict'] != 'not_grounded'})
    return {'notice': NOTICE, 'validation_id': validation.id,
            'validation_hash': validation.content_hash, 'proposal_id': proposal_record.id,
            'proposal_hash': proposal_record.content_hash, 'snapshot_id': data['snapshot_id'],
            'producer': _plain(proposal['producer']), 'outcome': data['outcome'],
            'review_state': data['review_state'], 'evidence': _plain(data['evidence']),
            'multi_observation_fields': _plain(data['multi_observation_fields']),
            'observations': observations}
