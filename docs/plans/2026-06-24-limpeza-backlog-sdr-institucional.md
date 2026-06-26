# Limpeza Backlog Primeiro Contato SDR via Chips Institucionais

> **For Hermes:** plano operacional para implementar/rodar somente após Rafael validar textos e cadência.

**Goal:** limpar backlog de primeiro contato dos owners Sarah e Lucas com negócios criados há mais de 3 dias e sem atividade comercial válida, rotacionando os chips institucionais Rafael, Mariana e Lucas Resende.

**Architecture:** criar um script separado do cron SDR atual para não misturar chips SDR com institucionais. O script lê HubSpot ao vivo, filtra apenas owners Sarah/Lucas, deals nas 5 primeiras etapas, idade >72h, sem atividade comercial válida, com celular válido e sem `msg_type=primeiro_contato`. Envia texto aprovado via rotação 4607/4600/4606, registra `wpp_envios.json` e cria task COMPLETED no HubSpot dizendo explicitamente qual chip/conta disparou.

**Tech Stack:** Python 3 stdlib, HubSpot CRM API, bridges Baileys HTTP locais (`/status`, `/me`, `/send`), controle JSON em `controle/wpp_envios.json`.

---

## Snapshot atual HubSpot — 24/06 10:54 BRT

Escopo pedido: pendentes Sarah + Lucas, criados há mais de 3 dias, nunca tiveram contato comercial válido.

| Owner original | Prontos com WhatsApp | Sem telefone/fixo | Sem contato associado | Menos de 72h excluídos |
|---|---:|---:|---:|---:|
| Sarah | 32 | 3 | 3 | 9 |
| Lucas | 61 | 24 | 2 | 8 |
| **Total** | **93** | **27** | **5** | **17** |

## Pool de envio aprovado para limpar backlog

| Porta | Conta | Uso no plano |
|---:|---|---|
| 4607 | Rafael Calixto | institucional/backlog |
| 4600 | Mariana \| Zydon | institucional/backlog |
| 4606 | Lucas Resende | institucional/backlog |

Não usar Sarah 2/4604 nesse fluxo enquanto `/send` estiver retornando 500/503. Não usar Lucas Batista/4603 se o objetivo for blindar SDR.

## Cadência segura proposta

Backlog velho não é urgente como lead novo. Para acelerar sem parecer blast:

1. Rodar apenas seg-sex 08:30–17:30 BRT.
2. Máximo inicial: **4 mensagens por chip por hora**.
3. Com 3 chips: até **12/hora**.
4. Colocar intervalo mínimo de **7 a 12 minutos por chip** e jitter aleatório.
5. Nunca mandar os 3 chips no mesmo segundo: espaçar 30–90s entre envios globais.
6. Parar o chip no primeiro erro HTTP 500/503/timeout e remover da rotação até diagnóstico.
7. Parar tudo se houver respostas negativas, bloqueios, QR, `needsQR` ou queda repetida.
8. Primeira rodada recomendada pós-validação: **9 envios totais** (3 por chip) e observar 30–60min.
9. Se estável, subir para rodadas de 18–24/dia; limpar 93 em ~4–5 dias conservadoramente ou em ~1 dia se Rafael aceitar volume maior monitorado.

## Mensagens para validação do Rafael

Regra: texto deve soar como recuperação humana de pedido antigo, sem desculpa longa, sem parecer robô e sem prometer que o remetente fará o atendimento. Como os chips são institucionais, usar “vou te direcionar”/“te coloco com o consultor” e registrar o owner original no HubSpot.

### Variante A — direta e chamativa

`Oi, {nome}. Aqui é {remetente}, da Zydon. Vi que ficou pendente seu pedido sobre digitalização de vendas B2B para a {empresa} e não quero deixar isso parado. Faz sentido eu te direcionar para uma análise rápida e objetiva de onde vocês podem ganhar venda on-line no B2B?`

### Variante B — recuperação de cadastro antigo

`Oi, {nome}, tudo bem? Aqui é {remetente}, da Zydon. Estou revisando alguns cadastros que ficaram sem retorno e vi o da {empresa}. Pelo perfil de vocês, pode ter oportunidade boa em venda B2B digital. Posso te mandar para o consultor certo retomar isso com você?`

### Variante C — mais forte / oportunidade perdida

`Oi, {nome}. Aqui é {remetente}, da Zydon. Seu cadastro da {empresa} ficou parado aqui e pode ter passado batido. Antes de arquivar, queria confirmar: vocês ainda querem avaliar como vender mais no B2B com pedido on-line e atendimento mais organizado?`

### Variante D — curta para lead antigo

`Oi, {nome}. Aqui é {remetente}, da Zydon. Vi um pedido antigo da {empresa} sobre nossa plataforma B2B e estou limpando essa fila para não deixar ninguém sem retorno. Ainda faz sentido falar sobre vendas on-line para clientes B2B?`

### Variante E — com contexto ERP quando existir

