import importlib.util
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path('/root/.hermes/zydon-prospeccao')


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WhatsAppDispatchQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q = load_module('whatsapp_dispatch_queue')

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.path = Path(self._td.name) / 'whatsapp_dispatch_queue.json'

    def tearDown(self):
        self._td.cleanup()

    def _enqueue(self, **kw):
        base = dict(origin='followup', to='5511999999999@s.whatsapp.net', nature='followup_f1',
                    owner_uid='breno', text='Oi, tudo bem?', path=self.path)
        base.update(kw)
        return self.q.enqueue_dispatch(**base)

    def test_enqueue_is_idempotent_and_dedupes(self):
        first = self._enqueue()
        second = self._enqueue()
        self.assertTrue(first['ok'])
        self.assertFalse(first['deduped'])
        self.assertTrue(second['deduped'])
        self.assertEqual(first['dispatch_id'], second['dispatch_id'])
        rows = self.q.load_dispatches(self.path)
        self.assertEqual(len(rows), 1)

    def test_different_lead_or_origin_are_not_deduped(self):
        self._enqueue()
        other_lead = self._enqueue(to='5511888888888@s.whatsapp.net')
        other_origin = self._enqueue(origin='proatividade', nature='first_contact')
        self.assertFalse(other_lead['deduped'])
        self.assertFalse(other_origin['deduped'])
        self.assertEqual(len(self.q.load_dispatches(self.path)), 3)

    def test_enqueue_blocks_same_lead_on_second_port_even_with_different_content(self):
        first = self._enqueue(to='553499999999', port=4601, text='primeira abordagem')
        second = self._enqueue(to='553499999999', port=4611, text='segunda abordagem diferente')
        self.assertTrue(first['ok'])
        self.assertFalse(second['ok'])
        self.assertTrue(second['blocked'])
        self.assertEqual(second['reason'], 'active_contact_other_port')
        self.assertEqual(second['existing_port'], 4601)
        self.assertEqual(len(self.q.load_dispatches(self.path)), 1)

    def test_enqueue_allows_same_lead_same_port_followup(self):
        first = self._enqueue(to='553499999999', port=4601, text='primeira abordagem')
        second = self._enqueue(to='553499999999', port=4601, text='follow up diferente', nature='followup_f2')
        self.assertTrue(first['ok'])
        self.assertTrue(second['ok'])
        self.assertFalse(second['deduped'])
        self.assertEqual(len(self.q.load_dispatches(self.path)), 2)

    def test_dedupe_uses_logical_message_not_parts(self):
        parts = [
            {'kind': 'text', 'text': 'Parte um do follow'},
            {'kind': 'text', 'text': 'Parte dois do follow'},
        ]
        a = self.q.enqueue_dispatch(origin='followup', to='5511777777777@s.whatsapp.net',
                                    nature='followup_f2', owner_uid='sarah', parts=parts, path=self.path)
        b = self.q.enqueue_dispatch(origin='followup', to='5511777777777@s.whatsapp.net',
                                    nature='followup_f2', owner_uid='sarah', parts=parts, path=self.path)
        self.assertFalse(a['deduped'])
        self.assertTrue(b['deduped'])
        # Uma única mensagem lógica com 2 partes => 1 hash, 1 linha na fila.
        self.assertEqual(len(self.q.load_dispatches(self.path)), 1)
        # Enfileirar apenas a primeira parte é OUTRA mensagem lógica => não dedupa.
        c = self.q.enqueue_dispatch(origin='followup', to='5511777777777@s.whatsapp.net',
                                    nature='followup_f2', owner_uid='sarah', parts=parts[:1], path=self.path)
        self.assertFalse(c['deduped'])
        self.assertEqual(len(self.q.load_dispatches(self.path)), 2)

    def test_dedupe_window_allows_new_dispatch_after_window(self):
        t0 = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
        self._enqueue(now=t0, dedupe_window_seconds=3600)
        # Dentro da janela: dedupa.
        inside = self._enqueue(now=t0 + timedelta(minutes=30), dedupe_window_seconds=3600)
        self.assertTrue(inside['deduped'])
        # Fora da janela: novo disparo legítimo.
        outside = self._enqueue(now=t0 + timedelta(hours=2), dedupe_window_seconds=3600)
        self.assertFalse(outside['deduped'])
        self.assertEqual(len(self.q.load_dispatches(self.path)), 2)

    def test_acquire_locks_next_atomically_by_priority(self):
        t0 = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
        self.q.enqueue_dispatch(origin='followup', to='5511111111111@s.whatsapp.net', nature='followup_f1',
                                owner_uid='breno', text='follow', path=self.path, now=t0)
        self.q.enqueue_dispatch(origin='agenda', to='5511222222222@s.whatsapp.net', nature='agenda_reminder',
                                owner_uid='breno', text='lembrete', path=self.path, now=t0)
        picked = self.q.acquire_next_dispatch(owner_uid='breno', locked_by='worker-1', path=self.path, now=t0)
        # agenda tem prioridade menor (sai antes) que followup.
        self.assertEqual(picked['origin'], 'agenda')
        self.assertEqual(picked['status'], 'locked')
        self.assertEqual(picked['attempts'], 1)
        self.assertEqual(picked['locked_by'], 'worker-1')
        # O mesmo item não pode ser reservado duas vezes.
        picked2 = self.q.acquire_next_dispatch(owner_uid='breno', locked_by='worker-2', path=self.path, now=t0)
        self.assertEqual(picked2['origin'], 'followup')
        picked3 = self.q.acquire_next_dispatch(owner_uid='breno', locked_by='worker-3', path=self.path, now=t0)
        self.assertIsNone(picked3)

    def test_acquire_respects_scheduled_at(self):
        t0 = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
        future = (t0 + timedelta(hours=1)).isoformat()
        self.q.enqueue_dispatch(origin='followup', to='5511333333333@s.whatsapp.net', nature='followup_f1',
                                owner_uid='sarah', text='depois', scheduled_at=future, path=self.path, now=t0)
        self.assertIsNone(self.q.acquire_next_dispatch(owner_uid='sarah', path=self.path, now=t0))
        got = self.q.acquire_next_dispatch(owner_uid='sarah', path=self.path, now=t0 + timedelta(hours=2))
        self.assertIsNotNone(got)

    def test_mark_sent_and_failed(self):
        res = self._enqueue()
        did = res['dispatch_id']
        sent = self.q.mark_dispatch_status(did, 'sent', path=self.path, messageId='WA123')
        self.assertEqual(sent['status'], 'sent')
        self.assertEqual(sent['messageId'], 'WA123')
        self.assertIn('sent_at', sent)
        failed = self.q.mark_dispatch_status(did, 'failed', last_error='bridge_timeout', path=self.path)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['last_error'], 'bridge_timeout')

    def test_mark_status_rejects_unknown_status(self):
        res = self._enqueue()
        with self.assertRaises(ValueError):
            self.q.mark_dispatch_status(res['dispatch_id'], 'exploded', path=self.path)

    def test_enqueue_rejects_unknown_origin(self):
        with self.assertRaises(ValueError):
            self._enqueue(origin='banana')

    def test_metrics_by_origin_status_owner_and_port(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        self.q.enqueue_dispatch(origin='followup', to='5511444444444@s.whatsapp.net', nature='followup_f1',
                                owner_uid='breno', port=4605, text='a', path=self.path, now=t0)
        self.q.enqueue_dispatch(origin='diagnostico', to='5511555555555@s.whatsapp.net', nature='diagnostic_bundle',
                                owner_uid='sarah', port=4601, text='b', path=self.path, now=t0)
        r = self.q.enqueue_dispatch(origin='agenda', to='5511666666666@s.whatsapp.net', nature='agenda_reminder',
                                    owner_uid='breno', port=4605, text='c', path=self.path, now=t0)
        self.q.mark_dispatch_status(r['dispatch_id'], 'sent', path=self.path, now=t0)
        m = self.q.queue_metrics(path=self.path, now=t0)
        self.assertEqual(m['total'], 3)
        self.assertEqual(m['queued'], 2)
        self.assertEqual(m['sent'], 1)
        self.assertEqual(m['sentToday'], 1)
        self.assertEqual(m['byOrigin']['followup'], 1)
        self.assertEqual(m['byOwner']['breno'], 2)
        self.assertEqual(m['byPort']['4605'], 2)
        self.assertEqual(m['throughputLastHour'], 1)

    def test_snapshot_returns_summary_and_recent_rows(self):
        for i in range(3):
            self.q.enqueue_dispatch(origin='proatividade', to=f'55119999999{i}{i}@s.whatsapp.net',
                                    nature='first_contact', owner_uid='lucas_batista', text=f'msg {i}', path=self.path)
        snap = self.q.dispatch_queue_snapshot(limit=2, path=self.path)
        self.assertEqual(snap['summary']['total'], 3)
        self.assertEqual(len(snap['rows']), 2)
        self.assertIn('dispatchId', snap['rows'][0])
        self.assertIn('status', snap['rows'][0])

    def test_required_fields_present_on_every_row(self):
        res = self._enqueue()
        row = res['row']
        required = {
            'dispatch_id', 'origin', 'nature', 'quota_class', 'priority', 'owner_uid', 'lead_key',
            'jid', 'phone', 'port', 'sender_role', 'message_hash', 'logical_message_id', 'dedupe_key',
            'scheduled_at', 'locked_at', 'attempts', 'last_error', 'created_at', 'updated_at', 'status', 'execution_mode',
        }
        missing = required - set(row.keys())
        self.assertEqual(missing, set(), f'campos obrigatórios ausentes: {missing}')

    def test_orchestrator_intent_compatibility_helper(self):
        orch = load_module('whatsapp_send_orchestrator')
        intent = orch.prepare_intent(owner_uid='sarah', to='5511888888888@s.whatsapp.net', nature='first_contact',
                                     origin='cron_first_contact', text='oi', rows=[],
                                     users={'sarah': {'role': 'sdr', 'ports': [4601]}},
                                     ports={4601: {'owner': 'sarah', 'role': 'sdr'}})
        res = self.q.enqueue_intent(intent, origin='proatividade', path=self.path)
        self.assertTrue(res['ok'])
        row = res['row']
        self.assertEqual(row['origin'], 'proatividade')
        self.assertEqual(row['nature'], 'first_contact')
        self.assertEqual(row['port'], 4601)
        self.assertEqual(row['logical_message_id'], intent['logical_message_id'])

    def test_capacity_policy_targets_1000_unique_conversations_and_10_simultaneous(self):
        policy = self.q.dispatch_capacity_policy()
        self.assertEqual(policy['dailyUniqueConversationTarget'], 1000)
        self.assertEqual(policy['maxSimultaneousConversations'], 10)
        self.assertGreaterEqual(policy['requiredSdrChips'], 6)
        self.assertGreaterEqual(policy['perChipDailyTarget'], 167)
        self.assertIn('lock_by_port', policy['locks'])
        self.assertIn('lock_by_destination', policy['locks'])

    def test_acquire_batch_respects_global_concurrency_ports_and_destinations(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        # 12 intenções; duas repetem porta/destino e não devem ser reservadas no mesmo batch.
        for i in range(12):
            port = 4601 if i < 2 else 4600 + i
            phone = '5511999000000' if i in (0, 1) else f'55119990000{i:02d}'
            self.q.enqueue_dispatch(origin='proatividade', to=phone, nature='first_contact',
                                    owner_uid='sarah', port=port, text=f'oi {i}', path=self.path, now=t0)
        batch = self.q.acquire_dispatch_batch(path=self.path, max_items=10, locked_by='worker-shadow', now=t0)
        self.assertEqual(len(batch), 10)
        self.assertEqual(len({r['port'] for r in batch}), 10)
        self.assertEqual(len({r['jid'] for r in batch}), 10)
        self.assertTrue(all(r['status'] == 'locked' for r in batch))

    def test_dispatch_flow_blocks_groups_broadcast_and_internal_chip_targets(self):
        flow = load_module('whatsapp_dispatch_flow')
        blocked = [
            '120363408131718880@g.us',
            'status@broadcast',
            '5511999999999@broadcast',
            '553484325076@s.whatsapp.net',  # Breno interno
            '553484291640@s.whatsapp.net',  # Sarah interno
            '553484295409@s.whatsapp.net',  # Lucas Batista interno
            '553484428888@s.whatsapp.net',  # Lucas Resende interno
            '553496698718@s.whatsapp.net',  # Rafael interno
        ]
        for jid in blocked:
            res = flow.record_dispatch_shadow_from_row({'to': jid, 'text': 'oi', 'port': 4605}, origin='followup', nature='followup_f1')
            self.assertTrue(res.get('skipped'), jid)
            self.assertEqual(res.get('reason'), 'internal_or_group_target')

    def test_live_worker_blocks_groups_broadcast_and_internal_chip_targets(self):
        worker = load_module('whatsapp_dispatch_worker')
        blocked = [
            '120363408131718880@g.us',
            'status@broadcast',
            '5511999999999@broadcast',
            '553484325076@s.whatsapp.net',
            '553484291640@s.whatsapp.net',
            '553484295409@s.whatsapp.net',
            '553484428888@s.whatsapp.net',
            '553496698718@s.whatsapp.net',
        ]
        for jid in blocked:
            row = {'execution_mode': 'worker_owned', 'port': 4605, 'jid': jid, 'text': 'oi'}
            self.assertEqual(worker._validate_live_row(row), 'internal_or_group_target_blocked', jid)

    def test_worker_dry_run_locks_but_does_not_send_and_requeues(self):
        worker = load_module('whatsapp_dispatch_worker')
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        for i in range(3):
            self.q.enqueue_dispatch(origin='followup', to=f'55119888888{i:02d}', nature='followup_f1',
                                    owner_uid='breno', port=4605 + i, text=f'follow {i}', path=self.path, now=t0)
        result = worker.run_once(path=self.path, dry_run=True, max_simultaneous=10, now=t0)
        self.assertEqual(result['mode'], 'dry_run')
        self.assertEqual(result['locked'], 3)
        self.assertEqual(result['sent'], 0)
        rows = self.q.load_dispatches(self.path)
        self.assertEqual({r['status'] for r in rows}, {'queued'})
        self.assertTrue(all(r.get('shadow_checked_at') for r in rows))

    def test_live_worker_ignores_shadow_rows_and_only_sends_worker_owned(self):
        worker = load_module('whatsapp_dispatch_worker')
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        self.q.enqueue_dispatch(origin='followup', to='5511988888801', nature='followup_f1',
                                owner_uid='breno', port=4605, text='shadow legado', path=self.path, now=t0,
                                execution_mode='shadow')
        owned = self.q.enqueue_dispatch(origin='agenda', to='5511988888802', nature='agenda_reminder',
                                        owner_uid='breno', port=4606, text='worker novo', path=self.path, now=t0,
                                        execution_mode='worker_owned')
        calls = []
        def fake_transport(row):
            calls.append(row)
            return {'ok': True, 'messageId': 'WA-LIVE-1', 'status': 1}
        result = worker.run_once(path=self.path, dry_run=False, max_simultaneous=10, now=t0, transport=fake_transport)
        self.assertEqual(result['mode'], 'live')
        self.assertEqual(result['sent'], 1)
        self.assertEqual(result['blocked'], 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['dispatch_id'], owned['dispatch_id'])
        rows = {r['dispatch_id']: r for r in self.q.load_dispatches(self.path)}
        self.assertEqual(rows[owned['dispatch_id']]['status'], 'sent')
        shadow = [r for r in rows.values() if r['text'] == 'shadow legado'][0]
        self.assertEqual(shadow['status'], 'queued')

    def test_live_worker_blocks_incomplete_worker_owned_rows_without_sending(self):
        worker = load_module('whatsapp_dispatch_worker')
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        bad = self.q.enqueue_dispatch(origin='agenda', to='5511988888803', nature='agenda_reminder',
                                      owner_uid='breno', port=None, text='sem porta', path=self.path, now=t0,
                                      execution_mode='worker_owned')
        calls = []
        result = worker.run_once(path=self.path, dry_run=False, max_simultaneous=10, now=t0, transport=lambda row: calls.append(row))
        self.assertEqual(result['sent'], 0)
        self.assertEqual(result['blocked'], 1)
        self.assertEqual(calls, [])
        rows = {r['dispatch_id']: r for r in self.q.load_dispatches(self.path)}
        self.assertEqual(rows[bad['dispatch_id']]['status'], 'blocked')
        self.assertIn('missing_port_or_text', rows[bad['dispatch_id']]['last_error'])

    def test_live_worker_calls_completion_after_successful_send(self):
        worker = load_module('whatsapp_dispatch_worker')
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        owned = self.q.enqueue_dispatch(origin='agenda', to='5511988888804', nature='agenda_reminder',
                                        owner_uid='breno', port=4605, text='worker novo', path=self.path, now=t0,
                                        execution_mode='worker_owned', completion_type='agenda_queue', agenda_queue_key='agenda-x')
        completed = []
        def fake_transport(row):
            return {'ok': True, 'messageId': 'WA-LIVE-2', 'status': 1}
        def fake_completion(row, resp):
            completed.append((row, resp))
            return {'ok': True, 'completed': True}
        result = worker.run_once(path=self.path, dry_run=False, max_simultaneous=10, now=t0,
                                 transport=fake_transport, completion_callback=fake_completion)
        self.assertEqual(result['sent'], 1)
        self.assertEqual(result['completed'], 1)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0][0]['dispatch_id'], owned['dispatch_id'])
        self.assertEqual(completed[0][1]['messageId'], 'WA-LIVE-2')

    def test_live_worker_tries_alternate_jid_when_primary_fails(self):
        worker = load_module('whatsapp_dispatch_worker')
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        self.q.enqueue_dispatch(origin='nao_mql', to='5511987654321@s.whatsapp.net', nature='non_mql_outreach',
                                owner_uid='Lucas Resende', port=4606, text='nao mql', path=self.path, now=t0,
                                execution_mode='worker_owned', completion_type='non_mql', alternate_jids=['551187654321@s.whatsapp.net'])
        attempted = []
        def fake_transport(row):
            attempted.append(row['jid'])
            if len(attempted) == 1:
                return {'ok': False, 'error': 'not on whatsapp'}
            return {'ok': True, 'messageId': 'WA-ALT-OK', 'status': 1, 'to': row['jid']}
        result = worker.run_once(path=self.path, dry_run=False, max_simultaneous=10, now=t0,
                                 transport=fake_transport, completion_callback=lambda row, resp: {'ok': True})
        self.assertEqual(attempted, ['5511987654321@s.whatsapp.net', '551187654321@s.whatsapp.net'])
        self.assertEqual(result['sent'], 1)
        rows = self.q.load_dispatches(self.path)
        self.assertEqual(rows[0]['status'], 'sent')
        self.assertEqual(rows[0]['messageId'], 'WA-ALT-OK')

    def test_live_worker_sends_parts_in_order_for_sequence_dispatch(self):
        worker = load_module('whatsapp_dispatch_worker')
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        self.q.enqueue_dispatch(origin='followup', to='5511987654300@s.whatsapp.net', nature='followup_f2',
                                owner_uid='breno', port=4605, text='texto completo', path=self.path, now=t0,
                                execution_mode='worker_owned', completion_type='followup',
                                parts=['Bom dia', 'Contexto rápido', 'Faz sentido?'], delay_schedule=[0, 0])
        sent_parts = []
        def fake_transport(row):
            sent_parts.append(row.get('text'))
            return {'ok': True, 'messageId': f"WA-PART-{len(sent_parts)}", 'status': 1, 'to': row['jid']}
        result = worker.run_once(path=self.path, dry_run=False, max_simultaneous=10, now=t0,
                                 transport=fake_transport, completion_callback=lambda row, resp: {'ok': True})
        self.assertEqual(sent_parts, ['Bom dia', 'Contexto rápido', 'Faz sentido?'])
        self.assertEqual(result['sent'], 1)
        row = self.q.load_dispatches(self.path)[0]
        self.assertEqual(row['messageId'], 'WA-PART-3')
        self.assertEqual(row['bridge_response']['parts'], 3)
        self.assertEqual(row['bridge_response']['messageIds'], ['WA-PART-1', 'WA-PART-2', 'WA-PART-3'])

    def test_live_worker_sends_text_file_text_sequence_for_diagnostic_bundle(self):
        worker = load_module('whatsapp_dispatch_worker')
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        self.q.enqueue_dispatch(
            origin='diagnostico', to='5511999999999@s.whatsapp.net', nature='diagnostic_bundle',
            owner_uid='sarah', port=4601, text='texto inicial\nPDF\npergunta final', path=self.path, now=t0,
            execution_mode='worker_owned', completion_type='diagnostic_bundle',
            parts=[
                {'kind': 'text', 'text': 'texto inicial'},
                {'kind': 'file', 'filePath': '/tmp/diagnostico.pdf', 'fileName': 'Diagnostico.pdf', 'thumbnailPath': '/tmp/thumb.jpg'},
                {'kind': 'text', 'text': 'pergunta final'},
            ],
            delay_schedule=[0, 0],
        )
        calls = []
        completions = []
        def fake_transport(row):
            calls.append(dict(row))
            return {'ok': True, 'messageId': f"WA-DIAG-{len(calls)}", 'status': 1, 'to': row['jid'], 'kind': row.get('kind') or 'text'}
        def fake_completion(row, resp):
            completions.append((dict(row), dict(resp)))
            return {'ok': True, 'status': 'done'}
        result = worker.run_once(path=self.path, dry_run=False, max_simultaneous=1, now=t0,
                                 transport=fake_transport, completion_callback=fake_completion)
        self.assertEqual(result['sent'], 1)
        self.assertEqual([c.get('kind') or 'text' for c in calls], ['text', 'file', 'text'])
        self.assertEqual(calls[1]['filePath'], '/tmp/diagnostico.pdf')
        self.assertEqual(calls[1]['fileName'], 'Diagnostico.pdf')
        self.assertEqual(calls[1]['thumbnailPath'], '/tmp/thumb.jpg')
        self.assertEqual(completions[0][1]['messageIds'], ['WA-DIAG-1', 'WA-DIAG-2', 'WA-DIAG-3'])
        row = self.q.load_dispatches(self.path)[0]
        self.assertEqual(row['status'], 'sent')
        self.assertEqual(row['messageId'], 'WA-DIAG-3')


class PerChipScaleQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q = load_module('whatsapp_dispatch_queue')

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.path = Path(self._td.name) / 'whatsapp_dispatch_queue.json'

    def tearDown(self):
        self._td.cleanup()

    def _owned(self, **kw):
        base = dict(origin='followup', nature='followup_f1', owner_uid='breno',
                    text='oi', execution_mode='worker_owned', path=self.path)
        base.update(kw)
        return self.q.enqueue_dispatch(**base)

    def test_scale_config_defaults_flag_off_and_conservative(self):
        cfg = self.q.dispatch_scale_config(path=self.path / 'missing.json')
        self.assertFalse(cfg['per_chip_async_enabled'])
        self.assertTrue(cfg['dry_run'])
        self.assertEqual(cfg['per_chip_batch_size'], 1)
        self.assertGreaterEqual(cfg['max_attempts'], 1)

    def test_scale_config_overrides_and_coerces(self):
        cfg = self.q.dispatch_scale_config({'per_chip_async_enabled': True, 'per_chip_batch_size': 0,
                                            'per_chip_hourly_limit': '50', 'max_chips': '3'},
                                           path=self.path / 'missing.json')
        self.assertTrue(cfg['per_chip_async_enabled'])
        self.assertEqual(cfg['per_chip_batch_size'], 1)  # 0 vira 1 (conservador)
        self.assertEqual(cfg['per_chip_hourly_limit'], 50)
        self.assertEqual(cfg['max_chips'], 3)

    def test_per_chip_hourly_sent_count(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        rows = [
            {'status': 'sent', 'port': 4601, 'sent_at': t0.isoformat()},
            {'status': 'sent', 'port': 4601, 'sent_at': (t0 - timedelta(minutes=30)).isoformat()},
            {'status': 'sent', 'port': 4601, 'sent_at': (t0 - timedelta(hours=2)).isoformat()},  # fora da janela
            {'status': 'sent', 'port': 4602, 'sent_at': t0.isoformat()},
            {'status': 'queued', 'port': 4601},
        ]
        counts = self.q.per_chip_hourly_sent_count(rows, now=t0, window_seconds=3600)
        self.assertEqual(counts['4601'], 2)
        self.assertEqual(counts['4602'], 1)

    def test_chip_lock_metrics_counts_locked_and_sent_per_chip(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        self._owned(to='5511900000001', port=4601, now=t0)
        self._owned(to='5511900000002', port=4601, now=t0, nature='followup_f2')
        self._owned(to='5511900000003', port=4602, now=t0)
        batch = self.q.acquire_chip_batch(path=self.path, port=4601, max_per_chip=5,
                                          execution_modes=['worker_owned'], now=t0)
        self.assertEqual(len(batch), 2)
        m = self.q.chip_lock_metrics(path=self.path, now=t0)
        self.assertEqual(m['byChip']['4601']['locked'], 2)
        self.assertEqual(m['byChip']['4602']['queued'], 1)
        self.assertEqual(m['lockedTotal'], 2)

    def test_acquire_chip_batch_groups_many_per_chip_without_blocking_others(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        # Chip 4601 tem 3 leads; chip 4602 tem 1. Lote por-chip pega vários do 4601
        # e ainda serve o 4602 no mesmo lote.
        for i in range(3):
            self._owned(to=f'551190000010{i}', port=4601, now=t0, nature=f'followup_f{i+1}')
        self._owned(to='5511900000200', port=4602, now=t0)
        batch = self.q.acquire_chip_batch(path=self.path, max_per_chip=5,
                                          execution_modes=['worker_owned'], locked_by='w1', now=t0)
        by_port = {}
        for r in batch:
            by_port.setdefault(str(r['port']), 0)
            by_port[str(r['port'])] += 1
        self.assertEqual(by_port['4601'], 3)
        self.assertEqual(by_port['4602'], 1)
        self.assertTrue(all(r['status'] == 'locked' for r in batch))

    def test_acquire_chip_batch_respects_per_chip_hourly_limit(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        # 1 envio já saiu na última hora nesse chip; limite 2 => só sobra 1 de headroom.
        sent = self._owned(to='5511900000300', port=4601, now=t0 - timedelta(minutes=10))
        self.q.mark_dispatch_status(sent['dispatch_id'], 'sent', path=self.path, now=t0 - timedelta(minutes=10))
        for i in range(3):
            self._owned(to=f'551190000031{i}', port=4601, now=t0, nature=f'followup_f{i+1}')
        batch = self.q.acquire_chip_batch(path=self.path, max_per_chip=5, per_chip_hourly_limit=2,
                                          execution_modes=['worker_owned'], now=t0)
        self.assertEqual(len(batch), 1)  # 2 - 1 já enviado = 1 de headroom

    def test_acquire_chip_batch_skips_attempts_exhausted(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        r = self._owned(to='5511900000400', port=4601, now=t0)
        # Simula item que já bateu no teto de tentativas.
        self.q.mark_dispatch_status(r['dispatch_id'], 'queued', path=self.path, now=t0, attempts=3)
        batch = self.q.acquire_chip_batch(path=self.path, max_per_chip=5, max_attempts=3,
                                          execution_modes=['worker_owned'], now=t0)
        self.assertEqual(batch, [])

    def test_schedule_retry_requeues_with_backoff_then_fails_when_exhausted(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        r = self._owned(to='5511900000500', port=4601, now=t0)
        did = r['dispatch_id']
        # attempts=1 após reservar.
        self.q.acquire_chip_batch(path=self.path, max_per_chip=1, execution_modes=['worker_owned'], now=t0)
        out1 = self.q.schedule_retry(did, path=self.path, now=t0, backoff_seconds=300, max_attempts=3, last_error='timeout')
        self.assertTrue(out1['retried'])
        row = [x for x in self.q.load_dispatches(self.path) if x['dispatch_id'] == did][0]
        self.assertEqual(row['status'], 'queued')
        self.assertIsNone(row['locked_by'])
        self.assertIsNotNone(row['scheduled_at'])
        # Backoff no futuro: não sai de novo no mesmo instante.
        self.assertEqual(self.q.acquire_chip_batch(path=self.path, execution_modes=['worker_owned'], now=t0), [])
        # Simula esgotar tentativas.
        self.q.mark_dispatch_status(did, 'locked', path=self.path, now=t0, attempts=3)
        out2 = self.q.schedule_retry(did, path=self.path, now=t0, max_attempts=3, last_error='timeout')
        self.assertFalse(out2['retried'])
        row = [x for x in self.q.load_dispatches(self.path) if x['dispatch_id'] == did][0]
        self.assertEqual(row['status'], 'failed')
        self.assertTrue(row.get('retry_exhausted'))

    def test_schedule_retry_never_touches_sent(self):
        r = self._owned(to='5511900000600', port=4601)
        did = r['dispatch_id']
        self.q.mark_dispatch_status(did, 'sent', path=self.path)
        out = self.q.schedule_retry(did, path=self.path, max_attempts=3)
        self.assertFalse(out['retried'])
        self.assertEqual(out['status'], 'sent')
        row = [x for x in self.q.load_dispatches(self.path) if x['dispatch_id'] == did][0]
        self.assertEqual(row['status'], 'sent')


class PerChipWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q = load_module('whatsapp_dispatch_queue')
        cls.worker = load_module('whatsapp_dispatch_worker')

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.path = Path(self._td.name) / 'whatsapp_dispatch_queue.json'

    def tearDown(self):
        self._td.cleanup()

    def _owned(self, **kw):
        base = dict(origin='followup', nature='followup_f1', owner_uid='breno',
                    text='oi', execution_mode='worker_owned', path=self.path)
        base.update(kw)
        return self.q.enqueue_dispatch(**base)

    def test_per_chip_disabled_falls_back_to_shadow_and_never_sends(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        self._owned(to='5511900001001', port=4601, now=t0)
        calls = []
        cfg = self.q.dispatch_scale_config({'per_chip_async_enabled': False}, path=self.path / 'x.json')
        out = self.worker.run_per_chip_once(path=self.path, config=cfg, now=t0,
                                            transport=lambda r: calls.append(r))
        self.assertEqual(calls, [])
        self.assertEqual(out['mode'], 'dry_run')
        self.assertFalse(out['perChip']['enabled'])
        rows = self.q.load_dispatches(self.path)
        self.assertEqual({r['status'] for r in rows}, {'queued'})

    def test_per_chip_enabled_live_sends_multiple_per_chip_without_duplicates(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        for i in range(3):
            self._owned(to=f'551190000200{i}', port=4601, now=t0, nature=f'followup_f{i+1}')
        self._owned(to='5511900002100', port=4602, now=t0)
        cfg = self.q.dispatch_scale_config({'per_chip_async_enabled': True, 'dry_run': False,
                                           'per_chip_batch_size': 5}, path=self.path / 'x.json')
        sent = []
        def fake_transport(row):
            sent.append(row['jid'])
            return {'ok': True, 'messageId': f'WA-{len(sent)}', 'status': 1, 'to': row['jid']}
        out = self.worker.run_per_chip_once(path=self.path, config=cfg, now=t0,
                                            transport=fake_transport,
                                            completion_callback=lambda r, resp: {'ok': True})
        self.assertEqual(out['mode'], 'per_chip_live')
        self.assertEqual(out['sent'], 4)
        # Nenhum destino recebeu duas vezes.
        self.assertEqual(len(sent), len(set(sent)))
        self.assertEqual(out['byChip']['4601']['sent'], 3)
        self.assertEqual(out['byChip']['4602']['sent'], 1)

    def test_per_chip_enabled_retries_failure_without_duplicate_send(self):
        t0 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        self._owned(to='5511900003000', port=4601, now=t0)
        cfg = self.q.dispatch_scale_config({'per_chip_async_enabled': True, 'dry_run': False,
                                           'per_chip_batch_size': 5, 'max_attempts': 3,
                                           'retry_backoff_seconds': 300}, path=self.path / 'x.json')
        calls = []
        def failing_transport(row):
            calls.append(row['jid'])
            return {'ok': False, 'error': 'bridge_timeout'}
        out = self.worker.run_per_chip_once(path=self.path, config=cfg, now=t0,
                                            transport=failing_transport,
                                            completion_callback=lambda r, resp: {'ok': True})
        self.assertEqual(out['sent'], 0)
        self.assertEqual(out['retried'], 1)
        self.assertEqual(out['failed'], 0)  # ainda há tentativa => requeue, não falha
        self.assertEqual(len(calls), 1)  # só uma tentativa de envio nesta execução
        row = self.q.load_dispatches(self.path)[0]
        self.assertEqual(row['status'], 'queued')  # de volta à fila para nova tentativa
        self.assertIsNotNone(row['scheduled_at'])


if __name__ == '__main__':
    unittest.main()
