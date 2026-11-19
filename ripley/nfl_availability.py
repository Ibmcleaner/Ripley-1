"""Frozen NFL availability inputs and independent, deterministic row checks."""
from collections.abc import Mapping
from datetime import date, datetime, timezone
import re

from .core import MAX_ROW_TEXT_CHARS, content_hash


def _utc(value):
    if not isinstance(value, str):
        raise ValueError('UTC timestamp required')
    result = datetime.fromisoformat(value)
    if result.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError('UTC timestamp required')
    return result


def _words(row, patterns):
    return {value for value, pattern in patterns.items()
            if re.search(pattern, row['text'], re.IGNORECASE)}


DESIGNATIONS = {'out': r'\b(?:out|O)\b', 'doubtful': r'\b(?:doubtful|D)\b',
                'questionable': r'\b(?:questionable|Q)\b'}
PRACTICE = {'full': r'\bfull\b', 'limited': r'\blimited\b',
            'dnp': r'\b(?:dnp|did not practice)\b'}


def _object_schema(**properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties),
            'additionalProperties': False}


def _array_schema(items):
    return {'type': 'array', 'items': items}


class NflAvailabilityAdapter:
    domain_id = 'nfl-availability'
    version = '1'
    task_type = 'extract'
    replay_policy = 'no'
    timeout_seconds = 45
    expected_output = {'players': list}
    output_schema = _object_schema(players=_array_schema(_object_schema(
        player_id={'type': 'string'},
        designation=_object_schema(
            value={'type': 'string', 'enum': ['out', 'doubtful', 'questionable', 'unlisted', 'unknown']},
            support=_array_schema({'type': 'string'})),
        practice=_array_schema(_object_schema(
            date={'type': 'string'}, status={'type': 'string', 'enum': ['full', 'limited', 'dnp']},
            support=_array_schema({'type': 'string'}))),
        supersession=_array_schema(_object_schema(
            field={'type': 'string'}, governing={'type': 'string'},
            superseded=_array_schema({'type': 'string'}))),
        conflict=_object_schema(flag={'type': 'boolean'}, support=_array_schema({'type': 'string'}),
                                note={'type': 'string'}),
        as_of={'anyOf': [{'type': 'string'}, {'type': 'null'}]},
    )))

    def snapshot_metadata(self, inputs):
        if (not isinstance(inputs, Mapping) or
                set(inputs) != {'game_id', 'team', 'cutoff_at', 'source_published_at',
                                'observed_at', 'evidence_at_basis', 'expected_players', 'rows'}):
            raise ValueError('invalid availability input fields')
        _utc(inputs['observed_at'])
        if inputs['source_published_at'] is not None:
            _utc(inputs['source_published_at'])
        basis = inputs['evidence_at_basis']
        if basis not in ('source_published_at', 'observed_at') or inputs[basis] is None:
            raise ValueError('evidence_at_basis must select a recorded timestamp')
        evidence_at = _utc(inputs[basis])
        if _utc(inputs['cutoff_at']) != evidence_at:
            raise ValueError('cutoff_at must equal the selected evidence timestamp')
        if not all(isinstance(inputs[key], str) and inputs[key] for key in ('game_id', 'team')):
            raise ValueError('game and team required')
        if not all(isinstance(inputs[key], (list, tuple)) for key in ('expected_players', 'rows')):
            raise ValueError('players and rows must be lists')
        players = {}
        for player in inputs['expected_players']:
            if (not isinstance(player, Mapping) or
                    set(player) != {'player_id', 'name', 'team', 'position'} or
                    not all(isinstance(v, str) and v for v in player.values()) or
                    player['player_id'] in players or player['team'] != inputs['team']):
                raise ValueError('invalid expected player')
            players[player['player_id']] = player
        row_ids = set()
        seen_players = set()
        text_size = 0
        for row in inputs['rows']:
            if (not isinstance(row, Mapping) or set(row) != {
                    'row_id', 'player_id', 'name', 'team', 'position', 'evidence_at',
                    'source', 'report_date', 'text'} or
                    not all(isinstance(v, str) for v in row.values()) or
                    not row['row_id'] or row['row_id'] in row_ids or
                    row['source'] != 'nfl.com-injury-report'):
                raise ValueError('invalid injury-report row')
            player = players.get(row['player_id'])
            if player is None or any(row[key] != player[key] for key in player):
                raise ValueError('row player does not match frozen subject')
            if _utc(row['evidence_at']) != evidence_at:
                raise ValueError('row evidence_at must equal the selected packet timestamp')
            date.fromisoformat(row['report_date'])
            row_ids.add(row['row_id'])
            seen_players.add(row['player_id'])
            text_size += len(row['text'])
        if set(players) != seen_players:
            raise ValueError('expected players must equal distinct row players')
        if text_size > MAX_ROW_TEXT_CHARS:
            raise ValueError('row text exceeds 24000 characters')
        return {'observed_at': inputs['observed_at'], 'sources': ['nfl.com-injury-report'],
                'data_quality': 'frozen-fixture'}


