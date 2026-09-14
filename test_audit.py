import copy
import unittest

from audit import audit_join, run_report


def request(left='id,value\n001,10\n002,20\n', right='id,label\n001,a\n002,b\n', key='id'):
    return {'observationsCsv': left, 'lookupCsv': right, 'key': key}


class AuditTests(unittest.TestCase):
    def test_duplicate_lookup_blocks_even_identical_rows(self):
        for right in ['id,label\n001,a\n001,b\n', 'id,label\n001,a\n001,a\n']:
            result = audit_join(request(right=right))
            self.assertEqual(result['verdict'], 'blocked')
            self.assertFalse(result['canJoinManyToOne'])
            self.assertEqual(result['duplicateLookupKeys'], ['001'])
            self.assertIsNone(result['matchedObservationRows'])

    def test_exact_keys_keep_leading_zero_na_and_whitespace(self):
        result = audit_join(request('id\n001\nNA\n1\n 001\n001\n', 'id\n001\nNA\n'))
        self.assertEqual(result['verdict'], 'needs_review')
        self.assertEqual(result['matchedObservationRows'], 3)
        self.assertEqual(result['unmatchedObservationRows'], 2)
        self.assertEqual(result['unmatchedExamples'], [
            {'dataRow': 3, 'keyValue': '1'}, {'dataRow': 4, 'keyValue': ' 001'}])

    def test_blank_keys_report_logical_data_rows_on_both_sides(self):
        result = audit_join(request('id,v\n,1\n  ,2\n001,3\n', 'id,v\n001,a\n,b\n'))
        self.assertEqual(result['verdict'], 'blocked')
        self.assertEqual(result['blankObservationDataRows'], [1, 2])
        self.assertEqual(result['blankLookupDataRows'], [2])

    def test_success_does_not_claim_aggregate_correctness_or_echo_other_columns(self):
        payload = request('id,secret\n001,private-text\n001,private-text\n', 'id,label\n001,a\n')
        original = copy.deepcopy(payload)
        result = audit_join(payload)
        self.assertEqual(result['verdict'], 'checks_passed')
        self.assertEqual(result['matchedObservationRows'], 2)
        self.assertEqual(payload, original)
        self.assertNotIn('private-text', str(result))
        self.assertIn('Does not validate values', result['scope'])

    def test_empty_inputs_do_not_count_as_useful_data(self):
        no_left = audit_join(request(left='id,value\n'))
        self.assertEqual(no_left['verdict'], 'needs_review')
        self.assertEqual(no_left['observationRows'], 0)
        no_lookup = audit_join(request(right='id,label\n'))
        self.assertEqual(no_lookup['unmatchedObservationRows'], 2)

    def test_csv_quoting_and_embedded_newlines(self):
        result = audit_join(request('id,note\n"a,b","line one\nline two"\n', 'id\n"a,b"\n'))
        self.assertEqual(result['verdict'], 'checks_passed')
        self.assertEqual(result['observationRows'], 1)

    def test_malformed_csv_and_ambiguous_header_fail_as_arguments(self):
        bad_inputs = ['', 'id,id\n001,001\n', 'id,\n001,x\n', 'other\n001\n',
                      'id,v\n001\n', 'id,v\n001,x,extra\n', 'id\n"unterminated', 'id\n\n']
        for csv_text in bad_inputs:
            for side in ['observationsCsv', 'lookupCsv']:
                payload = request(); payload[side] = csv_text
                with self.subTest(csv_text=csv_text, side=side):
                    self.assertEqual(run_report(payload)['verdict'], 'invalid_input')

    def test_request_contract(self):
        bad_payloads = [None, [], {}, {**request(), 'deduplicate': True},
                        {**request(), 'key': 1}, {**request(), 'key': ' '},
                        {**request(), 'observationsCsv': [{'id': '001'}]}]
        for payload in bad_payloads:
            self.assertEqual(run_report(payload)['verdict'], 'invalid_input')

    def test_bounded_input_and_examples(self):
        too_many_rows = 'id\n' + '001\n' * 501
        too_many_columns = ','.join(['id'] + [str(i) for i in range(50)]) + '\n'
        for bad in [too_many_rows, too_many_columns, 'id\n' + 'x' * 200_001,
                    'id\n' + '\u4e2d' * 200]:
            self.assertEqual(run_report(request(left=bad))['verdict'], 'invalid_input')
        result = audit_join(request('id\n' + '\n'.join(str(i) for i in range(30)) + '\n', 'id\n'))
        self.assertEqual(result['unmatchedObservationRows'], 30)
        self.assertEqual(len(result['unmatchedExamples']), 10)

    def test_internal_column_names_are_valid_keys(self):
        for key in ['_merge', '__join_audit_match', '__join_audit_match_2']:
            result = audit_join(request(f'{key}\n001\n', f'{key}\n001\n', key))
            self.assertEqual(result['verdict'], 'checks_passed')


if __name__ == '__main__':
    unittest.main()
