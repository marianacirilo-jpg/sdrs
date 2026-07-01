# -*- coding: utf-8 -*-
import unittest
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import non_mql_legit_outreach as n


class NonMqlProcessRigidityTests(unittest.TestCase):
    def test_process_identity_schedule_and_defaults_are_fixed_in_code(self):
        self.assertEqual(n.PROCESS_ID, 'zydon-nao-mql-tratativa-legitima')
        self.assertEqual(n.PROCESS_VERSION, 'rafael-approved-2026-06-30-v1')
        self.assertEqual(n.FIXED_BRT_TIMEZONE, 'America/Sao_Paulo')
        self.assertEqual(n.FIXED_SEND_WEEKDAYS_BRT, (0, 1, 2, 3, 4, 5, 6))
        self.assertEqual(n.FIXED_SEND_START_HOUR_BRT, 7)
        self.assertEqual(n.FIXED_SEND_END_HOUR_BRT, 22)
        self.assertEqual(n.DEFAULT_SEND_LIMIT, 999)
        self.assertEqual(n.DEFAULT_SLEEP_SECONDS, 10)

    def test_communicators_are_fixed_in_code(self):
        # Comunicadores fixos aprovados: Lucas Resende 4606, Mariana 4600, Rafael 4607.
        self.assertEqual(
            [(s['port'], s['name']) for s in n.SENDERS],
            [(4606, 'Lucas Resende'), (4600, 'Mariana'), (4607, 'Rafael')],
        )

    def test_outbound_window_is_rigid_and_brt_based(self):
        tz = ZoneInfo('America/Sao_Paulo')
        self.assertFalse(n.within_fixed_send_window(datetime(2026, 6, 30, 6, 59, tzinfo=tz)))
        self.assertTrue(n.within_fixed_send_window(datetime(2026, 6, 30, 7, 0, tzinfo=tz)))
        self.assertTrue(n.within_fixed_send_window(datetime(2026, 6, 30, 21, 59, tzinfo=tz)))
        self.assertFalse(n.within_fixed_send_window(datetime(2026, 6, 30, 22, 0, tzinfo=tz)))
        self.assertTrue(n.within_fixed_send_window(datetime(2026, 7, 4, 12, 0, tzinfo=tz)))

    def test_approved_message_text_is_fixed_except_name_sender_and_context(self):
        props = {'firstname': 'joana'}
        research = {'motivo': 'operação pequena sem ICP claro'}
        sender = {'name': 'Mariana'}
        msg = n.build_message(props, research, sender)
        self.assertEqual(msg, (
            'Oi Joana, tudo bem?\n\n'
            'Aqui é a Mariana, da Zydon, plataforma de eCommerce B2B.\n\n'
            'Vi que vocês demonstraram interesse na Zydon e quis te chamar por aqui para entender melhor.\n\n'
            'A Zydon é voltada para indústrias, distribuidores e atacadistas que vendem para outras empresas '
            'e querem organizar pedidos recorrentes em um portal B2B próprio.\n\n'
            'Pelo que conseguimos entender até aqui, não ficou tão claro se esse é o momento ou o tipo de operação de vocês.\n\n'
            'Como você imagina que a Zydon poderia te ajudar hoje?'
        ))

    def test_domain_mismatch_uses_only_the_approved_context_line(self):
        props = {'firstname': ''}
        research = {'motivo': 'domínio do e-mail não pertence à empresa informada'}
        sender = {'name': 'Lucas Resende'}
        msg = n.build_message(props, research, sender)
        self.assertIn(n.APPROVED_CONTEXT_LINE_MISMATCH, msg)
        self.assertNotIn(n.APPROVED_CONTEXT_LINE_STANDARD, msg)


if __name__ == '__main__':
    unittest.main()
