import importlib.util
import json
import time
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'channel_panel_v2.py'


def load_mod():
    spec = importlib.util.spec_from_file_location('channel_panel_v2', MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ChannelV2CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_screen_routes_are_declared_for_direct_urls(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn("APP_ROUTES", s)
        for route in ("/conversas", "/foco", "/gestao"):
            self.assertIn(route, s)

    def test_initial_view_mode_from_path_exists(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('initialViewModeFromPath', s)
        self.assertIn("history.pushState", s)

    def test_institutional_timeline_does_not_show_empty_when_ledger_exists(self):
        conv = '4610::5519993361631@s.whatsapp.net'  # Cris Mazzer / Ana / Gustavo: caso reportado
        msgs = self.mod.messages_for('rafael', conv)
        self.assertGreaterEqual(len(msgs), 1)
        self.assertTrue(any((m.get('text') or m.get('mediaName') or m.get('mediaType')) for m in msgs))
        self.assertTrue(all(m.get('fromMe') is False or self.mod.is_institutional_dispatch_msg(m) for m in msgs))

    def test_messages_for_institutional_chat_is_fast(self):
        conv = '4610::5519993361631@s.whatsapp.net'
        t0 = time.time()
        msgs = self.mod.messages_for('rafael', conv)
        elapsed = time.time() - t0
        self.assertGreaterEqual(len(msgs), 1)
        self.assertLess(elapsed, 1.5)

    def test_communicator_personal_outbound_is_not_exposed(self):
        # Amostra conhecida de comunicador: valida a regra crítica sem varrer centenas de chats.
        sample = '4610::5519993361631@s.whatsapp.net'
        msgs = self.mod.messages_for('rafael', sample)
        bad = [m for m in msgs if m.get('fromMe') and not self.mod.is_institutional_dispatch_msg(m)]
        self.assertEqual(bad, [], f'personal outbound exposed in {sample}')

    def test_frontend_does_not_render_empty_on_message_fetch_failure(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('Não consegui carregar mensagens agora', s)
        self.assertIn('catch(e)', s)
        self.assertNotIn('drawTimeline(true);\n  if(!(msgs||[]).length)', s)

    def test_inbox_timeout_is_not_shown_as_auth_failure(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('err.status=r.status', s)
        self.assertIn('err.timeout=true', s)
        self.assertIn('const isAuthError=e && (e.status===401 || e.status===403)', s)
        self.assertIn("api('/api/conversations',{timeoutMs: opts.fast?9000:20000})", s)
        self.assertIn("api('/api/conversations-safe',{timeoutMs:12000})", s)
        self.assertIn('Não consegui carregar o inbox agora', s)
        self.assertIn('Não é logout. Sua sessão continua válida', s)

    def test_analytics_routes_do_not_poll_inbox_in_background(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('não recalcule a inbox inteira em background', s)
        self.assertIn("viewMode==='foco'||viewMode==='gestao'", s)

    def test_cache_invalidation_removes_message_and_marks_conversation_cache_stale(self):
        conv = '4610::5519993361631@s.whatsapp.net'
        self.mod.MESSAGES_API_CACHE[('rafael', conv)] = {'ts': time.time(), 'body': b'old'}
        self.mod.MESSAGES_API_CACHE[('sarah', conv)] = {'ts': time.time(), 'body': b'old'}
        self.mod.CONVERSATION_PERMISSION_CACHE[('rafael', conv)] = {'ts': time.time(), 'allowed': True}
        self.mod.CONVERSATION_PERMISSION_CACHE[('sarah', conv)] = {'ts': time.time(), 'allowed': True}
        self.mod.CONVERSATIONS_API_CACHE['__view_all__'] = {'ts': time.time(), 'conversations': [{'id': conv}]}
        self.mod.CONVERSATIONS_API_CACHE['rafael'] = {'ts': time.time(), 'conversations': [{'id': conv}]}
        self.mod.invalidate_channel_api_cache('rafael', conv)
        self.assertNotIn(('rafael', conv), self.mod.MESSAGES_API_CACHE)
        self.assertNotIn(('sarah', conv), self.mod.MESSAGES_API_CACHE)
        self.assertNotIn(('rafael', conv), self.mod.CONVERSATION_PERMISSION_CACHE)
        self.assertNotIn(('sarah', conv), self.mod.CONVERSATION_PERMISSION_CACHE)
        self.assertIn('__view_all__', self.mod.CONVERSATIONS_API_CACHE)
        self.assertIn('rafael', self.mod.CONVERSATIONS_API_CACHE)
        self.assertEqual(self.mod.CONVERSATIONS_API_CACHE['__view_all__']['ts'], 0)
        self.assertEqual(self.mod.CONVERSATIONS_API_CACHE['rafael']['ts'], 0)

    def test_management_dispatch_stats_chart_by_day_and_chip(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn("def dispatch_stats(uid='rafael', days=14):", s)
        self.assertIn("if path=='/api/dispatch-stats'", s)
        self.assertIn("api('/api/dispatch-stats?days=14')", s)
        self.assertIn('Disparos WhatsApp por dia · por chip', s)
        self.assertIn('class="dispatch-col', s)
        self.assertIn('class="dispatch-stack"', s)
        self.assertIn('function setDispatchChip(port)', s)
        self.assertIn('function setDispatchDay(day)', s)
        self.assertIn('function previewDispatchDay(day)', s)
        self.assertIn('function openDispatchModal(day, port', s)
        self.assertIn('id="dispatchModal"', s)
        self.assertIn('Abrir conversa', s)
        self.assertIn('deepConv=qs.get', s)
        self.assertIn('if(deepConv && !deepConvOpened)', s)
        self.assertNotIn('deepConvOpened && convs.some', s)
        self.assertIn('Colunas verticais empilhadas', s)
        self.assertIn('controle/wpp_envios.json', s)
        stats = self.mod.dispatch_stats('rafael', 14)
        self.assertTrue(stats.get('ok'))
        self.assertIn('days', stats)
        self.assertIn('chips', stats)
        sample_events = [ev for day in stats['days'] for events in (day.get('details') or {}).values() for ev in events]
        self.assertTrue(sample_events)
        self.assertIn('/conversas?conv=', sample_events[0].get('link',''))
        self.assertIn('message', sample_events[0])
        self.assertLessEqual(len(stats['days']), 14)
        self.assertIsInstance(stats.get('total'), int)

    def test_hubspot_context_exposes_contact_and_deal_links(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('function hubspotRecordUrl(kind,id)', s)
        self.assertIn("kind==='deal'?'0-3':'0-1'", s)
        self.assertIn('https://app.hubspot.com/contacts/48590774/record/', s)
        self.assertIn('hubspotRecordLinks(c,data)', s)
        self.assertIn('target="_blank" rel="noopener noreferrer"', s)
        self.assertIn('c.hubspotContactId=ct.id', s)
        self.assertIn('c.hubspotDealId=d.id', s)

    def test_hubspot_context_is_lazy_after_timeline(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('timeline primeiro', s)
        self.assertIn('setTimeout(()=>{ if(active===id', s)
        self.assertNotIn('if(!hsCache[c.id]) loadHubspot(c);', s)

    def test_message_endpoint_has_no_global_lock_or_aggressive_focus_reload(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('stale-while-revalidate', s)
        self.assertNotIn('got_lock=MESSAGES_API_LOCK.acquire', s)
        self.assertNotIn("window.addEventListener('focus',()=>{ loadAll", s)
        self.assertIn('},30000);', s)
        self.assertGreaterEqual(self.mod.MESSAGES_API_TTL, 12)
        self.assertIn('AbortController', s)
        self.assertIn('timeoutMs', s)

    def test_institutional_permission_uses_fast_ledger_not_load_ports(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        start = s.index('def _institutional_dispatch_rows_for_chat')
        end = s.index('def institutional_conv_readonly_allowed', start)
        block = s[start:end]
        self.assertIn('wpp_envios_fastlane_events', block)
        self.assertNotIn('load_ports(', block)

    def test_group_bridge_port_does_not_create_communicator_mirror(self):
        old_file = self.mod.WPP_ENVIOS_FILE
        tmp = Path('/tmp/channel_v2_group_bridge_no_mirror.json')
        row = {
            'date_tz': '2026-06-26T15:31:00-03:00',
            'status': 'enviado_lead',
            'to': '5511954151000@c.us',
            'bridge_port': 4601,
            'group_bridge_port': 4606,
            'owner_id': '88063842',
            'text': 'mensagem enviada ao lead pela Sarah',
            'group_summary': 'resumo interno no grupo',
        }
        try:
            tmp.write_text(json.dumps({'envios': [row]}), encoding='utf-8')
            self.mod.WPP_ENVIOS_FILE = tmp
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            self.mod._WPP_FASTLANE_CACHE = {}
            sarah_events = self.mod.wpp_envios_fastlane_events([4601], max_age_hours=24*3650)
            comm_events = self.mod.wpp_envios_fastlane_events([4606], max_age_hours=24*3650)
            self.assertEqual(len(sarah_events), 1)
            self.assertEqual(sarah_events[0].get('port'), 4601)
            self.assertEqual(comm_events, [])
            self.assertNotIn('institutionalMirror', json.dumps(sarah_events))
        finally:
            self.mod.WPP_ENVIOS_FILE = old_file
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            self.mod._WPP_FASTLANE_CACHE = {}
            if tmp.exists():
                tmp.unlink()

    def test_loading_indicator_is_delayed_for_fast_message_requests(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('loadingTimer=setTimeout', s)
        self.assertIn('},350);', s)
        self.assertIn('clearTimeout(loadingTimer)', s)

    def test_open_conversation_updates_active_card_without_full_list_redraw(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('data-conv=', s)
        self.assertIn('function updateActiveCard', s)
        start = s.index('async function openConv')
        end = s.index('/* ---- CH-018', start)
        block = s[start:end]
        self.assertIn('updateActiveCard(id)', block)
        self.assertNotIn('drawCards();', block)

    def test_mobile_composer_has_balanced_inner_message_box(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('@media (max-width:820px)', s)
        self.assertIn('.cbox textarea{min-height:52px', s)
        self.assertIn('font-size:14.5px', s)
        self.assertIn('.send{height:40px', s)
        self.assertIn('.attach-btn{width:40px;height:40px}', s)
        self.assertNotIn('.cbox textarea{min-height:64px', s)

    def test_login_uses_channel_brand_palette_not_green_button(self):
        html = self.mod.login_page_html({'client_id': 'x', 'client_secret': 'y'})
        self.assertIn('background:#0B0F0C', html)
        self.assertIn('color:#CDEB00', html)
        self.assertNotIn('background:#1F3D2B;color:#FFFFFF', html)
        self.assertIn('width:min(100%,480px)', html)

    def test_auth_session_ttls_are_business_safe(self):
        self.assertGreaterEqual(self.mod.SESSION_TTL, 7 * 24 * 3600)
        self.assertGreaterEqual(self.mod.OAUTH_STATE_TTL, 3600)


if __name__ == '__main__':
    unittest.main()
