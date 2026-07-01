# Rotinas / Configuração centralizada — design de produto e arquitetura

Data: 2026-06-30
Autor: Claude Code (a pedido de Rafael)
Status: proposta de design (sem código de produção alterado)
Escopo: como centralizar em **`/rotinas` → Configuração** tudo que vinha virando
aba/tela separada (Followups, Proatividade, Dexter Center, rotinas cruas), sem
tocar nas análises da Gestão e sem quebrar a operação em horário comercial.

---

## 1. Visão geral

### 1.1 Problema
A automação comercial cresceu por sprints. Cada necessidade nova (followups,
proatividade, centralizador Dexter, inventário de scripts) tendeu a virar uma
**aba principal própria** competindo com Conversas / Foco / Gestão / Agendas.
Isso gera três custos:

- **Redundância**: a mesma rotina (ex.: follow-up F1-F4) aparece como aba, como
  bloco em Gestão e como cron em Dexter Center.
- **Ambiguidade de dono**: não fica claro o que é *configuração operacional*
  (parametrizar a máquina) e o que é *análise de performance* (ler resultado).
- **Risco de operação**: telas de configuração misturadas com telas de SDR
  aumentam a chance de expor termos técnicos ou ação perigosa no lugar errado.

### 1.2 Direção de produto (já decidida pelo Rafael)
- **`/rotinas` é a home privada de orquestração/configuração** (Rafael/admin).
  Toda tentativa de "mais uma aba" para operação Dexter converge para cá, na
  seção **Configuração**, organizada **por jornada comercial** — não por script
  cru. (Ref.: `channel-v2-rotinas-absorve-abas-separadas-2026-06-30.md` e
  `channel-v2-rotinas-orchestration-center-2026-06-30.md`.)
- **`/gestao` continua sendo a casa da análise/performance** (cards por SDR,
  gargalos, taxa de Introdução, qualidade de abordagem). Nada de análise sai da
  Gestão neste design.
- **Não criar novas abas principais.** Rotas antigas (`/followups`,
  `/proatividade`) já redirecionam para `/rotinas` e devem permanecer só como
  compatibilidade/endpoint técnico.

### 1.3 Princípio-guia (a "fronteira")
> **Rotinas configura a máquina. Gestão lê o que a máquina produziu.**

- Se a tela permite **mudar um parâmetro** que altera comportamento futuro
  (texto aprovado, cap por chip, janela, cron, backup, git) → **Rotinas/Config**.
- Se a tela **mede o passado/presente** para decidir manualmente (taxa de
  resposta, gargalo de etapa, fila humana, no-show) → **Gestão (análise)**.
- O elo entre as duas é **read-only e de mão única**: Rotinas pode *linkar* para
  a análise correspondente na Gestão ("ver performance desta jornada"), e a
  Gestão pode *linkar* para o ajuste em Rotinas ("ajustar parâmetro"), mas
  **nenhuma das duas duplica a função da outra**.

### 1.4 Estado atual (base já existente, não reinventar)
Já existe e deve ser **evoluído**, não substituído:

- `controle/rotinas_orquestracao_config.json` — config versionável real.
- `ROTINAS_CONFIG_DEFAULTS` + `sanitize_rotinas_config()` + `save_rotinas_config()`
  com clamp/saneamento no backend (não confia no frontend).
- `ROTINAS_JOURNEY_DEFS` — 8 jornadas já definidas.
- `GET/POST /api/rotinas/config` e `GET /api/rotinas/summary`.
- `_rotinas_centralized_modules()` já absorve **followups**, **proatividade** e
  **dexter_center** como módulos resumidos dentro de Rotinas.
- `proatividade_config()` / `save_proatividade_config()` — config separada que
  **deve ser exposta dentro de Rotinas** (hoje vive paralela).

A proposta abaixo é a forma final para a qual essa base deve convergir.

---

## 2. Mapa da jornada comercial (entrada do lead → agendamento/introdução)

