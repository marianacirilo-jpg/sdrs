import importlib.util
from pathlib import Path
import unittest

ROOT = Path('/root/.hermes/zydon-prospeccao')
SPEC = importlib.util.spec_from_file_location('whatsapp_conversation_scope', ROOT / 'scripts' / 'whatsapp_conversation_scope.py')


class WhatsAppConversationScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(cls.mod)

    def test_communicator_personal_chat_without_system_origin_is_not_listened(self):
        decision = self.mod.should_listen_to_incoming(
            port=4600,
            chat_jid='5511999999999@s.whatsapp.net',
            history=[
                {'fromMe': True, 'type': 'notify', 'text': 'mensagem pessoal'},
                {'fromMe': False, 'type': 'notify', 'text': 'oi'},
            ],
            ledger_rows=[],
            audit_rows=[],
            ports={'4600': {'role': 'comunicador', 'owner': 'mariana'}},
        )
        self.assertFalse(decision['listen'])
        self.assertEqual(decision['reason'], 'not_system_initialized')

    def test_sdr_external_direct_chat_is_listened_even_without_system_origin(self):
        decision = self.mod.should_listen_to_incoming(
            port=4612,
            chat_jid='5511999999999@s.whatsapp.net',
            history=[
                {'fromMe': True, 'type': 'notify', 'text': 'mensagem pessoal'},
                {'fromMe': False, 'type': 'notify', 'text': 'oi'},
            ],
            ledger_rows=[],
            audit_rows=[],
            ports={'4612': {'role': 'sdr', 'owner': 'sarah'}},
        )
        self.assertTrue(decision['listen'])
        self.assertEqual(decision['reason'], 'sdr_external_direct_thread')
        self.assertEqual(decision['owner_sdr'], 'sarah')

    def test_groups_are_never_listened(self):
        decision = self.mod.should_listen_to_incoming(
            port=4612,
            chat_jid='120363408131718880@g.us',
            history=[{'fromMe': False, 'type': 'notify', 'text': 'oi'}],
            ledger_rows=[{'to': '120363408131718880@g.us', 'bridge_port': 4612, 'nature': 'first_contact'}],
            audit_rows=[],
            ports={'4612': {'role': 'sdr', 'owner': 'sarah'}},
        )
        self.assertFalse(decision['listen'])
        self.assertEqual(decision['reason'], 'group_thread')

    def test_chip_to_chip_threads_are_never_listened_even_with_history(self):
        decision = self.mod.should_listen_to_incoming(
            port=4601,
            chat_jid='553496698718@s.whatsapp.net',
            history=[
                {'fromMe': True, 'type': 'cron-sdr-primeiro-contato', 'text': 'teste'},
                {'fromMe': False, 'type': 'notify', 'text': 'resposta'},
            ],
            ledger_rows=[{'to': '553496698718@s.whatsapp.net', 'bridge_port': 4601, 'nature': 'first_contact'}],
            audit_rows=[],
        )
        self.assertFalse(decision['listen'])
        self.assertEqual(decision['reason'], 'internal_chip_thread')

    def test_automation_originated_thread_is_listened_and_owned_by_agent(self):
        decision = self.mod.should_listen_to_incoming(
            port=4601,
            chat_jid='5511888888888@s.whatsapp.net',
            history=[
                {'fromMe': True, 'type': 'cron-sdr-primeiro-contato', 'text': 'primeiro contato'},
                {'fromMe': False, 'type': 'notify', 'text': 'quero entender melhor'},
            ],
            ledger_rows=[{'to': '5511888888888@s.whatsapp.net', 'bridge_port': 4601, 'nature': 'first_contact', 'owner_sdr': 'sarah'}],
            audit_rows=[],
        )
        self.assertTrue(decision['listen'])
        self.assertEqual(decision['mode'], 'agent_owns_relationship')
        self.assertEqual(decision['state'], 'pending_agent_followthrough')
        self.assertEqual(decision['owner_sdr'], 'sarah')

    def test_active_dispatch_audit_also_initializes_thread(self):
        decision = self.mod.should_listen_to_incoming(
            port=4605,
            chat_jid='5511777777777@s.whatsapp.net',
            history=[{'fromMe': False, 'type': 'notify', 'text': 'pode me chamar'}],
            ledger_rows=[],
            audit_rows=[{'to': '5511777777777@s.whatsapp.net', 'port': 4605, 'origin': 'manual_channel', 'nature': 'manual_reply'}],
        )
        self.assertTrue(decision['listen'])
        self.assertEqual(decision['reason'], 'system_initialized')

    def test_escalation_only_when_context_is_ambiguous_or_requires_human(self):
        normal = self.mod.classify_followthrough('Pode me explicar melhor como funciona?')
        self.assertFalse(normal['escalate'])
        self.assertEqual(normal['next_state'], 'pending_agent_followthrough')

        ambiguous = self.mod.classify_followthrough('(sem texto extraído)')
        self.assertTrue(ambiguous['escalate'])
        self.assertEqual(ambiguous['next_state'], 'pending_human_review')

        price = self.mod.classify_followthrough('Qual o preço?')
        self.assertFalse(price['escalate'])
        self.assertEqual(price['next_state'], 'pending_agent_followthrough')


if __name__ == '__main__':
    unittest.main()
