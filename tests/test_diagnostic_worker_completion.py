import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')


def load_completions():
    spec = importlib.util.spec_from_file_location('whatsapp_worker_completions_test', ROOT / 'scripts' / 'whatsapp_worker_completions.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DiagnosticWorkerCompletionTests(unittest.TestCase):
    def test_diagnostic_bundle_completion_writes_ledger_and_agenda_after_worker_send(self):
        mod = load_completions()
        with tempfile.TemporaryDirectory() as td:
            old_wpp = mod.WPP
            old_agenda = mod.AGENDA_QUEUE
            mod.WPP = Path(td) / 'wpp_envios.json'
            mod.AGENDA_QUEUE = Path(td) / 'agenda_queue.json'
            mod.WPP.write_text(json.dumps({'envios': []}), encoding='utf-8')
            try:
                row = {
                    'completion_type': 'diagnostic_bundle',
                    'email': 'lead@empresa.com.br',
                    'contact_id': '123',
                    'deal_id': '456',
                    'slug': 'empresa-lead',
                    'empresa': 'Empresa Lead',
                    'phone': '11999999999',
                    'jid': '5511999999999@s.whatsapp.net',
                    'port': 4601,
                    'owner_id': '88063842',
                    'owner_name': 'Sarah',
                    'sender_name': 'Sarah',
                    'text': 'Bom dia. Fiz uma análise prévia do potencial da digitalização B2B do seu negócio.',
                    'question_text': 'Como você imagina que a Zydon poderia te apoiar?',
                    'agenda_text': 'Se quiser garantir o melhor horário...',
                    'pdf_path': '/tmp/Empresa - Potencial de Digitalizacao B2B.pdf',
                    'hubspot_file_id': 'file-1',
                    'hubspot_file_error': None,
                    'task_id': 'task-1',
                    'group_summary_response': {'skipped': True, 'reason': 'test'},
                    'question_sent_at': '2026-07-01T12:00:00+00:00',
                    'agenda_queue_key': 'agenda:lead@empresa.com.br:empresa-lead:4601:5511999999999@s.whatsapp.net',
                }
                response = {
                    'success': True,
                    'messageId': 'mid-question',
                    'messageIds': ['mid-text', 'mid-file', 'mid-question'],
                    'responses': [
                        {'part': 1, 'response': {'messageId': 'mid-text'}},
                        {'part': 2, 'response': {'messageId': 'mid-file'}},
                        {'part': 3, 'response': {'messageId': 'mid-question'}},
                    ],
                }
                out = mod.complete_after_send(row, response)
                self.assertTrue(out['ok'])
                data = json.loads(mod.WPP.read_text(encoding='utf-8'))
                envios = data['envios']
                self.assertEqual(len(envios), 1)
                rec = envios[0]
                self.assertEqual(rec['status'], 'enviado_lead')
                self.assertEqual(rec['to'], row['jid'])
                self.assertEqual(rec['bridge_port'], 4601)
                self.assertEqual(rec['text_response']['messageId'], 'mid-text')
                self.assertEqual(rec['file_response']['messageId'], 'mid-file')
                self.assertEqual(rec['question_response']['messageId'], 'mid-question')
                self.assertTrue(rec['agenda_pending'])
                agenda = json.loads(mod.AGENDA_QUEUE.read_text(encoding='utf-8'))
                self.assertEqual(len(agenda['items']), 1)
                self.assertEqual(agenda['items'][0]['key'], row['agenda_queue_key'])
                self.assertEqual(agenda['items'][0]['status'], 'pending')
            finally:
                mod.WPP = old_wpp
                mod.AGENDA_QUEUE = old_agenda


if __name__ == '__main__':
    unittest.main()
