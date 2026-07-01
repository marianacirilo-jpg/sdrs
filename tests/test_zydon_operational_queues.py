import importlib.util
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest

ROOT = Path('/root/.hermes/zydon-prospeccao')
SPEC = importlib.util.spec_from_file_location('zydon_operational_queues', ROOT / 'scripts' / 'zydon_operational_queues.py')


class ZydonOperationalQueuesLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(cls.mod)

    def test_append_wpp_envio_locked_preserves_schema_and_all_concurrent_appends(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'wpp_envios.json'
            path.write_text(json.dumps({'envios': []}, ensure_ascii=False), encoding='utf-8')

            def write(i):
                self.mod.append_wpp_envio_locked({'logical_message_id': f'lm_{i}', 'idx': i}, path=path)

            with ThreadPoolExecutor(max_workers=10) as ex:
                list(ex.map(write, range(100)))

            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertIsInstance(data, dict)
            self.assertIn('envios', data)
            self.assertEqual(len(data['envios']), 100)
            self.assertEqual({r['idx'] for r in data['envios']}, set(range(100)))

    def test_append_wpp_envio_alias_uses_locked_owner(self):
        self.assertIs(self.mod.append_wpp_envio, self.mod.append_wpp_envio_locked)

    def test_replace_wpp_envios_locked_preserves_schema(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'wpp_envios.json'
            self.mod.replace_wpp_envios_locked([{'idx': 1}, {'idx': 2}], path=path)
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(data, {'envios': [{'idx': 1}, {'idx': 2}]})

    def test_normalize_envios_keeps_legacy_list_compatible(self):
        data = self.mod.normalize_envios([{'a': 1}, {'b': 2}])
        self.assertEqual(data, {'envios': [{'a': 1}, {'b': 2}]})


if __name__ == '__main__':
    unittest.main()
