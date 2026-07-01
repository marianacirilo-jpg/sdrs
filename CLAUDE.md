# Zydon Channel V2 — regras obrigatórias para Claude Code

Este projeto é operação crítica em horário comercial. Não trate como protótipo.

## Regras invioláveis

1. **Nenhuma feature sem rota dedicada quando for tela/fluxo visível.**
   - Conversas: `/conversas`
   - Foco SDR: `/foco`
   - Gestão: `/gestao`
   - Novas telas precisam de rota própria e teste.

2. **Nenhuma feature/bugfix sem teste.**
   - Use `python3 -m unittest discover -s tests -v`.
   - Para o painel principal, adicione/atualize `tests/test_channel_v2_core.py`.
   - Testes obrigatórios para mudanças em: `/api/conversations`, `/api/messages`, autenticação, PDF/mídia, privacidade de comunicadores, rotas de tela e performance básica.

3. **Comunicadores têm privacidade máxima.**
   - Nunca expor conversa pessoal de comunicador.
   - Só mostrar envio operacional registrado pelo Channel/ledger e resposta do lead naquele chat operacional.

4. **Não quebrar a operação durante horário comercial.**
   - Não reiniciar bridges/chips WhatsApp sem ordem explícita.
   - Não reiniciar produção diretamente enquanto edita código.
   - Não matar/subir `8280` público manualmente durante desenvolvimento.
   - Mudança de código deve passar por staging/candidate primeiro; produção só troca depois que o candidate estiver estável.
   - Fluxo padrão aprovado por Rafael: trabalhar sempre na stage; quando a stage estiver validada/estável, Hermes faz uma promoção única e transparente para produção, sem interrupção perceptível para SDRs.

5. **Deploy seguro é obrigatório.**
   - Nunca diga “pronto” depois de editar arquivo no diretório vivo.
   - Primeiro rode validação local e staging: `scripts/channel_v2_safe_deploy.sh stage`.
   - Esse comando cria uma cópia de release, roda testes, sobe candidate em porta privada `8891` e valida APIs reais sem tocar no público.
   - Promoção para o público exige etapa explícita depois do stage aprovado: `scripts/channel_v2_safe_deploy.sh promote <release_dir>` ou `scripts/channel_v2_safe_deploy.sh deploy`.
   - Se o candidate falhar, a produção fica intacta.
   - Se a promoção falhar, rollback automático sobe a versão anterior no port público.
   - Claude Code NÃO deve executar promote/deploy sozinho; ele pode rodar `stage` e reportar o release dir. Dexter/Hermes decide promover.

6. **Performance é requisito funcional.**
   - `/api/messages` para conversa institucional comum deve responder em menos de 1.5s localmente.
   - A UI não pode trocar erro/timeout de mensagem por “Sem mensagens”. Deve manter histórico ou mostrar erro de carregamento com retry.

7. **Mostrar realidade, não texto de auditoria.**
   - A interface do SDR deve parecer WhatsApp/inbox real: bolhas reais, horário real, anexo real, resposta real.
   - Não criar cards, rótulos ou textos visíveis como “auditoria”, “registro”, “log”, “evento técnico”, “ledger”, “fonte”, “debug” ou equivalente para explicar a origem interna de uma mensagem.
   - Ledger/controle/history são fontes internas para dedupe, privacidade e reconstrução fiel; na UI eles enriquecem uma bolha real, não viram uma segunda mensagem nem um bloco de auditoria.
   - No detalhe da conversa, nunca renderize ledger/fila/intenção como bolha se não houver bolha real no history/bridge/device do WhatsApp. Listagem/card pode existir por origem operacional; timeline visual só mostra mensagens reais.
   - Testes e comentários podem usar termos técnicos, mas nunca deixe esses termos aparecerem para SDRs/clientes na tela.

8. **Design system sempre na paleta oficial Zydon.**
   - Fonte de marca: `Manual_Zydon.pdf` enviado por Rafael; referência extraída em `docs/zydon-brand-design-system.md`.
   - Paleta oficial: Lime Green `#CDEB00`, Neutral Black `#000000`, Tech Gray `#C3C3C6`, Light Gray `#E6E6E6`.
   - Todo design system, UI, PDF, dashboard, gráfico, login, card e mockup deve partir dessa paleta. Não inventar paleta paralela nem visual SaaS genérico.
   - Tema dark pode usar preto profundo derivado do Neutral Black (`#06080A`, `#08090A`, `#0B0F0C`), mas o visual deve continuar preto/neutro + lime Zydon com parcimônia.
   - Informações operacionais antigas/passadas presentes em materiais ou telas antigas são descartáveis; não transformar isso em regra atual de produto. O manual enviado vale como guia de marca/paleta, não como fonte de operação comercial atual.

## Validação mínima antes de concluir

```bash
scripts/channel_v2_release_gate.sh
scripts/channel_v2_safe_deploy.sh stage
```

O `release_gate` valida o código; o `safe_deploy stage` prova a versão candidata em uma cópia isolada e porta privada antes de qualquer promoção pública.

Esse gate executa:

```bash
python3 -m py_compile scripts/channel_panel_v2.py tests/channel_v2_smoke_gate.py
node --check /tmp/channel_v2_frontend.js
python3 -m unittest tests.test_channel_v2_core tests.test_channel_v2_watchdog_hysteresis -v
python3 tests/channel_v2_smoke_gate.py
```

Se qualquer comando falhar, a tarefa não está concluída. O smoke gate mede rotas, `/api/conversations`, `/api/messages` e casos institucionais reais que já deram “Carregando mensagens”/“Sem mensagens”. O watchdog `zydon-channel-v2-performance-watchdog` roda a cada 5 minutos e só alerta no Discord quando houver falha real. Antes de entregar UI, confira que nenhum texto técnico/de auditoria virou texto visível para o SDR.
