# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from mql_execution_queue import (  # noqa: E402
    default_step_state,
    dedupe_keys,
    execution_id,
    load_queue,
    mark_step,
    save_queue,
    upsert_mql_item,
)


class TestMqlExecutionQueue(unittest.TestCase):
    def test_load_queue_cria_estrutura_vazia_quando_arquivo_nao_existe(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'queue.json'
            self.assertEqual(load_queue(path), {'version': 1, 'items': []})

    def test_dedupe_keys_normaliza_e_remove_vazios(self):
        keys = dedupe_keys(contact_id=' 123 ', deal_id='456', phone='+55 (34) 99999-1111', email=' Lead@Empresa.COM ')
        self.assertEqual(keys, ['contact:123', 'deal:456', 'phone:5534999991111', 'email:lead@empresa.com'])

    def test_execution_id_estavel_independente_da_ordem(self):
        a = execution_id(['email:a@b.com', 'phone:5534999991111'])
        b = execution_id(['phone:5534999991111', 'email:a@b.com'])
        self.assertEqual(a, b)
        self.assertTrue(a.startswith('mql:'))

    def test_upsert_nao_duplica_por_chave_sobreposta(self):
        queue = {'version': 1, 'items': []}
        item1 = {'contact_id': '1', 'email': 'lead@empresa.com', 'dedupe_keys': dedupe_keys(contact_id='1', email='lead@empresa.com'), 'company': 'Empresa A'}
        item2 = {'contact_id': '1', 'email': 'outro@empresa.com', 'dedupe_keys': dedupe_keys(contact_id='1', email='outro@empresa.com'), 'company': 'Empresa Atualizada'}
        first, created1 = upsert_mql_item(queue, item1)
        second, created2 = upsert_mql_item(queue, item2)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(first['execution_id'], second['execution_id'])
        self.assertEqual(len(queue['items']), 1)
        self.assertEqual(queue['items'][0]['company'], 'Empresa Atualizada')
        self.assertIn('pdf_generated', queue['items'][0]['steps'])

    def test_save_queue_escrita_json_valida(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'queue.json'
            data = {'version': 1, 'items': [{'execution_id': 'mql:test'}]}
            save_queue(data, path)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), data)
            self.assertFalse(path.with_suffix('.tmp').exists())

    def test_mark_step_atualiza_apenas_item_alvo(self):
        queue = {'version': 1, 'items': [
            {'execution_id': 'mql:a', 'steps': {'pdf_generated': default_step_state()}},
            {'execution_id': 'mql:b', 'steps': {'pdf_generated': default_step_state()}},
        ]}
        item = mark_step(queue, 'mql:b', 'pdf_generated', 'done', path='/tmp/a.pdf')
        self.assertEqual(item['steps']['pdf_generated']['status'], 'done')
        self.assertEqual(item['steps']['pdf_generated']['path'], '/tmp/a.pdf')
        self.assertEqual(queue['items'][0]['steps']['pdf_generated']['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
