import importlib.util
import unittest
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')


class WhatsAppCutoverReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('cutover', ROOT / 'scripts' / 'whatsapp_cutover_readiness.py')
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def test_audit_reports_known_active_dispatch_flows_and_callers(self):
        report = self.mod.build_cutover_report(ROOT)
        flows = {f['id']: f for f in report['flows']}
        for fid in ['agenda_queue', 'non_mql', 'diagnostic_mql', 'followup_parallel', 'reentry_drip', 'dynamic_sender']:
            self.assertIn(fid, flows, f'fluxo ausente no mapa de cutover: {fid}')
            self.assertTrue(flows[fid]['script'])
            self.assertIn('cron_name', flows[fid])

    def test_audit_classifies_only_ready_flows_as_cutover_candidate(self):
        report = self.mod.build_cutover_report(ROOT)
        flows = {f['id']: f for f in report['flows']}
        self.assertEqual(flows['agenda_queue']['cutover_status'], 'candidate')
        self.assertIn('has_complete_payload', flows['agenda_queue']['checks'])
        self.assertIn('lead_reply_guard', flows['agenda_queue']['checks'])
        self.assertEqual(flows['followup_parallel']['cutover_status'], 'needs_adapter')
        self.assertEqual(flows['diagnostic_mql']['cutover_status'], 'needs_adapter')

    def test_audit_detects_no_unknown_active_direct_senders_without_flow_owner(self):
        report = self.mod.build_cutover_report(ROOT)
        self.assertEqual(report['unknown_direct_senders'], [], report['unknown_direct_senders'])

    def test_report_has_safe_order_for_swapping(self):
        report = self.mod.build_cutover_report(ROOT)
        order = [step['flow_id'] for step in report['recommended_cutover_order']]
        self.assertGreaterEqual(len(order), 1)
        self.assertEqual(order[0], 'agenda_queue')
        self.assertLess(order.index('agenda_queue'), order.index('followup_parallel'))


if __name__ == '__main__':
    unittest.main()
