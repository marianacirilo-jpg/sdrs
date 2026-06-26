# Zydon Channel V2 — Notas de Design

Documento que acompanha o mockup `design/channel-v2-mockup.html`. Explica as decisões visuais e de UX, e mapeia o caminho para portar isso para produção em `scripts/channel_panel.py` **sem reescrever o backend**.

> O mockup é exploratório e self-contained (HTML/CSS/JS puro, só Google Fonts Inter). Não toca em produção, bridges ou crons. Abra o arquivo direto no navegador.

---

## 1. Objetivo do redesign

Tirar o Channel da cara de "log técnico / trabalho de faculdade" e levá-lo a um **SaaS comercial premium B2B**, no nível de Linear/Superhuman (precisão dark) + Intercom (conversa com contexto). A meta operacional é a do plano: **o SDR entende em 5 segundos o que precisa responder.**

Tudo no mockup serve a essa frase.

---

## 2. Direção visual aplicada

| Token | Valor | Uso |
|---|---|---|
| Background | `#06080A` | fundo profundo, quase preto |
| Painel | `#0E1114` / `#0B0E11` | colunas |
| Surface | `rgba(255,255,255,.035)` | cards/inputs, elevação por luz, não por cor |
| Border | `rgba(255,255,255,.08)` | bordas finas (1px), nunca pretas duras |
| Texto | `#F4F7F5` / `#A7B0AA` / `#68736D` | 3 níveis de hierarquia |
| Accent Zydon | `#CDEB00` | **só** prioridade, resposta do lead, ação primária e logo |
| Success/Warn/Danger | `#20C997` / `#F7B955` / `#FF6B6B` | status, SLA, saúde do chip |

Princípios que diferenciam de dashboard amador:

- **Accent com parcimônia.** O verde aparece em ~5 lugares por tela (logo, fila quente, bolha do lead, botão Responder, score quente). O resto é grayscale quente. É o que separa "premium" de "carnaval".
- **Elevação por luz, não por caixa.** Superfícies são branco translúcido sobre fundo escuro, com 1px de borda sutil — em vez de blocos com fundo sólido e sombra pesada.
- **Tipografia Inter 400–800**, `letter-spacing` levemente negativo nos títulos, `tabular-nums` em horários/contadores. Densidade alta sem poluição.
- **Sem aparência de tabela.** A lista é um feed de cards, não linhas de planilha.
- **Microinterações discretas:** SLA "Responder agora" pulsa, hover suave, ring de score em SVG.

---

## 3. Layout — 4 zonas

```
┌──────────┬──────────────┬───────────────────────┬───────────────┐
│ Sidebar  │ Lista de     │ Conversa              │ Contexto      │
│ filas +  │ conversas    │ (timeline + composer) │ comercial     │
│ chips    │ (feed cards) │                       │ (HubSpot etc) │
└──────────┴──────────────┴───────────────────────┴───────────────┘
   248px        392px              flex                  340px
```

### Zona 1 — Sidebar / Filas
- Logo Zydon Channel (raio verde) + subtítulo "Inbox comercial".
- Filas operacionais com contador e ícone: **Responder agora** (quente, em verde), Meus leads, Sem resposta, Diagnóstico enviado, 1º contato SDR, Resolvidas, Erros/Offline (com ponto de alerta vermelho).
- Bloco **Saúde dos chips**: 8 chips com bolinha de status (online/atenção/offline) e volume/dia. Resolve o pedido "Rafael auditar todos os chips sem abrir WhatsApp".
- Rodapé com usuário logado + admin.

