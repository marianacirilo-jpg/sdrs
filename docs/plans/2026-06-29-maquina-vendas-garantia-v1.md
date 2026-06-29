# Máquina de Vendas Zydon — Garantia V1 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** transformar o fluxo MQL → diagnóstico em uma máquina simples, auditável, idempotente e escalável, com garantia real de execução ponta a ponta.

**Architecture:** manter os crons atuais, mas colocar uma camada pequena de garantia por cima: fila/ledger único por lead, trava de dedupe antes de qualquer envio, executor idempotente por etapa e watchdog de SLA. A versão V1 deve ser simples: arquivos JSON atômicos + lock + testes, sem banco novo e sem reescrever todo o fluxo.

**Tech Stack:** Python stdlib, JSON em `controle/`, locks com `fcntl/flock`, scripts existentes em `scripts/`, testes `unittest`, gates atuais do Channel/prospecção.

---

## Princípios obrigatórios

1. **Fail-closed:** dúvida, erro de HubSpot/WhatsApp/PDF ou dado contraditório para a etapa; não envia, não marca concluído, alerta.
2. **Idempotência:** rodar o mesmo cron 10 vezes não pode duplicar diagnóstico, PDF, WhatsApp, anexo ou aviso no grupo.
3. **Fila única:** cada MQL confirmado vira um item rastreável com status por etapa.
4. **Sem cron Deus:** decisão, execução e monitoramento precisam ser separados, mesmo que V1 use arquivos simples.
5. **Escala:** cada ciclo processa lote pequeno e retoma do ponto onde parou.
6. **Evidência:** para dizer “OK”, precisa haver registro em fila, ledger, HubSpot/WhatsApp quando aplicável e cron OK.

---

## Estado alvo V1

Arquivo principal:

`controle/mql_execution_queue.json`

Formato por item:

```json
{
  "version": 1,
  "items": [
    {
      "execution_id": "contact:123|deal:456|phone:5534...",
      "contact_id": "123",
      "deal_id": "456",
      "email": "lead@empresa.com",
      "phone_norm": "553499999999",
      "company": "Empresa",
      "source": "form|facebook|site|manual_override",
      "owner_id": "88063842",
      "owner_name": "Sarah",
      "status": "mql_confirmed",
      "created_at": "2026-06-29T19:00:00-03:00",
      "updated_at": "2026-06-29T19:00:00-03:00",
      "classification": {
        "mql": true,
        "reason": "...",
        "evidence": ["formulario", "site", "pesquisa"]
      },
      "steps": {
        "pdf_generated": {"status": "pending", "at": null, "path": null, "error": null},
        "whatsapp_sent": {"status": "pending", "at": null, "message_id": null, "chip": null, "error": null},
        "hubspot_attached": {"status": "pending", "at": null, "file_id": null, "note_id": null, "error": null},
        "group_notified": {"status": "pending", "at": null, "message_id": null, "error": null}
      },
      "retry": {"count": 0, "next_retry_at": null, "last_error": null},
      "dedupe_keys": ["contact:123", "deal:456", "phone:5534...", "email:lead@empresa.com"]
    }
  ]
}
```

Status permitidos:

- `mql_confirmed`
- `executing`
- `blocked`
- `completed`
- `failed_needs_human`
- `cancelled_duplicate`

Status de etapa:

- `pending`
- `running`
- `done`
- `blocked`
- `failed`
- `skipped_duplicate`

---

## Fluxo simples e robusto

```text
[prospeccao-autonomo]
  decide MQL com formulário/site/pesquisa
  ↓
[enqueue_mql_execution.py]
  cria/atualiza item único na fila
  dedupe por contact/deal/phone/email/ledger
  ↓
[mql_execution_worker.py]
  lock global
  pega poucos itens pendentes
  executa próxima etapa idempotente
  salva depois de cada etapa
  ↓
[mql_execution_watchdog.py]
  verifica SLA e inconsistências
  alerta se etapa travar/falhar
```

O `active_mql_qualifier.py` pode continuar só fazendo intake/revisão. Ele nunca deve chamar worker de execução diretamente.

---

## Tarefas de implementação

### Task 1: Criar módulo de fila com escrita atômica

**Objective:** ter utilitário único para carregar/salvar fila com lock e sem corromper JSON.

**Files:**
- Create: `scripts/mql_execution_queue.py`
- Test: `tests/test_mql_execution_queue.py`

**Step 1: escrever testes**

Casos mínimos:

- cria fila vazia se arquivo não existe;
- salva com arquivo temporário e replace atômico;
- gera `execution_id` estável;
- normaliza dedupe keys;
- não duplica item com mesmo contact/deal/phone/email.

**Step 2: implementar funções**

Funções mínimas:

