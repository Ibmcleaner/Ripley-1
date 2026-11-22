"""Attributable human judgments about immutable grounding evidence."""
import hashlib as _hashlib
import re as _re


CRITERIA_ID = 'semantic-review-criteria-v1'
CRITERIA_LINES = (
    'A. Decide whether the observation is a reasonable interpretation of the evidence shown in the review package.',
    'B. Preserve declared uncertainty. Do not treat an uncertain observation as certain.',
    'C. Do not infer information that the cited evidence does not support.',
    'D. If the evidence does not support a clear judgment, use needs_clarification.',
    'E. acceptable means semantically acceptable under these criteria only.',
    'F. acceptable does not mean approved for execution, source authenticated, source true, provider authorized, budget authorized, task approved or deployment approved.',
)
CRITERIA_TEXT = '\n'.join(CRITERIA_LINES)
CRITERIA_SHA256 = _hashlib.sha256(CRITERIA_TEXT.encode('utf-8')).hexdigest()
REVIEWER_KIND = 'human'
VERDICTS = ('acceptable', 'rejected', 'needs_clarification')
MAX_REASON_CHARS = 512
MAX_UNRESOLVED_ISSUES = 8
MAX_ISSUE_CHARS = 256


class SemanticReviewError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _string(value, maximum):
    if type(value) is not str or not 1 <= len(value) <= maximum:
        return False
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        return False
    return True


def _reviewer(value):
    return (_string(value, 128)
            and _re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]*', value) is not None)


def _decision(value):
    if type(value) is not dict:
        return False
    required = {'observation_id', 'verdict', 'reason'}
    if (not _string(value.get('observation_id'), 64)
            or type(value.get('verdict')) is not str or value['verdict'] not in VERDICTS
            or not _string(value.get('reason'), MAX_REASON_CHARS)):
        return False
    if value['verdict'] == 'needs_clarification':
        issues = value.get('unresolved_issues')
        return (set(value) == required | {'unresolved_issues'}
                and type(issues) is list and 1 <= len(issues) <= MAX_UNRESOLVED_ISSUES
                and all(_string(issue, MAX_ISSUE_CHARS) for issue in issues))
    return set(value) == required


def _add(ledger, kind, data):
    try:
        return ledger.add(kind, data)
    except Exception:
        raise SemanticReviewError('ledger_write_failed') from None


def record_semantic_review(ledger, validation_id, validation_hash, reviewer_identity, decisions):
    if (any(type(value) is not str for value in
            (validation_id, validation_hash, reviewer_identity)) or type(decisions) is not list):
        raise SemanticReviewError('invalid_call')

    def refuse(reason):
        return _add(ledger, 'semantic_review_refusal', {
            'validation_id': validation_id if 1 <= len(validation_id) <= 64 else None,
            'reviewer_identity': reviewer_identity if _reviewer(reviewer_identity) else None,
            'reason': reason})

    if not _reviewer(reviewer_identity):
        return refuse('reviewer_invalid')
    validation = ledger.records.get(validation_id)
    if validation is None or validation.kind != 'grounding_validation':
        return refuse('validation_unavailable')
    if validation.content_hash != validation_hash:
        return refuse('validation_hash_mismatch')
    data = validation.data
    if data['review_state'] != 'awaiting_semantic_review':
        return refuse('not_reviewable')
    proposal_record = ledger.records.get(data['proposal_id'])
    if (proposal_record is None or proposal_record.kind != 'proposal'
            or proposal_record.content_hash != data['proposal_hash']):
        return refuse('proposal_unavailable')
    if any(record.kind == 'semantic_review' and record.data['validation_id'] == validation.id
           for record in ledger.records.values()):
        return refuse('already_reviewed')
    proposal = proposal_record.data['proposal']
    producer_identity = proposal['producer']['identity']
    if reviewer_identity.casefold() == producer_identity.casefold():
        return refuse('reviewer_is_producer')
    eligible = {item['observation_id']: item['verdict'] for item in data['verdicts']
                if item['verdict'] != 'not_grounded'}
    if not eligible:
        return refuse('no_eligible_observations')
    if not all(_decision(decision) for decision in decisions):
        return refuse('decision_schema_invalid')
    identifiers = [decision['observation_id'] for decision in decisions]
    if len(set(identifiers)) != len(identifiers):
        return refuse('decision_duplicate')
    proposal_ids = {item['observation_id'] for item in proposal['observations']}
    if any(identity not in eligible or identity not in proposal_ids for identity in identifiers):
        return refuse('decision_not_eligible')
    if any(identity not in identifiers for identity in eligible):
        return refuse('decision_missing')
    supplied = {decision['observation_id']: decision for decision in decisions}
    ordered = []
    for observation in proposal['observations']:
        identity = observation['observation_id']
        if identity in eligible:
            decision = supplied[identity]
            ordered.append({'observation_id': identity, 'status': observation['status'],
                            'grounding_verdict': eligible[identity], 'verdict': decision['verdict'],
                            'reason': decision['reason'],
                            'unresolved_issues': decision.get('unresolved_issues', [])})
    return _add(ledger, 'semantic_review', {
        'validation_id': validation.id, 'validation_hash': validation.content_hash,
        'proposal_id': proposal_record.id, 'proposal_hash': proposal_record.content_hash,
        'snapshot_id': data['snapshot_id'], 'snapshot_hash': data['snapshot_hash'],
        'producer_identity': producer_identity, 'reviewer_kind': REVIEWER_KIND,
        'reviewer_identity': reviewer_identity, 'criteria_id': CRITERIA_ID,
        'criteria_sha256': CRITERIA_SHA256, 'decisions': ordered})