### Zona 2 — Lista de conversas
- **Busca grande** no topo (atalho `/`), placeholder "empresa, contato, telefone".
- Subcabeçalho com nome da fila + contagem + toggle **Prioridade / Recentes**.
- Filtros em chips: **Todos / por SDR (com avatar) / por chip**.
- **Cards de conversa** (não tabela), cada um com:
  - Empresa em destaque + horário relativo (verde se urgente).
  - Contato · cargo.
  - Preview da última mensagem com **origem colorida** (`Lead:` verde / `SDR:` / `Auto:` azul).
  - Linha de metadados: **badge de etapa** (Diagnóstico / 1º contato / Respondeu / Reunião / Falha), **owner com avatar**, e **SLA** ("Responder agora" pulsante / "há 3h sem resposta").
  - Conversas com **resposta do lead sobem ao topo** e ganham faixa verde sutil + ponto de não-lido.
- Empty state decente: "Nada para responder agora 🎉".

### Zona 3 — Conversa
- Header **comercial, não técnico**: avatar da empresa, nome + badge de etapa, contato·cargo, telefone **mascarado** (`+55 11 9•••• ••32`), owner + chip. **Nada de JID bruto.**
- Ações claras no header: **Agendar, Resolver**, busca, e toggle do painel de contexto.
- Timeline com **separadores por dia**.
- **Cards de evento de automação** ("Diagnóstico enviado", "1º contato SDR", "Reunião agendada", "Falha no envio") — visualmente distintos das bolhas.
- **PDF card** bonito (ícone vermelho, nome, tamanho, botão download).
- **Bolhas limpas** com autor/chip discreto e check de entregue/lida.
- **Resposta do lead destacada**: faixa "Resposta do lead" + bolha verde com glow.
- **Composer premium**: quick replies (incluindo "✨ Sugestão IA"), abas **Responder / Nota interna** (a nota fica âmbar), anexar arquivo, enviar PDF/diagnóstico, emoji, dica de atalho.

### Zona 4 — Contexto comercial
- Identidade do lead + **score de prioridade** (ring SVG) + etiquetas (quentes em verde).
- **Próxima ação sugerida** em destaque, com botões **Responder / Criar tarefa**.
- **HubSpot** (badge "Conectado"): owner, deal stage, lifecycle, última atividade.
- **Notas internas** + adicionar nota.
- **Histórico de automações** em timeline vertical.
- **Saúde do chip** desta conversa: volume/cap, taxa de resposta, risco de bloqueio, status. Porta/chip aparecem aqui como **metadado discreto** ("porta 4604").

---

## 4. Conteúdo mockado

Dados representativos no array `CONV` do JS, filtráveis/clicáveis de verdade:

- **Grupo Maranno** — resposta do lead *"Tenho interesse, consigo ver amanhã?"* (topo, fila Responder agora, chip Sarah 2).
- **LightShip Embalagens** — diagnóstico enviado, sem resposta há 3h (Sarah 2).
- **IA Crono** — 1º contato Breno.
- **HIPER STOK** — 1º contato Lucas.
- **Caffeine Army** — lead pediu preço (segunda resposta quente).
- **Copperbras** — reunião marcada.
- **Schmidt Alimentos** — erro de envio (chip instável) → popula a fila Erros/Offline.

O JS implementa de verdade: troca de fila, filtro por SDR, busca, seleção de conversa, render da timeline/contexto, toggle Responder/Nota, drawer mobile.

---

## 5. Decisões de UX que atacam o briefing

- **"Saber em 5s o que responder"** → fila *Responder agora* + SLA pulsante + ordenação que joga respostas de lead pro topo + bloco *Próxima ação sugerida*.
- **Sem JID bruto** → telefone mascarado e título sempre por empresa; JID/porta nunca aparecem na coluna principal.
- **Porta/chip como metadado** → chip vira "Sarah 2"; a porta `4604` só aparece em cinza no painel de saúde.
- **Botões de operação** → Responder, Agendar, Criar tarefa, Resolver (linguagem comercial, não "Atualizar/Enviar").
- **Separar automação de resposta real** → eventos de automação têm card próprio; só `fromMe:false` vira "Resposta do lead" com destaque.
- **Responsivo** → ≤1180px o contexto vira drawer; ≤820px vira fluxo lista → conversa → contexto com tabbar inferior.

---

## 6. Caminho de implementação em `scripts/channel_panel.py`

