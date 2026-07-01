import importlib.util
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone

ROOT = Path('/root/.hermes/zydon-prospeccao')


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WhatsAppQuotaManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quota = load_module('whatsapp_quota_manager')
        cls.nature = load_module('whatsapp_message_nature')

    def test_diagnostic_bundle_counts_once_by_logical_message_id(self):
        rows = [
            {'logical_message_id': 'lm_diag_1', 'quota_class': 'pipeline_followthrough', 'quota_counted': True, 'bridge_port': 4601},
            {'logical_message_id': 'lm_diag_1', 'quota_class': 'pipeline_followthrough', 'quota_counted': True, 'bridge_port': 4601},
            {'logical_message_id': 'lm_diag_1', 'quota_class': 'pipeline_followthrough', 'quota_counted': True, 'bridge_port': 4601},
        ]
        self.assertEqual(self.quota.count_logical_sends(rows, quota_class='pipeline_followthrough'), 1)

    def test_manual_and_internal_do_not_consume_cold_quota(self):
        rows = [
            {'logical_message_id': 'lm_manual', 'quota_class': 'active_conversation', 'quota_counted': False, 'bridge_port': 4601},
            {'logical_message_id': 'lm_group', 'quota_class': 'internal', 'quota_counted': False, 'bridge_port': 4607},
            {'logical_message_id': 'lm_cold', 'quota_class': 'cold_automation', 'quota_counted': True, 'bridge_port': 4601},
        ]
        self.assertEqual(self.quota.count_logical_sends(rows, quota_class='cold_automation'), 1)

    def test_shadow_reserve_reports_block_without_side_effect(self):
        rows = [{'logical_message_id': f'lm_{i}', 'quota_class': 'cold_automation', 'quota_counted': True, 'bridge_port': 4601} for i in range(8)]
        decision = self.quota.check_quota({'quota_class': 'cold_automation', 'quota_counted': True, 'selected_port': 4601}, rows=rows, limits={'cold_automation': {'per_port_hour': 8}}, enforce=False)
        self.assertFalse(decision['allowed_if_enforced'])
        self.assertTrue(decision['shadow'])
        self.assertEqual(decision['reason'], 'quota_would_block')


class WhatsAppDispatchOrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orch = load_module('whatsapp_send_orchestrator')

    def test_build_intent_routes_existing_thread_and_adds_quota_fields(self):
        rows = [{'to': '5511999999999@s.whatsapp.net', 'bridge_port': 4605, 'date_tz': datetime.now(timezone.utc).isoformat()}]
        users = {'breno': {'role': 'sdr', 'ports': [4605, 4611]}}
        ports = {4605: {'owner': 'breno', 'role': 'sdr'}, 4611: {'owner': 'breno', 'role': 'sdr'}}
        intent = self.orch.prepare_intent(
            owner_uid='breno',
            to='5511999999999@s.whatsapp.net',
            nature='followup_f1',
            origin='cron_followup_unificado',
            text='teste',
            rows=rows,
            users=users,
            ports=ports,
        )
        self.assertEqual(intent['selected_port'], 4605)
        self.assertEqual(intent['routing']['mode'], 'existing_thread')
        self.assertEqual(intent['quota_class'], 'cold_automation')
        self.assertTrue(intent['quota_counted'])
        self.assertEqual(intent['status'], 'prepared')

    def test_record_dispatch_writes_legacy_and_central_fields_once(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'wpp_envios.json'
            intent = self.orch.prepare_intent(owner_uid='sarah', to='5511888888888@s.whatsapp.net', nature='first_contact', origin='cron_first_contact', text='oi', rows=[], users={'sarah': {'role': 'sdr', 'ports': [4601]}}, ports={4601: {'owner': 'sarah', 'role': 'sdr'}})
            data = self.orch.record_dispatch(intent, {'success': True, 'messageId': 'ABC'}, path=path)
            rows = data['envios']
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['bridge_port'], 4601)
            self.assertEqual(row['nature'], 'first_contact')
            self.assertEqual(row['status'], 'primeiro_contato')
            self.assertEqual(row['msg_type'], 'primeiro_contato')
            self.assertEqual(row['messageId'], 'ABC')

    def test_enrich_legacy_row_preserves_status_but_adds_central_fields(self):
        row = {'status': 'mql_agenda_sdr_apos_diagnostico', 'msg_type': 'custom_legacy', 'to': '5511888888888@c.us', 'bridge_port': 4601, 'text': 'agenda'}
        out = self.orch.enrich_legacy_row(row, nature='diagnostic_agenda_invite', origin='cron_agenda_queue', thread_state='scheduled_meeting', owner_uid='sarah')
        self.assertEqual(out['status'], 'mql_agenda_sdr_apos_diagnostico')
        self.assertEqual(out['msg_type'], 'custom_legacy')
        self.assertEqual(out['nature'], 'diagnostic_agenda_invite')
        self.assertEqual(out['quota_class'], 'pipeline_followthrough')
        self.assertTrue(out['logical_message_id'].startswith('lm_'))


if __name__ == '__main__':
    unittest.main()
