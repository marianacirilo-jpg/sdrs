import importlib.util
import json
import re
import tempfile
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

    def test_future_cron_send_paths_are_centralized_or_read_only(self):
        """Crons ativos não podem postar na bridge por fora da camada segura.

        Wrappers shell podem chamar scripts do projeto; o envio real precisa passar
        por whatsapp_safe_send.safe_post_bridge/safe_send_text. Monitores e UIs que
        só leem status/history ficam explicitamente permitidos.
        """
        active_wrappers = [
            Path('/root/.hermes/scripts/zydon_whatsapp_warmup.py'),
            Path('/root/.hermes/scripts/zydon_non_mql_legit_backfill.sh'),
            Path('/root/.hermes/scripts/zydon_agenda_queue_sender.sh'),
            Path('/root/.hermes/scripts/zydon_sdr_followup_unificado_5min.sh'),
            Path('/root/.hermes/scripts/zydon_funnel_audit_alert.py'),
            Path('/root/.hermes/scripts/zydon_incoming_response_alert_1min.sh'),
        ]
        allowed_read_only_terms = ('watchdog', 'monitor', 'status', 'history', 'channel_panel', 'queue_status', 'claude')
        for path in active_wrappers:
            text = path.read_text(encoding='utf-8')
            blob = text
            # Inclui scripts Python referenciados pelo wrapper quando estiverem no repo.
            for rel in re.findall(r'(?:python3\s+)?(?:/root/\.hermes/zydon-prospeccao/)?([\w./-]+\.py)', text):
                p = (ROOT / rel) if not rel.startswith('/') else Path(rel)
                if p.exists():
                    blob += '\n' + p.read_text(encoding='utf-8')
            # A agenda usa process_gate_once por importlib; incluir a camada real.
            if 'process_gate_once.py' in blob or 'pg.post_bridge' in blob:
                pg = ROOT / 'scripts/process_gate_once.py'
                if pg.exists():
                    blob += '\n' + pg.read_text(encoding='utf-8')
            has_send_intent = any(tok in blob for tok in ('/send', '/send-file', 'safe_send_text', 'safe_post_bridge'))
            is_read_only = any(tok in path.name for tok in allowed_read_only_terms)
            with self.subTest(path=str(path)):
                if has_send_intent and not is_read_only:
                    self.assertIn('whatsapp_safe_send', blob)
                    self.assertRegex(blob, r'safe_(post_bridge|send_text|send_file)')

    def test_legacy_shell_direct_senders_are_blocked(self):
        for rel in [
            'dispatch_airtudo.sh',
            'dispatch_lumaville.sh',
            'dispatch_caffeine.sh',
            'dispatch_4_mql.sh',
            'naomql_notify.sh',
        ]:
            text = (ROOT / rel).read_text(encoding='utf-8')
            with self.subTest(rel=rel):
                self.assertIn('LEGACY_WHATSAPP_DIRECT_SEND_BLOCKED', text)
                self.assertRegex(text, r'(?m)^exit 2$')

    def test_manual_one_off_python_senders_do_not_post_directly_to_bridge(self):
        direct_patterns = [
            r"urllib\.request\.Request\(\s*f?['\"]http://127\.0\.0\.1:\{?port\}?\{?path\}?",
            r"urllib\.request\.Request\(\s*f?['\"]http://127\.0\.0\.1:\{?PORT\}?\{?path\}?",
            r"requests\.post\(\s*f?['\"]http://127\.0\.0\.1:.*?/send",
        ]
        for rel in [
            'scripts/manual_automec_diagnostico_send.py',
            'scripts/manual_dmz_diagnostico_send.py',
            'scripts/manual_dmz_agenda_after_respiro.py',
            'scripts/manual_automec_agenda_after_respiro.py',
        ]:
            path = ROOT / rel
            if not path.exists():
                continue
            text = path.read_text(encoding='utf-8')
            with self.subTest(rel=rel):
                self.assertIn('pg.post_bridge', text)
                for pat in direct_patterns:
                    self.assertIsNone(re.search(pat, text), pat)

    def test_disparo_dinamico_blocks_requested_and_canonicalized_jids_from_audit(self):
        spec = importlib.util.spec_from_file_location('disparo_dinamico_test', ROOT / 'disparo_dinamico.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        row = {
            'event': 'send',
            'uid': 'disparo_dinamico',
            'targetJid': '5562999498799@s.whatsapp.net',
            'chatOriginal': '5562999498799@s.whatsapp.net',
            'bridge': {
                'to': '556299498799@s.whatsapp.net',
                'requestedTo': '5562999498799@s.whatsapp.net',
                'canonicalization': {
                    'jid': '556299498799@s.whatsapp.net',
                    'requested': '5562999498799@s.whatsapp.net',
                },
            },
        }
        with tempfile.NamedTemporaryFile('w+', encoding='utf-8') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
            f.flush()
            old = mod.OUTBOUND_AUDIT
            try:
                mod.OUTBOUND_AUDIT = f.name
                blocked = mod.outbound_audit_phone_set()
            finally:
                mod.OUTBOUND_AUDIT = old
        self.assertIn('62999498799', blocked)  # requested/original
        self.assertIn('6299498799', blocked)   # canonicalized by bridge


if __name__ == '__main__':
    unittest.main()
