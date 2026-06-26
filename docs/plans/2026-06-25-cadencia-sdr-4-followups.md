# Cadência SDR 4 Follow-ups Implementation Plan

**Goal:** Transformar o fluxo atual de follow-up pós-diagnóstico MQL em uma cadência SDR completa de 4 mensagens úteis, com movimentação automática de etapas no HubSpot.

**Contexto Rafael 25/06/2026:**
- Follow-ups automáticos são exclusivamente para negócios em `Primeiro Contato`.
- Quando o SDR manda o primeiro follow-up, o negócio deve estar/mover para `Primeiro Contato` (`1214320997`).
- Se o lead responder em qualquer momento, mover para `Retorno Contato` (`998099482`) e parar automação.
- Follow 2, 3 e 4 saem em dias úteis, preferencialmente pela manhã.
- Após o 4º follow sem resposta, mover para `Negócio perdido` (`984052835`).
- Mensagens devem ser personalizadas por negócio, usando dor/ERP/contexto e podendo variar os templates recebidos.

**Estado atual medido:** `Primeiro Contato` tem 274 negócios: Lucas Batista 131, Sarah 105, Breno 37, owner 86020066 1.

## Etapas HubSpot
- `1214320997` — Primeiro Contato
- `998099482` — Retorno Contato
- `984052835` — Negócio perdido

## Arquitetura proposta

Unificar evolução no script existente `scripts/mql_sdr_followup.py`, renomeando mentalmente o cron para motor de cadência SDR. Não criar outro cron paralelo para evitar duplicidade. O mesmo cron `zydon-mql-sdr-followup-5min` roda de 5 em 5 min, mas só dispara quando há candidato e janela útil.

## Regras de cadência

1. Candidatos: somente deals na etapa `1214320997` / Primeiro Contato, owners Sarah/Breno/Lucas Batista, com celular válido e sem resposta após a última mensagem.
2. Follow 1: no dia em que o lead entrar, se estiver em horário de trabalho. Se entrar fora de horário útil, enviar no próximo dia útil.
3. Follow 2: próximo dia útil após Follow 1, preferencialmente de manhã.
4. Follow 3: próximo dia útil após Follow 2, preferencialmente de manhã.
5. Follow 4: próximo dia útil após Follow 3, preferencialmente de manhã.
6. Cada follow precisa educar ou dar direcionamento, pedir ligação ou fazer uma pergunta operacional. Não pode ser só cobrança.
7. Após enviar o Follow 1, registrar como primeira mensagem enviada e garantir que o negócio está em `Primeiro Contato`.
8. Se responder em qualquer momento, mover para `Retorno Contato` (`998099482`) e parar automação.
9. Se os 4 follows foram enviados, não houve resposta/reação, e o negócio ainda está em `Primeiro Contato`, mover para `Negócio perdido` (`984052835`) com `closed_lost_reason = Falta de retorno - Início do funil`.
10. Se o negócio saiu de `Primeiro Contato` por ação humana antes do fim, não mover para perdido automaticamente.

## Tipos de ledger

Usar `controle/wpp_envios.json`:
- `msg_type: mql_sdr_followup`, com `attempt_number: 1..4`
- registrar `deal_id`, `contact_id`, `messageId`, `text`, `sender_name`, `bridge_port`, `dealstage_after_followup`

## Tarefas de implementação

### Task 1 — Adicionar cálculo de dias úteis
Modificar `scripts/mql_sdr_followup.py`:
- criar `is_business_time(now_brt)` para seg-sex, horário de trabalho;
- criar `next_business_day(dt)`;
- criar `business_days_elapsed(start, now)`;
- Follow 1 sai no mesmo dia se o lead entrou em horário útil; se entrou fora, fica para o próximo dia útil;
- Follow 2, 3 e 4 saem em dias úteis subsequentes;
- priorizar disparos de todos os follows pela manhã, sem travar lead novo que entrou em horário útil.

### Task 2 — Contar tentativas por deal/telefone
Modificar `already_followed()` para não bloquear qualquer follow, mas retornar maior `attempt_number` já enviado.
- Se já tem 1, próximo é 2.
- Se já tem 2, próximo é 3.
- Se já tem 3, próximo é 4.
- Se já tem 4, avaliar perda.

### Task 3 — Detectar resposta e mover para Retorno Contato
Reutilizar `incoming_after(jid, after_dt)`.
- Se houver resposta após qualquer mensagem da cadência, chamar PATCH dealstage `998099482`.
- Registrar no ledger ou task: `cadencia_sdr_respondeu`.
- Não enviar nova mensagem.

### Task 4 — Gerar mensagens 1 a 4
Adaptar templates recebidos:
- Dia 1: apresentação/contextualização da dor, ERP, pergunta ligação/WhatsApp.
- Dia 2: prova social/contexto segmento.
- Dia 3: ROI simples usando região/segmento/vendedores/canal, com fallback conservador.
- Dia 4: despedida adaptando dor principal.

