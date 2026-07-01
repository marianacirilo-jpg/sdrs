# Claude Code Task Pack — Zydon Channel Growth / PO backlog

Gerado por Hermes/Dexter em 2026-06-29T16:30:57Z.

## Contexto do produto

Produto: `sdrs.zydon.com.br` / Zydon Channel V2.
Usuários: 20+ SDRs/supervisores usando em produção.
Objetivo operacional: aumentar conversão real no funil `mensagem enviada → resposta → agenda → agenda realizada`.

## Regras invioláveis

1. NÃO editar/reiniciar produção diretamente.
2. NÃO matar/subir `8280`/`8791` manualmente.
3. NÃO reiniciar WhatsApp bridges/chips.
4. NÃO alterar auth, QR, cookies, secrets, `controle/wpp_envios.json` ou dados de produção.
5. NÃO executar `promote` nem `deploy` sozinho.
6. Pode editar somente:
   - `scripts/channel_panel_v2.py`
   - `tests/test_channel_v2_core.py`
   - `tests/channel_v2_smoke_gate.py`
   - documentação em `docs/`
7. Antes de finalizar, obrigatoriamente rodar:
   - `python3 -m py_compile scripts/channel_panel_v2.py tests/channel_v2_smoke_gate.py`
   - extrair JS e `node --check`
   - `python3 -m unittest tests.test_channel_v2_core -v`
   - `scripts/channel_v2_safe_deploy.sh stage`
8. Reportar o release dir gerado pelo stage. Hermes/Dexter decide promoção pública.

Leia também:
- `CLAUDE.md`
- `docs/channel-safe-deploy-runbook.md`
- skill/reference: `zydon-channel-ui`

## Dados reais atuais usados para priorização

Leitura pública autenticada em 2026-06-29:

- `/api/dispatch-stats`: 831 envios analisados.
- `followupPerformance`: 831 envios, 92 retornos, 38 abordagens/versionamentos.
- `lossRanking` atual:
  - Responderam e não agendaram: 77.
  - Agendaram e ainda não viraram realizada/status final: 58.
  - Sem resposta depois de follow-up: 2.
- `/api/pipeline/focus`: 454 negócios no HubSpot.
  - Primeiro Contato: 253.
  - Retorno Contato: 64.
  - Diagnóstico SDR: 13.
  - No Show: 124.
- Por owner:
  - Lucas Batista: 231 negócios.
  - Sarah: 149 negócios.
  - Breno: 74 negócios.
- Sinal de gargalo forte: abordagem `Primeiro contato` versão 29/06 tem 99 envios e apenas 1 retorno (~1%).
- Sinal de operação: agendas sem outcome final aparecem como gargalo; agenda realizada só deve contar com confirmação HubSpot.

## Hipótese de PO

O maior ganho agora não é criar mais gráfico; é transformar a Gestão/Foco em uma esteira diária de execução:

1. mostrar exatamente quais leads precisam de ação hoje;
2. separar gargalo por tipo de perda;
3. tornar óbvio para o SDR/supervisor o próximo movimento;
4. medir se a ação virou resposta, agenda ou realizada.

## Atividades priorizadas para Claude Code

### P0-1 — Foco SDR: “Ações de hoje” com SLA e motivo

**Problema**
Hoje o Foco mostra pipe e fila de resgate, mas ainda não força uma rotina diária clara. O SDR precisa saber: quem eu tenho que atacar agora, por quê, e qual é a próxima ação.

**Escopo**
Adicionar bloco no `/foco` chamado `Ações de hoje`, acima ou próximo da fila de resgate.

Categorias sugeridas:

1. `Responder agora` — lead respondeu e não teve próxima ação registrada.
2. `Converter para agenda` — lead respondeu, mas não há reunião associada.
3. `Confirmar diagnóstico` — há reunião futura sem confirmação/lembrete recente.
4. `Resolver no-show` — negócio está em No Show ou reunião passada sem outcome concluído.
5. `Sem movimento` — negócio parado por X horas/dias conforme stage.

**Dados permitidos**
Usar dados já lidos por `/api/pipeline/focus`, `/api/dispatch-stats` e conversas existentes. Não enviar mensagem, não gravar em HubSpot.

**UI**
Cards escuros, humanos, sem termos técnicos. Cada item deve ter:
- empresa/deal;
- dono/SDR;
- motivo simples;
- tempo/SLA;
- botão `Abrir conversa` ou `Abrir HubSpot` quando link existir.