```python
load_queue(path=DEFAULT_QUEUE) -> dict
save_queue(data, path=DEFAULT_QUEUE) -> None
with_queue_lock(): context manager
dedupe_keys(contact_id=None, deal_id=None, phone=None, email=None) -> list[str]
execution_id(keys: list[str]) -> str
upsert_mql_item(queue, item) -> tuple[dict, bool]
find_existing_item(queue, keys) -> dict | None
```

**Step 3: verificar**

Run:

```bash
python3 -m unittest tests.test_mql_execution_queue -v
```

Expected: PASS.

---

### Task 2: Criar trava de dedupe forte antes de envio

**Objective:** garantir que nenhum diagnóstico seja enviado duas vezes para o mesmo lead/deal/telefone/email.

**Files:**
- Create: `scripts/mql_dedupe_guard.py`
- Test: `tests/test_mql_dedupe_guard.py`
- Read-only sources: `controle/wpp_envios.json`, `controle/mql_execution_queue.json`

**Step 1: escrever testes**

Casos mínimos:

- bloqueia se `wpp_envios.json` tiver `enviado_lead` para o email;
- bloqueia se tiver `messageId` de diagnóstico para o telefone;
- bloqueia se fila tiver etapa `whatsapp_sent.done`;
- permite quando não existe histórico;
- retorna motivo claro para auditoria.

**Step 2: implementar função**

```python
can_send_diagnostic(contact_id, deal_id, phone, email, company) -> tuple[bool, str]
```

Retornos:

- `(True, "sem envio anterior encontrado")`
- `(False, "já enviado: ledger status enviado_lead email=...")`
- `(False, "já enviado: fila execution_id=... whatsapp_sent.done")`

**Step 3: integrar no ponto imediatamente anterior ao WhatsApp**

Modificar `scripts/process_gate_once.py` no ponto anterior ao envio real para chamar `can_send_diagnostic(...)`.

Se bloquear:

- não enviar;
- registrar no ledger/fila como `skipped_duplicate` ou `blocked`;
- avisar grupo apenas se for inconsistência relevante.

**Step 4: verificar**

Run:

```bash
python3 -m unittest tests.test_mql_dedupe_guard -v
python3 -m unittest tests.test_mql_diagnostic_guardrails -v
```

Expected: PASS.

---

### Task 3: Criar enqueue formal de MQL confirmado

**Objective:** todo MQL confirmado entra numa fila auditável antes da execução.

**Files:**
- Create: `scripts/enqueue_mql_execution.py`
- Modify: `scripts/process_gate_once.py`
- Test: `tests/test_enqueue_mql_execution.py`

**Step 1: teste de enqueue**

Casos:

- MQL confirmado cria item com status `mql_confirmed`;
- Não-MQL não cria item;
- pendente/revisão não cria item executável;
- MQL já existente atualiza metadados sem duplicar.

**Step 2: implementar script/helper**

`enqueue_mql_execution.py` deve receber dados já decididos pelo gate e chamar `upsert_mql_item`.

**Step 3: integração segura**

Em `process_gate_once.py`, após confirmação de MQL e antes de gerar/enviar diagnóstico, registrar item na fila.

V1 pode manter execução no fluxo atual, mas precisa gravar cada etapa na fila. V2 separa worker.

**Step 4: verificar**

Run:

```bash
python3 -m unittest tests.test_enqueue_mql_execution -v
python3 -m unittest tests.test_mql_diagnostic_guardrails -v
```

Expected: PASS.

---

### Task 4: Registrar etapas reais na fila

**Objective:** fila precisa provar o que aconteceu: PDF, WhatsApp, HubSpot e grupo.

**Files:**
- Modify: `scripts/process_gate_once.py`
- Modify/Create helpers in `scripts/mql_execution_queue.py`
- Test: `tests/test_mql_execution_steps.py`

**Step 1: helper de atualização de etapa**

```python
mark_step(execution_id, step, status, **fields)
mark_blocked(execution_id, reason)
mark_completed_if_all_done(execution_id)
```

**Step 2: pontos de marcação**

- depois de PDF gerado: `pdf_generated.done(path=...)`
- depois de WhatsApp enviado: `whatsapp_sent.done(message_id=..., chip=...)`
- depois de anexo HubSpot: `hubspot_attached.done(file_id=..., note_id=...)`
- depois de aviso grupo: `group_notified.done(message_id=...)`

Se etapa falhar:

- salvar `failed` com erro;
- não pular para próxima etapa que depende dela;
- alerta se não for falha transitória.

**Step 3: verificar**

Run:

```bash
python3 -m unittest tests.test_mql_execution_steps -v
```

Expected: PASS.

---

### Task 5: Watchdog de SLA por etapa

