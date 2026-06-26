import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'roteiro_panel.py'


def load_mod():
    spec = importlib.util.spec_from_file_location('roteiro_panel', MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RoteiroPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_project_is_standalone_not_channel_route(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('Roteiro Comercial Zydon', s)
        self.assertIn('roteiro.zydon.com.br', s)
        self.assertIn('PDF_STORY_SECTIONS', s)
        self.assertIn('/api/start-presentation', s)
        self.assertIn('ROTEIRO_VIEW_ALL_UIDS', s)
        self.assertNotIn('APP_ROUTES', s)
        self.assertNotIn('channel_panel_v2', s)
        self.assertEqual(self.mod.PRESENTATION_STAGE_ID, '990617426')
        self.assertGreaterEqual(len(self.mod.default_roteiro()['sections']), 10)

    def test_roteiro_specific_visibility_rule(self):
        old = self.mod.load_users
        try:
            self.mod.load_users = lambda: {
                'rafael': {'admin': True, 'view_all': True},
                'lucas_resende': {'view_all': True},
                'mariana': {'view_all': True},
                'breno': {'hubspot_owner_id': '86265630'},
                'growth_lead': {'role': 'growth_leader'},
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

    def test_owner_label_never_returns_bare_number(self):
        old = self.mod.load_users
        try:
            self.mod.load_users = lambda: {
                'breno': {'name': 'Breno', 'hubspot_owner_id': '86265630'},
                'ec_novo': {'name': 'Carla', 'hubspot_owner_id': '99999999'},
            }
            # nome fixo conhecido
            self.assertEqual(self.mod.owner_label('86265630'), 'Breno')
            # nome resolvido pela carteira HubSpot do usuário
            self.assertEqual(self.mod.owner_label('99999999'), 'Carla')
            # desconhecido vira "Owner <id>", nunca número solto
            self.assertEqual(self.mod.owner_label('76764091'), 'Owner 76764091')
            self.assertEqual(self.mod.owner_label(''), 'Sem proprietário')
        finally:
            self.mod.load_users = old

    def test_ui_is_guided_journey_not_worm_grid(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        # jornada guiada / cockpit de execução
        self.assertIn('Iniciar apresentação', s)
        self.assertIn('startPresentation', s)
        self.assertIn('function cockpit', s)
        self.assertIn('function briefing', s)
        self.assertIn('Voltar à fila', s)
        # painel de preparação separado em três seções
        self.assertIn('Pesquisa', s)
        self.assertIn('Hipóteses', s)
        self.assertIn('Perguntas de descoberta', s)
        # editor existe mas é secundário (toggle), não domina a tela
        self.assertIn('toggleEditor', s)
        # a grade de tampinhas/minhoca foi removida da UI
        self.assertNotIn('class="worm"', s)
        self.assertNotIn('tampinhas', s)

    def test_auth_uses_roteiro_cookie_and_callback(self):
        self.assertEqual(self.mod.SESSION_COOKIE, 'zydon_roteiro_session')
        self.assertEqual(self.mod.oauth_redirect_uri(None), 'https://roteiro.zydon.com.br/oauth/callback')
        self.assertIn('@zydon.com.br', self.mod.auth_page())

    def test_roteiro_save_load_roundtrip(self):
        old_file = self.mod.ROTEIRO_FILE
        old_audit = self.mod.ROTEIRO_AUDIT_FILE
        tmp = Path('/tmp/roteiro_panel_test.json')
        audit = Path('/tmp/roteiro_panel_test.jsonl')
        try:
            self.mod.ROTEIRO_FILE = tmp
            self.mod.ROTEIRO_AUDIT_FILE = audit
            for f in (tmp, audit):
                if f.exists(): f.unlink()
            saved = self.mod.roteiro_save('rafael', {'title':'Roteiro X','subtitle':'Sub','sections':[{'id':'a','title':'Abertura','body':'Diagnóstico'}]})
            self.assertTrue(saved['ok'])
            loaded = self.mod.roteiro_load()
            self.assertEqual(loaded['title'], 'Roteiro X')
            self.assertEqual(loaded['sections'][0]['body'], 'Diagnóstico')
            self.assertTrue(audit.exists())
        finally:
            self.mod.ROTEIRO_FILE = old_file
            self.mod.ROTEIRO_AUDIT_FILE = old_audit
            for f in (tmp, audit):
                if f.exists(): f.unlink()

if __name__ == '__main__':
    unittest.main()
