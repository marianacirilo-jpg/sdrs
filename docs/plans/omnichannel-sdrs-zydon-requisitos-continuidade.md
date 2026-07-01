# Evolução Omnichannel — SDRs Zydon

Data: 2026-07-01
Status: requisitos de continuidade após centralização WhatsApp

## Objetivo executivo
Transformar o painel `sdrs.zydon` em uma central omnichannel operacional para SDRs e gestão, mantendo o WhatsApp como canal principal e auditável, sem expor conversas privadas, grupos ou mensagens que não existam no device.

## Princípios invioláveis
1. **Privacidade por desenho**: conversa entre chips internos, Rafael/Mariana/SDRs/comunicadores, aquecimento e grupos nunca entram no painel comercial.
2. **Origem operacional obrigatória**: só aparece conversa iniciada por automação Zydon ou envio manual pelo painel.
3. **Detalhe fiel ao device**: timeline do detalhe mostra apenas bolhas reais presentes no history/bridge/device; ledger/fila apenas cria card/listagem e enriquece bolha real.
4. **Fila única de saída**: todo envio novo passa pelo worker central `worker_owned`, com completion hook antes de marcar processo como concluído.
5. **Sem duplicidade**: lead único, destino canônico com/sem nono dígito, lock por chip e destino, dedupe por origem/natureza/mensagem.
6. **Sem processo incompleto**: status original só muda depois de entrega confirmada e completion executado.

## Escopo funcional — dia a dia do vendedor
### Inbox operacional
- Cards por lead/conversa operacional.
- Filtro por SDR, chip, etapa, SLA, prioridade, origem e natureza.
- Indicadores: aguardando resposta, precisa ação SDR, enviado por automação, manual pelo painel, respondeu, agendado.
- Sem grupos, broadcast ou contatos internos.

### Detalhe da conversa
- Timeline real do WhatsApp/device.
- Identificação clara de mensagens nossas, mensagens do lead, automação, envio manual e mídia real.
- Badges sem jargão técnico para SDR: “Automação”, “Manual”, “Diagnóstico”, “Follow-up”, “Agenda”.
- Auditoria lateral: origem, worker dispatch id, messageId, completion, tarefa HubSpot, mas sem transformar auditoria em bolha.

### Envio manual pelo painel
- Envio sempre pela fila central `worker_owned` com origem `manual_operacional`.
- Preview com chip escolhido, destino canônico e proteção contra número interno/grupo.
- Status granular: aguardando, enviando, enviado, falhou, completion pendente.

### Auditorias
- Visão por lead: tudo que saiu, quem/qual chip, quando, messageId, tarefa criada, origem.
- Visão por chip: volume/hora/dia, falhas, bloqueios de privacidade, fila atual.
- Visão por automação: agenda, Não-MQL, follow-up, reentrada, diagnóstico, manual.
- Export auditável sem mensagens privadas/grupos.

## Escopo omnichannel futuro
Cada canal novo só entra se tiver:
1. Adaptador de histórico real.
2. Adaptador de envio pela fila central.
3. Identidade canônica do contato.
4. Guarda de privacidade equivalente.
5. Teste de “não inventar mensagem”.

Canais candidatos:
- WhatsApp: produção principal.
- HubSpot: tarefas, notas, deals e reuniões como eventos de auditoria, não como bolhas de chat.
- E-mail: somente se houver caixa operacional vinculada ao lead.
- Ligações/reuniões: eventos de timeline/auditoria, não chat.

## Arquitetura desejada
### Camadas
1. **Identity/Privacy**: `whatsapp_jid_utils.py` e futura `channel_identity.py`.
2. **Dispatch Queue**: `whatsapp_dispatch_queue.py`.
3. **Worker**: `whatsapp_dispatch_worker.py`.
4. **Completion Hooks**: `whatsapp_worker_completions.py`.
5. **History Adapters**: WhatsApp device/history, HubSpot events, futuro e-mail.
6. **Panel API**: `channel_panel_v2.py`.

### Eventos canônicos
Campos mínimos:
- `event_id`
- `channel`
- `direction`
- `contact_key`
- `lead_key`
- `port_or_account`
- `origin`
- `nature`
- `occurred_at`
- `real_message=true/false`
- `message_id`
- `text/media`
- `audit_only=true/false`

## Roadmap recomendado
### Fase 0 — Segurança antes de volume
- Centralizar bloqueio grupo/broadcast/interno.
- Testar worker/flow/painel contra grupos, broadcast e chips internos.
- Bloquear fila/worker para qualquer destino interno.

### Fase 1 — Saídas WhatsApp unificadas
- Agenda: concluído.
- Não-MQL: concluído/ligado.
- Follow-up LSC: migrar uma lane por vez com flag.
- Cadência F2-F4: migrar depois de follow-up LSC validado.
- Reentrada: migrar após completion específico.
- Diagnóstico/PDF: migrar por último, porque envolve mídia/documento.

### Fase 2 — Painel omnichannel operacional
- Status individual de dispatch no card.
- Aba de auditoria por lead.
- Filtros por SLA/natureza/origem.
- Envio manual via fila central.

### Fase 3 — Canais adicionais
- HubSpot events como timeline auditável.
- E-mail/ligação apenas com adaptador real e consentimento operacional.

## Critérios de aceite
- Grupo nunca aparece em `/api/conversations` nem `/api/messages`.
- Contato interno nunca aparece sem origem operacional, e mesmo com origem não vira lead comercial.
- Mensagem não enviada nunca aparece como bolha.
- Todo envio worker-owned tem completion hook ou status explícito de completion skipped.
- Nenhum fluxo legado envia direto quando flag worker-owned estiver ativa.
- Release gate + smoke + browser real antes de promover UI.
