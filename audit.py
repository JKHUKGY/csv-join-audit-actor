"""Bounded, read-only diagnostics for a proposed many-to-one CSV join."""
from collections import Counter
import csv
from io import StringIO

import pandas as pd

MAX_BYTES = 200_000
MAX_ROWS = 500
MAX_COLUMNS = 50
MAX_EXAMPLES = 10
MAX_KEY_BYTES = 512


class InputError(ValueError):
    """The tool arguments do not satisfy the documented input contract."""


def _read_csv(value, name, key):
    if not isinstance(value, str) or len(value.encode('utf-8')) > MAX_BYTES:
        raise InputError(f'{name} must be CSV text of at most {MAX_BYTES} UTF-8 bytes')
    try:
        rows = list(csv.reader(StringIO(value, newline=''), strict=True))
    except csv.Error as exc:
        raise InputError(f'{name} is malformed CSV') from exc
    if not rows:
        raise InputError(f'{name} needs a header')
    header, data = rows[0], rows[1:]
    if not header or len(header) > MAX_COLUMNS:
        raise InputError(f'{name} needs 1-{MAX_COLUMNS} columns')
    if any(not field.strip() for field in header) or len(set(header)) != len(header):
        raise InputError(f'{name} has blank or duplicate column names')
    if key not in header:
        raise InputError(f'{name} is missing the specified key column')
    if len(data) > MAX_ROWS:
        raise InputError(f'{name} exceeds {MAX_ROWS} data rows')
    if any(len(row) != len(header) for row in data):
        raise InputError(f'{name} has a data row with the wrong number of fields')
    key_index = header.index(key)
    if any(len(row[key_index].encode('utf-8')) > MAX_KEY_BYTES for row in data):
        raise InputError(f'{name} has a key exceeding {MAX_KEY_BYTES} UTF-8 bytes')
    return pd.DataFrame(data, columns=header, dtype='string')


def audit_join(payload):
    """Return one JSON-compatible report; never merge other columns or repair data."""
    required = {'observationsCsv', 'lookupCsv', 'key'}
    if not isinstance(payload, dict) or set(payload) != required:
        raise InputError('Provide exactly observationsCsv, lookupCsv, and key')
    key = payload['key']
    if not isinstance(key, str) or not key.strip() or len(key) > 100:
        raise InputError('key must be nonblank text of at most 100 characters')
    left = _read_csv(payload['observationsCsv'], 'observationsCsv', key)
    right = _read_csv(payload['lookupCsv'], 'lookupCsv', key)
    left_values, right_values = left[key].tolist(), right[key].tolist()
    blank_left = [i + 1 for i, value in enumerate(left_values) if not value.strip()]
    blank_right = [i + 1 for i, value in enumerate(right_values) if not value.strip()]
    counts = Counter(value for value in right_values if value.strip())
    duplicates = [value for value, count in counts.items() if count > 1]
    report = {
        'reportVersion': 1,
        'key': key,
        'observationRows': len(left),
        'lookupRows': len(right),
        'blankObservationKeyCount': len(blank_left),
        'blankLookupKeyCount': len(blank_right),
        'blankObservationDataRows': blank_left[:MAX_EXAMPLES],
        'blankLookupDataRows': blank_right[:MAX_EXAMPLES],
        'duplicateLookupKeyCount': len(duplicates),
        'duplicateLookupKeys': duplicates[:MAX_EXAMPLES],
        'exampleLimit': MAX_EXAMPLES,
        'canJoinManyToOne': False,
        'matchedObservationRows': None,
        'unmatchedObservationRows': None,
        'unmatchedExamples': [],
        'scope': 'Exact string key, nonblank keys, unique lookup keys, and match coverage only. Does not validate values, units, timestamps, sampling, or aggregate correctness.',
    }
    if blank_left or blank_right or duplicates:
        report.update(verdict='blocked', nextAction='Resolve blank or duplicate lookup keys at the source; do not deduplicate automatically.')
        return report

    # Project to keys: other columns cannot introduce suffix collisions or leak
    # into the report. pandas itself checks cardinality; we do not infer it.
    marker = '__join_audit_match' if key != '__join_audit_match' else '__join_audit_match_2'
    merged = left[[key]].merge(right[[key]], on=key, how='left',
                               validate='many_to_one', indicator=marker, sort=False)
    if len(merged) != len(left):
        raise RuntimeError('Many-to-one left join changed the observation count')
    unmatched = [i for i, status in enumerate(merged[marker]) if status == 'left_only']
    report.update(
        canJoinManyToOne=True,
        matchedObservationRows=len(left) - len(unmatched),
        unmatchedObservationRows=len(unmatched),
        unmatchedExamples=[{'dataRow': i + 1, 'keyValue': left_values[i]}
                           for i in unmatched[:MAX_EXAMPLES]],
    )
    if not left_values:
        report.update(verdict='needs_review', nextAction='No observations were supplied; do not infer a data-backed aggregate.')
    elif unmatched:
        report.update(verdict='needs_review', nextAction='Resolve unmatched keys or explicitly decide how they affect the analysis.')
    else:
        report.update(verdict='checks_passed', nextAction='These join checks passed. Validate the measurement semantics before computing an aggregate.')
    return report


def run_report(payload):
    """Keep argument failures distinguishable from a passing Actor execution."""
    try:
        return audit_join(payload)
    except InputError as exc:
        return {'reportVersion': 1, 'verdict': 'invalid_input',
                'canJoinManyToOne': False, 'reason': str(exc),
                'nextAction': 'Correct the tool arguments. No join was performed.'}
