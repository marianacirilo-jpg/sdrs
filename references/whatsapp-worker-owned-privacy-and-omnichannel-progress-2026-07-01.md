# WhatsApp worker_owned + Omnichannel SDRs — progresso 2026-07-01

## Revisão Claude Code
Relatório gerado em:

```txt
docs/plans/claude-review-omnichannel-privacy-and-worker-migration.md
```

Principais achados aplicados:
- Guardas de grupo/broadcast/interno divergiam entre painel, flow e worker.
- Centralização necessária em helper único.
- Migração deve seguir agenda/nao_mql → LSC/first_contact → cadência F2-F4 → reentry → diagnóstico/PDF.

## Requisitos omnichannel
Documento criado:

```txt
docs/plans/omnichannel-sdrs-zydon-requisitos-continuidade.md
```

Princípios:
- Timeline do detalhe só mostra history/bridge/device real.
- Grupo/broadcast nunca entra.
- Conversa íntima entre chips/comunicadores nunca entra.
- Só conversa iniciada por automação/painel entra no operacional.
- Envio manual futuro precisa passar por fila central.

## Privacidade/hardening implementado
Arquivos:
- `scripts/whatsapp_jid_utils.py`
- `scripts/whatsapp_dispatch_flow.py`
- `scripts/whatsapp_dispatch_worker.py`
- `scripts/channel_panel_v2.py`
- `tests/test_whatsapp_dispatch_queue.py`
- `tests/test_channel_v2_core.py`

Contrato central:
- `is_group_or_broadcast()` bloqueia `@g.us`, `@broadcast`, `status@broadcast`.
- `INTERNAL_WPP_DIGITS` centraliza chips internos.
- `is_blocked_operational_target()` usado no flow/worker.

Testes novos/validados:
- worker bloqueia grupos, broadcast e chips internos.
- flow bloqueia grupos, broadcast e chips internos.
- painel não lista nem abre grupos/broadcast/conversas internas.
- detalhe rejeita ledger/fila sem bolha real.

## Worker-owned concluído/ativo
### Agenda pós-diagnóstico
- Ativo.
- Completion `agenda_queue`.
- 5 envios reais concluídos no worker.

### Não-MQL
- Ativo.
- Completion `non_mql`.
- Mantém alternate_jids com/sem 9.

### Lead Sem Contato / primeiro contato SDR
- Producer worker-owned implementado em `disparo_dinamico.py`.
- Flag: `ZYDON_DISPARO_DINAMICO_WORKER_OWNED=1`.
- Wrapper LSC ligado em `/root/.hermes/scripts/zydon_followup_parallel_lanes_launcher.sh` apenas para a lane `disparo_dinamico.py --stage-scope lead_sem_contato`.
- Completion `first_contact` implementado em `scripts/whatsapp_worker_completions.py`.
- Worker envia partes (`parts`) com `delay_schedule`.
- Após envio confirmado: grava ledger, cria task HubSpot e move etapa para Primeiro Contato.

## Ainda não ligado por segurança
### Cadência F2/F3/F4 (`scripts/cadencia_primeiro_contato.py`)
Motivo: precisa completion próprio por tentativa F2/F3/F4 e regra de marcação/perda após F4. Não deve ser ligado no worker genérico antes disso.

### Reentry
Motivo: cron atual ainda com erro recente; precisa isolar producer, completion e dedupe antes de ativar.

### Diagnóstico/PDF
Motivo: envolve sequência texto + PDF/mídia + pergunta final. Precisa suporte worker-owned de mídia e completion específico para PDF antes de desligar legado.

## Validação executada
- `py_compile` dos módulos alterados.
- 30 testes focados de follow-up/worker/privacy OK.
- Channel release gate completo: 169 testes OK.
- Stage 8891 OK.
- Promote produção OK.
- Health 8280/8791 OK.
- Smoke `/api/conversations` e `/api/messages` OK.
- Dispatch monitor exit 0.

## Estado da fila no fechamento
```json
{"total": 94, "by_mode": {"None": 17, "shadow": 72, "worker_owned": 5}, "worker_owned_queued": []}
```

Interpretação: não havia worker_owned pendente/travado no fechamento; worker_owned existentes estavam concluídos/sent.
