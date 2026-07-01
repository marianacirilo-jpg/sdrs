# Auditoria — Centralização dos crons/envios WhatsApp Zydon

**Data:** 2026-06-30
**Tipo:** READ-ONLY (nenhum código foi editado, nenhum cron/bridge/painel tocado, nenhum WhatsApp enviado)
**Autor:** Claude Code (auditoria a pedido de Rafael)
**Escopo:** mapear todos os caminhos de envio WhatsApp, do diagnóstico até a agenda marcada, e propor um modelo único de natureza/origem + limites corretos + plano de centralizador.

---

## 0. Sumário executivo

O transporte de WhatsApp **já está razoavelmente centralizado** em `scripts/whatsapp_safe_send.py` (todos os caminhos relevantes passam por `safe_post_bridge`/`safe_send_text`, e há teste que obriga isso — `tests/test_whatsapp_send_standardization.py`). O problema **não é mais o transporte**, e sim **3 camadas acima dele que continuam fragmentadas**:

1. **Ledger sem dono único.** O mesmo arquivo `controle/wpp_envios.json` é escrito por **pelo menos 5 helpers de append diferentes**, sendo que **2 dos principais (`registrar_envio` e `save_wpp`) gravam sem `flock` no arquivo** — risco de lost-update entre crons concorrentes.
2. **Limites incoerentes e por "mensagem bruta".** Existem **dois valores divergentes** de `MAX_EXTERNAL_PER_PORT_HOUR` (8 em `disparo_dinamico.py`, 3 em `process_gate_once.py`). Pior: a contagem é por **parte enviada** (texto, PDF e pergunta contam separado) e **por chip**, nunca por **conversa/destinatário/natureza**. Não há distinção entre disparo frio automatizado, follow-up, resposta de agenda e mensagem manual de SDR.
3. **Natureza/origem implícita e espalhada.** Cada caminho inventa seus próprios `status`/`msg_type`/`campaign_id` (ver §2). Não há um vocabulário único; o painel e os limites têm que adivinhar a natureza por substring de string.

A recomendação central (§6) é introduzir **`scripts/whatsapp_message_nature.py`** (vocabulário) + **`scripts/whatsapp_quota_manager.py`** (quotas por conversa/natureza/chip) e fazer **`whatsapp_safe_send.py` exigir um envelope `{nature, origin, thread_state, logical_message_id}`** em todo envio — sem trocar a bridge nem reescrever os senders de uma vez.

---

## 1. Mapa dos crons (jobs.json) relevantes a WhatsApp, por jornada

Fonte: `/root/.hermes/cron/jobs.json` (snapshot 2026-06-30T22:38Z). Estado = `enabled`/`state`.

### 1.1 Entrada / MQL / diagnóstico

| Cron | id | Schedule | Estado | Script/Prompt | Envia WhatsApp ao lead? |
|---|---|---|---|---|---|
| `zydon-prospeccao-autonomo` | fcfbcaf10afa | every 10m | **ATIVO** | agente (skill `zydon-prospeccao`) → `motor/gate.py` + pipeline | **Sim** (combo MQL via pipeline) |
| `zydon-active-mql-qualifier-1min` | 4f26aecc5e27 | every 1m | **ATIVO** | `scripts/active_mql_qualifier.py` | Não (só escreve `mql_pipeline_queue.json`) |
| `zydon-mql-watchdog` | cc80cc27a27f | */5 | **ATIVO** | `zydon_mql_watchdog.sh` | Não (guardião) |
| `zydon-mql-heartbeat-30min` | ec2a7069e022 | */30 | pausado 29/06 | `zydon_mql_heartbeat.sh` | Não |
| `zydon-pending-lead-discord-alert` | cc6c80580fe2 | every 1m | **ATIVO** | `zydon_pending_lead_watchdog.sh` | Não (alerta Discord) |
| `zydon-drive-sync` | 36eb0b73091b | */5 | **ATIVO** | `sync_drive.sh` | Não |

> O envio real do diagnóstico MQL (texto + PDF + pergunta) acontece dentro do pipeline disparado pelo agente `zydon-prospeccao-autonomo`, que importa `scripts/process_gate_once.py`. Não há um cron script-only dedicado "só dispara diagnóstico"; é orquestrado pelo agente.

### 1.2 Agenda / diagnóstico agendado

