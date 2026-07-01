# Regra Rafael — reconversão perdida sempre recupera negócio e diagnóstico

Data: 2026-07-01

Regra operacional daqui para frente:

1. Qualquer contato antigo que reconverter (`recent_conversion_date > createdate + 5 minutos`) por formulário, anúncio/site ou meeting link deve ser tratado como oportunidade comercial recuperável, salvo teste/fake/interno/customer.
2. Se a reconversão não tiver negócio aberto, criar novo negócio aberto na primeira etapa do pipeline:
   - Pipeline: `671008549`
   - Etapa: `984052829` / Lead Sem Contato
   - Não marcar `e_sql = sql` automaticamente; o correto é MQL no contato + negócio aberto para SDR qualificar.
   - Owner: SDR atual/histórico; se ausente, distribuir em rotação Sarah/Breno/Lucas.
3. Criar task HIGH para o SDR quando criar o negócio.
4. Toda reconversão válida entra na fila de envio de diagnóstico, com dedupe forte antes do envio.
5. Dúvida/pending_review vira MQL por padrão; só desqualificar claramente teste/fake/sem empresa/sem estrutura real.
6. Diagnóstico em lote deve ser enviado devagar e sempre: 1 por ciclo, com rotação/quota dos chips, sem disparo em massa.

Crons/scripts:
- Watcher futuro: `zydon-reentry-recovery-watch-15min` (`d635016b904e`) roda `~/.hermes/scripts/zydon_reentry_recovery_watch.py` a cada 15 min.
- Drip de diagnóstico: `zydon-reentry-diagnostic-drip-10min` (`75ea2c207a3e`) roda `~/.hermes/scripts/zydon_reentry_diagnostic_drip_20260701.py` a cada 10 min, 06h-20h BRT.
- Fila atual: `controle/audits/reentry_diagnostic_drip_queue_20260701.json`.
