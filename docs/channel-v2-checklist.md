# Channel V2 — Checklist ponta-a-ponta

Data: 2026-06-24

## Segurança
- [ ] `/` sem login redireciona ou renderiza `/login`, sem mostrar dados.
- [ ] `/api/conversations` sem login retorna 403.
- [ ] Token antigo `?u=&t=` não autentica sem `CHANNEL_ALLOW_TOKEN_AUTH=1`.
- [ ] Header Cloudflare Access `@zydon.com.br` autentica.
- [ ] Header de domínio externo rejeita.
- [ ] Túnel público está pausado até domínio/auth.

## Inbox
- [ ] `/api/conversations` retorna conversas reais.
- [ ] Não há grupo interno, broadcast, `status@broadcast`.
- [ ] Não há JID bruto/`@lid` em título/subtítulo visível.
- [ ] Conversas internas entre chips Zydon não aparecem.
- [ ] `Responder agora` só inclui lead com última entrada real posterior à última saída.
- [ ] Resolvida sai da fila até nova mensagem.

## HubSpot
- [ ] `/api/hubspot` encontra contato/deal em lead real.
- [ ] `/api/hubspot/action` sem auth retorna 403.
- [ ] `/api/hubspot/action` com auth cria note/task quando executado.
- [ ] Ações HubSpot são auditadas em `controle/channel_hubspot_actions.jsonl`.

## Estado local
- [ ] `/api/state` sem auth retorna 403.
- [ ] Pendente/resolvido/nota persistem em `controle/channel_state.json`.
- [ ] Artefatos de teste são removidos/limpos.

## WhatsApp/envio
- [ ] Dedupe de duplo Enter existe no frontend (`sendInFlight`).
- [ ] Dedupe backend `_dedupe_send` existe.
- [ ] Teste de Enter repetido mockado não gera múltiplas chamadas.
- [ ] Upload/anexo existe via `/api/send-file`.

## UI
- [ ] JS passa em `node --check`.
- [ ] Dark/light existem.
- [ ] Quick replies contextuais existem.
- [ ] Botões de bulk perigosos seguem disabled até prévia/limites.
