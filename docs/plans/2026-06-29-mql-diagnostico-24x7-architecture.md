# Arquitetura 24x7 para MQL → Diagnóstico Zydon

> **Status:** rascunho de revisão com Rafael. Não implementar automaticamente sem aprovação.

**Objetivo:** fazer o fluxo de leads de formulário, site/demo e Facebook Lead Ads rodar 24x7 sem criar diagnóstico antes do MQL confirmado.

**Princípio central:** diagnóstico é consequência do MQL confirmado, não etapa da investigação.

**Regra econômica do Rafael:** marcar um lead como MQL também ensina o Facebook/otimização de mídia. MQL errado não é só erro operacional: treina o Facebook errado e desperdiça dinheiro. Portanto, em dúvida, o lead fica `pending_review`/Não-MQL, não MQL.

---

## Situação atual auditada

### Jobs relevantes

- `zydon-prospeccao-autonomo` (`fcfbcaf10afa`)
  - Roda a cada 5 minutos.
  - Usa LLM/Hermes com skill `zydon-prospeccao`.
  - Executa `python3 motor/gate.py`, pesquisa, classifica e, se MQL, gera/envia diagnóstico.
  - Está ativo e último status estava OK.

- `zydon-pending-lead-discord-alert` (`cc6c80580fe2`)
  - Roda a cada 1 minuto.
  - Script `zydon_pending_lead_watchdog.sh` → `scripts/pending_lead_watchdog.py`.
  - Só alerta/registrar pendência de lead novo, sem enviar WhatsApp e sem processar.
  - Seguro como intake/observabilidade.

- `zydon-active-mql-qualifier-1min` (`4f26aecc5e27`)
  - Roda a cada 1 minuto.
  - Script `zydon_active_mql_qualifier.sh` → `scripts/active_mql_qualifier.py`.
  - Problema: classifica rápido e, se achar MQL, chama `send_mql()`, que gera PDF e envia WhatsApp.
  - Foi pausado em 2026-06-29 a pedido/revisão, porque mistura heurística rápida com criação/envio de diagnóstico.

- `zydon-agenda-queue-sender-1min` (`3a6c93e1c0ae`)
  - Roda a cada 1 minuto.
  - Só processa agenda pós-diagnóstico que já está em fila.
  - Seguro, desde que a fila só receba item após diagnóstico MQL real.

### Scripts com risco de diagnóstico direto

- `scripts/active_mql_qualifier.py`
  - Deve ser refeito ou mantido pausado.
  - Hoje contém `send_mql()` com `pg.generate_pdf(...)` e envio WhatsApp.

- Scripts manuais one-off:
  - `scripts/manual_automec_diagnostico_send.py`
  - `scripts/manual_dmz_diagnostico_send.py`
  - `scripts/manual_greenix_diagnostico_cadence.py`
  - `scripts/manual_greenix_finish_cadence.py`
  - Devem ganhar trava ou serem arquivados para evitar execução acidental.

- `scripts/process_gate_once.py`
  - Fluxo principal atual.
  - Gera PDF dentro do bloco MQL, após classificação/gate.
  - Precisa de trava técnica explícita em `generate_pdf()` ou função wrapper para recusar diagnóstico sem evidência MQL confirmada.

---

## Arquitetura recomendada

Separar o fluxo em 6 estágios, cada um com uma responsabilidade única.

### 1. Intake 24x7: detectar lead novo

**Responsabilidade:** encontrar leads novos/reentradas de formulário.

**Entrada:** HubSpot contacts recentes, `createdate`, `recent_conversion_date`, formulário/site/Facebook Lead Ads.

**Saída:** registro em uma fila local, por exemplo:

`controle/mql_pipeline_queue.json`

Estados possíveis:

- `intake_detected`
- `research_pending`

**Regras:**

- Não envia WhatsApp.
- Não muda lifecycle.
- Não cria PDF.
- Não marca como processado final.
- Dedup por `email`, `contact_id`, `phone`, `recent_conversion_date`.

**Base atual reaproveitável:** `scripts/pending_lead_watchdog.py` e `motor/gate.py`.

---

### 2. Research/classificação

