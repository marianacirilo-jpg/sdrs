# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import active_mql_qualifier as q


class ActiveMqlQualifierNoiseTests(unittest.TestCase):
    def test_reentry_meetings_link_is_not_form_signal_even_when_original_source_is_form(self):
        props = {
            'hs_object_source': 'FORM',
            'hs_object_source_label': 'FORM',
            'createdate': '2026-06-29T20:00:00.000Z',
            'recent_conversion_date': '2026-06-29T21:00:00.000Z',
            'recent_conversion_event_name': 'Meetings Link: Lucas Batista',
        }
        self.assertTrue(q.is_reentry_contact(props))
        self.assertFalse(q.is_form_signal(props, is_reentry=True))

    def test_reentry_without_event_does_not_use_original_form_source(self):
        props = {
            'hs_object_source': 'FORM',
            'hs_object_source_label': 'FORM',
            'createdate': '2026-06-29T20:00:00.000Z',
            'recent_conversion_date': '2026-06-29T21:00:00.000Z',
            'recent_conversion_event_name': '',
        }
        self.assertTrue(q.is_reentry_contact(props))
        self.assertFalse(q.is_form_signal(props, is_reentry=True))

    def test_real_form_event_still_enters_fast_qualifier(self):
        props = {'recent_conversion_event_name': 'Facebook Lead Ads: FORM VENCEDOR'}
        self.assertTrue(q.is_form_signal(props, is_reentry=True))

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