A automação é uma esteira única. Toda configuração deve poder ser ancorada em
**uma** destas etapas (e só uma como dona principal):

```
  [1] ENTRADA          [2] QUALIFICAÇÃO        [3] PRIMEIRO            [4] FOLLOW-UP
  Formulário/lead  →   MQL vs Não-MQL      →   CONTATO            →   SDR (F1–F4)      →
  HubSpot source       diagnóstico + PDF       SDR/chip/horário       cadência/respostas
       │                    │                        │                      │
       ▼                    ▼                        ▼                      ▼
  [5] AGENDA / NO-SHOW  →  [6] AGENDAMENTO / INTRODUÇÃO (handoff p/ closer)
  confirma/remarca/lembra   reunião marcada = objetivo do funil

  ──────────────────────────── camadas transversais ────────────────────────────
  [A] WHATSAPP / CHIPS   bridges, canonicalização, limites, qualidade outbound, QR
  [B] CHANNEL / PAINÉIS  Conversas, Foco, Gestão, Rotinas, performance/watchdogs
  [C] GOVERNANÇA         backups (rclone/GDrive), git/commit, release gate, stage, rollback
```

Mapeamento direto para as 8 jornadas já existentes em `ROTINAS_JOURNEY_DEFS`:

| Etapa da jornada | `key` da jornada | Grupo |
|---|---|---|
| [1] Entrada | `entrada_mql` | Aquisição |
| [2] Qualificação Não-MQL | `nao_mql` | Aquisição |
| [3] Primeiro contato | `primeiro_contato` | SDR |
| [4] Follow-up | `followup_sdr` | SDR |
| [5] Agenda / No-show | `agenda_no_show` | SDR |
| [6] Agendamento/Introdução | `agenda_no_show` (subetapa "Introdução") | SDR |
| [A] WhatsApp/Chips | `whatsapp_infra` | Infra |
| [B] Channel/Painéis | `channel_ui` | Produto |
| [C] Governança | `backups_git` | Governança |

> **Ajuste recomendado (taxonomia final):** "Agendamento/Introdução" hoje é
> tratado como subetapa de `agenda_no_show`. Para deixar a esteira fiel ao
> objetivo do funil (a reunião marcada / handoff), recomendo **renomear o label**
> de `agenda_no_show` para **"Agenda / No-show / Introdução"** (sem trocar a
> `key`, para não quebrar `journeyOverrides` salvos). Assim a jornada cobre
> confirmação → remarcação → lembrete → no-show → reunião marcada → handoff.

---

## 3. Matriz: módulo × dono × tela × fonte de dados × pode configurar?

"Pode configurar?" = a tela permite editar parâmetro que muda comportamento.
"Análise" = a tela só lê/mede. Esta matriz **é a fronteira** entre Rotinas e Gestão.

