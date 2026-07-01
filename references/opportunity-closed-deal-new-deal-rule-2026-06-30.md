# Regra Rafael — Opportunity com negócio fechado

Data: 2026-06-30

Quando um contato/lead estiver com `lifecyclestage = opportunity`, mas todos os negócios associados estiverem fechados/perdidos (`hs_is_closed = true`, especialmente etapa `984052835` / Perdido), o fluxo NÃO deve tratar como Não-MQL nem reaproveitar o negócio fechado.

## Ação obrigatória

1. Verificar negócios associados ao contato no HubSpot.
2. Se não houver nenhum negócio aberto no pipeline principal:
   - criar novo negócio no pipeline `671008549`;
   - colocar na primeira etapa `984052829` / Lead Sem Contato;
   - atribuir ao SDR responsável/owner do fluxo;
   - associar o novo negócio ao contato;
   - criar tarefa para o SDR responsável revisar diagnóstico e fazer follow-up;
   - registrar auditoria no ledger operacional.
3. Depois disso, seguir diagnóstico/follow-up usando o novo negócio aberto.

## Caso que originou a regra

Dinlog / GrupoDin — contato `gru.vcp.santos@grupodin.com.br` estava como `opportunity`, mas o negócio associado `52224338861` estava fechado/perdido. Foi criado novo negócio `61931151982` em `984052829` e task `112125684005` para Lucas Batista.
