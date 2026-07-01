# Diagnóstico/PDF worker_owned — fundação segura 2026-07-01

## Escopo feito
Preparada a base para migrar o diagnóstico MQL completo para a fila central sem interromper os fluxos já ativos.

## Mudanças implementadas

### Worker WhatsApp
`/root/.hermes/zydon-prospeccao/scripts/whatsapp_dispatch_worker.py`

Agora suporta sequência mista:

1. texto (`/send`)
2. arquivo/PDF (`/send-file`)
3. texto/pergunta (`/send`)

Contrato de `parts`:

```json
[
  {"kind":"text", "text":"..."},
  {"kind":"file", "filePath":"...pdf", "fileName":"...pdf", "thumbnailPath":"...jpg"},
  {"kind":"text", "text":"Como você imagina que a Zydon poderia te apoiar?"}
]
```

O worker preserva `messageIds` de todas as partes e só roda completion quando o bundle inteiro retorna sucesso.

### Completion de diagnóstico
`/root/.hermes/zydon-prospeccao/scripts/whatsapp_worker_completions.py`

Novo hook:

```txt
completion_type=diagnostic_bundle
```

Ele grava `wpp_envios.json` com:

- `status=enviado_lead`
- `text_response`
- `file_response`
- `question_response`
- `pdf_path`
- `hubspot_file_id` quando existir
- `task_id` quando existir
- `agenda_pending=true`

E cria/atualiza item em `controle/agenda_queue.json` para a etapa posterior de agenda.

### Producer isolado
`/root/.hermes/zydon-prospeccao/scripts/process_gate_once.py`

Nova função:

```python
enqueue_worker_owned_diagnostic_bundle(...)
```

Ela apenas enfileira o diagnóstico completo como `worker_owned`; não envia WhatsApp.

## Importante: ainda NÃO ligado ao main live
A função foi criada e testada, mas não foi conectada ao fluxo principal de diagnóstico ainda.

Motivo: o sistema está rodando em produção e o cutover completo precisa preservar:

- upload/anexo HubSpot
- task HubSpot
- aviso interno 1:1 Mariana/Rafael
- dedupe MQL em andamento
- fallback SDR→comunicador
- agenda queue
- recuperação se cair entre texto/PDF/pergunta

## Testes verdes
Rodado em 2026-07-01:

```txt
29 testes OK
```

Inclui:

- `test_live_worker_sends_text_file_text_sequence_for_diagnostic_bundle`
- `test_diagnostic_bundle_completion_writes_ledger_and_agenda_after_worker_send`
- `test_enqueue_worker_owned_diagnostic_bundle_uses_text_pdf_question_and_completion`
- testes de privacidade grupos/broadcast/chips internos
- testes de follow-up/cadência
- higiene stale in_progress de reentry

## Estado operacional após mudança
Monitor da fila:

```txt
MONITOR_EXIT:0
worker_owned {'sent': 15, 'cancelled': 8}
reentry {'sent': 4, 'skipped_existing_diagnostic': 8, 'needs_review': 11, 'in_progress': 2, 'pending': 73}
```

Sem itens locked travados no momento da validação.

## Próximo passo seguro
Conectar `process_gate_once.main()` a uma flag controlada, por exemplo:

```bash
ZYDON_MQL_DIAGNOSTIC_WORKER_OWNED=1
```

Fluxo de cutover recomendado:

1. gerar PDF normalmente;
2. resolver SDR/chip normalmente;
3. fazer upload HubSpot/anexo/task antes ou mover essa criação para completion;
4. enfileirar `diagnostic_bundle` em vez de chamar `/send` + `/send-file` direto;
5. worker envia texto/PDF/pergunta;
6. completion grava ledger e agenda;
7. manter legado desligado apenas para os itens `worker_owned`, sem pausar cron inteiro;
8. validar 1 lead controlado antes de ampliar.

## Guardrail
Não aumentar `max_simultaneous` para bundle com PDF enquanto o worker ainda usa delays síncronos. O runner live deve continuar processando 1 dispatch lógico por execução até termos worker assíncrono/por item.
