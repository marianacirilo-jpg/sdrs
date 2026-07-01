#!/usr/bin/env python3
import importlib.util
import sys
import unittest
from pathlib import Path

MONITOR_PATH = Path('/root/.hermes/zydon-prospeccao/scripts/whatsapp_bridge_health_monitor.py')


def load_monitor():
    spec = importlib.util.spec_from_file_location('whatsapp_bridge_health_monitor', MONITOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class WhatsAppBridgeHealthMonitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_monitor()

    def test_format_silent_when_no_findings(self):
        self.assertEqual(self.mod.format_findings([]), '')

    def test_format_reports_port_and_reason(self):
        finding = self.mod.HealthFinding(4607, 'canonicalize_indisponivel', 'connection refused')
        out = self.mod.format_findings([finding])
        self.assertIn('4607', out)
        self.assertIn('canonicalize_indisponivel', out)
        self.assertIn('connection refused', out)

    def test_constants_cover_expected_ports(self):
        self.assertEqual(self.mod.PORTS, [4600, 4601, 4603, 4605, 4606, 4607, 4609, 4610])
        self.assertTrue(self.mod.TEST_REQUESTED.endswith('@s.whatsapp.net'))
        self.assertTrue(self.mod.TEST_CANONICAL.endswith('@s.whatsapp.net'))
        self.assertNotEqual(self.mod.TEST_REQUESTED, self.mod.TEST_CANONICAL)


if __name__ == '__main__':
    unittest.main()
