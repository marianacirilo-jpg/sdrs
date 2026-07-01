# Handoff — FOLLOWUPS dashboard pausado para Dexter (2026-06-30)

## Motivo
Rafael pediu para parar este fluxo porque Dexter assumiu: “FOI MAL, eu pedi pro dexter cuidar disso tudo, salve tudo que vc tem e espere ate ele terminar”.

## Estado operacional
- Não reativar cron de follow-up por causa deste trabalho.
- Não promover/deployar Channel público.
- Não reiniciar bridges/chips WhatsApp.
- Não executar `safe_deploy promote/deploy` sem ordem explícita de Rafael/Dexter.
- Trabalho atual está **incompleto e não validado em stage**.

## Arquivos tocados nesta tentativa
- `scripts/channel_panel_v2.py`
  - adicionada rota `/followups` em `APP_ROUTES`;
  - adicionada API read-only `/api/followups-dashboard`;
  - criada função `followups_dashboard(uid, limit=160)`;
  - criada regra `followups_access_allowed(uid)` com Rafael-only;
  - UI adicionada no menu lateral/mobile com modo `followups`;
  - JS criado: `loadFollowups`, `drawFollowups`, KPIs, abas `overview/leads/logs/config`, datagrid de leads, logs e configuração read-only.
- `tests/test_channel_v2_core.py`
  - adicionado teste `test_followups_screen_is_rafael_only_read_only_and_wired`;
  - rota `/followups` incluída em teste de rotas;
  - houve ajuste em teste de approach/agenda perto de horário de meia-noite; revisar antes de aceitar.
- `/tmp/claude_followups_dashboard.md`
  - prompt enviado ao Claude Code para implementar/revisar a tela.

## Validações já rodadas
Última validação parcial passou:
```bash
python3 -m py_compile scripts/channel_panel_v2.py
node --check /tmp/channel_v2_frontend.js
python3 -m unittest \
  tests.test_channel_v2_core.ChannelV2CoreTests.test_followups_screen_is_rafael_only_read_only_and_wired \
  tests.test_channel_v2_core.ChannelV2CoreTests.test_screen_routes_are_declared_for_direct_urls -v
```
Resultado: OK.

Validação anterior completa de `tests.test_channel_v2_core` falhou antes dos últimos ajustes:
- erro `NameError: parse_dt` em `followups_dashboard` — corrigido usando `_parse_wpp_envio_ts`;
- erro `Counter` indefinido — corrigido importando `Counter`;
- falha em `test_approach_review_min_sample_rule` por divisão de buckets perto de meia-noite; revisar porque houve patch posterior em teste, mas a suíte completa NÃO foi rerodada depois.

## Pendências obrigatórias para Dexter antes de entregar
1. Reabrir diff de `scripts/channel_panel_v2.py` e `tests/test_channel_v2_core.py`.
2. Rodar gate local obrigatório:
```bash
python3 -m py_compile scripts/channel_panel_v2.py tests/channel_v2_smoke_gate.py
python3 - <<'PY'
from pathlib import Path
s=Path('scripts/channel_panel_v2.py').read_text()
js=s[s.index('<script>')+8:s.index('</script></body></html>')]
Path('/tmp/channel_v2_frontend.js').write_text(js)
print(len(js))
PY
node --check /tmp/channel_v2_frontend.js
python3 -m unittest tests.test_channel_v2_core tests.test_channel_v2_watchdog_hysteresis -v
python3 tests/channel_v2_smoke_gate.py
```
3. Se passar, só então rodar stage isolado:
```bash
scripts/channel_v2_safe_deploy.sh stage
```
4. Não promover para produção sem validação explícita.

## Escopo funcional pretendido da tela FOLLOWUPS
- URL: `/followups`
- API: `/api/followups-dashboard`
- Acesso: somente Rafael (`uid == 'rafael'`), read-only nesta primeira versão.
- Dados agregados:
  - `controle/sdr_followup_queue_status.json`
  - `controle/followup_textos_aprovados_rafael_20260630.json`
  - `docs/followup-research/*/lead-match-matrix.json`
  - `controle/wpp_envios.json`
  - resumo de rotinas/watchdogs já disponível via `rotinas_summary`.
- Datagrid proposto:
  - empresa/lead;
  - SDR;
  - fase F1/F2/F3/F4;
  - status MQL/precisa análise/liberado/enviado;
  - diagnóstico/fit Zydon;
  - buyer profile;
  - bloqueio/quality gate;
  - link HubSpot;
  - link interno de conversa quando possível.
- Aba configuração read-only:
  - janela operacional;
  - requireResearch;
  - scanMaxDeals;
  - manifesto e hashes dos textos fixos.

## Observações de risco
- A UI contém termos de auditoria/log em uma tela que é do Rafael, não dos SDRs; ainda assim, Dexter deve garantir que isso não apareça em telas comuns de SDR.
- `followups_dashboard` usa dados locais e read-only, mas precisa revisão de performance para `wpp_envios` grande.
- O teste completo e stage ainda não foram feitos depois das últimas correções.
