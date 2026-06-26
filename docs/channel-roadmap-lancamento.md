# Zydon Channel — Roadmap de Lançamento

> Atualizado em 2026-06-24. PO/tester: Hermes. Implementação: Claude Code sob validação Hermes.

## Norte do produto

O Channel precisa substituir o uso diário de WhatsApp físico/Web pelos SDRs sem virar CRM paralelo. A experiência principal é:

**lead → conversa WhatsApp → contexto HubSpot → próxima ação → registro/auditoria.**

Chip/conexão existe como suporte operacional secundário. Segurança, HubSpot e adoção comercial são requisitos de lançamento, não “nice to have”.

## Benchmarks de mercado considerados

Padrões de Respond.io, Trengo, WATI, Front, Intercom e HubSpot Conversations:

- Inbox compartilhada multiagente.
- Atribuição/roteamento de conversas.
- Notas internas e status de conversa.
- CRM integrado no contexto da conversa.
- Quick replies e respostas com IA.
- Upload de arquivos/imagens/áudio.
- Analytics de tempo de resposta, resolução e performance por agente.
- Segurança/SSO/controle de acesso.
- Automação com limites, logs e governança.

## Estado atual validado

### Já feito

- V2 premium rodando local em `127.0.0.1:8791`.
- UI estilo WhatsApp Web + HubSpot lateral.
- Dark mode e light/calm mode.
- Auth Google/OIDC/Cloudflare Access implementado no código.
- API sem login retorna 403.
- Token antigo na URL não autentica por padrão.
- Túneis públicos pausados por segurança.
- Watchdog mantém V2 local vivo.
- Heartbeat de segurança a cada 15min.
- HubSpot read-only real na lateral.
- Upload/anexo pela UI implementado estruturalmente.
- Proteção contra duplo envio por Enter/delay.
- Dedup visual de automação/mensagem.
- Correção visual de `@lid`/JID bruto.
- Dashboard de carga por SDR.
- Seleção em massa estrutural com ações perigosas bloqueadas.

### Bloqueadores para URL pública do time

1. Domínio fixo, ideal: `channel.zydon.com.br`.
2. Cloudflare Access ou Google OAuth com:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `CHANNEL_PUBLIC_BASE_URL=https://channel.zydon.com.br`
3. Named tunnel Cloudflare ou proxy equivalente.

Enquanto isso não estiver pronto: **não expor link público.**

## Roadmap executivo

### R0 — Segurança e fundação de lançamento

Objetivo: liberar acesso público seguro sem regressão.

| Prioridade | Item | Status | Dono | Aceite |
|---|---|---|---|---|
| P0 | Domínio `channel.zydon.com.br` | Bloqueado Rafael/infra | Rafael/infra | DNS aponta para Cloudflare/named tunnel |
| P0 | Cloudflare Access ou Google OAuth | Bloqueado Rafael/infra | Rafael/infra + Hermes | Só `@zydon.com.br` acessa |
| P0 | Named tunnel fixo | A fazer | Hermes | URL não muda em restart |
| P0 | Despausar túnel público | A fazer depois do auth | Hermes | `/` exige login; APIs 403 sem auth |
| P0 | Smoke test público | A fazer depois do auth | Hermes | Rafael entra com Google e vê tudo |

### R1 — Inbox operacional mínima para SDR

Objetivo: SDR trabalhar no Channel o dia inteiro sem abrir WhatsApp físico.

| Prioridade | Item | Tarefa Kanban | Aceite |
|---|---|---|---|
| P0 | Persistir estado de conversa | CH-010 | Resolver/pendente/nota interna sobrevivem restart |
| P0 | Notas internas | CH-010/031 | Nota fica visível no Channel e/ou HubSpot |
| P0 | Quick replies por SDR | CH-012 | SDR responde rápido com templates por cenário |
| P0 | Fila “Responder agora” refinada | CH-008 | Só respostas reais recentes entram no topo |
| P0 | Teste ponta-a-ponta | CH-013 | Texto, anexo, resposta recebida, chip offline, sem permissão |
| P1 | Admin usuários/chips | CH-064 | Rafael vincula email a chips sem editar JSON |

### R2 — HubSpot como fonte de integridade

Objetivo: o Channel não criar CRM paralelo e ajudar a cumprir a rotina comercial.

| Prioridade | Item | Tarefa Kanban | Aceite |
|---|---|---|---|
| P0 | Criar task no HubSpot pela conversa | CH-031 | Task associada a contato e negócio |
| P0 | Criar nota no HubSpot pela conversa | CH-031 | Nota com texto e link da conversa |
| P0 | Reunião/agenda visível | CH-032 | Painel mostra reunião marcada e owner correto |
| P0 | Ações em massa com prévia | CH-034 | Selecionar leads → prévia → task/nota no HubSpot |
| P1 | Histórico HubSpot+WhatsApp unificado | novo CH-036 | Timeline form → diagnóstico → mensagem → resposta → task |
| P1 | Auditoria de escrita | novo CH-037 | Log local de quem fez o quê, quando, em qual lead |