| Módulo / função | Dono | Tela (home) | Fonte de dados | Pode configurar aqui? |
|---|---|---|---|---|
| Parâmetros globais (autonomia, notificar só exceções, aprovação obrigatória) | Rafael | **/rotinas → Config** | `rotinas_orquestracao_config.json` | **Sim** (editável) |
| Política de mensagens (fonte texto, cap/chip/dia, auto-rewrite) | Rafael | **/rotinas → Config** | `rotinas_orquestracao_config.json::messagePolicy` | **Sim** |
| Textos aprovados / manifesto F1-F4 | Rafael/Dexter | **/rotinas → Follow-up** | `controle/followup_textos_aprovados_rafael_*.json` (hash) | **Sim** (editar texto + bump hash) |
| Regras incoming MQL fixas (`FIXED_*`) | Rafael | **/rotinas → Entrada/Não-MQL** | `FIXED_*` no código + version | Parcial (ver §6: só em FIXED_* + bump version) |
| Política de logs (retenção, mascarar telefone, esconder técnico) | Rafael | **/rotinas → Config** | `...::logPolicy` | **Sim** |
| Política de backup (ligado, intervalo, destino rclone/GDrive) | Rafael | **/rotinas → Governança** | `...::backupPolicy` | **Sim** (parâmetro; execução é ação guardada) |
| Política de git (ligado, commit pós-validação, branch) | Rafael | **/rotinas → Governança** | `...::gitPolicy` | **Sim** (parâmetro) |
| Crons / cadência (ligar/desligar, janela) | Rafael/Dexter | **/rotinas → jornada da cron** | `dexter_center_report` + config de proatividade | **Sim** (flag enabled; disparo real é ação guardada) |
| Proatividade (janela revisão, cooldown grupo, dedupe CRM, modo) | Rafael | **/rotinas → Config/Entrada** | `proatividade_config()` (`PROATIVIDADE_CONFIG_FILE`) | **Sim** |
| Limites/qualidade WhatsApp por chip | Rafael | **/rotinas → WhatsApp/Chips** | bridges + `messagePolicy.dailyCapPerChip` | **Sim** (limite); reiniciar chip é ação guardada |
| Overrides por jornada (ligar/desligar, dono, nota) | Rafael | **/rotinas → cabeçalho da jornada** | `...::journeyOverrides` | **Sim** |
| Inventário de scripts/watchdogs/processos | Dexter | **/rotinas → inventário recolhível** | `_rotinas_*_rows()` | Não (só observabilidade) |
| **Cards por SDR / carteira** | Rafael | **/gestao** | `sdr_orchestrator_summary` ← `pipeline_focus` (HubSpot) | **Não — análise** |
| **Gargalos de pipeline por etapa** | Rafael | **/gestao** | `pipelineBottlenecks` | **Não — análise** |
| **Performance de abordagem (resposta/agenda)** | Rafael | **/gestao** | `_orch_approach_performance` / `dispatch_stats` | **Não — análise** |
| **Fila humana / intervenções / higiene de tarefa** | Rafael | **/gestao** | `humanQueue`, `taskHygiene` | **Não — análise** |
| **Taxa de Introdução do mês** | Rafael | **/gestao** | `pipeline_focus` | **Não — análise** |
| **Foco SDR (o que fazer agora)** | SDR | **/foco** | atividade/tarefas | Não (execução guiada, não config) |
| **Inbox real do SDR** | SDR | **/conversas** | conversas + ledger | Não |
| Saúde de automação (watchdogs verdes/vermelhos) | Rafael | **/gestao** lê + **/rotinas** lê | `automationHealth` / watchdogs | Não (observabilidade compartilhada) |

Leitura rápida da matriz:
- **Tudo que é "Pode configurar = Sim" mora em `/rotinas`.**
- **Tudo que é "análise" mora em `/gestao`** e permanece intocado.
- **`/foco` e `/conversas` são execução do SDR**, nunca configuração.

---

## 4. Proposta de UX da tela `/rotinas`

### 4.1 Princípios
- **Resumo primeiro, detalhe sob demanda.** Topo mostra estado e poucos
  controles; inventário técnico fica recolhível.
- **Agrupar por jornada**, na ordem da esteira comercial.
- **Linguagem humana** nos rótulos. (A tela é do Rafael, mas mantemos o padrão
  para nunca vazar termo técnico/"auditoria" para telas de SDR — ver §6/§8.)
- **Ações seguras por padrão; ação perigosa só com confirmação + log + rollback**
  e enquanto `requireApprovalForDangerousActions` estiver travado (fase atual).
- **Sem morosidade:** endpoints locais, sem recomputar inbox pesada no hot path.

### 4.2 Layout (ordem dos blocos)

