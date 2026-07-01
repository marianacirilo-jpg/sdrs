#!/usr/bin/env python3
"""Regressão da histerese do watchdog de performance do Channel V2.

Incidente 20260629T123227Z: o watchdog confirmou em 2 amostras uma falha que era
SÓ `/health 8280 timed out`, com toda rota/inbox dentro do orçamento
(conversations=6759ms<8000, rotas<2500, mensagens ok). Isso é contenção de GIL
durante recompute/rajada de disparo (o orçamento de /health é 3s/1000ms, bem mais
apertado que o trabalho legítimo do painel), não queda voltada ao usuário.

Estes testes fixam o contrato: falha confirmada só em health_8280 é silenciada;
qualquer falha funcional corroborante (rota, inbox, mensagens) ou no worker
health_8791 continua alertando.
"""
import importlib.util
import json
import unittest
import urllib.error
import urllib.parse
from pathlib import Path

WATCHDOG_PATH = Path('/root/.hermes/scripts/zydon_channel_v2_performance_watchdog.py')


def load_watchdog():
    spec = importlib.util.spec_from_file_location('zydon_channel_v2_performance_watchdog', WATCHDOG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_fetch_with_conv_list(present_ids, forbidden_convs=(), conv_list_down=False,
                               empty_convs=()):
    """Stub de fetch sem rede.

    /api/conversations devolve conversas carregando `present_ids` (+ padding p/
    passar o limiar de contagem), ou erra quando `conv_list_down`. /api/messages
    levanta HTTP 403 para qualquer conv em `forbidden_convs` (privacidade / lead
    migrado), devolve 200 com messages=[] para qualquer conv em `empty_convs`
    (detalhe vazio numa conv que segue anunciada), senão 200 com uma mensagem.
    Tudo o mais passa.
    """
    forbidden = set(forbidden_convs)
    empty = set(empty_convs)

    def fake_fetch(url, headers=None, timeout=8):
        if '/health' in url:
            return 200, b'ok', 5
        if any(r in url for r in ('/conversas', '/foco', '/gestao')):
            return 200, b'<html>Inbox comercial</html>', 50
        if '/api/conversations' in url:
            if conv_list_down:
                raise urllib.error.HTTPError(url, 503, 'Service Unavailable', {}, None)
            convs = [{'id': cid} for cid in present_ids]
            convs += [{'id': f'pad{i}::x@s.whatsapp.net'} for i in range(300)]
            return 200, json.dumps({'conversations': convs}).encode(), 100
        if '/api/messages' in url:
            for c in forbidden:
                if urllib.parse.quote(c, safe='') in url:
                    raise urllib.error.HTTPError(url, 403, 'Forbidden', {}, None)
            for c in empty:
                if urllib.parse.quote(c, safe='') in url:
                    return 200, json.dumps({'messages': []}).encode(), 1
            return 200, json.dumps({'messages': [{'text': 'x'}]}).encode(), 120
        return 200, b'', 5

    return fake_fetch


class WatchdogHysteresisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wd = load_watchdog()

    def test_confirm_failures_returns_key_msg_pairs_present_in_both_samples(self):
        first = [('health_8280', 'a'), ('route_/foco', 'b')]
        second = [('health_8280', 'a2'), ('conversations', 'c2')]
        confirmed = self.wd.confirm_failures(first, second)
        # só health_8280 está nas duas; devolve o par com a msg da 2ª amostra
        self.assertEqual(confirmed, [('health_8280', 'a2')])

    def test_lone_public_health_failure_is_treated_as_contention(self):
        # exatamente o incidente: única falha confirmada é /health 8280
        confirmed = [('health_8280', '/health 8280 erro=TimeoutError: timed out')]
        self.assertTrue(self.wd.is_lone_public_health_contention(confirmed))

    def test_health_failure_with_functional_failure_is_real_outage(self):
        confirmed = [
            ('health_8280', '/health 8280 erro=TimeoutError: timed out'),
            ('route_/conversas', 'rota /conversas status=502'),
        ]
        self.assertFalse(self.wd.is_lone_public_health_contention(confirmed))

    def test_worker_health_failure_is_not_public_contention(self):
        # health_8791 é o espelho interno: não é silenciado como CONTENÇÃO pública
        # (8280). É tratado pelo classificador próprio is_lone_internal_mirror_down.
        confirmed = [('health_8791', '/health 8791 status=500')]
        self.assertFalse(self.wd.is_lone_public_health_contention(confirmed))

    def test_empty_confirmed_is_not_contention(self):
        self.assertFalse(self.wd.is_lone_public_health_contention([]))

    def test_functional_only_failure_still_alerts(self):
        confirmed = [('conversations', '/api/conversations ms=12000')]
        self.assertFalse(self.wd.is_lone_public_health_contention(confirmed))


class WatchdogInternalMirrorTests(unittest.TestCase):
    """Incidente 20260629T205922Z-0537250b: a única falha confirmada foi
    `/health 8791 Connection refused`, com o público 8280=1ms, rotas=1ms,
    conversations=31ms/677 e mensagens ok. 8791 é o espelho interno (mesmo
    `channel_panel_v2.py` em 127.0.0.1, mesmos dados reais do 8280); os SDRs usam o
    8280. Espelho interno fora do ar, com tudo voltado ao SDR verde, não é queda
    user-facing — é processo que o ensure_zydon_channel ressuscita e cuja liveness
    o security heartbeat já cobre. Estes testes travam o contrato: lone health_8791
    é breadcrumb (silenciado); qualquer falha funcional/8280 junto volta a alertar.
    """

    @classmethod
    def setUpClass(cls):
        cls.wd = load_watchdog()

    def test_lone_internal_mirror_down_is_silenced(self):
        confirmed = [('health_8791', '/health 8791 erro=URLError: <urlopen error [Errno 111] Connection refused>')]
        self.assertTrue(self.wd.is_lone_internal_mirror_down(confirmed))

    def test_mirror_down_with_public_health_is_real_outage(self):
        # 8791 E 8280 fora => mesmo código nas duas portas caindo: queda real.
        confirmed = [
            ('health_8791', '/health 8791 erro=Connection refused'),
            ('health_8280', '/health 8280 erro=Connection refused'),
        ]
        self.assertFalse(self.wd.is_lone_internal_mirror_down(confirmed))

    def test_mirror_down_with_functional_failure_is_real_outage(self):
        confirmed = [
            ('health_8791', '/health 8791 erro=Connection refused'),
            ('conversations', '/api/conversations status=502'),
        ]
        self.assertFalse(self.wd.is_lone_internal_mirror_down(confirmed))

    def test_empty_confirmed_is_not_mirror_down(self):
        self.assertFalse(self.wd.is_lone_internal_mirror_down([]))

    def test_public_contention_is_not_classified_as_mirror_down(self):
        # lone health_8280 é contenção pública, não espelho interno: classificadores
        # disjuntos não se sobrepõem.
        confirmed = [('health_8280', '/health 8280 erro=TimeoutError: timed out')]
        self.assertFalse(self.wd.is_lone_internal_mirror_down(confirmed))
        self.assertTrue(self.wd.is_lone_public_health_contention(confirmed))


class WatchdogStaleFixtureTests(unittest.TestCase):
    """Incidente 20260629T202005Z-de0fd15a: as fixtures `4603::<lead>` (fim da
    lista do Lucas) deram 403 nas duas amostras porque a cadência de hoje saiu por
    chip COMUNICADOR (a conv migrou para outra porta), então `4603::<lead>` não é
    mais anunciada e o painel nega por privacidade — correto. A detecção de fixture
    velha existia (`message_case_is_stale_fixture`/`record_stale_fixtures`) mas não
    estava ligada em `run_checks`, e o falso positivo virou alerta. Estes testes
    travam o wiring: fixture fora da lista é silenciada; conv que ESTÁ na lista e
    falha continua alertando; lista indisponível => testa como antes.
    """

    BIOCOM = '4607::5534992492012@s.whatsapp.net'
    LUNAR = '4605::5511987045720@s.whatsapp.net'
    BOUTIQUE = '4610::5555997175688@s.whatsapp.net'
    LUCAS1 = '4603::5541998029432@s.whatsapp.net'
    LUCAS2 = '4603::5551981340773@s.whatsapp.net'
    LIVE = [BIOCOM, LUNAR, BOUTIQUE]

    @classmethod
    def setUpClass(cls):
        cls.wd = load_watchdog()

    def setUp(self):
        self._orig_fetch = self.wd.fetch
        self.addCleanup(lambda: setattr(self.wd, 'fetch', self._orig_fetch))

    def test_message_case_is_stale_fixture_pure(self):
        ids = {self.BIOCOM, self.LUNAR}
        self.assertTrue(self.wd.message_case_is_stale_fixture(self.LUCAS1, ids))
        self.assertFalse(self.wd.message_case_is_stale_fixture(self.BIOCOM, ids))
        # lista indisponível => nunca classifica como stale
        self.assertFalse(self.wd.message_case_is_stale_fixture(self.LUCAS1, None))

    def test_run_checks_wires_stale_detection(self):
        import inspect
        self.assertIn('note_stale', inspect.signature(self.wd.run_checks).parameters)

    def test_stale_fixture_403_is_silenced_when_absent_from_list(self):
        # Reproduz o incidente: 4603::* fora da lista e dando 403 => sem falha.
        self.wd.fetch = _fake_fetch_with_conv_list(
            self.LIVE, forbidden_convs=[self.LUCAS1, self.LUCAS2])
        fails, _ = self.wd.run_checks(None, {}, attempts=1, settle=0)
        keys = {k for k, _ in fails}
        self.assertFalse(any('4603' in k for k in keys), f'fails={fails}')

    def test_forbidden_conv_still_in_list_still_alerts(self):
        # Privacidade não mascara queda real: se o painel AINDA anuncia a conv e
        # /api/messages dá 403, isso é problema e tem que alertar.
        self.wd.fetch = _fake_fetch_with_conv_list(
            self.LIVE + [self.LUCAS1], forbidden_convs=[self.LUCAS1])
        fails, _ = self.wd.run_checks(None, {}, attempts=1, settle=0)
        keys = {k for k, _ in fails}
        self.assertTrue(any(self.LUCAS1 in k for k in keys), f'fails={fails}')

    def test_conv_list_unavailable_tests_fixture_as_before(self):
        # Sem lista (known_conv_ids=None) NÃO perdemos cobertura: a fixture 403
        # ainda é testada e falha, como antes da mudança.
        self.wd.fetch = _fake_fetch_with_conv_list(
            self.LIVE, forbidden_convs=[self.LUCAS1], conv_list_down=True)
        fails, _ = self.wd.run_checks(None, {}, attempts=1, settle=0)
        keys = {k for k, _ in fails}
        # /api/conversations em si falha (503)...
        self.assertTrue(any(k == 'conversations' for k in keys), f'fails={fails}')
        # ...e a fixture 403 também continua falhando (não silenciada)
        self.assertTrue(any(self.LUCAS1 in k for k in keys), f'fails={fails}')

    def test_healthy_live_conversation_produces_no_fails(self):
        self.wd.fetch = _fake_fetch_with_conv_list(
            self.LIVE + [self.LUCAS1, self.LUCAS2])
        fails, metrics = self.wd.run_checks(None, {}, attempts=1, settle=0)
        self.assertEqual(fails, [], f'fails={fails}')
        self.assertTrue(any(m.startswith('conversations=') for m in metrics))


class WatchdogEmptyDetailFixtureTests(unittest.TestCase):
    """Incidente 20260701T111315Z-2842b381: a fixture antiga 'BIOCOM Rafael/Sarah'
    (4607::5534992492012) é card operacional institucional SEM bolha real no device.
    Pelo contrato do painel (King Talhas 26/06, privacidade de comunicador) o detalhe
    devolve 200 com messages=[] em vez de inventar bolha falsa. A conv ESTÁ na lista,
    então o guard de fixture-velha não a pula, e o check `not msgs` alarmava para
    sempre (determinístico: 1ms/count=0 nas duas amostras) — falso positivo, não queda.

    Correção: o watchdog passa a probar 4607::5585988903132 (Rafael institucional com
    bolhas reais, já validado pelo smoke gate). Estes testes travam o contrato: a
    fixture count=0-por-contrato saiu das CASES e a real entrou; mas detecção de
    detalhe vazio numa conv que segue anunciada continua alertando (regra 6: não trocar
    histórico por 'Sem mensagens')."""

    EMPTY_BY_CONTRACT = '4607::5534992492012@s.whatsapp.net'
    REAL_BUBBLES = '4607::5585988903132@s.whatsapp.net'

    @classmethod
    def setUpClass(cls):
        cls.wd = load_watchdog()

    def setUp(self):
        self._orig_fetch = self.wd.fetch
        self.addCleanup(lambda: setattr(self.wd, 'fetch', self._orig_fetch))

    def _case_convs(self):
        return [conv for _, conv, _ in self.wd.CASES]

    def test_empty_by_contract_fixture_removed_from_cases(self):
        # A conv sem detalhe-por-contrato não pode mais ser fixture: alarmaria sempre.
        self.assertNotIn(self.EMPTY_BY_CONTRACT, self._case_convs())

    def test_real_bubble_fixture_is_probed(self):
        # Cobertura do caminho de mensagens institucional é preservada com a conv real.
        self.assertIn(self.REAL_BUBBLES, self._case_convs())

    def test_empty_detail_on_listed_conv_still_alerts(self):
        # Regra 6: se a conv AINDA é anunciada e o detalhe volta vazio, é regressão
        # real ('Sem mensagens' no lugar de histórico) e tem que alertar — não pode
        # ser silenciada como fixture velha (ela está na lista).
        self.wd.fetch = _fake_fetch_with_conv_list(
            [self.REAL_BUBBLES], empty_convs=[self.REAL_BUBBLES])
        fails, _ = self.wd.run_checks(None, {}, attempts=1, settle=0)
        keys = {k for k, _ in fails}
        self.assertTrue(any(self.REAL_BUBBLES in k for k in keys), f'fails={fails}')

    def test_real_bubble_fixture_produces_no_fail_when_detail_present(self):
        self.wd.fetch = _fake_fetch_with_conv_list([self.REAL_BUBBLES])
        fails, _ = self.wd.run_checks(None, {}, attempts=1, settle=0)
        self.assertFalse(any(self.REAL_BUBBLES in k for k, _ in fails), f'fails={fails}')


if __name__ == '__main__':
    unittest.main()
