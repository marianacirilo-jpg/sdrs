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


class AgendaQueueWorkerOwnedCutoverTests(unittest.TestCase):
    def test_agenda_queue_worker_owned_does_not_call_legacy_send_and_marks_queued_worker_owned(self):
        agenda = load_module('scripts/agenda_queue_sender.py', 'agenda_queue_sender_cutover_test')
        queue_mod = load_module('scripts/whatsapp_dispatch_queue.py', 'dispatch_queue_for_agenda_cutover')
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            agenda.QUEUE = td / 'agenda_queue.json'
            agenda.WPP = td / 'wpp_envios.json'
            agenda.LOCK = td / 'agenda.lock'
            agenda.DISPATCH_QUEUE = td / 'whatsapp_dispatch_queue.json'
            agenda.QUEUE.write_text(json.dumps({'items': [{
                'key': 'agenda-test-1',
                'status': 'pending',
                'due_at': 0,
                'port': 4605,
                'jid': '5511999990000@s.whatsapp.net',
                'text': 'Podemos seguir para agenda?',
                'email': 'lead@example.com',
                'contact_id': '123',
                'deal_id': '456',
                'owner_id': '86265630',
                'question_message_id': 'Q1',
            }]}, ensure_ascii=False), encoding='utf-8')
            agenda.WPP.write_text(json.dumps({'envios': []}), encoding='utf-8')
            agenda.message_ts = lambda port, mid: 0
            agenda.lead_replied_after = lambda port, jid, ts0: []
            def forbidden_send(*args, **kwargs):
                raise AssertionError('legacy bridge send must not be called in worker_owned cutover mode')
            agenda.pg.post_bridge_with_retries_locked = forbidden_send

            agenda.main(worker_owned=True)

            items = json.loads(agenda.QUEUE.read_text(encoding='utf-8'))['items']
            self.assertEqual(items[0]['status'], 'queued_worker_owned')
            self.assertTrue(items[0].get('worker_dispatch_id'))
            self.assertFalse(items[0].get('done_at'))
            dispatches = queue_mod.load_dispatches(agenda.DISPATCH_QUEUE)
            self.assertEqual(len(dispatches), 1)
            row = dispatches[0]
            self.assertEqual(row['execution_mode'], 'worker_owned')
            self.assertEqual(row['agenda_queue_key'], 'agenda-test-1')
            self.assertEqual(row['completion_type'], 'agenda_queue')
            self.assertEqual(row['jid'], '5511999990000@s.whatsapp.net')
            self.assertEqual(row['port'], 4605)

    def test_agenda_queue_worker_owned_missing_text_never_enqueues_empty_dispatch(self):
        agenda = load_module('scripts/agenda_queue_sender.py', 'agenda_queue_sender_missing_text_test')
        queue_mod = load_module('scripts/whatsapp_dispatch_queue.py', 'dispatch_queue_for_agenda_missing_text')
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            agenda.QUEUE = td / 'agenda_queue.json'
            agenda.WPP = td / 'wpp_envios.json'
            agenda.LOCK = td / 'agenda.lock'
            agenda.DISPATCH_QUEUE = td / 'whatsapp_dispatch_queue.json'
            agenda.QUEUE.write_text(json.dumps({'items': [{
                'key': 'agenda-missing-text',
                'status': 'pending',
                'due_at': 0,
                'port': 4607,
                'jid': '5511999990002@s.whatsapp.net',
                'text': None,
                'email': 'lead3@example.com',
                'question_message_id': 'Q3',
            }]}, ensure_ascii=False), encoding='utf-8')
            agenda.WPP.write_text(json.dumps({'envios': []}), encoding='utf-8')
            agenda.message_ts = lambda port, mid: 0
            agenda.lead_replied_after = lambda port, jid, ts0: []

            agenda.main(worker_owned=True)

            items = json.loads(agenda.QUEUE.read_text(encoding='utf-8'))['items']
            self.assertEqual(items[0]['status'], 'needs_review')
            self.assertEqual(items[0]['result']['reason'], 'missing_agenda_text')
            self.assertFalse(queue_mod.load_dispatches(agenda.DISPATCH_QUEUE))

    def test_worker_completion_marks_agenda_item_done_only_after_worker_send_ok(self):
        completion = load_module('scripts/whatsapp_worker_completions.py', 'worker_completions_cutover_test')
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            completion.AGENDA_QUEUE = td / 'agenda_queue.json'
            completion.WPP = td / 'wpp_envios.json'
            completion.AGENDA_QUEUE.write_text(json.dumps({'items': [{
                'key': 'agenda-test-2',
                'status': 'queued_worker_owned',
                'worker_dispatch_id': 'dsp-test-2',
                'port': 4605,
                'jid': '5511999990001@s.whatsapp.net',
                'text': 'Agenda 2',
                'email': 'lead2@example.com',
                'contact_id': '222',
                'deal_id': '333',
                'owner_id': '86265630',
            }]}, ensure_ascii=False), encoding='utf-8')
            completion.WPP.write_text(json.dumps({'envios': [{'status': 'enviado_lead', 'email': 'lead2@example.com', 'to': '5511999990001@s.whatsapp.net', 'bridge_port': 4605}]}, ensure_ascii=False), encoding='utf-8')
            row = {
                'dispatch_id': 'dsp-test-2',
                'completion_type': 'agenda_queue',
                'agenda_queue_key': 'agenda-test-2',
                'jid': '5511999990001@s.whatsapp.net',
                'port': 4605,
                'text': 'Agenda 2',
                'owner_uid': '86265630',
            }
            resp = {'messageId': 'MSG-OK', 'status': 1}

            result = completion.complete_after_send(row, resp)

            self.assertTrue(result['ok'])
            items = json.loads(completion.AGENDA_QUEUE.read_text(encoding='utf-8'))['items']
            self.assertEqual(items[0]['status'], 'done')
            self.assertEqual(items[0]['result']['response']['messageId'], 'MSG-OK')
            self.assertTrue(items[0].get('done_at'))
            envios = json.loads(completion.WPP.read_text(encoding='utf-8'))['envios']
            self.assertTrue(any(r.get('status') == 'agenda_followup_done' and r.get('agenda_queue_key') == 'agenda-test-2' for r in envios))
            self.assertFalse(envios[0].get('agenda_pending', True))


if __name__ == '__main__':
    unittest.main()