```
┌─ /rotinas — Central de Orquestração ───────────────────────────────────┐
│ Barra de estado: bridges 8/8 · watchdogs 5 ok · crons N ativos ·       │
│                  backups: há 4 min · ⚠ avisos (se houver)              │
├────────────────────────────────────────────────────────────────────────┤
│ [0] CONFIGURAÇÃO GLOBAL  (sempre visível, editável, salva com 1 clique) │
│   • Modo de autonomia:  ( ) Conservador  (•) Equilibrado  ( ) Expansivo │
│   • Notificar só exceções  [x]                                          │
│   • Exigir aprovação p/ ações perigosas  [x] (travado nesta fase)       │
│   • Mensagens: fonte=textos aprovados · cap/chip/dia=[30] · auto-rewrite[ ]│
│   • Registros: retenção=[90]d · mascarar telefone[x] · esconder técnico[x]│
│   [ Salvar configuração ]   estado: "salvo com segurança" / erro+retry  │
├────────────────────────────────────────────────────────────────────────┤
│ [1] JORNADAS (cards na ordem da esteira; cada card expande)            │
│   ▸ Entrada MQL            ok · 6 rotinas · ⚙ ajustar                   │
│   ▸ Não-MQL                ok · 2 rotinas · ⚙ ajustar                   │
│   ▸ Primeiro contato       ok · fila N · ⚙ ajustar                      │
│   ▸ Follow-up SDR          ok · F1-F4 · textos ✓hash · ⚙ ajustar        │
│   ▸ Agenda/No-show/Introd. ok · confirmações N · ⚙ ajustar              │
│   ▸ WhatsApp / chips       8/8 bridges · limites · ⚙ ajustar            │
│   ▸ Channel / painéis      watchdogs 5 ok · ⚙ ajustar                   │
│   ▸ Backups / Git          backup 5min · git main · ⚙ ajustar          │
├────────────────────────────────────────────────────────────────────────┤
│ [2] INVENTÁRIO TÉCNICO  (recolhido por padrão)                          │
│   scripts · watchdogs · processos · portas — read-only                  │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Anatomia de um card de jornada (ao expandir)
Cada card de jornada tem a **mesma estrutura previsível**:

1. **Cabeçalho** — nome humano, dono (editável), toggle *Ativa/Pausada*, nota livre.
   (Mapeia para `journeyOverrides[key] = {enabled, owner, notes}`.)
2. **Resumo** — 3–4 métricas-chave da jornada (ex.: Follow-up → pendentes /
   prontos / em pesquisa). Mesmas métricas de `_rotinas_centralized_modules`.
3. **Parâmetros editáveis** — só os campos daquela jornada (ver §5).
4. **Ações** — divididas em:
   - **Seguras** (salvar parâmetro, salvar nota) → executam direto.
   - **Guardadas** (rodar cron agora, reiniciar chip, promover deploy, limpar
     fila) → botão em estado **"requer aprovação"**, desabilitado enquanto a
     trava global estiver ligada; ao habilitar, exige modal de confirmação +
     gera log + caminho de rollback.
5. **Atalho para análise** — link "Ver performance desta jornada em Gestão"
   (não duplica dado; só navega).

### 4.4 Estados de cada controle
- **Carregando** — skeleton; nunca trocar erro por "vazio".
- **Salvando** — botão em loading, demais campos travados.
- **Salvo** — toast "Parâmetros salvos com segurança." (já existe `rotinasNotice`).
- **Erro** — mensagem clara + **retry**, sem perder o que o usuário digitou.
- **Bloqueado** — ação perigosa aparece com cadeado e tooltip explicando a trava.
- **Stale/degradado** — quando um módulo absorvido falha (`status: 'atenção'`),
  o card mostra aviso discreto, não some.

### 4.5 Mobile
Mesma hierarquia em coluna única: barra de estado → Config global colapsável →
lista de jornadas → inventário no fim. Sem botões de Followups/Proatividade na
navegação (já removidos).

---

## 5. Modelo de dados / schema JSON sugerido

Evolução **retrocompatível** do `controle/rotinas_orquestracao_config.json` atual
(`version: 1`). A proposta sobe para `version: 2`, **absorvendo a config de
proatividade** e adicionando blocos por jornada — mantendo todo clamp/saneamento
no backend (`sanitize_rotinas_config`).

```jsonc
{
  "version": 2,

  // ---- [0] Config global (já existe em v1) ----
  "autonomyMode": "equilibrado",            // conservador | equilibrado | expansivo
  "notifyOnlyExceptions": true,
  "requireApprovalForDangerousActions": true, // trava fixa nesta fase (backend força true)
  "operatorValidation": "stage-test",        // fluxo aprovado: validar em stage antes

  "messagePolicy": {
    "source": "textos_aprovados",            // nunca texto cru fora do manifesto
    "allowAutoRewrite": false,
    "dailyCapPerChip": 30                     // clamp backend 1..80
  },
  "logPolicy": {
    "retentionDays": 90,                      // clamp 7..365
    "redactPhone": true,
    "showTechnicalDetails": false             // nunca expor técnico em tela de SDR
  },
  "backupPolicy": {
    "enabled": true,
    "intervalMinutes": 5,                     // clamp 5..1440
    "destination": "gdrive/rclone"
  },
  "gitPolicy": {
    "enabled": true,
    "commitAfterValidatedChange": true,
    "branch": "main"
  },

  // ---- [NOVO v2] Proatividade absorvida (hoje em PROATIVIDADE_CONFIG_FILE) ----
  "proactivityPolicy": {
    "autonomyMode": "equilibrado",           // conservador | equilibrado | autonomo
    "reviewWindowHours": 24,                  // clamp 1..10080
    "groupAlertCooldownMin": 60,
    "historyStaleMin": 30,
    "crmDedupeMin": 120,
    "operatorNote": ""                        // <=1000 chars
  },

  // ---- [NOVO v2] Parâmetros por jornada ----
  // Substitui/expande journeyOverrides: além de enabled/owner/notes,
  // cada jornada ganha um sub-objeto "params" tipado e clampado.
  "journeys": {
    "entrada_mql": {
      "enabled": true, "owner": "Dexter", "notes": "",
      "params": {
        "requireResearch": true,
        "scanMaxDeals": 160,                  // clamp p.ex. 20..300
        "generatePdf": true,
        "fixedRulesVersion": 7                // espelha version de FIXED_* (read-only; ver §6)
      }
    },
    "nao_mql": {
      "enabled": true, "owner": "Dexter", "notes": "",
      "params": { "reclassifyAllowed": false, "fixedRulesVersion": 7 }
    },
    "primeiro_contato": {
      "enabled": true, "owner": "Dexter", "notes": "",
      "params": {
        "operationalWindowBrt": "06:00-19:59", // sexta 06:00-17:59 (string validada)
        "fridayWindowBrt": "06:00-17:59",
        "maxNewPerChipPerDay": 30              // herda/override de messagePolicy
      }
    },
    "followup_sdr": {
      "enabled": true, "owner": "Dexter", "notes": "validado em stage",
      "params": {
        "phasesEnabled": ["F1","F2","F3","F4"],
        "approvedTextsFile": "controle/followup_textos_aprovados_rafael_20260630.json",
        "approvedTextsSha256Ok": true,         // calculado no backend, read-only na UI
        "minHoursBetweenPhases": 24,
        "requireResearch": true
      }
    },
    "agenda_no_show": {
      "enabled": true, "owner": "Dexter", "notes": "",
      "params": {
        "confirmEnabled": true,
        "reminderHoursBefore": 3,
        "rescheduleOnNoShow": true,
        "introHandoffEnabled": true            // etapa Agendamento/Introdução
      }
    },
    "whatsapp_infra": {
      "enabled": true, "owner": "Dexter", "notes": "",
      "params": {
        "expectedBridges": 8,
        "dailyCapPerChip": 30,                  // espelha messagePolicy
        "qualityMonitorEnabled": true
        // reiniciar bridge/chip = AÇÃO GUARDADA, nunca um campo aqui
      }
    },
    "channel_ui": {
      "enabled": true, "owner": "Dexter", "notes": "",
      "params": { "watchdogIntervalMin": 5, "msgsApiTargetMaxMs": 1500 }
    },
    "backups_git": {
      "enabled": true, "owner": "Dexter", "notes": "",
      "params": {
        "releaseGateRequired": true,
        "stageRequiredBeforePromote": true,
        "autoRollbackOnPromoteFail": true
      }
    }
  },

  // ---- [NOVO v2] Crons declarados (flag liga/desliga; disparo = ação guardada) ----
  "crons": [
    { "id": "followup_sdr_cadence", "journey": "followup_sdr", "enabled": false,
      "scheduleHuman": "a cada 15 min em janela", "dangerousToRun": true },
    { "id": "incoming_response_alert", "journey": "entrada_mql", "enabled": true,
      "scheduleHuman": "a cada 5 min", "dangerousToRun": false }
    // origem real: dexter_center_report; aqui guardamos só o override seguro
  ],

  // ---- Auditoria interna (NUNCA renderizada como bloco "auditoria" na UI) ----
  "_meta": {
    "lastSavedBy": "rafael",
    "lastSavedAtBrt": "2026-06-30T00:00:00-03:00",
    "schemaMigratedFrom": 1
  }
}
```

### 5.1 Regras de saneamento (backend, obrigatórias)
- **Migração v1→v2**: ler v1, mapear `journeyOverrides` → `journeys[key].{enabled,owner,notes}`, importar `PROATIVIDADE_CONFIG_FILE` → `proactivityPolicy`, então gravar v2. Manter leitura de v1 por compat.
- **Clamp de todo número** (faixas indicadas acima); **whitelist de enums**;
  **truncamento de strings**; **regex de branch** (já feito hoje).
- `requireApprovalForDangerousActions` é **forçado a `true`** pelo backend nesta fase, independentemente do payload.
- Campos calculados (`approvedTextsSha256Ok`, `fixedRulesVersion`,
  `_meta.lastSaved*`) são **read-only na UI**: o POST os ignora e o backend os recomputa.
- **`approvedTextsFile` não aceita caminho arbitrário** — só nomes dentro de
  `controle/` que casem com o padrão do manifesto (evita path traversal).
- Escrita **atômica** (tmp + replace), como já é hoje.

### 5.2 Onde ficam as fontes (não duplicar)
- **Fonte de verdade de comportamento** = este JSON (parâmetros) + `FIXED_*`
  (regras imutáveis no código) + manifesto de textos (com hash).
- **Fonte de verdade de resultado** = HubSpot (via `pipeline_focus`), ledger
  outbound, métricas — lidas pela Gestão, nunca regravadas por Rotinas.

---

## 6. Regras anti-redundância

Cada função tem **um dono e uma tela principal**. As demais aparições são
*links* ou *resumos read-only*, nunca cópias editáveis.

| Concorrência histórica | Resolução |
|---|---|
| **Followups** (aba) vs Rotinas vs Gestão | Configuração de follow-up (textos, fases, cadência, pesquisa) = **só Rotinas → Follow-up**. Performance de follow-up (taxa de resposta/agenda) = **só Gestão**. `/followups` redireciona para `/rotinas`. |
| **Proatividade** (aba) vs Rotinas | `proatividade_config` passa a ser editada **dentro de Rotinas** (`proactivityPolicy`). `/proatividade` redireciona. O summary de decisões/execuções vira **resumo read-only** no card da jornada + atalho para Gestão. |
| **Dexter Center** (aba/bloco) vs Rotinas vs Gestão | Crons e contextos = **governança em Rotinas** (flag liga/desliga). Saúde/observabilidade = **resumo read-only**. Nenhum bloco "Dexter Center" solto em Gestão/Agendas. |
| **Foco** vs Rotinas | Foco é **execução do SDR** ("o que fazer agora"), nunca configuração. Rotinas nunca mostra fila de execução individual de SDR. |
| **Gestão** vs Rotinas | Gestão **só lê/mede** (HubSpot, ledger). Rotinas **só parametriza**. Proibido Rotinas recalcular KPI de Gestão e proibido Gestão editar parâmetro. Comunicação só por link. |
| Inventário de scripts em vários lugares | Um único inventário recolhível em Rotinas. Jornadas mostram contagem, não a lista crua. |
| Incoming MQL textos/regras | Permanecem em `FIXED_*` no código (rigidez por design — ver memória `incoming-policy-rigidity`). Rotinas **exibe** a versão e permite *bump* controlado, mas **não** transforma regra fixa em campo livre. `nao_mql_grupo` nunca é chip original Não-MQL→MQL. |

Regra de ouro de UI (CLAUDE.md §7): **nada de cards/rótulos "auditoria",
"log", "ledger", "evento técnico"** em telas de SDR. Ledger/history são fontes
internas (dedupe/privacidade/reconstrução); na UI enriquecem a bolha real, não
viram bloco. Em `/rotinas` (tela do Rafael) usamos linguagem humana mesmo assim,
para nunca arriscar vazamento por reuso de componente.

### 6.1 Teste de decisão (para futuras features)
Antes de criar qualquer tela nova, responder:
1. **Edita comportamento futuro?** → vai para `/rotinas`, dentro de uma jornada.
2. **Só mede o passado?** → vai para `/gestao`.
3. **É execução do SDR no dia?** → `/foco` ou `/conversas`.
4. Se "precisa de aba própria", a resposta padrão é **não** — encaixar em uma
   das quatro acima.

---

## 7. Plano incremental de implementação

Cada passo é pequeno, testável e respeita o fluxo: editar → `release_gate` →
`safe_deploy stage` → (Rafael/Dexter promove). Claude Code **não** promove.

> **Pré-condição transversal:** seguir o handoff vigente — Followups/Proatividade/
> Dexter Center estão **pausados aguardando Dexter**. Estes passos são de design e
> de preparação de config; **não reativar cron nem promover** sem ordem explícita.

### Passo 1 — Renomear label da jornada de agenda (taxonomia)
- **O quê:** label de `agenda_no_show` → "Agenda / No-show / Introdução"
  (mantém `key`).
- **Aceite:** `GET /api/rotinas/summary` retorna o novo label; `journeyOverrides`
  antigos continuam casando; teste de rotas verde.

### Passo 2 — Schema v2 com migração v1→v2 (backend, sem UI nova)
- **O quê:** estender `ROTINAS_CONFIG_DEFAULTS` + `sanitize_rotinas_config` para
  `version: 2`, com `journeys{}`, `crons[]`, `_meta`; migração lê v1.
- **Aceite:** carregar um arquivo v1 antigo produz v2 saneado; campos calculados
  ignorados no POST; clamps cobertos por teste em `tests/test_channel_v2_core.py`.

### Passo 3 — Absorver `proactivityPolicy` no schema
- **O quê:** importar `PROATIVIDADE_CONFIG_FILE` para `proactivityPolicy`;
  `save_rotinas_config` passa a ser a fonte; manter leitura legada por compat.
- **Aceite:** editar proatividade em Rotinas persiste e é lido de volta; nenhuma
  regressão em `proatividade_summary`.

### Passo 4 — Card de jornada com parâmetros editáveis (UI, uma jornada piloto)
- **O quê:** implementar o card §4.3 só para **Follow-up SDR** (piloto):
  toggle/owner/notes + `minHoursBetweenPhases` + visão hash dos textos (read-only).
- **Aceite:** salvar parâmetro reflete no JSON; estado salvo/erro/retry corretos;
  nenhum termo técnico visível; `node --check` do JS extraído passa.

### Passo 5 — Replicar o padrão de card para as demais jornadas
- **O quê:** mesmo componente para as outras 7 jornadas, lendo `journeys[key].params`.
- **Aceite:** cada jornada mostra só seus campos; smoke gate de rotas verde.

### Passo 6 — Ações guardadas (UI de confirmação, sem executar)
- **O quê:** botões de ação perigosa em estado "requer aprovação" (cadeado,
  tooltip, modal de confirmação), **sem disparar** enquanto a trava global está
  ligada. Apenas registra intenção em log interno.
- **Aceite:** com trava ligada, nenhum POST de ação perigosa executa; teste
  garante 403/no-op; UI mostra cadeado.

### Passo 7 — Links cruzados Rotinas ↔ Gestão
- **O quê:** atalho "ver performance" em cada card → rota correspondente em
  `/gestao`; e em Gestão, atalho "ajustar parâmetro" → `/rotinas`.
- **Aceite:** navegação funciona; nenhum dado de KPI é recalculado em Rotinas;
  nenhuma config é editável na Gestão.

### Passo 8 — Limpeza de redundância de navegação
- **O quê:** confirmar que `/followups` e `/proatividade` só redirecionam; nenhum
  bloco "Dexter Center" solto; inventário único recolhível.
- **Aceite:** testes de rota/centralização verdes; `summary.modules` contém
  followups/proatividade/dexter_center como resumo.

### Validação obrigatória em todo passo
```bash
scripts/channel_v2_release_gate.sh
scripts/channel_v2_safe_deploy.sh stage
```
(O `stage` prova a versão candidata em cópia isolada na porta privada 8891.
Promoção é decisão de Rafael/Dexter, fora do escopo do Claude Code.)

---

## 8. Riscos e guardrails

| Risco | Guardrail |
|---|---|
| Quebrar config existente na migração v1→v2 | Migração idempotente + leitura de v1 mantida; backup do JSON antes de gravar; escrita atômica; teste de migração. |
| Campo editável virar vetor de ação perigosa | Ações perigosas **nunca** são campo de form; são botões guardados com `requireApprovalForDangerousActions=true` forçado no backend. |
| Frontend mandar valor inválido | `sanitize_rotinas_config` faz clamp/whitelist/truncate; backend ignora campos calculados; path traversal bloqueado em `approvedTextsFile`. |
| Vazar termo técnico/"auditoria" para SDR | Componentes de Rotinas isolados das telas de SDR; revisão obrigatória de texto antes de entregar UI (CLAUDE.md §7). |
| Morosidade ao abrir `/rotinas` | Endpoints locais; `_rotinas_centralized_modules` já evita recursão e não recomputa inbox; não varrer `wpp_envios` grande no hot path (paginar/limitar). |
| Reativar cron/bridge sem ordem | Followups/Proatividade/Dexter **pausados aguardando Dexter**; nenhum passo aqui liga cron ou reinicia chip; só parametriza. |
| Promoção indevida | Claude Code só roda `stage`; promote/deploy é decisão humana; rollback automático se promote falhar. |
| Privacidade de comunicadores | Rotinas nunca expõe conversa pessoal de comunicador; só envio operacional registrado + resposta no chat operacional (CLAUDE.md §3). |
| Conflito Rotinas × Gestão (duplicar dado) | Fronteira §1.3/§6: Rotinas parametriza, Gestão mede; comunicação só por link; teste pode checar que Rotinas não expõe KPI de Gestão e vice-versa. |
| Auth/secrets | Não tocar em auth/secrets/logs grandes; `/rotinas` continua Rafael/admin-only (`rotinas_access_allowed`). |

---

## 9. Resumo executivo

- **`/rotinas` = configurar a esteira** (entrada → qualificação → primeiro
  contato → follow-up → agenda/no-show → introdução), por jornada, com
  parâmetros seguros e ações perigosas travadas.
- **`/gestao` = medir a esteira** (mantém todas as análises atuais, sem perda).
- **`/foco` e `/conversas` = executar** (SDR).
- O schema `rotinas_orquestracao_config.json` evolui para **v2**, absorvendo
  proatividade e ganhando blocos por jornada, sem quebrar v1.
- **Anti-redundância** garantida pela regra "configura vs mede" e pelo teste de
  decisão de 4 perguntas para qualquer feature futura.
- Implementação **incremental e validada em stage**, sem promoção autônoma e
  respeitando os handoffs de pausa vigentes.
