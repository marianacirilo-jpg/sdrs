from pathlib import Path
import re
import unittest

ROOT = Path('/root/.hermes/zydon-prospeccao')
ACTIVE_SENDERS = [
    ROOT / 'disparo_dinamico.py',
    ROOT / 'scripts' / 'cadencia_primeiro_contato.py',
    ROOT / 'scripts' / 'process_gate_once.py',
    ROOT / 'scripts' / 'agenda_queue_sender.py',
    ROOT / 'scripts' / 'monitor_diagnostico_agendado.py',
    ROOT / 'scripts' / 'non_mql_legit_outreach.py',
]


class WhatsAppCentralizerContractTests(unittest.TestCase):
    def test_active_senders_use_central_ledger_or_orchestrator(self):
        for path in ACTIVE_SENDERS:
            src = path.read_text(encoding='utf-8')
            with self.subTest(path=str(path)):
                self.assertTrue(
                    ('enrich_legacy_row' in src) or ('record_dispatch' in src) or ('registrar_envio(' in src and 'disparo_dinamico' not in path.name),
                    f'{path} precisa carregar envelope central de natureza/origem/quota',
                )

    def test_active_senders_do_not_write_wpp_envios_directly(self):
        direct_write = re.compile(r"WPP(?:_FILE)?\.write_text|wpp_envios\.json'.*write_text|open\([^\n]*wpp_envios\.json[^\n]*['\"]w")
        for path in ACTIVE_SENDERS:
            src = path.read_text(encoding='utf-8')
            with self.subTest(path=str(path)):
                self.assertIsNone(direct_write.search(src), f'{path} não pode escrever wpp_envios direto; usar zydon_operational_queues')

    def test_centralizer_modules_exist(self):
        for rel in [
            'scripts/whatsapp_message_nature.py',
            'scripts/whatsapp_routing.py',
            'scripts/whatsapp_quota_manager.py',
            'scripts/whatsapp_send_orchestrator.py',
            'scripts/whatsapp_conversation_scope.py',
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)


if __name__ == '__main__':
    unittest.main()
