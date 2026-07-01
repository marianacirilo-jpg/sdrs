# WhatsApp Dispatch — cutover Não-MQL para worker_owned — 2026-07-01

## Implementado
O fluxo Não-MQL foi preparado e ligado para criar `worker_owned` em vez de enviar direto.

Wrapper ativo:

```txt
/root/.hermes/scripts/zydon_non_mql_legit_backfill.sh
```

Agora exporta:

```bash
ZYDON_NON_MQL_WORKER_OWNED=1
```

## Fluxo novo

```txt
zydon-nao-mql-tratativa-legitima-10min
  -> scripts/non_mql_legit_outreach.py --send
  -> record_dispatch_worker_owned(origin=nao_mql, completion_type=non_mql)
  -> whatsapp_dispatch_worker.py live
  -> safe_post_bridge
  -> whatsapp_worker_completions.py::_complete_non_mql
  -> wpp_envios.json + HubSpot task
```

## Segurança
- No modo `worker_owned`, `send_one()` não chama `post_bridge_short` nem `safe_post_bridge` diretamente.
- Producer apenas enfileira.
- Worker tenta `jid` principal e depois `alternate_jids` se o principal falhar.
- Completion grava ledger `enviado_nao_mql_legitimo` e task HubSpot só depois do envio OK.
- Se HubSpot task falhar, ledger ainda é salvo com `task_error`, evitando reenvio.

## Testes
Criado:

```txt
tests/test_non_mql_worker_owned_cutover.py
```

Cobre:
- Não-MQL worker_owned não chama envio legado.
- Enfileira `alternate_jids`.
- Completion grava ledger e task após worker OK.

Atualizado:

```txt
tests/test_whatsapp_dispatch_queue.py
```

Cobre:
- Worker tenta `alternate_jids` quando principal falha.

Validação executada:

```txt
33 testes OK
py_compile OK
```

## Execução controlada
Dry-run antes de ligar retornou:

```txt
eligible_count=0
```

Depois do wrapper ligado, uma execução real saiu silenciosa e não criou Não-MQL `worker_owned`, porque não havia elegíveis no momento.

Estado após validação:

```txt
nao_mql_worker_owned=0
failed_or_blocked_worker_owned=0
monitor_exit=0
```

## Rollback
Remover `ZYDON_NON_MQL_WORKER_OWNED=1` de:

```txt
/root/.hermes/scripts/zydon_non_mql_legit_backfill.sh
```

Os envios voltam ao legado.
