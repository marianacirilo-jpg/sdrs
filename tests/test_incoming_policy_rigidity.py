#!/usr/bin/env python3
"""Trava de rigidez da política de incoming.

Garante que textos, classificações e razões de decisão estão fixos na política
única (FIXED_*) e que as regras-chave do incoming não regridem:
preço -> R$597, Uberlândia, pergunta de segmento, agradecimento pausa,
ligação não auto-responde. Também valida que prior_non_mql_action_for_lead
não usa row de grupo (`nao_mql_grupo`) como referência de chip original.
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS_PROSP = Path('/root/.hermes/zydon-prospeccao/scripts')
INCOMING_PATH = Path('/root/.hermes/scripts/zydon_incoming_response_alert.py')
GATE_PATH = SCRIPTS_PROSP / 'process_gate_once.py'

# whatsapp_safe_send é importado pelo incoming no nível de módulo.
sys.path.insert(0, str(SCRIPTS_PROSP))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


incoming = _load('zydon_incoming_response_alert', INCOMING_PATH)


class IncomingPolicyTest(unittest.TestCase):
    def test_preco_usa_template_fixo(self):
        reply, reason = incoming.safe_auto_reply_for_legit_non_mql('Quanto custa?')
        self.assertEqual(reason, 'preco_base_597_consultor')
        self.assertIn('R$597,00 por mês', reply)
        self.assertEqual(reply, incoming.FIXED_REPLY_TEMPLATES['preco_base_597_consultor'])

    def test_localizacao_uberlandia(self):
        reply, reason = incoming.safe_auto_reply_for_legit_non_mql(
            'Boa noite, sua empresa é de Uberlândia mg')
        self.assertEqual(reason, 'responde_localizacao_uberlandia')
        self.assertEqual(reply, incoming.FIXED_REPLY_TEMPLATES['responde_localizacao_uberlandia'])

    def test_pergunta_segmento_para_case(self):
        reply, reason = incoming.safe_auto_reply_for_legit_non_mql(
            'Vc tem algum cliente no nosso Segmento?')
        self.assertEqual(reason, 'pergunta_segmento_para_case')
        self.assertEqual(reply, incoming.FIXED_REPLY_TEMPLATES['pergunta_segmento_para_case'])

    def test_agradecimento_classifica_encerramento(self):
        cls = incoming.classification('obrigado')
        self.assertEqual(cls, incoming.FIXED_CLASSIFICATIONS['agradecimento'])
        self.assertTrue(incoming.is_closure_ack('obrigado'))

    def test_ligacao_nao_auto_responde(self):
        reply, reason = incoming.safe_auto_reply_for_legit_non_mql('pode ligar?')
        self.assertIsNone(reply)
        self.assertEqual(reason, 'exige_humano_ligacao_agenda_ou_juridico')

    def test_negativo_e_agressivo_travam(self):
        self.assertIsNone(incoming.safe_auto_reply_for_legit_non_mql('não tenho interesse')[0])
        self.assertIsNone(incoming.safe_auto_reply_for_legit_non_mql('isso é golpe')[0])

    def test_toda_razao_pertence_a_policy(self):
        # Qualquer reason devolvido tem que estar na política fixa.
        amostras = [
            'Quanto custa?', 'pode ligar?', 'sua empresa é de Uberlândia',
            'Vc tem cliente no nosso segmento?', 'somos uma indústria com site b2b',
            'queria informações sobre capilaridade e representantes',
            'não tenho interesse', 'isso é golpe', '', 'oi tudo bem',
        ]
        for txt in amostras:
            _, reason = incoming.safe_auto_reply_for_legit_non_mql(txt)
            self.assertIn(reason, incoming.FIXED_DECISION_REASONS, msg=f'reason fora da policy: {reason!r} para {txt!r}')

    def test_policy_version_presente(self):
        self.assertTrue(getattr(incoming, 'INCOMING_POLICY_VERSION', ''))

    def test_listener_usa_escopo_central_de_conversa(self):
        self.assertTrue(hasattr(incoming, 'should_listen_to_incoming'))
        src = INCOMING_PATH.read_text(encoding='utf-8')
        self.assertIn('should_listen_to_incoming', src)
        self.assertIn('scope_decision', src)


class PriorNonMqlChipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = _load('process_gate_once_for_test', GATE_PATH)

    def test_row_de_grupo_nao_vira_chip_original(self):
        envios = [{
            'email': 'lead@empresa.com', 'status': 'nao_mql_grupo',
            'to': '120363408131718880@g.us', 'bridge_port': 4600,
        }]
        prior = self.gate.prior_non_mql_action_for_lead(envios, email='lead@empresa.com')
        self.assertIsNone(prior, 'row de grupo nao_mql_grupo não pode ser referência de chip')

    def test_tratativa_externa_real_eh_aceita(self):
        envios = [{
            'email': 'lead@empresa.com', 'status': 'enviado_nao_mql_legitimo',
            'to': '553499999999@s.whatsapp.net', 'bridge_port': 4603,
        }]
        prior = self.gate.prior_non_mql_action_for_lead(envios, email='lead@empresa.com')
        self.assertIsNotNone(prior)
        self.assertEqual(prior.get('bridge_port'), 4603)


class IncomingCrmEffectivenessTest(unittest.TestCase):
    def test_efetivo_false_para_fracas_sem_texto_e_negativa(self):
        for txt in ['obrigado', 'ok', '(sem texto extraído)', 'não tenho interesse']:
            cls = incoming.classification(txt)
            self.assertFalse(
                incoming.is_effective_for_crm(txt, cls),
                msg=f'esperava NÃO efetivo para {txt!r}')

    def test_agent_conduz_intencao_simples_sem_task_humana(self):
        for txt in ['quanto custa?', 'faz sentido',
                    'vocês têm algum cliente no nosso segmento?',
                    'somos uma indústria com site b2b']:
            cls = incoming.classification(txt)
            self.assertFalse(
                incoming.is_effective_for_crm(txt, cls),
                msg=f'agente deve conduzir sem task humana para {txt!r}')

    def test_handoff_claro_continua_gerando_task_humana(self):
        for txt in ['pode ligar?', 'vamos marcar uma reunião', 'me manda uma proposta']:
            cls = incoming.classification(txt)
            self.assertTrue(
                incoming.is_effective_for_crm(txt, cls),
                msg=f'esperava task humana para {txt!r}')

    def test_legit_non_mql_vira_followthrough_do_agente_sem_task_automatica(self):
        txt = 'Desejo informações'
        cls = incoming.classification(txt)
        self.assertFalse(incoming.is_effective_for_crm(txt, cls, is_legit_non_mql=True))
        follow = incoming.classify_followthrough(txt)
        self.assertFalse(follow['escalate'])
        self.assertEqual(follow['next_state'], 'pending_agent_followthrough')
        # mas continua False quando é fraca pura ou negativa, mesmo legítimo
        self.assertFalse(incoming.is_effective_for_crm('ok', incoming.classification('ok'), is_legit_non_mql=True))
        self.assertFalse(incoming.is_effective_for_crm('não tenho interesse',
                                                       incoming.classification('não tenho interesse'),
                                                       is_legit_non_mql=True))


class IncomingSlaTest(unittest.TestCase):
    def test_manha_vira_14h_mesmo_dia(self):
        in_dt = datetime(2026, 6, 30, 13, 0, tzinfo=timezone.utc)  # 10h BRT, terça
        due = incoming.next_sdr_due_for_incoming(in_dt).astimezone(incoming.BRT)
        self.assertEqual((due.day, due.month, due.hour), (30, 6, 14))

    def test_tarde_vira_9h_proximo_dia_util(self):
        in_dt = datetime(2026, 6, 30, 18, 0, tzinfo=timezone.utc)  # 15h BRT, terça
        due = incoming.next_sdr_due_for_incoming(in_dt).astimezone(incoming.BRT)
        self.assertEqual((due.day, due.month, due.hour), (1, 7, 9))  # quarta 9h

    def test_fim_de_semana_vai_para_segunda(self):
        in_dt = datetime(2026, 7, 4, 13, 0, tzinfo=timezone.utc)  # sábado 10h BRT
        due = incoming.next_sdr_due_for_incoming(in_dt).astimezone(incoming.BRT)
        self.assertEqual(due.weekday(), 0)  # segunda-feira
        self.assertEqual(due.hour, 9)


class IncomingCrmTaskTest(unittest.TestCase):
    def test_skipped_missing_ids_nao_chama_hubspot(self):
        calls = []
        orig = incoming.hubspot_request
        incoming.hubspot_request = lambda *a, **k: (calls.append((a, k)), {})[1]
        try:
            res = incoming.move_to_retorno_and_create_task(
                {'contact_id': '123'},  # falta deal_id e owner_id
                4601, '553499999999@s.whatsapp.net', 'quanto custa?',
                datetime(2026, 6, 30, 13, 0, tzinfo=timezone.utc),
                incoming.classification('quanto custa?'))
        finally:
            incoming.hubspot_request = orig
        self.assertEqual(res.get('status'), 'skipped_missing_ids')
        self.assertEqual(calls, [], 'não pode tocar no HubSpot sem IDs')

    def test_move_completo_em_memoria(self):
        calls = []

        def fake(method, path, body=None):
            calls.append((method, path))
            if method == 'GET':
                return {'properties': {'dealstage': incoming.STAGE_PRIMEIRO_CONTATO}}
            if str(path).endswith('/tasks'):
                return {'id': 'task_1'}
            return {'id': 'deal_ok'}

        orig = incoming.hubspot_request
        incoming.hubspot_request = fake
        try:
            res = incoming.move_to_retorno_and_create_task(
                {'deal_id': '555', 'contact_id': '123', 'owner_id': '77',
                 'empresa': 'ACME', 'contato': 'João'},
                4601, '553499999999@s.whatsapp.net', 'quanto custa?',
                datetime(2026, 6, 30, 13, 0, tzinfo=timezone.utc),
                incoming.classification('quanto custa?'))
        finally:
            incoming.hubspot_request = orig
        self.assertEqual(res.get('status'), 'moved_and_task_created')
        self.assertEqual(res.get('task_id'), 'task_1')
        self.assertTrue(any(m == 'GET' for m, _ in calls), 'deve consultar etapa atual antes')
        self.assertTrue(any(m == 'PATCH' for m, _ in calls), 'deve mover etapa via PATCH')
        self.assertTrue(any(p.endswith('/tasks') for _, p in calls), 'deve criar tarefa')

    def test_nao_regrede_deal_em_etapa_avancada(self):
        calls = []

        def fake(method, path, body=None):
            calls.append((method, path))
            return {'properties': {'dealstage': '1151853491'}}  # Diagnóstico SDR

        orig = incoming.hubspot_request
        incoming.hubspot_request = fake
        try:
            res = incoming.move_to_retorno_and_create_task(
                {'deal_id': '555', 'contact_id': '123', 'owner_id': '77'},
                4601, '553499999999@s.whatsapp.net', 'quanto custa?',
                datetime(2026, 6, 30, 13, 0, tzinfo=timezone.utc),
                incoming.classification('quanto custa?'))
        finally:
            incoming.hubspot_request = orig
        self.assertEqual(res.get('status'), 'skipped_stage_not_initial')
        self.assertTrue(any(m == 'GET' for m, _ in calls))
        self.assertFalse(any(m == 'PATCH' for m, _ in calls), 'não pode regredir etapa avançada')
        self.assertFalse(any(str(p).endswith('/tasks') for _, p in calls), 'não deve criar task se pulou por etapa')
    def test_nao_move_quando_etapa_atual_nao_veio(self):
        calls = []

        def fake(method, path, body=None):
            calls.append((method, path))
            return {'properties': {}}

        orig = incoming.hubspot_request
        incoming.hubspot_request = fake
        try:
            res = incoming.move_to_retorno_and_create_task(
                {'deal_id': '555', 'contact_id': '123', 'owner_id': '77'},
                4601, '553499999999@s.whatsapp.net', 'quanto custa?',
                datetime(2026, 6, 30, 13, 0, tzinfo=timezone.utc),
                incoming.classification('quanto custa?'))
        finally:
            incoming.hubspot_request = orig
        self.assertEqual(res.get('status'), 'skipped_stage_unknown')
        self.assertTrue(any(m == 'GET' for m, _ in calls))
        self.assertFalse(any(m == 'PATCH' for m, _ in calls))
        self.assertFalse(any(str(p).endswith('/tasks') for _, p in calls))


class IncomingMetaMergeTest(unittest.TestCase):
    def test_meta_merge_nao_apaga_ids_com_linha_nova_incompleta(self):
        meta_by_port = {4601: {}}
        variants = {'553499999999@s.whatsapp.net'}
        incoming._index_ledger_meta(meta_by_port, 4601, variants, {
            'deal_id': '555', 'contact_id': '123', 'owner_id': '77',
            'email': 'lead@empresa.com', 'to': '553499999999@s.whatsapp.net',
        })
        incoming._index_ledger_meta(meta_by_port, 4601, variants, {
            'email': 'lead@empresa.com', 'to': '553499999999@s.whatsapp.net',
            'empresa': 'ACME',
        })
        meta = meta_by_port[4601]['553499999999@s.whatsapp.net']
        self.assertEqual(meta.get('deal_id'), '555')
        self.assertEqual(meta.get('contact_id'), '123')
        self.assertEqual(meta.get('owner_id'), '77')
        self.assertEqual(meta.get('empresa'), 'ACME')


class IncomingMediaSemTextoTest(unittest.TestCase):
    def test_media_sem_texto_classifica_e_nao_e_efetivo(self):
        cls = incoming.classification('(sem texto extraído)')
        self.assertEqual(cls, incoming.FIXED_CLASSIFICATIONS['media_sem_texto'])
        # nunca tratada como retorno comercial efetivo, mesmo legítimo Não-MQL
        self.assertFalse(incoming.is_effective_for_crm('(sem texto extraído)', cls))
        self.assertFalse(
            incoming.is_effective_for_crm('(sem texto extraído)', cls, is_legit_non_mql=True))
        # vazio também é mídia sem texto
        self.assertEqual(incoming.classification(''),
                         incoming.FIXED_CLASSIFICATIONS['media_sem_texto'])

    def test_is_no_text_payload(self):
        self.assertTrue(incoming.is_no_text_payload(''))
        self.assertTrue(incoming.is_no_text_payload('   '))
        self.assertTrue(incoming.is_no_text_payload('(sem texto extraído)'))
        self.assertFalse(incoming.is_no_text_payload('oi'))

    def test_safe_auto_reply_para_media_sem_texto(self):
        reply, reason = incoming.safe_auto_reply_for_legit_non_mql('(sem texto extraído)')
        self.assertIsNone(reply)
        self.assertEqual(reason, 'sem_texto_extraido')


class IncomingHistoryHealthTest(unittest.TestCase):
    def test_missing_stale_ok_com_cooldown(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            orig = (incoming.WA, incoming.WATCH_PORTS, incoming.PORT_NAMES)
            incoming.WA = tmp
            incoming.WATCH_PORTS = {4600, 4601}
            incoming.PORT_NAMES = {4600: 'Mariana', 4601: 'Sarah'}
            try:
                now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
                fresh = tmp / 'history_4601.json'
                fresh.write_text('[]', encoding='utf-8')
                os.utime(fresh, (now.timestamp(), now.timestamp()))

                # 4600 ausente -> alerta; 4601 fresco -> sem alerta
                state = {}
                alerts = incoming.history_health_alerts(state, now=now)
                self.assertEqual(len(alerts), 1)
                self.assertIn('porta 4600', alerts[0])

                # cooldown de 60min: nova chamada imediata não realerta
                self.assertEqual(incoming.history_health_alerts(state, now=now), [])

                # 4601 fica stale (>15min) -> alerta
                old = now - timedelta(minutes=30)
                os.utime(fresh, (old.timestamp(), old.timestamp()))
                alerts2 = incoming.history_health_alerts(state, now=now)
                self.assertTrue(any('porta 4601' in a for a in alerts2))
                self.assertFalse(any('porta 4600' in a for a in alerts2))
            finally:
                incoming.WA, incoming.WATCH_PORTS, incoming.PORT_NAMES = orig


class IncomingGroupRateLimitTest(unittest.TestCase):
    def test_recent_apos_mark_e_expira_no_cooldown(self):
        state = {}
        now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
        key = '4600|553499999999@s.whatsapp.net|cls'
        self.assertFalse(incoming._wa_group_recent(state, key, now))
        incoming._wa_group_mark(state, key, now)
        self.assertTrue(incoming._wa_group_recent(state, key, now + timedelta(minutes=5)))
        # passado o cooldown de 15min, deixa de ser recente
        self.assertFalse(incoming._wa_group_recent(state, key, now + timedelta(minutes=20)))

    def test_reserved_state_keys_preservam_dedupes(self):
        for k in (incoming.CRM_DEDUPE_KEY, incoming.GROUP_ALERT_DEDUPE_KEY,
                  incoming.HEALTH_STATE_KEY):
            self.assertIn(k, incoming.RESERVED_STATE_KEYS)


if __name__ == '__main__':
    unittest.main()
