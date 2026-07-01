import importlib.util
import unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
SPEC = importlib.util.spec_from_file_location('mql_sdr_followup', ROOT / 'scripts' / 'mql_sdr_followup.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class TestMqlSdrFollowup(unittest.TestCase):
    def test_post_diagnostic_followup_is_deterministic_followup1_not_manual_question(self):
        rec = {
            'nome': 'Vitor',
            'empresa': 'DMZ',
            'slug': 'dmz-vitor-feriza',
            'to': '5516992919340@c.us',
            'group_summary': (
                '✅ Lead qualificado\n'
                'Empresa: DMZ\n'
                '• Formulário indica venda para sorveterias, açaiterias e delivery de açaí/sorvete.\n'
                '• Dor direta de pedidos desorganizados por WhatsApp, telefone e planilha; operação sem loja virtual.'
            ),
            'text': 'Fiz uma análise prévia do potencial da digitalização B2B do seu negócio.',
        }
        text = mod.compose(rec, 'Lucas Batista')
        self.assertIn('estudei a DMZ com base no diagnóstico', text)
        self.assertIn('sorveterias', text)
        self.assertIn('WhatsApp, telefone e planilha', text)
        self.assertIn('https://portal.ceasamais.com.br/', text)
        self.assertNotIn('quero entender onde faz mais sentido começar', text)
        self.assertNotIn('Você quer entender o portal B2B na prática', text)
        self.assertNotIn('Como você imagina que a Zydon poderia te apoiar?', text)

    def test_legacy_manual_followup_counts_as_already_followed(self):
        envios = [
            {'msg_type': 'mql_sdr_followup', 'deal_id': '1', 'to': '5516992919340@c.us'},
        ]
        rec = {'deal_id': '1', 'to': '5516992919340@c.us'}
        self.assertTrue(mod.already_followed(envios, rec))

    def test_daily_limit_counts_only_today_not_entire_history(self):
        now_brt = mod.datetime.now(mod.BRT)
        yesterday = now_brt - timedelta(days=1)
        envios = [
            {'msg_type': mod.MSG_TYPE, 'sdr': 'Sarah', 'date_tz': yesterday.isoformat()},
            {'msg_type': mod.MSG_TYPE, 'sdr': 'Sarah', 'date_tz': now_brt.isoformat()},
            {'msg_type': mod.MSG_TYPE, 'sdr': 'Lucas Batista', 'date_tz': now_brt.isoformat()},
        ]
        self.assertEqual(mod.sent_count(envios, 'Sarah'), 2)
        self.assertEqual(mod.sent_count(envios, 'Sarah', today_only=True), 1)


if __name__ == '__main__':
    unittest.main()
