import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT = Path('/root/.hermes/scripts/zydon_reentry_diagnostic_drip_20260701.py')
ROOT = Path('/root/.hermes/zydon-prospeccao')


def load_mod():
    spec = importlib.util.spec_from_file_location('reentry_drip_test', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ReentryDiagnosticDripSafetyTests(unittest.TestCase):
    def test_stale_in_progress_items_are_requeued_before_batch(self):
        mod = load_mod()
        brt = ZoneInfo('America/Sao_Paulo')
        now = datetime(2026, 7, 1, 12, 0, tzinfo=brt)
        q = {
            'items': [
                {'status': 'in_progress', 'email': 'old@example.com', 'started_at': (now - timedelta(hours=2)).isoformat(), 'attempts': 1},
                {'status': 'in_progress', 'email': 'fresh@example.com', 'started_at': (now - timedelta(minutes=5)).isoformat(), 'attempts': 0},
                {'status': 'sent', 'email': 'sent@example.com', 'started_at': (now - timedelta(hours=2)).isoformat()},
            ]
        }
        changed = mod.requeue_stale_in_progress(q, now_dt=now, max_age_minutes=45)
        self.assertEqual(changed, 1)
        self.assertEqual(q['items'][0]['status'], 'pending')
        self.assertEqual(q['items'][0]['attempts'], 2)
        self.assertIn('requeued_from_stale_in_progress', q['items'][0]['last_requeue_reason'])
        self.assertEqual(q['items'][1]['status'], 'in_progress')
        self.assertEqual(q['items'][2]['status'], 'sent')


class ReentryDiagnosticNatureTests(unittest.TestCase):
    def test_reentry_diagnostic_nature_is_registered_so_completion_does_not_crash(self):
        # O completion worker_owned chama enrich_legacy_row -> describe_nature.
        # Se a nature não estiver na taxonomia, o completion quebra e o ledger
        # real do lead nunca é escrito (dedupe/histórico ficam cegos).
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'wpp_nature_test', ROOT / 'scripts' / 'whatsapp_message_nature.py')
        n = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(n)
        self.assertIn('reentry_diagnostic', n.known_natures())
        desc = n.describe_nature('reentry_diagnostic', 'cold_outreach')
        self.assertEqual(desc['quota_class'], 'cold_automation')
        self.assertTrue(desc['quota_counted'])


class ReentryReclassifyDryRunTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_mod()
        self.brt = ZoneInfo('America/Sao_Paulo')
        self.now = datetime(2026, 7, 1, 12, 0, tzinfo=self.brt)

    def _no_dupe(self, item):
        return (False, '')

    def test_existing_diagnostic_is_marked_skip_not_resent(self):
        q = {'items': [{'status': 'pending', 'email': 'dup@example.com', 'phone': '11999998888'}]}
        plan = self.mod.reclassify_queue_dry_run(
            q, dispatches=[], now_dt=self.now,
            dedupe_fn=lambda it: (True, 'ledger status enviado_lead por email'))
        self.assertEqual(plan['plan'][0]['action'], 'skip_existing_diagnostic')
        changed = self.mod.apply_reclassification(q, plan, now_dt=self.now)
        self.assertEqual(changed, 1)
        self.assertEqual(q['items'][0]['status'], 'skipped_existing_diagnostic')

    def test_stale_in_progress_requeues_and_fresh_is_kept(self):
        q = {'items': [
            {'status': 'in_progress', 'email': 'old@x.com', 'phone': '11999990001',
             'started_at': (self.now - timedelta(hours=2)).isoformat()},
            {'status': 'in_progress', 'email': 'fresh@x.com', 'phone': '11999990002',
             'started_at': (self.now - timedelta(minutes=5)).isoformat()},
        ]}
        plan = self.mod.reclassify_queue_dry_run(q, dispatches=[], now_dt=self.now, dedupe_fn=self._no_dupe)
        actions = {p['email']: p['action'] for p in plan['plan']}
        self.assertEqual(actions['old@x.com'], 'requeue_pending')
        self.assertEqual(actions['fresh@x.com'], 'keep_in_progress')
        self.mod.apply_reclassification(q, plan, now_dt=self.now)
        self.assertEqual(q['items'][0]['status'], 'pending')
        self.assertEqual(q['items'][0]['attempts'], 1)
        self.assertEqual(q['items'][1]['status'], 'in_progress')

    def test_missing_phone_is_flagged_needs_review_not_improvised(self):
        q = {'items': [{'status': 'needs_review', 'email': 'nophone@x.com', 'phone': ''}]}
        plan = self.mod.reclassify_queue_dry_run(q, dispatches=[], now_dt=self.now, dedupe_fn=self._no_dupe)
        entry = plan['plan'][0]
        self.assertEqual(entry['action'], 'needs_review')
        self.assertTrue(entry.get('ambiguous'))
        self.assertIn('telefone', entry['reason'])

    def test_clean_needs_review_is_requeued_to_pending(self):
        q = {'items': [{'status': 'needs_review', 'email': 'ok@x.com', 'phone': '11999990003'}]}
        plan = self.mod.reclassify_queue_dry_run(q, dispatches=[], now_dt=self.now, dedupe_fn=self._no_dupe)
        self.assertEqual(plan['plan'][0]['action'], 'requeue_pending')

    def test_active_central_dispatch_is_respected_not_recontacted(self):
        q = {'items': [{'status': 'pending', 'email': 'live@x.com', 'phone': '11999990004',
                        'deal_id': 'D123', 'worker_owned_dispatch_id': 'dsp_live'}]}
        dispatches = [{'dispatch_id': 'dsp_live', 'origin': 'reentry', 'status': 'queued', 'lead_key': 'D123'}]
        plan = self.mod.reclassify_queue_dry_run(q, dispatches=dispatches, now_dt=self.now, dedupe_fn=self._no_dupe)
        self.assertEqual(plan['plan'][0]['action'], 'already_queued_worker_owned')

    def test_sent_central_dispatch_reconciles_item_to_sent(self):
        q = {'items': [{'status': 'in_progress', 'email': 's@x.com', 'phone': '11999990005',
                        'worker_owned_dispatch_id': 'dsp_sent'}]}
        dispatches = [{'dispatch_id': 'dsp_sent', 'origin': 'reentry', 'status': 'sent'}]
        plan = self.mod.reclassify_queue_dry_run(q, dispatches=dispatches, now_dt=self.now, dedupe_fn=self._no_dupe)
        self.assertEqual(plan['plan'][0]['action'], 'reconcile_sent')
        self.mod.apply_reclassification(q, plan, now_dt=self.now)
        self.assertEqual(q['items'][0]['status'], 'sent')

    def test_lost_worker_dispatch_is_flagged_needs_review(self):
        q = {'items': [{'status': 'queued_worker_owned', 'email': 'lost@x.com', 'phone': '11999990006',
                        'worker_owned_dispatch_id': 'dsp_gone'}]}
        # queued_worker_owned não está em TARGET, então não entra no plano; força in_progress.
        q['items'][0]['status'] = 'in_progress'
        plan = self.mod.reclassify_queue_dry_run(q, dispatches=[], now_dt=self.now, dedupe_fn=self._no_dupe)
        entry = plan['plan'][0]
        self.assertEqual(entry['action'], 'needs_review')
        self.assertEqual(entry.get('lost_dispatch_id'), 'dsp_gone')

    def test_apply_is_idempotent(self):
        q = {'items': [{'status': 'pending', 'email': 'dup@x.com', 'phone': '11999990007'}]}
        plan = self.mod.reclassify_queue_dry_run(
            q, dispatches=[], now_dt=self.now, dedupe_fn=lambda it: (True, 'já enviado'))
        first = self.mod.apply_reclassification(q, plan, now_dt=self.now)
        second = self.mod.apply_reclassification(q, plan, now_dt=self.now)
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)


if __name__ == '__main__':
    unittest.main()
