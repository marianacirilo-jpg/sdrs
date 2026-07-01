# Follow-up F2/F3/F4 worker_owned cutover — 2026-07-01

## Escopo
Migração da cadência `scripts/cadencia_primeiro_contato.py` para fila central `worker_owned`.

## Contratos implementados
- `ZYDON_CADENCIA_WORKER_OWNED=1` faz o producer enfileirar em vez de enviar direto.
- `completion_type=followup_cadence` grava ledger/task somente após envio confirmado pelo worker.
- `msg_type=primeiro_contato_cadencia` preservado para dedupe e métricas legadas.
- `nature=followup_f{n}` preserva F2/F3/F4 na fila central.
- Wrapper ativo `/root/.hermes/scripts/zydon_sdr_followup_unificado_5min.sh` usa a flag.
- Launcher paralelo `/root/.hermes/scripts/zydon_followup_parallel_lanes_launcher.sh` também usa a flag.

## Incidente controlado durante validação
Uma execução manual do worker com timeout curto pegou lote grande de Follow 2/3 com delays humanos e deixou itens `locked` antes do completion. Recuperação feita:
- itens com partes reais no WhatsApp: enviar somente partes faltantes e rodar completion;
- itens sem nenhuma parte real: voltar para `queued`;
- nenhum item reenviado completo por cima de mensagem já entregue.

## Correção permanente
`/root/.hermes/scripts/zydon_dispatch_worker_live.py` agora:
- usa lock de processo;
- processa `max_simultaneous=1` por invocação;
- evita concorrência entre ticks do cron enquanto uma sequência longa está em andamento.

## Validação
- `py_compile` OK para cadência, completions e worker.
- `tests.test_followup_incident_safety` OK.
- `tests.test_cadencia_lost_deal_gate` OK.
- `tests.test_whatsapp_dispatch_queue` OK.
- Monitor da fila OK após recuperação.

## Próximos passos
- Deixar cron `zydon-dispatch-worker-live-1min` processar pendentes gradualmente.
- Não aumentar batch do worker enquanto as sequências usam delays longos síncronos.
- Próxima migração: reentry/diagnóstico com suporte seguro a texto + PDF/mídia.
