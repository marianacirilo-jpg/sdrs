# WhatsApp Cron Centralizer Implementation Plan

> **For Hermes:** Use subagent-driven-development or Claude Code only task-by-task. Do not let Claude Code promote/deploy production or restart WhatsApp bridges.

**Goal:** Centralizar de uma vez a orquestração de WhatsApp Zydon, com natureza/origem/limite consistentes, sem múltiplos crons competindo e sem bagunçar diagnóstico, agenda, primeiro contato, follow-up, Não-MQL e conversa manual.

**Architecture:** Manter `scripts/whatsapp_safe_send.py` como camada única de transporte, mas mover a decisão de envio para um envelope padronizado com `nature`, `origin`, `thread_state`, `logical_message_id` e quota por conversa/natureza/chip. Migrar os senders em fases pequenas, primeiro em modo shadow e depois enforcement. A UI `/rotinas` vira cockpit operacional com abas diretas e data grids acionáveis, não uma visão geral solta.

**Tech Stack:** Python 3.12, scripts cron Hermes, Baileys bridge via HTTP local, JSON ledgers em `controle/`, Channel V2 em `scripts/channel_panel_v2.py`, unittest, safe deploy stage-first.

---

## Base factual usada

Relatório Claude Code criado em:

`docs/architecture/whatsapp-cron-centralizer-audit-2026-06-30.md`

Achados principais:

1. O transporte WhatsApp já passa majoritariamente por `scripts/whatsapp_safe_send.py`.
2. O problema central está acima do transporte:
   - vários helpers escrevendo `controle/wpp_envios.json`;
   - limites divergentes entre scripts;
   - contagem por mensagem bruta/parte, não por envio lógico/conversa/natureza;
   - painel tendo que inferir origem por `status`, `msg_type` e `campaign_id` soltos.
3. Crons antigos `PAUSADO-NAO-REATIVAR-*` devem continuar desligados.
4. `zydon-followup-parallel-lanes-5min` deve ficar pausado salvo ordem explícita.
5. `/rotinas` deve ser cockpit operacional em abas, com data grids e ações, sem “Visão geral” desconectada.

---

## Decisões de arquitetura propostas

### D1. Um envio lógico não é uma bolha

Um diagnóstico MQL pode gerar:

- texto inicial;
- PDF;
- pergunta final.

Hoje isso pode contar como 3 mensagens. No centralizador deve contar como:

```txt
1 logical_message_id
3 parts
nature = diagnostic_bundle ou diagnostic_initial/pdf/question por parte
quota_class = pipeline_followthrough
```

### D2. Manual/conversa ativa não consome quota de prospecção fria

Mensagem manual via Channel ou conversa em andamento deve registrar natureza correta, mas não entrar no mesmo limite de cold outbound.

Classes:

```txt
cold_automation       first_contact, followup_f1..f4, non_mql_outreach
pipeline_followthrough diagnostic_*, agenda_*, postdiag followup
active_conversation   manual_reply e respostas em thread ativa
internal              alertas internos, premeeting, warmup, system_monitor
```

### D3. Quota passa a ser por conversa/natureza/chip/dia

Não basta `N mensagens por chip`.

O manager deve olhar:

```txt
port
canonical conversation_id/JID
lead/contact/deal quando disponível
nature
quota_class
logical_message_id
dia BRT
últimos envios por conversa
```

### D4. `wpp_envios.json` terá um dono de escrita

Todos os helpers devem delegar a `scripts/zydon_operational_queues.py` ou a uma nova fachada de ledger, com lock real.

---

## Nova taxonomia obrigatória

Criar vocabulário fixo, sem strings soltas novas.

### `nature`

```txt
manual_reply
diagnostic_initial
diagnostic_pdf
diagnostic_question
diagnostic_bundle
diagnostic_agenda_invite
agenda_confirmation
agenda_reminder
first_contact
followup_f1
followup_f2
followup_f3
followup_f4
followup_f1_postdiag
non_mql_outreach
no_show_recovery
internal_group_alert
system_monitor
warmup
premeeting_summary
```

### `origin`

