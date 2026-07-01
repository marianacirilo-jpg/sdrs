import importlib.util
from pathlib import Path
import unittest

ROOT = Path('/root/.hermes/zydon-prospeccao')
SPEC = importlib.util.spec_from_file_location('whatsapp_routing', ROOT / 'scripts' / 'whatsapp_routing.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class WhatsAppRoutingTests(unittest.TestCase):
    def setUp(self):
        self.ports = {
            4601: {'label': 'Sarah 1', 'owner': 'sarah', 'role': 'sdr'},
            4611: {'label': 'Sarah 2', 'owner': 'sarah', 'role': 'sdr'},
            4603: {'label': 'Lucas', 'owner': 'lucas', 'role': 'sdr'},
            4607: {'label': 'Rafael', 'owner': 'rafael', 'role': 'comunicador'},
        }
        self.users = {
            'sarah': {'ports': [4601, 4611], 'role': 'sdr'},
            'lucas': {'ports': [4603], 'role': 'sdr'},
        }

    def test_sdr_ports_allows_multiple_chips_for_same_sdr(self):
        self.assertEqual(mod.sdr_ports('sarah', ports=self.ports, users=self.users), [4601, 4611])

    def test_existing_thread_keeps_same_chip_for_lead(self):
        rows = [
            {'bridge_port': 4611, 'to': '553499999999@s.whatsapp.net', 'date_tz': '2026-06-30T10:00:00-03:00'},
            {'bridge_port': 4601, 'to': '553488888888@s.whatsapp.net', 'date_tz': '2026-06-30T11:00:00-03:00'},
        ]
        got = mod.choose_outbound_port('sarah', '3499999999', rows=rows, ports=self.ports, users=self.users)
        self.assertEqual(got['port'], 4611)
        self.assertEqual(got['mode'], 'existing_thread')

    def test_new_thread_balances_only_owner_sdr_chips_not_comunicador(self):
        rows = [
            {'bridge_port': 4601, 'to': '553400000001@s.whatsapp.net'},
            {'bridge_port': 4601, 'to': '553400000002@s.whatsapp.net'},
            {'bridge_port': 4607, 'to': '553400000003@s.whatsapp.net'},
        ]
        got = mod.choose_outbound_port('sarah', '553477777777', lead_key='deal-1', rows=rows, ports=self.ports, users=self.users)
        self.assertEqual(got['port'], 4611)
        self.assertEqual(got['mode'], 'new_thread_balanced')

    def test_without_sdr_port_fails_closed(self):
        got = mod.choose_outbound_port('missing', '553477777777', ports=self.ports, users=self.users)
        self.assertIsNone(got['port'])
        self.assertEqual(got['mode'], 'no_sdr_port')

    # --- Privacidade: grupo/broadcast/chip interno nunca vira envio ---

    def test_blocks_group_broadcast_and_internal_chip_targets(self):
        for target in (
            '120363408131718880@g.us',
            'status@broadcast',
            '5511999999999@broadcast',
            '553484325076@s.whatsapp.net',  # Breno interno
            '553484291640@s.whatsapp.net',  # Sarah interno
        ):
            got = mod.choose_outbound_port('sarah', target, ports=self.ports, users=self.users)
            self.assertIsNone(got['port'], target)
            self.assertEqual(got['mode'], 'blocked_private_target', target)

    # --- Trava anti-duplo-contato via fila unificada ---

    def test_active_contact_lock_keeps_chip_already_talking_to_lead(self):
        # Lead já tem disparo ativo no chip 4611 (da Sarah). Deve manter 4611
        # mesmo que o balanceamento normal escolhesse outro.
        dispatches = [
            {'port': 4611, 'jid': '553499999999@s.whatsapp.net', 'status': 'queued',
             'created_at': '2026-07-01T09:00:00+00:00'},
        ]
        got = mod.choose_outbound_port('sarah', '3499999999', dispatches=dispatches,
                                       ports=self.ports, users=self.users)
        self.assertEqual(got['port'], 4611)
        self.assertEqual(got['mode'], 'active_contact_lock')

    def test_active_contact_conflict_when_other_sdr_already_talking(self):
        # Lead já está em contato ativo por chip de OUTRO SDR (Lucas/4603).
        # A Sarah não pode abrir um segundo contato.
        dispatches = [
            {'port': 4603, 'phone': '553499999999', 'status': 'locked',
             'created_at': '2026-07-01T09:00:00+00:00'},
        ]
        got = mod.choose_outbound_port('sarah', '3499999999', dispatches=dispatches,
                                       ports=self.ports, users=self.users)
        self.assertIsNone(got['port'])
        self.assertEqual(got['mode'], 'active_contact_conflict')
        self.assertEqual(got['locked_port'], 4603)

    def test_inactive_dispatch_does_not_lock_lead(self):
        # Disparos cancelados/pulados/falhos não prendem o lead a um chip.
        for status in ('cancelled', 'skipped', 'failed'):
            dispatches = [
                {'port': 4611, 'jid': '553499999999@s.whatsapp.net', 'status': status,
                 'created_at': '2026-07-01T09:00:00+00:00'},
            ]
            self.assertIsNone(
                mod.active_contact_port('3499999999', dispatches=dispatches), status)

    def test_would_double_contact_only_flags_a_second_port(self):
        dispatches = [
            {'port': 4611, 'jid': '553499999999@s.whatsapp.net', 'status': 'sent',
             'created_at': '2026-07-01T09:00:00+00:00'},
        ]
        # Enfileirar por OUTRA porta seria segundo contato -> True.
        self.assertTrue(mod.would_double_contact('3499999999', 4601, dispatches=dispatches))
        # Enfileirar pela MESMA porta que já fala com o lead -> False.
        self.assertFalse(mod.would_double_contact('3499999999', 4611, dispatches=dispatches))
        # Lead sem contato ativo -> qualquer porta é livre.
        self.assertFalse(mod.would_double_contact('553400000000', 4601, dispatches=dispatches))

    def test_active_contact_port_can_scope_to_owner_chips(self):
        dispatches = [
            {'port': 4603, 'jid': '553499999999@s.whatsapp.net', 'status': 'queued',
             'created_at': '2026-07-01T09:00:00+00:00'},
        ]
        # Global enxerga o chip do Lucas.
        self.assertEqual(mod.active_contact_port('3499999999', dispatches=dispatches), 4603)
        # Restrito à Sarah: o chip do Lucas não conta.
        self.assertIsNone(mod.active_contact_port('3499999999', dispatches=dispatches,
                                                  owner_uid='sarah', ports=self.ports, users=self.users))

    def test_dispatch_lock_is_opt_in_and_ledger_path_still_works(self):
        # Sem fila explícita, mantém o comportamento por ledger (afinidade).
        rows = [
            {'bridge_port': 4611, 'to': '553499999999@s.whatsapp.net', 'date_tz': '2026-06-30T10:00:00-03:00'},
        ]
        got = mod.choose_outbound_port('sarah', '3499999999', rows=rows,
                                       ports=self.ports, users=self.users)
        self.assertEqual(got['port'], 4611)
        self.assertEqual(got['mode'], 'existing_thread')


if __name__ == '__main__':
    unittest.main()
