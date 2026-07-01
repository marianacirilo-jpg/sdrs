# WhatsApp Dispatch — auditoria de cutover para worker_owned — 2026-07-01

## Objetivo
Rafael pediu para testar como se fosse trocar os crons que criam os disparos, ver quem chama quem, como chama, se está conforme o desenho novo e só sair trocando com segurança.

## Resultado do teste/auditoria
Criado script versionado:

```txt
scripts/whatsapp_cutover_readiness.py
```

Criado teste:

```txt
tests/test_whatsapp_cutover_readiness.py
```

Validação executada:

```txt
python3 -m unittest tests.test_whatsapp_cutover_readiness tests.test_whatsapp_dispatch_queue tests.test_whatsapp_dispatch_flow_contract -v
```

Resultado: 27 testes OK.

## Simulação real com fila atual
A fila real no momento tinha 35 itens shadow:

```txt
agenda: 3
diagnostico: 8
proatividade: 24
```

Todos os itens tinham payload completo:

```txt
jid OK
text OK
port OK
logical_message_id OK
dedupe_key OK
nature OK
```

Simulação em arquivo temporário, convertendo shadow -> worker_owned, com transporte falso:

```txt
worker live simulado: sent=8, blocked=0, failed=0
```

Ele teria enviado no primeiro lote:

```txt
agenda: 2
diagnostico: 4
proatividade: 2
```

Sem enviar WhatsApp real.

## Mapa de fluxos ativos

1. `agenda_queue`
   - cron: `zydon-agenda-queue-sender-1min`
   - script: `scripts/agenda_queue_sender.py`
   - status: `candidate`
   - risco: baixo
   - motivo: tem fila própria, payload completo, guarda `lead_replied_after`, já faz shadow.

2. `non_mql`
   - cron: `zydon-nao-mql-tratativa-legitima-10min`
   - script: `scripts/non_mql_legit_outreach.py`
   - status: `needs_adapter`
   - motivo: tem retry por telefone alternativo dentro do sender; worker precisa adapter.

3. `diagnostic_mql`
   - cron: `zydon-active-mql-qualifier-1min`
   - script: `scripts/process_gate_once.py`
   - status: `needs_adapter`
   - motivo: mistura diagnóstico/PDF/mídia/grupo/HubSpot; precisa separar lead vs interno e mídia antes do worker.

4. `followup_parallel`
   - cron: `zydon-followup-parallel-lanes-5min`
   - script: `scripts/cadencia_primeiro_contato.py`
   - status: `needs_adapter`
   - motivo: maior volume; preservar lane, sequência e limitar por SDR/chip.

5. `agenda_monitor`
   - cron: `zydon-diagnostico-agendado-monitor`
   - script: `scripts/monitor_diagnostico_agendado.py`
   - status: `needs_adapter`
   - motivo: mistura acompanhamento/avisos e registro; separar notificação interna vs envio ao lead.

6. `reentry_drip`
   - cron: `zydon-reentry-diagnostic-drip-10min`
   - script externo: `/root/.hermes/scripts/zydon_reentry_diagnostic_drip_20260701.py`
   - status: `needs_adapter`
   - motivo: chama `process_gate_once.pg.main()` por fora; precisa adapter explícito.

7. `dynamic_sender`
   - script: `disparo_dinamico.py`
   - status: `needs_adapter`
   - motivo: base compartilhada; não trocar central direto antes dos chamadores.

## Ponto crítico encontrado antes de trocar
O primeiro candidato (`agenda_queue`) não deve simplesmente marcar `done` ao criar worker_owned.

Risco se trocar errado:

```txt
cron cria worker_owned
marca done antes do worker enviar
worker falha depois
processo fica incompleto
```

Risco inverso:

```txt
cron cria worker_owned
não marca nada
cron roda de novo no minuto seguinte
pode tentar enfileirar de novo
```

Deduper segura duplicidade, mas o fluxo fica sujo.

## Troca segura correta
Antes de virar o `agenda_queue`, implementar:

```txt
agenda_queue_sender cria worker_owned e marca item como queued_worker_owned
worker, após send OK, finaliza agenda_queue item como done/sent_worker_owned
worker registra response/attempts no item original
monitor alerta se queued_worker_owned ficar parado
```

Só depois ativar no wrapper:

```txt
ZYDON_AGENDA_WORKER_OWNED=1 python3 scripts/agenda_queue_sender.py
```

## Ordem recomendada

1. `agenda_queue` — primeiro, depois do completion hook.
2. `non_mql` — adapter de retry por telefone alternativo.
3. `followup_parallel` — uma lane/SDR por vez.
4. `reentry_drip` — adapter do script externo.
5. `diagnostic_mql` — depois de separar mídia/PDF/interno.
6. `dynamic_sender` — por último, nunca trocar central direto primeiro.
