import importlib.util
from pathlib import Path
import unittest

ROOT = Path('/root/.hermes/zydon-prospeccao')
SPEC = importlib.util.spec_from_file_location('whatsapp_message_nature', ROOT / 'scripts' / 'whatsapp_message_nature.py')


class WhatsappMessageNatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(cls.mod)

    def test_core_natures_map_to_quota_classes_and_legacy_fields(self):
        m = self.mod
        cases = [
            ('first_contact', 'cold_outreach', 'cold_automation', 'primeiro_contato', 'primeiro_contato'),
            ('followup_f2', 'cold_outreach', 'cold_automation', 'followup_f2', 'primeiro_contato_cadencia'),
            ('followup_f1_postdiag', 'post_diagnostic', 'pipeline_followthrough', 'mql_followup1_deterministico', 'mql_followup1_deterministico'),
            ('diagnostic_initial', 'post_diagnostic', 'pipeline_followthrough', 'mql_diagnostico_em_andamento', 'diagnostic_initial'),
            ('agenda_confirmation', 'scheduled_meeting', 'pipeline_followthrough', 'enviado_lead', 'diagnostico_agenda_confirmacao'),
            ('manual_reply', 'active_conversation', 'active_conversation', 'manual_reply', 'manual_reply'),
            ('internal_group_alert', 'internal_only', 'internal', 'enviado_grupo', 'internal_group_alert'),
            ('warmup', 'cold_outreach', 'warmup', 'warmup', 'warmup'),
        ]
        for nature, thread_state, quota, legacy_status, legacy_msg_type in cases:
            with self.subTest(nature=nature, thread_state=thread_state):
                intent = m.describe_nature(nature, thread_state)
                self.assertEqual(intent['quota_class'], quota)
                self.assertEqual(intent['legacy_status'], legacy_status)
                self.assertEqual(intent['legacy_msg_type'], legacy_msg_type)

    def test_active_thread_overrides_cold_followup_quota(self):
        m = self.mod
        intent = m.describe_nature('followup_f3', 'active_conversation')
        self.assertEqual(intent['quota_class'], 'active_conversation')
        self.assertFalse(intent['quota_counted'])

    def test_bundle_parts_share_logical_message_id_and_count_once(self):
        m = self.mod
        bundle = m.build_logical_message(
            nature='diagnostic_bundle',
            thread_state='post_diagnostic',
            origin='cron_diagnostic_pipeline',
            conversation_id='553499999999@s.whatsapp.net',
            selected_port=4603,
            owner_sdr='lucas_batista',
            parts=[
                {'kind': 'text', 'part_nature': 'diagnostic_initial'},
                {'kind': 'file', 'part_nature': 'diagnostic_pdf'},
                {'kind': 'text', 'part_nature': 'diagnostic_question'},
            ],
        )
        self.assertEqual(bundle['quota_class'], 'pipeline_followthrough')
        self.assertTrue(bundle['quota_counted'])
        self.assertEqual(len(bundle['parts']), 3)
        self.assertEqual(len({p['logical_message_id'] for p in bundle['parts']}), 1)
        self.assertEqual(bundle['logical_message_id'], bundle['parts'][0]['logical_message_id'])

    def test_unknown_nature_fails_closed(self):
        with self.assertRaises(ValueError):
            self.mod.describe_nature('invented_nature', 'cold_outreach')


if __name__ == '__main__':
    unittest.main()
