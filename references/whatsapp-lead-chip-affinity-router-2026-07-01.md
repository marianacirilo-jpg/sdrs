# WhatsApp lead→chip affinity router — 2026-07-01

## Objetivo
Garantir que um lead não seja abordado por múltiplos chips/números e que a cadência continue pelo mesmo chip que iniciou a conversa.

## Regras de negócio
1. Lead novo pode ser distribuído entre chips saudáveis do SDR.
2. Lead com histórico/ledger em um chip mantém o mesmo chip.
3. Lead com item ativo na fila (`queued`, `locked`, `sent`, `blocked`) em uma porta não pode entrar por outra porta.
4. Agenda pós-diagnóstico herda o chip do diagnóstico.
5. Follow-up F2/F3/F4 usa o roteador antes da escolha legada e grava `routing_mode`/`routing_reason` no sender.
6. Grupos, broadcasts e chips internos continuam bloqueados pela fronteira de privacidade.

## Arquivos alterados
- `scripts/whatsapp_routing.py`: helpers centrais de afinidade/anti-duplo-contato.
- `scripts/whatsapp_dispatch_queue.py`: bloqueio sob lock para impedir mesmo lead por segunda porta.
- `scripts/cadencia_primeiro_contato.py`: `choose_sender_for_lead` consulta roteador com ledger + fila ativa.
- `scripts/process_gate_once.py`: `pick_online_port` consulta roteador com ledger + fila ativa; `resolve_diagnostic_sender` expõe contrato testável.
- `scripts/whatsapp_chip_operator_learning.py`: snapshot de aprendizado contínuo por chip/operador.

## Testes relevantes
- `tests.test_whatsapp_routing`
- `tests.test_whatsapp_dispatch_queue`
- `tests.test_followup_incident_safety.FollowupIncidentSafetyTest.test_choose_sender_keeps_active_router_chip_for_lead`
- `tests.test_prospeccao_pdf_msg.TestDiagnosticoWorkerOwnedProducer.test_pick_online_port_respects_active_dispatch_queue_affinity`
- `tests.test_whatsapp_chip_operator_learning`

## Validação feita
```bash
python3 -m py_compile scripts/process_gate_once.py scripts/cadencia_primeiro_contato.py
python3 -m unittest tests.test_prospeccao_pdf_msg.TestDiagnosticoWorkerOwnedProducer \
  tests.test_followup_incident_safety.FollowupIncidentSafetyTest \
  tests.test_whatsapp_dispatch_queue tests.test_whatsapp_routing \
  tests.test_whatsapp_chip_operator_learning -v
```
Resultado: 62 testes OK.

Monitor real:
```txt
MONITOR_EXIT:0
worker_owned {'sent': 15, 'cancelled': 8}
```

## Próximos cuidados
- Ao adicionar chips extras para um SDR, atualizar `controle/channel_ports.json` e `controle/channel_users.json`.
- Não transformar comunicadores institucionais em SDR sem decisão explícita.
- Qualquer produtor novo de WhatsApp deve usar `record_dispatch_worker_owned`/fila central ou `choose_outbound_port` antes de escolher porta.
- Fallback de chip só pode acontecer com motivo registrado e sem duplicar mensagem.