**Responsabilidade:** pesquisar e classificar.

**Entrada:** lead da fila em `research_pending`.

**Ações:**

- Ler formulário HubSpot.
- Pesquisar site/domínio oficial.
- Usar estudos da web e fontes públicas.
- Aplicar crivo ICP Zydon.
- Gerar justificativa clara.

**Saída:** decisão estruturada:

```json
{
  "state": "classified_mql" | "classified_non_mql" | "pending_review",
  "mql": true,
  "confidence": "alta" | "media" | "baixa",
  "reasons": ["..."],
  "sources": ["form", "site", "web"],
  "confirmed_by": "gate_auto" | "rafael" | "manual_review"
}
```

**Regras:**

- Se houver dúvida, vira `pending_review`.
- `pending_review` não cria diagnóstico.
- Não-MQL registra decisão e avisa grupo, sem WhatsApp ao lead.
- MQL só segue se `state == classified_mql` e justificativa existir.

---

### 3. Confirmação MQL e preparação HubSpot

**Responsabilidade:** transformar decisão MQL em estado operacional confirmado.

**Entrada:** item `classified_mql`.

**Ações:**

- Marcar/confirmar `lifecyclestage=marketingqualifiedlead`.
- Aguardar criação/atribuição de deal.
- Resolver SDR dono real pelo negócio, não só pelo contato.
- Bloquear se não houver owner/deal confiável.

**Saída:** estado `mql_confirmed_ready_for_diagnostic`.

**Regras:**

- Sem owner/deal confiável: `blocked_missing_owner_or_deal` e avisa grupo.
- Sem WhatsApp válido: `blocked_invalid_phone` e avisa grupo.
- Ainda não gera PDF até chegar no estado confirmado.

---

### 4. Geração do PDF

**Responsabilidade:** gerar diagnóstico apenas para MQL confirmado.

**Entrada obrigatória:** item com estado `mql_confirmed_ready_for_diagnostic`.

**Ações:**

- Pedir/usar Claude Code para montar PDF com:
  - estudos da web;
  - dados do formulário;
  - justificativa MQL;
  - insight específico.

**Trava técnica obrigatória:**

`generate_pdf()` deve recusar execução se não receber um contexto com:

- `mql_confirmed == True`;
- `contact_id`;
- `deal_id` ou motivo de bloqueio tratado;
- `classification_state == mql_confirmed_ready_for_diagnostic`;
- `classification_reasons` não vazio.

**Saída:** estado `diagnostic_pdf_generated`.

---

### 5. Envio do combo ao lead

**Responsabilidade:** enviar WhatsApp em cadência aprovada.

**Entrada:** `diagnostic_pdf_generated`.

**Cadência:**

1. Texto curto:
   `Fiz uma análise prévia do potencial da digitalização B2B do seu negócio.`
2. Aguardar 60s.
3. Enviar PDF.
4. Aguardar 30s.
5. Pergunta:
   `Como você imagina que a Zydon poderia te apoiar?`
6. Após 20min, agenda se lead não respondeu.

**Regras:**

- Gravar `mql_diagnostico_em_andamento` antes do primeiro `/send`.
- Exigir `messageId` real.
- Se qualquer etapa falhar, estado `send_failed` e alerta.
- Se lead responder antes da agenda, pular agenda e criar task para SDR.

**Saída:** `diagnostic_sent`.

---

### 6. HubSpot, ledger e grupo

**Responsabilidade:** fechar rastreabilidade.

**Ações obrigatórias:**

- Upload/anexo do PDF no HubSpot.
- Nota/tarefa associada ao contato e ao negócio com `hs_attachment_ids`.
- `wpp_envios.json` com messageIds, PDF path/file id, owner, deal, contato.
- Aviso no grupo WhatsApp com decisão final, motivo e quem enviou.
- `processed_emails.txt` com status final.

**Saída:** `completed`.

---

## Mudanças técnicas recomendadas

### Task 1: Pausar/remover o fluxo rápido perigoso

**Arquivo/job:** `zydon-active-mql-qualifier-1min`

**Estado atual:** pausado.

**Recomendação:** manter pausado até virar apenas intake/revisão, ou remover.

