Você está no repositório /root/.hermes/zydon-prospeccao. Responda em PT-BR.

Contexto do Rafael:
- Ele quer centralizar de uma vez os crons/envios WhatsApp Zydon.
- Hoje há vários crons/scripts competindo: diagnóstico, agenda, primeiro contato, follow-up, Não-MQL, respostas, guardiões.
- Problema de arquitetura: cada caminho manda WhatsApp de um jeito, registra ledger de um jeito e aplica limites de forma inconsistente.
- Problema de produto: limites atuais parecem contar quantidade bruta de mensagens, sem distinguir conversa/manual/automação/natureza/destinatário. Mensagem manual ou conversa em andamento não pode cair na mesma categoria de disparo automatizado frio.
- Rafael quer organizar desde diagnóstico até agenda marcada, com natureza/origem correta para o painel e para limites.

Tarefa: faça uma auditoria READ-ONLY e escreva o relatório em `docs/architecture/whatsapp-cron-centralizer-audit-2026-06-30.md`.

Leia primeiro estes arquivos:
- `scripts/whatsapp_safe_send.py`
- `scripts/zydon_operational_queues.py`
- `scripts/channel_panel_v2.py` apenas onde monta `/rotinas`, `/agendas`, `/api/rotinas/summary`, `/api/agendas`, dispatch/follow-up stats
- `disparo_dinamico.py`
- `disparo_primeiro_contato.py`
- `scripts/cadencia_primeiro_contato.py`
- `scripts/mql_sdr_followup.py`
- `scripts/process_gate_once.py`
- `scripts/agenda_queue_sender.py`
- `scripts/active_mql_qualifier.py`
- `scripts/non_mql_legit_outreach.py`
- `scripts/monitor_diagnostico_agendado.py`
- `/root/.hermes/scripts/zydon_sdr_followup_unificado_5min.sh`
- `/root/.hermes/scripts/zydon_sdr_followup_unificado_guard.sh`
- `/root/.hermes/scripts/zydon_agenda_queue_sender.sh`
- `/root/.hermes/scripts/zydon_active_mql_qualifier.sh`
- `/root/.hermes/scripts/zydon_mql_sdr_followup.sh`
- `/root/.hermes/scripts/zydon_cadencia_primeiro_contato_all.sh`
- `/root/.hermes/cron/jobs.json`

Não edite código. Não rode comandos destrutivos. Não reinicie bridges, crons, painéis, nem mande WhatsApp. Pode usar `Read`, `Bash` somente para inspeção read-only (`grep`, `python -m py_compile` se quiser, listar jobs, ler JSON). Pode usar `Write` apenas para criar o relatório final.

O relatório deve conter:
1. Mapa dos crons ativos e pausados relevantes para WhatsApp, agrupados por jornada:
   - Entrada/MQL/diagnóstico
   - agenda/diagnóstico agendado
   - primeiro contato
   - follow-up F1-F4
   - Não-MQL
   - respostas/conversas
   - monitores/guardiões
2. Mapa dos caminhos reais de envio WhatsApp:
   - arquivo/script
   - função principal
   - usa ou não `whatsapp_safe_send`
   - escreve onde no ledger/fila
   - quais status/msg_type/campaign_id usa
   - quais limites aplica
3. Conflitos arquiteturais encontrados:
   - múltiplos locks
   - múltiplos ledgers/helpers de append
   - limites por mensagem bruta versus por conversa/destinatário/natureza
   - crons antigos que devem continuar `PAUSADO-NAO-REATIVAR`
   - risco de mesma pessoa receber por caminhos diferentes
4. Proposta de modelo único de natureza/origem de mensagem:
   - `nature`: manual_reply, diagnostic_initial, diagnostic_pdf, diagnostic_agenda_invite, agenda_confirmation, agenda_reminder, first_contact, followup_f1, followup_f2, followup_f3, followup_f4, non_mql_outreach, no_show_recovery, internal_group_alert, system_monitor, warmup, premeeting_summary etc.
   - `origin`: manual_channel, cron_active_mql, cron_followup_unificado, cron_agenda_queue, cron_non_mql, cron_incoming_response, user_manual_script, watchdog etc.
   - `thread_state`: cold_outreach, active_conversation, post_diagnostic, scheduled_meeting, no_show, opt_out, internal_only
5. Proposta de limite correto:
   - separar quota de `cold/prospecting automation` de mensagens em conversa ativa
   - não contar manual SDR/Rafael da mesma forma que automação fria
   - contar por destinatário/conversa/dia e por chip, não só por número bruto de partes/split messages
   - distinguir mensagem composta/split de um único envio lógico
6. Plano de centralizador:
   - novo módulo ou extensão sugerida, com nomes de arquivos e APIs: por exemplo `scripts/whatsapp_send_orchestrator.py`, `scripts/whatsapp_message_nature.py`, `scripts/whatsapp_quota_manager.py`, ou alternativa se preferir
   - como cada sender migraria para `enqueue/send_request` único
   - como a UI `/rotinas` deveria mostrar data grid/action buttons para operar filas
7. Plano de migração em fases pequenas, com testes por fase e rollback.
8. Perguntas abertas/decisões que precisam do Rafael.

Formato: markdown claro, executivo e técnico. Use tabelas. Seja específico com caminhos reais. Não diga genericamente “centralizar”; diga exatamente onde e como.
