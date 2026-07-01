import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
sys.path.insert(0, str(ROOT / 'scripts'))


def load_monitor():
    spec = importlib.util.spec_from_file_location('monitor_diagnostico_agendado', ROOT / 'scripts' / 'monitor_diagnostico_agendado.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MonitorDiagnosticoAgendadoTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_monitor()

    def test_google_bidirectional_link_uses_legacy_video_conference_url(self):
        def fake_hs(method, path, payload=None):
            self.assertEqual(method, 'GET')
            self.assertEqual(path, '/engagements/v1/engagements/111898891924')
            return {'metadata': {'videoConferenceUrl': 'https://meet.google.com/hqu-arjo-gmd'}}

        self.mod.hs = fake_hs
        meeting = {
            'id': '111898891924',
            'properties': {
                'hs_meeting_source': 'BIDIRECTIONAL_SYNC',
                'hs_meeting_external_url': 'https://www.google.com/calendar/event?eid=abc',
                'hs_meeting_location': None,
                'hs_meeting_body': None,
            },
        }
        self.assertEqual(self.mod.meeting_join_link(meeting), 'https://meet.google.com/hqu-arjo-gmd')
        self.assertIsNone(self.mod.link_lookup_error(meeting))

    def test_google_bidirectional_legacy_lookup_failure_is_blocking(self):
        def fake_hs(method, path, payload=None):
            raise RuntimeError('temporary HubSpot 503')

        self.mod.hs = fake_hs
        meeting = {
            'id': '111898891924',
            'properties': {
                'hs_meeting_source': 'BIDIRECTIONAL_SYNC',
                'hs_meeting_external_url': 'https://www.google.com/calendar/event?eid=abc',
            },
        }
        self.assertEqual(self.mod.meeting_join_link(meeting), '')
        self.assertIn('temporary HubSpot 503', self.mod.link_lookup_error(meeting))

    def test_found_link_overrides_legacy_lookup_failure(self):
        # BIDIRECTIONAL_SYNC com link direto já no v3 (hs_meeting_location), mas o
        # endpoint legado de engagement falha. O link bom já está em mãos, então o
        # fail-closed NÃO deve bloquear o envio.
        def fake_hs(method, path, payload=None):
            raise RuntimeError('temporary HubSpot 503')

        self.mod.hs = fake_hs
        meeting = {
            'id': '111898891924',
            'properties': {
                'hs_meeting_source': 'BIDIRECTIONAL_SYNC',
                'hs_meeting_location': 'https://meet.google.com/hqu-arjo-gmd',
                'hs_meeting_external_url': 'https://www.google.com/calendar/event?eid=abc',
            },
        }
        link = self.mod.meeting_join_link(meeting)
        self.assertEqual(link, 'https://meet.google.com/hqu-arjo-gmd')
        # O erro legado fica registrado, mas com link presente não pode bloquear.
        self.assertIsNotNone(self.mod.link_lookup_error(meeting))
        self.assertIsNone(self.mod.should_block_for_missing_link(meeting, link))

    def test_missing_link_with_legacy_failure_blocks(self):
        # BIDIRECTIONAL_SYNC sem link direto e com lookup legado falho: bloqueia.
        def fake_hs(method, path, payload=None):
            raise RuntimeError('temporary HubSpot 503')

        self.mod.hs = fake_hs
        meeting = {
            'id': '111898891924',
            'properties': {
                'hs_meeting_source': 'BIDIRECTIONAL_SYNC',
                'hs_meeting_external_url': 'https://www.google.com/calendar/event?eid=abc',
            },
        }
        link = self.mod.meeting_join_link(meeting)
        self.assertEqual(link, '')
        blocked = self.mod.should_block_for_missing_link(meeting, link)
        self.assertIsNotNone(blocked)
        self.assertIn('temporary HubSpot 503', blocked)

    def test_missing_link_non_google_source_does_not_block(self):
        # Fonte não-Google sem link: segue normal com texto "link no e-mail",
        # não há lookup legado obrigatório, então não bloqueia.
        def fake_hs(method, path, payload=None):
            raise RuntimeError('should not matter')

        self.mod.hs = fake_hs
        meeting = {
            'id': 'm-public',
            'properties': {
                'hs_meeting_source': 'MEETINGS_PUBLIC',
                'hs_meeting_external_url': 'https://www.google.com/calendar/event?eid=abc',
            },
        }
        link = self.mod.meeting_join_link(meeting)
        self.assertEqual(link, '')
        self.assertIsNone(self.mod.should_block_for_missing_link(meeting, link))

    def test_no_link_message_snapshots_are_fixed(self):
        self.mod.meeting_join_link = lambda meeting: ''
        meeting = {'id': 'm1', 'properties': {'hs_meeting_start_time': '2026-06-30T12:00:00Z'}}
        contact = {'properties': {'firstname': 'Leandro', 'lastname': 'Souza'}}
        deal = {'properties': {'dealname': 'Design Moveis Corporativo'}}
        confirmation = self.mod.confirmation_message(meeting, deal, contact, {'nome': 'Breno'})
        reminder = self.mod.reminder_message(meeting, deal, contact, {'nome': 'Breno'})
        group = self.mod.group_notification_message(meeting, deal, contact, {'nome': 'Breno'})
        self.assertEqual(
            confirmation,
            'Leandro, aqui é Breno da Zydon. Diagnóstico confirmado para 30/06/2026 09:00.\n\n'
            'O convite também ficou no seu e-mail/calendário.\n\n'
            'Se puder, entra pelo computador para a gente conseguir te mostrar melhor na prática.\n\n'
            'Caso queira alterar sua data ou horário do diagnóstico, pode me chamar por aqui que alinhamos o novo momento.'
        )
        self.assertEqual(
            reminder,
            'Leandro, passando para lembrar do nosso diagnóstico hoje às 30/06/2026 09:00.\n\n'
            'O link está no convite do calendário/e-mail.\n\n'
            'Se conseguir entrar pelo computador, a experiência fica melhor para vermos o processo com calma.'
        )
        self.assertEqual(
            group,
            '📅 Diagnóstico agendado\n\n'
            'Design Moveis Corporativo marcou diagnóstico com Breno para 30/06/2026 09:00.\n'
            'Lead: Leandro Souza\n'
            'Link: não localizado direto no HubSpot'
        )

    def test_confirmation_message_includes_reschedule_phrase(self):
        self.mod.meeting_join_link = lambda meeting: 'https://meet.google.com/abc-defg-hij'
        meeting = {'id': 'm1', 'properties': {'hs_meeting_start_time': '2026-06-30T12:00:00Z'}}
        contact = {'properties': {'firstname': 'Leandro'}}
        deal = {'properties': {'dealname': 'Teste'}}
        msg = self.mod.confirmation_message(meeting, deal, contact, {'nome': 'Breno'})
        expected = (
            'Leandro, aqui é Breno da Zydon. Diagnóstico confirmado para 30/06/2026 09:00.\n\n'
            'Link para acessar: https://meet.google.com/abc-defg-hij\n\n'
            'Se puder, entra pelo computador para a gente conseguir te mostrar melhor na prática.\n\n'
            'Caso queira alterar sua data ou horário do diagnóstico, pode me chamar por aqui que alinhamos o novo momento.'
        )
        self.assertEqual(msg, expected)

    def test_fixed_template_constants_do_not_drift(self):
        self.assertEqual(self.mod.CONFIRMATION_NO_LINK_LINE, 'O convite também ficou no seu e-mail/calendário.')
        self.assertEqual(self.mod.CONFIRMATION_COMPUTER_LINE, 'Se puder, entra pelo computador para a gente conseguir te mostrar melhor na prática.')
        self.assertEqual(self.mod.CONFIRMATION_RESCHEDULE_LINE, 'Caso queira alterar sua data ou horário do diagnóstico, pode me chamar por aqui que alinhamos o novo momento.')
        self.assertEqual(self.mod.REMINDER_NO_LINK_LINE, 'O link está no convite do calendário/e-mail.')
        self.assertEqual(self.mod.REMINDER_COMPUTER_LINE, 'Se conseguir entrar pelo computador, a experiência fica melhor para vermos o processo com calma.')
        self.assertEqual(self.mod.GROUP_NO_LINK_LINE, 'Link: não localizado direto no HubSpot')
        self.assertEqual(self.mod.LINK_DIRECT_HOSTS, ('meet.google.com', 'zoom.us', 'teams.microsoft.com'))
        self.assertEqual(self.mod.REMINDER_WINDOW_START_HOUR_BRT, 7)
        self.assertEqual(self.mod.REMINDER_WINDOW_END_HOUR_BRT, 11)
        self.assertEqual(self.mod.REMINDER_MIN_LEAD_TIME_MINUTES, 30)
        self.assertEqual(self.mod.CONFIRMATION_REMINDER_MIN_GAP_HOURS, 2)
        self.assertEqual(self.mod.PREP_TASK_LEAD_HOURS, 2)

    def test_reminder_and_group_message_snapshots_are_fixed(self):
        self.mod.meeting_join_link = lambda meeting: 'https://meet.google.com/abc-defg-hij'
        meeting = {'id': 'm1', 'properties': {'hs_meeting_start_time': '2026-06-30T12:00:00Z'}}
        contact = {'properties': {'firstname': 'Leandro', 'lastname': 'Souza'}}
        deal = {'properties': {'dealname': 'Design Moveis Corporativo'}}
        reminder = self.mod.reminder_message(meeting, deal, contact, {'nome': 'Breno'})
        group = self.mod.group_notification_message(meeting, deal, contact, {'nome': 'Breno'})
        self.assertEqual(
            reminder,
            'Leandro, passando para lembrar do nosso diagnóstico hoje às 30/06/2026 09:00.\n\n'
            'Link: https://meet.google.com/abc-defg-hij\n\n'
            'Se conseguir entrar pelo computador, a experiência fica melhor para vermos o processo com calma.'
        )
        self.assertEqual(
            group,
            '📅 Diagnóstico agendado\n\n'
            'Design Moveis Corporativo marcou diagnóstico com Breno para 30/06/2026 09:00.\n'
            'Lead: Leandro Souza\n'
            'Link: https://meet.google.com/abc-defg-hij'
        )

    def test_persist_state_progress_saves_dedupe_before_slow_logging(self):
        saved = []
        self.mod.save_state = lambda state: saved.append({k: (v.copy() if hasattr(v, 'copy') else v) for k, v in state.items()})
        state = {}
        processed = {'m-old'}
        confirmations = {'m-confirmed'}
        reminders = {'m-reminded'}
        group_notified = {'m-group'}
        sent_at = {'m-confirmed': '2026-06-30T10:00:00+00:00'}

        self.mod.persist_state_progress(state, processed, confirmations, reminders, group_notified, sent_at)

        self.assertEqual(saved[-1]['processed_meeting_ids'], ['m-old'])
        self.assertEqual(saved[-1]['confirmation_sent_meeting_ids'], ['m-confirmed'])
        self.assertEqual(saved[-1]['reminder_sent_meeting_ids'], ['m-reminded'])
        self.assertEqual(saved[-1]['group_notified_meeting_ids'], ['m-group'])
        self.assertEqual(saved[-1]['confirmation_sent_at'], sent_at)
        self.assertIn('last_run_at', saved[-1])


if __name__ == '__main__':
    unittest.main()