**Critérios de aceite**
- `/foco` contém `Ações de hoje`.
- Não aparece texto técnico: `audit`, `ledger`, `debug`, `fonte`, `evento técnico`.
- Cards limitados para performance mobile (ex.: top 20 + ver mais).
- Teste em `tests/test_channel_v2_core.py` validando presença do bloco e limites.
- Stage 8891 validado.

### P0-2 — Gestão: ranking acionável de perdas por SDR

**Problema**
Já existe perda geral, mas supervisor precisa saber quem está perdendo onde: Sarah/Lucas/Breno e em qual etapa.

**Escopo**
Adicionar ao `/api/dispatch-stats` e UI `/gestao` um ranking por SDR/owner:

- `Respondeu e não agendou` por SDR.
- `Agendou e não realizou/sem outcome` por SDR.
- `Sem resposta` por SDR e abordagem.

**UI**
Bloco `Perdas por SDR` com top gargalo e contagem. Exemplo de copy:

- `Lucas Batista · 18 responderam sem agenda`
- `Sarah · 12 agendas sem status final`

**Critérios de aceite**
- Endpoint expõe `lossRanking.byOwner` ou equivalente.
- UI mostra ranking humano por SDR.
- Deve preservar `lossRanking.items` atual para não quebrar UI existente.
- Teste unitário cobre novo objeto e HTML.

### P0-3 — Gestão: alerta de baixa performance por versão de abordagem

**Problema**
Primeiro contato versão 29/06 tem 99 envios e 1 retorno (~1%). Isso precisa saltar aos olhos como alerta, não ficar escondido em card.

**Escopo**
Criar bloco em `/gestao`: `Abordagens para revisar`.

Regra inicial:
- mínimo de amostra: >= 20 envios;
- alerta se resposta < 5% ou agenda < 2%;
- mostrar versão/data, tipo, enviados, respostas, agendas e exemplo de mensagem.

**UI**
Não usar tom alarmista; usar linguagem PO/comercial:
- `Revisar abertura`
- `CTA fraco para resposta`
- `Boa resposta, baixa agenda`

**Critérios de aceite**
- Primeiro contato versão 29/06 aparece se continuar com 99/1.
- Teste unitário cobre regra de amostra mínima.
- Não criar card por personalização individual; agrupar por abordagem + versão.

### P1-1 — Gestão/Foco: agenda outcome center

**Problema**
Há 58 agendas sem confirmação de realizada. Sem outcome no HubSpot, a operação não sabe se o gargalo é presença, no-show ou falta de atualização.

**Escopo**
Bloco `Status das agendas` com:
- futuras;
- realizadas confirmadas;
- passadas sem outcome;
- no-show/canceladas.

Mostrar por SDR e por abordagem de origem.

**Critérios de aceite**
- Agenda realizada só conta com outcome HubSpot concluído.
- Passadas sem outcome aparecem como `Atualizar status da reunião`, não como realizada.
- Teste cobre que reunião futura não entra como realizada.

### P1-2 — Foco SDR: drill-down da fila de resgate

**Problema**
A fila de resgate precisa ser operacional, não só painel.

**Escopo**
Ao clicar em categoria da fila, abrir lista filtrada com top leads reais e o motivo.

**Critérios de aceite**
- Não carregar centenas de itens no DOM mobile; limite inicial 50/80.
- Botão abre conversa/HubSpot.
- Sem envio automático.

### P2 — Experimentos campeão/desafiante

**Problema**
Rafael altera textos de follow-up; precisa comparar versão antiga vs nova sem misturar taxa.

**Escopo**
Criar seção `Campeão vs desafiante` por tipo de abordagem/versionamento.

Critérios:
- mostrar somente quando as duas versões têm amostra mínima;
- avisar `amostra insuficiente` quando não houver base;
- comparar resposta, agenda e realizada.

## Ordem de execução recomendada

1. P0-1 — `Ações de hoje` no Foco.
2. P0-2 — `Perdas por SDR` na Gestão.
3. P0-3 — `Abordagens para revisar` na Gestão.
4. P1-1 — `Status das agendas`.
5. P1-2 — drill-down da fila.
6. P2 — campeão/desafiante.

## Entrega esperada do Claude Code

Ao finalizar, escrever relatório em:

`docs/claude-tasks/channel-po-growth-20260629T163057Z-report.md`

Com:
- tarefas implementadas;
- arquivos alterados;
- testes rodados e resultado real;
- release dir do `safe_deploy stage`;
- riscos/remanescentes;
- confirmação explícita de que não executou promote/deploy e não tocou bridge/WhatsApp.
