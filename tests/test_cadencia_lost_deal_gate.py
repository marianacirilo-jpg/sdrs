import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'scripts' / 'cadencia_primeiro_contato.py'


def load_mod():
    spec = importlib.util.spec_from_file_location('cadencia_primeiro_contato', MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CadenciaLostDealGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_blocks_lost_deal_before_whatsapp_send(self):
        blocked, reason = self.mod.should_block_automation_for_deal_state({
            'ok': True,
            'stage': self.mod.STAGE_PERDIDO,
            'pipeline': self.mod.PIPELINE,
        })
        self.assertTrue(blocked)
        self.assertIn('Perdido', reason)

    def test_allows_primeiro_contato_only(self):
        blocked, reason = self.mod.should_block_automation_for_deal_state({
            'ok': True,
            'stage': self.mod.STAGE_PRIMEIRO_CONTATO,
            'pipeline': self.mod.PIPELINE,
        })
        self.assertFalse(blocked, reason)

    def test_fail_closed_when_hubspot_stage_cannot_be_confirmed(self):
        blocked, reason = self.mod.should_block_automation_for_deal_state({
            'ok': False,
            'reason': 'timeout',
        })
        self.assertTrue(blocked)
        self.assertIn('fail-closed', reason)


if __name__ == '__main__':
    unittest.main()
