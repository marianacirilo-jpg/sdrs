# -*- coding: utf-8 -*-
"""Testes da normalização de faixas do formulário (cards do PDF) e da regra de
não repetir/colar o diagnóstico no follow-up de WhatsApp.

Cobre dois incidentes de produção (Policrom, 26/06):
  - card TIME TOTAL do PDF saía '1 a a a 10' (enum '1_a_10' mal normalizado);
  - follow-up SDR virava textão moroso reapresentando o diagnóstico.
"""
import importlib.util
import json
import os
import re
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')
MOTOR = os.path.join(ROOT, 'motor')
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, MOTOR)


def _load(mod_name, rel_path):
    spec = importlib.util.spec_from_file_location(mod_name, os.path.join(ROOT, rel_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pg = _load('process_gate_once', 'scripts/process_gate_once.py')
gate = _load('gate', 'motor/gate.py')
cad = _load('cadencia_primeiro_contato', 'scripts/cadencia_primeiro_contato.py')
gen = _load('gen', 'motor/gen.py')
batch_prepare = _load('batch_prepare', 'motor/batch_prepare.py')
non_mql = _load('non_mql_legit_outreach', 'scripts/non_mql_legit_outreach.py')
pending_watchdog = _load('pending_lead_watchdog', 'scripts/pending_lead_watchdog.py')
active_mql = _load('active_mql_qualifier', 'scripts/active_mql_qualifier.py')


def _sample_pdf_html(research, raw=None, empresa='Ceramica Ana Claudia', erp='Bling',
                     faturamento='de R$5 a R$10 milhões', pessoas='1_a_10'):
    """Monta o HTML do PDF como o generate_pdf faz: dict base + enriquecimento
    consultivo (segmento mapeado, história, referências) vindo da pesquisa."""
    d = batch_prepare.build_lead_dict({'name': 'Ana', 'empresa': empresa,
                                       'erp': erp, 'faturamento': faturamento})
    d['empresa'] = empresa
    seg, desc = pg.map_segmento_mapeado(research, raw)
    d['segmento_mapeado'] = seg
    d['segmento_desc'] = desc
    d['historia'] = pg.extract_historia(research)
    d['referencias'] = pg.build_referencias(research)
    d['time_total'] = pg.normalize_form_range(pessoas)
    return gen.build_html(d)

PERGUNTA_OFICIAL = 'Como você imagina que a Zydon poderia te apoiar?'


class TestContratoMqlDiagnosticoRigido(unittest.TestCase):
    """Textos/cadência do MQL são contrato fixo no código, não strings soltas."""

    def test_textos_e_tempos_fixos_do_diagnostico_mql(self):
        self.assertEqual(pg.TEXT_TO_PDF_DELAY_SECONDS, 60)
        self.assertEqual(pg.PDF_TO_QUESTION_DELAY_SECONDS, 30)
        self.assertEqual(pg.QUESTION_TO_AGENDA_DELAY_SECONDS, 20 * 60)
        self.assertEqual(
            pg.MQL_DIAGNOSTIC_TEXT_FIXED,
            'Fiz uma análise prévia do potencial da digitalização B2B do seu negócio.',
        )
        self.assertEqual(pg.sdr_opening_question(False), PERGUNTA_OFICIAL)
        self.assertEqual(pg.sdr_opening_question(True), PERGUNTA_OFICIAL)
        self.assertEqual(pg.MQL_INTENT_QUESTION_FIXED, PERGUNTA_OFICIAL)
        self.assertEqual(
            pg.MQL_AGENDA_PREFIX_FIXED,
            'Se quiser garantir o melhor horário para um diagnóstico completo, pode marcar direto aqui:',
        )

    def test_fluxo_usa_constantes_oficiais_sem_repetir_texto_solto(self):
        src = Path(SCRIPTS, 'process_gate_once.py').read_text(encoding='utf-8')
        # A frase aprovada só pode existir na definição da constante; o envio usa a constante.
        self.assertEqual(src.count('Fiz uma análise prévia do potencial da digitalização B2B do seu negócio.'), 1)
        self.assertIn('f"{MQL_DIAGNOSTIC_TEXT_FIXED}"', src)
        self.assertIn('return MQL_INTENT_QUESTION_FIXED', src)
        self.assertIn('f"{MQL_AGENDA_PREFIX_FIXED} {agenda}"', src)


def _alta_consciencia_html(empresa='Distribuidora Comparato'):
    """HTML do PDF para um lead de alta consciência (criativo Papel Rasgar/
    Comparativo): mesma base do diagnóstico, com a flag alta_consciencia ligada,
    que adiciona a página de fundação B2B vs B2C adaptado."""
    d = batch_prepare.build_lead_dict({'name': 'Carlos', 'empresa': empresa,
                                       'erp': 'Bling', 'faturamento': 'de R$5 a R$10 milhões'})
    d['empresa'] = empresa
    d['alta_consciencia'] = True
    return gen.build_html(d)


class TestNormalizeFormRange(unittest.TestCase):
    def test_enum_basico_nao_vira_a_a_a(self):
        # Bug original: '1_a_10'.replace('_', ' a ') == '1 a a a 10'
        self.assertEqual(pg.normalize_form_range('1_a_10'), '1 a 10')
        self.assertNotIn('a a', pg.normalize_form_range('1_a_10'))

    def test_outras_faixas_do_formulario(self):
        casos = {
            '11_a_25': '11 a 25',
            '26_a_50': '26 a 50',
            '51_a_100': '51 a 100',
            '101_a_150': '101 a 150',
            '21_a_100_': '21 a 100',  # enum com underscore sobrando
        }
        for raw, esperado in casos.items():
            self.assertEqual(pg.normalize_form_range(raw), esperado, raw)
            self.assertNotIn('a a', pg.normalize_form_range(raw), raw)

    def test_valores_sem_faixa_passam_intactos(self):
        self.assertEqual(pg.normalize_form_range('+151'), '+151')
        self.assertEqual(pg.normalize_form_range('10 a 20 pessoas'), '10 a 20 pessoas')
        self.assertEqual(pg.normalize_form_range(''), '')
        self.assertEqual(pg.normalize_form_range(None), '')

    def test_idempotente(self):
        once = pg.normalize_form_range('1_a_10')
        self.assertEqual(pg.normalize_form_range(once), once)


class TestDiagnosticoWorkerOwnedProducer(unittest.TestCase):
    def test_resolve_diagnostic_sender_uses_router_affinity_and_not_first_owner_port(self):
        old_choose = pg.choose_outbound_port
        try:
            pg.choose_outbound_port = lambda owner_uid, phone_or_jid, **kw: {
                'port': 4611,
                'mode': 'existing_thread',
                'reason': 'teste mantém chip do lead',
            }
            owner = {'nome': 'Sarah', 'porta': 4601, 'portas': [4601, 4611], 'owner_uid': 'sarah'}
            sender = pg.resolve_diagnostic_sender(owner, '553499999999@s.whatsapp.net', lead_key='deal-123')
        finally:
            pg.choose_outbound_port = old_choose
        self.assertEqual(sender['porta'], 4611)
        self.assertEqual(sender['routing_mode'], 'existing_thread')
        self.assertEqual(sender['owner_uid'], 'sarah')

    def test_pick_online_port_respects_active_dispatch_queue_affinity(self):
        old_bridge_me = pg.bridge_me
        old_limits = pg.port_within_external_limits
        try:
            pg.bridge_me = lambda port: (True, {'phone': str(port), 'name': f'Chip {port}'})
            pg.port_within_external_limits = lambda envios, port: (True, 'ok')
            owner = {'nome': 'Sarah', 'porta': 4601, 'portas': [4601, 4611], 'owner_uid': 'sarah'}
            dispatches = [{'port': 4611, 'jid': '553499999999@s.whatsapp.net', 'status': 'queued'}]
            port, ok, _me, _detail = pg.pick_online_port(owner, [], jid='553499999999@s.whatsapp.net', lead_key='deal-123', dispatches=dispatches)
        finally:
            pg.bridge_me = old_bridge_me
            pg.port_within_external_limits = old_limits
        self.assertTrue(ok)
        self.assertEqual(port, 4611)

    def test_enqueue_worker_owned_diagnostic_bundle_uses_text_pdf_question_and_completion(self):
        calls = []
        old_record = pg.record_dispatch_worker_owned
        try:
            pg.record_dispatch_worker_owned = lambda **kwargs: calls.append(kwargs) or {'ok': True, 'dispatch_id': 'dsp-test'}
            res = pg.enqueue_worker_owned_diagnostic_bundle(
                jid='5511999999999@s.whatsapp.net',
                port=4601,
                msg='texto inicial',
                pdf_path='/tmp/diag.pdf',
                pdf_file_name='Diagnostico.pdf',
                thumb_path='/tmp/thumb.jpg',
                question_text='pergunta final',
                email='lead@empresa.com.br',
                contact_id='123',
                deal_id='456',
                slug='empresa-lead',
                company='Empresa Lead',
                phone='11999999999',
                owner_id='88063842',
                owner_name='Sarah',
                sender_name='Sarah',
                agenda_text='agenda depois',
                task_id='task-1',
                hubspot_file_id='file-1',
            )
        finally:
            pg.record_dispatch_worker_owned = old_record
        self.assertTrue(res['ok'])
        self.assertEqual(len(calls), 1)
        row = calls[0]
        self.assertEqual(row['origin'], 'diagnostico')
        self.assertEqual(row['nature'], 'diagnostic_bundle')
        self.assertEqual(row['completion_type'], 'diagnostic_bundle')
        self.assertEqual(row['parts'][0], {'kind': 'text', 'text': 'texto inicial'})
        self.assertEqual(row['parts'][1]['kind'], 'file')
        self.assertEqual(row['parts'][1]['filePath'], '/tmp/diag.pdf')
        self.assertEqual(row['parts'][1]['fileName'], 'Diagnostico.pdf')
        self.assertEqual(row['parts'][2], {'kind': 'text', 'text': 'pergunta final'})
        self.assertEqual(row['delay_schedule'], [pg.TEXT_TO_PDF_DELAY_SECONDS, pg.PDF_TO_QUESTION_DELAY_SECONDS])
        self.assertEqual(row['task_id'], 'task-1')
        self.assertEqual(row['hubspot_file_id'], 'file-1')

    def test_flag_desligada_preserva_fluxo_legado_com_send(self):
        import inspect
        # Sem a env var, o producer NÃO entra no caminho worker_owned e o main()
        # continua com o transporte legado direto (/send e /send-file).
        old = os.environ.pop('ZYDON_MQL_DIAGNOSTIC_WORKER_OWNED', None)
        try:
            self.assertFalse(pg.diagnostic_worker_owned_enabled())
        finally:
            if old is not None:
                os.environ['ZYDON_MQL_DIAGNOSTIC_WORKER_OWNED'] = old
        src = inspect.getsource(pg.main)
        # O caminho legado do lead continua existindo e é gated pela flag.
        self.assertIn("post_bridge_with_retries(port,'/send'", src)
        self.assertIn("post_bridge_with_retries_locked(port,'/send-file'", src)
        self.assertIn('if diagnostic_worker_owned_enabled():', src)
        idx_flag = src.index('if diagnostic_worker_owned_enabled():')
        idx_dispatch = src.index('dispatch_diagnostic_worker_owned(')
        idx_legacy_send = src.index("post_bridge_with_retries(port,'/send'")
        # A ramificação worker_owned (flag ligada) vem antes do transporte legado e
        # encerra o item com `continue` sem tocar em post_bridge/send-file.
        self.assertLess(idx_flag, idx_dispatch)
        self.assertLess(idx_dispatch, idx_legacy_send)
        branch = src[idx_flag:idx_legacy_send]
        self.assertIn('continue', branch)
        # nenhuma chamada real de transporte ao lead dentro do bloco worker_owned
        self.assertNotIn('post_bridge_with_retries', branch)
        self.assertNotIn('safe_post_bridge', branch)

    def test_flag_ligada_enfileira_bundle_worker_owned_sem_enviar_direto(self):
        # dispatch_diagnostic_worker_owned enfileira o bundle worker_owned com
        # completion + campos mínimos e NÃO chama transporte direto do lead.
        captured = {}
        direct_sends = []

        def fake_record(**kwargs):
            captured.update(kwargs)
            return {'ok': True, 'dispatch_id': 'dsp-wo'}

        def boom_bridge(*a, **k):
            direct_sends.append((a, k))
            raise AssertionError('worker_owned não pode chamar transporte direto do lead')

        patches = {
            'record_dispatch_worker_owned': fake_record,
            'load_wpp': lambda: [],
            'existing_group_notification': lambda *a, **k: (False, ''),
            'append_group_inflight': lambda *a, **k: None,
            'post_group_with_rotation': lambda text, envios: (4607, {'to': 'x', 'internal_notify_label': 'Mariana Cirilo'}, []),
            'upload_pdf_to_hubspot': lambda pdf, slug: ('file-1', None),
            'hubspot_file_url': lambda fid: f'https://files/{fid}',
            'create_task': lambda *a, **k: 'task-9',
            'post_bridge': boom_bridge,
            'safe_post_bridge': boom_bridge,
        }
        olds = {name: getattr(pg, name) for name in patches}
        try:
            for name, fn in patches.items():
                setattr(pg, name, fn)
            out = pg.dispatch_diagnostic_worker_owned(
                envios=[], email='lead@empresa.com.br', cid='123', slug='empresa-lead',
                deals=['456'], primary_deal_id='456', owner='88063842', owner_name='Sarah',
                sdr='Sarah', company='Empresa Lead', phone='11999999999',
                jid='5511999999999@s.whatsapp.net', port=4601, pdf='/tmp/diag_canon.pdf',
                pretty='/tmp/Empresa - Potencial de Digitalizacao B2B.pdf', thumb='/tmp/thumb.jpg',
                msg='texto inicial', intent_question=pg.MQL_INTENT_QUESTION_FIXED,
                agenda_msg='agenda depois', group_summary='✅ Lead qualificado',
                queue_item=None, owner_actions=[])
        finally:
            for name, fn in olds.items():
                setattr(pg, name, fn)
        # não houve envio direto ao lead
        self.assertEqual(direct_sends, [])
        # enfileirou exatamente um bundle worker_owned
        self.assertEqual(captured.get('origin'), 'diagnostico')
        self.assertEqual(captured.get('nature'), 'diagnostic_bundle')
        self.assertEqual(captured.get('completion_type'), 'diagnostic_bundle')
        # três partes reais: texto, PDF, pergunta
        self.assertEqual(captured['parts'][0], {'kind': 'text', 'text': 'texto inicial'})
        self.assertEqual(captured['parts'][1]['kind'], 'file')
        self.assertEqual(captured['parts'][2]['text'], pg.MQL_INTENT_QUESTION_FIXED)
        # campos mínimos para o completion (ledger/agenda/task/hubspot)
        for field in ('task_id', 'hubspot_file_id', 'agenda_text', 'agenda_queue_key',
                      'deal_id', 'contact_id', 'phone', 'owner_id', 'pdf_path', 'jid', 'port'):
            self.assertIn(field, captured, field)
        self.assertEqual(captured['task_id'], 'task-9')
        self.assertEqual(captured['hubspot_file_id'], 'file-1')
        self.assertEqual(captured['agenda_queue_key'], 'agenda:lead@empresa.com.br:empresa-lead:4601:5511999999999@s.whatsapp.net')
        self.assertEqual(out['task_id'], 'task-9')
        self.assertEqual(out['file_id'], 'file-1')

    def test_producer_worker_owned_marca_execution_mode_live(self):
        # record_dispatch_worker_owned força execution_mode=worker_owned na fila,
        # que é o único modo que o worker live executa.
        import importlib.util
        fspec = importlib.util.spec_from_file_location('flow_wo', os.path.join(ROOT, 'scripts', 'whatsapp_dispatch_flow.py'))
        flow = importlib.util.module_from_spec(fspec)
        fspec.loader.exec_module(flow)
        qspec = importlib.util.spec_from_file_location('queue_wo', os.path.join(ROOT, 'scripts', 'whatsapp_dispatch_queue.py'))
        queue = importlib.util.module_from_spec(qspec)
        qspec.loader.exec_module(queue)
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'dispatch.json'
            res = flow.record_dispatch_worker_owned(origin='diagnostico', nature='diagnostic_bundle',
                                                    to='5511999999999@s.whatsapp.net', text='bundle',
                                                    owner_uid='sarah', port=4601, path=path)
            self.assertTrue(res['ok'])
            rows = queue.load_dispatches(path)
            self.assertEqual(rows[0]['execution_mode'], 'worker_owned')
            self.assertEqual(rows[0]['origin'], 'diagnostico')


class TestNaoRepetirDiagnostico(unittest.TestCase):
    def test_contextualizacao_nunca_cola_diagnostico(self):
        diag = ('Fiz um diagnóstico completo da operação: vocês vendem por WhatsApp, '
                'usam Omie, têm gargalo no pedido manual e potencial alto de digitalização '
                'B2B com catálogo, tabela por cliente e recompra recorrente.')
        out = cad.contextualizacao_obrigatoria(diag, 'Policrom')
        self.assertNotIn('Tenho este contexto inicial', out)
        self.assertNotIn('diagnóstico', out.lower())
        self.assertNotIn('Omie', out)
        self.assertIn('objetivo', out.lower())
        # Mensagem curta, não textão.
        self.assertLess(len(out), 200)

    def test_contextualizacao_sem_empresa(self):
        out = cad.contextualizacao_obrigatoria('qualquer diagnóstico longo aqui')
        self.assertIn('objetivo', out.lower())
        self.assertNotIn('Tenho este contexto inicial', out)

    def test_pergunta_oficial_preservada(self):
        # A pergunta oficial precisa continuar disponível como variação do follow 1.
        # A escolha por lead é determinística (hash), então variamos o deal_id para
        # cobrir as variações e garantir que a pergunta oficial é uma delas e que
        # nenhuma variação cola o diagnóstico.
        textos = []
        for i in range(20):
            lead = {'deal_id': f'deal{i}', 'jid': f'55119{i:08d}@s.whatsapp.net',
                    'nome': 'Leonardo', 'empresa': 'Policrom'}
            t = cad.extract_message_variation(lead, 1, None)
            textos.append(t)
            self.assertNotIn('Tenho este contexto inicial', t)
            self.assertNotIn('Como você imagina que a Zydon pode te ajudar?', t)
            self.assertNotIn('Como você imagina que q Zydon pode te ajudar?', t)
            self.assertNotIn('Quero entender o objetivo', t)
            self.assertNotIn('diagnóstico', t.lower())
            self.assertLess(len(t), 240)
        juntos = '\n'.join(textos)
        self.assertIn(PERGUNTA_OFICIAL, juntos)


class TestPerguntaOficialEmScriptsAtivos(unittest.TestCase):
    def test_scripts_ativos_nao_tem_pergunta_antiga(self):
        antigos = [
            'Como você imagina que q Zydon pode te ajudar?',
            'Como você imagina que a Zydon pode te ajudar?',
        ]
        for rel in [
            'scripts/process_gate_once.py',
            'disparo_dinamico.py',
            'scripts/mql_sdr_followup.py',
            'scripts/cadencia_primeiro_contato.py',
            'scripts/channel_panel_v2.py',
        ]:
            txt = Path(ROOT, rel).read_text(encoding='utf-8')
            self.assertIn(PERGUNTA_OFICIAL, txt, rel)
            for old in antigos:
                self.assertNotIn(old, txt, rel)


class TestClassificacaoSemContradicao(unittest.TestCase):
    def test_reentrada_por_meetings_link_nao_fura_dedup(self):
        props = {
            'hs_object_source': 'FORM',
            'recent_conversion_event_name': 'Meetings Link: lucas-alcantara-nogueira-batista',
            'createdate': '2026-06-29T20:00:00.000Z',
            'recent_conversion_date': '2026-06-29T21:00:00.000Z',
        }
        self.assertFalse(pg.is_form_reentry_event(props))
        self.assertFalse(gate.is_form_reentry_event(props))
        self.assertFalse(gate.is_forms_channel_lead(props))

    def test_reentrada_sem_evento_nao_usa_source_form_original(self):
        props = {
            'hs_object_source': 'FORM',
            'hs_object_source_label': 'FORM',
            'createdate': '2026-06-29T20:00:00.000Z',
            'recent_conversion_date': '2026-06-29T21:00:00.000Z',
            'recent_conversion_event_name': '',
        }
        self.assertFalse(gate.is_forms_channel_lead(props))

    def test_evento_offline_nao_entra_no_gate_forms(self):
        props = {'hs_object_source': 'OFFLINE', 'recent_conversion_event_name': 'Offline Sources'}
        self.assertFalse(gate.is_form_reentry_event(props))
        self.assertFalse(gate.is_forms_channel_lead(props))
        self.assertFalse(pending_watchdog.is_form_signal(props))

    def test_form_facebook_entra_no_alerta_e_gate(self):
        props = {'hs_object_source': 'FORM', 'recent_conversion_event_name': 'Novo lead Facebook'}
        self.assertTrue(gate.is_forms_channel_lead(props))
        self.assertTrue(pending_watchdog.is_form_signal(props))

    def test_form_admin_interno_base_teste_nao_alerta_nem_entra_na_fila_mql(self):
        props = {
            'hs_object_source': 'FORM',
            'recent_conversion_event_name': 'form admin (interno)',
            'hs_analytics_source': 'OFFLINE',
            'hs_analytics_source_data_1': 'INTEGRATION',
            'hs_analytics_source_data_2': '52447',
            'company': 'Leo Testes',
            'firstname': 'Leonardo Tester',
            'email': 'leonardolns.ux+7@gmail.com',
        }
        self.assertFalse(pending_watchdog.is_form_signal(props))
        self.assertFalse(active_mql.is_form_signal(props))
        dummy = {
            'hs_object_source': 'FORM',
            'recent_conversion_event_name': 'Plataforma de E-commerce B2B com IA e ERP | Zydon: Formulário site (demonstração)',
            'company': 'Empresa Ltda.',
            'firstname': 'joao',
            'email': 'joao@empresa.com.br',
            'phone': '+55(11) 99999-9999',
        }
        self.assertFalse(pending_watchdog.is_form_signal(dummy))
        self.assertFalse(active_mql.is_form_signal(dummy))

    def test_evermax_distribuidora_autopecas_posto_frota_e_mql(self):
        props = {
            'company': 'Evermax Distribuidor',
            'email': 'iron.san@evermax.com.br',
            'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados': 'Postos de combustível auto peças atacadista moto peças',
            'qual_erp_utiliza_': 'TOTVS',
            'qual_o_faturamento_anual_da_sua_empresa_': 'De R$5 a R$10 milhões ao ano',
            'quantas_pessoas_atuam_na_sua_empresa': '21_a_100_',
            'de_qual_forma_mais_vende_hoje_em_dia': 'Presença no cliente',
        }
        research = {
            'mql': True,
            'empresa_real': 'Evermax Distribuidor — distribuidora autorizada Moove/Mobil desde 1997.',
            'dominio_site': 'evermax.com.br — site oficial, CNPJ, unidades MT/MS.',
            'segmento': 'Distribuidora autorizada de lubrificantes, aditivos e pneus para autopeças, postos de combustível, oficinas, frotas, transportadoras e máquinas agrícolas.',
            'motivo': 'Distribuição autorizada, produto físico de reposição recorrente, tabela, estoque, preço, disponibilidade e pedidos frequentes.',
            'insight': 'postos, oficinas, autopeças e frotas consultarem catálogo, preço e disponibilidade para repor estoque',
        }
        ok, reason = pg.strict_icp_check(props, research)
        self.assertTrue(ok, reason)
        self.assertRegex(reason, r'distribuidora|fornecedora')

    def test_promedix_distribuidora_hospitalar_site_historico_e_mql(self):
        props = {
            'company': 'Promedix Produtos Médicos',
            'email': 'juliana@medix.ind.br',
            'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados': 'casas cirúrgicas e distribuição',
            'qual_erp_utiliza_': 'Bling',
            'quantas_pessoas_atuam_na_sua_empresa': '11_a_25',
        }
        research = {
            'mql': True,
            'empresa_real': 'MEDIX / Promedix Produtos Médicos — fornecedora/distribuidora de produtos médicos e hospitalares.',
            'dominio_site': 'medix.ind.br — domínio oficial, site oficial ativo, mais de 10 anos de mercado.',
            'segmento': 'Distribuidora de produtos médicos, materiais laboratoriais, saneantes e instrumentais para casas cirúrgicas, hospitais e clínicas.',
            'motivo': 'Catálogo amplo com mais de 1.000 itens, lista de produtos, preço, disponibilidade, estoque e compra recorrente.',
            'insight': 'compradores de saúde consultarem catálogo e disponibilidade para repor itens',
        }
        ok, reason = pg.strict_icp_check(props, research)
        self.assertTrue(ok, reason)

    def test_lleida_maquinas_equipamentos_site_historico_e_mql(self):
        props = {
            'company': 'Lleida',
            'email': 'leonardo@lleida.com.br',
            'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados': 'máquinas e equipamentos para empresas',
            'qual_erp_utiliza_': 'Outro',
            'quantas_pessoas_atuam_na_sua_empresa': '21_a_100_',
        }
        research = {
            'mql': True,
            'empresa_real': 'Lleida Máquinas e Equipamentos — fornecedor/distribuidor de máquinas e equipamentos industriais.',
            'dominio_site': 'lleida.com.br — site oficial ativo, empresa real com anos de mercado.',
            'segmento': 'Fornecedor de máquinas e equipamentos, peças e suprimentos para empresas e compradores técnicos.',
            'motivo': 'Produto físico, orçamento recorrente, catálogo, tabela, estoque e disponibilidade para compradores B2B.',
            'insight': 'empresas consultarem máquinas, peças e disponibilidade sem depender de cada atendimento manual',
        }
        ok, reason = pg.strict_icp_check(props, research)
        self.assertTrue(ok, reason)

    def test_koche_fabricante_automotivo_para_oficinas_e_mql_sem_confundir_com_confeccao(self):
        props = {
            'company': 'Kóche',
            'email': 'contato@industriakoche.com.br',
            'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados': 'Mecânicas automotivas',
            'qual_erp_utiliza_': 'Olist (Tiny)',
            'qual_o_faturamento_anual_da_sua_empresa_': 'De R$5 a R$10 milhões ao ano',
            'quantas_pessoas_atuam_na_sua_empresa': '21_a_100_',
            'de_qual_forma_mais_vende_hoje_em_dia': 'WhatsApp',
            'vende_em_loja_virtual_': 'sim',
        }
        research = {
            'mql': True,
            'empresa_real': 'Kóche Automotiva / Indústria Kóche — fabricante nacional da máquina FT-100 para troca de óleo de câmbio automático e acessórios/flanges para oficinas automotivas.',
            'dominio_site': 'industriakoche.com.br redireciona para kocheautomotiva.com.br — site oficial ativo, compre direto da fábrica, loja com flanges/acessórios, carrinho, preços, treinamento e suporte para oficinas.',
            'segmento': 'Indústria/fabricante de equipamento automotivo e acessórios para oficinas mecânicas, com venda recorrente de máquinas/flanges/peças, loja virtual, tabela/preço, estoque e atendimento por WhatsApp para oficinas.',
            'motivo': 'Fabricante nacional com produto físico, catálogo/loja e foco em oficinas automotivas.',
            'insight': 'oficinas consultarem máquinas, flanges e acessórios com preço e disponibilidade para montar pedidos',
        }
        ok, reason = pg.strict_icp_check(props, research)
        self.assertTrue(ok, reason)
        self.assertNotIn('confecção', reason.lower())

    def test_coturno_atalaia_varejo_online_atacado_whatsapp_e_mql(self):
        props = {
            'company': 'Atalaia calçados militares',
            'email': 'lucas@coturnoatalaia.com.br',
            'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados': 'Lojas de artigos militares',
            'qual_erp_utiliza_': 'Bling',
            'qual_o_faturamento_anual_da_sua_empresa_': 'De R$500 mil a R$1 milhão ao ano',
            'quantas_pessoas_atuam_na_sua_empresa': '1_a_10',
            'quantos_vendedores_internos_sua_empresa_possui': '2_a_5',
            'de_qual_forma_mais_vende_hoje_em_dia': 'Varejo online e atacado no whatsapp',
            'vende_em_loja_virtual_': 'sim',
            'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor': 'Sim',
            'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente': 'pedidos_chegam_desorganizados_(whatsapp,_telefone,_planilha)',
        }
        research = {
            'mql': True,
            'empresa_real': 'Coturno Atalaia / Atalaia Calçados Militares — marca/loja de coturnos militares, botas táticas, linha exército/PRF/PMSC e acessórios, com e-commerce próprio.',
            'dominio_site': 'coturnoatalaia.com.br redireciona para loja.coturnoatalaia.com.br — site oficial/e-commerce ativo com carrinho, pedidos, categorias PMSC, Botas Táticas, Coturnos Exército, Padrão PRF, acessórios, numeração especial e produtos com preço.',
            'segmento': 'Comércio/marca de calçados militares e acessórios com e-commerce e atacado no WhatsApp; produto físico com grade/numeração, estoque, preço, disponibilidade e potencial de recompra por lojas de artigos militares, equipes e compradores recorrentes.',
            'motivo': 'Bling, loja virtual, atacado no WhatsApp, pedidos desorganizados e catálogo de produtos físicos com SKUs/preços.',
            'insight': 'lojistas e compradores recorrentes consultarem grade, preço e disponibilidade de coturnos e acessórios para pedidos de atacado',
        }
        ok, reason = pg.strict_icp_check(props, research)
        self.assertTrue(ok, reason)

    def test_divergencia_mql_vs_crivo_nao_vira_nao_mql_grupo(self):
        import inspect
        src = inspect.getsource(pg.main)
        self.assertIn('DIVERGÊNCIA MQL vs crivo', src)
        self.assertIn('não enviei lead nem avisei grupo', src)
        self.assertNotIn("r['mql'] = False\n            r['motivo'] = (r.get('motivo') or '') + f' | Reprovado no crivo", src)

    def test_reentrada_por_formulario_pode_furar_dedup(self):
        props = {'recent_conversion_event_name': 'Diagnóstico comercial Zydon'}
        self.assertTrue(pg.is_form_reentry_event(props))
        self.assertTrue(gate.is_form_reentry_event(props))

    def test_gate_nao_busca_mql_manual_por_lastmodifieddate(self):
        import inspect
        self.assertIn('lastmodifieddate', gate.PROPERTIES)
        src = inspect.getsource(gate.hubspot_search)
        self.assertNotIn("'propertyName': 'lastmodifieddate'", src)
        self.assertNotIn("'value': 'marketingqualifiedlead'", src)
        # lastmodifieddate continua parseável para leitura/debug, mas não pode ser
        # gatilho automático de gol de mão: ele muda por task/owner/nota/automação.
        self.assertIsNotNone(gate.parse_hs_datetime('2026-06-28T18:10:46.141Z'))

    def test_gate_main_desarma_manual_mql_por_lastmodifieddate(self):
        import inspect
        src = inspect.getsource(gate.main)
        self.assertIn('manual_mql_trigger = False', src)
        self.assertNotIn('manual_mql_trigger = is_manual_mql_trigger', src)

    def test_mql_manual_fura_forms_e_crm_ui_quando_modificado_depois(self):
        from datetime import datetime, timezone
        props = {
            'lifecyclestage': 'marketingqualifiedlead',
            'lastmodifieddate': '2026-06-28T18:10:46.141Z',
            'hs_object_source': 'CRM_UI',
            'recent_conversion_event_name': 'Offline Sources',
        }
        processed_at = datetime(2026, 6, 28, 18, 0, tzinfo=timezone.utc)
        old_fetch = gate.fetch_lifecycle_history
        try:
            gate.fetch_lifecycle_history = lambda contact_id, token: [
                {'value': 'marketingqualifiedlead', 'timestamp': '2026-06-28T18:10:46.141Z', 'sourceType': 'MOBILE_IOS', 'updatedByUserId': 68346480}
            ]
            now = datetime(2026, 6, 28, 18, 20, tzinfo=timezone.utc)
            manual_mql_trigger = gate.is_manual_mql_trigger({'id': '123'}, props, processed_at, 'token', now=now)
        finally:
            gate.fetch_lifecycle_history = old_fetch
        self.assertTrue(manual_mql_trigger)
        self.assertFalse(gate.is_forms_channel_lead(props))

    def test_mql_automatico_ou_integracao_nao_e_override_manual(self):
        from datetime import datetime, timezone
        props = {
            'lifecyclestage': 'marketingqualifiedlead',
            'lastmodifieddate': '2026-06-29T10:05:30Z',
            'hs_object_source': 'FORM',
        }
        processed_at = datetime(2026, 6, 29, 9, 0, tzinfo=timezone.utc)
        old_fetch = gate.fetch_lifecycle_history
        try:
            for source_type in ['AUTOMATION_PLATFORM', 'INTEGRATION', 'FORM']:
                gate.fetch_lifecycle_history = lambda contact_id, token, st=source_type: [
                    {'value': 'marketingqualifiedlead', 'timestamp': '2026-06-29T10:05:30Z', 'sourceType': st}
                ]
                now = datetime(2026, 6, 29, 10, 10, tzinfo=timezone.utc)
                self.assertFalse(gate.is_manual_mql_trigger({'id': '123'}, props, processed_at, 'token', now=now), source_type)
        finally:
            gate.fetch_lifecycle_history = old_fetch

    def test_lastmodified_recente_sem_lifecycle_mql_recente_nao_e_manual_mql(self):
        from datetime import datetime, timezone
        props = {
            'lifecyclestage': 'marketingqualifiedlead',
            'lastmodifieddate': '2026-06-28T20:03:58.282Z',
            'hs_object_source': 'FORM',
        }
        processed_at = datetime(2026, 6, 28, 20, 3, tzinfo=timezone.utc)
        old_fetch = gate.fetch_lifecycle_history
        try:
            gate.fetch_lifecycle_history = lambda contact_id, token: [
                {'value': 'marketingqualifiedlead', 'timestamp': '2026-06-14T16:04:59.365Z'},
                {'value': 'lead', 'timestamp': '2026-06-14T16:04:56.564Z'},
            ]
            now = datetime(2026, 6, 28, 20, 10, tzinfo=timezone.utc)
            manual_mql_trigger = gate.is_manual_mql_trigger({'id': '228338097261'}, props, processed_at, 'token', now=now)
        finally:
            gate.fetch_lifecycle_history = old_fetch
        self.assertFalse(manual_mql_trigger)

    def test_mql_antigo_sem_processed_nao_entra_como_manual(self):
        from datetime import datetime, timezone
        props = {
            'lifecyclestage': 'marketingqualifiedlead',
            'lastmodifieddate': '2026-06-28T22:42:13.282Z',
            'hs_object_source': 'FORM',
        }
        old_fetch = gate.fetch_lifecycle_history
        try:
            gate.fetch_lifecycle_history = lambda contact_id, token: [
                {'value': 'marketingqualifiedlead', 'timestamp': '2026-05-31T12:44:59.685Z'},
                {'value': 'lead', 'timestamp': '2026-05-31T12:39:57.532Z'},
            ]
            now = datetime(2026, 6, 28, 22, 45, tzinfo=timezone.utc)
            manual_mql_trigger = gate.is_manual_mql_trigger({'id': '225256699997'}, props, None, 'token', now=now)
        finally:
            gate.fetch_lifecycle_history = old_fetch
        self.assertFalse(manual_mql_trigger)

    def test_processamento_nao_forca_mql_por_lifecycle_automatico_antigo(self):
        import inspect
        src = inspect.getsource(pg.main)
        self.assertIn('hubspot_mql_authority = manual_hubspot_mql', src)
        self.assertNotIn('hubspot_mql_authority = manual_hubspot_mql or hubspot_lifecycle_mql', src)
        self.assertIn('MQL antigo/herdado', src)

    def test_mql_bloqueia_se_ja_anunciou_nao_mql(self):
        envios = [{'email': 'lead@empresa.com.br', 'status': 'nao_mql_grupo'}]
        msg = pg.prior_classification_conflict(envios, 'lead@empresa.com.br', 'mql')
        self.assertIn('já havia anúncio/ação Não-MQL', msg)

    def test_mql_manual_marketing_vence_nao_mql_anterior(self):
        envios = [{'email': 'lead@empresa.com.br', 'status': 'nao_mql_grupo'}]
        msg = pg.prior_classification_conflict(envios, 'lead@empresa.com.br', 'mql', manual_hubspot_mql=True)
        self.assertIsNone(msg)

    def test_nao_mql_bloqueia_se_ja_enviou_mql(self):
        envios = [{'email': 'lead@empresa.com.br', 'status': 'enviado_lead'}]
        msg = pg.prior_classification_conflict(envios, 'lead@empresa.com.br', 'nao_mql')
        self.assertIn('já havia anúncio/envio MQL', msg)

    def test_backfill_nao_mql_aceita_ledger_recente(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        recent = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M')
        envios = [{'email': 'novo@empresa.com.br', 'status': 'nao_mql_grupo', 'date': recent, 'empresa': 'Empresa'}]
        items = non_mql.ledger_non_mql_research_items(envios)
        self.assertEqual(items[0][0], 'novo@empresa.com.br')

    def test_nao_mql_tratativa_bloqueia_se_ja_teve_diagnostico_mql(self):
        envios = [{'email': 'lead@empresa.com.br', 'status': 'mql_diagnostico_rafael_texto'}]
        sent, why = non_mql.already_sent(envios, email='lead@empresa.com.br')
        self.assertTrue(sent)
        self.assertIn('mql_diagnostico_rafael_texto', why)

    def test_definidor_nao_mql_aciona_worker_externo_imediato_com_override(self):
        fake = mock.Mock(
            returncode=0,
            stdout=json.dumps({
                'ok': True,
                'results': [{
                    'sender': 'Lucas Resende',
                    'port': 4606,
                    'result': {'ok': True, 'messageId': 'MSG123', 'task_id': 'TASK123'},
                }],
            }),
            stderr='',
        )
        props = {
            'lifecyclestage': 'lead',
            'company': 'Empresa Teste',
            'phone': '+55 11 99999-0000',
            'firstname': 'Ana',
        }
        with mock.patch.object(pg.subprocess, 'run', return_value=fake) as run_mock, \
             mock.patch.object(pg, 'load_wpp', return_value=[{'status': 'enviado_nao_mql_legitimo'}]):
            _, note = pg.trigger_non_mql_external_now(
                'lead@empresa.com.br', '123', props, {'slug': 'empresa-teste', 'motivo': 'Não MQL'}, [], []
            )
        self.assertIn('tratativa externa Não-MQL enviada', note)
        kwargs = run_mock.call_args.kwargs
        self.assertEqual(kwargs['env']['ZYDON_NON_MQL_IGNORE_HOURLY'], '1')
        self.assertEqual(kwargs['env']['ZYDON_NON_MQL_IGNORE_DAILY'], '1')
        self.assertNotIn('ZYDON_SKIP_SEND_LOCK', kwargs['env'])
        self.assertIn('--send-current', run_mock.call_args.args[0])

    def test_process_gate_nao_mql_nao_pode_ser_so_grupo_interno(self):
        src = Path(ROOT, 'scripts/process_gate_once.py').read_text(encoding='utf-8')
        self.assertIn('trigger_non_mql_external_now(email, cid, props, r, deals', src)
        self.assertIn('tratativa externa acionada imediatamente pelo definidor MQL', src)
        self.assertNotIn('somente aviso interno conforme regra do ciclo', src)
        self.assertNotIn('sem contato ao lead")', src)

    def test_mql_inflight_bloqueia_reenvio_diagnostico(self):
        envios = [{'email': 'lead@empresa.com.br', 'status': 'mql_diagnostico_em_andamento', 'to': '5511999999999@c.us'}]
        blocked, why = pg.existing_mql_outreach(envios, email='lead@empresa.com.br', phone='11999999999')
        self.assertTrue(blocked)
        self.assertIn('mql_diagnostico_em_andamento', why)

    def test_no_show_recente_bloqueia_novo_diagnostico_pdf(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        envios = [{
            'sent_at_brt': '2026-06-28 11:27:21',
            'date': '2026-06-28 11:27:21',
            'status': 'enviado',
            'msg_type': 'no_show_pontual_all_pending_20260628',
            'campaign': 'no_show_pontual_all_pending_20260628',
            'contact_id': '225522824885',
            'to': '5519982248424@s.whatsapp.net',
            'text': 'Para uma operação de vitrine e pedido B2B para lojistas/revendas, faz sentido retomar esse diagnóstico?',
            'messageId': '3EB0710F0ACCD2F241FEF9',
        }]
        now = datetime(2026, 6, 28, 20, 27, tzinfo=ZoneInfo('America/Sao_Paulo'))
        blocked, why = pg.recent_prior_operational_diagnosis(
            envios,
            email='robertocarneiro@americasul.com',
            phone='19982248424',
            contact_id='225522824885',
            now=now,
        )
        self.assertTrue(blocked)
        self.assertIn('abordagem operacional recente', why)

    def test_no_show_antigo_nao_bloqueia_novo_form_real(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        envios = [{
            'date': '2026-06-26 11:27:21',
            'msg_type': 'no_show_pontual_all_pending_20260628',
            'contact_id': '225522824885',
            'to': '5519982248424@s.whatsapp.net',
            'text': 'faz sentido retomar esse diagnóstico?',
            'messageId': '3EB0710F0ACCD2F241FEF9',
        }]
        now = datetime(2026, 6, 28, 20, 27, tzinfo=ZoneInfo('America/Sao_Paulo'))
        blocked, why = pg.recent_prior_operational_diagnosis(envios, phone='19982248424', contact_id='225522824885', now=now)
        self.assertFalse(blocked)
        self.assertEqual('', why)

    def test_gate_dedup_telefone_le_ledger_dict_e_status_manual_mql(self):
        import json
        import tempfile
        data = {'envios': [
            {'status': 'enviado_lead_manual_mql', 'to': '5511964430677@s.whatsapp.net'},
            {'status': 'manual_nao_mql_convertido_mql', 'to': '5514997511020@s.whatsapp.net'},
        ]}
        old = gate.WPP_ENVIOS
        with tempfile.NamedTemporaryFile('w+', encoding='utf-8', delete=False) as f:
            json.dump(data, f)
            tmp = f.name
        try:
            gate.WPP_ENVIOS = Path(tmp)
            phones = gate.load_sent_phones()
        finally:
            gate.WPP_ENVIOS = old
            os.unlink(tmp)
        self.assertIn('11964430677', phones)
        self.assertIn('14997511020', phones)

    def test_mql_enviado_bloqueia_reentrada_por_agenda(self):
        envios = [{'email': 'lead@empresa.com.br', 'status': 'enviado_lead', 'to': '5511999999999@c.us'}]
        blocked, why = pg.existing_mql_outreach(envios, email='outro@empresa.com.br', phone='11999999999')
        self.assertTrue(blocked)
        self.assertIn('telefone', why)

    def test_grupo_em_andamento_bloqueia_duplicata_de_resumo(self):
        envios = [{'email': 'lead@empresa.com.br', 'status': 'grupo_notificacao_em_andamento', 'to': pg.GROUP}]
        blocked, why = pg.existing_group_notification(envios, email='lead@empresa.com.br')
        self.assertTrue(blocked)
        self.assertIn('grupo já notificado', why)

    def test_enviado_lead_com_group_summary_bloqueia_novo_resumo_grupo(self):
        envios = [{'email': 'lead@empresa.com.br', 'status': 'enviado_lead', 'group_summary': '✅ Lead qualificado'}]
        blocked, why = pg.existing_group_notification(envios, email='lead@empresa.com.br')
        self.assertTrue(blocked)
        self.assertIn('enviado_lead', why)

    def test_nao_mql_grupo_tem_linguagem_simples(self):
        research = {
            'segmento': 'Loja virtual de informática e serviços técnicos',
            'motivo': 'Reprovado no crivo MQL acirrado/fail-closed: pesquisa pública não confirmou indústria/distribuidor/atacado; venda por marketplace e ERP Outro.',
            'dominio_site': 'wzetta.com.br — loja virtual ativa',
        }
        text = pg.group_reason_bullets(research, mql=False)
        for termo in ['crivo', 'fail-closed', 'ICP', 'Reprovado']:
            self.assertNotIn(termo.lower(), text.lower())
        self.assertIn('•', text)
        self.assertRegex(text, r'B2B|varejo|serviço|prova pública|virar MQL')


class TestGrupoInflightStale(unittest.TestCase):
    """Incidente Kóche/Atalaia: marcador `grupo_notificacao_em_andamento` gravado
    antes do `/send` que morria deixava o grupo travado para sempre. O marker
    inflight puro só pode bloquear por uma janela curta de corrida (10 min)."""

    def setUp(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        self.tz = ZoneInfo('America/Sao_Paulo')
        self.now = datetime(2026, 6, 30, 12, 0, tzinfo=self.tz)

    def _marker(self, minutes_ago, **extra):
        from datetime import timedelta
        dt = self.now - timedelta(minutes=minutes_ago)
        row = {
            'email': 'lead@empresa.com.br',
            'status': 'grupo_notificacao_em_andamento',
            'to': pg.GROUP,
            'date_tz': dt.isoformat(),
            'date': dt.strftime('%Y-%m-%d %H:%M'),
        }
        row.update(extra)
        return row

    def test_marker_recente_sem_resposta_bloqueia(self):
        envios = [self._marker(3)]
        blocked, why = pg.existing_group_notification(
            envios, email='lead@empresa.com.br', now=self.now)
        self.assertTrue(blocked)
        self.assertIn('grupo já notificado', why)

    def test_marker_antigo_sem_resposta_nao_bloqueia(self):
        # Marker stale (passou da janela de 10 min) sem prova de envio: libera novo envio.
        envios = [self._marker(45)]
        blocked, why = pg.existing_group_notification(
            envios, email='lead@empresa.com.br', now=self.now)
        self.assertFalse(blocked)
        self.assertEqual(why, '')

    def test_marker_antigo_com_success_bloqueia(self):
        envios = [self._marker(120, group_summary_response={'success': True})]
        blocked, why = pg.existing_group_notification(
            envios, email='lead@empresa.com.br', now=self.now)
        self.assertTrue(blocked)
        self.assertIn('grupo já notificado', why)

    def test_marker_antigo_com_messageid_bloqueia(self):
        envios = [self._marker(120, messageId='ABC123@g.us')]
        blocked, why = pg.existing_group_notification(
            envios, email='lead@empresa.com.br', now=self.now)
        self.assertTrue(blocked)
        self.assertIn('grupo já notificado', why)

    def test_marker_antigo_com_group_bridge_port_bloqueia(self):
        # Resposta/porta do grupo = não é marcador puro de corrida; continua bloqueando.
        envios = [self._marker(120, group_bridge_port=8222)]
        blocked, why = pg.existing_group_notification(
            envios, email='lead@empresa.com.br', now=self.now)
        self.assertTrue(blocked)

    def test_marker_sem_timestamp_bloqueia_conservador(self):
        # Sem date/date_tz não dá para medir idade: mantém bloqueio (comportamento atual).
        envios = [{'email': 'lead@empresa.com.br',
                   'status': 'grupo_notificacao_em_andamento', 'to': pg.GROUP}]
        blocked, why = pg.existing_group_notification(
            envios, email='lead@empresa.com.br', now=self.now)
        self.assertTrue(blocked)

    def test_enviado_lead_sem_resumo_nao_bloqueia(self):
        envios = [{'email': 'lead@empresa.com.br', 'status': 'enviado_lead',
                   'to': '5511999999999@c.us'}]
        blocked, why = pg.existing_group_notification(
            envios, email='lead@empresa.com.br', now=self.now)
        self.assertFalse(blocked)
        self.assertEqual(why, '')

    def test_enviado_lead_com_resumo_bloqueia(self):
        envios = [{'email': 'lead@empresa.com.br', 'status': 'enviado_lead',
                   'group_summary': '✅ Lead qualificado'}]
        blocked, why = pg.existing_group_notification(
            envios, email='lead@empresa.com.br', now=self.now)
        self.assertTrue(blocked)
        self.assertIn('enviado_lead', why)


class TestSegmentoMapeado(unittest.TestCase):
    def test_food_service(self):
        r = {'segmento': 'Indústria alimentícia de doces de banana com distribuição B2B/atacado'}
        rotulo, desc = pg.map_segmento_mapeado(r, None)
        self.assertTrue(rotulo.startswith('Food Service'), rotulo)
        self.assertIn('atacado', rotulo)
        self.assertTrue(desc)

    def test_cosmeticos_vira_cs(self):
        r = {'segmento': 'Distribuidora atacadista de cosméticos profissionais para salões'}
        rotulo, _ = pg.map_segmento_mapeado(r, {'cargo_area': 'Cosméticos'})
        self.assertIn('CS', rotulo)

    def test_sem_certeza_nao_inventa_sigla(self):
        r = {'segmento': 'Indeterminado; sem evidência pública de operação B2B'}
        rotulo, desc = pg.map_segmento_mapeado(r, None)
        self.assertTrue(rotulo.startswith('Segmento B2B mapeado'), rotulo)
        for sigla in ('CPET', 'CVET', 'Food Service'):
            self.assertNotIn(sigla, rotulo)
        self.assertTrue(desc)


class TestHistoriaEContexto(unittest.TestCase):
    def test_ano_so_quando_existe_na_pesquisa(self):
        r = {'empresa_real': 'Bananinha Paraibuna — indústria, ativa desde 1975'}
        self.assertIn('1975', pg.extract_historia(r))

    def test_nunca_inventa_ano(self):
        # Ano só pode vir de empresa_real/dominio_site/redes/motivo. Se não houver,
        # não pode aparecer ano nenhum.
        r = {'empresa_real': 'Distribuidora B2B sem data pública',
             'dominio_site': 'exemplo.com.br', 'redes': '', 'motivo': ''}
        self.assertEqual(pg.extract_historia(r), '')

    def test_ano_em_segmento_nao_e_usado(self):
        # 'segmento' não é fonte autorizada para fundação.
        r = {'segmento': 'Indústria ativa desde 1900', 'empresa_real': 'Empresa X'}
        self.assertNotIn('1900', pg.extract_historia(r))


class TestReferenciasEnxutas(unittest.TestCase):
    def test_referencias_tem_site_fontes_formulario(self):
        r = {'dominio_site': 'scbeauty.com.br; portal scbeauty.meuspedidos.com.br',
             'redes': 'Instagram e CNPJ'}
        refs = pg.build_referencias(r)
        chaves = [k for k, _ in refs]
        self.assertIn('Site', chaves)
        self.assertIn('Fontes públicas', chaves)
        self.assertIn('Formulário', chaves)
        # Enxuto: nada de URL gigante, só o domínio raiz.
        site = dict(refs)['Site']
        self.assertEqual(site, 'scbeauty.com.br')
        self.assertNotIn('meuspedidos', site)

    def test_sem_dominio_nao_quebra(self):
        refs = pg.build_referencias({'dominio_site': 'Sem domínio corporativo'})
        self.assertIn('Formulário', [k for k, _ in refs])


class TestPdfHtmlEnriquecido(unittest.TestCase):
    def test_segmento_mapeado_aparece_no_html(self):
        html = _sample_pdf_html({'segmento': 'Indústria/fabricante de cerâmica decorativa'},
                                {'cargo_area': 'Indústria'})
        self.assertIn('Segmento mapeado', html)

    def test_referencias_enxutas_no_html(self):
        html = _sample_pdf_html({'segmento': 'Indústria de cerâmica decorativa',
                                 'dominio_site': 'ceramicaanaclaudia.com.br', 'redes': 'Instagram'})
        self.assertIn('Referências usadas', html)
        self.assertIn('ceramicaanaclaudia.com.br', html)

    def test_title_comercial_do_pdf(self):
        html = _sample_pdf_html({'segmento': 'Indústria de cerâmica decorativa'})
        self.assertIn('<title>Ceramica Ana Claudia - Potencial de Digitalizacao B2B.pdf</title>', html)

    def test_secao_roi_explicita(self):
        html = _sample_pdf_html({'segmento': 'Indústria de cerâmica decorativa'})
        self.assertIn('POTENCIAL & ROI', html)
        self.assertIn('Cada pedido manual custa caro', html)

    def test_process_gate_separa_agenda_do_diagnostico(self):
        txt = Path(ROOT, 'scripts/process_gate_once.py').read_text(encoding='utf-8')
        for proibido in [
            "intent_question = 'Pode ser?'",
            'te chama amanhã',
            'te mostrar isso na prática',
            'consultora da Zydon te chama',
            'consultor da Zydon te chama',
        ]:
            self.assertNotIn(proibido, txt)
        self.assertIn(PERGUNTA_OFICIAL, txt)
        self.assertIn('agenda_msg = agenda_followup_for_lead', txt)
        self.assertIn('PDF_TO_QUESTION_DELAY_SECONDS = 30', txt)
        self.assertIn('QUESTION_TO_AGENDA_DELAY_SECONDS = 20 * 60', txt)
        self.assertLess(txt.index('PDF_TO_QUESTION_DELAY_SECONDS'), txt.index('QUESTION_TO_AGENDA_DELAY_SECONDS'))
        self.assertIn("'agenda_text': agenda_msg", txt)

    def test_mensagem_diagnostico_nao_embute_agenda(self):
        owner_id = '88063842'
        agenda_msg = pg.agenda_followup_for_lead(True, owner_id)
        self.assertIn('https://meetings.hubspot.com/sarah-bento', agenda_msg)
        self.assertIn('Se quiser garantir o melhor horário para um diagnóstico completo, pode marcar direto aqui:', agenda_msg)
        self.assertNotIn('Se quiser adiantar', agenda_msg)
        self.assertNotIn('Eu te chamo amanhã', agenda_msg)
        msg = (f"Bom dia, Bruno, tudo bem? Aqui é a Mariana, da Zydon.\n\n"
               f"Fiz uma análise prévia do potencial da digitalização B2B do seu negócio.")
        self.assertNotIn('meetings.hubspot.com', msg)
        self.assertNotIn('te chama', msg)
        self.assertNotIn(PERGUNTA_OFICIAL, msg)

    def test_mensagem_diagnostico_whatsapp_e_objetiva(self):
        txt = Path(ROOT, 'scripts/process_gate_once.py').read_text(encoding='utf-8')
        for frase_longa in [
            'oportunidades bem práticas de digitalização B2B',
            'O ponto que mais chamou atenção foi',
            'Te mando o PDF aqui porque acho que vai fazer sentido',
            'Ponto principal:',
            'Por que você procurou a Zydon?',
            'Em resumo:',
        ]:
            self.assertNotIn(frase_longa, txt)
        self.assertIn('Fiz uma análise prévia do potencial da digitalização B2B do seu negócio.', txt)
        self.assertNotIn('Montei um diagnóstico rápido da {company} em PDF.', txt)
        self.assertIn("'question_text': intent_question", txt)
        self.assertIn("'pdf_to_question_seconds': PDF_TO_QUESTION_DELAY_SECONDS", txt)
        self.assertIn("'question_to_agenda_seconds': QUESTION_TO_AGENDA_DELAY_SECONDS", txt)
        self.assertIn('Como você imagina que a Zydon poderia te apoiar?', pg.sdr_opening_question(True))
        longo = 'aplicadores e profissionais de comunicação visual recomprarem vinil, tintas e películas por catálogo digital com preço e disponibilidade, reduzindo a demora no atendimento e pedidos manuais no balcão ou WhatsApp'
        curto = pg.concise_diag_insight(longo)
        self.assertLessEqual(len(curto), 95)
        self.assertFalse(curto.lower().startswith('dá pra'))
        self.assertNotRegex(curto, r'[.]{2,}$')

    def test_mql_precisa_ter_sdr_dono_antes_do_whatsapp_externo(self):
        txt = Path(ROOT, 'scripts/process_gate_once.py').read_text(encoding='utf-8')
        self.assertTrue(pg.has_known_sdr_owner('88063842'))  # Sarah
        self.assertTrue(pg.has_known_sdr_owner('86265630'))  # Breno
        self.assertTrue(pg.has_known_sdr_owner('85778446'))  # Lucas Batista
        self.assertFalse(pg.has_known_sdr_owner(''))
        self.assertFalse(pg.has_known_sdr_owner('rafael'))
        self.assertIn('if not has_known_sdr_owner(owner):', txt)
        self.assertIn('⚠️ MQL bloqueado: sem SDR dono', txt)
        self.assertIn("'mql_bloqueado_sem_sdr_dono'", txt)
        self.assertNotIn("append_processed(email, slug, 'mql_bloqueado_sem_sdr_dono'", txt)
        self.assertLess(txt.index('if not has_known_sdr_owner(owner):'), txt.index('append_mql_inflight(latest_envios'))

    def test_nunca_gera_1_a_a_a_10(self):
        html = _sample_pdf_html({'segmento': 'Indústria de cerâmica decorativa'}, pessoas='1_a_10')
        self.assertNotIn('1 a a a 10', html)
        self.assertIn('1 a 10', html)


def _css_font_size(css, selector):
    """Extrai o font-size (px) de um seletor exato do TEMPLATE do PDF."""
    m = re.search(r'(?:^|[}\n])\s*' + re.escape(selector) + r'\s*\{([^}]*)\}', css, re.M)
    assert m, f'seletor não encontrado: {selector}'
    fm = re.search(r'font-size:\s*([\d.]+)px', m.group(1))
    assert fm, f'sem font-size em: {selector}'
    return float(fm.group(1))


class TestPdfLegibilidadeMobile(unittest.TestCase):
    """Revisão mobile (Morena Bakana): PDF não pode comprimir tudo em 3 páginas,
    bloco SOBRE precisa ser objetivo e fontes maiores para ler no celular."""

    # Pesquisa pública longa colada — exatamente o caso que o Rafael quer enxugar.
    SOBRE_LONGO = (
        'A Morena Bakana é uma indústria/distribuidora B2B do segmento de moda praia e '
        'beachwear sediada em Cabo Frio, RJ, com atuação no atacado para lojistas e '
        'multimarcas de todo o Brasil. Fundada por empreendedoras locais, opera com '
        'coleções sazonais, pronta-entrega e programas de revenda, vendendo hoje '
        'majoritariamente por WhatsApp, catálogos em PDF e visitas de representantes em '
        'feiras do setor. Fontes públicas indicam presença ativa no Instagram, perfil '
        'comercial verificado e participação recorrente em eventos de moda praia, além de '
        'menções em portais regionais de economia criativa da Região dos Lagos e cadastro '
        'ativo na base de CNPJ consultada para esta análise.'
    )

    def _html(self, sobre):
        d = batch_prepare.build_lead_dict({'name': 'Maurina', 'empresa': 'Morena Bakana',
                                           'erp': 'Bling', 'faturamento': 'de R$5 a R$10 milhões'})
        d['sobre'] = sobre
        return gen.build_html(d)

    def test_pdf_nao_trava_em_tres_paginas(self):
        html = self._html('Empresa B2B de moda praia.')
        n = html.count('<section class="page">')
        self.assertNotEqual(n, 3, 'PDF não pode ficar preso em exatamente 3 páginas')
        # Paginação limpa: Análise/Sobre, Perfil, Diagnóstico, ROI, Integração.
        self.assertGreaterEqual(n, 5)

    def test_perfil_vira_pagina_propria(self):
        # PERFIL DA OPERAÇÃO sai da capa para página própria, para o grid de cards
        # não estourar o min-height da capa e quebrar no meio do card/texto.
        html = self._html('Empresa B2B de moda praia.')
        self.assertIn('>PERFIL DA OPERAÇÃO</span>', html)
        # capa (SOBRE) e perfil ficam em <section> diferentes
        idx_sobre = html.find('SOBRE A ')
        idx_perfil = html.find('PERFIL DA OPERAÇÃO')
        self.assertGreater(idx_perfil, idx_sobre)
        self.assertIn('</section>', html[idx_sobre:idx_perfil])
        # o grid de cards acompanha o perfil, não a capa
        idx_grid = html.find('class="profile"')
        self.assertGreater(idx_grid, idx_perfil)

    def test_integracao_vira_pagina_propria(self):
        html = self._html('Empresa B2B de moda praia.')
        self.assertIn('E A INTEGRAÇÃO? JÁ ESTÁ RESOLVIDA', html)
        # tag da página dedicada à integração
        self.assertIn('>INTEGRAÇÃO</span>', html)
        # ROI e integração ficam em <section> diferentes (há fechamento entre eles)
        idx_roi = html.find('POTENCIAL &amp; ROI') if 'POTENCIAL &amp; ROI' in html else html.find('POTENCIAL & ROI')
        idx_integ = html.find('E A INTEGRAÇÃO')
        self.assertGreater(idx_integ, idx_roi)
        self.assertIn('</section>', html[idx_roi:idx_integ])

    def test_cards_blindados_contra_quebra_interna(self):
        # CSS precisa evitar page break dentro de cards/blocos relevantes.
        css = gen.TEMPLATE
        self.assertIn('break-inside:avoid', css)
        self.assertIn('page-break-inside:avoid', css)
        for seletor in ['.pcard', '.aboutbox', '.callout', '.contabox',
                        '.statcard', '.meanbox', '.erpbox', '.chk', '.findings li']:
            self.assertIn(seletor, css, seletor)

    def test_sobre_longo_e_resumido(self):
        self.assertGreater(len(self.SOBRE_LONGO), 300)
        resumo = gen.resumo_sobre(self.SOBRE_LONGO)
        self.assertLess(len(resumo), len(self.SOBRE_LONGO))
        self.assertLessEqual(len(resumo), 320)
        html = self._html(self.SOBRE_LONGO)
        # o textão integral não pode ser colado no PDF
        self.assertNotIn(self.SOBRE_LONGO, html)
        self.assertIn(resumo, html)

    def test_sobre_curto_passa_intacto(self):
        curto = 'Distribuidora B2B de moda praia com pedidos por WhatsApp e representantes.'
        self.assertEqual(gen.resumo_sobre(curto), curto)
        self.assertIn(curto, self._html(curto))

    def test_fontes_chave_maiores_que_padrao_antigo(self):
        # valores do layout antigo apertado, que precisavam crescer para mobile
        antigos = {
            '.aboutbox p': 15.5,
            '.findings p': 16,
            '.callout p': 16,
            '.contabox p': 15,
            '.meanbox > p': 16,
            '.chk p': 14.5,
            '.pval': 18.5,
            '.statcard p': 13,
            '.erpval': 17,
            '.pfoot': 11.5,
        }
        for sel, antigo in antigos.items():
            self.assertGreater(_css_font_size(gen.TEMPLATE, sel), antigo, sel)

    def test_pdf_tem_motor_da_compra_e_nao_morosidade(self):
        html = self._html('Empresa B2B de moda praia.')
        self.assertIn('MOTOR DA COMPRA', html)
        self.assertIn('QUEM COMPRA E COMO COMPRA', html)
        self.assertIn('Quem compra', html)
        self.assertIn('Como estimular no digital', html)
        self.assertNotIn('morosidade', html.lower())

    def test_motor_de_compra_deduz_clientes_pushpull_e_estimulo(self):
        research = {
            'segmento': 'Marca/fabricante de moda praia para revendedoras, lojistas e multimarcas',
            'insight': 'revendedoras consultarem catálogo, grades e disponibilidade para repor peças',
            'motivo': 'Venda por WhatsApp e representantes, produto sazonal e de alto giro.',
        }
        raw = {'vende_para': '', 'resposta': 'WhatsApp', 'dor': 'perde vendas pela demora no atendimento'}
        motor = pg.motor_de_compra(research, raw)
        self.assertIn('lojistas', motor['quem'])
        self.assertIn('revendas', motor['quem'])
        self.assertIn('WhatsApp', motor['como_hoje'])
        self.assertRegex(motor['pushpull'].lower(), r'empurrad|puxad')
        self.assertIn('sazonalidade', motor['estimulo'])

    def test_potencial_de_digitalizacao_ganha_destaque(self):
        html = self._html('Empresa B2B de moda praia.')
        self.assertIn('POTENCIAL DE DIGITALIZAÇÃO: ONDE ISSO CAPTURA VALOR', html)
        self.assertIn('Quatro alavancas concretas', html)
        self.assertIn('Login, cadastro e tabela comercial por cliente', html)
        self.assertIn('Recompra entra sozinha 24/7', html)
        self.assertIn('Potencial operacional, não promessa', html)


class TestMqlCommitAntesDoSleepLongo(unittest.TestCase):
    """Incidente Kóche/Atalaia (29/06): grupo, HubSpot e ledger `enviado_lead`
    ficavam DEPOIS do sleep de 20 min. Se o processo caísse/fosse morto durante o
    respiro, o lead já tinha texto+PDF+pergunta, mas o grupo não recebia o aviso,
    o HubSpot não recebia o PDF/task e a fila ficava `mql_confirmed` com
    hubspot_attached/group_notified pendentes (exatamente o estado do Atalaia).

    Correção: registrar grupo+HubSpot+ledger ANTES do sleep; agenda vira etapa
    posterior idempotente/retomável."""

    def setUp(self):
        import inspect
        self.src = inspect.getsource(pg.main)

    def _idx(self, needle):
        i = self.src.find(needle)
        self.assertGreaterEqual(i, 0, f'não encontrei no main(): {needle}')
        return i

    def test_grupo_e_hubspot_e_ledger_antes_do_sleep_de_20min(self):
        sleep_longo = self._idx('time.sleep(QUESTION_TO_AGENDA_DELAY_SECONDS)')
        grupo = self._idx('post_group_with_rotation(group_summary, envios)')
        hubspot = self._idx('upload_pdf_to_hubspot(pdf, slug)')
        ledger = self._idx("append_processed(email, slug, 'enviado_lead'")
        registro = self._idx("'status':'enviado_lead'")
        # tudo que o time/CRM/ledger precisam acontece ANTES do respiro longo
        self.assertLess(grupo, sleep_longo, 'grupo deve ser avisado antes do sleep de 20 min')
        self.assertLess(hubspot, sleep_longo, 'HubSpot deve ser anexado antes do sleep de 20 min')
        self.assertLess(ledger, sleep_longo, 'ledger enviado_lead deve ser gravado antes do sleep de 20 min')
        self.assertLess(registro, sleep_longo, 'registro enviado_lead deve ser gravado antes do sleep de 20 min')

    def test_marcacao_da_fila_de_garantia_antes_do_sleep(self):
        sleep_longo = self._idx('time.sleep(QUESTION_TO_AGENDA_DELAY_SECONDS)')
        hubspot_step = self._idx("'hubspot_attached', 'done'")
        grupo_step = self._idx("'group_notified', 'done' if group_port")
        self.assertLess(hubspot_step, sleep_longo)
        self.assertLess(grupo_step, sleep_longo)

    def test_agenda_e_etapa_posterior_idempotente_e_apos_o_sleep(self):
        sleep_longo = self._idx('time.sleep(QUESTION_TO_AGENDA_DELAY_SECONDS)')
        agenda_decisao = self._idx('should_send_agenda(replied_before_question, replied')
        agenda_envio = self._idx("'text': agenda_msg")
        self.assertGreater(agenda_decisao, sleep_longo, 'a agenda só é decidida após o respiro de 20 min')
        self.assertGreater(agenda_envio, sleep_longo, 'a agenda só é enviada após o respiro de 20 min')
        # o registro persiste o estado retomável da agenda antes do sleep
        self.assertIn("'agenda_pending': True", self.src)
        self.assertIn("'question_sent_at': question_sent_at.isoformat()", self.src)
        self.assertIn("diag_record['agenda_pending'] = False", self.src)

    def test_ledger_enviado_lead_nao_depende_do_resultado_da_agenda(self):
        # o registro enviado_lead é montado antes do envio da agenda: agenda_response
        # começa None e é preenchido depois, sem bloquear grupo/HubSpot/ledger.
        registro = self._idx("'status':'enviado_lead'")
        agenda_envio = self._idx("'text': agenda_msg")
        self.assertLess(registro, agenda_envio)
        self.assertIn("'agenda_response': None", self.src)


class TestShouldSendAgendaIdempotente(unittest.TestCase):
    """A agenda é etapa posterior idempotente: não duplica em retomada e não passa
    por cima de quem respondeu."""

    def test_envia_quando_nao_respondeu_e_nao_enviada(self):
        send, reason = pg.should_send_agenda(False, False, agenda_already_sent=False)
        self.assertTrue(send)
        self.assertIn('enviar agenda', reason)

    def test_nao_envia_se_lead_respondeu_antes_da_pergunta(self):
        send, reason = pg.should_send_agenda(True, False, agenda_already_sent=False)
        self.assertFalse(send)
        self.assertIn('respondeu', reason)

    def test_nao_envia_se_lead_respondeu_depois_da_pergunta(self):
        send, reason = pg.should_send_agenda(False, True, agenda_already_sent=False)
        self.assertFalse(send)
        self.assertIn('respondeu', reason)

    def test_nao_reenvia_se_agenda_ja_enviada(self):
        send, reason = pg.should_send_agenda(False, False, agenda_already_sent=True)
        self.assertFalse(send)
        self.assertIn('já enviada', reason)


class TestPendingLeadWatchdogDiscordOnly(unittest.TestCase):
    """Entrada do lead avisa só Discord. Grupo WhatsApp recebe apenas o resumo
    final do process_gate_once, quando já decidiu MQL ou Não-MQL."""

    def test_watchdog_nao_tem_envio_de_grupo_na_entrada(self):
        self.assertFalse(hasattr(pending_watchdog, 'send_group_alert'))
        self.assertFalse(hasattr(pending_watchdog, 'GROUP_JID'))

    def test_form_facebook_continua_alertavel_no_discord(self):
        props = {'hs_object_source': 'FORM', 'recent_conversion_event_name': 'Facebook Lead Ads: FORM VENCEDOR'}
        self.assertTrue(pending_watchdog.is_form_signal(props))

    def test_numero_celular_antigo_nao_e_marcado_como_fixo(self):
        self.assertFalse(pending_watchdog.is_landline_br('553199626769'))
        self.assertTrue(pending_watchdog.is_landline_br('553133336769'))

    def test_non_mql_legit_bloqueia_base_teste_dummy(self):
        props = {'firstname':'joao','company':'Empresa Ltda.','phone':'+55(11) 99999-9999','hs_searchable_calculated_phone_number':'+55(11) 99999-9999'}
        self.assertTrue(non_mql.is_test_or_dummy_lead('joao@empresa.com.br', props, {'slug':'empresa-ltda-joao-formulario-teste'}))

    def test_envio_prioriza_variante_com_nono_digito(self):
        self.assertEqual(pg.phone_variants_with_optional_9('553199626769')[0], '5531999626769')
        self.assertEqual(pg.jid_from_phone('553199626769'), '5531999626769@c.us')


class TestDeteccaoAltaConsciencia(unittest.TestCase):
    """Detecção de lead de criativo Papel Rasgar / Comparativo / Adibão por
    origem/criativo do HubSpot e pelas respostas do próprio lead."""

    def test_detecta_por_criativo_papel_rasgar(self):
        props = {'hs_latest_source_data_2': 'Campanha Papel Rasgar | conjunto comparativo'}
        hit, termos = pg.detect_high_awareness_origin(props=props)
        self.assertTrue(hit)
        self.assertIn('papel rasgar', termos)

    def test_detecta_por_evento_de_conversao_vsl_comparativo(self):
        props = {'recent_conversion_event_name': 'VSL Comparativo Tray x Zydon'}
        hit, termos = pg.detect_high_awareness_origin(props=props)
        self.assertTrue(hit)
        self.assertIn('tray', termos)

    def test_detecta_por_resposta_do_lead_no_formulario(self):
        raw = {'resposta': 'Quero login e senha pro meu cliente revenda ver a tabela comercial dele',
               'dor': 'preciso de liberação de acesso por CNPJ'}
        hit, termos = pg.detect_high_awareness_origin(raw=raw)
        self.assertTrue(hit)
        self.assertIn('login e senha', termos)
        self.assertIn('tabela comercial', termos)

    def test_detecta_concorrente_b2c_na_pesquisa(self):
        research = {'motivo': 'Lead avaliando trocar Shopify/Nuvemshop por algo B2B'}
        hit, termos = pg.detect_high_awareness_origin(research=research)
        self.assertTrue(hit)
        self.assertTrue({'shopify', 'nuvemshop'} & set(termos))

    def test_lead_comum_nao_dispara(self):
        props = {'hs_latest_source': 'ORGANIC_SEARCH', 'hs_latest_source_data_2': 'google'}
        research = {'segmento': 'Distribuidora de autopeças'}
        raw = {'resposta': 'Vendo por WhatsApp e telefone', 'dor': 'pedido manual demora muito'}
        hit, termos = pg.detect_high_awareness_origin(props=props, research=research, raw=raw)
        self.assertFalse(hit)
        self.assertEqual(termos, [])

    def test_pergunta_abertura_fixa_para_diagnostico(self):
        self.assertEqual(pg.sdr_opening_question(True), PERGUNTA_OFICIAL)
        self.assertEqual(pg.sdr_opening_question(False), PERGUNTA_OFICIAL)


class TestPdfFundacaoB2B(unittest.TestCase):
    """PDF enriquecido com a fundação B2B vs B2C adaptado para lead de alta
    consciência. Explica processo/fundação no vocabulário certo, sem virar lista
    de features e sem usar 'tabela de preço'."""

    def setUp(self):
        self.html = _alta_consciencia_html()

    def test_pagina_fundacao_aparece(self):
        self.assertIn('FUNDAÇÃO B2B', self.html)
        self.assertIn('POR QUE B2B NÃO É B2C ADAPTADO', self.html)

    def test_vocabulario_obrigatorio_presente(self):
        for termo in ['login e senha', 'tabela comercial', 'análise', 'liberação',
                      'revenda', 'varejo', 'carteira de cliente', 'CNPJ', 'ERP']:
            self.assertIn(termo, self.html, termo)

    def test_nao_usa_tabela_de_preco_no_argumento_b2b(self):
        self.assertNotIn('tabela de preço', self.html.lower())
        self.assertNotIn('tabela de precos', self.html.lower())

    def test_cita_concorrentes_b2c(self):
        for marca in ['Tray', 'Shopify', 'Nuvemshop', 'Mercado Livre']:
            self.assertIn(marca, self.html, marca)

    def test_mantem_paginas_extras_e_fontes_grandes(self):
        n = self.html.count('<section class="page">')
        # alta consciência tem páginas extras: capa/sobre + fundação + perfil
        # + motor da compra + diagnóstico + ROI + integração = 7
        self.assertGreaterEqual(n, 7)
        self.assertEqual(n, 7)
        # fontes maiores já implementadas continuam valendo
        self.assertGreater(_css_font_size(gen.TEMPLATE, '.findings p'), 16)
        self.assertGreater(_css_font_size(gen.TEMPLATE, '.callout p'), 16)

    def test_lead_comum_nao_recebe_pagina_fundacao(self):
        d = batch_prepare.build_lead_dict({'name': 'Ana', 'empresa': 'Ceramica Ana Claudia',
                                           'erp': 'Bling', 'faturamento': 'de R$5 a R$10 milhões'})
        html = gen.build_html(d)
        self.assertNotIn('FUNDAÇÃO B2B', html)
        self.assertNotIn('POR QUE B2B NÃO É B2C ADAPTADO', html)
        # lead comum: capa/sobre + perfil + motor da compra + diagnóstico + ROI + integração = 6
        self.assertEqual(html.count('<section class="page">'), 6)


class TestMqlGapWatchdog(unittest.TestCase):
    """Falso alerta Vanyluz/com1@vanyluz.com: o watchdog alertava 'MQL sem
    WhatsApp' durante a janela entre o marcador idempotente
    `mql_diagnostico_em_andamento` (gravado antes do 1º /send) e o `enviado_lead`
    final, porque esse status não estava em OK_STATUSES. O telefone
    11910883756 nunca foi inválido — só não havia status reconhecido."""

    @classmethod
    def setUpClass(cls):
        path = '/root/.hermes/scripts/zydon_mql_gap_watchdog.py'
        if not os.path.exists(path):
            raise unittest.SkipTest('watchdog não encontrado neste ambiente')
        spec = importlib.util.spec_from_file_location('zydon_mql_gap_watchdog', path)
        cls.wd = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.wd)  # main() guard impede chamada de rede no import

    def test_diagnostico_em_andamento_eh_status_ok(self):
        self.assertIn('mql_diagnostico_em_andamento', self.wd.OK_STATUSES)

    def test_inflight_nao_alerta_como_issue(self):
        # MQL ainda na cadência texto->PDF->agenda: só tem o marcador in-flight.
        self.assertEqual(self.wd.classify({'mql_diagnostico_em_andamento'}), 'ok')
        now = self.wd.dt.datetime(2026, 6, 28, 18, 20, tzinfo=self.wd.dt.timezone.utc)
        started = now - self.wd.dt.timedelta(minutes=20)
        self.assertEqual(self.wd.classify({'mql_diagnostico_em_andamento'}, started, now), 'ok')

    def test_inflight_antigo_vira_travado(self):
        now = self.wd.dt.datetime(2026, 6, 28, 18, 50, tzinfo=self.wd.dt.timezone.utc)
        started = now - self.wd.dt.timedelta(minutes=31)
        self.assertEqual(self.wd.classify({'mql_diagnostico_em_andamento'}, started, now), 'stalled')

    def test_status_final_vence_inflight_antigo(self):
        now = self.wd.dt.datetime(2026, 6, 28, 18, 50, tzinfo=self.wd.dt.timezone.utc)
        started = now - self.wd.dt.timedelta(minutes=90)
        statuses = {'mql_diagnostico_em_andamento', 'enviado_lead'}
        self.assertEqual(self.wd.classify(statuses, started, now), 'ok')

    def test_conversao_manual_mql_com_task_vence_inflight_antigo(self):
        # Caso Delícias do Interior: era Não-MQL, lead respondeu, diagnóstico foi
        # enviado pelo mesmo chip e task/negócio do SDR dono foram criados. O
        # marcador in-flight antigo não pode continuar gerando alerta travado.
        now = self.wd.dt.datetime(2026, 6, 28, 22, 30, tzinfo=self.wd.dt.timezone.utc)
        started = now - self.wd.dt.timedelta(minutes=105)
        statuses = {
            'enviado_nao_mql_legitimo',
            'nao_mql_grupo',
            'mql_diagnostico_em_andamento',
            'manual_nao_mql_convertido_mql',
            'mql_convertido_task_sdr',
        }
        self.assertEqual(self.wd.classify(statuses, started, now), 'ok')

    def test_sem_registro_continua_alertando(self):
        # MQL realmente sem tratamento deve seguir gerando alerta legítimo.
        self.assertEqual(self.wd.classify(set()), 'issue')

    def test_conflito_nao_mql_preservado(self):
        self.assertEqual(self.wd.classify({'nao_mql_grupo'}), 'conflict')


class TestErpGoliveNativo(unittest.TestCase):
    """Rodapé de integração do PDF usa o prazo médio de go-live por ERP nativo,
    não mais '7 a 14 dias' fixo para todos. Olist/Tiny e Bling: 30 dias; Omie:
    45 dias; Sankhya: 45 a 60 dias."""

    def _erp(self, erp):
        return batch_prepare.build_lead_dict({'name': 'Ana', 'empresa': 'Empresa Teste',
                                              'erp': erp, 'faturamento': 'de R$5 a R$10 milhões'})

    def _assert_nativo(self, d, prazo, erp):
        self.assertEqual(d['erp_golive'], prazo, erp)
        self.assertEqual(d['erp_integ'], 'Integração nativa', erp)
        self.assertEqual(d['erp_dev'], 'Não (nativo)', erp)
        self.assertIn(prazo, d['erp_line'], erp)
        self.assertNotIn('7 a 14 dias', d['erp_line'], erp)

    def test_olist_e_tiny_30_dias(self):
        for erp in ['Olist', 'Olist (Tiny)', 'Tiny']:
            self._assert_nativo(self._erp(erp), '30 dias', erp)

    def test_bling_30_dias(self):
        self._assert_nativo(self._erp('Bling'), '30 dias', 'Bling')

    def test_sankhya_45_a_60_dias(self):
        self._assert_nativo(self._erp('Sankhya'), '45 a 60 dias', 'Sankhya')

    def test_omie_45_dias(self):
        self._assert_nativo(self._erp('Omie'), '45 dias', 'Omie')

    def test_erp_sob_projeto_continua_nao_nativo(self):
        d = self._erp('Outro')
        self.assertEqual(d['erp_integ'], 'Integração sob projeto')
        self.assertNotEqual(d['erp_dev'], 'Não (nativo)')
        self.assertNotIn('7 a 14 dias', d['erp_line'])


if __name__ == '__main__':
    unittest.main()
