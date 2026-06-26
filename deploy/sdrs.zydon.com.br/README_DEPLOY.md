# Zydon Channel — Deploy em `sdrs.zydon.com.br`

## Objetivo
Hospedar o Channel V2 em `https://sdrs.zydon.com.br` com segurança mínima obrigatória: **login Google restrito a e-mails Zydon** e APIs bloqueadas sem autenticação.

## Arquitetura esperada
O app `scripts/channel_panel_v2.py` é um servidor Python stdlib que roda localmente em `127.0.0.1:8791`.

Nginx/Proxy público:

```text
Internet -> HTTPS sdrs.zydon.com.br -> nginx -> 127.0.0.1:8791
```

Importante: o Channel espera acessar localmente:

- projeto: `/root/.hermes/zydon-prospeccao`
- dados do WhatsApp: `/root/.hermes/whatsapp-extra/channel_data`
- bridges WhatsApp nas portas `4600` a `4607`
- credenciais HubSpot em `/root/.hermes/credentials/hubspot.env`

Portanto, o host precisa ser **o mesmo servidor que roda as bridges** ou ter esses serviços/dados acessíveis localmente. Se o host for só hospedagem web comum sem acesso às bridges, ele deve fazer apenas reverse proxy para o servidor operacional.

---

## 1. DNS
Criar registro DNS:

```text
sdrs.zydon.com.br -> IP público do host
```

Se usar Cloudflare, deixar proxy ativo ou DNS-only conforme política do host. O app já funciona atrás de proxy desde que envie `X-Forwarded-Proto: https`.

---

## 2. Google OAuth
Criar OAuth Client no Google Cloud:

- Tipo: **Web application**
- Authorized JavaScript origins:
  - `https://sdrs.zydon.com.br`
- Authorized redirect URIs:
  - `https://sdrs.zydon.com.br/oauth/callback`

Guardar:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

O app só aceita e-mails dos domínios:

- `@zydon.com.br`
- `@zydon.com`

Usuários atualmente mapeados:

- `rafael@zydon.com.br` -> admin / todos os chips
- `mariana@zydon.com.br` -> Mariana
- `breno@zydon.com.br` -> Breno
- `sarah@zydon.com.br` -> Sarah
- `lucas.batista@zydon.com.br` -> Lucas Batista
- `lucas.resende@zydon.com.br` -> Lucas Resende

---

## 3. Instalar arquivos
No host, manter o projeto em:

```bash
/root/.hermes/zydon-prospeccao
```

Copiar/atualizar pelo menos:

```bash
scripts/channel_panel_v2.py
scripts/channel_v2_smoke_test.py
docs/channel-v2-checklist.md
docs/channel-kanban.md
deploy/sdrs.zydon.com.br/
```

Se for um host novo, também precisa copiar/instalar o stack WhatsApp (`/root/.hermes/whatsapp-extra`) e as credenciais/estado necessários, com muito cuidado para não expor secrets.

---

## 4. Variáveis de ambiente
Criar arquivo:

```bash
sudo mkdir -p /etc/zydon-channel
sudo chmod 700 /etc/zydon-channel
sudo nano /etc/zydon-channel/sdrs.env
sudo chmod 600 /etc/zydon-channel/sdrs.env
```

Conteúdo:

```env
GOOGLE_CLIENT_ID=COLE_AQUI
GOOGLE_CLIENT_SECRET=COLE_AQUI
CHANNEL_PUBLIC_BASE_URL=https://sdrs.zydon.com.br
GOOGLE_REDIRECT_URI=https://sdrs.zydon.com.br/oauth/callback
CHANNEL_ALLOW_TOKEN_AUTH=0
```

Também garantir HubSpot:

```bash
/root/.hermes/credentials/hubspot.env
```

com o token existente da Zydon. **Não enviar esse arquivo em pacote público.**

---

## 5. Systemd
Copiar o service:

```bash
sudo cp deploy/sdrs.zydon.com.br/zydon-channel-sdrs.service /etc/systemd/system/zydon-channel-sdrs.service
sudo systemctl daemon-reload
sudo systemctl enable --now zydon-channel-sdrs
sudo systemctl status zydon-channel-sdrs --no-pager
```

Logs:

```bash
journalctl -u zydon-channel-sdrs -f
```

---

## 6. Nginx
Copiar config:

```bash
sudo cp deploy/sdrs.zydon.com.br/nginx-sdrs.zydon.com.br.conf /etc/nginx/sites-available/sdrs.zydon.com.br
sudo ln -sf /etc/nginx/sites-available/sdrs.zydon.com.br /etc/nginx/sites-enabled/sdrs.zydon.com.br
sudo nginx -t
sudo systemctl reload nginx
```

TLS com certbot, se não houver Cloudflare Origin Certificate/SSL do host:

```bash
sudo certbot --nginx -d sdrs.zydon.com.br
```

---

## 7. Validação de segurança
Rodar no host:

```bash
cd /root/.hermes/zydon-prospeccao
python3 scripts/channel_v2_smoke_test.py
```

Validações manuais obrigatórias:

```bash
# Deve redirecionar/tela de login, sem mostrar dados
curl -I https://sdrs.zydon.com.br/

# APIs sem login devem bloquear
curl -i https://sdrs.zydon.com.br/api/conversations
# esperado: HTTP 403

# Token antigo em URL NÃO pode autenticar
curl -i 'https://sdrs.zydon.com.br/?u=rafael&t=qualquer'
# esperado: login/sem dados
```

Login real:

1. Abrir `https://sdrs.zydon.com.br`
2. Entrar com Google `@zydon.com.br`
3. Ver se Rafael vê todos os chips
4. Ver se SDR vê somente os próprios chips
5. Testar `/logout`

---

## 8. Regras de segurança
- `CHANNEL_ALLOW_TOKEN_AUTH=0` em produção.
- Nunca publicar URL com `?u=&t=`.
- Credenciais em `/etc/zydon-channel/sdrs.env` com `chmod 600`.
- HubSpot token fora do repositório/pacote.
- Nginx só expõe HTTPS.
- App só escuta em `127.0.0.1:8791`, nunca `0.0.0.0` em produção.
- APIs sem cookie/Cloudflare Access/Google devem retornar `403`.

---

## 9. Rollback
Se algo der errado:

```bash
sudo systemctl stop zydon-channel-sdrs
sudo rm -f /etc/nginx/sites-enabled/sdrs.zydon.com.br
sudo nginx -t && sudo systemctl reload nginx
```

Isso tira o painel do ar sem mexer nas bridges WhatsApp.
