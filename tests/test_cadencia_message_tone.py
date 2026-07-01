import hashlib
import importlib.util
import json
import re
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/root/.hermes/zydon-prospeccao')
SPEC = importlib.util.spec_from_file_location('cadencia_primeiro_contato', ROOT / 'scripts' / 'cadencia_primeiro_contato.py')
cad = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cad)

MANIFEST_PATH = ROOT / 'controle' / 'followup_textos_aprovados_rafael_20260630.json'


class CadenciaMessageToneTests(unittest.TestCase):
    def lead(self, attempt, **extra):
        data = {
            'deal_id': f'deal-{attempt}',
            'jid': f'55119999999{attempt}@s.whatsapp.net',
            'nome': 'André',
            'empresa': 'Avena Sports',
            'owner_name': 'Lucas Batista',
            'next_attempt': attempt,
            'attempt_count': attempt - 1,
            'prior_had_link': True,
            'erp': 'Bling',
            'vende_em_loja_virtual': '',
        }
        data.update(extra)
        return data

    def test_follow_2_matches_rafael_saved_text(self):
        text = cad.extract_message_variation(self.lead(2), 2, {'sender_name': 'Lucas Batista'})
        self.assertIn('Boa tarde, André. Tudo bem?', text)
        self.assertIn('A maioria das indústrias que chegam aqui trava no mesmo ponto: como liberar acesso no ecommerce só pra revendas, sem entrar concorrente ou consumidor final. É esse o seu caso ou é outra coisa?', text)
        self.assertIn('Hoje cada cliente seu enxerga a tabela comercial dele, ou está todo mundo vendo o mesmo preço?', text)
        self.assertIn('Faz sentido bater um papo rápido sobre isso? Podemos falar por aqui ou prefere por ligação?', text)
        self.assertNotIn('Separei um portal real para visualizar', text)

    def test_follow_3_matches_rafael_saved_text_without_duplicate_stanza(self):
        text = cad.extract_message_variation(self.lead(3), 3, {'sender_name': 'Lucas Batista'})
        self.assertIn('Boa tarde, André. Tudo bem?', text)
        self.assertIn('Quando o seu cliente vai fazer um pedido, alguém na Avena Sports precisa confirmar a tabela de preço, estoque e digitar e conferir o pedido no ERP?', text)
        self.assertIn('Hoje vocês já possuem algum canal onde o cliente consegue tirar o pedido sozinho?', text)
        self.assertIn('Faz sentido bater um papo rápido sobre isso?', text)
        self.assertEqual(text.count('Quando o seu cliente vai fazer um pedido'), 1)

    def test_follow_4_matches_rafael_saved_text(self):
        text = cad.extract_message_variation(self.lead(4), 4, {'sender_name': 'Lucas Batista'})
        self.assertIn('Boa tarde, André. Tudo bem?', text)
        self.assertIn('Se o momento não for agora, sem problema, me avisa. Mas se ainda fizer sentido criar um portal onde o seu cliente faz o pedido sozinho, 24h, sem precisar acionar ninguém, é só responder aqui que eu te mostro em 15 min.', text)
        self.assertIn('Se esse tema voltar a fazer sentido, me chama por aqui que eu retomo contigo.', text)
        self.assertNotIn('último toque', text.lower())

    def test_follow_1_still_uses_studied_portal_when_no_prior_link(self):
        lead = self.lead(1, prior_had_link=False)
        text = cad.extract_message_variation(lead, 1, {'sender_name': 'Lucas Batista'})
        self.assertIn('Boa tarde, André. Tudo bem?', text)
        self.assertIn('Separei um portal real mais próximo de operação com artigos esportivos para você visualizar:', text)
        self.assertIn('https://b2b.bullpadelbr.com/', text)
        self.assertIn('Esse cliente vende para lojas, academias e pontos ligados a artigos esportivos.', text)
        self.assertIn('O cliente novo solicita acesso, entra com login, vê catálogo, tabela comercial e condição dele, e o pedido cai direto no ERP.', text)
        self.assertIn('Você acha que isso ainda faz sentido para a Avena Sports?', text)
        ok, reason = cad.approved_followup_template_gate(text, 1, lead)
        self.assertTrue(ok, reason)

    def test_all_followups_are_exact_manifest_render_only(self):
        for attempt in (1, 2, 3, 4):
            lead = self.lead(attempt, prior_had_link=(attempt != 1))
            text = cad.extract_message_variation(lead, attempt, {'sender_name': 'Lucas Batista'})
            expected = cad._render_approved_template(attempt, lead)
            self.assertEqual(text, expected)
            ok, reason = cad.approved_followup_template_gate(text, attempt, lead)
            self.assertTrue(ok, reason)

    def test_approval_gate_rejects_old_follow_2_text(self):
        old = 'William, passando para deixar mais concreto.\n\nEsse é um exemplo real de portal B2B:\n\nhttps://stoky.com.br/'
        ok, reason = cad.approved_followup_template_gate(old, 2)
        self.assertFalse(ok)
        self.assertTrue('faltam' in reason or 'antigo' in reason)

    def test_approval_gate_rejects_follow_3_duplicate_stanza(self):
        lead = self.lead(3)
        text = cad.extract_message_variation(lead, 3, {'sender_name': 'Lucas Batista'})
        duplicated = text + '\n\nQuando o seu cliente vai fazer um pedido, alguém na Avena Sports precisa confirmar a tabela de preço, estoque e digitar e conferir o pedido no ERP?'
        ok, reason = cad.approved_followup_template_gate(duplicated, 3, lead)
        self.assertFalse(ok)
        self.assertIn('duplicada', reason)