### Task 2: Criar fila única de pipeline

**Criar:** `scripts/mql_pipeline_store.py`

Funções:

- `upsert_item(...)`
- `transition_state(...)`
- `find_pending(...)`
- `append_event(...)`

Arquivo de dados:

- `controle/mql_pipeline_queue.json`

### Task 3: Criar trava global de diagnóstico

**Modificar:** `scripts/process_gate_once.py`

Adicionar wrapper:

```python
def assert_mql_confirmed_for_diagnostic(lead, research, context):
    if not context.get('mql_confirmed'):
        raise RuntimeError('diagnóstico bloqueado: MQL não confirmado')
    if context.get('classification_state') != 'mql_confirmed_ready_for_diagnostic':
        raise RuntimeError('diagnóstico bloqueado: estado inválido')
    if not context.get('classification_reasons'):
        raise RuntimeError('diagnóstico bloqueado: justificativa MQL ausente')
```

Chamar antes de qualquer `generate_pdf()` operacional.

### Task 4: Reescrever `active_mql_qualifier.py`

Transformar em:

- detectar lead;
- salvar pendência;
- talvez avisar Discord/grupo que iniciou análise;
- nunca chamar `generate_pdf()`;
- nunca enviar `/send` ou `/send-file` ao lead.

### Task 5: Arquivar ou travar scripts manuais antigos

Adicionar no topo dos one-offs:

```python
raise SystemExit('Script manual antigo bloqueado. Use fluxo MQL confirmado.')
```

Ou mover para `scripts/archived_manual_diagnostics/`.

### Task 6: Testes obrigatórios

Adicionar testes em `tests/test_prospeccao_pdf_msg.py` ou novo `tests/test_mql_pipeline_guardrails.py`:

- Não-MQL não chama `generate_pdf`.
- Pendente/revisão não chama `generate_pdf`.
- MQL sem owner/deal não chama `generate_pdf`.
- `active_mql_qualifier.py` não contém `/send-file` nem `generate_pdf` após refactor.
- `agenda_queue_sender.py` só envia item com `status=pending` já originado de diagnóstico enviado.

### Task 7: Observabilidade 24x7

Criar/ajustar watchdog para alertar:

- lead em `research_pending` há mais de 10min;
- `classified_mql` sem `mql_confirmed_ready_for_diagnostic` há mais de 10min;
- `mql_confirmed_ready_for_diagnostic` sem PDF há mais de 10min;
- `mql_diagnostico_em_andamento` há mais de 30min;
- PDF gerado sem `diagnostic_sent`;
- HubSpot sem attachment após envio;
- grupo sem aviso após decisão final.

---

## Decisões do Rafael em 2026-06-29

1. Todo MQL pode disparar automaticamente 24x7.
2. Fora do horário comercial, pode usar comunicador institucional sempre.
3. Não-MQL mantém a lógica atual: decisão interna/grupo/task; tratativa externa segue separada no cron próprio de Não-MQL legítimo.
4. A decisão técnica sobre `active_mql_qualifier` fica com Hermes/Dexter: fazer o melhor desenho, desde que não volte a misturar diagnóstico pré-MQL.
5. Fonte de leads do fluxo automático: formulários de demonstração/site e Facebook Lead Ads usados pela operação.
6. Exceção manual, o “gol de mão”: é sempre o F5/troca manual de ciclo de vida em janela recente, normalmente últimas 12–24 horas, e Rafael avisa quando for para considerar. Pode acionar o fluxo, mas precisa ser tratado como override explícito e auditável. Não usar qualquer lifecycle solto/antigo como autorização para PDF, porque isso já gerou retrabalho.

---

## Recomendação final

A melhor arquitetura é manter 24x7, mas com trilhos separados:

`intake → pesquisa/classificação → confirmação MQL → geração PDF → envio combo → HubSpot/ledger/grupo`

O que quebrou o desenho foi misturar `classificar rápido` com `gerar/enviar diagnóstico`. A correção é reativar velocidade 24x7 só no intake e na pesquisa, e deixar PDF/envio atrás de uma trava de MQL confirmado.