| Cron | id | Schedule | Estado | Script | Envia? |
|---|---|---|---|---|---|
| `zydon-agenda-queue-sender-1min` | 3a6c93e1c0ae | every 1m | **ATIVO** (auto-resumed) | `zydon_agenda_queue_sender.sh` → `scripts/agenda_queue_sender.py` | **Sim** (frase de agenda pós-respiro 20min) |
| `zydon-diagnostico-agendado-monitor` | f61922cff64e | every 5m | **ATIVO** (auto-resumed) | `zydon_monitor_diagnostico_agendado.sh` → `scripts/monitor_diagnostico_agendado.py` | **Sim** (confirmação + lembrete agenda) |
| `zydon-sdr-premeeting-summary-30min` | f75e09f50657 | every 1m | **ATIVO** | `zydon_sdr_premeeting_summary.py` | Sim (resumo pré-reunião — destino interno SDR) |

### 1.3 Primeiro contato

| Cron | id | Schedule | Estado | Script | Envia? |
|---|---|---|---|---|---|
| `zydon-sdr-followup-unificado-5min` | 3365e74523dc | */5 9-21 1-5 | **ATIVO** (cron único oficial) | `zydon_sdr_followup_unificado_5min_async_launcher.sh` → `disparo_dinamico.py` + `cadencia_primeiro_contato.py` | **Sim** |
| `PAUSADO-NAO-REATIVAR-sdr-primeiro-contato-5min-toda-base` | 25fda16cf15c | */5 9-22 1-5 | **PAUSADO-NAO-REATIVAR** | `zydon_sdr_primeiro_contato_fresh_5min.sh` | (legado) |
| `PAUSADO-NAO-REATIVAR-zydon-lead-sem-contato-primeira-hora` | 94d13a7dcf29 | 0 9 1-5 | **PAUSADO** (last_status error/timeout) | `zydon_lead_sem_contato_primeira_hora.sh` | (legado) |
| `sdr-seguro-hoje-12h-brt` | f405aab9741b | once | desabilitado (one-shot antigo) | `disparo_dinamico.py lucas --limit 2` | (legado manual) |

### 1.4 Follow-up F1–F4

| Cron | id | Schedule | Estado | Script | Envia? |
|---|---|---|---|---|---|
| `zydon-sdr-followup-unificado-5min` | 3365e74523dc | */5 9-21 1-5 | **ATIVO** | (acima) — roda a régua F1/F2/F3/F4 via `cadencia_primeiro_contato.py` | **Sim** |
| `PAUSADO-NAO-REATIVAR-zydon-mql-sdr-followup-5min` | 5f510cd016da | */5 9-22 1-5 | **PAUSADO-NAO-REATIVAR** | `zydon_mql_sdr_followup.sh` → `mql_sdr_followup.py` | (legado; Follow-up 1 pós-diagnóstico) |
| `PAUSADO-NAO-REATIVAR-zydon-cadencia-primeiro-contato-all` | b308e1849c94 | */30 10-22 1-5 | **PAUSADO-NAO-REATIVAR** | `zydon_cadencia_primeiro_contato_all.sh` | (legado; régua completa) |
| `zydon-followup-parallel-lanes-5min` | 958f9438cdfe | every 5m | **PAUSADO** 30/06 | `zydon_followup_parallel_lanes_launcher.sh` | (lanes paralelas por chip — desligado) |
| `zydon-sdr-followup-queue-snapshot` | c333fc9e6736 | every 15m | **ATIVO** | `..._queue_status_snapshot.sh` → `sdr_followup_queue_status.py` | Não (snapshot/SLA) |
| `zydon-claude-nextday-followup-research` | e87ae4779935 | 30 23 1-5 | **ATIVO** | `zydon_prepare_nextday_followups_claude.sh` | Não (pesquisa, escreve docs) |
| `zydon-claude-nextday-followup-monitor` | 60ab2496c35b | every 10m | **ATIVO** | `..._claude_monitor.sh` | Não |
| `zydon-relatorio-diario-follows-18h` | 0f123d45330a | 0 21 | **ATIVO** | agente relatório | Não |

> **Observação crítica:** o `mql_sdr_followup.py` (Follow-up 1 pós-diagnóstico) está com o cron **PAUSADO-NAO-REATIVAR**, mas o **wrapper `zydon_mql_sdr_followup.sh` ainda existe e é funcional**, e o guard (`zydon_sdr_followup_unificado_guard.sh`) explicitamente espera que ele **continue pausado**. O Follow-up 1 pós-diagnóstico hoje está **descoberto** no fluxo unificado: o passo "2) Pós-diagnóstico vira Follow-up 1" foi **comentado** no `zydon_sdr_followup_unificado_5min.sh` (linhas 68–72, "PAUSA DE SEGURANÇA 30/06").

### 1.5 Não-MQL

| Cron | id | Schedule | Estado | Script | Envia? |
|---|---|---|---|---|---|
| `zydon-nao-mql-tratativa-legitima-10min` | 26d955a3c406 | */10 0,10-23 | **ATIVO** | `zydon_non_mql_legit_backfill.sh` → `non_mql_legit_outreach.py` | **Sim** (1 pergunta ao lead, comunicadores 4606/4600/4607) |

