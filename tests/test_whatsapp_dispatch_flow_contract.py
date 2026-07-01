import unittest
import tempfile
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')

COMMERCIAL_SENDERS = [
    'disparo_dinamico.py',
    'scripts/cadencia_primeiro_contato.py',
    'scripts/process_gate_once.py',
    'scripts/agenda_queue_sender.py',
    'scripts/monitor_diagnostico_agendado.py',
    'scripts/non_mql_legit_outreach.py',
]

class WhatsAppDispatchFlowContractTests(unittest.TestCase):
    def test_all_commercial_senders_dual_write_to_unified_dispatch_queue(self):
        missing = []
        for rel in COMMERCIAL_SENDERS:
            text = (ROOT / rel).read_text(encoding='utf-8', errors='ignore')
            if 'record_dispatch_shadow' not in text and 'enqueue_dispatch' not in text and 'enqueue_intent' not in text:
                missing.append(rel)
        self.assertEqual(missing, [], f'senders sem dual-write para fila unificada: {missing}')

    def test_dual_write_helper_is_fail_open_for_current_traffic_and_dedupe_first(self):
        helper = (ROOT / 'scripts' / 'whatsapp_dispatch_flow.py').read_text(encoding='utf-8', errors='ignore')
        self.assertIn('def record_dispatch_shadow', helper)
        self.assertIn('enqueue_dispatch', helper)
        self.assertIn('except Exception', helper)
        self.assertIn('fail_open', helper)
        self.assertIn('logical_message_id', helper)
        self.assertIn('dedupe', helper.lower())

    def test_record_dispatch_shadow_writes_one_deduped_queue_item(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('flow', ROOT / 'scripts' / 'whatsapp_dispatch_flow.py')
        flow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(flow)
        qspec = importlib.util.spec_from_file_location('queue', ROOT / 'scripts' / 'whatsapp_dispatch_queue.py')
        queue = importlib.util.module_from_spec(qspec)
        qspec.loader.exec_module(queue)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'dispatch.json'
            first = flow.record_dispatch_shadow(origin='followup', nature='followup_f2', to='5511999999999', text='Oi teste', owner_uid='sarah', port=4601, path=path)
            second = flow.record_dispatch_shadow(origin='followup', nature='followup_f2', to='5511999999999', text='Oi teste', owner_uid='sarah', port=4601, path=path)
            self.assertTrue(first['ok'])
            self.assertTrue(second['deduped'])
            rows = queue.load_dispatches(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['origin'], 'followup')
            self.assertEqual(rows[0]['nature'], 'followup_f2')
            self.assertEqual(rows[0]['quota_class'], 'cold_automation')
            self.assertTrue(rows[0]['logical_message_id'].startswith('lm_'))
            self.assertEqual(rows[0]['execution_mode'], 'shadow')

    def test_record_dispatch_worker_owned_marks_live_executable_item(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('flow', ROOT / 'scripts' / 'whatsapp_dispatch_flow.py')
        flow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(flow)
        qspec = importlib.util.spec_from_file_location('queue', ROOT / 'scripts' / 'whatsapp_dispatch_queue.py')
        queue = importlib.util.module_from_spec(qspec)
        qspec.loader.exec_module(queue)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'dispatch.json'
            res = flow.record_dispatch_worker_owned(origin='agenda', nature='agenda_reminder', to='5511988888888', text='agenda', owner_uid='breno', port=4605, path=path)
            self.assertTrue(res['ok'])
            rows = queue.load_dispatches(path)
            self.assertEqual(rows[0]['execution_mode'], 'worker_owned')

    def test_record_dispatch_shadow_from_row_skips_internal_and_group_targets(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('flow', ROOT / 'scripts' / 'whatsapp_dispatch_flow.py')
        flow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(flow)
        group = flow.record_dispatch_shadow_from_row({'to': '120363408131718880@g.us', 'text': 'interno'}, origin='agenda', nature='internal_group_alert')
        mariana = flow.record_dispatch_shadow_from_row({'to': '553484255965@s.whatsapp.net', 'text': 'interno'}, origin='agenda', nature='internal_group_alert')
        self.assertTrue(group['skipped'])
        self.assertTrue(mariana['skipped'])
        self.assertEqual(group['reason'], 'internal_or_group_target')

if __name__ == '__main__':
    unittest.main()
