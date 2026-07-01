# Channel V2 — Plano de Garantia Operacional da Máquina de Vendas

> **For Hermes:** Use este plano como gate antes de novas features estruturais no Channel/Foco/Gestão SDR. Tudo deve ser stage-first, testado e observável.

**Goal:** Tornar `sdrs.zydon.com.br` uma máquina de vendas confiável, rápida, segura, escalável e auditável, sem falha silenciosa e sem poluir operação SDR.

**Architecture:** O Channel V2 continua read-heavy, stage-first e cache/snapshot-first. A camada operacional deve separar execução SDR, gestão/orquestração, automações e watchdogs. Qualquer mutação em WhatsApp/HubSpot precisa ter idempotência, limites, evidência, rollback/pausa e observabilidade.

**Tech Stack:** Python stdlib server (`scripts/channel_panel_v2.py`), testes `unittest`, safe deploy scripts, crons Hermes, HubSpot API, bridge WhatsApp local, ledger `controle/wpp_envios.json`, histories `history_*.json`.

---

## Princípios não negociáveis

1. **Alta disponibilidade percebida:** usuário nunca fica preso em `Carregando...`; sempre há snapshot, erro recuperável ou retry.
2. **Sem falha silenciosa:** toda falha real precisa ser detectada, classificada e roteada para alerta correto.
3. **Privacidade máxima:** comunicador só mostra conversa operacional vinculada; nada de espelho WhatsApp pessoal.
4. **Read-only por padrão:** dashboards de gestão e higiene só analisam; não fecham/excluem/enviam sem fluxo explícito de aprovação.
5. **Escala por cache/snapshot:** endpoints pesados nunca podem bloquear primeira tela quando há snapshot aceitável.
6. **Idempotência em envio:** nenhum lead recebe duplicado por retry, corrida, cron paralelo ou reinício.
7. **Stage-first:** produção só recebe release validada em `8891`, com promoção única e rollback automático.
8. **Qualidade comercial:** não basta enviar; medir resposta, agenda, reunião realizada, gargalo e exemplo real.
9. **Controle de demanda:** quando volume subir, degradar com fila/backpressure, nunca travar painel ou duplicar ação.
10. **Evidência:** toda decisão do Dexter/Gestão precisa ter fonte operacional verificável e link.

---

## Estado vivo verificado em 2026-06-29 22:37 UTC

Produção pública saudável:

- `/health`: p50 305ms
- `/foco`: p50 127ms
- `/gestao`: p50 158ms
- `/api/conversations`: p50 315ms, 686 conversas
- `/api/sdr-orchestrator-summary`: p50 2052ms, 3 SDRs, 4 intervenções, 6 abordagens
- `/api/task-hygiene-preview`: p50 522ms, `mutates=false`, 539 candidatas a fechar com aprovação
- `/api/dispatch-stats`: p50 384ms
- Watchdog manual: exit 0

Crons críticos vistos OK:

- `zydon-channel-v2-performance-watchdog`: OK
- `zydon-channel-v2-security-heartbeat`: OK
- `zydon-channel-8280-watchdog`: OK
- `zydon-sdr-followup-unificado-5min`: OK
- `zydon-sdr-followup-unificado-guard`: agendado
- crons antigos separados de primeiro contato/follow/cadência: pausados e marcados `PAUSADO-NAO-REATIVAR`

---

## SLOs mínimos

### Painel público

- `/health`: p95 < 500ms
- `/conversas`: p95 < 1.5s
- `/api/conversations`: p95 < 1.5s em cache quente; p95 < 5s em refresh manual `force=1`
- `/api/messages`: p95 < 1.5s para conversas institucionais comuns
- `/foco`: p95 < 1.5s
- `/api/sdr-orchestrator-summary`: p95 < 2.5s com snapshot/cache; nunca recompute HubSpot frio no primeiro request se snapshot existir
- `/api/dispatch-stats`: p95 < 2s

### Operação SDR/WhatsApp

- Nenhum envio duplicado por lead/chat/template/dia.
- Toda resposta de lead operacional precisa aparecer em `/conversas` e/ou alerta correto em até 2 minutos.
- Cadência deve respeitar limite por chip e janela comercial.
- Opt-out, agressivo, humano já assumiu e lead inseguro bloqueiam automação.
- Crons de envio precisam ser idempotentes e concorrência-safe.

### Segurança/privacidade

- Comunicadores: zero exposição de chat pessoal sem ledger/origem operacional.
- Auth: só `@zydon.com.br` e escopo de usuário/porta correto.
- Sem secrets em logs, bundles Claude, docs ou mensagens Discord.
- Qualquer limpeza/fechamento de tarefa é preview + aprovação explícita.

---

## Fase 1 — Observabilidade e incident response

### Task 1: Painel interno de saúde operacional

**Objective:** Criar bloco/API read-only que consolide saúde de endpoints, crons, snapshots, caches e última promoção.

**Files:**
- Modify: `scripts/channel_panel_v2.py`
- Test: `tests/test_channel_v2_core.py`

**Acceptance:**
- API `/api/ops-health-summary` read-only.
- Mostra: release ativa, pid/cwd público, idade de snapshots, últimos status dos watchdogs conhecidos, latência recente se disponível.
- Não chama WhatsApp bridge pesado nem HubSpot no request.
- Teste garante ausência de mutação e termos técnicos invisíveis para SDR.

### Task 2: Matriz de alertas classificados

**Objective:** Separar alerta de painel, HubSpot, WhatsApp bridge, cron de envio, segurança e webview/cache.

