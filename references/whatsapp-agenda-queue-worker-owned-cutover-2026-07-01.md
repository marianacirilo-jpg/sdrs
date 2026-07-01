# WhatsApp Dispatch — cutover real do agenda_queue para worker_owned — 2026-07-01

## Implementado
Primeiro fluxo real migrado para o motor novo: `agenda_queue`.

Antes:

```txt
zydon-agenda-queue-sender-1min -> scripts/agenda_queue_sender.py -> post_bridge_with_retries_locked -> WhatsApp
```

Agora:

```txt
zydon-agenda-queue-sender-1min -> scripts/agenda_queue_sender.py -> record_dispatch_worker_owned -> whatsapp_dispatch_queue.json
zydon-dispatch-worker-live-1min -> scripts/whatsapp_dispatch_worker.py -> safe_post_bridge -> WhatsApp
worker completion -> scripts/whatsapp_worker_completions.py -> agenda_queue item done + wpp_envios agenda_followup_done
```

## Segurança implementada
- Wrapper `~/.hermes/scripts/zydon_agenda_queue_sender.sh` agora exporta `ZYDON_AGENDA_WORKER_OWNED=1`.
- Agenda cron não chama mais bridge legado quando `worker_owned` está ativo.
- Agenda cron marca item como `queued_worker_owned`, não `done`.
- Worker só finaliza o item original depois de resposta OK do WhatsApp.
- Completion hook atualiza `agenda_queue.json` e `wpp_envios.json`.
- Monitor `zydon_dispatch_queue_monitor.py` alerta se agenda ficar `queued_worker_owned` parada >10min.

## Testes
- `tests/test_agenda_queue_worker_owned_cutover.py`
  - prova que o cron não chama legado no modo worker_owned.
  - prova que cria dispatch `execution_mode=worker_owned` com `completion_type=agenda_queue`.
  - prova que completion finaliza só depois do worker send OK.
- `tests.test_whatsapp_dispatch_queue...test_live_worker_calls_completion_after_successful_send`
  - prova que worker chama completion callback após envio bem-sucedido.

## Execução real controlada
Antes do cutover havia 2 agendas vencidas pendentes.

Rodada do cron agenda:

```txt
agenda_worker_owned_queued: fabiominelligu@gmail.com via 4606 dispatch=dsp_46b438a3a8a11302e212
agenda_worker_owned_queued: contato@sqimports.com.br via 4609 dispatch=dsp_813fe2ac9627381c0f4a
```

Rodada do worker live:

```txt
locked=2
sent=2
failed=0
blocked=0
completed=2
completion_failed=0
```

Message IDs reais:

```txt
dsp_46b438a3a8a11302e212 -> 3EB06255D89D5B8476B602
dsp_813fe2ac9627381c0f4a -> 3EB0992DAF6321801BF2BE
```

Estado final:

```txt
dispatch_by_mode: shadow=47, worker_owned=2
dispatch_by_status: queued=47, sent=2
worker_owned_failed_or_blocked=0
active_dedupe_duplicates=0
agenda_by_status: done=17, pending=3
```

## Rollback simples
Para voltar agenda ao legado, editar `~/.hermes/scripts/zydon_agenda_queue_sender.sh` e remover:

```bash
export ZYDON_AGENDA_WORKER_OWNED=1
```

Os demais fluxos continuam shadow/legado.
