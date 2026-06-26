# Zydon Channel — Kanban de Lançamento

> PO/tester: Hermes. Implementação delegada: Claude Code. Objetivo: comercial resolver 100% da rotina pelo Channel sem acessar telefone físico.

## Regras de produto

1. A tela é para o atendente/comercial, não para o técnico.
2. A hierarquia principal é **lead → conversa → negócio HubSpot → próxima tarefa**, não chip/conexão.
3. O atendente não precisa saber JID, porta, `@lid` ou qual chip técnico usar.
4. Cada usuário entra com email `@zydon.com.br` e vê leads/conversas/chips vinculados.
5. Conexão/chip é suporte operacional secundário: visível quando há problema, mas nunca o foco da tela.
6. Se conexão cair, a pessoa resolve no próprio painel: QR, status, reconectar, pedir novo chip — sem Discord/telefone físico.
7. Rafael/admin tem visão de escala: volume por chip, risco de bloqueio, necessidade de aumentar chips, performance SDR.
8. HubSpot precisa aparecer como contexto comercial central: lead, contato, owner, etapa, negócio, agenda/tarefa.
9. O SDR precisa ver e fazer pelo Channel: ler mensagens, responder, enviar arquivos/PDFs, ouvir/enviar áudios, ver status da conexão, conectar outro chip se necessário.
10. A tela será usada o dia inteiro: precisa ter **dark mode e light/calm mode**, baixa fadiga visual, densidade controlada e leitura tranquila.
11. A integridade operacional vem do HubSpot: não criar “CRM paralelo”; o Channel deve ajudar o SDR a cumprir tarefas/atividades preservando owner, deal, etapa, tarefa e histórico do CRM.
12. Rafael/admin precisa ver carga por SDR: quantos leads entraram, quantos foram chamados, quantos responderam, pendências, automações feitas/falhas e backlog por pessoa.
13. O produto precisa suportar ações em massa seguras: selecionar leads, criar tarefas, marcar resolvido/pendente, disparar follow-up aprovado, mover fila — sempre com limites e prévia.
14. Segurança mínima obrigatória antes de entregar ao time: domínio fixo + autenticação Google `@zydon.com.br` ou, no mínimo transitório, token individual não compartilhável.

## Kanban

### NOW — Sprint 0: transformar MVP em produto apresentável

| ID | Status | Dono | Tarefa | Critério de aceite |
|---|---|---|---|---|
| CH-001 | DONE_VALIDATED | Claude Code + Hermes | Criar V2 premium em paralelo (`scripts/channel_panel_v2.py`) | V2 compila, roda na 8791, APIs reais funcionam, UI 4 zonas validada visualmente |
| CH-002 | DONE_VALIDATED | Hermes/tester | Validar UI V2 com dados reais de Sarah/Breno/Lucas/Mariana/Rafael | Health ok; 363 conversas; auth CF Rafael ok; sem vazamento de JID/@lid nos 200 primeiros cards; respostas recentes no topo |
| CH-003 | PARTIAL | Claude Code | Criar filas derivadas reais | Responder agora, Sem resposta, Diagnóstico, 1º contato implementados; Resolvidas/Erros ainda pendentes |
| CH-004 | DONE_VALIDATED | Claude Code + Hermes | Criar aba Conexões/Chips | `/api/chips` + modal Conexões; mostra Breno/Sarah com 2 chips, QR/reconectar, volume/dia, risco e recomendação |
| CH-005 | IN_PROGRESS | Hermes/tester | Testar conexão/QR por chip sem Discord | API validada; falta teste real com usuário escaneando QR no painel |
| CH-006 | DONE_VALIDATED | Claude Code + Hermes | Corrigir conversas `@lid`/telefones falsos do history-sync | API validada: 0 vazamentos visuais de `@lid`/JID/grupo e 0 telefones falsos internacionais; LID vira “Lead sem número” |
| CH-007 | DONE_VALIDATED | Claude Code + Hermes | Reduzir duplicidade evento automação + mensagem enviada | Dedup visual implementado; eventos com mídia/PDF diferente continuam visíveis para não esconder arquivos reais |
| CH-008 | DONE_VALIDATED | Hermes | Refinar fila Responder agora | Usa `lastIncomingTime > lastOutgoingTime`, exclui resolvidas sem nova entrada, remove conversas internas de chips Zydon/SDR; validação: 343 conversas, 41 responder agora, 0 internos na fila |
| CH-009 | BLOCKED_AUTH | Hermes/Claude | Preparar migração V2 para link principal | V2 local pronto; só migrar túnel público após domínio + Google/Cloudflare Access ativo |
| CH-015 | DONE_VALIDATED | Claude Code + Hermes | Rebaixar Conexões/Chips para suporte secundário | Sidebar/topo focam leads/pipeline; Conexões virou botão discreto com alerta apenas se precisar ação |
| CH-016 | DONE_VALIDATED | Claude Code + Hermes | Criar visão comercial/HubSpot-first no contexto | Lateral prioriza lead/negócio/próxima ação e HubSpot real validado em CH-030 |
| CH-017 | DONE_VALIDATED | Claude Code + Hermes | Criar filas comerciais | Novos leads, Responder agora, Meus negócios, Diagnóstico enviado, Primeiro contato, Reuniões/tarefas, Sem resposta |
| CH-018 | DONE_VALIDATED | Claude Code + Hermes | Envio de arquivos/áudios pela UI | Composer tem Anexar; `/api/send-file` salva upload e chama bridge `/send-file`; validação sem envio real passou |
| CH-019 | DONE_VALIDATED | Claude Code + Hermes | Tema claro/calm + alternância dark/light | Dark segue default; light/calm com variáveis CSS, botão persistido no localStorage e sidebar clara ajustada para baixa fadiga |
| CH-025 | DONE_VALIDATED | Claude Code + Hermes | Dashboard de carga por SDR | Admin vê carga por SDR; SDR vê minha carga; métricas por fila + alertas de conexão derivados de conversas/chips |
| CH-026 | DONE_VALIDATED | Claude Code + Hermes | Seleção e ações em massa seguras | Checkbox seleciona sem abrir conversa; barra de ações aparece; ações perigosas/HubSpot write ficam disabled até etapa de integridade |
| CH-020 | DONE_VALIDATED | Claude Code + Hermes | Layout mais parecido com WhatsApp Web | Chat refinado: breakpoint 1320 recolhe contexto, área central fica larga; fundo tipo WhatsApp, bolhas agrupadas sem nomes repetidos, hora dentro da bolha, mídia com timestamp corrigido, composer/quick replies mais limpos; smoke 39/39 |
| CH-027 | DONE_VALIDATED | Hermes | Corrigir duplo envio por Enter/delay | `sendInFlight` trava Enter/botão durante envio, limpa composer imediatamente e backend `_dedupe_send` bloqueia duplicados recentes; teste mockado com 4 Enter gerou 1 chamada |