**Acceptance:**
- Watchdog entrega mensagem com categoria: `painel`, `performance`, `privacidade`, `envio`, `hubspot`, `cron`, `webview provável`.
- Alertas sem ação humana não spamam Discord.
- Provider/Hermes timeout não vira outage do Channel.

---

## Fase 2 — Escala/performance

### Task 3: Budget de custo por endpoint

**Objective:** Impedir regressão de endpoint que chama recompute pesado por acidente.

**Acceptance:**
- Testes estruturais para garantir que Gestão SDR usa `_orch_pipeline_focus_for_summary()`, não `pipeline_focus()` direto.
- Testes para `/api/hubspot`, `/api/messages`, `/api/conversations`, `/api/sdr-orchestrator-summary` não chamarem loops globais desnecessários.
- Smoke gate mede pelo menos 2 conversas institucionais e 1 endpoint de gestão.

### Task 4: Singleflight/backpressure geral

**Objective:** Coalescer requests concorrentes de endpoints caros e evitar tempestade após restart.

**Acceptance:**
- Um recompute por chave por vez.
- Requests simultâneos recebem snapshot stale ou aguardam limite curto.
- Teste com threads provando que só há um cálculo pesado.

### Task 5: Snapshot de Gestão SDR separado

**Objective:** Persistir resumo de orquestração para abrir sempre rápido mesmo se `dispatch_stats` ou pipeline estiverem frios.

**Acceptance:**
- Arquivo `controle/channel_sdr_orchestrator_snapshot.json` por usuário/scope.
- API retorna snapshot com `stale=true` se cálculo atual falhar.
- Background refresh não bloqueia tela.

---

## Fase 3 — Segurança/idempotência de automações

### Task 6: Ledger idempotente central

**Objective:** Todo envio operacional passa por chave idempotente (`lead/deal/chat/tipo/template/version/day`) antes de chamar bridge.

**Acceptance:**
- Reenvio por retry não duplica WhatsApp.
- Concorrência entre crons não duplica.
- Testes com dois workers simulados tentando enviar o mesmo lead.

### Task 7: Guardião de crons antigos e concorrência

**Objective:** Garantir que só o cron unificado envia follow-up SDR e que crons pausados não reativam.

**Acceptance:**
- Guard alerta se job antigo sair de `paused`.
- Guard alerta se houver dois jobs com mesma responsabilidade de envio.
- Guard não altera estado sem aprovação; só alerta.

### Task 8: Política de fail-closed

**Objective:** Se contexto incompleto, inseguro ou contraditório, não enviar; escalar.

**Acceptance:**
- MQL contraditório, owner ausente, opt-out, humano ativo, chat grupo e lead inseguro viram bloqueio/alerta.
- Testes com fixtures para cada bloqueio.

---

## Fase 4 — Qualidade comercial profunda

### Task 9: Score de qualidade da abordagem

**Objective:** Além de taxa, medir qualidade da mensagem e risco de poluição.

**Acceptance:**
- Gestão mostra abordagem com: volume, resposta, agenda, realizada, tempo médio de resposta, exemplos bons/ruins.
- Sem bucket técnico `outros` sem explicação; sempre mostrar texto/pergunta/ângulo real.
- Identificar abordagem com muito volume e baixa resposta para revisão.

### Task 10: SLA de ação humana

**Objective:** Mostrar quem precisa agir agora e cobrar follow-up correto.

**Acceptance:**
- Fila humana prioriza: levantada de mão, reunião sem próximo passo, No Show sem touchpoint, Retorno sem agenda, diagnóstico pendente.
- Cada item com evidência e link HubSpot/conversa.
- Sem logs de automação como pendência.

---

## Fase 5 — Recuperação, backup e continuidade

### Task 11: Runbook de incidente

**Objective:** Documentar resposta para falhas sem improviso.

**Acceptance:**
- Runbook em `docs/runbooks/channel-v2-incident-response.md`.
- Casos: público lento, 0 conversas mobile, `/api/messages` 403, HubSpot timeout, bridge desconectada, watchdog provider timeout, deploy lock, duplicate send.
- Cada caso com: verificar, mitigar, não fazer, validar.

### Task 12: Backup e restauração testada

**Objective:** Garantir recuperação de ledger, histories, snapshots e configs.

**Acceptance:**
- Script read-only de verificação de backup recente.
- Alerta se backup > 10min ou arquivo crítico ausente.
- Teste de restauração em diretório temporário, sem produção.

---

## Gates obrigatórios por release

Antes de qualquer promoção:

```bash
scripts/channel_v2_release_gate.sh
scripts/channel_v2_safe_deploy.sh stage
```

Validação real mínima no candidate:

```bash
/foco
/gestao
/api/conversations
/api/messages?conv=<2 casos institucionais reais>
/api/sdr-orchestrator-summary
/api/task-hygiene-preview
/api/dispatch-stats
```

Após promoção:

```bash
python3 /root/.hermes/scripts/zydon_channel_v2_performance_watchdog.py
```

Critérios para dizer “pronto”:

- testes OK;
- stage OK;
- público OK;
- watchdog OK;
- sem restart de bridge/chip WhatsApp;
- sem mutação indevida de HubSpot/ledger;
- evidência de latência e contagem.

---

## Próxima prioridade recomendada

1. Criar `/api/ops-health-summary` e runbook de incidente.
2. Persistir snapshot específico de Gestão SDR.
3. Implementar guard de idempotência/concorrência para automações de envio.
4. Expandir análise de abordagem para qualidade e revisão de baixa performance.
5. Adicionar backup/restore verification de arquivos críticos.
