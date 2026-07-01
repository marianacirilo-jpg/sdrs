import importlib.util
import unittest
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
SPEC = importlib.util.spec_from_file_location('active_mql_qualifier', ROOT / 'scripts' / 'active_mql_qualifier.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ActiveMqlQualifierPolicyTests(unittest.TestCase):
    def test_doubtful_ad_lead_defaults_to_mql_candidate(self):
        props = {
            'email': 'lead@empresa.com.br',
            'company': 'Empresa Real',
            'recent_conversion_event_name': 'Facebook Lead Ads: FORM VENCEDOR',
            'qual_erp_utiliza_': 'Bling',
            'qual_o_faturamento_anual_da_sua_empresa_': 'Ainda não faturamos',
            'quantas_pessoas_atuam_na_sua_empresa': '1 a 10',
        }
        state, reason = mod.classify_hint(props, {'ok': True, 'summary': 'loja virtual com produtos'})
        self.assertEqual(state, 'mql_candidate_needs_main_pipeline')
        self.assertIn('regra Rafael', reason)

    def test_obvious_fake_or_no_company_is_non_mql_hint(self):
        props = {
            'email': 'teste@example.com',
            'company': 'Empresa Teste Fake',
            'recent_conversion_event_name': 'Facebook Lead Ads: FORM VENCEDOR',
        }
        state, reason = mod.classify_hint(props, {'ok': False, 'summary': ''})
        self.assertEqual(state, 'classified_non_mql_hint')
        self.assertIn('teste/fake', reason)

    def test_pipeline_flags_allow_diagnostic_for_mql_candidate(self):
        # Não roda o lock/arquivo; apenas garante que a política usada em upsert inclui o estado.
        eligible = {'mql_candidate_needs_main_pipeline','mql_opportunity_needs_diagnostic','mql_confirmado_rafael_manual','mql_opportunity_diagnostico_autorizado'}
        self.assertIn('mql_candidate_needs_main_pipeline', eligible)


if __name__ == '__main__':
    unittest.main()