### R3 — Gestão de automações e prioridades

Objetivo: Rafael enxergar se as automações estão funcionando e onde há risco/perda.

| Prioridade | Item | Tarefa Kanban | Aceite |
|---|---|---|---|
| P0 | Status diagnóstico/1º contato/follow-up | CH-035 | Feito, pendente, falhou, aguardando resposta |
| P0 | Alertas de falha de automação | CH-035 | Falha sobe fila e aparece para admin |
| P1 | SLA por conversa | novo CH-036 | “há X min sem resposta” e ranking por urgência |
| P1 | Carga por SDR com pendências | CH-025 evoluir | Admin vê backlog acionável, não só contagem |

### R4 — Múltiplos chips sem dor operacional

Objetivo: SDR não precisar saber qual chip usar; admin enxerga risco de escala.

| Prioridade | Item | Tarefa Kanban | Aceite |
|---|---|---|---|
| P1 | Teste real de QR no painel | CH-005 | Usuário conecta chip sem Discord |
| P1 | Score de saúde do chip | CH-040 | Volume/dia, falhas, respostas, desconexões |
| P1 | Recomendação de novo chip | CH-041 | Sugere quando volume/risco ultrapassa limite |
| P1 | Roteamento inteligente | CH-042 | Se Breno tem 2 chips, sistema escolhe saudável |
| P1 | Teste Breno 2 chips | CH-043 | Conversa única, fallback sem bagunça |

### R5 — IA comercial útil, depois da operação sólida

Objetivo: acelerar resposta sem perder tom Zydon nem integridade.

| Prioridade | Item | Tarefa Kanban | Aceite |
|---|---|---|---|
| P2 | Resumo automático | CH-050 | Resumo fiel da conversa e próximo passo |
| P2 | Sugestão de resposta | CH-051 | Tom Zydon, contexto HubSpot, sem jargão |
| P2 | Transcrição de áudio | CH-052 | Áudio recebido vira texto pesquisável |
| P2 | Avaliação de qualidade | CH-053 | 20 exemplos reais, taxa de acerto aceitável |

### R6 — Plataforma robusta

Objetivo: sair de painel Python/JSON para produto sustentável.

| Prioridade | Item | Aceite |
|---|---|---|
| P2 | SQLite/Postgres para estado | Conversas, notas, status, auditoria versionados |
| P2 | SSE/WebSocket | Atualização em tempo real sem refresh/poll pesado |
| P2 | Retenção e backup formal | Dados sincronizados com Drive/backup seguro |
| P2 | Rate limit por usuário/chip | Evita blast acidental |
| P3 | Avaliar WhatsApp Business API oficial | Caminho de escala se chips físicos ficarem frágeis |

## Ordem de execução recomendada agora

### Se o objetivo é liberar o time rápido

1. Resolver domínio/auth: R0.
2. Implementar `CH-010` estado persistente + notas.
3. Implementar `CH-031` task/nota HubSpot.
4. Refinar `CH-008` fila Responder agora.
5. Fazer `CH-013` teste ponta-a-ponta com 1 SDR.
6. Liberar piloto para Rafael + 1 SDR.
7. Só depois abrir para todos.

### Se o objetivo é evoluir sem depender do domínio agora

1. `CH-010` persistência local.
2. `CH-031` HubSpot write.
3. `CH-008` prioridade real.
4. `CH-035` status das automações.
5. `CH-012` quick replies.

## Definição de “pronto para piloto”

- Acesso público exige login `@zydon.com.br`.
- SDR consegue responder texto e anexar arquivo.
- Lead que respondeu aparece no topo.
- HubSpot lateral mostra contato/deal/owner/stage corretamente.
- Criar tarefa/nota no HubSpot funciona.
- Resolver/pendenciar conversa persiste.
- Admin vê carga por SDR.
- Sem JID/porta/`@lid` na visão principal.
- Sem duplo envio por Enter.
- Watchdog e heartbeat ativos.

## Definição de “pronto para time inteiro”

- Piloto validado com Rafael + pelo menos 1 SDR por 1 dia útil.
- QR/conexão resolvido pelo painel.
- Ações em massa com prévia e log.
- Alertas de falha de automação.
- Admin usuários/chips pela UI.
- Backup e auditoria revisados.
- Roadmap de WhatsApp API oficial decidido: manter chips ou migrar gradualmente.

## Próxima tarefa técnica indicada

**CH-010 + CH-031 em sequência.**

Motivo: sem persistir estado/notas e sem escrever task/nota no HubSpot, o Channel ainda é inbox. Com isso, vira ferramenta de execução comercial e mantém integridade do CRM.
