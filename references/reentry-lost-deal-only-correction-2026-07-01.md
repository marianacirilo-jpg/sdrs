# Correção de regra — reconversão com negócio perdido

Data: 2026-07-01

Correção Rafael:

Não basta ser reconversão e não ter diagnóstico histórico. O critério correto para recuperar automaticamente é:

1. Contato antigo reconverteu de verdade (`recent_conversion_date > createdate + 5min`).
2. Evento veio de formulário/anúncio/site ou meeting link.
3. O contato tem negócio vinculado que estava PERDIDO/fechado (`hs_is_closed=true`, ex. stage `984052835`).
4. Ainda não tem diagnóstico/PDF registrado.

Ação:
- Se já existe negócio aberto pós-reconversão: NÃO criar outro; apenas enfileirar diagnóstico.
- Se não existe negócio aberto e existe negócio perdido/fechado vinculado: criar novo negócio em `984052829`, criar task HIGH para SDR, e enfileirar diagnóstico.
- MQL sim; SQL não (`e_sql` deve ficar vazio, salvo ação humana/automação específica posterior).
- Não reviver lead/negócio morto que não teve reinscrição real.
- Não enfileirar casos “open-only” que apenas têm negócio aberto e nenhum negócio perdido vinculado.

Estado corrigido em 2026-07-01:
- Fila anterior de 191 foi filtrada para 154 casos corretos.
- 36 casos open-only foram removidos da fila de diagnóstico de reentry.
- 154 = reconversão real + negócio perdido vinculado + sem diagnóstico.
- Breakdown: 100 form/ad/site; 54 meeting link.

Crons:
- `zydon-reentry-diagnostic-drip-10min` usa a fila filtrada.
- `zydon-reentry-recovery-watch-15min` foi corrigido para exigir `closed_deals` antes de criar/enfileirar.
