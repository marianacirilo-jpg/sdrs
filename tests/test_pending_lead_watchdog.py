import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'pending_lead_watchdog.py'
spec = importlib.util.spec_from_file_location('pending_lead_watchdog', MODULE_PATH)
pending = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pending)


class PendingLeadWatchdogTest(unittest.TestCase):
    def test_reentry_meetings_link_is_not_form_signal_even_when_original_source_is_form(self):
        props = {
            'hs_object_source': 'FORM',
            'hs_object_source_label': 'FORM',
            'recent_conversion_event_name': 'Meetings Link: Lucas Batista',
        }
        self.assertFalse(pending.is_form_signal(props, is_reentry=True))

    def test_reentry_requires_recent_event_when_source_is_original_form(self):
        props = {
            'hs_object_source': 'FORM',
            'hs_object_source_label': 'FORM',
            'recent_conversion_event_name': '',
        }
        self.assertFalse(pending.is_form_signal(props, is_reentry=True))

    def test_real_form_event_still_alerts_for_new_lead_or_reentry(self):
        props = {
            'recent_conversion_event_name': 'Facebook Lead Ads: FORM VENCEDOR -> 25/06/2026',
        }
        self.assertTrue(pending.is_form_signal(props, is_reentry=False))
        self.assertTrue(pending.is_form_signal(props, is_reentry=True))

    def test_new_contact_from_form_source_without_event_still_alerts(self):
        props = {
            'hs_object_source': 'FORM',
            'hs_object_source_label': 'FORM',
            'recent_conversion_event_name': '',
        }
        self.assertTrue(pending.is_form_signal(props, is_reentry=False))


if __name__ == '__main__':
    unittest.main()
