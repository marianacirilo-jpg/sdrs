import importlib.util
import json
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


class ChipOperatorLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_module('whatsapp_chip_operator_learning')

    def setUp(self):
        self.now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)

    # ------------------------------------------------------------------ #
    # Classificação de eventos
    # ------------------------------------------------------------------ #
    def test_classify_ledger_outcome_sent_failed_and_neutral(self):
        m = self.m
        self.assertEqual(m.classify_ledger_outcome({'status': 'enviado_lead'}), 'sent')
        self.assertEqual(m.classify_ledger_outcome({'status': 'agenda_followup_done'}), 'sent')
        self.assertEqual(m.classify_ledger_outcome({'send_response': {'status': 1, 'messageId': 'X'}}), 'sent')
        self.assertEqual(m.classify_ledger_outcome({'send_error': 'not on whatsapp'}), 'failed')
        self.assertEqual(m.classify_ledger_outcome({'status': 'telefone_invalido'}), 'failed')
        # neutros: duplicata apagada, substituído, em andamento, sem sinal
        self.assertIsNone(m.classify_ledger_outcome({'status': 'deleted_whatsapp_duplicate'}))
        self.assertIsNone(m.classify_ledger_outcome({'status': 'mql_diagnostico_em_andamento'}))
        self.assertIsNone(m.classify_ledger_outcome({'status': None}))

    def test_reply_evidence_detection(self):
        m = self.m
        self.assertTrue(m.has_reply_evidence({'lead_reply': True}))
        self.assertTrue(m.has_reply_evidence({'reply_at': '2026-07-01T10:00:00-03:00'}))
        self.assertTrue(m.has_reply_evidence({'status': 'enviado_resposta_provavel_mql'}))
        self.assertFalse(m.has_reply_evidence({'status': 'enviado_lead'}))

    # ------------------------------------------------------------------ #
    # Score puro
    # ------------------------------------------------------------------ #
    def test_health_score_is_pure_and_bounded(self):
        m = self.m
        # sem histórico terminal => neutro
        self.assertEqual(m.chip_health_score({}), m.NEUTRAL_SCORE)
        # tudo enviado => alto
        healthy = m.chip_health_score({'sent': 10})
        self.assertGreaterEqual(healthy, 90.0)
        # tudo falho => baixo
        bad = m.chip_health_score({'sent': 0, 'failed': 10})
        self.assertEqual(bad, 0.0)
        # locks presos penalizam
        stale = m.chip_health_score({'sent': 10, 'stale': 3})
        self.assertLess(stale, healthy)
        # determinístico
        self.assertEqual(m.chip_health_score({'sent': 7, 'failed': 3}),
                         m.chip_health_score({'sent': 7, 'failed': 3}))

    def test_reply_bonus_raises_score(self):
        m = self.m
        # com headroom (nem tudo perfeito) o bônus de resposta aparece
        base = m.chip_health_score({'sent': 8, 'failed': 2})
        with_reply = m.chip_health_score({'sent': 8, 'failed': 2, 'replies': 8})
        self.assertGreater(with_reply, base)
        self.assertLessEqual(with_reply, 100.0)

    # ------------------------------------------------------------------ #
    # Agregação do snapshot
    # ------------------------------------------------------------------ #
    def test_snapshot_aggregates_by_chip_owner_origin_nature(self):
        m = self.m
        ledger = [
            {'status': 'enviado_lead', 'bridge_port': 4603, 'owner_sdr': 'Sarah',
             'origin': 'cron_mql_diagnostic_pipeline', 'nature': 'diagnostic_bundle',
             'date_tz': '2026-07-01T08:00:00-03:00', 'logical_message_id': 'lm1'},
            {'status': 'enviado_lead', 'bridge_port': 4603, 'owner_sdr': 'Sarah',
             'origin': 'cron_mql_diagnostic_pipeline', 'nature': 'diagnostic_bundle',
             'date_tz': '2026-07-01T09:00:00-03:00', 'logical_message_id': 'lm2',
             'status_reply': None, 'lead_reply': True},
            {'send_error': 'not on whatsapp', 'bridge_port': 4603, 'owner_sdr': 'Sarah',
             'origin': 'cron_cadencia_primeiro_contato', 'nature': 'followup_f2',
             'date_tz': '2026-07-01T09:30:00-03:00'},
        ]
        snap = m.build_learning_snapshot(ledger_rows=ledger, dispatch_rows=[], now=self.now)
        chip = snap['chips']['4603']
        self.assertEqual(chip['sent'], 2)
        self.assertEqual(chip['failed'], 1)
        self.assertEqual(chip['replies'], 1)
        self.assertEqual(chip['attempts'], 3)
        self.assertAlmostEqual(chip['successRate'], round(2 / 3, 4))
        self.assertEqual(chip['port'], 4603)
        self.assertIn('sarah', chip['owners'])
        self.assertEqual(chip['byNature']['diagnostic_bundle']['sent'], 2)
        self.assertEqual(chip['byOrigin']['cron_cadencia_primeiro_contato']['failed'], 1)
        self.assertEqual(chip['lastSentAt'], '2026-07-01T12:00:00+00:00')  # 09:00 BRT
        # operador
        op = snap['operators']['sarah']
        self.assertEqual(op['sent'], 2)
        self.assertEqual(op['displayName'], 'Sarah')
        self.assertEqual(op['ports'], ['4603'])
        # totais
        self.assertEqual(snap['totals']['sent'], 2)
        self.assertEqual(snap['totals']['failed'], 1)

    def test_snapshot_dedupes_same_logical_message_across_sources(self):
        m = self.m
        ledger = [{'status': 'enviado_lead', 'bridge_port': 4601, 'owner_sdr': 'breno',
                   'origin': 'x', 'nature': 'first_contact', 'date_tz': '2026-07-01T08:00:00-03:00',
                   'logical_message_id': 'shared-1'}]
        queue = [{'status': 'sent', 'port': 4601, 'owner_uid': 'breno', 'origin': 'x',
                  'nature': 'first_contact', 'sent_at': '2026-07-01T11:05:00+00:00',
                  'logical_message_id': 'shared-1'}]
        snap = m.build_learning_snapshot(ledger_rows=ledger, dispatch_rows=queue, now=self.now)
        # mesmo envio lógico nas duas fontes => conta 1
        self.assertEqual(snap['chips']['4601']['sent'], 1)

    def test_snapshot_detects_locked_and_stale_from_queue(self):
        m = self.m
        queue = [
            {'status': 'locked', 'port': 4605, 'owner_uid': 'lucas', 'origin': 'followup',
             'nature': 'followup_f1', 'locked_at': '2026-07-01T11:59:00+00:00',
             'updated_at': '2026-07-01T11:59:00+00:00'},  # 1 min atrás: locked, não stale
            {'status': 'locked', 'port': 4605, 'owner_uid': 'lucas', 'origin': 'followup',
             'nature': 'followup_f1', 'locked_at': '2026-07-01T11:00:00+00:00',
             'updated_at': '2026-07-01T11:00:00+00:00'},  # 60 min atrás: stale
        ]
        snap = m.build_learning_snapshot(ledger_rows=[], dispatch_rows=queue, now=self.now,
                                         stale_seconds=15 * 60)
        chip = snap['chips']['4605']
        self.assertEqual(chip['locked'], 2)
        self.assertEqual(chip['stale'], 1)
        self.assertEqual(chip['lastError'], 'stale_lock')

    def test_snapshot_is_idempotent_for_same_inputs(self):
        m = self.m
        ledger = [{'status': 'enviado_lead', 'bridge_port': 4600, 'owner_sdr': 'Sarah',
                   'origin': 'o', 'nature': 'n', 'date_tz': '2026-07-01T08:00:00-03:00'}]
        a = m.build_learning_snapshot(ledger_rows=ledger, dispatch_rows=[], now=self.now,
                                      generated_at='fixed')
        b = m.build_learning_snapshot(ledger_rows=list(ledger), dispatch_rows=[], now=self.now,
                                      generated_at='fixed')
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_write_snapshot_creates_file_and_reloads(self):
        m = self.m
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'chip_operator_learning.json'
            ledger = [{'status': 'enviado_lead', 'bridge_port': 4609, 'owner_sdr': 'Sarah',
                       'origin': 'o', 'nature': 'n', 'date_tz': '2026-07-01T08:00:00-03:00'}]
            snap = m.write_learning_snapshot(path=path, ledger_rows=ledger, dispatch_rows=[], now=self.now)
            self.assertTrue(path.exists())
            reloaded = m.load_learning_snapshot(path)
            self.assertEqual(reloaded['chips']['4609']['sent'], 1)
            self.assertEqual(reloaded['version'], snap['version'])

    def test_since_days_filters_old_events(self):
        m = self.m
        ledger = [
            {'status': 'enviado_lead', 'bridge_port': 4610, 'owner_sdr': 'Sarah', 'origin': 'o',
             'nature': 'n', 'date_tz': '2026-06-01T08:00:00-03:00'},  # 30 dias atrás
            {'status': 'enviado_lead', 'bridge_port': 4610, 'owner_sdr': 'Sarah', 'origin': 'o',
             'nature': 'n', 'date_tz': '2026-06-30T08:00:00-03:00'},  # recente
        ]
        snap = m.build_learning_snapshot(ledger_rows=ledger, dispatch_rows=[], now=self.now, since_days=7)
        self.assertEqual(snap['chips']['4610']['sent'], 1)

    # ------------------------------------------------------------------ #
    # Consulta do roteador (não liga envio)
    # ------------------------------------------------------------------ #
    def test_router_prefers_healthy_chip_and_includes_unknown_candidate(self):
        m = self.m
        ledger = (
            [{'status': 'enviado_lead', 'bridge_port': 4601, 'owner_sdr': 's', 'origin': 'o',
              'nature': 'n', 'date_tz': '2026-07-01T08:00:00-03:00'} for _ in range(10)]
            + [{'send_error': 'x', 'bridge_port': 4602, 'owner_sdr': 's', 'origin': 'o',
                'nature': 'n', 'date_tz': '2026-07-01T08:00:00-03:00'} for _ in range(10)]
        )
        snap = m.build_learning_snapshot(ledger_rows=ledger, dispatch_rows=[], now=self.now)
        ranked = m.rank_healthy_chips(snap, candidate_ports=[4601, 4602, 4699])
        ports = [r['port'] for r in ranked]
        # chip saudável primeiro, desconhecido neutro no meio, insalubre por último
        self.assertEqual(ports[0], 4601)
        self.assertEqual(ports[-1], 4602)
        self.assertIn(4699, ports)
        unknown = next(r for r in ranked if r['port'] == 4699)
        self.assertIsNone(unknown['healthy'])
        self.assertFalse(unknown['known'])
        self.assertEqual(m.prefer_healthy_chip(snap, candidate_ports=[4602, 4601]), 4601)

    def test_router_returns_none_when_no_candidates_and_empty_snapshot(self):
        m = self.m
        snap = m.build_learning_snapshot(ledger_rows=[], dispatch_rows=[], now=self.now)
        self.assertIsNone(m.prefer_healthy_chip(snap, candidate_ports=[]))


if __name__ == '__main__':
    unittest.main()
