import importlib.util
import json
import re
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
WRAPPER = Path('/root/.hermes/scripts/zydon_sdr_followup_unificado_5min.sh')
MQL = ROOT / 'scripts' / 'mql_sdr_followup.py'
CADENCIA = ROOT / 'scripts' / 'cadencia_primeiro_contato.py'
DISPARO = ROOT / 'disparo_dinamico.py'


def load_disparo_module():
    spec = importlib.util.spec_from_file_location('disparo_dinamico_test', DISPARO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_mql_module():
    spec = importlib.util.spec_from_file_location('mql_sdr_followup', MQL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_cadencia_module():
    spec = importlib.util.spec_from_file_location('cadencia_primeiro_contato_test', CADENCIA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FollowupIncidentSafetyTest(unittest.TestCase):
    def test_unified_wrapper_never_runs_mql_followup_inside_short_cron(self):
        text = WRAPPER.read_text(encoding='utf-8')
        self.assertNotIn('python3 scripts/mql_sdr_followup.py', text)
        self.assertNotRegex(
            text,
            r'timeout\s+(?:[1-9][0-9]?|[1-5][0-9]{2})s\s+python3\s+scripts/(?:mql_sdr_followup|cadencia_primeiro_contato)\.py',
            'Scripts que enviam sequência com pausa não podem rodar com timeout curto; isso causou repetição de saudação em 30/06.',
        )

    def test_unified_wrapper_runs_cadencia_in_worker_owned_mode(self):
        text = WRAPPER.read_text(encoding='utf-8')
        self.assertIn('ZYDON_CADENCIA_WORKER_OWNED=1', text)
        self.assertRegex(text, r'env\s+ZYDON_CADENCIA_WORKER_OWNED=1\s+python3\s+scripts/cadencia_primeiro_contato\.py')

    def test_mql_followup_dedupes_against_real_whatsapp_history_even_without_ledger(self):
        mod = load_mql_module()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            old_wa_data = mod.WA_DATA
            try:
                mod.WA_DATA = tmp
                source_dt = datetime(2026, 6, 30, 9, 0, tzinfo=timezone.utc)
                rows = [
                    {
                        'fromMe': True,
                        'timestamp': source_dt.timestamp() + 120,
                        'text': 'Bom dia, Jander. Tudo bem?',
                        'rawKey': {
                            'remoteJid': '556281238012@s.whatsapp.net',
                            'fromMe': True,
                            'id': '3EB_TEST_DUP',
                        },
                    }
                ]
                (tmp / 'history_4603.json').write_text(json.dumps(rows), encoding='utf-8')
                rec = {
                    'to': '556281238012@s.whatsapp.net',
                    'deal_id': 'deal-jander',
                    'date_tz': source_dt.isoformat(),
                }
                self.assertTrue(
                    mod.already_followed([], rec),
                    'Mesmo sem ledger, mensagem real já existente no histórico deve bloquear novo Follow 1.',
                )
            finally:
                mod.WA_DATA = old_wa_data


    def test_atalaia_phone_variants_block_second_sender_after_mql_diagnostico(self):
        mod = load_disparo_module()
        envios = [
            {
                'status': 'enviado_lead',
                'bridge_port': 4609,
                'to': '553598889190@s.whatsapp.net',
                'phone': '35998889190',
                'empresa': 'Atalaia calçados militares',
            }
        ]
        blocked = mod.envios_phone_set(envios)
        self.assertIn('35998889190', blocked)
        self.assertIn('3598889190', blocked)
        self.assertTrue(mod.same_phone_key('5535998889190@s.whatsapp.net', '553598889190@s.whatsapp.net'))

    def test_disparo_dinamico_worker_owned_producer_uses_sequence_and_completion(self):
        mod = load_disparo_module()
        calls = []
        old_record = mod.record_dispatch_worker_owned
        try:
            mod.record_dispatch_worker_owned = lambda **kw: calls.append(kw) or {'ok': True, 'dispatch_id': 'dsp-first-contact-test'}
            lead = {
                'jid': '5511999990000@s.whatsapp.net',
                'deal_id': 'deal-1',
                'contact_id': 'contact-1',
                'nome': 'Ana',
                'tel_fmt': '(11) 99999-0000',
                'empresa': 'Empresa Teste',
            }
            msg = 'Bom dia, Ana.\n\nContexto rápido da Zydon para B2B.\n\nFaz sentido conversar?'
            res = mod.enqueue_worker_owned_first_contact(lead, 4605, msg, owner_id='86265630', owner_name='Breno', sender_label='Breno', sender_phone='553484325076')
            self.assertTrue(res['ok'])
            self.assertEqual(calls[0]['completion_type'], 'first_contact')
            self.assertEqual(calls[0]['origin'], 'proatividade')
            self.assertEqual(calls[0]['nature'], 'first_contact')
            self.assertGreaterEqual(len(calls[0]['parts']), 2)
            self.assertEqual(len(calls[0]['delay_schedule']), len(calls[0]['parts']) - 1)
            self.assertEqual(calls[0]['deal_id'], 'deal-1')
        finally:
            mod.record_dispatch_worker_owned = old_record

    def test_cadencia_worker_owned_producer_uses_sequence_and_completion(self):
        mod = load_cadencia_module()
        calls = []
        old_record = getattr(mod, 'record_dispatch_worker_owned', None)
        try:
            mod.record_dispatch_worker_owned = lambda **kw: calls.append(kw) or {'ok': True, 'dispatch_id': 'dsp-cadence-test'}
            lead = {
                'jid': '5511999991111@s.whatsapp.net',
                'deal_id': 'deal-cad-1',
                'contact_id': 'contact-cad-1',
                'nome': 'Ana',
                'empresa': 'Empresa Cadência',
                'owner_key': 'sarah',
                'owner_id': '88063842',
                'owner_name': 'Sarah',
                'next_attempt': 3,
            }
            sender = {'sender_name': 'Gustavo', 'port': 4610, 'sender_phone': '553499999999', 'is_communicator': True}
            text = 'Bom dia, Ana.\n\nParte dois com contexto real.\n\nQuando o seu cliente vai fazer um pedido, ele ainda precisa chamar alguém no WhatsApp?'
            res = mod.enqueue_worker_owned_cadence(lead, sender, text)
            self.assertTrue(res['ok'])
            self.assertEqual(calls[0]['completion_type'], 'followup_cadence')
            self.assertEqual(calls[0]['origin'], 'followup')
            self.assertEqual(calls[0]['nature'], 'followup_f3')
            self.assertEqual(calls[0]['attempt_number'], 3)
            self.assertEqual(calls[0]['port'], 4610)
            self.assertGreaterEqual(len(calls[0]['parts']), 2)
            self.assertEqual(len(calls[0]['delay_schedule']), len(calls[0]['parts']) - 1)
            self.assertEqual(calls[0]['deal_id'], 'deal-cad-1')
        finally:
            if old_record is not None:
                mod.record_dispatch_worker_owned = old_record

    def test_choose_sender_keeps_active_router_chip_for_lead(self):
        mod = load_cadencia_module()
        old_choose = mod.choose_outbound_port
        old_bridge_sender = mod.bridge_sender_for_lead
        try:
            mod.choose_outbound_port = lambda owner_uid, phone_or_jid, **kw: {
                'port': 4611,
                'mode': 'active_contact_lock',
                'reason': 'lead já ativo no chip 4611',
            }
            mod.bridge_sender_for_lead = lambda lead, port, label, phone: {
                'port': port,
                'sender_name': label,
                'sender_phone': phone,
                'owner_uid': lead.get('owner_key'),
            }
            lead = {
                'jid': '553499999999@s.whatsapp.net',
                'owner_key': 'sarah',
                'owner_name': 'Sarah',
                'deal_id': 'deal-router',
                'ports': [4601, 4611],
            }
            sender, errors = mod.choose_sender_for_lead(lead, envios=[], use_communicators=False)
        finally:
            mod.choose_outbound_port = old_choose
            mod.bridge_sender_for_lead = old_bridge_sender
        self.assertIsNone(errors)
        self.assertEqual(sender['port'], 4611)
        self.assertEqual(sender['routing_mode'], 'active_contact_lock')

    def test_followup_cadence_completion_writes_ledger_after_worker_send(self):
        spec = importlib.util.spec_from_file_location('whatsapp_worker_completions_test', ROOT / 'scripts' / 'whatsapp_worker_completions.py')
        completion = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(completion)
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            old_wpp = completion.WPP
            old_create = completion.create_cadence_task
            old_update = completion.move_cadence_deal_if_needed
            try:
                completion.WPP = tmp / 'wpp_envios.json'
                completion.WPP.write_text('{"envios": []}', encoding='utf-8')
                completion.create_cadence_task = lambda row, text, response: 'task-cad-1'
                completion.move_cadence_deal_if_needed = lambda row: '1214320997'
                row = {
                    'jid': '5511999991111@s.whatsapp.net',
                    'text': 'Follow 3 aprovado',
                    'port': 4610,
                    'sender_name': 'Gustavo',
                    'sender_phone': '553499999999',
                    'sender_is_communicator': True,
                    'owner_uid': 'sarah',
                    'owner_key': 'sarah',
                    'owner_id': '88063842',
                    'owner_name': 'Sarah',
                    'lead_name': 'Ana',
                    'empresa': 'Empresa Cadência',
                    'deal_id': 'deal-cad-1',
                    'contact_id': 'contact-cad-1',
                    'attempt_number': 3,
                    'completion_type': 'followup_cadence',
                }
                res = completion.complete_after_send(row, {'success': True, 'messageId': 'MSG-CAD-1', 'messageIds': ['MSG-A','MSG-B','MSG-C']})
                self.assertTrue(res['ok'])
                data = json.loads(completion.WPP.read_text(encoding='utf-8'))
                envios = data['envios']
                self.assertEqual(len(envios), 1)
                self.assertEqual(envios[0]['msg_type'], 'primeiro_contato_cadencia')
                self.assertEqual(envios[0]['attempt_number'], 3)
                self.assertEqual(envios[0]['task_id'], 'task-cad-1')
                self.assertEqual(envios[0]['messageId'], 'MSG-CAD-1')
            finally:
                completion.WPP = old_wpp
                completion.create_cadence_task = old_create
                completion.move_cadence_deal_if_needed = old_update

    def test_cadence_send_window_runs_until_20_brt(self):
        mod = load_cadencia_module()
        self.assertTrue(mod.cadence_send_window(datetime(2026, 7, 1, 19, 59, tzinfo=mod.BRT)))
        self.assertFalse(mod.cadence_send_window(datetime(2026, 7, 1, 20, 0, tzinfo=mod.BRT)))
        self.assertTrue(mod.cadence_send_window(datetime(2026, 7, 3, 19, 30, tzinfo=mod.BRT)))

    def test_port_limits_count_unique_people_not_message_parts(self):
        mod = load_disparo_module()
        now = datetime.now(timezone(timedelta(hours=-3))).isoformat()
        envios = [
            {'bridge_port': 4606, 'to': '5511999999999@s.whatsapp.net', 'date_tz': now, 'messageId': 'm1', 'text_status': 'ok'},
            {'bridge_port': 4606, 'to': '5511999999999@s.whatsapp.net', 'date_tz': now, 'messageId': 'm2', 'text_status': 'ok'},
            # Mesmo lead em variante BR sem 9º dígito: continua contando como 1 pessoa.
            {'bridge_port': 4606, 'to': '551199999999@s.whatsapp.net', 'date_tz': now, 'messageId': 'm3', 'text_status': 'ok'},
            {'bridge_port': 4606, 'to': '5511888888888@s.whatsapp.net', 'date_tz': now, 'messageId': 'm4', 'text_status': 'ok'},
        ]
        self.assertEqual(mod.envios_porta_periodo(envios, 4606, seconds=3600), 2)
        self.assertEqual(mod.envios_porta_periodo(envios, 4606, same_day=True), 2)


if __name__ == '__main__':
    unittest.main()
