# Handoff para Dexter — MQL/Channel rigidez e visibilidade

Data: 2026-06-30
Origem: pedido do Rafael para parar e aguardar Dexter terminar.

## Status geral

Rafael pediu para Dexter assumir. Parei aqui. Não fazer novos envios, HubSpot, deploy/promote ou restart até Dexter terminar/validar.

## O que foi feito nesta sessão

### 1. Fluxo MQL rigidificado no código
Arquivo: `scripts/process_gate_once.py`

Foram centralizadas constantes fixas:

```python
TEXT_TO_PDF_DELAY_SECONDS = 60
PDF_TO_QUESTION_DELAY_SECONDS = 30
QUESTION_TO_AGENDA_DELAY_SECONDS = 20 * 60
MQL_DIAGNOSTIC_TEXT_FIXED = 'Fiz uma análise prévia do potencial da digitalização B2B do seu negócio.'
MQL_INTENT_QUESTION_FIXED = 'Como você imagina que a Zydon poderia te apoiar?'
MQL_AGENDA_PREFIX_FIXED = 'Se quiser garantir o melhor horário para um diagnóstico completo, pode marcar direto aqui:'
```

O envio usa as constantes, não texto solto espalhado.

### 2. Fix anterior preservado: commit antes do sleep de 20min
Arquivo: `scripts/process_gate_once.py`

O fluxo MQL registra grupo/HubSpot/ledger/fila antes do `time.sleep(QUESTION_TO_AGENDA_DELAY_SECONDS)`. A agenda virou etapa posterior idempotente com `agenda_pending` e `should_send_agenda()`.

Motivo: incidente Kóche/Atalaia em que texto+PDF+pergunta podiam sair, mas grupo/HubSpot/fila ficavam pendentes se o processo morresse no sleep.

### 3. Marker de grupo stale
Arquivo: `scripts/process_gate_once.py`

`grupo_notificacao_em_andamento` puro sem prova de envio real só bloqueia por `GROUP_INFLIGHT_STALE_SECONDS = 10 * 60`. Marker antigo sem `success/messageId/group_bridge_port` não trava grupo para sempre.

### 4. Channel/UI — visibilidade Kóche/Atalaia
Arquivo: `scripts/channel_panel_v2.py`

Backend local recalculado mostrou Kóche/Atalaia no topo:

```text
atalaia-calcados-militares-lucas-gibram +55 35 99888-9190 4609 ... diagnostico=feito sdr=sarah
koche-automotiva-rafael-silveira +55 19 99950-7130 4610 ... diagnostico=feito sdr=breno
Velas Vitoria +55 11 91551-1222 4600 ... diagnostico=pendente sdr=sarah
```

Hipótese do print do Rafael: UI/processo/prewarm/cache antigo ou aba sem refresh no momento; backend atual já mostra.

### 5. Fragilidades corrigidas/revisadas com Claude Code
Claude Code foi chamado para revisar fragilidades. Achados incorporados:

- `gateway` agora conta como porta de dispatch em `_dispatch_port_for_row()`.
- `_wpp_envio_lead_chat()` reconstrói chat individual a partir de `phone/telefone/whatsapp/lead_phone/numero + gateway/bridge_port` quando não há `to/jid`.
- `_wpp_envio_group_only_notice()` impede aviso interno ao grupo de virar conversa individual do lead.
- `real_phone_digits()` canonicaliza BR móvel antigo com 6/7/8/9 para nono dígito, mas não mexe em fixo 2-5.
- Contratos de inbox/timeline centralizados em constantes: `VISIBLE_TIMELINE_REAL_MESSAGE_CONTRACT`, `LEDGER_REAL_MESSAGE_MATCH_WINDOW_SEC`, `AUTOMATION_NEAR_DUP_WINDOW_SEC`, `LEDGER_METADATA_SKIP_FIELDS`, `PUBLIC_INBOX_COPY`.
- Claude também adicionou wiring read-only de `/agendas` no Channel; não promoveu.

### 6. Testes adicionados/validados
Arquivos:
- `tests/test_prospeccao_pdf_msg.py`
- `tests/test_channel_v2_core.py`

Testes importantes:
- `TestContratoMqlDiagnosticoRigido`
- `TestMqlCommitAntesDoSleepLongo`
- `TestShouldSendAgendaIdempotente`
- `TestGrupoInflightStale`
- `test_mql_outbound_fastlane_visible_for_koche_and_atalaia`
- `test_fastlane_reconstructs_individual_chat_from_phone_gateway_but_not_group_notice`
- `test_agendas_screen_backend_and_frontend_are_wired`
- `test_agendas_report_is_read_only_masks_phone_and_aggregates`

## Validação rodada

```bash
python3 -m py_compile scripts/process_gate_once.py scripts/channel_panel_v2.py tests/test_prospeccao_pdf_msg.py tests/test_channel_v2_core.py
```
OK.

```bash
python3 -m unittest tests.test_channel_v2_core -v
```
Resultado: 107 testes OK.

```bash
python3 -m unittest \
  tests.test_prospeccao_pdf_msg.TestContratoMqlDiagnosticoRigido \
  tests.test_prospeccao_pdf_msg.TestClassificacaoSemContradicao.test_koche_fabricante_automotivo_para_oficinas_e_mql_sem_confundir_com_confeccao \
  tests.test_prospeccao_pdf_msg.TestClassificacaoSemContradicao.test_coturno_atalaia_varejo_online_atacado_whatsapp_e_mql \
  tests.test_prospeccao_pdf_msg.TestMqlCommitAntesDoSleepLongo \
  tests.test_prospeccao_pdf_msg.TestShouldSendAgendaIdempotente \
  tests.test_prospeccao_pdf_msg.TestGrupoInflightStale -v
```
Resultado: 20 testes OK.

Observação: `scripts/channel_v2_release_gate.sh` rodou a parte unitária OK, mas o smoke gate retornou HTTP 404 em rota após `/conversas`, `/foco`, `/gestao`; Claude corrigiu wiring de `/agendas`. Não foi promovido/reiniciado produção.

## Estado operacional / cautelas

- Não foram enviados WhatsApps nesta etapa.
- Não foi chamado HubSpot.
- Não foi feito promote/deploy/restart proposital.
- Não há `process_gate_once.py` ativo pelo check anterior.
- Aguardar Dexter antes de qualquer novo passo.

## Pendência para Dexter

1. Revisar diff completo dos arquivos alterados.
2. Rodar gate/stage seguro se for assumir deploy.
3. Conferir no Channel público/stage se Kóche/Atalaia aparecem no topo após refresh/prewarm.
4. Só promover depois de validar visualmente e garantir que não há envio duplicado.