### NEXT — Sprint 1: operação 100% dentro do Channel

| ID | Status | Dono | Tarefa | Critério de aceite |
|---|---|---|---|---|
| CH-010 | DONE_VALIDATED | Claude Code + Hermes | Persistir estado de conversa | `/api/state` persiste `open/pending/resolved` e nota interna em `controle/channel_state.json`; APIs enriquecem `localStatus/localNote`; sem auth 403; teste real feito e artefato de teste removido |
| CH-011 | DONE_VALIDATED | Claude Code + Hermes | Upload de mídia pela UI | Implementado via CH-018: composer anexa PDF/imagem/documento/áudio e chama `/api/send-file`; sem envio real em teste |
| CH-012 | DONE_VALIDATED | Hermes | Quick replies por SDR | Botões contextuais Retomar/Agendar/Detalhes/Recebi/Assinatura; usam empresa ativa e SDR/chip ativo; JS validado com `node --check` |
| CH-013 | DONE_VALIDATED | Hermes | Criar testes manuais/ponta-a-ponta | `docs/channel-v2-checklist.md` + `scripts/channel_v2_smoke_test.py`; smoke passou 23/23: auth, APIs, HubSpot, inbox, JS, heartbeat, sem túnel público |
| CH-014 | DONE_VALIDATED | Hermes | Configuração de usuários/chips | Admin API/UI criada: Rafael lista/cria/edita/remove usuários e vincula emails/chips sem editar JSON; não vaza tokens; não-admin 403; teste criou/removeu usuário temporário; smoke 31/31 |

### NEXT — Sprint 2: segurança e link definitivo