```txt
manual_channel
cron_active_mql
cron_diagnostic_pipeline
cron_followup_unificado
cron_followup_postdiag
cron_agenda_queue
cron_agenda_monitor
cron_non_mql
cron_incoming_response
cron_warmup
user_manual_script
watchdog
```

### `thread_state`

```txt
cold_outreach
active_conversation
post_diagnostic
scheduled_meeting
no_show
opt_out
internal_only
```

### Campos novos no ledger/audit

Adicionar progressivamente:

```json
{
  "nature": "followup_f2",
  "origin": "cron_followup_unificado",
  "thread_state": "cold_outreach",
  "quota_class": "cold_automation",
  "logical_message_id": "...",
  "logical_part": 1,
  "logical_parts_total": 1,
  "conversation_id": "5534...@s.whatsapp.net",
  "quota_counted": true,
  "manual": false
}
```

Compatibilidade: manter `status`, `msg_type`, `campaign_id` legados por enquanto, derivados da natureza.

---

## Fase 0 — congelar mapa e contratos

**Objective:** Criar testes de contrato antes de mexer em produção.

**Files:**
- Create: `tests/test_whatsapp_message_nature.py`
- Create: `tests/test_whatsapp_quota_manager.py`
- Modify later: nenhum sender ainda

**Tasks:**

1. Criar testes para mapear cada `nature` para `legacy_status`, `legacy_msg_type`, `quota_class` esperado.
2. Criar fixtures pequenas simulando:
   - diagnóstico com 3 partes;
   - follow-up frio;
   - resposta manual;
   - agenda confirmation;
   - alerta interno.
3. Rodar:

```bash
cd /root/.hermes/zydon-prospeccao
python3 -m unittest tests.test_whatsapp_message_nature tests.test_whatsapp_quota_manager -v
```

Expected inicial: fail, porque módulos ainda não existem.

**Rollback:** apagar testes/módulos novos. Nenhum sender afetado.

---

## Fase 1 — módulo de natureza

**Objective:** Criar vocabulário único e derivação legada sem mudar envio.

**Files:**
- Create: `scripts/whatsapp_message_nature.py`
- Test: `tests/test_whatsapp_message_nature.py`

**Implementation sketch:**

```python
NATURE_LEGACY = {
    'manual_reply': {'status': 'manual_reply', 'msg_type': 'manual_reply', 'quota_class': 'active_conversation'},
    'diagnostic_initial': {'status': 'enviado_lead', 'msg_type': 'diagnostico_mql', 'quota_class': 'pipeline_followthrough'},
    'diagnostic_pdf': {'status': 'enviado_lead', 'msg_type': 'diagnostico_pdf', 'quota_class': 'pipeline_followthrough'},
    'diagnostic_question': {'status': 'enviado_lead', 'msg_type': 'diagnostico_question', 'quota_class': 'pipeline_followthrough'},
    'first_contact': {'status': 'enviado_lead', 'msg_type': 'primeiro_contato', 'quota_class': 'cold_automation'},
    'followup_f1': {'status': 'enviado_lead', 'msg_type': 'primeiro_contato_cadencia', 'quota_class': 'cold_automation'},
    'followup_f2': {'status': 'enviado_lead', 'msg_type': 'primeiro_contato_cadencia', 'quota_class': 'cold_automation'},
    'followup_f3': {'status': 'enviado_lead', 'msg_type': 'primeiro_contato_cadencia', 'quota_class': 'cold_automation'},
    'followup_f4': {'status': 'enviado_lead', 'msg_type': 'primeiro_contato_cadencia', 'quota_class': 'cold_automation'},
    'non_mql_outreach': {'status': 'enviado_nao_mql_legitimo', 'msg_type': 'nao_mql_legitimo_tratativa', 'quota_class': 'cold_automation'},
    'agenda_confirmation': {'status': 'enviado_lead', 'msg_type': 'diagnostico_agenda_confirmacao', 'quota_class': 'pipeline_followthrough'},
    'agenda_reminder': {'status': 'enviado_lead', 'msg_type': 'diagnostico_agenda_lembrete_dia', 'quota_class': 'pipeline_followthrough'},
    'internal_group_alert': {'status': 'enviado_grupo', 'msg_type': 'internal_group_alert', 'quota_class': 'internal'},
}
```

