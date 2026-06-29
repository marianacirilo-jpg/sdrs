import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WhatsAppSendStandardizationTests(unittest.TestCase):
    def assert_uses_safe_layer(self, rel):
        text = (ROOT / rel).read_text(encoding='utf-8')
        self.assertIn('whatsapp_safe_send', text, rel)

    def test_active_project_senders_use_safe_layer(self):
        for rel in [
            'disparo_dinamico.py',
            'disparo_primeiro_contato.py',
            'send_lead.py',
            'scripts/process_gate_once.py',
            'scripts/non_mql_legit_outreach.py',
            'scripts/monitor_diagnostico_agendado.py',
            'scripts/sumico_inicio_funil.py',
            'scripts/manual_greenix_diagnostico_cadence.py',
            'scripts/manual_greenix_finish_cadence.py',
            'scripts/channel_panel.py',
            'motor/ciclo.py',
        ]:
            with self.subTest(rel=rel):
                self.assert_uses_safe_layer(rel)

    def test_active_cron_python_senders_use_safe_layer(self):
        for path in [
            Path('/root/.hermes/scripts/zydon_whatsapp_warmup.py'),
            Path('/root/.hermes/scripts/zydon_incoming_response_alert.py'),
            Path('/root/.hermes/scripts/zydon_funnel_audit_alert.py'),
        ]:
            with self.subTest(path=str(path)):
                self.assertIn('whatsapp_safe_send', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
