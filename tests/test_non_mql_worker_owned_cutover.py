import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')


def load_module(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class NonMqlWorkerOwnedCutoverTests(unittest.TestCase):
    def _candidate(self):
        return {
            'email': 'leadnaomql@example.com',
            'contact_id': '12345',
            'props': {'firstname': 'Joana', 'company': 'Empresa Exemplo'},
            'research': {'motivo': 'Não-MQL teste', 'slug': 'empresa-exemplo'},
            'slug': 'empresa-exemplo',
            'company': 'Empresa Exemplo',
            'phone': '11987654321',
            'phone_variants': ['11987654321', '1187654321'],
            'domain': 'example.com',
            'deals': ['999'],
            'reason': 'Não-MQL teste',
        }

    def test_non_mql_worker_owned_does_not_call_legacy_send_and_enqueues_alternates(self):
        non = load_module('scripts/non_mql_legit_outreach.py', 'non_mql_cutover_test')
        queue_mod = load_module('scripts/whatsapp_dispatch_queue.py', 'dispatch_queue_for_non_mql_cutover')
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            non.DISPATCH_QUEUE = td / 'whatsapp_dispatch_queue.json'
            envios = []
            cand = self._candidate()
            sender = {'port': 4606, 'name': 'Lucas Resende', 'intro': 'x'}
            def forbidden(*args, **kwargs):
                raise AssertionError('legacy bridge send must not be called in worker_owned mode')
            non.post_bridge_short = forbidden

            result = non.send_one(cand, sender, envios, dry_run=False, worker_owned=True)

            self.assertTrue(result['ok'])
            self.assertEqual(result['mode'], 'worker_owned')
            self.assertEqual(envios, [])
            rows = queue_mod.load_dispatches(non.DISPATCH_QUEUE)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['execution_mode'], 'worker_owned')
            self.assertEqual(row['origin'], 'nao_mql')
            self.assertEqual(row['completion_type'], 'non_mql')
            self.assertEqual(row['jid'], '5511987654321@s.whatsapp.net')
            self.assertIn('551187654321@s.whatsapp.net', row['alternate_jids'])
            self.assertEqual(row['contact_id'], '12345')
            self.assertEqual(row['campaign_id'], non.CAMPAIGN)

    def test_non_mql_completion_records_ledger_and_task_after_worker_send_ok(self):
        completion = load_module('scripts/whatsapp_worker_completions.py', 'worker_completions_non_mql_test')
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            completion.WPP = td / 'wpp_envios.json'
            completion.WPP.write_text(json.dumps({'envios': []}), encoding='utf-8')
            created_tasks = []
            completion.create_non_mql_task = lambda row, msg, response: created_tasks.append((row, msg, response)) or 'task-123'
            row = {
                'dispatch_id': 'dsp-non-mql-1',
                'completion_type': 'non_mql',
                'origin': 'nao_mql',
                'nature': 'non_mql_outreach',
                'jid': '5511987654321@s.whatsapp.net',
                'port': 4606,
                'text': 'Oi Joana...',
                'email': 'leadnaomql@example.com',
                'contact_id': '12345',
                'slug': 'empresa-exemplo',
                'empresa': 'Empresa Exemplo',
                'phone': '11987654321',
                'sender_name': 'Lucas Resende',
                'campaign_id': 'nao_mql_legitimo_tratativa',
                'reason': 'Não-MQL teste',
                'deals': ['999'],
            }
            resp = {'messageId': 'WA-NON-MQL-OK', 'status': 1}

            result = completion.complete_after_send(row, resp)

            self.assertTrue(result['ok'])
            self.assertEqual(result['task_id'], 'task-123')
            envios = json.loads(completion.WPP.read_text(encoding='utf-8'))['envios']
            self.assertEqual(len(envios), 1)
            entry = envios[0]
            self.assertEqual(entry['status'], 'enviado_nao_mql_legitimo')
            self.assertEqual(entry['messageId'], 'WA-NON-MQL-OK')
            self.assertEqual(entry['task_id'], 'task-123')
            self.assertEqual(entry['campaign_id'], 'nao_mql_legitimo_tratativa')
            self.assertEqual(len(created_tasks), 1)


if __name__ == '__main__':
    unittest.main()
