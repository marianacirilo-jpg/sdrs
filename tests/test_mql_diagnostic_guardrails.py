# -*- coding: utf-8 -*-
"""Guardrails para impedir diagnóstico pré-MQL.

Regra Rafael 2026-06-29: lead de formulário/site/Facebook pode ser pesquisado,
classificado e pendenciado 24x7, mas HTML/PDF/WhatsApp de diagnóstico só pode
nascer depois de MQL confirmado.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestDiagnosticoPreMqlGuardrails(unittest.TestCase):
    def test_active_mql_qualifier_nao_gera_pdf_nem_envia_combo(self):
        txt = (ROOT / 'scripts/active_mql_qualifier.py').read_text(encoding='utf-8')
        proibidos = [
            'generate_pdf(',
            "'/send-file'",
            '"/send-file"',
            'def send_mql(',
            'mql_diagnostico_em_andamento',
        ]
        for needle in proibidos:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, txt)

    def test_process_gate_once_tem_trava_explicita_antes_de_pdf(self):
        txt = (ROOT / 'scripts/process_gate_once.py').read_text(encoding='utf-8')
        self.assertIn('assert_mql_confirmed_for_diagnostic', txt)
        self.assertIn('mql_confirmed_ready_for_diagnostic', txt)
        self.assertRegex(txt, re.compile(r'assert_mql_confirmed_for_diagnostic\([^\n]+\)\s*\n\s*slug,pdf,pretty=generate_pdf\(', re.M))

    def test_process_gate_once_tem_dedupe_guard_imediatamente_antes_do_whatsapp(self):
        txt = (ROOT / 'scripts/process_gate_once.py').read_text(encoding='utf-8')
        self.assertIn('from mql_dedupe_guard import can_send_diagnostic', txt)
        self.assertIn('dedupe_ok, dedupe_reason = can_send_diagnostic(contact_id=cid, deal_id=primary_deal_id, phone=phone, email=email, company=company)', txt)
        self.assertRegex(txt, re.compile(r'if not dedupe_ok:\s*\n\s*reports\.append\([^\n]+PULADO dedupe forte', re.M))
        send_region = txt[txt.index('latest_envios = load_wpp()\n        already_mql'):] 
        self.assertLess(send_region.index('can_send_diagnostic('), send_region.index('append_mql_inflight('))


if __name__ == '__main__':
    unittest.main()