`Oi, {nome}. Aqui é {remetente}, da Zydon. Vi que a {empresa} tinha solicitado contato sobre digitalização B2B e que vocês usam {erp}. Isso pode facilitar bastante uma conversa mais objetiva. Posso te direcionar para o consultor certo retomar esse diagnóstico?`

### Variante F — sem empresa confiável

`Oi, {nome}. Aqui é {remetente}, da Zydon. Vi que você tinha solicitado contato sobre digitalização de vendas B2B e ficou sem retorno por aqui. Ainda faz sentido te direcionar para uma conversa rápida sobre isso?`

## Rotação de remetente

Para cada lead pronto:

1. Validar portas com `/status` e `/me`:
   - 4607 Rafael Calixto
   - 4600 Mariana \| Zydon
   - 4606 Lucas Resende
2. Escolher a porta menos usada nas últimas 24h no `wpp_envios.json` para esse `campaign_id`.
3. Inserir `{remetente}` conforme conta:
   - 4607: `o Rafael`
   - 4600: `a Mariana`
   - 4606: `o Lucas`
4. Alternar variante por hash determinístico do `deal_id` para manter variedade e idempotência.
5. Se `{erp}` vazio/outro, não usar variante E.

## Marcação obrigatória no HubSpot

Após cada envio com sucesso real do `/send`:

1. Append em `controle/wpp_envios.json`:
   - `msg_type: "primeiro_contato_backlog_institucional"`
   - `campaign_id: "backlog_sarah_lucas_72h_2026_06_24"`
   - `sdr_original: "Sarah" | "Lucas"`
   - `sender_name: "Rafael" | "Mariana" | "Lucas Resende"`
   - `bridge_port: 4607 | 4600 | 4606`
   - `to`, `deal_id`, `contact_id`, `empresa`, `nome`, `text`, `date`
   - `messageId/status` se a bridge retornar.
2. Criar task COMPLETED no HubSpot associada ao contato e ao deal:
   - `hs_task_subject`: `WhatsApp — primeiro contato backlog enviado por {sender_name}`
   - `hs_task_body`: incluir texto enviado, telefone/JID, porta, owner original, campanha e timestamp.
   - `hs_task_status`: `COMPLETED`
   - `hs_task_priority`: `MEDIUM`
   - `hubspot_owner_id`: manter owner original do negócio quando possível.
   - Associações: contato typeId 204, deal typeId 216.
3. Anti-loop futuro deve bloquear tanto `msg_type='primeiro_contato'` quanto `msg_type='primeiro_contato_backlog_institucional'` para o mesmo telefone.

## Implementação em tarefas pequenas

### Task 1: Criar script de auditoria/export

**Objective:** materializar a fila >72h Sarah/Lucas sem enviar nada.

**Files:**
- Create: `scripts/export_backlog_sdr_72h.py`
- Output: `controle/backlog_sarah_lucas_72h.json`

**Verification:** rodar `python3 scripts/export_backlog_sdr_72h.py --dry-run` e confirmar total perto de 93 prontos.

### Task 2: Criar builder de mensagens aprovadas

**Objective:** gerar texto com `{remetente}`, `{nome}`, `{empresa}` e `{erp}` usando variantes aprovadas.

**Files:**
- Create: `scripts/backlog_message_templates.py`

**Verification:** gerar 20 amostras e checar que não há textos idênticos em sequência nem placeholder vazio.

### Task 3: Criar dispatcher institucional dry-run

**Objective:** simular rotação 4607/4600/4606, sem enviar.

**Files:**
- Create: `scripts/disparo_backlog_institucional.py`

**Command:**
`python3 scripts/disparo_backlog_institucional.py --dry-run --limit 9`

**Verification:** deve imprimir lead, porta escolhida, remetente, texto e task que seria criada.

### Task 4: Implementar envio real com fail-stop

**Objective:** enviar somente quando `--send` for passado e parar no primeiro erro por chip.

**Command inicial recomendado:**
`python3 scripts/disparo_backlog_institucional.py --send --limit 9 --max-per-chip-hour 4 --campaign-id backlog_sarah_lucas_72h_2026_06_24`

**Verification:** confirmar `wpp_envios.json` com 9 registros e HubSpot com 9 tasks COMPLETED.

### Task 5: Criar cron manual/monitorado

**Objective:** só depois da primeira rodada validada, criar cron no máximo de hora em hora.

**Cadência:**
- `17 11-20 * * 1-5` UTC, equivalente a 08:17–17:17 BRT.
- `--limit 9` por execução no início.
- `deliver=discord` para acompanhar.

**Verification:** cron silencioso quando não envia; entrega resumo apenas se enviou/erro.

## Critério de sucesso

- Nenhum lead recebe duplicado.
- Toda mensagem enviada tem task no HubSpot dizendo “enviado por Rafael/Mariana/Lucas Resende”.
- Backlog >72h Sarah/Lucas reduz de 93 para 0 ou para “sem telefone/fixo/sem contato”.
- Nenhum chip passa de limite definido e qualquer erro 500/503 pausa a porta automaticamente.