As mensagens devem ser geradas por funções, não hard-coded únicas:
- `compose_attempt_1(rec)`
- `compose_attempt_2(rec)`
- `compose_attempt_3(rec)`
- `compose_attempt_4(rec)`

### Task 5 — Enriquecer dados do lead
Buscar contato/deal no HubSpot para campos:
- nome, empresa, ERP
- estado/região se disponível
- número de vendedores se disponível
- dor principal do formulário se disponível
- canal de pedido atual se disponível
- segmento/indústria se disponível

Fallback quando campo vazio:
- dor: “digitalizar a operação comercial sem complicar o que já funciona”
- ERP: “seu ERP” ou omitir integração nativa se desconhecido
- vendedores: 3
- região: MG
- tempo operacional: 60%

### Task 6 — Calcular ROI do Dia 3
Implementar tabela regional e ajuste segmento.
Validar fórmula:
- custo empresa = (salário + comissão ajustada) × 1,7
- custo operacional = custo empresa × percentual tempo
- custo total mês = custo operacional × número vendedores
- custo anual = custo total mês × 12

### Task 7 — Mover etapa após cada evento
- Após Follow 1 confirmado: garantir dealstage `1214320997`.
- Após resposta/reação detectada: mover para `998099482` / Retorno Contato e parar automação.
- Após Follow 4 enviado e janela vencida sem resposta: se o negócio ainda estiver em `1214320997`, mover para `984052835` / Negócio perdido e preencher `closed_lost_reason = Falta de retorno - Início do funil`.
- Se o negócio já saiu de Primeiro Contato por ação humana, não mover para perdido.

### Task 8 — Rate limit e roteamento de chips
Manter limites conservadores:
- SDR chips primeiro: Sarah 4601, Breno 4605, Lucas Batista 4603.
- Se volume grande, adicionar opção futura de comunicadores institucionais com gancho de passagem, mas não ativar sem nova aprovação.
- Máximo inicial recomendado: 2/h por SDR, 12/dia por SDR para cadência, até Rafael liberar volume maior.

### Task 9 — Dry-run antes de produção
Comandos:
```bash
python3 scripts/mql_sdr_followup.py --dry-run --limit 20
python3 scripts/mql_sdr_followup.py --dry-run --owner sarah --limit 20
python3 scripts/mql_sdr_followup.py --dry-run --owner breno --limit 20
python3 scripts/mql_sdr_followup.py --dry-run --owner lucas --limit 20
```
Verificar:
- nenhum lead com resposta entra;
- tentativas corretas;
- datas úteis corretas;
- mensagem tem dor/ERP/contexto;
- sem travessão.

### Task 10 — Execução inicial proposta
Se aprovado, rodar hoje com cap seguro:
- follow atual agora para candidatos vencidos, limite 2 por SDR/h;
- restante entra em janela de manhã nos próximos dias úteis;
- amanhã: follow seguinte para quem não respondeu;
- segunda: próximo follow;
- terça: último follow/despedida e perda dos que completarem 4 sem resposta.

## Verificação final
- Conferir `controle/wpp_envios.json` para tentativas.
- Conferir HubSpot por batch read para etapas.
- Conferir cron `zydon-mql-sdr-followup-5min` status OK.
- Emitir relatório por SDR: enviados, aguardando, respondeu, perdido, bloqueado sem telefone.


## Atualização Rafael — rotação, limpeza do passado e filtro 3 semanas

- Fazer um disparo inicial para limpar o passado antes de operar só a esteira nova.
- Filtrar a limpeza por negócios em `Primeiro Contato` com atividade ou criação nas últimas 3 semanas; negócios sem atividade há mais de 3 semanas estão sendo movidos para perdido por outra ação.
- Contagem ao vivo em 25/06 16:16 BRT: `Primeiro Contato` bruto = 274; com atividade ou criação nas últimas 3 semanas = 218 (Lucas Batista 108, Sarah 78, Breno 31, owner 86020066 1). Recalcular antes de disparar porque a ação de perdido pode reduzir para ~160.
- Prioridade de envio: chips dos SDRs. Se o volume for grande, permitir rotação auxiliar nos comunicadores institucionais 4600/4606/4607 com gancho de passagem: “a consultora/o consultor vai te chamar” ou “a consultora está falando contigo”, sem fingir ser o SDR quando não for.
- Mensagens devem ser hipersegmentadas quando possível: usar contexto de site/segmento/diagnóstico; Claude Code Opus 4.8 pode pesquisar lote pequeno de empresas para gerar abordagem menos genérica.
- Execução inicial recomendada: rodar dry-run com amostra, aprovar texto, disparar em cap seguro por hora, e deixar o restante distribuído em manhãs de dias úteis.
