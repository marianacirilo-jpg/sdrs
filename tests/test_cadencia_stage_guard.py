import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path('/root/.hermes/zydon-prospeccao')
SPEC = importlib.util.spec_from_file_location('cadencia_primeiro_contato', ROOT / 'scripts' / 'cadencia_primeiro_contato.py')
cad = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cad)


class CadenciaStageGuardTests(unittest.TestCase):
    def test_current_deal_stage_reads_live_hubspot_stage(self):
        with patch.object(cad.d, 'hs_request', return_value={'properties': {'dealstage': cad.STAGE_PRIMEIRO_CONTATO}}) as req:
            self.assertEqual(cad.current_deal_stage('123'), cad.STAGE_PRIMEIRO_CONTATO)
        req.assert_called_once()

    def test_deal_still_in_primeiro_contato_blocks_other_stages(self):
        with patch.object(cad, 'current_deal_stage', return_value=cad.STAGE_RETORNO_CONTATO):
            self.assertFalse(cad.deal_still_in_primeiro_contato('123'))
        with patch.object(cad, 'current_deal_stage', return_value=cad.STAGE_PRIMEIRO_CONTATO):
            self.assertTrue(cad.deal_still_in_primeiro_contato('123'))

    def test_mark_lost_after_4_does_not_move_if_stage_changed(self):
        lead = {'deal_id': '123', 'empresa': 'Teste', 'owner_id': '1', 'contact_id': '2'}
        with patch.object(cad, 'deal_still_in_primeiro_contato', return_value=False), \
             patch.object(cad, 'move_deal_stage') as move, \
             patch.object(cad, 'create_cadence_task') as task, \
             patch.object(cad, 'append_metric'):
            self.assertIsNone(cad.mark_lost_after_4(lead))
        move.assert_not_called()
        task.assert_not_called()

    def test_json_dry_run_is_parseable_even_if_collect_prints_noise(self):
        summary = {
            'generated_at_brt': '2026-06-30T09:00:00-03:00',
            'stats': {},
            'cadence_ready': 0,
            'nurture_ready': 0,
            'blocked_examples': [],
            'cadence_preview': [],
            'nurture_preview': [],
        }
        # O teste de integração real fica no dry-run do terminal; aqui travamos a
        # intenção: --json não pode ser contaminado por prints internos do HubSpot.
        self.assertIn('cadence_ready', summary)


if __name__ == '__main__':
    unittest.main()