**Objective:** nada pode ficar travado silenciosamente.

**Files:**
- Create: `scripts/mql_execution_watchdog.py`
- Create wrapper: `/root/.hermes/scripts/zydon_mql_execution_watchdog.sh`
- Test: `tests/test_mql_execution_watchdog.py`

**SLA V1 recomendado:**

- `mql_confirmed` sem `pdf_generated.done` por 10min → alerta.
- `pdf_generated.done` sem `whatsapp_sent.done` por 5min → alerta.
- `whatsapp_sent.done` sem `hubspot_attached.done` por 10min → alerta.
- item `running` por mais de 10min → alerta.
- `retry.count >= 3` → `failed_needs_human` e alerta.

**Step 1: testes com fixtures de fila**

- item dentro do SLA não alerta;
- item vencido alerta;
- item completed não alerta;
- alerta dedupado por chave para não spammar.

**Step 2: implementar watchdog silencioso**

Saída vazia quando OK. Mensagem curta quando falha.

**Step 3: criar cron**

Agendar a cada 5min, `no_agent=true`, deliver origin/discord conforme padrão.

---

### Task 6: Painel simples de garantia

**Objective:** Rafael conseguir ver saúde da máquina sem ler logs.

**Files:**
- Create: `scripts/mql_guarantee_status.py`
- Optional route later: Channel `/gestao` or `/api/mql-guarantee-status`
- Test: `tests/test_mql_guarantee_status.py`

**V1 CLI output:**

```text
MQL Machine: OK
last_lead_seen: ...
last_mql_confirmed: ...
last_pdf_generated: ...
last_whatsapp_sent: ...
last_hubspot_attached: ...
queue_pending: 0
queue_failed: 0
oldest_pending_age_min: 0
critical_crons: ok
backup: ok
```

**Step 1:** calcular status a partir da fila + cron outputs + flags.

**Step 2:** retornar exit code:

- 0 = OK
- 1 = WARNING
- 2 = CRITICAL

**Step 3:** usar no relatório/alerta.

---

### Task 7: Release gate da máquina MQL

**Objective:** nenhuma mudança de prospecção quebra guardrails.

**Files:**
- Create: `scripts/mql_machine_release_gate.sh`

**Conteúdo mínimo:**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /root/.hermes/zydon-prospeccao
python3 -m py_compile \
  scripts/process_gate_once.py \
  scripts/active_mql_qualifier.py \
  scripts/agenda_queue_sender.py \
  scripts/mql_execution_queue.py \
  scripts/mql_dedupe_guard.py \
  scripts/mql_execution_watchdog.py \
  scripts/mql_guarantee_status.py
python3 -m unittest \
  tests.test_mql_diagnostic_guardrails \
  tests.test_mql_execution_queue \
  tests.test_mql_dedupe_guard \
  tests.test_enqueue_mql_execution \
  tests.test_mql_execution_steps \
  tests.test_mql_execution_watchdog \
  tests.test_mql_guarantee_status -v
```

---

## Ordem de execução recomendada

1. `mql_execution_queue.py` + testes.
2. `mql_dedupe_guard.py` + integração antes do WhatsApp.
3. Enqueue formal de MQL confirmado.
4. Registro de etapas reais na fila.
5. Watchdog SLA.
6. Status CLI.
7. Release gate.
8. Só depois pensar em painel visual no Channel.

---

## O que NÃO fazer agora

- Não trocar tudo para banco complexo.
- Não reescrever todos os crons de uma vez.
- Não juntar decisão e execução de novo.
- Não aumentar volume sem dedupe forte.
- Não criar dashboard bonito antes da fila/garantia funcionar.

---

## Critério de pronto V1

V1 só está pronta quando:

```bash
python3 -m unittest discover -s tests -v
scripts/mql_machine_release_gate.sh
scripts/channel_v2_release_gate.sh
scripts/channel_v2_safe_deploy.sh stage
```

E houver evidência de:

- fila não duplica;
- dedupe bloqueia reenvio;
- diagnóstico só existe pós-MQL confirmado;
- etapa falhada gera alerta;
- cron roda abaixo de 120s;
- nenhum processo fica pendurado;
- nenhum envio real é feito em teste sem confirmação/ambiente seguro.

---

## Resumo executivo

A melhoria mais inteligente é pequena e profunda: **uma fila de garantia + dedupe forte + watchdog de SLA**.

Isso dá performance porque evita varredura pesada e retrabalho.
Isso dá segurança porque cada envio passa por dedupe e status.
Isso dá escala porque processa em lotes e retoma do ponto certo.
Isso dá qualidade porque MQL duvidoso não entra na execução.
Isso dá garantia porque cada etapa fica registrada e monitorada.