### 1.6 Respostas / conversas (escuta, não envia)

| Cron | id | Schedule | Estado | Script | Envia? |
|---|---|---|---|---|---|
| `zydon-cinco-primeiras-etapas-escuta-respostas` | 530b046d4297 | every 1m | **ATIVO** | `zydon_incoming_response_alert_1min.sh` | Não (escuta + alerta Discord; **único tópico que "conversa"**) |
| `zydon-outgoing-send-alert` | 225cf584ab53 | every 1m | pausado 28/06 | `zydon_outgoing_send_alert.py` | Não |
| `zydon-aprendizado-diario-personalidades-chips` | 4249beb5a37a | 0 20 | **ATIVO** | agente (skill) | Não (aprende, não envia) |

### 1.7 Monitores / guardiões

| Cron | id | Schedule | Estado | Script |
|---|---|---|---|---|
| `zydon-sdr-followup-unificado-guard` | a9fd68e7932c | every 5m | **ATIVO** | `zydon_sdr_followup_unificado_guard.sh` |
| `zydon-followup-loop-audit-watchdog` | 23c83da09ce6 | every 5m | **ATIVO** | `zydon_followup_loop_audit_watchdog.sh` |
| `zydon-sdr-followup-stall-alert` | f8625910b70f | every 5m | **ATIVO** | `zydon_sdr_followup_stall_alert.sh` |
| `zydon-whatsapp-outbound-quality-monitor` | 64665fd07a2f | every 5m | **ATIVO** | `whatsapp_outbound_quality_monitor.py` |
| `zydon-whatsapp-bridge-health-monitor` | 7fe6a9b3130e | every 5m | **ATIVO** | `whatsapp_bridge_health_monitor.py` |
| `zydon-cron-processing-bottleneck-watchdog` | 26afdce18ede | every 10m | **ATIVO** | `..._bottleneck_watchdog.py` (faz **auto-resume** de crons!) |
| `zydon-funnel-audit-alert-08-12-16-brt` | a76f905d0db8 | 0 11,15,19 | **ATIVO** | `zydon_funnel_audit_alert.py` |
| `zydon-channel-v2-performance-watchdog` | 88580c915115 | every 10m | **ATIVO** | `zydon_channel_v2_performance_watchdog.py` |
| `zydon-channel-watchdog` / `...-8280-watchdog` / `...-security-heartbeat` / `...-autofix-monitor` / `roteiro-8290` / `envios-dashboard` | vários | 2–15m | **ATIVOS** | infra (painel/bridges/tunnels) |
| `zydon-whatsapp-warmup-manha/tarde` | 8e029574ba6e / cf572920eadd | 30 12 / 30 20 | **ATIVOS** | `zydon_whatsapp_warmup.py` (envia interno entre chips) |

> ⚠️ **`zydon-cron-processing-bottleneck-watchdog` reativa crons sozinho** (`auto_resumed_by` aparece em agenda-queue, monitor-agendado, unificado, guard, snapshot, quality, bridge-health, stall-alert, loop-audit). Isso significa que pausar um desses crons **não é estável**: o watchdog pode religá-lo. Decisão de produto necessária (§8).

---

## 2. Mapa dos caminhos reais de envio WhatsApp

Todos os caminhos abaixo terminam em `scripts/whatsapp_safe_send.py::safe_post_bridge` (POST `http://127.0.0.1:{port}/send` ou `/send-file` via `urllib`, linha 408), que aplica: normalização de JID/PN, bloqueio de `@lid` sem telefone, dedupe por destino+payload (janela 3600s), `GLOBAL_TRANSPORT_LOCK` + lock por destino+payload, auditoria em `controle/channel_outbound_audit.jsonl` e reconciliação contra `history_<port>.json`.