def _latest(rows, patterns):
    stated = [(row, _words(row, patterns)) for row in rows]
    stated = [(row, values) for row, values in stated if values]
    if not stated:
        return set(), [], []
    timestamp = max(_utc(row['evidence_at']) for row, _ in stated)
    governing = [(row, values) for row, values in stated if _utc(row['evidence_at']) == timestamp]
    values = set().union(*(values for _, values in governing))
    return values, [row for row, _ in governing], stated


class AvailabilityValidator:
    identity = 'availability-validator'
    version = '1'
    ruleset = 'nfl-availability-v1'
    requires_snapshot = True

    def validate(self, result, adapter, snapshot):
        failures = []

        def fail(rule, player_id, field):
            finding = {'rule': rule, 'player_id': player_id, 'field': field}
            if finding not in failures:
                failures.append(finding)

        inputs = snapshot.data['inputs']
        rows = {row['row_id']: row for row in inputs['rows']}
        cutoff = _utc(inputs['cutoff_at'])
        output = result.data['output']
        entries = output.get('players') if isinstance(output, Mapping) else None
        if not isinstance(entries, (list, tuple)) or set(output) != {'players'}:
            fail(1, None, 'players')
            entries = []
        expected = {p['player_id'] for p in inputs['expected_players']}
        ids = [p.get('player_id') for p in entries if isinstance(p, Mapping)]
        if (len(ids) != len(entries) or not all(isinstance(i, str) for i in ids) or
                len(ids) != len(set(ids)) or set(ids) != expected):
            fail(1, None, 'players')
        for entry in entries:
            if not isinstance(entry, Mapping) or not isinstance(entry.get('player_id'), str):
                fail(1, None, 'player_id')
                continue
            player_id = entry['player_id']
            if set(entry) != {'player_id', 'designation', 'practice', 'supersession', 'conflict', 'as_of'}:
                fail(1, player_id, 'shape')
                continue
            try:
                self._player(entry, player_id, rows, cutoff, fail)
            except (KeyError, TypeError, ValueError, AttributeError):
                fail(1, player_id, 'shape')
        failures.sort(key=lambda finding: finding['rule'])
        return {'result_id': result.id, 'validator': self.identity,
                'validator_version': self.version, 'ruleset': self.ruleset,
                'result_hash': result.content_hash,
                'contract_hash': content_hash({k: t.__name__ for k, t in adapter.expected_output.items()}),
                'passed': not failures, 'failures': failures}

    def _player(self, entry, player_id, rows, cutoff, fail):
        cited = set()

        def citations(ids, field):
            if not isinstance(ids, (list, tuple)) or not all(isinstance(i, str) for i in ids):
                fail(2, player_id, field)
                return []
            found = []
            for row_id in ids:
                if row_id not in rows:
                    fail(2, player_id, field)
                    continue
                row = rows[row_id]
                cited.add(row_id)
                if row['player_id'] != player_id:
                    fail(3, player_id, field)
                if _utc(row['evidence_at']) > cutoff:
                    fail(7, player_id, field)
                found.append(row)
            return found

        eligible = [r for r in rows.values() if r['player_id'] == player_id
                    and _utc(r['evidence_at']) <= cutoff]
        designation = entry['designation']
        if set(designation) != {'value', 'support'}:
            raise ValueError('invalid designation fields')
        support = citations(designation['support'], 'designation')
        values, governing, stated = _latest(eligible, DESIGNATIONS)
        conflicts = set()
        conflict_fields = []
        required_supersessions = {}
        if len(values) > 1:
            if designation['value'] != 'unknown':
                fail(4, player_id, 'designation')
            conflicts.update(r['row_id'] for r in governing)
            conflict_fields.append('designation')
        elif values:
            value = next(iter(values))
            governing_ids = {r['row_id'] for r in governing}
            if (designation['value'] != value or
                    not governing_ids.intersection(r['row_id'] for r in support) or
                    any(value not in _words(r, DESIGNATIONS) for r in support)):
                fail(4, player_id, 'designation')
            earlier = {r['row_id'] for r, old_values in stated
                       if r['row_id'] not in governing_ids and old_values != {value}}
            if earlier:
                required_supersessions['designation'] = (governing_ids, earlier)
        elif eligible:
            if designation['value'] != 'unlisted' or not support or any(_words(r, DESIGNATIONS) for r in support):
                fail(4, player_id, 'designation')
        elif designation['value'] != 'unknown' or support:
            fail(4, player_id, 'designation')
        if (designation['value'] == 'unknown' and len(values) == 1) or (
                designation['value'] == 'unlisted' and (values or not eligible)):
            fail(8, player_id, 'designation')

        practices = entry['practice']
        if not isinstance(practices, (tuple, list)):
            raise ValueError('practice list required')
        practice_dates = [p['date'] for p in practices]
        if len(practice_dates) != len(set(practice_dates)):
            fail(5, player_id, 'practice')
        all_dates = set(practice_dates) | {r['report_date'] for r in eligible if _words(r, PRACTICE)}
        for day in sorted(all_dates):
            candidates = [r for r in eligible if r['report_date'] == day or day in r['text']]
            statuses, latest, practice_stated = _latest(candidates, PRACTICE)
            entry_for_day = next((p for p in practices if p['date'] == day), None)
            field = 'practice:' + day
            if len(statuses) > 1:
                conflicts.update(r['row_id'] for r in latest)
                conflict_fields.append(day)
                if entry_for_day is not None:
                    fail(5, player_id, field)
            if entry_for_day is None:
                continue
            if set(entry_for_day) != {'date', 'status', 'support'}:
                raise ValueError('invalid practice fields')
            proof = citations(entry_for_day['support'], field)
            if (not proof or date.fromisoformat(day) > cutoff.date() or
                    entry_for_day['status'] not in PRACTICE or
                    any(entry_for_day['status'] not in _words(r, PRACTICE) or
                        date.fromisoformat(r['report_date']) < date.fromisoformat(day) for r in proof) or
                    statuses != {entry_for_day['status']}):
                fail(5, player_id, field)
            if len(statuses) == 1:
                value = next(iter(statuses))
                latest_ids = {r['row_id'] for r in latest}
                earlier = {r['row_id'] for r, old in practice_stated
                           if r['row_id'] not in latest_ids and old != {value}}
                if earlier:
                    required_supersessions[field] = (latest_ids, earlier)

        supersessions = entry['supersession']
        if not isinstance(supersessions, (list, tuple)):
            raise ValueError('supersession list required')
        supplied = {}
        for supersession in supersessions:
            if set(supersession) != {'field', 'governing', 'superseded'}:
                raise ValueError('invalid supersession fields')
            field = supersession['field']
            citations([supersession['governing']], field)
            citations(supersession['superseded'], field)
            supplied.setdefault(field, []).append(supersession)
        for field in set(supplied) | set(required_supersessions):
            specs = supplied.get(field, [])
            requirement = required_supersessions.get(field)
            if requirement is None or len(specs) != 1:
                fail(6, player_id, field)
            elif (specs[0]['governing'] not in requirement[0] or
                    set(specs[0]['superseded']) != requirement[1]):
                fail(6, player_id, field)

        conflict = entry['conflict']
        if set(conflict) != {'flag', 'support', 'note'}:
            raise ValueError('invalid conflict fields')
        citations(conflict['support'], 'conflict')
        if (type(conflict['flag']) is not bool or conflict['flag'] != bool(conflicts) or
                set(conflict['support']) != conflicts or not isinstance(conflict['note'], str) or
                any(field not in conflict['note'] for field in conflict_fields)):
            fail(9, player_id, 'conflict')
        expected_as_of = max((_utc(rows[i]['evidence_at']) for i in cited), default=None)
        if expected_as_of is None:
            if entry['as_of'] is not None:
                fail(7, player_id, 'as_of')
        elif entry['as_of'] is None or _utc(entry['as_of']) != expected_as_of or expected_as_of > cutoff:
            fail(7, player_id, 'as_of')
