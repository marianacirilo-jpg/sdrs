import importlib.util
import json
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'whatsapp_safe_send.py'


def load_mod():
    spec = importlib.util.spec_from_file_location('whatsapp_safe_send', MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WhatsAppSafeSendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_resolve_target_blocks_lid_without_phone_alt(self):
        target, err = self.mod.resolve_target_jid(4601, '123456789012345@lid')
        self.assertEqual(target, '')
        self.assertIn('LID', err)

    def test_resolve_target_uses_history_phone_alt_for_lid(self):
        old_data_dir = self.mod.DATA_DIR
        tmp = Path('/tmp/whatsapp_safe_send_lid_alt')
        tmp.mkdir(parents=True, exist_ok=True)
        lid = '123456789012345@lid'
        pn = '5511999998888@s.whatsapp.net'
        (tmp / 'history_4601.json').write_text(json.dumps([
            {'chat': lid, 'fromMe': False, 'text': 'oi', 'rawKey': {'remoteJid': lid, 'remoteJidAlt': pn}},
        ]), encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            target, err = self.mod.resolve_target_jid(4601, lid)
            self.assertEqual(err, '')
            self.assertEqual(target, pn)
        finally:
            self.mod.DATA_DIR = old_data_dir

    def test_audit_and_reconcile_by_message_id(self):
        old_data_dir = self.mod.DATA_DIR
        old_audit = self.mod.OUTBOUND_AUDIT_FILE
        tmp = Path('/tmp/whatsapp_safe_send_audit')
        tmp.mkdir(parents=True, exist_ok=True)
        audit = tmp / 'audit.jsonl'
        pn = '5511999998888@s.whatsapp.net'
        (tmp / 'history_4601.json').write_text(json.dumps([
            {'chat': pn, 'fromMe': True, 'id': '3EB123', 'text': 'Olá', 'timestamp': 1234},
        ]), encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod.OUTBOUND_AUDIT_FILE = audit
            rec = self.mod.record_outbound_audit('unit', 4601, pn, pn, 'text', {'to': pn, 'text': 'Olá'}, {'messageId': '3EB123_text'})
            self.assertEqual(rec['messageIds'], ['3EB123'])
            result = self.mod.reconcile_outbound_record(rec)
            self.assertEqual(result['status'], 'found')
            self.assertEqual(result['matchedBy'], 'messageId')
            rows = [json.loads(x) for x in audit.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(rows[0]['event'], 'send')
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod.OUTBOUND_AUDIT_FILE = old_audit

    def test_safe_post_bridge_normalizes_before_calling_transport(self):
        calls = []
        def fake_post(url, payload, timeout=30):
            calls.append((url, payload, timeout))
            return {'success': True, 'messageId': 'abc_text'}
        old_post = self.mod._post_json
        old_audit = self.mod.OUTBOUND_AUDIT_FILE
        tmp = Path('/tmp/whatsapp_safe_send_post')
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            self.mod._post_json = fake_post
            self.mod.OUTBOUND_AUDIT_FILE = tmp / 'audit.jsonl'
            if self.mod.OUTBOUND_AUDIT_FILE.exists():
                self.mod.OUTBOUND_AUDIT_FILE.unlink()
            ok, resp = self.mod.safe_send_text(4601, '11999998888', 'Olá', uid='unit', reconcile=False)
            self.assertTrue(ok)
            self.assertEqual(calls[0][1]['to'], '5511999998888@s.whatsapp.net')
            self.assertEqual(resp['messageId'], 'abc_text')
        finally:
            self.mod._post_json = old_post
            self.mod.OUTBOUND_AUDIT_FILE = old_audit
    def test_safe_post_bridge_blocks_recent_duplicate_payload_before_transport(self):
        calls = []
        def fake_post(url, payload, timeout=30):
            calls.append((url, payload, timeout))
            return {'success': True, 'messageId': f'msg{len(calls)}'}
        old_post = self.mod._post_json
        old_audit = self.mod.OUTBOUND_AUDIT_FILE
        old_lock_dir = self.mod.SEND_LOCK_DIR
        tmp = Path('/tmp/whatsapp_safe_send_duplicate_guard')
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            self.mod._post_json = fake_post
            self.mod.OUTBOUND_AUDIT_FILE = tmp / 'audit.jsonl'
            if self.mod.OUTBOUND_AUDIT_FILE.exists():
                self.mod.OUTBOUND_AUDIT_FILE.unlink()
            self.mod.SEND_LOCK_DIR = tmp / 'locks'
            ok, first = self.mod.safe_send_text(4601, '11999998888', 'Mensagem igual', uid='unit', reconcile=False)
            self.assertTrue(ok)
            second = self.mod.safe_post_bridge(4601, '/send', {'to': '11999998888', 'text': 'Mensagem igual'}, uid='unit', reconcile=False)
            self.assertFalse(second.get('success'))
            self.assertTrue(second.get('blocked'))
            self.assertTrue(second.get('duplicate_recent'))
            self.assertEqual(len(calls), 1)
            rows = [json.loads(x) for x in self.mod.OUTBOUND_AUDIT_FILE.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(rows[-1]['event'], 'blocked_duplicate_recent')
            self.assertEqual(rows[-1]['duplicateOfMessageIds'], ['msg1'])
        finally:
            self.mod._post_json = old_post
            self.mod.OUTBOUND_AUDIT_FILE = old_audit
            self.mod.SEND_LOCK_DIR = old_lock_dir

    def test_recent_duplicate_scans_temporal_window_beyond_last_800_lines(self):
        old_audit = self.mod.OUTBOUND_AUDIT_FILE
        tmp = Path('/tmp/whatsapp_safe_send_audit_window')
        tmp.mkdir(parents=True, exist_ok=True)
        audit = tmp / 'audit.jsonl'
        pn = '5511999998888@s.whatsapp.net'
        payload = {'to': pn, 'text': 'Ainda é prioridade?'}
        duplicate_row = {
            'event': 'send',
            'ts': (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat(),
            'uid': 'unit',
            'port': 4601,
            'targetJid': pn,
            'sendType': 'text',
            'payloadSha256': self.mod._payload_sha256(payload),
            'messageIds': ['old-msg'],
            'bridge': {'to': pn},
        }
        filler = []
        for i in range(850):
            filler.append(json.dumps({
                'event': 'send',
                'ts': (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
                'uid': 'other',
                'port': 4601,
                'targetJid': f'55119999{i:04d}@s.whatsapp.net',
                'sendType': 'text',
                'payloadSha256': f'noise-{i}',
                'bridge': {'to': f'55119999{i:04d}@s.whatsapp.net'},
            }, ensure_ascii=False))
        audit.write_text(json.dumps(duplicate_row, ensure_ascii=False) + '\n' + '\n'.join(filler) + '\n', encoding='utf-8')
        try:
            self.mod.OUTBOUND_AUDIT_FILE = audit
            found = self.mod._recent_duplicate_send(4601, pn, 'text', payload, window_seconds=3600)
            self.assertIsNotNone(found)
            self.assertEqual(found['messageIds'], ['old-msg'])
        finally:
            self.mod.OUTBOUND_AUDIT_FILE = old_audit
    def test_recent_duplicate_blocks_same_payload_even_from_other_port(self):
        old_audit = self.mod.OUTBOUND_AUDIT_FILE
        tmp = Path('/tmp/whatsapp_safe_send_cross_port')
        tmp.mkdir(parents=True, exist_ok=True)
        audit = tmp / 'audit.jsonl'
        pn = '551188887777@s.whatsapp.net'
        payload = {'to': pn, 'text': 'Mesmo texto'}
        audit.write_text(json.dumps({
            'event': 'send',
            'ts': datetime.now(timezone.utc).isoformat(),
            'uid': 'sarah',
            'port': 4601,
            'targetJid': pn,
            'sendType': 'text',
            'payloadSha256': self.mod._payload_sha256(payload),
            'messageIds': ['cross-port-msg'],
            'bridge': {'to': pn},
        }, ensure_ascii=False) + '\n', encoding='utf-8')
        try:
            self.mod.OUTBOUND_AUDIT_FILE = audit
            found = self.mod._recent_duplicate_send(4603, pn, 'text', payload, window_seconds=3600)
            self.assertIsNotNone(found)
            self.assertEqual(found['port'], 4601)
        finally:
            self.mod.OUTBOUND_AUDIT_FILE = old_audit


    def test_safe_post_bridge_uses_global_transport_lock_and_payload_lock(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self.mod.OUTBOUND_AUDIT_FILE = tmp / 'audit.jsonl'
            self.mod.SEND_LOCK_DIR = tmp / 'locks'
            calls = []
            class DummyLock:
                def __init__(self, name): self.name = name
                def fileno(self): return -1
                def close(self): calls.append(('close', self.name))
            def fake_global():
                calls.append(('acquire', 'global'))
                return DummyLock('global')
            def fake_payload(port, target, send_type, payload):
                calls.append(('acquire', 'payload', port, target, send_type))
                return DummyLock('payload')
            def fake_release(fh):
                calls.append(('release', fh.name))
            self.mod._with_global_transport_lock = fake_global
            self.mod._with_send_lock = fake_payload
            self.mod._release_lock = fake_release
            self.mod._post_json = lambda url, payload, timeout=30: {'success': True, 'messageId': 'MID-GLOBAL'}
            self.mod.schedule_reconciliation = lambda audit: None
            resp = self.mod.safe_post_bridge(4601, '/send', {'to': '11999998888', 'text': 'Mensagem com lock global'}, uid='unit', reconcile=False)
            self.assertTrue(resp.get('success'))
            self.assertEqual(calls[0], ('acquire', 'global'))
            self.assertEqual(calls[1][0], 'acquire')
            self.assertEqual(calls[-2:], [('release', 'payload'), ('release', 'global')])


if __name__ == '__main__':
    unittest.main()
