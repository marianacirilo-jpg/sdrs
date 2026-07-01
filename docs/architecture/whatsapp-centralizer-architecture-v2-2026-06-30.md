# Arquitetura executável — Centralizador WhatsApp Zydon v2

**Data:** 2026-06-30
**Tipo:** Documento de arquitetura (READ-ONLY: nenhum código foi editado, nenhum cron/bridge/painel reiniciado, nenhum WhatsApp enviado)
**Autor:** Claude Code, a pedido de Rafael
**Substitui/consolida:** `docs/architecture/whatsapp-cron-centralizer-audit-2026-06-30.md` (auditoria) e `.hermes/plans/2026-06-30_224711-whatsapp-cron-centralizer.md` (plano). Este documento é o contrato executável; os dois anteriores são a base factual.

**Objetivo de Rafael:** arquitetura centralizada, codificada e **sem subjetividade** para entrada/saída de WhatsApp. Amanhã entram **2 chips por SDR** (depois 3+). Todo envio precisa escolher o chip certo por regra de negócio central, nunca usar chip de outro SDR, e os limites precisam contar **envio lógico** e **classe de quota**, não "mensagem bruta". A tela `/rotinas` precisa virar cockpit executivo/operacional, não parede de cards.

---

## 1. Causa raiz: por que há pouco follow-up e pouco controle

A baixa quantidade de disparos **não vem do transporte** (que já é central e seguro em `scripts/whatsapp_safe_send.py`). Vem de **cinco causas raiz acima do transporte**, todas estruturais:

1. **Decisão de envio fragmentada entre senders.** Cada sender (`disparo_dinamico.py`, `process_gate_once.py`, `cadencia_primeiro_contato.py`, `non_mql_legit_outreach.py`, `agenda_queue_sender.py`, `monitor_diagnostico_agendado.py`, painel) reimplementa sua própria noção de "posso enviar?", "qual chip?", "qual limite?". Não há um ponto único que decida. Resultado: muitos crons competindo, e cada um é conservador por medo de duplicar → o conjunto dispara **menos** do que poderia.

2. **Limite por mensagem bruta e por chip, não por envio lógico.** O combo MQL (texto + PDF + pergunta) conta como **3 disparos** contra o teto do chip. Um único envio lógico consome 3 do orçamento, então o chip "estoura" o limite cedo e o follow-up legítimo daquele dia é barrado. Pior: existem **dois valores divergentes** do mesmo teto — `MAX_EXTERNAL_PER_PORT_HOUR = 8` em `disparo_dinamico.py` e `= 3` em `process_gate_once.py`. O mesmo chip tem teto diferente conforme o caminho que dispara.

3. **Conversa ativa e mensagem manual caem na mesma quota de cold.** Não há `thread_state`. Uma resposta manual do SDR em conversa aberta é tratada (ou ignorada) como se fosse prospecção fria, e o painel `/api/send` nem registra natureza no ledger principal — fica invisível para qualquer contagem. Isso faz a operação "gastar" orçamento frio com mensagens que não são frias, e ao mesmo tempo não enxergar o que foi enviado manualmente.

4. **Follow-up pós-diagnóstico descoberto.** O passo "pós-diagnóstico vira Follow-up 1" (`mql_sdr_followup.py`) está com cron `PAUSADO-NAO-REATIVAR` e foi comentado no fluxo unificado em 30/06 por segurança. Hoje esse follow-up simplesmente **não roda** — uma das maiores fontes de volume perdido.

5. **Ledger sem dono de escrita.** `controle/wpp_envios.json` é escrito por **≥5 helpers**, sendo que `disparo_dinamico.registrar_envio` e `process_gate_once.save_wpp` fazem read-modify-write **sem `flock` no arquivo**. Dois crons concorrentes podem perder um append (lost update). Isso gera medo de paralelizar → menos lanes → menos disparo. O `whatsapp_routing.py` (decisão multichip determinística) **já existe e está pronto**, mas **nenhum sender o importa ainda** — a inteligência de chip está escrita e desligada.

> **Resumo:** o sistema dispara pouco porque cada sender é conservador isolado, o limite pune o envio lógico contando partes, conversa ativa e manual sujam a quota fria, o follow-up pós-diagnóstico está desligado, e o ledger sem lock desencoraja paralelismo. A correção é **mover a decisão para um centro único** com vocabulário fixo e quota por envio lógico.

---

## 2. Mapa atual dos senders/crons que decidem WhatsApp

Todos terminam em `whatsapp_safe_send.safe_post_bridge` (POST `127.0.0.1:{port}/send|/send-file`), que aplica: normalização JID→PN, bloqueio de `@lid` sem telefone, dedupe por destino+payload (janela 3600s), `GLOBAL_TRANSPORT_LOCK` + lock por destino+payload, auditoria em `controle/channel_outbound_audit.jsonl` e reconciliação contra `history_<port>.json`. **O transporte já é central. A decisão não é.**