**Validation:**

```bash
python3 -m unittest tests.test_whatsapp_message_nature -v
python3 -m py_compile scripts/whatsapp_message_nature.py
```

---

## Fase 2 — ledger único com lock

**Objective:** Nenhum sender ativo escreve `wpp_envios.json` com read-modify-write solto.

**Files:**
- Modify: `scripts/zydon_operational_queues.py`
- Modify: `disparo_dinamico.py`
- Modify: `scripts/process_gate_once.py`
- Modify: `scripts/monitor_diagnostico_agendado.py`
- Modify: `scripts/non_mql_legit_outreach.py`
- Test: `tests/test_zydon_operational_queues.py`

**Tasks:**

1. Expor `append_wpp_envio(record, path=WPP_ENVIOS)` como caminho oficial.
2. Em `disparo_dinamico.registrar_envio`, delegar para `append_wpp_envio`.
3. Em `process_gate_once.save_wpp`/`append_processed`, delegar para `append_wpp_envio` quando o destino for `wpp_envios`.
4. Em `monitor_diagnostico_agendado.append_wpp_envio`, remover helper próprio e delegar.
5. Em `non_mql_legit_outreach`, parar de usar helper legado de process_gate para append direto.
6. Adicionar teste concorrente: 10 threads appendando 10 registros, resultado final 100 registros sem perda.

**Validation:**

```bash
python3 -m unittest tests.test_zydon_operational_queues -v
python3 -m py_compile scripts/zydon_operational_queues.py disparo_dinamico.py scripts/process_gate_once.py scripts/monitor_diagnostico_agendado.py scripts/non_mql_legit_outreach.py
```

**Rollback:** voltar helpers locais, sem schema change.

---

## Fase 3 — quota manager em shadow mode

**Objective:** Calcular quota correta sem bloquear envio ainda.

**Files:**
- Create: `scripts/whatsapp_quota_manager.py`
- Test: `tests/test_whatsapp_quota_manager.py`
- Optional: `controle/whatsapp_quota_shadow.jsonl`

**Behavior inicial:**

```python
check_quota(..., enforce=False) -> QuotaDecision(ok=True, would_block=True/False, reason='...')
```

Shadow deve registrar:

```json
{
  "at": "...",
  "conversation_id": "...",
  "port": 4603,
  "nature": "followup_f2",
  "quota_class": "cold_automation",
  "logical_message_id": "...",
  "would_block": false,
  "reason": "ok"
}
```

**Rules:**

- `manual_reply` e `active_conversation`: nunca bloqueiam por quota fria.
- split/partes com mesmo `logical_message_id`: contam uma vez.
- cold automation: respeita por chip/hora, chip/dia, conversa/dia, conversa/nature/dia.
- internal: não entra em limite de lead.

**Validation:**

```bash
python3 -m unittest tests.test_whatsapp_quota_manager -v
python3 -m py_compile scripts/whatsapp_quota_manager.py
```

---

## Fase 4 — envelope opcional no safe_send

**Objective:** `safe_send_text` e `safe_send_file` aceitam metadados de natureza/origem sem quebrar callers antigos.

**Files:**
- Modify: `scripts/whatsapp_safe_send.py`
- Modify tests: `tests/test_whatsapp_safe_send.py`, `tests/test_whatsapp_send_standardization.py`

**API compatível:**

```python
safe_send_text(
    port,
    jid,
    text,
    uid='...',
    timeout=30,
    nature=None,
    origin=None,
    thread_state=None,
    logical_message_id=None,
    conversation_id=None,
    quota_enforce=False,
)
```

Se `nature is None`, usar:

```txt
nature = 'legacy_unknown'
origin = uid
quota_class = 'legacy'
quota_enforce = False
```

**Validation:**

```bash
python3 -m unittest tests.test_whatsapp_safe_send tests.test_whatsapp_send_standardization -v
python3 -m py_compile scripts/whatsapp_safe_send.py
```

