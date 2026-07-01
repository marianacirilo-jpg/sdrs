import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'disparo_dinamico.py'


def load_mod():
    spec = importlib.util.spec_from_file_location('disparo_dinamico', MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DisparoMessageHygieneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_empresa_valida_strips_internal_nova_oportunidade_suffix(self):
        self.assertEqual(self.mod.empresa_valida('Hosptel  - Nova oportunidade'), 'Hosptel')
        self.assertEqual(self.mod.empresa_valida('QUIMICA CARIOCA - nova oportunidade'), 'QUIMICA CARIOCA')
        self.assertEqual(self.mod.empresa_valida('Nova oportunidade'), '')

    def test_first_contact_messages_never_expose_nova_oportunidade(self):
        for builder in (self.mod.montar_msg_breno, self.mod.montar_msg_sarah, self.mod.montar_msg_lucas):
            msg = builder('Guilherme', 'Hosptel  - Nova oportunidade', 'Bling')
            self.assertIn('Hosptel', msg)
            self.assertNotIn('Nova oportunidade', msg)
            self.assertNotIn('nova oportunidade', msg.lower())
            self.assertNotIn('Hosptel  -', msg)

    def test_empresa_valida_blocks_address_as_company_name(self):
        endereco = 'Rua Pedro Gusso, 1540, Cidade Industrial, Curitiba PR 81310-300'
        self.assertEqual(self.mod.empresa_valida(endereco), '')
        msg = self.mod.montar_msg_sarah('Cristiano', endereco, '')
        self.assertIn('Recebi seu cadastro', msg)
        self.assertNotIn('Rua Pedro Gusso', msg)
        self.assertNotIn('Cidade Industrial', msg)
        self.assertNotIn('cadastro da Rua', msg)

    def test_empresa_valida_keeps_real_company_with_number(self):
        self.assertEqual(self.mod.empresa_valida('Distribuidora 3 Irmãos'), 'Distribuidora 3 Irmãos')



if __name__ == '__main__':
    unittest.main()
