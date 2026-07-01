Você está no repositório /root/.hermes/zydon-prospeccao. Responda em PT-BR.

Contexto do Rafael:
- O sistema de WhatsApp/follow-up está imaturo: poucos disparos, falta clareza de controle, muitos crons e scripts disputando decisão.
- Rafael quer arquitetura centralizada, codificada e sem subjetividade para entrada/saída WhatsApp.
- Amanhã ele vai conectar 2 chips por SDR, depois possivelmente 3+; todo envio precisa escolher o chip correto por regra de negócio central.
- Se já existe conversa com o lead em um chip do SDR, continuar no mesmo chip. Se lead novo, sortear/distribuir entre chips saudáveis daquele SDR. Nunca usar chip de outro SDR.
- O limite atual por quantidade bruta de mensagens está errado: bundle diagnóstico/PDF/pergunta não pode contar como 3 disparos frios; mensagem manual/active conversation não pode cair na mesma categoria de cold automation.
- A UI /rotinas ainda está feia e imatura; precisa virar cockpit executivo/operacional, não parede de cards.

Escopo de leitura principal:
- scripts/whatsapp_safe_send.py
- scripts/whatsapp_routing.py
- scripts/zydon_operational_queues.py
- scripts/disparo_dinamico.py
- scripts/process_gate_once.py
- scripts/channel_panel_v2.py somente trechos de /rotinas e admin chips/users
- /root/.hermes/cron/jobs.json somente nomes/scripts/schedules, sem prompts completos
- docs/architecture/whatsapp-cron-centralizer-audit-2026-06-30.md se existir
- .hermes/plans/2026-06-30_224711-whatsapp-cron-centralizer.md se existir

Tarefa:
Criar um documento de arquitetura executável em:
  docs/architecture/whatsapp-centralizer-architecture-v2-2026-06-30.md

O documento deve conter:
1. Causa raiz da baixa quantidade de follow-up e da falta de controle.
2. Mapa atual dos senders/crons que decidem WhatsApp.
3. Arquitetura-alvo com módulos claros:
   - MessageIntent / natureza
   - ConversationRouter multichip
   - QuotaManager por envio lógico e classe de quota
   - DispatchLedger único com lock
   - CronOrchestrator ou RunCoordinator
   - UI Control Plane (/rotinas)
4. Modelo de dados mínimo para envio lógico:
   - logical_message_id
   - lead_id / phone / jid / conversation_id
   - owner_sdr
   - selected_port
   - nature
   - origin
   - quota_class
   - parts[]
   - quota_counted
   - status
5. Classes de quota recomendadas:
   - cold_automation
   - pipeline_followthrough
   - active_conversation
   - internal
   - warmup/system
6. Regra de contagem:
   - bundle diagnóstico conta como 1 lógico, N partes
   - follow-up F1-F4 conta como cold/pipeline conforme contexto
   - manual reply/active conversation não consome cold quota
   - grupo interno não consome quota de lead
7. Plano de migração em fases pequenas, com arquivos, testes e validação.
8. Riscos operacionais e como evitar duplicidade/envio errado.
9. Proposta objetiva de redesenho da /rotinas: que módulos ficam, que módulos saem, layout, data grids, botões e KPIs que realmente importam.
10. Critérios de aceite para Rafael: como saber que ficou maduro.

Restrições:
- Não edite código neste trabalho; somente leia e escreva o documento de arquitetura.
- Não rode promote/deploy.
- Não reinicie bridges/chips/painéis.
- Não leia prompts completos de cron nem segredos.
- Não envie WhatsApp.
- Se não conseguir concluir, escreva no documento o que foi visto e o que faltou.

Validação:
- Ao final, liste no próprio documento os arquivos lidos e as suposições.