| ID | Status | Dono | Tarefa | Critério de aceite |
|---|---|---|---|---|
| CH-060 | BLOCKED_USER | Hermes/Rafael | Definir domínio fixo | Ex: `channel.zydon.com.br` com DNS/Cloudflare disponível |
| CH-061 | DONE_VALIDATED | Hermes/Rafael | Credenciais OAuth Google | `/root/.hermes/credentials/google_oauth.env` configurado com `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` reais, redirect `https://sdrs.zydon.com.br/oauth/callback`; `/health` público `googleConfigured=true`; `/login` mostra botão Google; secret não versionado no Drive |
| CH-062 | DONE_VALIDATED | Claude Code + Hermes | Implementar auth Google/OIDC ou Cloudflare Access | `/` sem login redireciona; APIs sem auth 403; token URL não autentica; Cloudflare Access `@zydon.com.br` funciona; Google OAuth pronto, aguardando credenciais |
| CH-063 | PARTIAL_PREPARED | Hermes | Configurar named tunnel Cloudflare | Pacote de produção preparado em `docs/channel-production-deploy.md` com DNS `sdrs.zydon.com.br -> 187.72.95.177`, Nginx reverse proxy, Cloudflare Access/Google OAuth checklist; não ativado túnel público |
| CH-064 | DONE_VALIDATED | Hermes | Admin usuários/chips | Rafael cria usuários e vincula chips pela UI; endpoint `/api/admin/users` só admin; tokens ocultos; smoke cobre 403 sem auth/não-admin |

### NEXT — Sprint 3: HubSpot e contexto comercial

| ID | Status | Dono | Tarefa | Critério de aceite |
|---|---|---|---|---|
| CH-030 | DONE_VALIDATED | Claude Code + Hermes | Enriquecer conversa com HubSpot | `/api/hubspot` read-only usa chave existente; lateral mostra contato, empresa, email, telefone, lifecycle, owner, negócio, etapa e pipeline; validado com Seal/Grupo Maranno/LightShip |
| CH-031 | DONE_VALIDATED | Claude Code + Hermes | Criar tarefa/nota no HubSpot pela conversa | `/api/hubspot/action` cria task/note vinculada a contato/deal; sem auth 403; note real criada e depois removida para não poluir CRM; auditoria em `controle/channel_hubspot_actions.jsonl` |
| CH-032 | DONE_VALIDATED | Hermes | Detectar reunião marcada | `/api/hubspot` agora busca reuniões associadas ao deal e mostra título, horário, organizador e outcome na lateral; validado com Luís Saconi / owner Lucas Batista / meeting 2026-06-11 18:45 |
| CH-033 | DONE_VALIDATED | Hermes/tester | Validar com 5 leads reais | Conferido via `/api/hubspot`: Integramix, ACELFAR, ATLAS, Rhino wood e Guaxupé; arquivo de evidência `docs/channel-v2-hubspot-5-leads-validation.md` |
| CH-034 | PARTIAL_VALIDATED | Hermes | Integridade HubSpot para ações em massa | Seleção em massa agora cria tarefa HubSpot com limite de 10, prévia, prompts e confirmação; usa `/api/hubspot/action`; smoke ok; falta teste real com seleção no piloto |
| CH-035 | DONE_VALIDATED | Hermes | Priorização de automações | API devolve `automation` por conversa: diagnóstico, 1º contato, follow-up, última automação e risco; cards/lateral mostram status; sort prioriza risco; smoke 25/25 com 165 conversas com automação detectada |

### NEXT — Sprint 4: escala/chips/risco

| ID | Status | Dono | Tarefa | Critério de aceite |
|---|---|---|---|---|
| CH-040 | DONE_VALIDATED | Hermes | Score de saúde do chip | `/api/chips` inclui `healthScore`, `loadPct`, `responseRate`, `riskReasons`; UI Conexões mostra saúde/100 e uso do limite; smoke cobre regressão |
| CH-041 | DONE_VALIDATED | Hermes | Recomendação de aumentar chips | Limite conservador ajustado para 30 msg/chip/dia; quando passa do limite, recomendação vira `adicionar_chip`; validação mostrou chips acima do limite hoje |
| CH-042 | DONE_VALIDATED | Claude Code + Hermes | Roteamento inteligente de chip | `/api/conversations` inclui `sendPort/sendPortLabel/sendRoutingReason`; envia por chip saudável do mesmo owner/permitido; validação real: 27 conversas redirecionadas, Breno 1→Breno 2 e Sarah 1→Sarah 2; sem envio real |
| CH-043 | DONE_VALIDATED | Hermes/tester | Teste com Breno 2 chips | Login `breno@zydon.com.br`: vê só 4602/4605, 20 conversas únicas, 8 rotas 4602→4605 porque Breno 1 indisponível; `sendPort` sempre permitido; sem envio real |

### LATER — Sprint 5: IA comercial

