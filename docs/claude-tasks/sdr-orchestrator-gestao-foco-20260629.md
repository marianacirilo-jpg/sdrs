# Pacote Claude Code — Gestão SDR / Orquestrador no Foco

Data: 2026-06-29
Projeto: `/root/.hermes/zydon-prospeccao`
Arquivo principal: `scripts/channel_panel_v2.py`
Testes: `tests/test_channel_v2_core.py`

## Contexto operacional

Rafael validou a separação:

- **Foco SDR**: execução do dia pelo SDR. Mostra só tarefas humanas reais e próximas ações.
- **Gestão SDR / Orquestrador**: visão de Rafael/Dexter para entender quem precisa intervenção, qual gargalo trava o funil, onde automações ajudam/poluem e quais tarefas antigas precisam limpeza com aprovação.

Documento de requisitos salvo em:

`/root/.hermes/skills/software-development/zydon-channel-ui/references/requisitos-painel-orquestrador-sdr-foco-gestao-2026-06-29.md`

## Tarefa técnica

Implementar uma primeira versão **read-only** e stage-only da visão Gestão SDR dentro de `/foco`, sem ações destrutivas e sem mexer em produção diretamente.

### 1. API nova: `/api/sdr-orchestrator-summary`

Deve ser read-only e usar dados já disponíveis do Channel/HubSpot sem mutação.

Retorno mínimo esperado:

```json
{
  "ok": true,
  "generatedAt": 123,
  "scope": "...",
  "sdrCards": [
    {
      "uid": "lucas_batista",
      "name": "Lucas Batista",
      "activeDeals": 0,
      "openHumanTasks": 0,
      "overdueHumanTasks": 0,
      "completedToday": 0,
      "futureMeetings": 0,
      "pastMeetingsWithoutOutcome": 0,
      "responsesAwaitingAction": 0,
      "introRate": 0,
      "manualVsAutomation": {"human": 0, "automation": 0},
      "status": "ok|attention|intervention"
    }
  ],
  "interventions": [
    {"severity":"red|yellow|gray|green", "title":"...", "reason":"...", "evidence":["..."], "suggestedAction":"...", "owner":"...", "type":"..."}
  ],
  "humanQueue": [
    {"company":"...", "phone":"...", "owner":"...", "stage":"...", "sla":"...", "context":"...", "nextAction":"...", "hubspotUrl":"...", "conversationId":"..."}
  ],
  "pipelineBottlenecks": [...],
  "automationHealth": [...],
  "taskHygienePreview": {...}
}
```

Pode derivar de `/api/pipeline/focus`/funções existentes, mas não deve chamar HubSpot de forma pesada se já houver snapshot/cache. Degradar para snapshot/stale se necessário.

### 2. API nova: `/api/task-hygiene-preview`

Read-only. Não fecha/exclui task.

Separar:

- `safeToCloseAfterApproval`
- `reviewBeforeAction`
- `doNotTouch`

Critérios mínimos:

- tarefas genéricas/logs de automação vencidas/antigas agrupadas em `safeToCloseAfterApproval`;
- tarefas comerciais antigas com contexto em `reviewBeforeAction`;
- preparar diagnóstico futuro, reunião futura e interação recente em `doNotTouch`.

Cada grupo deve trazer contagem e exemplos com evidência.

### 3. UI em `/foco`

Adicionar subaba/bloco novo chamado **Gestão SDR** sem remover o Foco atual.

Requisitos visuais:

- tema dark consistente;
- cards por SDR;
- bloco “Intervenções recomendadas pelo Dexter”;
- bloco “Fila humana”;
- bloco “Higiene de tarefas”;
- bloco “Gargalos do pipeline”;
- nada de texto técnico visível como `ledger`, `debug`, `fonte`, `auditoria`, `registro`, `log` na UI do SDR. Para automação, usar copy humana tipo “envios automáticos”/“histórico concluído”.

### 4. Testes obrigatórios

Adicionar/atualizar `tests/test_channel_v2_core.py` garantindo:

1. `/api/sdr-orchestrator-summary` existe no handler.
2. `/api/task-hygiene-preview` existe no handler.
3. Automação/WhatsApp/PDF enviado não conta como tarefa humana pendente.
4. Higiene agrupa tarefas sujas, mas não executa mutação/fechamento.
5. Toda intervenção tem severidade, motivo, evidência e ação sugerida.
6. UI `/foco` contém “Gestão SDR” e não contém texto técnico proibido nesse bloco.
7. Tudo segue stage-first.

## Restrições invioláveis

- NÃO promover produção.
- NÃO matar/subir `8280` público manualmente.
- NÃO reiniciar bridges/chips WhatsApp.
- NÃO tocar em QR/auth/cookies/secrets.
- NÃO alterar `controle/wpp_envios.json`.
- NÃO enviar WhatsApp.
- NÃO criar commit/push.
- Se precisar testar deploy, rode apenas `scripts/channel_v2_safe_deploy.sh stage`.

## Validação mínima

Rodar:

```bash
python3 -m py_compile scripts/channel_panel_v2.py tests/test_channel_v2_core.py
python3 - <<'PY'
from pathlib import Path
s=Path('scripts/channel_panel_v2.py').read_text(encoding='utf-8')
start=s.index('<script>')+len('<script>')
end=s.index('</script>', start)
Path('/tmp/channel_v2_frontend.js').write_text(s[start:end], encoding='utf-8')
print('frontend_js_bytes', end-start)
PY
node --check /tmp/channel_v2_frontend.js
python3 -m unittest tests.test_channel_v2_core -v
scripts/channel_v2_safe_deploy.sh stage
```

## Saída esperada do Claude Code

- Arquivos alterados.
- Como as duas APIs foram implementadas.
- Quais dados são reais vs derivados/snapshot.
- Quais testes foram adicionados.
- Resultado dos comandos.
- Release dir de stage, se rodou stage.
