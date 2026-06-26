# Zydon Channel — Plano de Evolução Produto/UX

> Objetivo: transformar o Channel de “painel técnico de mensagens” em uma central comercial diária que o time realmente queira usar.

## Diagnóstico honesto do MVP atual

O MVP resolveu a auditoria básica de envios, mas ainda parece ferramenta interna/faculdade porque:

- A experiência gira em torno de logs, não de rotina comercial.
- Falta linguagem de produto: fila, prioridade, dono, SLA, resposta pendente, próxima ação.
- A lista de conversas não guia o SDR para “o que faço agora?”.
- Ainda existe ruído técnico: JID, porta, tipos internos, `@lid`, registros de grupo.
- Não há visão de funil/conversão dentro da conversa.
- Não há confiança visual: pouca hierarquia, pouca densidade útil, pouco acabamento.
- Não tem “sensação de ferramenta premium” como Intercom/Front/Linear.

## Benchmarks estudados

### Respond.io / Trengo / SleekFlow / WATI / Zoko
Padrões relevantes:
- Inbox omnichannel centralizada.
- Atribuição de conversas por agente/time.
- Tags/labels por etapa e intenção.
- Automação de roteamento, follow-up e escalonamento.
- CRM sync e timeline do cliente.
- Analytics de tempo de resposta, taxa de resolução, performance por agente.

### Intercom / Crisp / Zendesk / Freshchat
Padrões relevantes:
- Foco em “conversa + contexto + ação”, não log.
- Perfil do contato sempre visível: dados, eventos, notas internas, próxima ação.
- Resumo de IA, sugestões de resposta e handoff com contexto.
- Mídias nativas: áudio, imagens, documentos, transcrição.
- SLA e status operacional explícito.

### Front / Superhuman / Linear
Padrões relevantes:
- Interface de trabalho rápida, elegante, keyboard-first.
- Filtros salvos, atalhos, busca instantânea, estados claros.
- Baixa fricção para triagem: unread, assigned, pending, done.
- Densidade alta sem parecer poluído.
- Dark UI premium com bordas sutis e tipografia forte.

### Kommo / HubSpot Conversations
Padrões relevantes:
- Conversa conectada ao pipeline comercial.
- Negócio, proprietário, estágio, tarefa e última atividade no mesmo lugar.
- Histórico completo por lead, não por número isolado.
- Próximo passo comercial como entidade principal.

## Princípios do produto Zydon Channel

1. **Commercial-first, not message-first**
   - A unidade principal não é a mensagem; é o lead/conversa com próxima ação.

2. **Inbox confiável para SDR**
   - O SDR abre e sabe: quem respondeu, o que precisa responder, o que está aguardando e o que já foi resolvido.

3. **Menos técnico, mais operação**
   - Porta/chip/JID ficam como metadados; o topo mostra empresa, pessoa, status e ação.

4. **Tudo que o time precisa em uma tela**
   - Conversa, dados do lead, owner, status HubSpot, diagnóstico enviado, PDF, tarefas, notas internas.

5. **Escala com governança**
   - Controle de permissões, auditoria, limites de chip, risco de bloqueio, SLA e performance.

6. **Design premium para adoção**
   - Se o comercial achar feio/confuso, não usa. O produto precisa parecer ferramenta de time moderno.

## Arquitetura de UX recomendada

### Layout desktop v2

**Coluna 1 — Navegação e filas**
- Inbox
- Respondidos / Não respondidos
- Meus leads
- Aguardando cliente
- Aguardando SDR
- Diagnóstico enviado
- Primeiro contato enviado
- Reunião marcada
- Erros de envio / chip offline
- Admin / todos os chips

**Coluna 2 — Lista de conversas**
Cada item deve mostrar:
- Empresa em destaque
- Nome do contato + cargo quando tiver
- Última mensagem, com origem: Lead / SDR / Automação / PDF
- Data/hora relativa e absoluta no hover
- Badge: `respondeu`, `sem resposta`, `MQL`, `1º contato`, `diagnóstico`, `reunião`
- Owner/SDR
- Chip usado
- SLA: “há 12 min sem resposta”, “responder agora”

**Coluna 3 — Conversa**
- Bolhas WhatsApp-like, mas mais limpas.
- Separadores por dia.
- Marcadores de automação: “Diagnóstico enviado”, “PDF enviado”, “Follow-up SDR”.
- Mídias renderizadas: PDF card, imagem, áudio player/transcrição.
- Caixa de resposta com quick replies e IA.

