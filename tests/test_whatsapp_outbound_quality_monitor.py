#!/usr/bin/env python3
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

MONITOR_PATH = Path('/root/.hermes/zydon-prospeccao/scripts/whatsapp_outbound_quality_monitor.py')


def load_monitor():
    spec = importlib.util.spec_from_file_location('whatsapp_outbound_quality_monitor', MONITOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class WhatsAppOutboundQualityMonitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_monitor()

    def base_record(self):
        return {
            'type': 'api-send',
            'port': 4607,
            'id': 'MSG1',
            'chat': '553388274655@s.whatsapp.net',
            'requestedChat': '5533988274655@s.whatsapp.net',
            'text': 'Qualquer dúvida, estou à disposição.',
            'iso': '2026-06-29T23:18:29+00:00',
            'canonicalization': {
                'requested': '5533988274655@s.whatsapp.net',
                'jid': '553388274655@s.whatsapp.net',
                'changed': True,
                'onWhatsApp': [{'jid': '553388274655@s.whatsapp.net', 'exists': True}],
            },
            'preflight': {
                'jid': '553388274655@s.whatsapp.net',
                'skipped': False,
                'devices': ['553388274655@s.whatsapp.net', '553388274655:52@s.whatsapp.net'],
                'privacyToken': True,
            },
            'ownSync': {'ok': True},
        }

    def test_good_canonicalized_send_is_silent(self):
        rec = self.base_record()
        finding = self.mod.analyze_record(rec, datetime(2026, 6, 29, 23, 20, tzinfo=timezone.utc), 180)
        self.assertIsNone(finding)

    def test_devices_empty_and_bad_token_are_high_risk(self):
        rec = self.base_record()
        rec['id'] = 'MSG2'
        rec['preflight'] = {
            'jid': '5533988274655@s.whatsapp.net',
            'skipped': False,
            'devices': [],
            'privacyToken': 'bad-request',
        }
        finding = self.mod.analyze_record(rec, datetime(2026, 6, 29, 23, 20, tzinfo=timezone.utc), 180)
        self.assertIsNotNone(finding)
        self.assertEqual(finding.severity, 'ALTA')
        self.assertIn('preflight_devices_vazio', finding.reasons)
        self.assertTrue(any(r.startswith('privacy_token_ruim') for r in finding.reasons))

    def test_recent_1to1_without_canonicalization_is_flagged(self):
        rec = self.base_record()
        rec['id'] = 'MSG3'
        rec['canonicalization'] = None
        finding = self.mod.analyze_record(rec, datetime(2026, 6, 29, 23, 20, tzinfo=timezone.utc), 180)
        self.assertIsNotNone(finding)
        self.assertIn('sem_canonicalizacao', finding.reasons)

    def test_groups_are_ignored(self):
        rec = self.base_record()
        rec['chat'] = '120363408131718880@g.us'
        rec['canonicalization'] = None
        finding = self.mod.analyze_record(rec, datetime(2026, 6, 29, 23, 20, tzinfo=timezone.utc), 180)
        self.assertIsNone(finding)

    def test_since_cutoff_ignores_legacy_risk_even_inside_window(self):
        rec = self.base_record()
        rec['id'] = 'MSG_LEGACY'
        rec['iso'] = '2026-06-29T23:18:29+00:00'
        rec['canonicalization'] = None
        finding = self.mod.analyze_record(
            rec,
            datetime(2026, 6, 29, 23, 40, tzinfo=timezone.utc),
            180,
            self.mod.parse_iso('2026-06-29T23:30:00Z'),
        )
        self.assertIsNone(finding)

    def test_state_dedupes_alerts(self):
        rec = self.base_record()
        rec['id'] = 'MSG4'
        rec['preflight'] = {'skipped': False, 'devices': [], 'privacyToken': True}
        with tempfile.TemporaryDirectory() as td:
            hist = Path(td) / 'history_4607.json'
            state = Path(td) / 'state.json'
            hist.write_text(json.dumps([rec]), encoding='utf-8')
            findings = self.mod.scan_histories([hist], datetime(2026, 6, 29, 23, 20, tzinfo=timezone.utc), 180)
            self.assertEqual(len(findings), 1)
            self.mod.save_state(state, {findings[0].key})
            already = self.mod.load_state(state)
            self.assertIn(findings[0].key, already)


if __name__ == '__main__':
    unittest.main()