| # | Sender | Cron oficial | Decide chip como? | Ledger (escrita) | Limite que aplica | Natureza hoje |
|---|---|---|---|---|---|---|
| 1 | `disparo_dinamico.py` (primeiro contato) | `zydon-sdr-followup-unificado-5min` | porta fixa/argumento do cron | `wpp_envios.json` via `registrar_envio` **(sem flock)** | `MAX_..._HOUR=8`, `_DAY=30`, por chip, por parte | `msg_type=primeiro_contato` |
| 2 | `cadencia_primeiro_contato.py` (F1–F4) | `zydon-sdr-followup-unificado-5min` | herda de #1 | via `d.registrar_envio` | `--max-per-hour=3` (SDR) + tetos de #1 | `primeiro_contato_cadencia` + `attempt_number` |
| 3 | `process_gate_once.py` (combo MQL) | `zydon-prospeccao-autonomo` (agente) | lógica interna do gate | `wpp_envios.json` via `save_wpp`/`append_processed` **(sem flock)** | `MAX_..._HOUR=3`, `_DAY=30` **(diverge de #1)** | `status=enviado_lead/...`, sem `campaign_id` |
| 4 | `mql_sdr_followup.py` (F1 pós-diag) | `PAUSADO-NAO-REATIVAR` + comentado no unificado | herda de #1 | via `d.registrar_envio` | `--max-per-hour=2`, `--max-per-day=12` | `mql_followup1_deterministico` |
| 5 | `non_mql_legit_outreach.py` | `zydon-nao-mql-tratativa-legitima-10min` | comunicadores 4606/4600/4607 | `wpp_envios.json` via `p.save_wpp` | `p.MAX_..._HOUR=3`, janela 07–22h | `nao_mql_legitimo_tratativa` |
| 6 | `agenda_queue_sender.py` | `zydon-agenda-queue-sender-1min` | herda do registro da agenda | `append_wpp_envio` **(com flock)** + `agenda_queue.json` | lock por arquivo | `mql_agenda_sdr_apos_diagnostico` |
| 7 | `monitor_diagnostico_agendado.py` | `zydon-diagnostico-agendado-monitor` (5m) | herda do registro | **helper próprio** `append_wpp_envio` (L461) | `--max-sends=2`/tick | `diagnostico_agenda_confirmacao/lembrete` |
| 8 | `active_mql_qualifier.py` | `zydon-active-mql-qualifier-1min` | **não envia** (só enfileira) | `mql_pipeline_queue.json` (locked) | — | estados internos |
| 9 | Painel `channel_panel_v2.py` `/api/send`, `/api/start-conversation` | manual (SDR/Rafael) | porta da sessão do SDR | **só** `channel_outbound_audit.jsonl` | dedupe texto; **sem quota** | **sem natureza registrada** |
| 10 | `manual_*.py`, `process_current_gate_*.py`, `send_backlog_*` | one-shot manual | ad-hoc | vários helpers | tetos do módulo importado | `status`/`msg_type` ad-hoc |

**Decisão de chip hoje:** cada SDR tem **exatamente 1 porta** (`channel_users.json`: breno→4605, sarah→4601, lucas_batista→4603), então a escolha de chip é trivial e nenhum sender precisou escolher. **Isso quebra amanhã** quando cada SDR tiver 2+ chips.

**Módulo de roteamento multichip já existe e está desligado:** `scripts/whatsapp_routing.py` implementa exatamente a regra que Rafael quer — `existing_thread_port` (continuar no chip que já conversou), `choose_new_thread_port` (distribuir lead novo por menor carga + hash estável entre chips saudáveis do SDR), `sdr_ports` (nunca cruzar SDR). **Nenhum sender o importa ainda.** Ligar isso é a peça que faz o multichip funcionar.

**Locks coexistentes** (funcionam, mas ninguém tem o mapa): `whatsapp_global_transport.lock` (transporte) + `whatsapp_send_locks/<hash>.lock` (idempotência destino+payload) na camada segura; `/tmp/zydon_external_whatsapp_send.lock` (semáforo dos crons); `queue_locks/*.lock` (filas); locks por wrapper de cron. O **ledger** (`wpp_envios.json`) escapa de todos em 2 dos helpers principais.

---

## 3. Arquitetura-alvo (módulos)

Princípio: **manter o transporte que já funciona**, mover a decisão para um centro único, em camadas com responsabilidade exclusiva. Nada de reescrever a bridge; nada de big-bang.

```
┌─────────────────────────────────────────────────────────────────────┐
│ SENDERS (disparo, cadencia, process_gate, non_mql, agenda, monitor,  │
│          painel manual, scripts manuais)                             │
│   — param de conhecer chip, split, ledger e quota —                  │
└───────────────┬─────────────────────────────────────────────────────┘
                │ send_request(SendRequest{conversation, owner_sdr,
                │              nature, origin, parts[...]})
                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ (A) MessageIntent / natureza        scripts/whatsapp_message_nature.py│
│     vocabulário fixo nature/origin/thread_state → quota_class,        │
│     legacy_status/msg_type (compat). SEM string solta nova.           │
├─────────────────────────────────────────────────────────────────────┤
│ (B) ConversationRouter multichip    scripts/whatsapp_routing.py (JÁ EXISTE)│
│     existing_thread_port → senão choose_new_thread_port; nunca cruza  │
│     SDR; saúde do chip via health. Decisão determinística + razão.    │
├─────────────────────────────────────────────────────────────────────┤
│ (C) QuotaManager                    scripts/whatsapp_quota_manager.py │
│     check_and_reserve(conversation, port, nature, thread_state)       │
│     conta por logical_message_id e por quota_class. Shadow→enforce.   │
├─────────────────────────────────────────────────────────────────────┤
│ (D) ConversationScope/listener      scripts/whatsapp_conversation_scope.py│
│     só escuta conversa iniciada pelo sistema; bloqueia pessoal e chip↔chip;│
│     agente conduz como dono e só escala dúvida real.                 │
├─────────────────────────────────────────────────────────────────────┤
│ (E) DispatchLedger único c/ lock    scripts/zydon_operational_queues.py│
│     append_wpp_envio_locked = ÚNICO dono de escrita de wpp_envios.json │
├─────────────────────────────────────────────────────────────────────┤
│ (F) Transporte seguro (mantém)      scripts/whatsapp_safe_send.py     │
│     normaliza JID, dedupe destino+payload, audit, reconciliação       │
└───────────────┬─────────────────────────────────────────────────────┘
                ▼  POST 127.0.0.1:{port}/send | /send-file
            Baileys bridge (intocada)

CronOrchestrator / RunCoordinator  →  governa QUEM roda quando, sem competir
UI Control Plane (/rotinas)        →  lê o ledger único + quota + router; opera filas
```

### (A) MessageIntent / natureza — `scripts/whatsapp_message_nature.py`
Vocabulário único e fechado. Substitui `status`/`msg_type`/`campaign_id` soltos (que passam a ser **derivados** para compatibilidade). Funções:
- `Nature`, `Origin`, `ThreadState` (constantes — ver §4 e §5).
- `quota_class_for(nature, thread_state) -> QuotaClass`.
- `derive_thread_state(conversation_id, ledger, hubspot_stage) -> ThreadState` (último incoming do lead, etapa HubSpot, presença de diagnóstico/agenda).
- `legacy_status_for(nature)` / `legacy_msg_type_for(nature)` — gera os campos antigos para o painel e os dedupes existentes não quebrarem.

### (B) ConversationRouter multichip — `scripts/whatsapp_routing.py` (já existe, falta ligar)
Regra de negócio central, **sem subjetividade**:
1. Se há thread aberta do lead em um chip **deste** SDR → continuar nesse chip (`existing_thread_port`).
2. Se lead novo → distribuir entre chips **saudáveis do mesmo SDR** por menor carga + hash estável (`choose_new_thread_port`).
3. Nunca usar chip de outro SDR (`sdr_ports` filtra por `owner`/`users[uid].ports`).
4. Retorna `{port, mode, reason}` — razão explícita para painel/log, e **não envia**.
Falta: (a) sender chamar `choose_outbound_port` em vez de porta fixa; (b) alimentar `health` (de `whatsapp_bridge_health_monitor`) para pular chip com QR/queda; (c) usar `channel_users.json[uid].ports` como fonte dos 2+ chips.

### (C) QuotaManager — `scripts/whatsapp_quota_manager.py`
- `check_and_reserve(conversation_id, port, nature, thread_state, logical_message_id) -> (ok, reason, quota_class)`.
- Lê o **ledger único** + `channel_outbound_audit.jsonl`, conta por `logical_message_id` (não por parte) e por `quota_class`.
- Constantes **únicas** (remove o 8×3): `MAX_COLD_PER_PORT_HOUR/_DAY`, `MAX_PER_CONVERSATION_DAY`, `MAX_SAME_NATURE_PER_CONVERSATION_DAY`. Config em `controle/whatsapp_quota_config.json` com `mode: off|shadow|enforce`.
- `active_conversation`/`internal` nunca bloqueiam por quota fria.

### (D) DispatchLedger único com lock — `scripts/zydon_operational_queues.py`
- `append_wpp_envio_locked(record)` vira o **único** caminho de escrita de `wpp_envios.json` (já tem `update_json_locked` com `flock`).
- `registrar_envio`, `save_wpp`/`append_processed`, o helper próprio do monitor e o do non_mql **passam a delegar** a ele. Resolve o lost-update.
- Schema do registro = §4.

### (E) Transporte seguro — `scripts/whatsapp_safe_send.py` (mantém)
Ganha um envelope opcional `nature/origin/thread_state/logical_message_id/conversation_id` em `safe_send_text/file`, repassado ao `record_outbound_audit`. Sem isso, default `legacy_*` e `quota_enforce=False` — callers antigos não quebram.

### CronOrchestrator / RunCoordinator
Hoje há crons que competem e um `bottleneck-watchdog` que faz **auto-resume sozinho**. Alvo: **1 cron operacional por jornada** (qualificação, diagnóstico/agenda, follow-up unificado, não-MQL, escuta de respostas) + um coordenador que:
- mantém os 4 `PAUSADO-NAO-REATIVAR` numa allowlist **negativa** que o watchdog respeita (nunca religa);
- expõe estado real (`último tick`, `próximo tick`, `obrigatório?`) para a aba Sistema do `/rotinas`;
- não duplica decisão de envio — isso é só do centralizador (A–E).

### UI Control Plane — `/rotinas`
Deixa de ser parede de cards read-only e vira **data grid operável** sobre o ledger único + quota + router (ver §9).

---

## 4. Modelo de dados mínimo do envio lógico

Um registro por **envio lógico** (não por bolha). O combo MQL = **1** `logical_message_id` com 3 `parts`.

```json
{
  "logical_message_id": "lm_20260630T2031_ab12cd",   // 1 por envio lógico
  "lead_id": "hs-deal-or-contact-id",                 // HubSpot quando houver
  "phone": "5534999999999",                           // dígitos canônicos BR
  "jid": "5534999999999@s.whatsapp.net",              // PN resolvido pela camada segura
  "conversation_id": "5534999999999@s.whatsapp.net",  // canonical (= jid; grupo = @g.us)
  "owner_sdr": "lucas_batista",                        // dono comercial; nunca cruza
  "selected_port": 4603,                               // chip escolhido pelo router
  "nature": "followup_f2",                             // §5 vocabulário fixo
  "origin": "cron_followup_unificado",                // quem disparou
  "thread_state": "cold_outreach",                    // estado da CONVERSA
  "quota_class": "cold_automation",                   // §6, derivado de nature+thread_state
  "parts": [                                           // partes do MESMO envio lógico
    {"seq": 1, "kind": "text", "part_nature": "diagnostic_initial", "message_id": "...", "status": "sent"},
    {"seq": 2, "kind": "file", "part_nature": "diagnostic_pdf",     "message_id": "...", "status": "sent"},
    {"seq": 3, "kind": "text", "part_nature": "diagnostic_question","message_id": "...", "status": "sent"}
  ],
  "quota_counted": true,                               // false p/ manual/active/internal
  "status": "sent",                                    // sent|blocked_quota|blocked_duplicate|partial|failed
  "router_mode": "existing_thread",                   // existing_thread|new_thread_balanced|no_sdr_port
  "router_reason": "Lead já conversa com este SDR por esse chip.",
  "ts": "2026-06-30T20:31:00-03:00"
}
```

Campos `status`/`msg_type`/`campaign_id` legados continuam derivados de `nature` (compat com painel/dedupe atuais). `phone`/`jid`/`conversation_id` saem da normalização que a camada segura já faz.

---

## 5. Classes de quota recomendadas

| `quota_class` | Inclui `nature` | Conta contra limite frio? |
|---|---|---|
| `cold_automation` | `first_contact`, `followup_f1..f4`, `non_mql_outreach` | **Sim** — alvo dos limites anti-bloqueio |
| `pipeline_followthrough` | `diagnostic_initial/pdf/question`, `diagnostic_agenda_invite`, `agenda_confirmation`, `agenda_reminder`, `followup_f1_postdiag`, `no_show_recovery` | Conta em limite **próprio**, mais permissivo (é consequência de MQL/agenda, não frio) |
| `active_conversation` | `manual_reply` e **qualquer** envio com `thread_state=active_conversation` | **Não** — nunca consome quota fria |
| `internal` | `internal_group_alert`, `premeeting_summary`, `system_monitor` | **Não** — não é mensagem a lead |
| `warmup` / `system` | `warmup` (aquecimento entre chips) | **Não** — saúde de chip, conta só em limite próprio de warmup |

Vocabulário fixo de `nature` (fonte: §4 da auditoria e §taxonomia do plano):
`manual_reply · diagnostic_initial · diagnostic_pdf · diagnostic_question · diagnostic_agenda_invite · agenda_confirmation · agenda_reminder · first_contact · followup_f1..f4 · followup_f1_postdiag · non_mql_outreach · no_show_recovery · internal_group_alert · system_monitor · warmup · premeeting_summary`.

`origin`: `manual_channel · cron_active_mql · cron_diagnostic_pipeline · cron_followup_unificado · cron_followup_postdiag · cron_agenda_queue · cron_agenda_monitor · cron_non_mql · cron_incoming_response · cron_warmup · user_manual_script · watchdog`.

`thread_state`: `cold_outreach · active_conversation · post_diagnostic · scheduled_meeting · no_show · opt_out · internal_only`.

---

## 6. Regras de contagem (sem subjetividade)

1. **Bundle diagnóstico = 1 envio lógico, N partes.** Texto + PDF + pergunta compartilham um `logical_message_id`; a quota conta **1**, não 3. As partes ficam em `parts[]`.
2. **Follow-up F1–F4 conta conforme contexto:**
   - `thread_state = cold_outreach` (sem resposta real do lead) → `quota_class = cold_automation`.
   - `thread_state = active_conversation` (lead respondeu de verdade) → `active_conversation`, **não** consome quota fria.
   - `followup_f1_postdiag` (pós-diagnóstico) → `pipeline_followthrough`.
3. **Manual reply / conversa ativa não consome cold quota.** `/api/send` registra `nature=manual_reply`, `quota_class=active_conversation`, `quota_counted=false`. Some-se ao ledger único só para o cockpit enxergar — nunca para barrar disparo frio.
4. **Grupo interno não consome quota de lead.** `internal_group_alert` (aviso ao grupo/1:1 Mariana/Rafael) é `quota_class=internal`, `quota_counted=false`.
5. **Contagem por chip é por `quota_class`, não global por parte.** `cold_automation` tem `MAX_COLD_PER_PORT_HOUR/_DAY` único (decisão pendente: 8 ou 3). `pipeline_followthrough` tem teto próprio mais alto. `internal`/`active_conversation`/`warmup` não entram no teto frio.
6. **Quota por conversa também existe:** `MAX_PER_CONVERSATION_DAY` e `MAX_SAME_NATURE_PER_CONVERSATION_DAY` (ex.: no máximo 1 `first_contact` por conversa; 1 `followup_fX`/dia/conversa) — protege contra "mesmo lead recebe por 2 caminhos no mesmo dia".

---

## 7. Plano de migração em fases pequenas

Cada fase: arquivos, teste, validação. Nenhuma toca bridge/chip. Toda fase passa por `scripts/channel_v2_release_gate.sh` + `scripts/channel_v2_safe_deploy.sh stage` antes de qualquer promoção. **Claude Code não promove/deploya sozinho.**

| Fase | Entrega | Arquivos | Teste | Validação | Rollback |
|---|---|---|---|---|---|
| **F0** | Contratos de teste antes do código | `tests/test_whatsapp_message_nature.py`, `tests/test_whatsapp_quota_manager.py` | mapeia cada `nature`→`legacy_status/msg_type/quota_class`; fixtures (bundle 3 partes, follow frio, manual, agenda, interno) | `python3 -m unittest tests.test_whatsapp_message_nature tests.test_whatsapp_quota_manager -v` (espera fail inicial) | apagar testes |
| **F1** | Vocabulário | `scripts/whatsapp_message_nature.py` | testes de F0 passam | `py_compile` + unittest | apagar arquivo (ninguém importa) |
| **F2** | **Ledger único com lock** | `scripts/zydon_operational_queues.py` + delegação em `disparo_dinamico.py`, `process_gate_once.py`, `monitor_diagnostico_agendado.py`, `non_mql_legit_outreach.py` | `tests/test_zydon_operational_queues.py`: 10 threads × 10 appends = 100 sem perda | `py_compile` dos 5 + smoke gate | voltar helpers locais (sem schema change) |
| **F3** | **Router multichip ligado em shadow** | `scripts/whatsapp_routing.py` (já existe) + health feed; um sender lê `choose_outbound_port` e **loga** decisão sem mudar porta | `tests/test_whatsapp_routing.py`: existing-thread, lead novo balanceado, nunca cruza SDR, chip doente pulado | `py_compile` + unittest | desligar leitura do router |
| **F4** | QuotaManager em **shadow** | `scripts/whatsapp_quota_manager.py` + `controle/whatsapp_quota_config.json` (`mode:shadow`) | conta por `logical_message_id`; compara com contagem atual em 1 dia real | unittest + shadow log | flag off |
| **F5** | Envelope opcional na camada segura | `scripts/whatsapp_safe_send.py` (+ `tests/test_whatsapp_safe_send.py`, `test_whatsapp_send_standardization.py`) | callers antigos não quebram; envelope chega no audit | unittest + smoke gate | caller volta à chamada antiga |
| **F6** | Migrar senders seguros: **#7 monitor → #6 agenda → #5 non_mql** | os 3 scripts | por-sender: payload+nature corretos | `py_compile` + unittest + watchdog de loop/duplicata | por-sender revert |
| **F7** | Migrar **#2 cadencia + #1 disparo** (maior volume); router sai de shadow para escolher chip de verdade | `disparo_dinamico.py`, `scripts/cadencia_primeiro_contato.py` | `tests/test_followup_incident_safety.py` + safety gate | manter `parallel-lanes` pausado; safety gate | por-sender revert; router volta a shadow |
| **F8** | Migrar **#3 combo MQL** = 1 logical id; unificar `MAX_COLD_PER_PORT_*` (fim do 8×3) | `scripts/process_gate_once.py` | `tests/test_prospeccao_pdf_msg.py` | unittest + smoke gate | manter constantes antigas em paralelo |
| **F9** | Painel `/api/send` registra `manual_reply` no ledger único, `quota_counted=false` | `scripts/channel_panel_v2.py` | `tests/test_channel_v2_core.py` | release_gate + safe_deploy stage | flag `manual ledger = off` |
| **F10** | `/rotinas` cockpit operável (§9) | `scripts/channel_panel_v2.py` (+ rota/teste) | `tests/test_channel_v2_core.py` (rota + ação) | release_gate + safe_deploy stage | esconder grid atrás de flag |
| **F11** | Quota **enforce** gradual: só `cold_automation` → depois `pipeline_followthrough` (mais permissivo); nunca `manual`/`internal` | `controle/whatsapp_quota_config.json` (`mode:enforce`) | watchdog de duplicidade/queda de envio | monitor de outbound quality | voltar `mode:shadow` |
| **F12** | Limpeza de crons: 1 por jornada; allowlist negativa no watchdog | `/root/.hermes/cron/jobs.json` (decisão Hermes) | guard valida pausados | guard + stall-alert | religar cron específico |

**Primeira entrega recomendada:** F0+F1+F2 (vocabulário + ledger único). Não muda envio nem quota, resolve a parte mais perigosa (ledger sem dono), e prepara o cockpit. Depois F3 (router em shadow) para Rafael ver a decisão de chip antes de ela valer.

---

## 8. Riscos operacionais e como evitar duplicidade/envio errado

| Risco | Como evita |
|---|---|
| **Mesmo lead recebe por 2 caminhos no mesmo dia** (MQL combo + régua F1; Não-MQL remarcado MQL) | Quota por conversa (`MAX_PER_CONVERSATION_DAY`, `MAX_SAME_NATURE_...`) no QuotaManager, além do dedupe destino+payload da camada segura. `thread_state` impede misturar frio com pós-diagnóstico. |
| **Chip de outro SDR usado** | `whatsapp_routing.sdr_ports` filtra por `owner`/`users[uid].ports`; router nunca devolve porta fora do SDR. Teste obrigatório "nunca cruza SDR". |
| **Lead novo cai em chip doente / com QR** | `choose_new_thread_port` recebe `health` e só sorteia entre chips saudáveis; alimentar de `whatsapp_bridge_health_monitor`. Fallback documentado se todos doentes. |
| **Lost update no ledger** (2 crons append simultâneo) | Ledger único `append_wpp_envio_locked` com `flock` (F2). Teste de concorrência 10×10. |
| **Combo MQL estoura limite contando 3** | Conta por `logical_message_id` (F4/F8). |
| **Manual/conversa ativa barrada por quota fria** | `active_conversation`/`internal` nunca consultam teto frio (§6). |
| **Watchdog religa cron que deve ficar pausado** | Allowlist **negativa** no `bottleneck-watchdog` para os 4 `PAUSADO-NAO-REATIVAR` (F12); guard alerta se religar. |
| **Migração quebra envio em produção** | Toda fase é shadow antes de enforce; `mode: off|shadow|enforce`; stage-first obrigatório; rollback por flag por fase. Nunca reiniciar bridge para isso (é fila/ledger/UI). |
| **Privacidade do comunicador** (CLAUDE.md regra 3) | Cockpit só mostra envio operacional registrado no ledger + resposta do lead naquele chat operacional; nunca conversa pessoal de comunicador. |
| **Texto técnico vazando para SDR** (CLAUDE.md regra 7) | `nature/origin/quota_class/logical_message_id` são **filtros e colunas internas** do cockpit; na timeline do SDR a bolha é real (texto/horário/anexo), sem rótulo "ledger/auditoria". |

---

## 9. Redesenho objetivo da `/rotinas`

**Diagnóstico do que existe hoje:** `/rotinas` (acesso só Rafael) é uma **parede de cards** montada por `_rotinas_intelligence_rows`, `_rotinas_centralized_modules`, `_rotinas_journey_rows`, `_rotinas_simplification_rows` — tudo **read-only e resumido** ("Jornada ponta a ponta", "Redundâncias evitadas", "Rastro operacional"). É leitura passiva: não dá para **operar** uma fila, liberar um item, pausar uma conversa. É exatamente o "feio e imaturo" que Rafael apontou.

**Alvo: cockpit em abas, cada aba é um data grid acionável.** Sai a "Visão geral" solta e os cards de auto-elogio ("redundâncias evitadas").

### Módulos que FICAM (viram abas com data grid)
| Aba | Data grid (colunas) | Ações por linha (POST allowlist, Rafael-only, confirmação) |
|---|---|---|
| **Qualificação** | Entrada · Empresa · Origem · Decisão · Motivo · Próxima ação · Responsável | Aprovar MQL · Manter Não-MQL · Pedir pesquisa · Abrir HubSpot · Abrir conversa |
| **Diagnóstico & Agenda** | Lead · Estado · Último envio · Natureza · Agenda · Link · SDR · Próxima ação | Reenviar convite · Enviar lembrete · Marcar sem link · Abrir agenda · Abrir conversa |
| **Follow-ups** | Lead · Fase (F1–F4) · SDR/chip · Natureza · **Quota** · Último envio · Bloqueio · SLA | Liberar próximo tick · Pausar conversa · Reprocessar pesquisa · Bloquear por opt-out · Abrir texto aprovado |
| **Conversas** | Lead · Última resposta · `thread_state` · Natureza sugerida · Dono · Ação sugerida | Abrir conversa · Marcar resolvido · Criar tarefa SDR · Bloquear automação |
| **Sistema** (técnico, recolhido) | Cron · Jornada · Estado · Último tick · Próximo tick · Obrigatório? | Pausar com motivo · Reativar · Rodar dry-run · Ver último log |

### Módulos que SAEM
- Cards "Jornada ponta a ponta", "Trabalhos realizados no dia", "Redundâncias evitadas", "Proatividades", "Rastro operacional" (`_rotinas_intelligence_rows`/`_rotinas_simplification_rows`) → viram, no máximo, **4–6 KPIs** no topo, não cards-parede.
- "Dexter Center / crons e contextos" como aba solta → absorvido na aba **Sistema**.
- Resumos `_rotinas_centralized_modules` (followups/proatividade/agendas) que só repetem contagem → viram os data grids reais acima.

### Layout
- **Topo:** barra de **KPIs que importam** (≤6): _Disparos hoje por classe_ (cold/pipeline/active) · _Follow-ups pendentes vs SLA_ · _Conversas aguardando resposta_ · _Saúde dos chips por SDR_ · _Bloqueios de quota hoje_ · _Agendas para confirmar_.
- **Centro:** abas → data grid com filtro (SDR, chip, natureza, estado) e **ação por linha**.
- **Direita/expand:** drawer da conversa real (bolhas WhatsApp, sem rótulo técnico — CLAUDE.md regra 7).
- Paleta Zydon oficial (Lime `#CDEB00`, Neutral Black, Tech Gray, Light Gray; dark `#06080A`) — CLAUDE.md regra 8.

### Backend
- Read-only primeiro: `GET /api/rotinas/grid/{qualification|diagnostic-agenda|followups|conversations|system}` (lê o **ledger único** + quota + router).
- Depois ação única com allowlist: `POST /api/rotinas/action` `{action, target_type, target_id, reason, confirm:true}`. Teste obrigatório: **nenhum** envio WhatsApp direto sem passar pela allowlist + camada segura.

### KPIs que realmente importam (e os que não)
- **Importam:** quantidade de envio **por classe de quota**, follow-ups dentro/fora de SLA, conversas sem resposta, saúde de chip por SDR, bloqueios de quota, agendas a confirmar.
- **Não importam (sair):** "redundâncias evitadas", "trabalhos realizados no dia" como vaidade, contagem de scripts/watchdogs como métrica de produto.

---

## 10. Critérios de aceite para Rafael (maturidade)

Está maduro quando **todos** forem verdade:

1. **Decisão de chip é central e auditável.** Todo envio passa por `whatsapp_routing.choose_outbound_port`; com 2+ chips por SDR, lead com thread aberta continua no mesmo chip e lead novo distribui entre chips saudáveis do **mesmo** SDR. Existe teste que falha se um envio usar chip de outro SDR.
2. **Envio lógico conta como 1.** Combo diagnóstico (texto+PDF+pergunta) consome **1** da quota, com 3 `parts`. Teste prova `quota_counted` contando `logical_message_id`, não partes.
3. **Conversa ativa e manual não gastam quota fria.** `/api/send` registra `manual_reply`/`active_conversation`, `quota_counted=false`, e aparece no cockpit sem barrar disparo frio.
4. **Limite único por chip.** Não existe mais `8` num arquivo e `3` em outro; há um `MAX_COLD_PER_PORT_*` central + tetos separados por `quota_class`.
5. **Ledger tem dono único.** `wpp_envios.json` só é escrito por `append_wpp_envio_locked`; teste de concorrência (10×10) sem lost update.
6. **Follow-up volta a rodar com controle.** O follow-up pós-diagnóstico está reativado **dentro** do orquestrador (idempotente, com quota), ou aposentado por decisão explícita — não mais "desligado por medo".
7. **Sem duplicidade entre caminhos.** Quota por conversa/dia + por natureza/conversa impede o mesmo lead receber por 2 caminhos no mesmo dia; watchdog de duplicidade fica verde.
8. **`/rotinas` é cockpit operável.** Rafael abre uma aba, vê data grid com `nature/quota/SLA`, e **age na linha** (liberar tick, pausar conversa, reenviar convite) sem ler ledger/log; nenhum texto técnico vaza para o SDR.
9. **Quota observável antes de bloquear.** Modo `shadow` rodou ≥1 dia mostrando o que **teria** bloqueado, e só então virou `enforce` por classe — sem queda de envio real.
10. **Operação intacta.** Tudo validado por `release_gate` + `safe_deploy stage`; nenhuma bridge/chip reiniciada; promoção feita por Hermes, transparente para os SDRs.

---

## Anexo — arquivos lidos e suposições

### Arquivos lidos nesta análise
- `scripts/whatsapp_safe_send.py` (transporte/camada segura — leitura integral).
- `scripts/whatsapp_routing.py` (router multichip — leitura integral; **já existe, não ligado**).
- `scripts/zydon_operational_queues.py` (filas/ledger com lock — leitura integral).
- `scripts/process_gate_once.py` (combo MQL — **507 KB**, não lido integral; usado o mapa da auditoria e a listagem de senders; ver suposição 2).
- `scripts/channel_panel_v2.py` (trechos de `/rotinas`: rotas `APP_ROUTES`, `_rotinas_journey_rows`, `_rotinas_centralized_modules`, `_rotinas_intelligence_rows`, acesso Rafael-only).
- `controle/channel_ports.json` e `controle/channel_users.json` (modelo de chips/SDR; hoje 1 porta por SDR).
- `docs/architecture/whatsapp-cron-centralizer-audit-2026-06-30.md` (auditoria — base factual dos senders, locks, limites 8×3).
- `.hermes/plans/2026-06-30_224711-whatsapp-cron-centralizer.md` (plano de fases — base da taxonomia e migração).
- Listagem de `scripts/*.py` e `/root/.hermes/cron/jobs.json` (apenas tamanho/nomes; **prompts completos de cron não foram lidos**, conforme restrição).

### Não lido (por restrição/escopo)
- `scripts/disparo_dinamico.py` está na **raiz** do projeto (`disparo_dinamico.py`), não em `scripts/`; também existe `disparo_primeiro_contato.py`. Não foram lidos integralmente nesta passada — limites/funções vêm da auditoria.
- `scripts/cadencia_primeiro_contato.py`, `agenda_queue_sender.py`, `monitor_diagnostico_agendado.py`, `non_mql_legit_outreach.py`, `mql_sdr_followup.py`: caracterizados pela auditoria, não relidos linha a linha aqui.
- Prompts completos de cron em `jobs.json` e quaisquer segredos — **não lidos** (restrição explícita).

### Suposições
1. A auditoria `whatsapp-cron-centralizer-audit-2026-06-30.md` está correta sobre os valores divergentes (`MAX_EXTERNAL_PER_PORT_HOUR = 8` em `disparo_dinamico.py` vs `3` em `process_gate_once.py`), os helpers de ledger sem `flock`, e o estado pausado do follow-up pós-diagnóstico. Não revalidei cada linha desses senders nesta passada.
2. `process_gate_once.py` (507 KB) continua enviando o combo MQL via `safe_post_bridge` e gravando em `wpp_envios.json` via `save_wpp`/`append_processed` como descrito na auditoria; assumo que a migração F8 cabe sem reescrever o gate inteiro (só o ponto de envio/ledger).
3. `channel_users.json[uid].ports` é a fonte pretendida dos 2+ chips por SDR quando Rafael conectar os novos chips amanhã; `whatsapp_routing.sdr_ports` já lê isso. Assumo que o cadastro dos novos chips será feito aí (e em `channel_ports.json` com `role=sdr`, `owner=<sdr>`).
4. `whatsapp_bridge_health_monitor.py` pode fornecer o `health{port: {healthy, needsQR}}` que `choose_new_thread_port` espera; não verifiquei o formato exato de saída desse monitor.
5. As decisões pendentes (teto frio 8 ou 3; combo conta 1; reativar ou aposentar follow-up pós-diag; default grupo vs 1:1; números de quota por conversa) são **de Rafael** — o documento recomenda, não decide.

### Restrições honradas
Nenhum código editado. Nenhum `promote`/`deploy` executado. Nenhuma bridge/chip/painel reiniciado. Nenhum prompt completo de cron ou segredo lido. Nenhum WhatsApp enviado.
</content>
</invoke>