**Coluna 4 — Contexto comercial**
- Empresa / contato / telefone.
- HubSpot owner + deal stage.
- Último evento: diagnóstico, primeiro contato, resposta.
- PDF enviado com link.
- Próxima ação sugerida.
- Notas internas.
- Histórico de automações.
- Saúde do chip.

## Funcionalidades por fase

### Fase 0 — Correção de adoção visual (imediata)
Objetivo: parar de parecer log técnico.

- Redesign visual premium dark, inspirado em Linear + Intercom.
- Esconder JID/porta por padrão.
- Lista ordenada por última mensagem.
- Filtros: Todos, Responder agora, Sem resposta, Diagnóstico, 1º contato, Por SDR.
- Cards de conversa com empresa, contato, hora, status, owner, última mensagem.
- Painel direito com contexto comercial.
- Empty states decentes: “Nada para responder agora”.

### Fase 1 — Inbox operacional para SDR
Objetivo: comercial usar no dia a dia.

- Login/link definitivo por usuário.
- Filas por usuário: `Minhas respostas`, `Aguardando cliente`, `Automação enviada`, `Resolvidas`.
- Marcar conversa como resolvida/pendente.
- Notas internas.
- Atribuir/transferir conversa.
- Quick replies por SDR.
- Busca por empresa, contato, telefone, email.
- Upload de PDF/imagem/áudio pela UI.

### Fase 2 — CRM e HubSpot profundo
Objetivo: parar de alternar entre WhatsApp e HubSpot.

- Puxar dados do contato/deal em tempo real.
- Mostrar lifecycle, owner, deal stage, reunião, tasks.
- Criar task no HubSpot pela conversa.
- Atualizar owner/status/follow-up no HubSpot.
- Timeline unificada: form → diagnóstico → PDF → resposta → tarefa → reunião.
- Deduplicação visual de mesmo lead em chips diferentes.

### Fase 3 — IA comercial
Objetivo: aumentar velocidade e qualidade da resposta.

- Resumo automático da conversa.
- Sugestão de próxima resposta no tom Zydon.
- Classificação de intenção: interessado, dúvida, preço, reunião, fora do ICP, suporte.
- Transcrição de áudio recebido.
- Extração de dados de imagem/documento.
- Detecção de lead quente e alerta para SDR.
- Recomendação de agenda/consultor correto.

### Fase 4 — Analytics e gestão
Objetivo: Rafael gerir escala.

- Dashboard por SDR: respostas, tempo médio, leads sem retorno, reuniões geradas.
- Conversão por automação: diagnóstico vs primeiro contato.
- Saúde por chip: volume/dia, respostas, erros, risco de bloqueio.
- SLA: conversas aguardando > X min.
- Heatmap por horário/canal.
- Auditoria de mensagens enviadas por automação.

### Fase 5 — Plataforma robusta
Objetivo: escalar sem gambiarra.

- Domínio fixo: `channel.zydon.com.br`.
- Auth real com usuário/senha/SSO ou magic link.
- Banco SQLite/Postgres em vez de JSON solto.
- Jobs idempotentes de importação.
- WebSocket/SSE para atualização em tempo real.
- Backup e retenção.
- Rate limits e permissões.
- Migração futura para WhatsApp Business API oficial se necessário.

## Roadmap sugerido

### Sprint 1 — Redesign e usabilidade básica
- Nova UI premium.
- Filtros e filas.
- Context panel comercial.
- Remover ruído técnico.
- Melhor mobile/tablet.

### Sprint 2 — Operação SDR
- Resolver/pendenciar.
- Notas internas.
- Quick replies.
- Upload de arquivos.
- Separar respostas reais de automação.

### Sprint 3 — HubSpot no painel
- Perfil/deal em tempo real.
- Criar task e registrar atividade.
- Mostrar agenda/owner/stage.
- Próxima ação.

### Sprint 4 — IA e gestão
- Resumo e sugestão de resposta.
- Transcrição de áudio.
- Dashboard de SLA/performance.

## Critérios de sucesso

- SDR entende em 5 segundos o que precisa responder.
- Rafael consegue auditar todos os chips sem abrir WhatsApp.
- Conversas com resposta de lead aparecem no topo automaticamente.
- Time para de pedir “cadê a mensagem?” ou “foi enviado?”.
- O painel vira rotina, não ferramenta de conferência.

## Direção visual recomendada

- Base: Linear/Superhuman para dashboard premium dark.
- Comportamento conversacional: Intercom/Crisp.
- Identidade Zydon: preto profundo + verde #CDEB00, usado com parcimônia.
- Densidade: alta, mas com hierarquia clara.
- Remover aparência de tabela/log.
