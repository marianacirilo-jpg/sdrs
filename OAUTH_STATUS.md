# OAUTH_STATUS — Zydon Channel

Atualizado em: 2026-06-24

## Status

Google OAuth configurado no servidor.

Validações executadas:

- `/root/.hermes/credentials/google_oauth.env` existe com permissão `600`.
- `GOOGLE_CLIENT_ID` presente.
- `GOOGLE_CLIENT_SECRET` presente.
- `GOOGLE_REDIRECT_URI=https://sdrs.zydon.com.br/oauth/callback`.
- `CHANNEL_PUBLIC_BASE_URL=https://sdrs.zydon.com.br`.
- `CHANNEL_ALLOW_TOKEN_AUTH=0`.
- `/health` local e público retornam `googleConfigured=true`.
- `/login` público mostra botão `Entrar com Google` e não mostra mais `Login Google ainda não configurado`.
- Smoke test: 62/62.
- Heartbeat: 0.

## Segurança

O arquivo com o secret fica fora do projeto, em `/root/.hermes/credentials/google_oauth.env`, e não deve ser enviado ao Drive nem commitado em nenhum repositório.

Domínio permitido para login: somente `@zydon.com.br`.