---

## Fase 5 — migrar sender seguro primeiro: agenda monitor

**Objective:** Migrar um caminho claro e menos perigoso para envelope.

**Files:**
- Modify: `scripts/monitor_diagnostico_agendado.py`
- Test existing/add: `tests/test_monitor_diagnostico_agendado*.py` se houver; senão novo teste unitário de payload/nature.

**Mapping:**

```txt
diagnostico_agenda_confirmacao -> nature=agenda_confirmation, origin=cron_agenda_monitor, thread_state=scheduled_meeting
diagnostico_agenda_lembrete_dia -> nature=agenda_reminder, origin=cron_agenda_monitor, thread_state=scheduled_meeting
diagnostico_agenda_aviso_grupo -> nature=internal_group_alert, origin=cron_agenda_monitor, thread_state=internal_only
```

**Validation:**

```bash
python3 -m py_compile scripts/monitor_diagnostico_agendado.py
python3 -m unittest tests.test_whatsapp_safe_send tests.test_zydon_operational_queues -v
```

---

## Fase 6 — migrar agenda queue e Não-MQL

**Objective:** Migrar caminhos com menor número de variantes antes do MQL combo.

**Files:**
- Modify: `scripts/agenda_queue_sender.py`
- Modify: `scripts/non_mql_legit_outreach.py`

**Mapping:**

```txt
agenda_queue_sender -> nature=diagnostic_agenda_invite, origin=cron_agenda_queue, thread_state=post_diagnostic
non_mql_legit_outreach -> nature=non_mql_outreach, origin=cron_non_mql, thread_state=cold_outreach
```

**Validation:**

```bash
python3 -m py_compile scripts/agenda_queue_sender.py scripts/non_mql_legit_outreach.py
python3 -m unittest tests.test_incoming_policy_rigidity tests.test_zydon_operational_queues -v
```

---

## Fase 7 — migrar primeiro contato e F1-F4

**Objective:** Centralizar o maior volume com quota ainda em shadow.

**Files:**
- Modify: `disparo_dinamico.py`
- Modify: `scripts/cadencia_primeiro_contato.py`

**Mapping:**

```txt
stage lead_sem_contato / primeiro_contato -> nature=first_contact
attempt_number=1 -> followup_f1
attempt_number=2 -> followup_f2
attempt_number=3 -> followup_f3
attempt_number=4 -> followup_f4
origin=cron_followup_unificado
thread_state=cold_outreach salvo se houver resposta real recente, opt-out ou agenda
```

**Important:** manter `zydon-followup-parallel-lanes-5min` pausado.

**Validation:**

```bash
python3 -m py_compile disparo_dinamico.py scripts/cadencia_primeiro_contato.py
bash /root/.hermes/scripts/zydon_followup_safety_gate.sh
python3 -m unittest tests.test_followup_incident_safety tests.test_whatsapp_safe_send -v
```

---

## Fase 8 — migrar combo MQL/process_gate

**Objective:** O combo diagnóstico vira um envio lógico com partes, sem contar 3 vezes contra quota.

**Files:**
- Modify: `scripts/process_gate_once.py`
- Test: `tests/test_prospeccao_pdf_msg.py`

**Mapping:**

```txt
texto inicial -> diagnostic_initial
PDF -> diagnostic_pdf
pergunta final -> diagnostic_question
logical_message_id igual para as partes do mesmo diagnóstico
origin=cron_diagnostic_pipeline ou cron_active_mql
thread_state=post_diagnostic
quota_class=pipeline_followthrough
```

**Validation:**

```bash
python3 -m unittest tests.test_prospeccao_pdf_msg tests.test_whatsapp_safe_send -v
python3 -m py_compile scripts/process_gate_once.py
```

---

## Fase 9 — registrar manual do Channel sem confundir quota

**Objective:** Mensagem manual deixa de ser invisível para o cockpit, mas não conta como automação fria.

**Files:**
- Modify: `scripts/channel_panel_v2.py`
- Test: `tests/test_channel_v2_core.py`

**Behavior:**

`/api/send` e `/api/start-conversation` devem registrar no audit/ledger:

