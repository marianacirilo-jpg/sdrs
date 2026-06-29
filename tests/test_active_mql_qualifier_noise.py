# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import active_mql_qualifier as q


class ActiveMqlQualifierNoiseTests(unittest.TestCase):
    def test_upsert_pipeline_is_silent_for_unchanged_existing_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            original = q.PIPELINE
            q.PIPELINE = Path(td) / 'mql_pipeline_queue.json'
            try:
                contact = {
                    'id': '123',
                    'properties': {
                        'email': 'lead@example.com',
                        'company': 'Empresa',
                        'createdate': '2026-06-29T20:00:00.000Z',
                        'recent_conversion_date': '2026-06-29T20:01:00.000Z',
                    },
                }
                site = {'summary': 'site ok'}
                self.assertTrue(q.upsert_pipeline(contact, 'mql_candidate_needs_main_pipeline', 'motivo', site))
                self.assertFalse(q.upsert_pipeline(contact, 'mql_candidate_needs_main_pipeline', 'motivo', site))
            finally:
                q.PIPELINE = original

    def test_upsert_pipeline_reports_when_state_changes(self):
        with tempfile.TemporaryDirectory() as td:
            original = q.PIPELINE
            q.PIPELINE = Path(td) / 'mql_pipeline_queue.json'
            try:
                contact = {'id': '123', 'properties': {'email': 'lead@example.com', 'createdate': '2026-06-29T20:00:00.000Z'}}
                site = {'summary': 'site ok'}
                self.assertTrue(q.upsert_pipeline(contact, 'pending_review', 'a', site))
                self.assertTrue(q.upsert_pipeline(contact, 'mql_candidate_needs_main_pipeline', 'b', site))
            finally:
                q.PIPELINE = original


if __name__ == '__main__':
    unittest.main()
