import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'roteiro_panel.py'
BEST = Path(__file__).resolve().parents[1] / 'controle' / 'roteiro_best_practices.json'

def load_mod():
    spec = importlib.util.spec_from_file_location('roteiro_panel', MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class RoteiroPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_project_is_standalone_not_channel(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('roteiro.zydon.com.br', s)
        self.assertIn('Roteiro Comercial Zydon', s)
        self.assertNotIn('APP_ROUTES', s)
        self.assertNotIn('channel_panel_v2', s)

    def test_comercial_tecnica_and_intro_stages(self):
        self.assertEqual(self.mod.INTRODUCTION_STAGE_ID, '1269308723')
        self.assertEqual(self.mod.PRESENTATION_STAGE_ID, '990617426')
        self.assertEqual(self.mod.TECHNICAL_STAGE_ID, '1269308724')
        for stage_id in ['1269308723', '1269710168', '990617426', '1269308724', '984052831', '1213797817', '984052834']:
            self.assertIn(stage_id, self.mod.ROTEIRO_STAGES)
        self.assertNotIn('984052835', self.mod.ROTEIRO_STAGES)  # perdido não entra no Roteiro
        self.assertNotIn('1269308723', self.mod.PRESENTATION_STAGES)

    def test_roteiro_only_lucas_requested_executive_owners(self):
        self.assertEqual(self.mod.ROTEIRO_EXECUTIVE_OWNER_LABELS, {
            '86020066': 'João Vitor',
            '89412201': 'Samara',
            '82229596': 'Edimilson',
            '89459433': 'Ítalo',
        })
        src = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn("'propertyName':'hubspot_owner_id','operator':'IN'", src)
        self.assertIn('Introdução em diante', src)
        self.assertIn('João Vitor, Samara, Edimilson ou Ítalo', src)

    def test_intro_uses_challenger_sale_path(self):
        ids = [p['id'] for p in self.mod.dynamic_phases({}, self.mod.INTRODUCTION_STAGE_ID)]
        self.assertEqual(ids, [
            'challenger_aquecimento',
            'challenger_reestruturacao',
            'challenger_angustia',
            'challenger_impacto_emocional',
            'challenger_novo_caminho',
        ])
        txt = ' '.join(str(x) for x in self.mod.challenger_intro_context()['challenges'])
        for token in ['Resistência do time comercial', 'Condições personalizadas', 'Pedidos manuais', 'Integração com ERP', 'crédito']:
            self.assertIn(token, txt)

    def test_comercial_tecnica_keep_our_solution_path(self):
        intro_ids = [p['id'] for p in self.mod.dynamic_phases({}, self.mod.INTRODUCTION_STAGE_ID)]
        commercial_ids = [p['id'] for p in self.mod.dynamic_phases({}, self.mod.PRESENTATION_STAGE_ID)]
        self.assertIn('diagnostico', commercial_ids)
        self.assertIn('cliente_vitrine', commercial_ids)
        self.assertNotEqual(intro_ids, commercial_ids)
        self.assertNotIn('challenger_aquecimento', commercial_ids)

    def test_roteiro_visibility_rule(self):
        old = self.mod.load_users
        try:
            self.mod.load_users = lambda: {
                'rafael': {'view_all': True},
                'lucas_resende': {'view_all': True},
                'mariana': {'view_all': True},
                'growth_lead': {'role': 'growth_leader'},
                'breno': {'hubspot_owner_id': '86265630'},
                'sem_owner': {'role': 'executivo'},
            }
            self.assertTrue(self.mod.roteiro_can_view_all('rafael'))
            self.assertTrue(self.mod.roteiro_can_view_all('lucas_resende'))
            self.assertTrue(self.mod.roteiro_can_view_all('growth_lead'))
            self.assertFalse(self.mod.roteiro_can_view_all('mariana'))
            self.assertEqual(self.mod.roteiro_owner_id_for_user('breno'), '86265630')
            self.assertEqual(self.mod.roteiro_owner_id_for_user('sem_owner'), '')
        finally:
            self.mod.load_users = old

    def test_form_data_humanization(self):
        props = {
            'vende_em_loja_virtual_': 'sim',
            'quantos_vendedores_internos_sua_empresa_possui': '6_a_20_',
            'principais_dores': 'vendedores_gastam_tempo_só_tirando_pedido',
            'qual_erp_utiliza_': 'Bling',
        }
        data = {x['label']: x['value'] for x in self.mod.build_form_data(props)}
        self.assertEqual(data['Vende em loja virtual'], 'Sim')
        self.assertEqual(data['Vendedores internos'], '6 a 20')
        self.assertEqual(data['ERP utilizado'], 'Bling')

    def test_dynamic_plan_with_sales_team_includes_vendedor(self):
        props = {'quantos_vendedores_internos_sua_empresa_possui': '6_a_20_'}
        ids = [p['id'] for p in self.mod.dynamic_phases(props)]
        self.assertIn('vendedor', ids)

    def test_dynamic_plan_without_sales_team_excludes_vendedor(self):
        props = {'quantos_vendedores_internos_sua_empresa_possui': '0'}
        ids = [p['id'] for p in self.mod.dynamic_phases(props)]
        self.assertNotIn('vendedor', ids)
        self.assertIn('cliente_vitrine', ids)
        self.assertIn('admin', ids)

    def test_big_four_and_whatsapp_change_plan(self):
        props = {'qual_erp_utiliza_': 'Olist (Tiny)', 'de_qual_forma_mais_vende_hoje_em_dia': 'WhatsApp'}
        ids = [p['id'] for p in self.mod.dynamic_phases(props)]
        self.assertIn('erp', ids)
        self.assertIn('whatsapp', ids)
        focus = ' '.join(self.mod.build_guide_focus(props))
        self.assertIn('Big Four', focus)
        self.assertIn('WhatsApp', focus)

    def test_best_practices_db(self):
        self.assertTrue(BEST.exists())
        data = self.mod.load_best_practices()
        txt = ' '.join([str(x) for x in data])
        self.assertIn('Challenger', txt)
        self.assertIn('Ensinar', txt)
        self.assertIn('Adaptar', txt)
        self.assertIn('Controlar', txt)

    def test_ui_is_wizard_with_questions_before_demo(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        for token in ['Perguntas antes de demonstrar', 'Próximo', 'Marcar fase concluída', 'Como adaptar essa fase', 'Next > Next']:
            self.assertIn(token, s)

    def test_gamified_buttons_are_wired(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        for token in [
            'function toggleTheme()',
            "localStorage.setItem('roteiroTheme',theme)",
            'onclick="toggleTheme()"',
            "onclick=\"setLevelFilter('intro')\"",
            "onclick=\"setLevelFilter('solution')\"",
            "onclick=\"start()\"",
            "onclick=\"toggleObj(${i})\"",
            "onclick=\"mark()\"",
            "theme-light",
        ]:
            self.assertIn(token, s)

    def test_strip_html(self):
        self.assertEqual(self.mod.strip_html('<p>Olá <b>mundo</b></p>'), 'Olá mundo')
        self.assertEqual(self.mod.strip_html('<style>x{}</style><script>a()</script>Texto'), 'Texto')
        self.assertEqual(self.mod.strip_html('Linha 1 &amp; linha&nbsp;2   fim'), 'Linha 1 & linha 2 fim')
        self.assertEqual(self.mod.strip_html(None), '')

    def test_engagement_intel_filters_diagnostic_and_followup(self):
        records = [
            {'type': 'notes', 'title': 'Nota', 'text': 'Diagnóstico SDR enviado: cliente é MQL e usa Bling.', 'ts': '2026-06-20T10:00:00Z'},
            {'type': 'tasks', 'title': 'Ligar para o lead', 'text': 'Combinar próximo passo e enviar proposta.', 'ts': '2026-06-22T09:00:00Z'},
            {'type': 'calls', 'title': 'Ligação', 'text': 'Cliente atendeu, falou sobre o estoque.', 'ts': '2026-06-21T08:00:00Z'},
        ]
        out = self.mod.build_engagement_intel(records)
        diag = ' '.join(i['text'] for i in out['diagnosticSummary'])
        foll = ' '.join(i['text'] for i in out['followUps'])
        self.assertIn('Diagnóstico SDR', diag)
        self.assertNotIn('Cliente atendeu', diag)
        self.assertIn('próximo passo', foll)
        self.assertIn('proposta', foll)
        # timeline traz tudo, mais recente primeiro
        self.assertEqual(len(out['hubspotTimeline']), 3)
        self.assertEqual(out['hubspotTimeline'][0]['ts'], '22/06/2026')

    def test_internet_context_from_mocked_html(self):
        html_doc = (
            '<html><head><title>Distribuidora ACME — Atacado B2B</title>'
            '<meta name="description" content="Maior distribuidora de bebidas do Sul.">'
            '</head><body>x</body></html>'
        )
        ctx = self.mod.parse_homepage(html_doc, 'https://acme.com.br')
        self.assertEqual(ctx['title'], 'Distribuidora ACME — Atacado B2B')
        self.assertEqual(ctx['description'], 'Maior distribuidora de bebidas do Sul.')
        self.assertEqual(ctx['url'], 'https://acme.com.br')
        self.assertEqual(ctx['source'], 'https://acme.com.br')
        self.assertEqual(self.mod.parse_homepage('<html><body>nada</body></html>', 'https://x.com'), {})

    def test_company_url_normalization(self):
        self.assertEqual(self.mod._company_url({'domain': 'acme.com.br'}), 'https://acme.com.br')
        self.assertEqual(self.mod._company_url({'website': 'http://loja.acme.com'}), 'http://loja.acme.com')
        self.assertEqual(self.mod._company_url({}), '')

    def test_ui_has_enrichment_sections(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        for token in ['Diagnóstico já enviado', 'Follow-ups importantes', 'Contexto web', 'diagBlock', 'followBlock', 'webBlock']:
            self.assertIn(token, s)

    def test_start_presentation_uses_intel_and_phases_when_mocked(self):
        old_deals = self.mod.presentation_deals
        old_intel = self.mod.deal_intelligence
        try:
            self.mod.presentation_deals = lambda uid: {'deals': [{'dealId': '1', 'dealName': 'ACME', 'stageLabel': 'Apresentação Técnica'}]}
            self.mod.deal_intelligence = lambda uid, did, stage_id='': {'hasForm': True, 'phases': [{'id': 'a'}], 'leadChips': []}
            out = self.mod.start_presentation('rafael', '1')
            self.assertTrue(out['ok'])
            self.assertEqual(out['run']['phaseCount'], 1)
            self.assertIn('intel', out)
        finally:
            self.mod.presentation_deals = old_deals
            self.mod.deal_intelligence = old_intel

    def test_post_meeting_template_has_required_fields(self):
        tpl = self.mod.post_meeting_template()
        keys = {f['key'] for f in tpl['fields']}
        for k in ['diagnostico_confirmado', 'telas_demonstradas', 'valor_percebido', 'objecoes_riscos', 'proximo_passo', 'quem_participa']:
            self.assertIn(k, keys)
        # rascunho local, não escreve no HubSpot
        self.assertIn('HubSpot', tpl['note'])

    def test_start_presentation_includes_post_meeting_template(self):
        old_deals = self.mod.presentation_deals
        old_intel = self.mod.deal_intelligence
        try:
            self.mod.presentation_deals = lambda uid: {'deals': [{'dealId': '1', 'dealName': 'ACME', 'stageLabel': 'Apresentação Técnica'}]}
            self.mod.deal_intelligence = lambda uid, did, stage_id='': {'hasForm': True, 'phases': [{'id': 'fechamento'}], 'leadChips': []}
            out = self.mod.start_presentation('rafael', '1')
            self.assertIn('postMeetingTemplate', out)
            self.assertTrue(out['postMeetingTemplate']['fields'])
        finally:
            self.mod.presentation_deals = old_deals
            self.mod.deal_intelligence = old_intel

    def test_owner_label_prefers_local_then_hubspot_owners_then_fallback(self):
        old = self.mod.load_users
        try:
            self.mod.load_users = lambda: {'breno': {'hubspot_owner_id': '86265630', 'name': 'Breno Local'}}
            # cadastro local vence
            self.assertEqual(self.mod.owner_label('86265630', {'86265630': 'Breno HubSpot'}), 'Breno Local')
            # HubSpot Owners resolve quando não há cadastro local nem label fixo do Roteiro
            self.assertEqual(self.mod.owner_label('70000001', {'70000001': 'Fulano HubSpot'}), 'Fulano HubSpot')
            # Labels fixos dos executivos do Roteiro vencem fallback/API sem escopo de Owners
            self.assertEqual(self.mod.owner_label('89412201', {'89412201': 'Fulano HubSpot'}), 'Samara')
            # fallback quando ninguém resolve
            self.assertEqual(self.mod.owner_label('99999999', {}), 'Owner 99999999')
            self.assertEqual(self.mod.owner_label(''), 'Sem proprietário')
        finally:
            self.mod.load_users = old

    def test_hubspot_owner_labels_from_mocked_api(self):
        old_req = self.mod.hs_request
        self.mod._OWNER_LABEL_CACHE.clear()
        try:
            self.mod.hs_request = lambda method, path, token, payload=None, timeout=30: {
                'results': [
                    {'id': '89412201', 'firstName': 'Maria', 'lastName': 'Silva', 'email': 'maria@zydon.com.br'},
                    {'id': '70000001', 'firstName': '', 'lastName': '', 'email': 'so.email@zydon.com.br'},
                ],
                'paging': {},
            }
            labels = self.mod.hubspot_owner_labels('fake-token')
            self.assertEqual(labels['89412201'], 'Maria Silva')
            self.assertEqual(labels['70000001'], 'so.email@zydon.com.br')
            # token vazio nunca chama API
            self.assertEqual(self.mod.hubspot_owner_labels(''), {})
        finally:
            self.mod.hs_request = old_req
            self.mod._OWNER_LABEL_CACHE.clear()

    def test_web_research_when_no_website(self):
        ctx = self.mod.fetch_internet_context({'name': 'Distribuidora ACME', 'city': 'Curitiba', 'state': 'PR', 'industry': 'Atacado'})
        self.assertTrue(ctx['webSearchQueries'])
        self.assertTrue(ctx['webResearchHints'])
        blob = ' '.join(ctx['webSearchQueries'])
        self.assertIn('Distribuidora ACME', blob)
        self.assertIn('LinkedIn', blob)
        self.assertIn('CNPJ', blob)
        self.assertEqual(self.mod.fetch_internet_context({}).get('webSearchQueries'), [])

    def test_research_angles_from_homepage(self):
        ctx = {'title': 'ACME Distribuidora Atacado', 'description': 'Catálogo de bebidas para revenda.'}
        angles = ' '.join(self.mod.build_research_angles({'industry': 'Atacado'}, ctx))
        self.assertIn('distribui', angles.lower())
        self.assertTrue(self.mod.build_research_angles({}, {}))

    def test_ui_has_presentation_mode_and_meeting_stages(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        for token in ['Modo apresentação', 'Sair do modo apresentação', 'Preparação', 'Reunião', 'Pós-reunião',
                      'postMeetingTemplate', 'togglePresent', 'prepView', 'postView', 'stageView', 'researchAngles', 'webSearchQueries']:
            self.assertIn(token, s)

if __name__ == '__main__':
    unittest.main()
