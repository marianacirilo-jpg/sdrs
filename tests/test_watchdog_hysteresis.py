"""Regressão do watchdog de performance do Channel V2 (histerese).

Incidente 20260628T194915Z-26a12501: pico transitório de cache frio/restart no
processo 8280 (/api/conversations em timeout => sem cache; recompute pesado satura
CPU/GIL e arrasta /health, /gestao e /api/messages). O watchdog amostrava uma única
vez e alarmava no transitório. A correção foi histerese: só alerta o que persiste
em DUAS amostras. Estes testes travam esse comportamento sem tocar a operação.
"""
import importlib.util
import json
import unittest
from pathlib import Path

WATCHDOG_PATH = Path('/root/.hermes/scripts/zydon_channel_v2_performance_watchdog.py')


def load_watchdog():
    spec = importlib.util.spec_from_file_location('zydon_channel_v2_performance_watchdog', WATCHDOG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WatchdogHysteresisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wd = load_watchdog()

    def test_confirm_function_exists(self):
        self.assertTrue(hasattr(self.wd, 'confirm_failures'))
        self.assertTrue(hasattr(self.wd, 'run_checks'))

    def test_transient_failure_is_dropped_on_warm_resample(self):
        # 1ª amostra ruim (cache frio), 2ª amostra limpa => sem alerta.
        first = [('health_8280', '/health 8280 erro=TimeoutError'),
                 ('conversations', '/api/conversations erro=TimeoutError')]
        second = []
        self.assertEqual(self.wd.confirm_failures(first, second), [])

    def test_persistent_failure_is_alerted(self):
        # Mesma key falha nas duas amostras => alerta com a mensagem mais recente.
        first = [('conversations', '/api/conversations ms=9000')]
        second = [('conversations', '/api/conversations ms=11000')]
        confirmed = self.wd.confirm_failures(first, second)
        self.assertEqual(confirmed, ['/api/conversations ms=11000'])

    def test_only_intersecting_keys_count(self):
        # Falhas diferentes entre amostras (flapping) não são confirmadas;
        # só a key presente nas duas (msg_X) sobrevive.
        first = [('health_8280', 'a'), ('msg_X', 'm-old')]
        second = [('route_/foco', 'b'), ('msg_X', 'm-new')]
        self.assertEqual(self.wd.confirm_failures(first, second), ['m-new'])

    def test_new_failure_appearing_only_in_second_sample_is_not_alerted(self):
        # Aparece só na 2ª amostra: ainda é uma única observação => não alerta.
        first = []
        second = [('conversations', 'novo timeout')]
        self.assertEqual(self.wd.confirm_failures(first, second), [])

    def test_warmup_is_conservative(self):
        # Aquecimento suficiente para o recompute frio (~10s) popular o cache.
        self.assertGreaterEqual(self.wd.WARMUP_SECONDS, 10)


def _fake_fetch_factory(message_latencies=None):
    """Stub de fetch sem rede. Todos os endpoints passam por padrão; só as
    conversas em `message_latencies` (sub-string do conv -> lista de ms por
    tentativa) controlam a latência de /api/messages por tentativa.
    """
    message_latencies = message_latencies or {}
    per_url_calls = {}

    def fake_fetch(url, headers=None, timeout=8):
        if '/health' in url:
            return 200, b'ok', 5
        if any(r in url for r in ('/conversas', '/foco', '/gestao')):
            return 200, b'<html>Inbox comercial</html>', 50
        if '/api/conversations' in url:
            body = json.dumps({'conversations': [{} for _ in range(300)]}).encode()
            return 200, body, 100
        if '/api/messages' in url:
            n = per_url_calls.get(url, 0)
            per_url_calls[url] = n + 1
            seq = None
            for sub, lats in message_latencies.items():
                if sub in url:
                    seq = lats
                    break
            ms = seq[min(n, len(seq) - 1)] if seq else 120
            body = json.dumps({'messages': [{'text': 'x'}]}).encode()
            return 200, body, ms
        return 200, b'', 5

    return fake_fetch


class WatchdogConfirmationRetryTests(unittest.TestCase):
    """Incidente 20260629T115515Z: a 2ª amostra reler caso lento disparava o
    refresh SWR e saturava o GIL (health_8280=2378ms), confirmando falso positivo.
    best-of-N na amostra de confirmação filtra essa contenção auto-induzida sem
    mascarar lentidão sustentada.
    """

    @classmethod
    def setUpClass(cls):
        cls.wd = load_watchdog()
        # conv real do log: "fim lista Lucas 1".
        cls.slow_conv = '5541998029432'

    def setUp(self):
        self._orig_fetch = self.wd.fetch
        self.addCleanup(lambda: setattr(self.wd, 'fetch', self._orig_fetch))

    def test_run_checks_accepts_attempts(self):
        import inspect
        self.assertIn('attempts', inspect.signature(self.wd.run_checks).parameters)

    def test_single_attempt_flags_a_slow_message_case(self):
        # attempts=1 (1ª amostra): leitura lenta única vira falha.
        self.wd.fetch = _fake_fetch_factory({self.slow_conv: [3496]})
        fails, _ = self.wd.run_checks(None, {}, attempts=1, settle=0)
        keys = {k for k, _ in fails}
        self.assertTrue(any(self.slow_conv in k for k in keys))

    def test_transient_slow_clears_on_confirmation_retry(self):
        # attempts=2: 1ª leitura lenta (refresh SWR), 2ª já quente => sem falha.
        self.wd.fetch = _fake_fetch_factory({self.slow_conv: [3496, 200]})
        fails, _ = self.wd.run_checks(None, {}, attempts=2, settle=0)
        keys = {k for k, _ in fails}
        self.assertFalse(any(self.slow_conv in k for k in keys), f'fails={fails}')

    def test_sustained_slow_still_fails_with_retries(self):
        # Lentidão real persiste em todas as tentativas => continua sendo falha.
        self.wd.fetch = _fake_fetch_factory({self.slow_conv: [3496, 3600]})
        fails, _ = self.wd.run_checks(None, {}, attempts=2, settle=0)
        keys = {k for k, _ in fails}
        self.assertTrue(any(self.slow_conv in k for k in keys), f'fails={fails}')

    def test_healthy_panel_produces_no_fails(self):
        self.wd.fetch = _fake_fetch_factory({})
        fails, metrics = self.wd.run_checks(None, {}, attempts=2, settle=0)
        self.assertEqual(fails, [])
        # Continua reportando métricas de todos os checks.
        self.assertTrue(any(m.startswith('health_8280=') for m in metrics))
        self.assertTrue(any(m.startswith('conversations=') for m in metrics))


if __name__ == '__main__':
    unittest.main()