| # | Script / função principal | Usa `whatsapp_safe_send`? | Ledger onde grava | status / msg_type / campaign_id | Limites que aplica |
|---|---|---|---|---|---|
| 1 | `disparo_dinamico.py` · `send_whatsapp_sequence` → `send_whatsapp` (L1093) → `safe_send_text` | **Sim** | `controle/wpp_envios.json` via `registrar_envio` (L130, **sem flock no arquivo**) | `msg_type='primeiro_contato'`, `campaign_id='lead_sem_contato_follow1'`, sem `status` (só `text_status='ok'`) | `MAX_EXTERNAL_PER_PORT_HOUR=8`, `_DAY=30` (L83-84); por **chip**, por **mensagem bruta** |
| 2 | `cadencia_primeiro_contato.py` (F1–F4) · chama `d.send_whatsapp_sequence` (L1695) | **Sim** (via #1) | `wpp_envios.json` via `d.registrar_envio` | `msg_type='primeiro_contato_cadencia'`, `campaign_id='cadencia_primeiro_contato_sem_resposta'`, `attempt_number=1..4` | `--max-per-hour=3` (SDR), `--max-per-port-hour=d.MAX...=8`, `--max-per-port-day=30`; lock por lead `/tmp/zydon_followup_lead_locks/` |
| 3 | `process_gate_once.py` (combo MQL) · `post_bridge` / `post_bridge_with_retries[_locked]` (L3242/3251/4142) → `safe_post_bridge` | **Sim** | `wpp_envios.json` via `save_wpp`/`append_processed` (L2659/2291, **sem flock no arquivo**) | `status` ∈ {`mql_diagnostico_em_andamento`, `enviado_lead`, `nao_mql_grupo`, `mql_telefone_invalido_grupo`, `mql_bloqueado_sem_sdr_dono`}; **sem `campaign_id`** | `MAX_EXTERNAL_PER_PORT_HOUR=3`, `_DAY=30` (L2622-23) — **diverge do #1** |
| 4 | `mql_sdr_followup.py` (Follow-up 1 pós-diag, **cron pausado**) · `d.send_whatsapp_sequence` (L660) | **Sim** (via #1) | `wpp_envios.json` via `d.registrar_envio` | `msg_type='mql_followup1_deterministico'`, `status='enviado_followup_mql'`, sem `campaign_id` | `--max-per-hour=2`, `--max-per-day=12`, `--max-age-hours=48` |
| 5 | `non_mql_legit_outreach.py` · `post_bridge_short` → `safe_post_bridge` (L431) | **Sim** | `wpp_envios.json` via `p.save_wpp` (process_gate) | `status='enviado_nao_mql_legitimo'`, `campaign_id='nao_mql_legitimo_tratativa'`, `msg_type='nao_mql_legitimo_tratativa'` | `p.MAX_EXTERNAL_PER_PORT_HOUR=3`/`_DAY=30`; janela fixa 07–22h; comunicadores 4606/4600/4607 |
| 6 | `agenda_queue_sender.py` (agenda pós-respiro) · `pg.post_bridge_with_retries_locked` (L106) | **Sim** (via #3) | `wpp_envios.json` via `zydon_operational_queues.append_wpp_envio` (**com flock**) + `agenda_queue.json` | `status='mql_agenda_sdr_apos_diagnostico'` e `'agenda_followup_done'`; sem `msg_type`/`campaign_id` | lock `/tmp/zydon_agenda_queue.lock` + lock por arquivo (queue_locks) |
| 7 | `monitor_diagnostico_agendado.py` · `safe_send_text` (L385) | **Sim** | `wpp_envios.json` via **`append_wpp_envio` próprio** (L461) + `diagnostico_agendado_processed.json` | `campaign_id='diagnostico_agendado'`, `msg_type` ∈ {`diagnostico_agenda_confirmacao`, `diagnostico_agenda_lembrete_dia`, `diagnostico_agenda_aviso_grupo[_lote]`}, `status` ∈ {`enviado_lead`,`enviado_grupo`} | `--max-sends=2`/tick; lock `controle/runtime/diagnostico_agendado_monitor.lock` |
| 8 | `active_mql_qualifier.py` · **não envia** | — | `mql_pipeline_queue.json` via `update_json_locked` | states internos (`mql_candidate_needs_main_pipeline`, `pending_review`, `classified_non_mql_hint`) | lock `/tmp/zydon_active_mql_qualifier.lock` |
| 9 | Painel V2 `channel_panel_v2.py` · `/api/send`, `/api/start-conversation` → `post_json` direto à bridge | **Parcial** (posta direto; grava audit `channel_outbound_audit.jsonl`) | `channel_outbound_audit.jsonl` (não `wpp_envios.json`) | envio manual SDR/Rafael — **sem `nature` registrada**, sem quota | dedupe `recently_sent_same_text`; **sem limite de quota** |
| 10 | Scripts `manual_*.py`, `sumico_inicio_funil.py`, `process_pending_cycle_*.py`, `send_backlog_*` | maioria **Sim** (via `safe_*`/`pg.post_bridge`) | `wpp_envios.json` (vários helpers) | `status`/`msg_type` ad-hoc por script | usam limites do módulo importado |

**Portas/chips (consistente entre os caminhos):**
- **SDR donos:** 4601 Sarah · 4603 Lucas Batista · 4605 Breno (4602/4604 desativados).
- **Comunicadores institucionais:** 4600 Mariana · 4606 Lucas Resende · 4607 Rafael · 4609 João Pedro · 4610 Gustavo.
- **Grupo/notificação interna:** legacy `120363408131718880@g.us`; pipeline MQL hoje notifica **1:1** (Mariana `553484255965@s.whatsapp.net`, rodízio 4607/4600).

---

## 3. Conflitos arquiteturais encontrados

### 3.1 Múltiplos helpers de append no MESMO ledger (`wpp_envios.json`)
Cinco caminhos de escrita coexistem:
1. `disparo_dinamico.registrar_envio` (read-modify-write, **sem flock no arquivo**) — usado por #1, #2, #4.
2. `process_gate_once.save_wpp`/`append_processed` (**sem flock no arquivo**) — usado por #3, #5, manuais.
3. `zydon_operational_queues.append_wpp_envio` (**com flock** via `update_json_locked`) — usado por #6.
4. `monitor_diagnostico_agendado.append_wpp_envio` (**helper próprio**, L461) — usado por #7.
5. Painel grava em `channel_outbound_audit.jsonl` (ledger paralelo), não em `wpp_envios.json`.

**Risco real:** dois crons que disparam ao mesmo tempo (ex.: unificado + agenda-queue-sender, ambos a cada 1–5min) podem fazer read-modify-write concorrente em `wpp_envios.json` sem lock de arquivo → **lost update** (um envio some do ledger). O `GLOBAL_SEND_LOCK`/`GLOBAL_TRANSPORT_LOCK` serializa o **transporte**, mas **não** a escrita do JSON do ledger nesses dois helpers principais.

### 3.2 Múltiplos locks, com semânticas diferentes
| Lock | Onde | Função |
|---|---|---|
| `/tmp/zydon_external_whatsapp_send.lock` | disparo, cadencia, process_gate, non_mql, wrapper mql_sdr_followup | semáforo global de envio (serializa crons) |
| `controle/runtime/whatsapp_global_transport.lock` | whatsapp_safe_send | semáforo de transporte (camada segura) |
| `controle/runtime/whatsapp_send_locks/<hash>.lock` | whatsapp_safe_send | idempotência por destino+payload |
| `/tmp/zydon_followup_lead_locks/<hash>.lock` | cadencia | 1 envio por telefone entre lanes |
| `controle/runtime/queue_locks/*.lock` | zydon_operational_queues | lock por arquivo de fila |
| `/tmp/zydon_agenda_queue*.lock`, `/tmp/zydon_active_mql_qualifier*.lock`, `/tmp/zydon_mql_sdr_followup.lock`, `/tmp/zydon_sdr_followup_unificado.lock`, `controle/runtime/diagnostico_agendado_monitor.lock` | wrappers/scripts | exclusão por cron |

São **dois semáforos globais distintos** (`...send.lock` no nível dos crons e `...transport.lock` na camada segura) que protegem janelas parcialmente sobrepostas, mais N locks por wrapper. Funciona, mas ninguém tem o mapa — e o ledger (§3.1) escapa de todos.

### 3.3 Limites por mensagem bruta × por conversa/natureza/destinatário
- **Dois valores divergentes** de `MAX_EXTERNAL_PER_PORT_HOUR`: **8** (`disparo_dinamico.py:83`) vs **3** (`process_gate_once.py:2622`). Como `cadencia` importa o `d.` (8) e `non_mql` importa o `p.` (3), o **mesmo chip** tem teto/hora diferente conforme o caminho que dispara.
- Contagem é **por parte/split**: no combo MQL, texto + PDF + pergunta contam como **3 envios** contra o teto do chip (`is_direct_external_envio` conta cada `/send` e `/send-file`). Um único "envio lógico" consome 3 do orçamento.
- Contagem é **por chip**, nunca **por conversa/destinatário/dia**. Não há proteção "este lead não pode receber de 2 caminhos diferentes hoje".
- **Mensagem manual** (painel `/api/send`) e **resposta em conversa ativa** **não entram em quota nenhuma** e não distinguem natureza — exatamente o que Rafael apontou.

### 3.4 Crons antigos que devem permanecer `PAUSADO-NAO-REATIVAR`
`sdr-primeiro-contato-5min-toda-base` (25fda16cf15c), `zydon-mql-sdr-followup-5min` (5f510cd016da), `zydon-cadencia-primeiro-contato-all` (b308e1849c94), `zydon-lead-sem-contato-primeira-hora` (94d13a7dcf29). O guard valida que continuem pausados. **Mas** o `bottleneck-watchdog` faz auto-resume de outros crons — confirmar que ele **nunca** religa estes quatro (o guard alerta, mas só depois do fato).

### 3.5 Risco de mesma pessoa receber por caminhos diferentes
Cenários concretos:
- Lead vira MQL → recebe combo (#3) **e** ainda está elegível na régua de Primeiro Contato (#2) se o ledger/etapa não sincronizar a tempo.
- Lead Não-MQL (#5) que depois é remarcado MQL: `already_sent` bloqueia por status posterior, mas a janela entre escrita não-travada do ledger (§3.1) pode deixar passar.
- Follow-up 1 pós-diagnóstico (#4, hoje pausado/comentado) vs régua F1 (#2): ambos gravam em `primeiro_contato*`/`mql_followup1*` e usam dedupe diferente.
O dedupe forte hoje é **por destino+payload na camada segura (3600s)** + **por telefone/deal no ledger** — protege repetição idêntica, mas **não** "naturezas diferentes para o mesmo lead no mesmo dia".

---

## 4. Proposta de modelo único de natureza/origem de mensagem

Introduzir um **envelope obrigatório** em todo envio, com 3 eixos. Nenhuma string solta nova: estes substituem `status`/`msg_type`/`campaign_id` ad-hoc (que viram derivados).

### 4.1 `nature` (o que a mensagem É)
| `nature` | Origem hoje (de→para) |
|---|---|
| `manual_reply` | painel `/api/send` em conversa ativa |
| `diagnostic_initial` | process_gate texto inicial (`enviado_lead` 1ª bolha) |
| `diagnostic_pdf` | process_gate `/send-file` |
| `diagnostic_question` | process_gate pergunta "Como você imagina…" |
| `diagnostic_agenda_invite` | agenda pós-respiro (`mql_agenda_sdr_apos_diagnostico`) |
| `agenda_confirmation` | monitor (`diagnostico_agenda_confirmacao`) |
| `agenda_reminder` | monitor (`diagnostico_agenda_lembrete_dia`) |
| `first_contact` | disparo_dinamico (`primeiro_contato`) |
| `followup_f1..f4` | cadencia (`primeiro_contato_cadencia` + `attempt_number`) |
| `followup_f1_postdiag` | mql_sdr_followup (`mql_followup1_deterministico`) |
| `non_mql_outreach` | non_mql (`nao_mql_legitimo_tratativa`) |
| `no_show_recovery` | (a definir — hoje inexistente) |
| `internal_group_alert` | nao_mql_grupo / aviso 1:1 Mariana |
| `system_monitor` | premeeting summary / health |
| `warmup` | zydon_whatsapp_warmup |
| `premeeting_summary` | premeeting (interno SDR) |

### 4.2 `origin` (QUEM disparou)
`manual_channel` (painel) · `cron_active_mql` · `cron_diagnostic_pipeline` (process_gate via agente) · `cron_followup_unificado` · `cron_followup_postdiag` (pausado) · `cron_agenda_queue` · `cron_agenda_monitor` · `cron_non_mql` · `cron_incoming_response` (só escuta) · `cron_warmup` · `user_manual_script` (manual_*.py) · `watchdog`.

### 4.3 `thread_state` (estado da CONVERSA, não da mensagem)
`cold_outreach` · `active_conversation` · `post_diagnostic` · `scheduled_meeting` · `no_show` · `opt_out` · `internal_only`.

> `thread_state` é a chave que falta hoje: é o que permite tratar **conversa ativa ≠ disparo frio** nos limites (§5). Deriva de: último incoming do lead, etapa HubSpot, presença de diagnóstico/agenda no ledger.

### 4.4 Identidade lógica
Adicionar `logical_message_id` (1 por **envio lógico**, mesmo que vire 3 bolhas) e `conversation_id` (canonical JID/telefone). Combo MQL = **1** `logical_message_id` com 3 partes (`diagnostic_initial`+`diagnostic_pdf`+`diagnostic_question`).

---

## 5. Proposta de limite correto

Princípio: **quota por (conversa, natureza-classe, chip, dia)**, não por parte bruta.

### 5.1 Separar classes de quota
| Classe de quota | Inclui `nature` | Por que separar |
|---|---|---|
| `cold_automation` | first_contact, followup_f1..f4, non_mql_outreach | é prospecção fria automatizada — alvo dos limites anti-bloqueio |
| `pipeline_followthrough` | diagnostic_*, agenda_*, followup_f1_postdiag | consequência de MQL/agenda confirmada; não é frio, mas conta para saúde do chip |
| `active_conversation` | manual_reply, e qualquer envio quando `thread_state=active_conversation` | **não** deve consumir quota de prospecção fria |
| `internal` | internal_group_alert, system_monitor, warmup, premeeting_summary | não conta para limite anti-spam de lead |

### 5.2 Regras
1. **`active_conversation` e `manual_reply` não contam** no teto `cold_automation`. Mensagem manual de SDR/Rafael nunca cai na mesma categoria de disparo frio.
2. **Contar por `logical_message_id`**, não por parte. Combo MQL = 1 contra a quota, não 3.
3. **Quota por destinatário/conversa/dia**: além de `por chip/hora` e `por chip/dia`, adicionar `por conversa/dia` e `por conversa/natureza` (ex.: no máximo 1 `first_contact` por conversa, 1 `followup_fX` por dia por conversa).
4. **Unificar o teto por chip**: um único `MAX_COLD_PER_PORT_HOUR`/`_DAY` (decisão Rafael: 8 ou 3?), eliminando a divergência 8×3.
5. **Distinguir split de envio único** já no envelope (`parts[]` dentro de 1 `logical_message_id`).

---

## 6. Plano de centralizador (onde e como, especificamente)

A base boa (`whatsapp_safe_send.py`) **fica**. Adicionamos duas peças e um envelope, sem trocar bridge nem reescrever senders de uma vez.

### 6.1 Novos módulos
**`scripts/whatsapp_message_nature.py`** — vocabulário único.
- `Nature`, `Origin`, `ThreadState` (enums/constantes) = §4.
- `derive_thread_state(conversation_id, ledger, hubspot_stage) -> ThreadState`.
- `legacy_status_for(nature)` / `legacy_msg_type_for(nature)` — gera os `status`/`msg_type`/`campaign_id` antigos para **compatibilidade** do painel e dos dedupes existentes (nada quebra).

**`scripts/whatsapp_quota_manager.py`** — quota por classe/conversa/chip/dia.
- `quota_class_for(nature, thread_state) -> QuotaClass` (§5.1).
- `check_and_reserve(conversation_id, port, nature, thread_state) -> (ok, reason)` — lê `wpp_envios.json` + `channel_outbound_audit.jsonl`, conta por `logical_message_id`, aplica regras §5.2, sob o **lock de ledger único** (abaixo).
- Constantes únicas `MAX_COLD_PER_PORT_HOUR/_DAY`, `MAX_PER_CONVERSATION_DAY`, etc. (remove as duplicadas 8×3).

### 6.2 Extensão da camada segura (ponto único de entrada)
Estender `whatsapp_safe_send.safe_post_bridge` para aceitar um envelope:
```
safe_send(port, jid, *, nature, origin, thread_state=None,
          logical_message_id=None, payload, uid, conversation_id=None)
```
- Se `thread_state is None`, deriva via `whatsapp_message_nature`.
- Antes do transporte: chama `whatsapp_quota_manager.check_and_reserve`. Se a classe for `active_conversation`/`internal`, **não** consome quota de cold.
- Grava ledger por **um único helper** `append_wpp_envio_locked` (mover o `update_json_locked` do `zydon_operational_queues` para ser **o** caminho; `registrar_envio`, `save_wpp`, o helper do monitor e o do non_mql passam a delegar a ele). Resolve §3.1.
- Mantém audit/reconciliação atuais. `record_outbound_audit` ganha `nature/origin/thread_state/logical_message_id`.

### 6.3 Migração dos senders para um `enqueue/send_request` único
Cada sender troca sua chamada de envio por:
```
from whatsapp_send_orchestrator import send_request
send_request(SendRequest(
    conversation_id=jid, port=port, parts=[...],
    nature=Nature.first_contact, origin=Origin.cron_followup_unificado))
```
`scripts/whatsapp_send_orchestrator.py` = fachada fina que monta `logical_message_id`, faz o split (move `split_whatsapp_text`/`send_whatsapp_sequence` para cá), chama `safe_send` por parte e devolve 1 registro lógico. Os senders param de conhecer split, ledger e quota.

Ordem de migração (cada um é um PR pequeno, testável): **#7 monitor → #6 agenda → #5 non_mql → #2 cadencia → #1 disparo → #3 process_gate → #9 painel**.

### 6.4 UI `/rotinas` como cockpit de filas
Hoje `/api/rotinas/summary` (linha ~14069) e `/api/dispatch-stats` (~14036) são **read-only**; `/api/agendas` (~14042) lê `wpp_envios.json`+`agenda_queue.json`; as únicas POST que mexem em fila são config (`/api/rotinas/config`, `/api/proatividade-config`) e envio manual (`/api/send`, `/api/start-conversation`).
Proposta: transformar `/rotinas` em **data grid operável** das filas (`wpp_envios`, `agenda_queue`, `mql_pipeline_queue`, `mql_execution_queue`), com colunas `nature/origin/thread_state/quota_class/logical_message_id/status` e **action buttons** (POST autenticado Rafael-only): *pausar fila*, *reprocessar item*, *bloquear conversa (opt_out)*, *liberar item*. Mantém a regra do CLAUDE.md: nada de rótulo "auditoria/ledger" visível; mostrar como operação real.

---

## 7. Plano de migração em fases pequenas

| Fase | Entrega | Teste | Rollback |
|---|---|---|---|
| **F0** | Criar `whatsapp_message_nature.py` (só vocabulário + `legacy_*`), sem ligar a nada | `tests/test_message_nature.py` (mapeia cada nature→status/msg_type legado) | apagar arquivo (ninguém importa) |
| **F1** | Unificar **append do ledger**: um `append_wpp_envio_locked`; `registrar_envio`/`save_wpp`/monitor/non_mql delegam | unittest concorrência (2 writers, sem lost update) + smoke gate existente | reverter para helpers antigos (sem schema change) |
| **F2** | `whatsapp_quota_manager.py` em **shadow mode** (loga decisão, não bloqueia) | comparar com contagem atual em 1 dia de dados reais | flag off |
| **F3** | Estender `safe_send` com envelope opcional; **1 sender** (#7 monitor) migra | smoke gate + `test_whatsapp_send_standardization` | sender volta à chamada antiga |
| **F4** | Migrar #6, #5, #2 (cada um 1 PR); quota sai de shadow para **enforce** só em `cold_automation` | por-sender unittest + watchdog de loop/duplicata | por-sender revert; quota volta a shadow |
| **F5** | Migrar #1, #3 (combo MQL = 1 logical id); unificar `MAX_COLD_PER_PORT_*` | `tests/test_prospeccao_pdf_msg.py` + smoke gate | manter constantes antigas em paralelo até validar |
| **F6** | `/rotinas` cockpit operável (data grid + actions) | `tests/test_channel_v2_core.py` (rota + ação) | esconder grid atrás de flag |

Cada fase passa por `scripts/channel_v2_release_gate.sh` + `scripts/channel_v2_safe_deploy.sh stage` antes de qualquer promoção (CLAUDE.md regra 5). Claude Code **não** promove sozinho.

---

## 8. Perguntas abertas / decisões que precisam do Rafael

1. **Teto único por chip/hora:** unificar `MAX_EXTERNAL_PER_PORT_HOUR` em **8** (disparo) ou **3** (process_gate)? Hoje o mesmo chip tem dois tetos conforme o caminho.
2. **Combo MQL conta como 1 ou 3** contra o limite do chip? (Proposta: 1 envio lógico.)
3. **`bottleneck-watchdog` auto-resume:** ele pode religar crons. Confirmar lista do que ele **nunca** pode religar (os 4 `PAUSADO-NAO-REATIVAR`) e se ele deve respeitar uma quota/flag central.
4. **Follow-up 1 pós-diagnóstico (`mql_sdr_followup.py`)** está pausado e o passo foi comentado no unificado (30/06). Reabilitar dentro do orquestrador (assíncrono/idempotente) ou aposentar de vez?
5. **Mensagem manual do painel (`/api/send`)** deve registrar `nature=manual_reply` no `wpp_envios.json` (hoje só vai para `channel_outbound_audit.jsonl`)? Isso é o que permite o cockpit `/rotinas` ver tudo num lugar.
6. **Quota por conversa/dia:** qual o número? (ex.: máx 1 first_contact + 1 followup por conversa por dia; combo MQL ilimitado por ser pipeline?)
7. **`no_show_recovery`**: existe jornada hoje? Não encontrei sender dedicado; criar `nature` reservada agora ou depois?
8. **Grupo vs 1:1:** consolidar todo aviso interno em uma `nature=internal_group_alert` com destino configurável (grupo `120363408131718880@g.us` **ou** 1:1 Mariana/Rafael), já que process_gate migrou para 1:1 mas o monitor ainda manda `@g.us`?

---

### Anexo — arquivos lidos nesta auditoria
`scripts/whatsapp_safe_send.py`, `scripts/zydon_operational_queues.py`, `disparo_dinamico.py`, `disparo_primeiro_contato.py`, `scripts/cadencia_primeiro_contato.py`, `scripts/mql_sdr_followup.py`, `scripts/process_gate_once.py`, `scripts/agenda_queue_sender.py`, `scripts/active_mql_qualifier.py`, `scripts/non_mql_legit_outreach.py`, `scripts/monitor_diagnostico_agendado.py`, `scripts/channel_panel_v2.py` (rotas), `/root/.hermes/cron/jobs.json`, e os wrappers `/root/.hermes/scripts/zydon_*`. Confirmações pontuais por `grep` (constantes de limite, locks de ledger).