| ID | Status | Dono | Tarefa | Critério de aceite |
|---|---|---|---|---|
| CH-050 | DONE_VALIDATED | Claude Code + Hermes | Resumo automático da conversa | `/api/conversations` inclui `aiSummary` heurístico sem LLM externa; lateral mostra resumo, próxima ação e sinais; validado em 426 conversas Rafael e 22 Breno, 0 sem resumo; detectou quente/morno/frio |
| CH-051 | DONE_VALIDATED | Claude Code + Hermes | Sugestão de resposta | Botão `✨ Sugerir resposta` preenche o composer com texto seguro baseado em `aiSummary`/sinais; não chama `/api/send`; sem ERP/go-live/HubSpot/chip/porta; smoke/JS ok |
| CH-052 | DONE_VALIDATED | Hermes | Transcrição de áudio | Áudio recebido é transcrito por faster-whisper local do Hermes, cacheado em `controle/channel_audio_transcripts.json`, exibido na bolha e entra na busca/resumo; validado com áudio real 4605/Breno 2 |
| CH-053 | TODO | Hermes/tester | Avaliar qualidade da IA | 20 exemplos reais, taxa de acerto aceitável |
| CH-054 | DONE_VALIDATED | Hermes | Fila de áudio pendente | Nova fila `Áudios pendentes`; `/api/conversations` devolve `audioPending/audioTranscriptText`; busca inclui texto transcrito; validação: 8 conversas com áudio, 2 áudios recebidos transcritos em amostra real |
| CH-055 | DONE_VALIDATED | Hermes | Sugestão com contexto HubSpot + áudio | Sugestão usa meeting/deal stage/áudio transcrito quando `hsCache` já carregou; continua só preenchendo composer, sem autoenvio |
| CH-056 | DONE_VALIDATED | Hermes | Ações HubSpot 1 clique | Lateral ganhou `Follow-up hoje` e `Nota resumo` que criam task/note com resumo/próxima ação/transcrição; prompts custom continuam disponíveis |
| CH-057 | DONE_VALIDATED | Hermes | `/queue` por SDR inclui mensagens dos chips Mariana/Lucas/Rafael quando o lead/deal é do SDR | Implementado `SHARED_DEAL_VISIBILITY_PORTS` (4600/4603/4606/4607), filtro por `sdr` do histórico + cache HubSpot, badge `↗ chip`, `/api/messages`/state/HubSpot action liberados só se conversa permitida; respostas saem por `sendPort` permitido do SDR; validado: Sarah 32 compartilhadas, Lucas Batista 45, Breno 1; outro SDR recebe 403 |
| CH-058 | DONE_VALIDATED | Hermes | Perfis supervisores veem todos os SDRs/conversas | `view_all` para Rafael, Mariana e Lucas Resende: API entrega 8 chips, 624 conversas, abre qualquer conversa e pode atuar por qualquer chip; Sarah/Breno/Lucas Batista seguem restritos. Smoke 62/62 |
| CH-059 | DONE_VALIDATED | Hermes | Filtro HubSpot: conversas sem vínculo (contato/deal/lead) não aparecem na inbox por padrão | Campo `hubspotLinked` baseado em `_load_shared_visibility_cache()`: 51 conversas com vínculo, 591 sem vínculo; toggle "🎯 HubSpot ON/OFF" na UI; busca manual traz conversa mesmo sem vínculo |
| CH-060 | DONE_VALIDATED | Hermes | Cookie SameSite=None para redirect OAuth cross-site sobreviver em HTTPS | `build_cookie()` agora usa `SameSite=None; Secure` em produção HTTPS e `Lax` em localhost dev; emails explícitos para todos os usuários no channel_users.json |
| CH-065 | QUEUED_DRYRUN | Hermes/Claude | Cadência automática para deals em Primeiro Contato sem resposta | Criado card `t_ccedae32`, spec `docs/cadencia-primeiro-contato-automatica.md` e dry-run `scripts/cadencia_primeiro_contato_dryrun.py`; primeira leitura: 19 aptos para 2º contato, 14 aguardando 24h, 3 responderam e 264 sem primeiro contato registrado no ledger; nenhum envio real ativado |

> Backlog de geração de demanda (épicos E1–E7, prioridade, critérios de aceite e riscos): ver `docs/channel-demand-generation-backlog.md`.

## Bloqueios reais

- **Link definitivo:** precisa domínio/DNS ou Cloudflare autenticado. Quick tunnel atual não é definitivo.
- **Google login:** precisa OAuth Google ou Cloudflare Access/Zero Trust configurado para `@zydon.com.br`.
- **Respostas antigas:** se nunca foram capturadas pela bridge antiga, não existem no servidor; daqui pra frente ficam salvas.

## Métricas de lançamento

- SDR consegue responder sem abrir WhatsApp físico.
- Admin consegue reconectar chip sem Discord.
- Conversas com resposta aparecem no topo.
- 0 JID bruto na visão principal.
- Cada usuário vê só seus chips.
- HubSpot lateral reduz troca de abas.
- Rafael consegue ver se precisa aumentar chips por volume/risco.
