# Zydon Channel V2 — pacote de produção

> Objetivo: publicar o Channel em `https://sdrs.zydon.com.br` com HTTPS e login corporativo, mantendo o app Python fechado em localhost.

## Arquitetura correta

```txt
Internet
  ↓
https://sdrs.zydon.com.br
  ↓ DNS A
187.72.95.177
  ↓ Nginx 443/HTTPS
http://127.0.0.1:8791
  ↓
scripts/channel_panel_v2.py
```

## DNS

No provedor DNS/Cloudflare:

```txt
sdrs.zydon.com.br  A  187.72.95.177
```

## Serviço Python

O app deve continuar bindado em localhost:

```bash
cd /root/.hermes/zydon-prospeccao
python3 scripts/channel_panel_v2.py --host 127.0.0.1 --port 8791
```

Nunca usar `--host 0.0.0.0` em produção.

## Nginx reverse proxy

Arquivo sugerido: `/etc/nginx/sites-available/zydon-channel.conf`

```nginx
server {
    listen 80;
    server_name sdrs.zydon.com.br;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name sdrs.zydon.com.br;

    # Certbot/Cloudflare origin cert preenche estes caminhos
    ssl_certificate     /etc/letsencrypt/live/sdrs.zydon.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sdrs.zydon.com.br/privkey.pem;

    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:8791;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
    }
}
```

Ativar:

```bash
ln -s /etc/nginx/sites-available/zydon-channel.conf /etc/nginx/sites-enabled/zydon-channel.conf
nginx -t
systemctl reload nginx
```

## Cloudflare Access recomendado

Criar app Access:

- Application domain: `sdrs.zydon.com.br`
- Policy: allow emails SOMENTE com domínio:
  - `@zydon.com.br`

Não liberar `@gmail.com`, `@outlook.com`, `@zydon.com` ou qualquer outro domínio.
- Header esperado pelo app:
  - `Cf-Access-Authenticated-User-Email`

O Channel já aceita esse header e mapeia o email para o usuário/chips.

## Alternativa Google OAuth

Se não usar Cloudflare Access, configurar env:

```bash
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://sdrs.zydon.com.br/oauth/callback
CHANNEL_PUBLIC_BASE_URL=https://sdrs.zydon.com.br
```

## Segurança obrigatória antes de liberar SDR

- [ ] DNS aponta para `187.72.95.177`.
- [ ] Nginx responde HTTPS.
- [ ] `curl -I https://sdrs.zydon.com.br` não abre app sem login.
- [ ] `/api/conversations` sem login retorna 403.
- [ ] Porta 8791 não está exposta publicamente.
- [ ] `CHANNEL_ALLOW_TOKEN_AUTH` ausente/desligado em produção.
- [ ] Cloudflare Access ou Google OAuth ativo.
- [ ] Smoke test passa localmente:

```bash
cd /root/.hermes/zydon-prospeccao
python3 scripts/channel_v2_smoke_test.py
python3 /root/.hermes/scripts/zydon_channel_v2_security_heartbeat.py
```

## Comando de health local

```bash
curl -s http://127.0.0.1:8791/health
```

## Deploy seguro obrigatório

Não editar/reiniciar diretamente o processo público enquanto SDRs estão usando o sistema. Antes de qualquer promoção, seguir `docs/channel-safe-deploy-runbook.md`:

```bash
cd /root/.hermes/zydon-prospeccao
scripts/channel_v2_safe_deploy.sh stage
# depois de aprovado:
scripts/channel_v2_safe_deploy.sh promote /root/.hermes/zydon-prospeccao/controle/releases/channel-v2/<timestamp>
```

O stage sobe uma candidate em `127.0.0.1:8891` e valida APIs reais sem tocar no público. A promoção só troca o port público depois que a candidate estiver estável; falha de promoção aciona rollback.

## Importante

- O app Python fica em localhost por segurança.
- Nginx é quem recebe o tráfego público.
- Não abrir túnel público sem login.
- Não liberar token por URL para SDR em produção.
- Claude Code não pode executar `promote`/`deploy` sozinho; ele só pode chegar até `stage` e reportar o release dir.