class ManifestFailClosedTests(unittest.TestCase):
    """Garante que o manifesto é a única fonte de verdade e que qualquer
    falha/ausência/adulteração BLOQUEIA o envio (fail-closed)."""

    def lead(self, attempt):
        return {'deal_id': f'm-{attempt}', 'jid': '5511999999999@s.whatsapp.net',
                'nome': 'André', 'empresa': 'Avena Sports', 'next_attempt': attempt}

    def _swap_manifest(self, new_path):
        original = cad.APPROVED_FOLLOWUP_MANIFEST
        cad.APPROVED_FOLLOWUP_MANIFEST = new_path
        self.addCleanup(lambda: setattr(cad, 'APPROVED_FOLLOWUP_MANIFEST', original))

    def _write_temp_manifest(self, data):
        tmp = Path(tempfile.mkdtemp()) / 'manifest.json'
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return tmp

    def _base_manifest(self):
        return json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))

    def test_gate_blocks_when_manifest_file_missing(self):
        self._swap_manifest(Path('/tmp/__no_such_followup_manifest__.json'))
        for attempt in (1, 2, 3, 4):
            ok, reason = cad.approved_followup_template_gate('qualquer coisa', attempt, self.lead(attempt))
            self.assertFalse(ok)
            self.assertIn('fail-closed', reason)

    def test_gate_blocks_when_manifest_text_tampered(self):
        data = self._base_manifest()
        # Texto alterado mas sha256 mantido => integridade falha => bloqueio.
        data['texts']['follow2'] = data['texts']['follow2'] + ' EXTRA NAO APROVADO'
        self._swap_manifest(self._write_temp_manifest(data))
        ok, reason = cad.approved_followup_template_gate('x', 2, self.lead(2))
        self.assertFalse(ok)
        self.assertIn('fail-closed', reason)

    def test_gate_blocks_when_manifest_missing_a_followup(self):
        data = self._base_manifest()
        del data['texts']['follow4']
        del data['sha256']['follow4']
        self._swap_manifest(self._write_temp_manifest(data))
        ok, reason = cad.approved_followup_template_gate('x', 4, self.lead(4))
        self.assertFalse(ok)
        self.assertIn('fail-closed', reason)

    def test_gate_blocks_unknown_placeholder_even_with_valid_hash(self):
        # Manifesto com placeholder fora da allowlist, porém com sha256 recalculado
        # para passar na verificação de integridade. O render deve falhar e bloquear.
        data = self._base_manifest()
        tampered = data['texts']['follow2'] + '\n\nMeu telefone: {telefone}'
        data['texts']['follow2'] = tampered
        data['sha256']['follow2'] = hashlib.sha256(tampered.encode('utf-8')).hexdigest()
        self._swap_manifest(self._write_temp_manifest(data))
        ok, reason = cad.approved_followup_template_gate('x', 2, self.lead(2))
        self.assertFalse(ok)
        self.assertIn('fail-closed', reason)

    def test_invalid_attempt_is_blocked(self):
        for attempt in (0, 5, 99):
            ok, reason = cad.approved_followup_template_gate('x', attempt, self.lead(2))
            self.assertFalse(ok)
            self.assertIn('inválida', reason)
        with self.assertRaises(ValueError):
            cad._render_approved_template(5, self.lead(2))

    def test_extract_raises_fail_closed_when_manifest_missing(self):
        # O caminho de envio/prévia (main()) depende de que a GERAÇÃO de texto
        # falhe quando o manifesto some — nunca caia em texto antigo. main()
        # captura essa exceção e bloqueia o lead em vez de mandar algo fora da régua.
        self._swap_manifest(Path('/tmp/__no_such_followup_manifest__.json'))
        with self.assertRaises(Exception):
            cad.extract_message_variation(self.lead(2), 2, {'sender_name': 'X'})

    def test_manifest_uses_only_allowed_variables(self):
        data = self._base_manifest()
        allowed = set(cad.APPROVED_FOLLOWUP_VARS)
        for key, tmpl in data['texts'].items():
            placeholders = set(re.findall(r'\{([^}]+)\}', tmpl))
            self.assertTrue(placeholders <= allowed,
                            f'{key} usa variáveis fora da allowlist: {placeholders - allowed}')

    def test_old_text_paths_are_removed(self):
        # Os geradores de texto alternativo/ponte foram removidos do módulo.
        for name in ('consultant_addendum', 'remove_sdr_bridge_mentions',
                     'apply_diagnostic_sdr_context_bridge', 'prior_diagnostic_sent_by_owner_sdr',
                     'APPROVED_FOLLOWUP_BANNED', 'APPROVED_FOLLOWUP_REQUIRED'):
            self.assertFalse(hasattr(cad, name), f'{name} deveria ter sido removido')

    def test_sender_does_not_change_text(self):
        lead = self.lead(2)
        a = cad.extract_message_variation(lead, 2, {'sender_name': 'Mariana', 'port': 4600})
        b = cad.extract_message_variation(lead, 2, {'sender_name': 'Lucas Batista'})
        c = cad.extract_message_variation(lead, 2, None)
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_cadence_send_window_blocks_weekend_and_after_friday_18(self):
        brt = timezone(timedelta(hours=-3))
        self.assertTrue(cad.cadence_send_window(datetime(2026, 6, 30, 10, 0, tzinfo=brt)))  # terça
        self.assertFalse(cad.cadence_send_window(datetime(2026, 7, 4, 10, 0, tzinfo=brt)))  # sábado
        self.assertFalse(cad.cadence_send_window(datetime(2026, 7, 3, 18, 0, tzinfo=brt)))  # sexta 18h
        self.assertFalse(cad.cadence_send_window(datetime(2026, 7, 2, 20, 0, tzinfo=brt)))  # quinta 20h

    def test_lead_has_study_uses_match_matrix_and_respects_block_reason(self):
        original = cad._RESEARCH_MATCH_MATRIX
        cad._RESEARCH_MATCH_MATRIX = {
            ('deal', 'ok-deal'): {
                'deal_id': 'ok-deal',
                'empresa': 'Empresa Boa',
                'buyer_profile': 'revenda que recompra por SKU',
                'quality_gate': {'has_source': True, 'has_buyer': True, 'not_generic': True, 'no_sdr_bridge': True},
            },
            ('deal', 'blocked-deal'): {
                'deal_id': 'blocked-deal',
                'empresa': 'Empresa Bloqueada',
                'block_reason': 'sem fonte confiável',
                'quality_gate': {'has_source': True, 'has_buyer': True, 'not_generic': True, 'no_sdr_bridge': True},
            },
        }
        self.addCleanup(lambda: setattr(cad, '_RESEARCH_MATCH_MATRIX', original))
        self.assertTrue(cad.lead_has_study({'deal_id': 'ok-deal', 'empresa': 'Empresa Boa', 'next_attempt': 2}, 2))
        self.assertFalse(cad.lead_has_study({'deal_id': 'blocked-deal', 'empresa': 'Empresa Bloqueada', 'next_attempt': 2}, 2))


if __name__ == '__main__':
    unittest.main()
