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
   - Se precisar reiniciar, reinicie apenas o painel web 8280/8791 e valide antes de reportar.

5. **Performance é requisito funcional.**
   - `/api/messages` para conversa institucional comum deve responder em menos de 1.5s localmente.
   - A UI não pode trocar erro/timeout de mensagem por “Sem mensagens”. Deve manter histórico ou mostrar erro de carregamento com retry.

## Validação mínima antes de concluir

```bash
scripts/channel_v2_release_gate.sh
```

Esse gate executa:

```bash
python3 -m py_compile scripts/channel_panel_v2.py tests/channel_v2_smoke_gate.py
node --check /tmp/channel_v2_frontend.js
python3 -m unittest discover -s tests -v
python3 tests/channel_v2_smoke_gate.py
```

Se qualquer comando falhar, a tarefa não está concluída. O smoke gate mede rotas, `/api/conversations`, `/api/messages` e casos institucionais reais que já deram “Carregando mensagens”/“Sem mensagens”. O watchdog `zydon-channel-v2-performance-watchdog` roda a cada 5 minutos e só alerta no Discord quando houver falha real.
