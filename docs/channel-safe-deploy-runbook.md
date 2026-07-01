# Zydon Channel V2 — deploy seguro / staging obrigatório

Rafael definiu em 2026-06-29: **não pode quebrar `sdrs.zydon.com.br` enquanto mexe em código**. Mais de 20 pessoas usam o painel. Toda mudança de Channel deve seguir este fluxo.

## Regra de ouro

1. Editar código **não é deploy**.
2. Nunca matar/subir o port público `8280` durante desenvolvimento.
3. Nunca reiniciar bridge/chip WhatsApp como parte de deploy do Channel.
4. Toda mudança vai primeiro para uma **release copy** isolada.
5. A release copy sobe em porta privada de staging (`8891`).
6. Só promove para público depois que a candidate estiver estável e validada.
7. Se promoção falhar, rollback automático volta a versão anterior.

## Comandos

### Só preparar e testar candidate, sem tocar no público

```bash
cd /root/.hermes/zydon-prospeccao
scripts/channel_v2_safe_deploy.sh stage
```

Esse comando:

- copia o projeto para `controle/releases/channel-v2/<timestamp>/`;
- roda `py_compile`;
- extrai e valida o JS com `node --check`;
- roda `python3 -m unittest discover -s tests -v`;
- sobe o candidato em `127.0.0.1:8891`;
- valida `/health`, `/api/conversations` e timelines reais em `/api/messages`;
- **não altera produção**.

No final ele imprime o caminho da release e o comando de promoção.

### Promover uma release já testada

```bash
scripts/channel_v2_safe_deploy.sh promote /root/.hermes/zydon-prospeccao/controle/releases/channel-v2/<timestamp>
```

Esse comando revalida o candidate antes de tocar produção. Só depois:

- mantém o port estável/interno `8791` vivo;
- troca somente o port público `8280`;
- valida `https://sdrs.zydon.com.br/api/conversations` com header Cloudflare Access;
- se o público não validar, executa rollback automático.

### Stage + promote em um comando

Use apenas quando a mudança for claramente segura e a janela permitir:

```bash
scripts/channel_v2_safe_deploy.sh deploy
```

## O que Claude Code pode e não pode fazer

Claude Code pode:

- editar arquivos de código/teste no escopo autorizado;
- rodar testes não destrutivos;
- rodar `scripts/channel_v2_safe_deploy.sh stage`;
- reportar o release dir aprovado.

Claude Code **não pode**:

- executar `promote` ou `deploy` sozinho;
- matar/subir `8280`/`8791` manualmente;
- reiniciar WhatsApp bridges/chips;
- alterar `controle/wpp_envios.json`, auth, QR, cookies ou segredos;
- declarar produção estável sem validação pública real.

## Checklist antes de dizer “pronto”

- [ ] Testes unitários passaram.
- [ ] JS passou no `node --check`.
- [ ] Candidate `8891` respondeu `/health`.
- [ ] Candidate `8891` respondeu `/api/conversations` com contagem real.
- [ ] Casos reais de `/api/messages` passaram.
- [ ] Produção ainda estava saudável antes da troca.
- [ ] Promoção validou o público `https://sdrs.zydon.com.br/api/conversations`.
- [ ] Se qualquer etapa falhou, produção não foi trocada ou rollback foi executado.

## Observação operacional

O script usa lock em `controle/runtime/channel/deploy.lock` para impedir deploy concorrente. Logs dos candidates ficam em `controle/runtime/channel/channel-<port>.log`.