O backend atual **já entrega 80% dos dados** que o mockup mostra. A migração é principalmente de template/CSS, não de arquitetura. Sugestão por etapas (alinhada à Fase 0/Sprint 1 do plano):

### 6.1 Troca de casca visual (baixo risco, alto impacto)
- Substituir o bloco `HTML` (string em `channel_panel.py:178`) pelo HTML/CSS deste mockup.
- Manter os endpoints atuais: `/api/conversations`, `/api/messages`, `/api/send`. O JS de produção continua chamando eles; só muda o render.
- Mapear o que já existe:
  - `conversations()` já produz `title` (empresa), `subtitle` (contato·sdr), `portLabel`, `responses`, `lastTime`, `lastSource` → vira o card.
  - `source_label()` já distingue 1º contato / diagnóstico texto / PDF / resposta → vira **badge** e **card de evento**.
  - `messages_for()` já traz as mensagens com `fromMe`, `type`, `mediaPath` → vira timeline + PDF card.
  - `PORTS` já mapeia porta→label/owner/role → vira owner+chip+filtro por SDR.
  - `bridge_status(port)` já existe → alimenta **Saúde dos chips** (online/offline real).

### 6.2 Campos novos a derivar (sem schema novo, só cálculo no Python)
- **SLA / "tempo sem resposta"**: `now - lastTime` quando a última mensagem é `fromMe`; "Responder agora" quando a última é do lead.
- **Filas**: derivar de dados que já existem —
  - *Responder agora* = `lastIncoming.timestamp > último fromMe` (lead respondeu por último).
  - *Sem resposta* = última é `fromMe` e sem resposta.
  - *Diagnóstico enviado* = existe msg `cron-mql-*`.
  - *1º contato SDR* = existe `cron-sdr-primeiro-contato` e nenhuma resposta.
  - *Erros/Offline* = `bridge_status` offline **ou** flag de falha de envio.
- **Separadores por dia**: agrupar `messages_for()` por `date(timestamp)` no front.
- **Day/relative time**: formatar no JS (`Intl.RelativeTimeFormat` pt-BR).

### 6.3 Campos que exigem persistência nova (Sprint 1/2 — opcional, degradação graciosa)
Renderizar como placeholders elegantes até existirem; o painel não quebra sem eles:
- **Notas internas, Resolver/Pendenciar, Atribuir** → tabela leve (começar com JSON em `controle/`, depois SQLite conforme Fase 5 do plano).
- **Score / Próxima ação / HubSpot (owner, stage, lifecycle)** → Fase 2/3 (MCP HubSpot já disponível no ambiente). Enquanto não houver, esconder a seção ou mostrar "—".
- **Quick replies por SDR** → arquivo de config por usuário.

### 6.4 Ordem recomendada
1. Trocar casca visual + esconder JID/porta + filas derivadas + SLA (tudo computável hoje).
2. Notas internas + Resolver/Pendenciar (persistência mínima).
3. HubSpot real no painel de contexto (owner/stage/lifecycle/última atividade).
4. Score e "próxima ação" (heurística simples → IA depois).

---

## 7. O que ainda é fake no mockup (não confundir com pronto)

- Score, "próxima ação sugerida", lifecycle/deal stage do HubSpot, notas e taxa de resposta/risco de bloqueio são **valores ilustrativos**.
- Botões (Agendar, Criar tarefa, Resolver, anexar, enviar) não têm ação real — é mockup de aprovação visual.
- Quick replies de IA são placeholders.

---

## 8. Próximos passos sugeridos

1. **Aprovar a direção visual** com o Rafael (esta tela).
2. Ajustar detalhes de marca (logo definitivo, tom do verde em telas reais).
3. Implementar **6.1 + 6.2** em um branch de produção — ganho de percepção imediato sem mexer em dados.
4. Planejar persistência mínima (notas/resolver) e integração HubSpot conforme Fases 1–3 do `channel-evolution-plan.md`.