```txt
nature=manual_reply
origin=manual_channel
thread_state=active_conversation
quota_class=active_conversation
quota_counted=false
manual=true
```

Não expor isso como texto técnico na timeline. Usar só para filtros, data grid e métricas.

**Validation:**

```bash
python3 -m unittest tests.test_channel_v2_core -v
scripts/channel_v2_release_gate.sh
scripts/channel_v2_safe_deploy.sh stage
```

---

## Fase 10 — `/rotinas` v2: data grids e ações

**Objective:** Transformar `/rotinas` em ferramenta de operação, não painel passivo.

**UI changes requested by Rafael:**

- Remover ou reduzir “Visão geral” solta.
- Manter abas diretas por trabalho:
  - `Qualificação`
  - `Diagnóstico e agenda`
  - `Follow-ups`
  - `Conversas`
  - `Sistema`
- Data grid claro com ação por linha.
- Botões de ação para Rafael operar sem ler ledger/log.

### Abas propostas

#### Qualificação

Data grid:

```txt
Entrada | Empresa | Origem | Decisão | Motivo | Próxima ação | Responsável | Ações
```

Ações:

```txt
Aprovar MQL
Manter Não-MQL
Pedir pesquisa
Abrir HubSpot
Abrir conversa
```

#### Diagnóstico e agenda

Data grid:

```txt
Lead | Estado | Último envio | Natureza | Agenda | Link | SDR | Próxima ação | Ações
```

Ações:

```txt
Reenviar convite
Enviar lembrete
Marcar como sem link
Abrir agenda
Abrir conversa
```

#### Follow-ups

Data grid:

```txt
Lead | Fase | SDR/chip | Natureza | Quota | Último envio | Bloqueio | SLA | Ações
```

Ações:

```txt
Liberar para próximo tick
Pausar conversa
Reprocessar pesquisa
Bloquear por opt-out
Abrir texto aprovado
```

#### Conversas

Data grid:

```txt
Lead | Última resposta | Thread state | Natureza sugerida | Dono | Ação sugerida | Ações
```

Ações:

```txt
Abrir conversa
Marcar resolvido
Criar tarefa SDR
Transcrever áudio
Bloquear automação
```

#### Sistema

Data grid técnico recolhido:

```txt
Cron | Jornada | Estado | Último tick | Próximo tick | Obrigatório? | Ações
```

Ações protegidas:

```txt
Pausar com motivo
Reativar
Rodar dry-run
Ver último log
```

Todas as ações perigosas precisam de confirmação explícita e audit local.

### Backend novo

Adicionar endpoints read-only primeiro:

```txt
GET /api/rotinas/grid/qualification
GET /api/rotinas/grid/diagnostic-agenda
GET /api/rotinas/grid/followups
GET /api/rotinas/grid/conversations
GET /api/rotinas/grid/system
```

Depois POST com allowlist:

```txt
POST /api/rotinas/action
```

Payload:

```json
{
  "action": "pause_conversation",
  "target_type": "conversation",
  "target_id": "5534...@s.whatsapp.net",
  "reason": "opt_out",
  "confirm": true
}
```

Testar que não há envio WhatsApp direto nesses endpoints sem action allowlist.

---

## Fase 11 — ligar quota enforcement gradualmente

**Objective:** Sair de shadow para bloqueio real sem travar negócio.

Ordem:

1. Enforce apenas `cold_automation`.
2. Depois `pipeline_followthrough` com limites separados e mais permissivos.
3. Nunca bloquear `manual_reply` por quota fria.
4. Internal não conta para lead quota.

Config central:

`controle/whatsapp_quota_config.json`

Exemplo:

```json
{
  "mode": "shadow",
  "cold_automation": {
    "max_per_port_hour": 8,
    "max_per_port_day": 30,
    "max_per_conversation_day": 1,
    "max_same_nature_per_conversation_day": 1
  },
  "pipeline_followthrough": {
    "max_per_port_hour": 12,
    "max_per_port_day": 40,
    "count_logical_only": true
  },
  "active_conversation": {
    "counts_against_cold": false
  }
}
```

