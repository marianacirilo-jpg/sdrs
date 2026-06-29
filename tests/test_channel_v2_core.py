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
        self.assertIn("applyTheme(currentTheme(), {visualOnly:true})", s)
        self.assertIn("function analyticsModeActive()", s)
        self.assertIn("const visualTheme=analyticsModeActive()?'dark':t", s)
        self.assertIn("app.classList.toggle('analytics-mode', analyticsMode)", s)

    def test_analytics_pages_are_dark_end_to_end_not_mixed_theme(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('[data-theme="dark"] .app.analytics-mode .list,[data-theme="dark"] .app.analytics-mode .cards{background:#07100B}', s)
        self.assertIn('[data-theme="dark"] .app.analytics-mode .zone-head,[data-theme="dark"] .app.analytics-mode .list-sub{background:#0B140F;border-bottom-color:rgba(205,235,0,.07)}', s)
        self.assertIn('[data-theme="dark"] .app.analytics-mode .mgmt-card,[data-theme="dark"] .app.analytics-mode .mgmt-section', s)
        self.assertIn('[data-theme="dark"] .app.analytics-mode .cad-board', s)
        self.assertNotIn('.cad-board{border:1px solid rgba(31,61,43,.14);background:linear-gradient(180deg,rgba(255,255,255,.72),rgba(31,61,43,.035));border-radius:18px;padding:14px;display:flex;flex-direction:column;gap:12px}\n@media', s)

    def _fake_pipeline_focus_for_orchestrator(self):
        now = time.time()
        old = now - 45*86400
        future = now + 3*86400
        return {
            'configured': True,
            'generatedAt': '2026-06-29T12:00:00-03:00',
            'scope': 'teste',
            'introConversion': {'rows': [{'owner': 'Breno', 'rate': 0.12}]},
            'stageRows': [
                {'stageId': '1151853491', 'label': 'Diagnóstico SDR', 'total': 3, 'buckets': {'0': 1, '1': 1, '2': 0, '3': 0, '4+': 1}},
            ],
            'deals': [
                {'dealId': '1', 'dealName': 'Lead humano', 'stageId': '1151853491', 'stageLabel': 'Diagnóstico SDR', 'owner': 'Breno', 'ownerId': '86265630', 'url': 'https://hubspot/deal/1', 'activityCount': 2,
                 'activities': [
                     {'kind': 'task', 'id': 't1', 'label': 'Preparar diagnóstico — Lead humano', 'ts': future, 'status': 'NOT_STARTED', 'type': 'TODO', 'isCall': False, 'isWhatsApp': False},
                     {'kind': 'task', 'id': 't2', 'label': 'WhatsApp — Diagnóstico enviado ao lead', 'ts': old, 'status': 'NOT_STARTED', 'type': 'TODO', 'isCall': False, 'isWhatsApp': True},
                 ]},
                {'dealId': '2', 'dealName': 'Lead sujo', 'stageId': '1151853491', 'stageLabel': 'Primeiro Contato', 'owner': 'Sarah', 'ownerId': '88063842', 'url': 'https://hubspot/deal/2', 'activityCount': 1,
                 'activities': [{'kind': 'task', 'id': 't3', 'label': 'Tarefa operacional genérica', 'ts': old, 'status': 'NOT_STARTED', 'type': 'TODO', 'isCall': False, 'isWhatsApp': False}]},
            ],
        }

    def test_sdr_orchestrator_summary_and_hygiene_are_read_only_and_human_first(self):
        old = self.mod._orch_pipeline_focus_for_summary
        old_ds = self.mod.dispatch_stats
        try:
            self.mod._orch_pipeline_focus_for_summary = lambda uid='rafael': self._fake_pipeline_focus_for_orchestrator()
            self.mod.dispatch_stats = lambda uid='rafael', days=14, force=False: {
                'ok': True,
                'periodDays': 14,
                'conversionFunnel': {
                    'totalSent': 10, 'totalReturns': 4, 'totalMeetings': 1, 'totalRealizedMeetings': 0,
                    'approaches': [
                        {'key': 'a1', 'label': 'Primeiro contato', 'angle': 'catálogo / pedido recorrente', 'sent': 10, 'returns': 4, 'meetings': 1, 'realizedMeetings': 0, 'responseRate': 40.0, 'meetingRate': 10.0, 'examples': [{'empresa': 'Lead A', 'message': 'mensagem real', 'link': '/conversas?conv=x'}]},
                    ],
                },
                'followupPerformance': {'attribution': 'último disparo antes da resposta'},
            }
            summary = self.mod.sdr_orchestrator_summary('rafael')
            hygiene = self.mod.task_hygiene_preview('rafael')
        finally:
            self.mod._orch_pipeline_focus_for_summary = old
            self.mod.dispatch_stats = old_ds
        self.assertTrue(summary.get('ok'))
        self.assertIn('sdrCards', summary)
        breno = next(c for c in summary['sdrCards'] if c['name'] == 'Breno')
        self.assertEqual(breno['openHumanTasks'], 1)
        self.assertEqual(breno['manualVsAutomation']['automation'], 1)
        self.assertTrue(summary.get('interventions'))
        for item in summary['interventions']:
            self.assertTrue(item.get('severity'))
            self.assertTrue(item.get('reason'))
            self.assertTrue(item.get('evidence'))
            self.assertTrue(item.get('suggestedAction'))
        self.assertFalse(hygiene.get('mutates'))
        self.assertEqual(summary['approachPerformance']['totalSent'], 10)
        self.assertEqual(summary['approachPerformance']['topApproaches'][0]['label'], 'Primeiro contato')
        self.assertGreaterEqual(hygiene['safeToCloseAfterApproval']['count'], 1)
        self.assertGreaterEqual(hygiene['doNotTouch']['count'], 1)
        ops = self.mod.ops_health_summary('rafael')
        self.assertFalse(ops.get('mutates'))
        self.assertIn(ops.get('risk'), ('ok', 'attention', 'critical'))
        self.assertIn('files', ops)
        self.assertIn('watchdog', ops)
        self.assertIn('signals', ops)

    def test_sdr_orchestrator_endpoints_and_focus_ui_are_declared(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn("path=='/api/sdr-orchestrator-summary'", s)
        self.assertIn("path=='/api/task-hygiene-preview'", s)
        self.assertIn("path=='/api/ops-health-summary'", s)
        self.assertIn('async function loadSdrOrchestrator()', s)
        self.assertIn('Gestão SDR', s)
        self.assertIn('Nada é fechado aqui.', s)
        self.assertIn('Performance de abordagens', s)
        self.assertIn('orchApproachPerformanceBlock', s)
        self.assertIn('orchOpsHealthBlock', s)
        self.assertIn('/api/ops-health-summary', s)
        self.assertIn('Saúde da máquina', s)
        self.assertIn('.focus-subtabs{', s)
        self.assertIn('background:linear-gradient(180deg,rgba(16,25,19,.86),rgba(8,13,10,.92))', s)
        self.assertIn('.focus-subtab{appearance:none', s)
        self.assertNotIn('.focus-subtab{border:0;background:none', s)
        self.assertIn('Monitoramento', s)
        self.assertIn('watchdog_status.json', s)
        self.assertIn('function orchApproachRow', s)
        self.assertIn('_orch_pipeline_focus_for_summary', s)
        self.assertIn('_pipeline_focus_snapshot_get(uid, max_age=24*3600)', s)
        start = s.index('function sdrOrchestratorBlock()')
        end = s.index('function filteredCards()', start)
        block = s[start:end]
        for forbidden in ('ledger', 'debug', 'fonte', 'auditoria', 'registro', 'log'):
            self.assertNotIn(forbidden, block.lower())

    def test_conversations_dependency_mtime_tracks_bridge_history_files(self):
        old_data_dir = self.mod.DATA_DIR
        old_deps = self.mod.CONVERSATIONS_DEP_FILES
        tmp = Path('/tmp/channel_v2_dep_mtime_test')
        tmp.mkdir(parents=True, exist_ok=True)
        ledger = tmp / 'wpp_envios.json'
        hist = tmp / 'history_4610.json'
        ledger.write_text('[]', encoding='utf-8')
        hist.write_text('[]', encoding='utf-8')
        old_ts = time.time() - 100
        new_ts = time.time() - 10
        import os
        os.utime(ledger, (old_ts, old_ts))
        os.utime(hist, (new_ts, new_ts))
        try:
            self.mod.DATA_DIR = tmp
            self.mod.CONVERSATIONS_DEP_FILES = (ledger,)
            self.assertAlmostEqual(self.mod.conversations_dependency_mtime(), new_ts, delta=1.0)
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod.CONVERSATIONS_DEP_FILES = old_deps

    def test_all_available_chips_are_exposed_even_when_paused(self):
        chips, summary = self.mod.chips_for('rafael')
        ports = {int(c.get('port')) for c in chips}
        for port in (4600, 4601, 4603, 4605, 4606, 4607, 4609, 4610):
            self.assertIn(port, ports)
        labels = {int(c.get('port')): c.get('label') for c in chips}
        self.assertEqual(labels.get(4601), 'Sarah')
        self.assertEqual(labels.get(4605), 'Breno')
        jp = next(c for c in chips if int(c.get('port')) == 4609)
        self.assertFalse(jp.get('paused'))
        self.assertEqual(jp.get('label'), 'João Pedro')
        self.assertGreaterEqual(summary.get('total', 0), 8)

    def test_mariana_and_lucas_resende_have_rafael_level_access(self):
        rafael = self.mod.sanitize_user_record('rafael', self.mod.USERS['rafael'])
        for uid in ('mariana', 'lucas_resende'):
            with self.subTest(uid=uid):
                user = self.mod.sanitize_user_record(uid, self.mod.USERS[uid])
                self.assertTrue(user.get('admin'))
                self.assertTrue(user.get('view_all'))
                self.assertEqual(user.get('role'), 'supervisor')
                self.assertEqual(user.get('ports'), rafael.get('ports'))

    def test_mariana_cirilo_email_maps_to_mariana_supervisor(self):
        self.assertEqual(self.mod.uid_from_email('mariana.cirilo@zydon.com.br'), 'mariana')
        mariana = self.mod.sanitize_user_record('mariana', self.mod.USERS['mariana'])
        self.assertIn('mariana.cirilo@zydon.com.br', mariana.get('emails'))
        self.assertTrue(mariana.get('admin'))
        self.assertTrue(mariana.get('view_all'))
        self.assertEqual(mariana.get('role'), 'supervisor')

    def test_outbound_delivery_jid_never_sends_raw_lid_when_phone_alt_exists(self):
        old_data_dir = self.mod.DATA_DIR
        tmp = Path('/tmp/channel_v2_outbound_lid_test')
        tmp.mkdir(parents=True, exist_ok=True)
        lid = '123456789012345@lid'
        pn = '5511999998888@s.whatsapp.net'
        (tmp / 'history_4601.json').write_text(json.dumps([
            {'port': 4601, 'chat': lid, 'fromMe': False, 'text': 'oi', 'timestamp': 1000,
             'rawKey': {'remoteJid': lid, 'remoteJidAlt': pn}},
        ]), encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod._HISTORY_RAW_CACHE = {}
            target, err = self.mod.outbound_delivery_jid(4601, lid)
            self.assertEqual(err, '')
            self.assertEqual(target, pn)
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod._HISTORY_RAW_CACHE = {}

    def test_outbound_delivery_jid_blocks_unmapped_lid(self):
        target, err = self.mod.outbound_delivery_jid(4601, '123456789012345@lid')
        self.assertEqual(target, '')
        self.assertIn('LID', err)

    def test_bridge_message_ids_extracts_nested_send_response(self):
        resp = {
            'messageId': 'root-id',
            'messageIds': ['part-a'],
            'responses': [
                {'response': {'messageId': 'part-b_text'}},
                {'id': 'part-c_pdf'},
            ],
        }
        self.assertEqual(
            self.mod.bridge_message_ids(resp),
            ['root-id', 'part-a', 'part-b', 'part-c'],
        )

    def test_outbound_audit_record_writes_internal_jsonl_with_message_ids(self):
        old_audit = self.mod.OUTBOUND_AUDIT_FILE
        tmp = Path('/tmp/channel_v2_outbound_audit_test.jsonl')
        if tmp.exists():
            tmp.unlink()
        try:
            self.mod.OUTBOUND_AUDIT_FILE = tmp
            rec = self.mod.record_outbound_audit(
                uid='sarah', port=4601, chat='123456789012345@lid',
                target_jid='5511999998888@s.whatsapp.net', send_type='text',
                payload={'text': 'Olá teste'}, bridge_resp={'messageId': '3EB123_text'},
                normalized_to_pn=True,
            )
            rows = [json.loads(line) for line in tmp.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['event'], 'send')
            self.assertEqual(rows[0]['targetJid'], '5511999998888@s.whatsapp.net')
            self.assertEqual(rows[0]['messageIds'], ['3EB123'])
            self.assertEqual(rows[0]['reconciliationStatus'], 'pending')
            self.assertTrue(rows[0]['normalizedToPN'])
            self.assertEqual(rec['auditId'], rows[0]['auditId'])
        finally:
            self.mod.OUTBOUND_AUDIT_FILE = old_audit
            try: tmp.unlink()
            except FileNotFoundError: pass

    def test_outbound_reconciliation_finds_bridge_history_by_message_id(self):
        old_data_dir = self.mod.DATA_DIR
        tmp = Path('/tmp/channel_v2_outbound_reconcile_test')
        tmp.mkdir(parents=True, exist_ok=True)
        pn = '5511999998888@s.whatsapp.net'
        (tmp / 'history_4601.json').write_text(json.dumps([
            {'port': 4601, 'chat': pn, 'fromMe': True, 'id': '3EB123', 'text': 'Olá teste', 'timestamp': 2000},
        ]), encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod._HISTORY_RAW_CACHE = {}
            result = self.mod.reconcile_outbound_record({
                'port': 4601,
                'targetJid': pn,
                'messageIds': ['3EB123'],
                'sendType': 'text',
                'textPreview': 'Olá teste',
            })
            self.assertEqual(result['status'], 'found')
            self.assertEqual(result['matchedBy'], 'messageId')
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod._HISTORY_RAW_CACHE = {}

    def test_refresh_conversations_button_is_separate_from_filters(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('ATUALIZAR CONVERSAS', s)
        self.assertNotIn('>Novidades<', s)
        zone = s[s.index('<section class="col list">'):s.index('<div class="pull-refresh"', s.index('<section class="col list">'))]
        self.assertIn('class="refresh-strip"', zone)
        self.assertIn('class="refresh-conv"', zone)
        self.assertLess(zone.index('class="search"'), zone.index('id="filterToggle"'))
        self.assertLess(zone.index('id="filterToggle"'), zone.index('class="refresh-strip"'))
        self.assertLess(zone.index('class="refresh-strip"'), zone.index('id="filterbar"'))
        self.assertNotIn('live-refresh', zone)

    def test_refresh_strip_blends_with_dark_theme_not_gray_block(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('.refresh-strip{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:6px 14px;border-bottom:1px solid var(--line-soft);background:var(--panel-2)}', s)
        self.assertIn('[data-theme="dark"] .refresh-strip{background:linear-gradient(90deg,rgba(205,235,0,.035),rgba(255,255,255,.018));border-bottom-color:rgba(205,235,0,.055)}', s)
        self.assertNotIn('.refresh-strip{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:6px 14px;border-bottom:1px solid var(--line-soft);background:rgba(255,255,255,.48)}', s)

    def test_list_page_info_blends_with_dark_theme_not_white_block(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('[data-theme="dark"] .list-page-info{background:rgba(16,25,19,.78);border-color:rgba(205,235,0,.06);box-shadow:none}', s)
        self.assertNotIn('background:rgba(255,255,255,.92);backdrop-filter:blur(10px)', s)

    def test_refresh_loading_indicator_is_subtle_and_page_info_is_clean(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('.live-status.loading .live-txt::after{content:" · atualizando"', s)
        self.assertIn("live.classList.toggle('loading', !!on)", s)
        self.assertIn('Mostrando <b>${visible.length}</b> de ${list.length}', s)
        self.assertNotIn('conversas renderizadas', s)
        self.assertNotIn('carregamento leve para não travar o mobile', s)
        self.assertNotIn('.cards.loading-lite::before', s)
        self.assertNotIn('.cards.loading-lite .list-page-info::after', s)
        self.assertNotIn('position:sticky;top:36px;z-index:4;display:block;margin:0 auto', s)

    def test_chip_filter_uses_all_user_ports_not_only_visible_conversations(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        start = s.index('function renderFilterBar()')
        end = s.index('function autoRiskScore', start)
        block = s[start:end]
        self.assertIn('me&&me.ports', block)
        self.assertIn("p.paused?' (pausado)'", block)

    def test_institutional_timeline_does_not_show_empty_when_ledger_exists(self):
        conv = '4610::5519993361631@s.whatsapp.net'  # Cris Mazzer / Ana / Gustavo: caso reportado
        msgs = self.mod.messages_for('rafael', conv)
        self.assertGreaterEqual(len(msgs), 1)
        self.assertTrue(any((m.get('text') or m.get('mediaName') or m.get('mediaType')) for m in msgs))

    def test_pdf_media_resolves_for_api_and_legacy_media_url(self):
        conv = '4609::5511988997573@s.whatsapp.net'  # Segline/PPA: PDF reportado no mobile
        msgs = self.mod.messages_for('rafael', conv)
        pdf = next((m for m in msgs if (m.get('mediaName') or '').endswith('.pdf') and m.get('mediaPath')), None)
        self.assertIsNotNone(pdf)
        fname = Path(pdf.get('mediaPath')).name
        self.assertIsNotNone(self.mod.resolve_media_file_for_user('rafael', fname, pdf.get('port'), conv))
        self.assertIsNotNone(self.mod.resolve_media_file_for_user('rafael', fname))

    def test_mobile_pdf_preview_modal_allows_internal_scroll(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('.file-modal .modal-body{padding:0;overflow:auto', s)
        self.assertIn('-webkit-overflow-scrolling:touch', s)
        self.assertIn('overscroll-behavior:contain', s)
        self.assertIn('@media(max-width:820px){.file-modal{align-items:stretch', s)
        self.assertIn('.file-preview{height:auto;min-height:calc(100dvh - 82px);overflow:auto;touch-action:pan-y}', s)
        self.assertIn('iframe scrolling="yes"', s)
        self.assertIn('.file-preview iframe{height:calc(100dvh - 82px);min-height:calc(100dvh - 82px);overflow:auto}', s)

    def test_real_pdf_and_ledger_pdf_are_shown_once(self):
        conv = '4609::5547984948495@s.whatsapp.net'  # Fibratto: anexo real + ledger do mesmo PDF
        msgs = self.mod.messages_for('rafael', conv)
        pdfs = [m for m in msgs if (m.get('mediaName') or '') == 'Fibratto - Potencial de Digitalizacao B2B.pdf']
        self.assertEqual(len(pdfs), 1)
        self.assertNotEqual(pdfs[0].get('type'), 'cron-mql-pdf')
        self.assertEqual(pdfs[0].get('automation'), 'Automação · Diagnóstico (PDF)')

    def test_atena_seed_and_cron_same_text_render_once(self):
        conv = '4601::5527997622516@s.whatsapp.net'
        msgs = self.mod.messages_for('rafael', conv)
        target = 'Vitor, seguindo o diagnóstico que te mandei, quero começar pelo motivo principal.'
        hits = [m for m in msgs if target in (m.get('text') or '')]
        self.assertEqual(len(hits), 1, [m.get('id') for m in hits])

    def test_suprema_split_send_does_not_render_full_ledger_duplicate(self):
        conv = '4607::5585988903132@s.whatsapp.net'
        msgs = self.mod.messages_for('rafael', conv)
        # WhatsApp real foi dividido em partes; o ledger cheio não deve aparecer como
        # quarta bolha duplicando a primeira parte + a segunda parte.
        full = [m for m in msgs if 'George, aqui é Rafael da Zydon.' in (m.get('text') or '') and 'Você acha que isso ainda faz sentido para a Suprema Caju' in (m.get('text') or '')]
        self.assertEqual(len(full), 0, [m.get('id') for m in full])
        intro = [m for m in msgs if 'George, aqui é Rafael da Zydon.' in (m.get('text') or '')]
        question = [m for m in msgs if 'Você acha que isso ainda faz sentido para a Suprema Caju' in (m.get('text') or '')]
        self.assertEqual(len(intro), 1, [m.get('id') for m in intro])
        self.assertEqual(len(question), 1, [m.get('id') for m in question])

    def test_pontual_no_show_dispatch_appears_in_supervisor_inbox(self):
        self.mod._WPP_FASTLANE_CACHE = {}
        self.mod.CONVERSATIONS_API_CACHE = {}
        convs = self.mod.conversations('rafael')
        by_id = {c.get('id'): c for c in convs}
        chemie = by_id.get('4600::5542999614340@s.whatsapp.net')
        self.assertIsNotNone(chemie)
        self.assertEqual(chemie.get('title'), 'Chemie Saude Ambinetal')
        self.assertEqual(chemie.get('dealOwnerLabel'), 'Lucas Batista')
        self.assertTrue(chemie.get('readOnlyInstitutional'))
        buriti = by_id.get('4600::5537999816900@s.whatsapp.net')
        self.assertIsNotNone(buriti)
        self.assertEqual(buriti.get('title'), 'Engenho Buriti')
        self.assertTrue(buriti.get('readOnlyInstitutional'))

    def test_pontual_text_and_ledger_render_once(self):
        conv = '4606::5511940339588@s.whatsapp.net'  # Bigmassa: bolha real + ledger 3min depois
        msgs = self.mod.messages_for('rafael', conv)
        needle = 'Márcio, tem um cliente da Zydon que lembrou a operação de vocês.'
        hits = [m for m in msgs if str(m.get('text') or '').startswith(needle)]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].get('automation'), 'Automação')

    def test_late_imported_ledger_with_same_message_id_renders_once(self):
        conv = '4603::5565998041355@s.whatsapp.net'  # Lemon/NutryCap: ledger importou ~79min depois
        msgs = self.mod.messages_for('rafael', conv)
        first = 'João, tem um cliente da Zydon que lembrou a operação de vocês.'
        second = 'João, se quiser ver como essa solução funcionaria para a sua empresa'
        self.assertEqual(len([m for m in msgs if str(m.get('text') or '').startswith(first)]), 1)
        self.assertEqual(len([m for m in msgs if str(m.get('text') or '').startswith(second)]), 1)
        self.assertTrue(any(m.get('automation') == 'Automação' for m in msgs if str(m.get('text') or '').startswith(first)))

    def test_operational_communicator_thread_shows_full_dialogue(self):
        conv = '4607::5511917808665@s.whatsapp.net'  # Nevoni/Vinícius: Rafael comunicador, Breno dono
        msgs = self.mod.messages_for('rafael', conv)
        texts = '\n'.join(m.get('text') or '' for m in msgs)
        self.assertIn('me refresca a memória', texts)
        self.assertIn('Show demais!', texts)
        self.assertIn('a Zydon é focada no segmento', texts)
        self.assertTrue(any(m.get('fromMe') and m.get('readOnlyInstitutionalThread') for m in msgs))

    def test_messages_for_institutional_chat_is_fast(self):
        conv = '4610::5519993361631@s.whatsapp.net'
        t0 = time.time()
        msgs = self.mod.messages_for('rafael', conv)
        elapsed = time.time() - t0
        self.assertGreaterEqual(len(msgs), 1)
        self.assertLess(elapsed, 1.5)

    def test_communicator_personal_outbound_is_not_exposed_without_operational_ledger(self):
        old_data_dir = self.mod.DATA_DIR
        old_wpp = self.mod.WPP_ENVIOS_FILE
        tmp = Path('/tmp/channel_v2_personal_privacy_test')
        tmp.mkdir(parents=True, exist_ok=True)
        chat = '559999999999@s.whatsapp.net'
        (tmp / 'history_4607.json').write_text(json.dumps([
            {'port':4607,'chat':chat,'fromMe':True,'type':'notify','text':'mensagem privada que não pode vazar','timestamp':1000},
            {'port':4607,'chat':chat,'fromMe':False,'type':'notify','text':'resposta privada que não pode vazar','timestamp':1001},
        ]), encoding='utf-8')
        empty_ledger = Path('/tmp/channel_v2_empty_wpp_envios.json')
        empty_ledger.write_text(json.dumps({'envios': []}), encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod.WPP_ENVIOS_FILE = empty_ledger
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            self.mod._WPP_FASTLANE_CACHE = {}
            msgs = self.mod.messages_for('rafael', f'4607::{chat}')
            self.assertEqual(msgs, [])
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod.WPP_ENVIOS_FILE = old_wpp
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            self.mod._WPP_FASTLANE_CACHE = {}

    def test_sdr_inbox_only_shows_automation_originated_conversations(self):
        old_data_dir = self.mod.DATA_DIR
        old_wpp = self.mod.WPP_ENVIOS_FILE
        tmp = Path('/tmp/channel_v2_sdr_operational_only_test')
        tmp.mkdir(parents=True, exist_ok=True)
        personal = '5511999990000@s.whatsapp.net'
        operational = '5511888880000@s.whatsapp.net'
        (tmp / 'history_4601.json').write_text(json.dumps([
            {'port':4601,'chat':personal,'fromMe':True,'type':'notify','text':'conversa pessoal sem automação','timestamp':1000},
            {'port':4601,'chat':personal,'fromMe':False,'type':'notify','text':'resposta pessoal','timestamp':1001},
            {'port':4601,'chat':operational,'fromMe':True,'type':'cron-sdr-primeiro-contato','text':'primeiro contato automático','timestamp':1002,'empresa':'Cliente Operacional','sdr':'Sarah'},
            {'port':4601,'chat':operational,'fromMe':False,'type':'notify','text':'resposta do lead','timestamp':1003},
        ]), encoding='utf-8')
        empty_ledger = tmp / 'wpp_envios.json'
        empty_ledger.write_text(json.dumps({'envios': []}), encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod.WPP_ENVIOS_FILE = empty_ledger
            self.mod.CONVERSATIONS_API_CACHE = {}
            self.mod.CONVERSATION_PERMISSION_CACHE = {}
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            self.mod._WPP_FASTLANE_CACHE = {}
            self.mod._HISTORY_RAW_CACHE = {}
            convs = self.mod.conversations('sarah')
            ids = {c.get('id') for c in convs}
            self.assertNotIn(f'4601::{personal}', ids)
            self.assertIn(f'4601::{operational}', ids)
            self.assertFalse(self.mod.conversation_id_allowed('sarah', f'4601::{personal}'))
            self.assertEqual(self.mod.messages_for('sarah', f'4601::{personal}'), [])
            self.assertGreaterEqual(len(self.mod.messages_for('sarah', f'4601::{operational}')), 1)
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod.WPP_ENVIOS_FILE = old_wpp
            self.mod.CONVERSATION_PERMISSION_CACHE = {}
            self.mod._HISTORY_RAW_CACHE = {}
            self.mod._WPP_FASTLANE_CACHE = {}
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}

    def test_cnpj_only_lead_uses_slug_as_human_card_identity(self):
        old_data_dir = self.mod.DATA_DIR
        old_wpp = self.mod.WPP_ENVIOS_FILE
        tmp = Path('/tmp/channel_v2_slug_identity_test')
        tmp.mkdir(parents=True, exist_ok=True)
        chat = '5543999053264@s.whatsapp.net'
        (tmp / 'history_4607.json').write_text(json.dumps([
            {'port':4607,'chat':chat,'fromMe':True,'type':'cron-whatsapp-texto','text':'primeiro contato','timestamp':1000,'status':'enviado_nao_mql_legitimo','empresa':'61259962000154','nome':'','slug':'liso-confeccoes-douglas','email':'douglasbarreto1998@gmail.com','source':'controle/wpp_envios.json+bridge:operational'},
        ]), encoding='utf-8')
        empty_ledger = tmp / 'wpp_envios.json'
        empty_ledger.write_text(json.dumps({'envios': [
            {'date':'2026-06-29 17:15:21','email':'douglasbarreto1998@gmail.com','contact_id':'230170566060','slug':'liso-confeccoes-douglas','empresa':'61259962000154','phone':'5543999053264','to':chat,'bridge_port':4607,'sender_name':'Rafael','status':'enviado_nao_mql_legitimo','type':'cron-whatsapp-texto','text':'primeiro contato'}
        ]}), encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod.WPP_ENVIOS_FILE = empty_ledger
            self.mod._HISTORY_RAW_CACHE = {}
            self.mod._HISTORY_MERGED_CACHE = {}
            self.mod._WPP_FASTLANE_CACHE = {}
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            convs = self.mod.conversations('rafael')
            card = next(c for c in convs if c.get('id') == f'4607::{chat}')
            self.assertEqual(card.get('title'), 'Liso Confeccoes')
            self.assertIn('Douglas', card.get('subtitle') or '')
            self.assertNotEqual(card.get('title'), '61259962000154')
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod.WPP_ENVIOS_FILE = old_wpp
            self.mod._HISTORY_RAW_CACHE = {}
            self.mod._HISTORY_MERGED_CACHE = {}
            self.mod._WPP_FASTLANE_CACHE = {}
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}

    def test_inbox_operational_filter_does_not_rescan_sdr_history_per_card(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('rows=_history_raw_rows(int(port))', s)
        self.assertIn('_HISTORY_MERGED_CACHE', s)
        self.assertIn('warm_history_caches_background()', s)
        self.assertIn("threading.Thread(target=_worker, daemon=True, name='channel-history-warmup').start()", s)
        self.assertIn('ledger_mtime=_wpp_envios_mtime() if is_institutional_port(port_i) else 0.0', s)
        self.assertIn("cached.get('history_mtime') == h_mtime", s)
        self.assertNotIn('json.loads(p.read_text(encoding=\'utf-8\')) if p.exists() else []\n    except Exception:\n        data=[]\n    out=[]', s)
        start = s.index('    out=[]\n    for c in conv.values():')
        end = s.index("        if is_institutional_port(c.get('port')):", start)
        block = s[start:end]
        self.assertIn("if not c.get('_operationalOrigin'):", block)
        self.assertIn("if is_institutional_port(c.get('port')) and not operational_conversation_has_origin", block)
        self.assertNotIn("if not (c.get('_operationalOrigin') and operational_conversation_has_origin", block)

    def test_institutional_inbox_uses_latest_thread_message_like_detail(self):
        conv = '4610::5516997039031@s.whatsapp.net'  # Casa dos Pneus: detalhe tinha resposta posterior do comunicador
        card = next(c for c in self.mod.conversations('rafael') if c.get('id') == conv)
        msgs = self.mod.messages_for('rafael', conv)
        last = max(msgs, key=lambda m: float(m.get('timestamp') or 0))
        self.assertEqual(card.get('lastTime'), last.get('timestamp'))
        self.assertEqual((card.get('last') or {}).get('text'), last.get('text'))
        self.assertEqual(card.get('inboxSortTime'), card.get('lastTime'))
        self.assertIn('Qual ERP vocês utilizam hoje?', (card.get('last') or {}).get('text') or '')

    def test_frontend_does_not_render_empty_on_message_fetch_failure(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('Não consegui carregar mensagens agora', s)
        self.assertIn('catch(e)', s)
        self.assertNotIn('drawTimeline(true);\n  if(!(msgs||[]).length)', s)

    def test_switching_conversation_never_keeps_previous_timeline_messages(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('msgsConvId=null', s)
        start = s.index('async function openConv')
        end = s.index('/* ---- CH-018', start)
        block = s[start:end]
        self.assertIn('const switchingConversation = msgsConvId !== id', block)
        self.assertIn('msgs=[]; msgsConvId=null;', block)
        self.assertIn('Atualizando a timeline desta conversa', block)
        self.assertIn('msgsConvId=id;', block)
        self.assertIn('if(msgsConvId===id && (msgs||[]).length)', block)
        self.assertIn('nunca mantém\n      // mensagens da conversa anterior', block)

    def test_inbox_timeout_is_not_shown_as_auth_failure(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('err.status=r.status', s)
        self.assertIn('err.timeout=true', s)
        self.assertIn('const isAuthError=e && (e.status===401 || e.status===403)', s)
        self.assertIn("const url='/api/conversations'+(opts.force?'?force=1':'');", s)
        self.assertIn("api(url,{timeoutMs: opts.force?60000:(opts.fast?9000:20000)})", s)
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

    def test_conversations_endpoint_uses_stale_while_revalidate_not_sync_recompute(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        start = s.index("if path in ('/api/conversations','/api/conversations-safe'):")
        end = s.index("        if path=='/api/messages':", start)
        block = s[start:end]
        self.assertIn('if cache and not force_refresh:', block)
        self.assertIn('background_refresh_conversations(uid, cache_key)', block)
        self.assertIn('devolve stale imediatamente', block)
        self.assertIn('convs=conversations(uid)', block)
        self.assertIn('with CONVERSATIONS_API_LOCK:', block)
        self.assertIn('should_compute', block)
        self.assertIn('CONVERSATIONS_REFRESHING.add(cache_key)', block)
        stale_return_pos = block.index("return self.sendb(200, body)")
        first_sync_pos = block.index('convs=conversations(uid)')
        self.assertLess(stale_return_pos, first_sync_pos, 'cache stale deve retornar antes de recomputar')
        stale_branch = block[block.index('if cache and not force_refresh:'):first_sync_pos]
        self.assertNotIn('convs=conversations(uid)', stale_branch)
        self.assertIn('force_refresh=str', block)
        self.assertIn("qs=parse_qs(parsed.query)", block)

    def test_messages_endpoint_uses_singleflight_for_cold_loads(self):
        """Carga fria de /api/messages deve coalescer cálculos concorrentes.

        Incidente manual-20260629T2031: durante disparo em lote (wpp_envios.json
        muda a cada segundos e invalida _WPP_FASTLANE_CACHE) várias threads pediam
        a MESMA conv fria e cada uma rodava messages_for síncrono (scan de ledger
        de 14 dias da porta institucional), empilhando 134 threads / 110% CPU no
        processo único 8280 e arrastando todas as rotas para 3-14s. O contrato:
        só uma thread computa por (uid, conv); as demais esperam o cache quente.
        """
        s = MODULE_PATH.read_text(encoding='utf-8')
        start = s.index("if path=='/api/messages':")
        end = s.index("if path=='/api/chips':", start)
        block = s[start:end]
        # SWR preservado: cache existente serve stale e atualiza em background.
        self.assertIn('background_refresh_messages(uid, conv, cache_key)', block)
        # Singleflight da carga fria.
        self.assertIn('MESSAGES_COMPUTING', block)
        self.assertIn('should_compute', block)
        self.assertIn('with MESSAGES_API_LOCK:', block)
        self.assertIn('MESSAGES_COMPUTING.add(cache_key)', block)
        self.assertIn('MESSAGES_COMPUTING.discard(cache_key)', block)
        # A flag é liberada em finally para não vazar singleflight em erro.
        self.assertIn('finally:', block)
        # Esperar o resultado quente em vez de recomputar quando já há cálculo em voo.
        wait_pos = block.index('if not should_compute:')
        compute_pos = block.index('messages_for(uid, conv)')
        self.assertLess(wait_pos, compute_pos, 'espera do singleflight deve vir antes do cálculo próprio')
        self.assertIn('MESSAGES_COMPUTING = set()', s)

    def test_manual_refresh_clears_active_card_removed_from_inbox(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        start = s.index('async function loadAll')
        end = s.index('renderShell();', start)
        block = s[start:end]
        self.assertIn('active && !convs.some(x=>x.id===active)', block)
        self.assertIn('active=null; msgs=[]; msgsConvId=null;', block)
        self.assertIn('Nenhuma conversa selecionada', block)
        self.assertIn('Selecione uma conversa operacional na lista', block)

    def test_conversations_sort_and_preview_follow_latest_visible_message(self):
        old_data_dir = self.mod.DATA_DIR
        old_wpp = self.mod.WPP_ENVIOS_FILE
        old_fastlane = getattr(self.mod, '_WPP_FASTLANE_CACHE', {})
        old_rows = getattr(self.mod, '_WPP_ENVIOS_ROWS_CACHE', {})
        tmp = Path('/tmp/channel_v2_sort_latest_message_test')
        tmp.mkdir(parents=True, exist_ok=True)
        now = time.time()
        chat_a = '5511999000001@s.whatsapp.net'
        chat_b = '5511999000002@s.whatsapp.net'
        (tmp / 'history_4601.json').write_text(json.dumps([
            {'port': 4601, 'chat': chat_a, 'fromMe': False, 'type': 'notify', 'text': 'cliente respondeu antes', 'timestamp': now - 300, 'empresa': 'Cliente A', 'nome': 'Ana'},
            {'port': 4601, 'chat': chat_b, 'fromMe': True, 'type': 'notify', 'text': 'mensagem nossa intermediaria', 'timestamp': now - 200, 'empresa': 'Cliente B', 'nome': 'Bruno'},
            {'port': 4601, 'chat': chat_a, 'fromMe': True, 'type': 'notify', 'text': 'última mensagem nossa precisa aparecer no preview', 'timestamp': now - 100, 'empresa': 'Cliente A', 'nome': 'Ana'},
        ]), encoding='utf-8')
        empty_ledger = tmp / 'wpp_envios.json'
        empty_ledger.write_text(json.dumps({'envios': []}), encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod.WPP_ENVIOS_FILE = empty_ledger
            self.mod._WPP_FASTLANE_CACHE = {}
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            convs = self.mod.conversations('sarah')
            ids = [c.get('id') for c in convs]
            id_a = f'4601::{chat_a}'
            id_b = f'4601::{chat_b}'
            self.assertLess(ids.index(id_a), ids.index(id_b), 'a lista deve ordenar pela última mensagem real, não só por resposta do cliente/entrada comercial')
            ca = next(c for c in convs if c.get('id') == id_a)
            self.assertEqual(ca.get('inboxSortTime'), ca.get('lastTime'))
            self.assertTrue(ca.get('last', {}).get('fromMe'))
            self.assertEqual(ca.get('last', {}).get('text'), 'última mensagem nossa precisa aparecer no preview')
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod.WPP_ENVIOS_FILE = old_wpp
            self.mod._WPP_FASTLANE_CACHE = old_fastlane
            self.mod._WPP_ENVIOS_ROWS_CACHE = old_rows

    def test_frontend_preview_uses_last_message_text_variants(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('c.last.text||c.last.body||c.last.caption||c.last.message||c.last.transcript', s)

    def test_management_dispatch_stats_chart_by_day_and_chip(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn("def dispatch_stats(uid='rafael', days=14, force=False):", s)
        self.assertIn("if path=='/api/dispatch-stats'", s)
        self.assertIn("api('/api/dispatch-stats?days=14'+(force?'&force=1':''),{timeoutMs:30000})", s)
        self.assertIn('Painel WhatsApp · envios por chip', s)
        self.assertIn('Mix de abordagens · por dia', s)
        self.assertIn('typeStats', s)
        self.assertIn('function dispatchTypeStatsBlock()', s)
        self.assertIn('function openDispatchTypeModal(day, key', s)
        self.assertIn('Follow-up 1', s)
        self.assertIn('Follow-up pós-diagnóstico', s)
        self.assertIn('Pausa por sumiço', s)
        self.assertIn('Outros', s)
        self.assertIn('dispatchTooltip', s)
        self.assertIn('showDispatchTooltip(event', s)
        self.assertIn('dias com dados', s)
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
        self.assertIn('Volume operacional por pessoa/chip', s)
        self.assertIn('Clique para abrir as mensagens que compõem cada camada', s)
        self.assertIn('controle/wpp_envios.json', s)
        stats = self.mod.dispatch_stats('rafael', 14)
        self.assertTrue(stats.get('ok'))
        self.assertIn('days', stats)
        self.assertIn('chips', stats)
        sample_events = [ev for day in stats['days'] for events in (day.get('details') or {}).values() for ev in events]
        self.assertTrue(sample_events)
        self.assertIn('/conversas?conv=', sample_events[0].get('link',''))
        self.assertIn('message', sample_events[0])
        self.assertIn('typeStats', stats)
        type_stats = stats['typeStats']
        self.assertEqual(type_stats.get('total'), stats.get('total'))
        self.assertTrue(type_stats.get('series'))
        labels = [x.get('label') for x in type_stats.get('series', [])]
        self.assertIn('Diagnóstico', labels)
        self.assertIn('Follow-up pós-diagnóstico', labels)
        self.assertTrue(any(str(x).startswith('Follow-up') for x in labels))
        self.assertEqual(sum(x.get('total', 0) for x in type_stats.get('series', [])), stats.get('total'))
        sample_type_events = [ev for day in type_stats['days'] for events in (day.get('details') or {}).values() for ev in events]
        self.assertTrue(sample_type_events)
        self.assertIn('kindLabel', sample_type_events[0])
        self.assertLessEqual(len(stats['days']), 14)
        self.assertEqual(stats.get('visibleDays'), len(stats.get('days') or []))
        self.assertTrue((not stats.get('days')) or stats['days'][0].get('total', 0) > 0)
        self.assertIsInstance(stats.get('total'), int)
        self.assertIn('followupPerformance', stats)
        self.assertIn('agendaPerformance', stats)
        self.assertIn('conversionFunnel', stats)
        self.assertIn('lossRanking', stats)
        self.assertIn('approaches', stats['conversionFunnel'])
        self.assertIn('items', stats['lossRanking'])
        agenda = stats['agendaPerformance']
        self.assertIn('ranked', agenda)
        self.assertIn('totalMeetings', agenda)
        self.assertIn('totalRealizedMeetings', agenda)
        self.assertIn('realizedRule', agenda)
        perf = stats['followupPerformance']
        self.assertIn('ranked', perf)
        self.assertIn('days', perf)
        self.assertIn('totalReturns', perf)
        self.assertIn('approaches', perf)
        if perf.get('approaches'):
            first_approach = perf['approaches'][0]
            self.assertIn('variants', first_approach)
            self.assertIn('parentKey', first_approach)
        self.assertIn('Abordagens que mais geram resposta', s)
        self.assertIn('CONVERSÃO PARA AGENDA', s)
        self.assertIn('Abordagens que viram reunião', s)
        self.assertIn('agendaPerformanceBlock', s)
        self.assertIn('conversionFunnelBlock', s)
        self.assertIn('lossRankingBlock', s)
        self.assertIn('rescueQueueBlock', s)
        self.assertIn('FUNIL COMPLETO POR ABORDAGEM', s)
        self.assertIn('Onde estamos perdendo conversão', s)
        self.assertIn('Fila de resgate operacional', s)
        self.assertIn('PERFORMANCE DOS FOLLOW-UPS', s)
        self.assertIn('Veja quais mensagens realmente geram resposta', s)
        self.assertIn('Escolha uma abordagem real para ver mensagem, variações e conversas', s)
        self.assertIn('Mensagem que gerou resposta', s)
        self.assertIn('Conversão por abordagem', s)
        self.assertIn('Variações usadas', s)
        self.assertIn('function setFollowupType(key)', s)
        self.assertIn('class="follow-card', s)
        self.assertIn('class="chat-preview', s)
        self.assertIn('Abordagem selecionada', s)
        self.assertIn('approaches', s)
        self.assertIn('variants', s)
        self.assertIn('approach-panel', s)
        self.assertIn('approachLabel', s)
        self.assertIn("examples': []", s)

    def test_pipeline_focus_uses_long_timeout_and_cached_snapshot_on_timeout(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn("api('/api/pipeline/focus',{timeoutMs:30000})", s)
        self.assertIn("localStorage.setItem('zydon:pipelineFocus:last'", s)
        self.assertIn("localStorage.getItem('zydon:pipelineFocus:last')", s)
        self.assertIn('Mostrando último snapshot enquanto atualiza o HubSpot', s)
        self.assertIn('HubSpot demorou para atualizar; mostrando último snapshot', s)

    def test_dispatch_stats_uses_persistent_snapshot_and_manual_force(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('DISPATCH_STATS_SNAPSHOT_FILE', s)
        self.assertIn('def _dispatch_stats_snapshot_get', s)
        self.assertIn('def _dispatch_stats_snapshot_set', s)
        self.assertIn('_dispatch_stats_snapshot_get(uid, days)', s)
        self.assertIn('_dispatch_stats_snapshot_set(uid, days, out)', s)
        self.assertIn('dispatchDepsMtime', s)
        self.assertIn('_dispatch_stats_dependency_mtime()', s)
        self.assertIn("localStorage.getItem('zydon:dispatchStats:last')", s)
        self.assertIn("localStorage.setItem('zydon:dispatchStats:last'", s)
        self.assertIn("api('/api/dispatch-stats?days=14'+(force?'&force=1':''),{timeoutMs:30000})", s)
        self.assertIn("force=1", s)

    def test_followup_return_rate_attributes_reply_to_last_touch(self):
        old_data_dir = self.mod.DATA_DIR
        old_wpp = self.mod.WPP_ENVIOS_FILE
        old_rows = dict(getattr(self.mod, '_WPP_ENVIOS_ROWS_CACHE', {}))
        old_hist = dict(getattr(self.mod, '_HISTORY_RAW_CACHE', {}))
        tmp = Path('/tmp/channel_v2_followup_return_test')
        tmp.mkdir(parents=True, exist_ok=True)
        now = time.time()
        def iso(ts):
            return time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(ts))
        chat_a = '5511999000001@s.whatsapp.net'
        chat_b = '5511999000002@s.whatsapp.net'
        rows = [
            {'date_tz': iso(now-7200), 'to': chat_a, 'bridge_port': 4601, 'status': 'enviado_followup_1', 'msg_type': 'follow-up 1', 'text': 'follow-up 1'},
            {'date_tz': iso(now-3600), 'to': chat_a, 'bridge_port': 4601, 'status': 'enviado_followup_2', 'msg_type': 'follow-up 2', 'text': 'follow-up 2'},
            {'date_tz': iso(now-90000), 'to': chat_b, 'bridge_port': 4601, 'status': 'enviado_followup_1', 'msg_type': 'follow-up 1', 'text': 'follow-up 1 versão de ontem'},
        ]
        (tmp / 'wpp_envios.json').write_text(json.dumps({'envios': rows}), encoding='utf-8')
        (tmp / 'history_4601.json').write_text(json.dumps([
            {'port': 4601, 'chat': chat_a, 'fromMe': False, 'text': 'Tenho interesse', 'timestamp': now-1800},
            {'port': 4601, 'chat': chat_b, 'fromMe': False, 'text': 'Pode me chamar', 'timestamp': now-3000},
        ]), encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod.WPP_ENVIOS_FILE = tmp / 'wpp_envios.json'
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            self.mod._HISTORY_RAW_CACHE = {}
            stats = self.mod.dispatch_stats('rafael', 14)
            perf = {r['key']: r for r in stats['followupPerformance']['series']}
            self.assertEqual(perf['followup_2']['sent'], 1)
            self.assertEqual(perf['followup_2']['returns'], 1)
            self.assertEqual(perf['followup_2']['responseRate'], 100.0)
            self.assertEqual(perf['followup_1']['sent'], 2)
            self.assertEqual(perf['followup_1']['returns'], 1)
            self.assertEqual(perf['followup_1']['responseRate'], 50.0)
            self.assertEqual(stats['followupPerformance']['ranked'][0]['key'], 'followup_2')
            approaches = [a for a in stats['followupPerformance']['approaches'] if a.get('parentKey') == 'followup_1']
            self.assertEqual(len(approaches), 2)
            self.assertTrue(all(a.get('versionLabel') for a in approaches))
            self.assertEqual(sorted(a.get('sent') for a in approaches), [1, 1])
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod.WPP_ENVIOS_FILE = old_wpp
            self.mod._WPP_ENVIOS_ROWS_CACHE = old_rows
            self.mod._HISTORY_RAW_CACHE = old_hist

    def test_nao_mql_similar_approaches_are_grouped_not_versioned_by_day(self):
        now = time.time()
        ev1 = {'kind': 'nao_mql', 'ts': now - 86400, 'message': 'Oi Luiz, tudo bem? Aqui é o Lucas Resende, da Zydon. Talvez a gente não consiga ajudar agora.', 'approach': {'label': 'Tratativa não MQL', 'angle': ''}}
        ev2 = {'kind': 'nao_mql', 'ts': now, 'message': 'Oi Marcos, tudo bem? Aqui é o Lucas Resende, da Zydon. Talvez a gente não consiga ajudar agora.', 'approach': {'label': 'Tratativa não MQL', 'angle': ''}}
        self.assertEqual(self.mod._dispatch_approach_key(ev1), self.mod._dispatch_approach_key(ev2))
        self.assertEqual(self.mod._dispatch_approach_key(ev1), 'nao_mql::tratativa nao mql')
        self.assertNotIn('v_', self.mod._dispatch_approach_key(ev1))

    def test_meeting_reminders_do_not_count_as_agenda_generating_approach(self):
        old_data_dir = self.mod.DATA_DIR
        old_wpp = self.mod.WPP_ENVIOS_FILE
        old_rows = dict(getattr(self.mod, '_WPP_ENVIOS_ROWS_CACHE', {}))
        old_hist = dict(getattr(self.mod, '_HISTORY_RAW_CACHE', {}))
        tmp = Path('/tmp/channel_v2_agenda_reminder_test')
        tmp.mkdir(parents=True, exist_ok=True)
        now = time.time()
        def iso(ts):
            return time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(ts))
        chat = '5511999000099@s.whatsapp.net'
        rows = [
            {'date_tz': iso(now-3600), 'to': chat, 'bridge_port': 4601, 'status': 'enviado_lead', 'msg_type': 'cron-mql-texto', 'text': 'Gabriella, passando para lembrar do nosso diagnóstico hoje às 29/06/2026 16:30. Link: https://meet.google.com/abc', 'meeting_id': 'm1', 'meeting_start': iso(now+7200)},
        ]
        (tmp / 'wpp_envios.json').write_text(json.dumps({'envios': rows}), encoding='utf-8')
        (tmp / 'history_4601.json').write_text('[]', encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod.WPP_ENVIOS_FILE = tmp / 'wpp_envios.json'
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            self.mod._HISTORY_RAW_CACHE = {}
            stats = self.mod.dispatch_stats('rafael', 14)
            self.assertEqual(stats['agendaPerformance']['totalMeetings'], 0)
            ranked = stats['agendaPerformance']['ranked']
            self.assertTrue(all((r.get('meetingExamples') or [{}])[0].get('message', '').lower().find('passando para lembrar') == -1 for r in ranked if r.get('meetingExamples')))
            self.assertTrue(self.mod._dispatch_is_meeting_reminder_text(rows[0]['text']))
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod.WPP_ENVIOS_FILE = old_wpp
            self.mod._WPP_ENVIOS_ROWS_CACHE = old_rows
            self.mod._HISTORY_RAW_CACHE = old_hist

    def test_pdf_attachment_card_is_responsive_inside_chat_bubble(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('width:min(330px,100%)', s)
        self.assertIn('appearance:none', s)
        self.assertIn('.pdf .pmeta{flex:1 1 auto;min-width:0;overflow:hidden}', s)
        self.assertIn('.pdf .pmeta span{display:block', s)
        self.assertIn('.bubble.has-media{padding:7px;min-width:min(330px,100%);max-width:min(360px,100%)}', s)
        self.assertIn('.bubble.has-media .btext{display:block;min-width:0}', s)
        self.assertIn('.bubble.has-media .pdf{margin:0 0 2px;width:100%;max-width:100%', s)
        self.assertIn('.brow.out .bubble.has-media .pdf{background:rgba(7,16,11,.16)', s)
        self.assertNotIn('.bubble.has-media .pdf{margin-top:4px;margin-bottom:2px;max-width:280px}', s)

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
            self.assertEqual(sarah_events[0].get('dispatchPort'), 4601)
            self.assertEqual(sarah_events[0].get('dispatchLabel'), 'Sarah')
            self.assertEqual(sarah_events[0].get('groupDispatchPort'), 4606)
            self.assertEqual(comm_events, [])
            self.assertNotIn('institutionalMirror', json.dumps(sarah_events))
        finally:
            self.mod.WPP_ENVIOS_FILE = old_file
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            self.mod._WPP_FASTLANE_CACHE = {}
            if tmp.exists():
                tmp.unlink()

    def test_comercial_ss_joao_pedro_dispatch_appears_with_correct_sender(self):
        convs = self.mod.conversations('rafael')
        hit = next((c for c in convs if c.get('id') == '4609::5516996097191@s.whatsapp.net'), None)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get('senderLabel'), 'João Pedro')
        self.assertEqual(hit.get('port'), 4609)
        self.assertTrue(hit.get('readOnlyInstitutional'))

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

    def test_mobile_pull_down_reloads_whole_page(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('function installPullToReload()', s)
        self.assertIn("document.querySelector('.list .scroll')", s)
        self.assertIn('id="pullRefresh"', s)
        self.assertIn('function setPullRefreshState', s)
        self.assertIn('Puxe para atualizar', s)
        self.assertIn('Solte para atualizar', s)
        self.assertIn('Atualizando conversas…', s)
        self.assertIn('pullSpin', s)
        self.assertIn("scroller.addEventListener('touchstart'", s)
        self.assertIn("scroller.addEventListener('touchmove'", s)
        self.assertIn("scroller.addEventListener('touchend'", s)
        self.assertIn('dy>85 && scroller.scrollTop<=0', s)
        self.assertIn('setTimeout(()=>window.location.reload(),260)', s)

    def test_late_ledger_uses_bridge_timestamp_in_inbox(self):
        bridge = {'port': 4603, 'chat': '5511999999999@s.whatsapp.net', 'id': '3EBREAL123', 'type': 'append', 'fromMe': True, 'timestamp': 1000, 'text': 'Oi'}
        fastlane = {'port': 4603, 'chat': '5511999999999@s.whatsapp.net', 'id': 'wpp_envios:x:1002', 'messageId': '3EBREAL123', 'type': 'seed-wpp-envios', 'fromMe': True, 'timestamp': 1002, 'text': 'Oi', 'source': 'controle/wpp_envios.json:fastlane'}
        late = {'port': 4603, 'chat': '5511999999999@s.whatsapp.net', 'id': '3EBREAL123_text', 'type': 'cron-whatsapp-texto', 'fromMe': True, 'timestamp': 9999, 'text': 'Oi', 'source': 'controle/wpp_envios.json', 'sender': 'cron-import'}
        out = self.mod._dedupe_loaded_items([bridge, fastlane, late])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['timestamp'], 1000)
        self.assertEqual(out[0]['timestampSource'], 'bridge')
        self.assertEqual(out[0]['bridgeMessageId'], '3EBREAL123')
        self.assertIn(out[0]['type'], ('seed-wpp-envios', 'cron-whatsapp-texto'))

    def test_deleted_bridge_message_keeps_deleted_flag_after_late_ledger_dedupe(self):
        bridge = {'port': 4606, 'chat': '5514997125104@s.whatsapp.net', 'id': '3EBDEL123', 'type': 'append', 'fromMe': True, 'timestamp': 1000, 'text': 'mensagem errada', 'deleted': True, 'deletedAt': '2026-06-28T16:39:38Z'}
        late = {'port': 4606, 'chat': '5514997125104@s.whatsapp.net', 'id': '3EBDEL123_text', 'type': 'cron-whatsapp-texto', 'fromMe': True, 'timestamp': 9999, 'text': 'mensagem errada', 'source': 'controle/wpp_envios.json', 'sender': 'cron-import'}
        out = self.mod._dedupe_loaded_items([bridge, late])
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].get('deleted'))
        self.assertEqual(out[0].get('deletedAt'), '2026-06-28T16:39:38Z')

    def test_bridge_cron_import_and_fastlane_render_once(self):
        text = 'Gabriella, aqui é Lucas Batista da Zydon. Diagnóstico confirmado. Link: https://meet.google.com/vrt-oqez-ign'
        bridge = {'port': 4603, 'chat': '5531999626769@c.us', 'id': '3EBREAL', 'type': 'append', 'fromMe': True, 'timestamp': 1782672824, 'text': text}
        cron_import = {'port': 4603, 'chat': '5531999626769@c.us', 'id': 'wpp_775_agenda_text', 'type': 'cron-agenda-diagnostico-texto', 'fromMe': True, 'timestamp': 1782672826, 'text': text, 'sender': 'cron-import', 'source': 'controle/wpp_envios.json'}
        fastlane = {'port': 4603, 'chat': '5531999626769@c.us', 'id': 'wpp_envios:5531999626769@c.us:1782672826', 'type': 'seed-wpp-envios', 'fromMe': True, 'timestamp': 1782672826.1, 'text': text, 'source': 'controle/wpp_envios.json:fastlane'}
        out = self.mod.collapse_automation([bridge, cron_import, fastlane])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['id'], '3EBREAL')
        self.assertEqual(out[0].get('automation'), 'Automação')

    def test_frontend_deleted_message_does_not_render_original_text(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('m.deleted?', s)
        self.assertIn('Mensagem apagada', s)

    def test_institutional_lucas_resende_audit_thread_loads_messages(self):
        conv = '4606::5554992020435@s.whatsapp.net'
        if not hasattr(self.mod, 'WPP_ENVIOS_FILE') or not self.mod.WPP_ENVIOS_FILE.exists():
            self.skipTest('ledger local indisponível')
        rows = self.mod._institutional_dispatch_rows_for_chat(4606, '5554992020435@s.whatsapp.net')
        if not rows:
            self.skipTest('fixture Ferramentas Amaral/Lucas Resende indisponível')
        self.assertEqual(self.mod.institutional_dispatch_owner_uid_from_msgs(rows), 'lucas_resende')
        self.assertTrue(self.mod.conversation_id_allowed('rafael', conv))
        msgs = self.mod.messages_for('rafael', conv)
        self.assertGreaterEqual(len(msgs), 1)
        self.assertIn('Franciele', msgs[-1].get('text') or '')

    def test_frontend_detail_loading_has_timeout_retry_and_empty_guard(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('showMessageLoadError', s)
        self.assertIn('Tentar novamente', s)
        self.assertIn('Guardrail mobile: nunca deixar a tela detalhe presa', s)
        self.assertIn('+(c.messages||0)>0', s)
        self.assertIn('timeline veio vazia', s)

    def test_nao_mql_legitimo_is_successful_treatment_not_failed_diagnostic(self):
        row = {
            'type': 'seed-wpp-envios',
            'fromMe': True,
            'status': 'enviado_nao_mql_legitimo',
            'msg_type': 'nao_mql_legitimo_tratativa',
            'empresa': 'Ferramentas Amaral',
            'response': {'success': True, 'messageId': '3EB050D045ADFEA0D075B0'},
        }
        self.assertFalse(self.mod._is_diag_dispatch(row))
        self.assertTrue(self.mod._auto_sent_ok(row))
        c = {'automation': self.mod._auto_summary_init()}
        self.mod._record_automation(c, row, 1782601257)
        auto = self.mod._finalize_automation(c['automation'])
        self.assertEqual(auto.get('risk'), 'ok')
        self.assertEqual(auto.get('failures'), 0)
        self.assertEqual(auto.get('diagnostico'), 'pendente')

    def test_manual_mql_diagnostico_success_responses_do_not_show_automation_failed(self):
        row = {
            'type': 'seed-wpp-envios',
            'fromMe': True,
            'status': 'manual_nao_mql_convertido_mql',
            'msg_type': 'diagnostico_manual_mql',
            'empresa': 'Delícias do Interior',
            'text_response': {'success': True, 'messageId': '3EBTXT'},
            'file_response': {'success': True, 'messageId': '3EBPDF'},
            'followup_response': {'success': True, 'messageId': '3EBFOLLOW'},
            'group_summary_response': {'success': True, 'messageId': '3EBGROUP'},
            'pdf_path': '/tmp/diagnostico.pdf',
        }
        self.assertTrue(self.mod._is_diag_dispatch(row))
        self.assertTrue(self.mod._auto_sent_ok(row))
        c = {'automation': self.mod._auto_summary_init()}
        self.mod._record_automation(c, row, 1782679323)
        auto = self.mod._finalize_automation(c['automation'])
        self.assertEqual(auto.get('risk'), 'ok')
        self.assertEqual(auto.get('failures'), 0)
        self.assertEqual(auto.get('diagnostico'), 'feito')

    def test_manual_mql_partial_response_failure_is_still_flagged_as_failed(self):
        # Falha parcial real (PDF não enviou) não pode ser mascarada por um
        # text_response success=True — o card precisa seguir como "Automação falhou".
        row = {
            'type': 'seed-wpp-envios',
            'fromMe': True,
            'status': 'manual_nao_mql_convertido_mql',
            'msg_type': 'diagnostico_manual_mql',
            'empresa': 'Delícias do Interior',
            'text_response': {'success': True, 'messageId': '3EBTXT'},
            'file_response': {'success': False, 'error': 'upload timeout'},
            'pdf_path': '/tmp/diagnostico.pdf',
        }
        self.assertFalse(self.mod._auto_sent_ok(row))
        c = {'automation': self.mod._auto_summary_init()}
        self.mod._record_automation(c, row, 1782679999)
        auto = self.mod._finalize_automation(c['automation'])
        self.assertEqual(auto.get('risk'), 'falha')
        self.assertEqual(auto.get('failures'), 1)

    def test_correction_send_status_is_successful_not_automation_failed(self):
        row = {
            'type': 'cron-whatsapp-texto',
            'fromMe': True,
            'status': 'correcao_whatsapp_enviada',
            'text': 'Pode deixar, Roberto. Amanhã vou pedir para o Lucas Batista entrar em contato contigo pela manhã.',
        }
        self.assertTrue(self.mod._auto_sent_ok(row))
        c = {'automation': self.mod._auto_summary_init()}
        self.mod._record_automation(c, row, 1782692834)
        auto = self.mod._finalize_automation(c['automation'])
        self.assertEqual(auto.get('risk'), 'ok')
        self.assertEqual(auto.get('failures'), 0)

    def test_delete_revoke_blank_event_does_not_drive_inbox_card_preview(self):
        msg = {'type': 'append', 'fromMe': True, 'text': 'Pode deixar, Roberto.', 'timestamp': 100}
        revoke = {'type': 'append', 'fromMe': True, 'text': '', 'timestamp': 110, 'deleted_message_id': '3EBOLD', 'delete_revoke_message_id': '3EBREVOKE'}
        self.assertTrue(self.mod._visible_for_card_last(msg))
        self.assertFalse(self.mod._visible_for_card_last(revoke))

    def test_mobile_cards_are_compact_and_automation_badge_is_single(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('padding:8px 10px 7px 30px', s)
        self.assertIn('.inst-map{display:flex;flex-wrap:nowrap', s)
        self.assertIn('max-width:52%', s)
        start = s.index('function automationBadge(c)')
        end = s.index('function sharedBadge(c)', start)
        block = s[start:end]
        self.assertIn('Um único badge de automação por card', block)
        self.assertNotIn("let out=''", block)
        self.assertNotIn("out+=", block)

    def test_inbox_card_uses_real_clock_time_not_relative_age(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('function cardTime(ts)', s)
        self.assertIn('horário/data real, não idade relativa tipo “5min”', s)
        self.assertIn('${esc(cardTime(c.lastTime))}', s)
        self.assertIn('title="${esc(dt(c.lastTime))}"', s)
        self.assertNotIn('${relTime(c.lastTime)}</span></div>', s)

    def test_inbox_card_does_not_duplicate_recent_timestamp(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        start = s.index('function slaTag(c)')
        end = s.index('/* ---------- render ---------- */', start)
        block = s[start:end]
        self.assertIn('idade da última interação já aparece uma vez', block)
        self.assertIn("return ''", block)
        self.assertNotIn('enviado há ${relTime(c.lastTime)}', block)
        self.assertIn('há ${relTime(c.lastTime)} sem resposta', block)

    def test_frontend_renders_outbound_automation_as_bubble_not_audit_card(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('function isEvent(m){return false}', s)
        self.assertIn("<div class=\"brow ${m.fromMe?'out':'in'}", s)
        self.assertIn('m.automation?', s)

    def test_diagnostic_pdf_with_different_pretty_names_collapses_to_one_bubble(self):
        real = {
            'type': 'append', 'fromMe': True, 'chat': '5511996077972@s.whatsapp.net',
            'id': '3EBPDFREAL', 'timestamp': 1000, 'mediaType': 'document',
            'mimetype': 'application/pdf',
            'mediaName': 'Grupo Automec - Potencial de Digitalizacao B2B.pdf',
        }
        synthetic = {
            'type': 'cron-mql-pdf', 'fromMe': True, 'chat': '5511996077972@s.whatsapp.net',
            'id': 'wpp_123_mql_pdf', 'timestamp': 1001,
            'text': 'PDF enviado: Gestor Negócios Atacado Grupo Automec GM. - Potencial de Digitalizacao B2B.pdf',
            'mediaType': 'document', 'mimetype': 'application/pdf',
            'mediaName': 'Gestor Negócios Atacado Grupo Automec GM. - Potencial de Digitalizacao B2B.pdf',
        }
        collapsed = self.mod.collapse_automation([real, synthetic])
        pdfs = [m for m in collapsed if self.mod._is_diagnostic_pdf_message(m)]
        self.assertEqual(len(pdfs), 1)
        self.assertEqual(pdfs[0]['id'], '3EBPDFREAL')
        self.assertIn('Automação', pdfs[0].get('automation', ''))

    def test_inbox_list_is_paginated_for_mobile_performance(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('const LIST_PAGE_SIZE=60', s)
        self.assertIn('list.slice(0, Math.min(listVisibleCount, list.length))', s)
        self.assertIn('function showMoreCards()', s)
        self.assertIn('list-page-info', s)
        self.assertIn('Mostrar mais', s)

    def test_mobile_usability_perf_features_exist_across_screens(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        # Tela principal: busca não recalcula a lista a cada tecla, preserva scroll
        # e usa snapshot leve para pintar a tela antes do refresh real.
        self.assertIn('function debounce(fn, wait=350)', s)
        self.assertIn('debouncedSearch=debounce', s)
        self.assertIn('function saveListScroll()', s)
        self.assertIn('function restoreListScroll()', s)
        self.assertIn('sessionStorage.setItem(listScrollKey()', s)
        self.assertIn('restoreInboxSnapshot()', s)
        self.assertIn('saveInboxSnapshot()', s)
        self.assertIn('function refreshInboxNewOnly()', s)
        self.assertIn('Atualizar a lista de conversas sem recarregar a página inteira', s)
        # Cards compactos: excesso de tags vira +N para reduzir altura/ruído.
        self.assertIn('function compactBadges(items, max=3)', s)
        self.assertIn('compactBadges(statusBadges,3)', s)
        self.assertIn('tag-more', s)
        # Outras telas/modais: listas grandes de Gestão/Foco têm limite visual.
        self.assertIn('const ANALYTICS_MODAL_LIMIT=80', s)
        self.assertIn('function limitedHtmlRows(rows, renderFn', s)
        self.assertIn('limitedHtmlRows(rows, pipeLeadModalRow', s)
        self.assertIn('limitedHtmlRows(rows, dispatchEventRow', s)
        self.assertIn('modal-limit-note', s)

    def test_login_uses_channel_brand_palette_not_green_button(self):
        html = self.mod.login_page_html({'client_id': 'x', 'client_secret': 'y'})
        self.assertIn('background:#0B0F0C', html)
        self.assertIn('color:#CDEB00', html)
        self.assertNotIn('background:#1F3D2B;color:#FFFFFF', html)
        self.assertIn('width:min(100%,480px)', html)

    def test_auth_session_ttls_are_business_safe(self):
        self.assertGreaterEqual(self.mod.SESSION_TTL, 7 * 24 * 3600)
        self.assertGreaterEqual(self.mod.OAUTH_STATE_TTL, 3600)

    def test_health_probe_responds_before_auth(self):
        # Regressão incidente 20260629T123227Z: /health 8280 estourava o timeout
        # de 3s do watchdog sob contenção de GIL em rajada de disparo. auth() relê
        # o env do OAuth do disco + valida HMAC a cada request e o uid nem era
        # usado pelo /health; o probe de liveness deve responder antes de auth().
        s = MODULE_PATH.read_text(encoding='utf-8')
        do_get = s[s.index('def do_GET(self):'):s.index('def do_POST(self):')]
        health_idx = do_get.index("if path=='/health'")
        auth_idx = do_get.index('uid=self.auth()')
        self.assertLess(
            health_idx, auth_idx,
            '/health deve retornar antes de uid=self.auth() para nao competir por disco/GIL',
        )


    # --- Foco SDR deve permanecer HubSpot-first ---------------------------------

    def test_experimental_conversation_queues_are_not_rendered_in_foco(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('function drawFocus()', s)
        foco_start = s.index('function drawFocus()')
        foco_end = s.index('function filteredCards()', foco_start)
        foco_block = s[foco_start:foco_end]
        # Incidente visual/operacional 2026-06-29: /foco não deve misturar cards
        # de conversa e agenda outcome experimental com o pipe HubSpot.
        self.assertNotIn('todayActionsBlock()', foco_block)
        self.assertNotIn('rescueQueueBlock()', foco_block)
        self.assertNotIn('agendaOutcomeBlock()', foco_block)
        self.assertIn('sdrTaskFocusBlock()', foco_block)
        self.assertIn('Pipe de apoio: etapas x atividades', foco_block)
        self.assertIn('pipeSimpleSummary()', foco_block)
        self.assertIn('pfStageMatrix()', foco_block)

    def test_foco_is_task_first_by_sdr_status_and_day(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('function sdrTaskFocusBlock()', s)
        self.assertIn('function pipelineTaskRows()', s)
        self.assertIn('Foco SDR: tarefas e atividades', s)
        self.assertIn('Atrasadas', s)
        self.assertIn('Hoje', s)
        self.assertIn('Próximas', s)
        self.assertIn('Concluídas', s)
        self.assertIn('Por SDR', s)
        self.assertIn('task-day-grid', s)
        self.assertIn('openOwnerTasks', s)
        self.assertIn('Escopo padrão: 5 primeiras etapas do pipe e os 3 SDRs ativos.', s)
        self.assertIn('focusFilterControls()', s)
        self.assertIn("setPipeFilter('owner'", s)
        self.assertIn("setPipeFilter('stage'", s)
        self.assertIn("setPipeFilter('task'", s)
        self.assertIn('Realizado vs esperado hoje', s)
        self.assertIn('task-meaning', s)
        self.assertIn('function taskTypeLabel(t)', s)
        self.assertIn('function taskPatternLabel(t)', s)
        self.assertIn('function taskGroupBars(tasks)', s)
        self.assertIn('Por tipo de ação', s)
        self.assertIn('Por padrão da descrição', s)
        self.assertIn('Separa ação real do SDR de registro de envio/automação', s)
        self.assertIn('function taskIsAutomationRecord(t)', s)
        self.assertIn("return 'WhatsApp / automação'", s)
        self.assertIn("return 'Preparar diagnóstico'", s)
        self.assertIn('não é fila de tarefa humana', s)
        self.assertIn('task-scope-strip', s)
        self.assertNotIn("return 'Diagnóstico';", s)
        self.assertIn('openTaskGroup', s)

    def test_pipeline_focus_supervisor_scope_is_limited_to_three_sdrs(self):
        self.assertEqual(set(self.mod._owner_ids_for_user('rafael')), set(self.mod.PLAYBOOK_OWNER_IDS.keys()))
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn("pipeline_focus_v8_task_first", s)
        self.assertIn('note_map={}', s)
        self.assertIn('call_map={}', s)
        self.assertIn('pipeline_focus_snapshot_{safe}.json', s)
        self.assertIn('_pipeline_focus_snapshot_get(uid)', s)
        self.assertIn('_pipeline_focus_snapshot_set(uid, out)', s)
        block = s[s.index('function sdrTaskFocusBlock()'):s.index('function openOwnerTasks', s.index('function sdrTaskFocusBlock()'))]
        self.assertNotIn("Fonte: HubSpot, read-only", block)

    def test_today_actions_block_is_not_user_visible_in_foco_until_validated(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('function todayActionsBlock()', s)
        block_start = s.index('function todayActionsBlock()')
        block_end = s.index('function lossByOwnerBlock()', block_start)
        block = s[block_start:block_end]
        for term in ('audit', 'ledger', 'debug', 'evento técnico', 'fonte', 'log'):
            self.assertNotIn(term, block)

    # --- P0-2: Perdas por SDR --------------------------------------------------

    def test_loss_ranking_by_owner_in_dispatch_stats(self):
        stats = self.mod.dispatch_stats('rafael', 14)
        lr = stats.get('lossRanking') or {}
        self.assertIn('items', lr)
        self.assertIn('byOwner', lr)
        self.assertIsInstance(lr['byOwner'], list)

    def test_loss_ranking_by_owner_has_expected_fields(self):
        stats = self.mod.dispatch_stats('rafael', 14)
        by_owner = (stats.get('lossRanking') or {}).get('byOwner') or []
        if by_owner:
            first = by_owner[0]
            self.assertIn('owner', first)
            self.assertIn('respondedNoMeeting', first)
            self.assertIn('meetingNoOutcome', first)
            self.assertIn('noResponseFollowup', first)
            self.assertIn('sent', first)

    def test_loss_by_owner_block_exists_in_gestao(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('function lossByOwnerBlock()', s)
        self.assertIn('Perdas por SDR', s)
        mgmt_start = s.index('function drawManagement()')
        mgmt_end = s.index('function pipelineSummaryBlock()', mgmt_start)
        mgmt_block = s[mgmt_start:mgmt_end]
        self.assertIn('lossByOwnerBlock()', mgmt_block)

    # --- P0-3: Abordagens para revisar -----------------------------------------

    def test_approach_review_in_dispatch_stats(self):
        stats = self.mod.dispatch_stats('rafael', 14)
        self.assertIn('approachReview', stats)
        self.assertIsInstance(stats['approachReview'], list)

    def test_approach_review_min_sample_rule(self):
        import time as _time
        from pathlib import Path as _Path
        import os as _os
        old_data_dir = self.mod.DATA_DIR
        old_wpp = self.mod.WPP_ENVIOS_FILE
        old_rows = dict(getattr(self.mod, '_WPP_ENVIOS_ROWS_CACHE', {}))
        old_hist = dict(getattr(self.mod, '_HISTORY_RAW_CACHE', {}))
        tmp = _Path('/tmp/channel_v2_approach_review_test')
        tmp.mkdir(parents=True, exist_ok=True)
        now = _time.time()
        def iso(ts):
            return _time.strftime('%Y-%m-%dT%H:%M:%S+00:00', _time.gmtime(ts))
        chat = '5511999000042@s.whatsapp.net'
        # 25 envios de "primeiro contato" com apenas 1 resposta (~4% resposta < 5%)
        # Todos no mesmo dia (intervalo de 5 min) para ficarem na mesma versão de abordagem
        rows = [
            {'date_tz': iso(now - 300 * (i + 1)), 'to': f'5511999{i:06d}@s.whatsapp.net',
             'bridge_port': 4601, 'status': 'enviado_primeiro_contato',
             'msg_type': 'primeiro_contato', 'text': 'Oi, aqui é teste versão fixture.'}
            for i in range(25)
        ]
        # Apenas 1 resposta para 1 chat
        (tmp / 'wpp_envios.json').write_text(
            __import__('json').dumps({'envios': rows}), encoding='utf-8')
        (tmp / 'history_4601.json').write_text(
            __import__('json').dumps([
                {'port': 4601, 'chat': '5511999000000@s.whatsapp.net', 'fromMe': False,
                 'text': 'Olá, pode me falar mais?', 'timestamp': now - 100},
            ]), encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod.WPP_ENVIOS_FILE = tmp / 'wpp_envios.json'
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            self.mod._HISTORY_RAW_CACHE = {}
            stats = self.mod.dispatch_stats('rafael', 14)
            ar = stats.get('approachReview') or []
            # Deve encontrar a abordagem com 25 envios e ~4% resposta
            matched = [x for x in ar if x.get('parentKey') == 'primeiro_contato']
            self.assertTrue(len(matched) >= 1, 'approachReview deve flagrar primeiro_contato com amostra >= 20 e resposta < 5%')
            self.assertGreaterEqual(matched[0].get('sent', 0), 20)
            self.assertLess(matched[0].get('responseRate', 100), 5.0)
            # Versão com menos de 20 envios não deve aparecer
            small = [x for x in ar if x.get('sent', 0) < 20]
            self.assertEqual(small, [], 'approachReview não deve incluir abordagem com amostra < 20')
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod.WPP_ENVIOS_FILE = old_wpp
            self.mod._WPP_ENVIOS_ROWS_CACHE = old_rows
            self.mod._HISTORY_RAW_CACHE = old_hist

    def test_approach_review_block_exists_in_gestao(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('function approachReviewBlock()', s)
        self.assertIn('Abordagens para revisar', s)
        self.assertIn('Revisar abertura', s)
        self.assertIn('CTA fraco para agenda', s)
        mgmt_start = s.index('function drawManagement()')
        mgmt_end = s.index('function pipelineSummaryBlock()', mgmt_start)
        mgmt_block = s[mgmt_start:mgmt_end]
        self.assertIn('approachReviewBlock()', mgmt_block)

    # --- P1-1: Status das agendas ----------------------------------------------

    def test_agenda_outcome_in_dispatch_stats(self):
        stats = self.mod.dispatch_stats('rafael', 14)
        self.assertIn('agendaOutcome', stats)
        ao = stats['agendaOutcome']
        self.assertIn('summary', ao)
        self.assertIn('future', ao)
        self.assertIn('realized', ao)
        self.assertIn('pastNoOutcome', ao)
        self.assertIn('cancelled', ao)
        self.assertIn('byOwner', ao)
        s = ao['summary']
        self.assertIn('total', s)
        self.assertIn('future', s)
        self.assertIn('realized', s)
        self.assertIn('pastNoOutcome', s)
        self.assertIn('cancelled', s)
        self.assertEqual(
            s['total'],
            s['future'] + s['realized'] + s['pastNoOutcome'] + s['cancelled'],
            'summary.total deve ser a soma das categorias'
        )

    def test_agenda_outcome_future_not_counted_as_realized(self):
        import time as _time
        from pathlib import Path as _Path
        old_data_dir = self.mod.DATA_DIR
        old_wpp = self.mod.WPP_ENVIOS_FILE
        old_rows = dict(getattr(self.mod, '_WPP_ENVIOS_ROWS_CACHE', {}))
        tmp = _Path('/tmp/channel_v2_agenda_outcome_test')
        tmp.mkdir(parents=True, exist_ok=True)
        now = _time.time()
        future_ts = now + 86400 * 2  # 2 dias no futuro
        def iso(ts):
            return _time.strftime('%Y-%m-%dT%H:%M:%SZ', _time.gmtime(ts))
        rows = [
            {'date_tz': iso(now - 3600), 'to': '5511999000001@s.whatsapp.net',
             'bridge_port': 4601, 'status': 'enviado_agenda', 'msg_type': 'agenda',
             'meeting_id': 'meet_future_001',
             'meeting_start': iso(future_ts),
             'text': 'Confirmação de reunião futura.'},
        ]
        (tmp / 'wpp_envios.json').write_text(
            __import__('json').dumps({'envios': rows}), encoding='utf-8')
        (tmp / 'history_4601.json').write_text('[]', encoding='utf-8')
        try:
            self.mod.DATA_DIR = tmp
            self.mod.WPP_ENVIOS_FILE = tmp / 'wpp_envios.json'
            self.mod._WPP_ENVIOS_ROWS_CACHE = {'mtime': 0, 'rows': []}
            self.mod._HISTORY_RAW_CACHE = {}
            stats = self.mod.dispatch_stats('rafael', 14)
            ao = stats.get('agendaOutcome') or {}
            s = ao.get('summary') or {}
            self.assertEqual(s.get('realized', 0), 0, 'reunião futura NÃO deve entrar em realized')
            self.assertGreaterEqual(s.get('future', 0), 0)
        finally:
            self.mod.DATA_DIR = old_data_dir
            self.mod.WPP_ENVIOS_FILE = old_wpp
            self.mod._WPP_ENVIOS_ROWS_CACHE = old_rows
            self.mod._HISTORY_RAW_CACHE = {}

    def test_agenda_outcome_block_exists_in_gestao_only(self):
        s = MODULE_PATH.read_text(encoding='utf-8')
        self.assertIn('function agendaOutcomeBlock()', s)
        self.assertIn('Status das agendas', s)
        self.assertIn('atualizar status da reunião', s)
        foco_start = s.index('function drawFocus()')
        foco_end = s.index('function filteredCards()', foco_start)
        self.assertNotIn('agendaOutcomeBlock()', s[foco_start:foco_end])
        mgmt_start = s.index('function drawManagement()')
        mgmt_end = s.index('function pipelineSummaryBlock()', mgmt_start)
        self.assertIn('agendaOutcomeBlock()', s[mgmt_start:mgmt_end])


if __name__ == '__main__':
    unittest.main()
