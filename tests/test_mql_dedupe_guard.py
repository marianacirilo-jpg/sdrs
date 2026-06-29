# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from mql_dedupe_guard import can_send_diagnostic  # noqa: E402
from mql_execution_queue import dedupe_keys, execution_id  # noqa: E402


class TestMqlDedupeGuard(unittest.TestCase):
    def _paths(self, td):
        return Path(td) / 'wpp_envios.json', Path(td) / 'mql_execution_queue.json'

    def test_permite_quando_nao_existe_historico(self):
        with tempfile.TemporaryDirectory() as td:
            ledger, queue = self._paths(td)
            ok, reason = can_send_diagnostic(contact_id='1', deal_id='2', phone='5534999991111', email='lead@empresa.com', ledger_path=ledger, queue_path=queue)
            self.assertTrue(ok)
            self.assertIn('sem envio anterior', reason)

    def test_bloqueia_por_email_enviado_lead_no_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            ledger, queue = self._paths(td)
            ledger.write_text(json.dumps({'envios': [{'status': 'enviado_lead', 'email': 'lead@empresa.com'}]}), encoding='utf-8')
            ok, reason = can_send_diagnostic(contact_id='1', deal_id='2', phone='5534999991111', email='Lead@Empresa.com', ledger_path=ledger, queue_path=queue)
            self.assertFalse(ok)
            self.assertIn('ledger', reason)
            self.assertIn('email', reason)

    def test_bloqueia_por_telefone_em_andamento_no_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            ledger, queue = self._paths(td)
            ledger.write_text(json.dumps({'envios': [{'status': 'mql_diagnostico_em_andamento', 'to': '5534999991111@s.whatsapp.net'}]}), encoding='utf-8')
            ok, reason = can_send_diagnostic(contact_id='1', deal_id='2', phone='+55 34 99999-1111', email='novo@empresa.com', ledger_path=ledger, queue_path=queue)
            self.assertFalse(ok)
            self.assertIn('telefone', reason)

    def test_bloqueia_por_fila_whatsapp_done(self):
        with tempfile.TemporaryDirectory() as td:
            ledger, queue = self._paths(td)
            keys = dedupe_keys(contact_id='1', deal_id='2', phone='5534999991111', email='lead@empresa.com')
            queue.write_text(json.dumps({'version': 1, 'items': [{
                'execution_id': execution_id(keys),
                'dedupe_keys': keys,
                'steps': {'whatsapp_sent': {'status': 'done', 'message_id': 'ABC'}}
            }]}), encoding='utf-8')
            ok, reason = can_send_diagnostic(contact_id='1', deal_id='2', phone='5534999991111', email='lead@empresa.com', ledger_path=ledger, queue_path=queue)
            self.assertFalse(ok)
            self.assertIn('fila', reason)
            self.assertIn('whatsapp_sent.done', reason)

    def test_bloqueia_por_fila_status_em_execucao(self):
        with tempfile.TemporaryDirectory() as td:
            ledger, queue = self._paths(td)
            keys = dedupe_keys(email='lead@empresa.com')
            queue.write_text(json.dumps({'version': 1, 'items': [{
                'execution_id': execution_id(keys),
                'dedupe_keys': keys,
                'status': 'executing',
                'steps': {}
            }]}), encoding='utf-8')
            ok, reason = can_send_diagnostic(email='lead@empresa.com', ledger_path=ledger, queue_path=queue)
            self.assertFalse(ok)
            self.assertIn('executing', reason)


if __name__ == '__main__':
    unittest.main()