Decisão pendente Rafael: `max_per_port_hour` cold deve ser 8 ou 3.

---

## Fase 12 — limpeza final dos crons

**Objective:** Um único cron operacional por jornada, sem duplicidade.

Manter ativos:

```txt
zydon-active-mql-qualifier-1min
zydon-prospeccao-autonomo enquanto pipeline MQL ainda depende dele
zydon-agenda-queue-sender-1min
zydon-diagnostico-agendado-monitor
zydon-sdr-followup-unificado-5min
zydon-nao-mql-tratativa-legitima-10min
zydon-cinco-primeiras-etapas-escuta-respostas
watchdogs/guards necessários
```

Manter pausados:

```txt
PAUSADO-NAO-REATIVAR-sdr-primeiro-contato-5min-toda-base
PAUSADO-NAO-REATIVAR-zydon-mql-sdr-followup-5min
PAUSADO-NAO-REATIVAR-zydon-cadencia-primeiro-contato-all
PAUSADO-NAO-REATIVAR-zydon-lead-sem-contato-primeira-hora
zydon-followup-parallel-lanes-5min
```

Adicionar proteção no watchdog para nunca auto-resumir estes.

---

## Validação global antes de promover qualquer fase

```bash
cd /root/.hermes/zydon-prospeccao
python3 -m unittest \
  tests.test_whatsapp_safe_send \
  tests.test_whatsapp_send_standardization \
  tests.test_zydon_operational_queues \
  tests.test_channel_v2_core \
  tests.test_prospeccao_pdf_msg \
  tests.test_followup_incident_safety -v

python3 -m py_compile \
  scripts/whatsapp_safe_send.py \
  scripts/zydon_operational_queues.py \
  scripts/channel_panel_v2.py \
  scripts/process_gate_once.py \
  scripts/agenda_queue_sender.py \
  scripts/monitor_diagnostico_agendado.py \
  scripts/non_mql_legit_outreach.py \
  disparo_dinamico.py \
  scripts/cadencia_primeiro_contato.py

scripts/channel_v2_release_gate.sh
scripts/channel_v2_safe_deploy.sh stage
```

Nunca reiniciar bridge/chip WhatsApp para essas fases. Isso é arquitetura de fila/ledger/UI, não QR/auth.

---

## Rollback geral

Cada fase deve ser reversível por feature flag/config:

```txt
quota mode = off | shadow | enforce
manual ledger registration = off | shadow | on
rotinas actions = read_only | dry_run | enabled
```

Se qualquer sinal de duplicidade, queda de envio ou alerta de WhatsApp aparecer:

1. voltar quota para `shadow`;
2. manter safe_send e ledger locked;
3. pausar apenas o sender migrado da fase, não os crons obrigatórios todos;
4. validar com `whatsapp_outbound_quality_monitor.py` e loop audit.

---

## Decisões que precisam do Rafael antes de enforcement

1. Cold automation por chip/hora: 8 ou 3?
2. Cold automation por chip/dia: manter 30 ou usar limite dinâmico por chip?
3. Por conversa/dia: permitir no máximo 1 automação fria por dia?
4. Combo MQL deve contar como 1 envio lógico? Recomendação: sim.
5. Manual reply deve ir para `wpp_envios.json` além do audit? Recomendação: sim, mas `quota_counted=false`.
6. Follow-up 1 pós-diagnóstico: reativar dentro do orquestrador ou aposentar?
7. Avisos internos: grupo ou 1:1 Rafael/Mariana como padrão final?
8. Ações da `/rotinas`: quais botões Rafael quer habilitar primeiro? Recomendação inicial: abrir conversa, abrir HubSpot, pausar conversa por opt-out, reprocessar pesquisa, liberar próximo tick.

---

## Primeira entrega recomendada

Começar por Fase 0 + Fase 1 + Fase 2.

Motivo:

- não muda envio;
- não muda quota;
- resolve a parte mais perigosa: ledger sem dono único;
- cria vocabulário para o painel parar de adivinhar por substring;
- prepara `/rotinas` para data grid real.

Depois disso, migrar sender por sender.
