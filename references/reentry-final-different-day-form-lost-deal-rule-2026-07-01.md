# Correção final — reconversão válida para recuperar diagnóstico

Data: 2026-07-01

Rafael refinou o critério: o objetivo é recuperar apenas leads que entraram no passado, tiveram negócio perdido/fechado, e depois mudaram de ideia/preencheram novamente campanha/formulário em outro dia.

Critério final para enfileirar diagnóstico/recriar negócio:

1. Mesmo contato antigo (`contact_id` existente).
2. `recent_conversion_date` em dia BRT diferente do `createdate` do contato.
3. Evento deve ser `form_or_ad`: formulário, anúncio, site/landing/demonstração.
4. Deve haver negócio vinculado perdido/fechado (`hs_is_closed=true`, ex. `984052835`).
5. Não deve haver diagnóstico/PDF já registrado.
6. Se já existe negócio aberto pós-reconversão, NÃO criar outro; apenas enfileirar diagnóstico.
7. Se não existe negócio aberto, criar novo negócio em `984052829` + task HIGH.
8. MQL sim; SQL não.
9. Excluir meeting link por padrão deste backfill; meeting não é “preencheu anúncio novamente”.
10. Excluir conversões no mesmo dia BRT da criação inicial; isso não é mudança posterior de ideia.

Estado após correção:
- Fila final: 98 leads.
- 98 = form/ad/site em dia BRT diferente + negócio perdido vinculado + sem diagnóstico.
- Excluídos: 54 meeting links e 2 form/ad no mesmo dia BRT; também já excluídos open-only sem negócio perdido.

Crons corrigidos/validados:
- `zydon-reentry-diagnostic-drip-10min` envia somente a fila de 98.
- `zydon-reentry-recovery-watch-15min` agora exige form/ad/site + dia BRT diferente + closed_deals antes de criar/enfileirar.
