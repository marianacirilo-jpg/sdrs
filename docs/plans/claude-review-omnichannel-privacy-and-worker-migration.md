# Revisão crítica — Privacidade/Grupos e migração para worker central (Channel V2 / SDRs Zydon)

> Revisão de código somente leitura. Data: 2026-07-01. Autor: Claude Code.
> Escopo lido: `scripts/channel_panel_v2.py`, `scripts/whatsapp_jid_utils.py`,
> `scripts/whatsapp_dispatch_worker.py`, `scripts/whatsapp_worker_completions.py`,
> `scripts/whatsapp_dispatch_flow.py`, `scripts/agenda_queue_sender.py`,
> `scripts/non_mql_legit_outreach.py`, `scripts/cadencia_primeiro_contato.py`,
> `disparo_dinamico.py`, `scripts/whatsapp_dispatch_queue.py` (referência) e os testes
> `tests/test_channel_v2_core.py`, `tests/test_whatsapp_dispatch_queue.py`,
> `tests/test_non_mql_worker_owned_cutover.py`, `tests/test_agenda_queue_worker_owned_cutover.py`,
> `tests/channel_v2_smoke_gate.py`.
>
> **Nada foi editado, nenhum teste longo foi executado, nenhum processo reiniciado.** Todas
> as referências `arquivo:linha` são aproximadas (arquivos vivos mudam) — confirmar antes de editar.

---

## Sumário executivo

O painel Channel V2 já tem várias camadas reais de defesa de privacidade (filtro de grupo em
`/api/conversations`, bloqueio de par Rafael↔Mariana, exigência de origem operacional, contrato de
"não inventar bolha" bem testado). O ponto frágil **não é o painel de leitura consolidado; é a
inconsistência entre as defesas**:

1. **O filtro de grupo/interno está reimplementado em vários lugares com regras diferentes**, em vez
   de um único ponto que use `whatsapp_jid_utils.is_group_or_broadcast()`. O utilitário canônico
   existe mas **quase não é chamado** — as guardas fazem `endswith('@g.us')` na mão.
2. **O caminho de disparo (flow → fila → worker) tem uma blocklist interna mais fraca que o painel.**
   O painel conhece 7 números internos (`INTERNAL_WPP_DIGITS`); o flow e o worker só bloqueiam 2
   (Rafael/Mariana) e só bloqueiam `@g.us` (não `@broadcast`/`status@broadcast`). Um disparo
   `worker_owned` para um chip interno de SDR (Sarah/Breno/Lucas Batista/Lucas Resende) ou para um
   `@broadcast` **não seria barrado**.
3. **A própria fila (`whatsapp_dispatch_queue.py`) não tem guarda de grupo/interno alguma** — confia
   100% em quem chama. Isso é aceitável enquanto todos os produtores passam pelo `flow`, mas é uma
   dependência implícita e não testada como invariante da fila.
4. **A migração para `worker_owned` só está pronta para `agenda` e `nao_mql`.** Os dois maiores
   volumes — `disparo_dinamico.py` (primeiro contato/proatividade/diagnóstico) e
   `cadencia_primeiro_contato.py` (follow 1–4) — só fazem *shadow dual-write*; ainda enviam pelo
   caminho legado. Faltam os completion hooks (`followup`, `first_contact`/`proatividade`,
   `diagnostico`) e suporte robusto a *parts/sequence* com delays no worker.

Recomendação central: **antes de expandir omnichannel, consolidar o filtro de privacidade em um
único helper e alinhar a blocklist do caminho de disparo com a do painel.** Depois, migrar os fluxos
restantes na ordem `disparo_dinamico` (proatividade/first_contact) → `cadencia` (follow) →
`diagnóstico/PDF`, cada um atrás de flag e com completion hook próprio + teste de cutover.

---

## Achados de risco

### R1 — Blocklist interna e de grupo do caminho de disparo é mais fraca que a do painel (ALTO)
- `scripts/whatsapp_dispatch_flow.py:83` — `record_dispatch_shadow_from_row` só barra `to` que
  `endswith('@g.us')` **ou** está em `{'553484255965@s.whatsapp.net','553496698718@s.whatsapp.net'}`.
- `scripts/whatsapp_dispatch_worker.py:128-131` — `_validate_live_row` repete exatamente as mesmas
  duas condições (`@g.us` + os mesmos 2 números).
- Já o painel conhece **7** números internos em `INTERNAL_WPP_DIGITS`
  (`channel_panel_v2.py:~3648-3655`: Mariana, Sarah antigo, Sarah canônico, Breno, Lucas Batista,
  Lucas Resende, Rafael).
- **Consequência:** um `record_dispatch_worker_owned` com destino de chip interno de SDR (ex.
  Breno `553484325076`, Sarah `553484291640`, Lucas Batista `553484295409`, Lucas Resende
  `553484428888`) **não é bloqueado** nem no enqueue nem no envio live. Também **`@broadcast` e
  `status@broadcast` não são bloqueados** (só `@g.us`).
- **Regra violada em potencial:** "nunca enviar/registrar conversa interna de comunicador" e "nunca
  trazer grupo". Hoje o volume real vem de `agenda`/`nao_mql`, que têm destino de lead validado
  antes; o risco cresce quando `disparo_dinamico`/`cadencia` migrarem, pois passam por seleção de
  porta de comunicador e round-robin.

### R2 — `is_group_or_broadcast()` existe mas quase não é usado; filtro espalhado (ALTO)
- `scripts/whatsapp_jid_utils.py:19-21` define `is_group_or_broadcast` cobrindo `@g.us`, `@broadcast`
  e `status@broadcast`.
- No painel e no caminho de disparo o filtro é feito com `endswith('@g.us')` manual em múltiplos
  pontos (ex. `channel_panel_v2.py:~4190`, `disparo_dinamico.py:334,374,1409,1429`,
  `whatsapp_dispatch_flow.py:83`, `whatsapp_dispatch_worker.py:128`). `@broadcast` fica de fora em
  vários deles.
- **Consequência:** cada novo ponto de leitura/escrita pode esquecer o filtro completo. DRY quebrado
  → risco recorrente de regressão de privacidade.

### R3 — Leitura crua de history sem filtro de grupo em ponto de métrica (MÉDIO)
- `channel_panel_v2.py` `_history_raw_rows()` (~1357-1372) retorna o JSON bruto do device sem filtrar
  grupo/broadcast; é a base de várias leituras.
- Os consumidores de **exibição** (`_raw_history_for_chat`/`_timeline_source_for_chat`, ~4695-4843)
  ficam protegidos por `message_matches_chat` + `is_real_device_timeline_message`, então a bolha na
  UI continua fiel ao device (bom, contrato mantido).
- Porém `_dispatch_response_attribution()` (~2524-2572) itera `_history_raw_rows(port)` e usa
  `canonical_chat_for_message(m)` **sem** checar `is_group_or_broadcast`. Uma resposta vinda de grupo
  pode ser atribuída a um disparo individual.
- **Consequência:** não é vazamento de bolha para o SDR (não vira mensagem na tela), mas **infla
  métrica de retorno** e pode "casar" resposta de grupo com um lead. Impacto de dado/relatório, não
  de UI. Confirmar em `dispatch_stats`/telas de gestão que consomem essa atribuição.

### R4 — Fila central não tem invariante de privacidade próprio (MÉDIO)
- `scripts/whatsapp_dispatch_queue.py` valida `origin` (lista fixa de 7), campos obrigatórios, dedupe
  e locks, mas **não** rejeita destino grupo/interno; `_jid_and_phone` inclusive aceita e normaliza
  `@g.us`.
- A guarda vive só em `flow.record_dispatch_shadow_from_row`. Se algum produtor futuro chamar
  `enqueue_dispatch`/`record_dispatch_worker_owned` direto (o `non_mql` e `agenda` já chamam
  `record_dispatch_worker_owned`, que **não** passa pela checagem de grupo de `_from_row`), a fila
  aceita.
- **Nota importante:** `record_dispatch_worker_owned(**kwargs)` (`flow.py:68-75`) só injeta
  `execution_mode='worker_owned'` e chama `record_dispatch_shadow` — que **não tem** a checagem de
  grupo/interno que existe em `record_dispatch_shadow_from_row`. Ou seja, o caminho worker_owned de
  `agenda` e `nao_mql` hoje depende exclusivamente de o `to` já vir limpo do produtor e da
  segunda linha de defesa em `_validate_live_row` (que é a blocklist fraca de R1).

### R5 — Lacunas de teste que deixam R1–R4 sem trava (ALTO, ver seção própria)
- Não há teste garantindo que `@g.us`/`@broadcast`/números internos são barrados no **enqueue** nem
  no **worker live** para todos os 7 números.
- Não há teste garantindo que `_dispatch_response_attribution` ignora grupo.
- Não há teste de `start-conversation` bloqueando `@g.us` (só há bloqueio de número institucional).

### R6 — Duas cópias divergentes da lógica de completion da agenda (BAIXO/MÉDIO — dívida)
- `scripts/whatsapp_worker_completions.py:_complete_agenda_queue` (47-107) e
  `scripts/agenda_queue_sender.py:mark_wpp_agenda_done` (50-72) implementam a mesma reconciliação de
  ledger quase idêntica. Divergência futura entre as duas pode gerar registro inconsistente
  (dedupe/privacidade dependem desse ledger). Unificar quando a agenda for 100% worker_owned.

### R7 — `agenda_queue_sender` salva a fila mas segue no caminho legado quando flag off (INFO)
- `agenda_queue_sender.py:131-169` só entra em worker_owned sob `ZYDON_AGENDA_WORKER_OWNED`. Enquanto
  a flag estiver off, o envio real continua em `pg.post_bridge_with_retries_locked` (159). Correto
  para a fase atual; só registrar que a promoção de fluxo é por flag, não por deploy.

---

## Testes recomendados

Contratos que faltam para garantir que grupo e conversa íntima nunca apareçam nem sejam disparados.
Priorizados por risco. (Adicionar aos arquivos indicados; manter termos técnicos só em teste.)

### Prioridade 1 — travar o caminho de disparo (fecha R1/R4)
Em `tests/test_whatsapp_dispatch_queue.py` (ou novo `test_whatsapp_dispatch_flow_contract.py`):
1. `record_dispatch_shadow_from_row` e `record_dispatch_worker_owned` **rejeitam** `@g.us`,
   `@broadcast` e `status@broadcast`.
2. Ambos rejeitam **todos os 7** números internos de `INTERNAL_WPP_DIGITS` (parametrizar a lista a
   partir de uma fonte única — ver Próximos passos), não só os 2 atuais.
3. `whatsapp_dispatch_worker._validate_live_row` bloqueia grupo/broadcast e os 7 internos, com
   `blocked += 1` e sem chamar transporte (estender o teste
   `test_live_worker_blocks_incomplete_worker_owned_rows_without_sending`).
4. A própria `enqueue_dispatch` (invariante de fila) rejeita destino de grupo/interno — ou, se a
   decisão for manter a guarda só no flow, um teste que documente e trave essa fronteira.

### Prioridade 2 — travar o painel (fecha R3/R5)
Em `tests/test_channel_v2_core.py`:
5. `_dispatch_response_attribution` ignora mensagem de grupo/broadcast (não atribui resposta de
   `@g.us` a disparo individual).
6. `/api/messages?conv=PORT::<grupo@g.us>` retorna `[]` (não vaza timeline de grupo mesmo se o JID
   estiver no history do device).
7. `start-conversation`/criação de conversa rejeita `@g.us` e número interno (hoje só há
   `test_new_conversation_blocks_institutional_and_internal_numbers` para institucional 4610).
8. SDR não vê nenhum dos 7 números internos no inbox (hoje só Rafael↔Mariana é coberto).

### Prioridade 3 — reforço/anti-regressão
9. Smoke gate (`tests/channel_v2_smoke_gate.py`): adicionar asserção de que nenhuma conversa listada
   em `/api/conversations` tem `chat` terminando em `@g.us`/`@broadcast` e que nenhum JID interno
   aparece. (Hoje o gate valida rotas, contagem e cópia visível, mas não varre os JIDs retornados.)
10. Teste único de "fonte de verdade de JID": todo ponto de leitura de history usa
    `is_group_or_broadcast` (garantido por um helper compartilhado) — teste de unidade do helper com
    a matriz `@g.us`/`@broadcast`/`status@broadcast`/`@lid`/PN.

---

## Plano de migração (ordem segura para terminar worker_owned)

Estado atual: `agenda` e `nao_mql` têm caminho `worker_owned` + completion + teste de cutover;
`disparo_dinamico` e `cadencia` só fazem shadow. Worker live só envia linhas `execution_mode ==
'worker_owned'` (`whatsapp_dispatch_worker.py:124,153`), então shadow nunca é enviado — o cutover é
por produtor e por flag, o que permite promoção gradual sem tocar produção diretamente.

**Fase 0 — Hardening de privacidade (pré-requisito, antes de migrar volume novo).**
- Fechar R1/R2/R4: helper único de guarda de destino (grupo/broadcast/interno) usado por
  `record_dispatch_shadow`, `record_dispatch_worker_owned` e `_validate_live_row`; alinhar a
  blocklist com `INTERNAL_WPP_DIGITS` (fonte única). Adicionar testes de Prioridade 1.
- Justificativa de ordem: `disparo_dinamico`/`cadencia` selecionam porta de comunicador e fazem
  round-robin; migrá-los antes do hardening amplia a superfície de R1.

**Fase 1 — `disparo_dinamico.py` proatividade/first_contact.**
- É o fluxo mais simples de um envio por lead (sem cadência multi-tentativa). Já tem shadow em
  `~163-169`; envio legado em `~1964`.
- Criar completion hook `proatividade`/`first_contact` em `whatsapp_worker_completions.py`
  (registrar `enviado_lead`/`primeiro_contato`, criar task HubSpot, mover deal
  "Lead Sem Contato"→"Primeiro Contato").
- Adicionar `record_dispatch_worker_owned` sob flag `ZYDON_DISPARO_DINAMICO_WORKER_OWNED`, sem
  chamar o envio legado quando a flag estiver on.
- **Bloqueio técnico a resolver antes:** *parts/sequence* com delays. O split em até 3 bolhas com
  `delay_schedule` (12–60s) vive em `disparo_dinamico.py:~1177-1296`. O worker já sabe enviar
  `parts` + `delay_schedule` (`whatsapp_dispatch_worker.py:_send_parts_sequence:72-97`, coberto por
  `test_live_worker_sends_parts_in_order_for_sequence_dispatch`). Garantir que o produtor
  enfileire `parts`/`delay_schedule` já renderizados, não o texto único.
- Teste de cutover espelhando `test_non_mql_worker_owned_cutover.py` (legacy send proibido; enfileira
  worker_owned; completion grava ledger/task só após envio ok).

**Fase 2 — `cadencia_primeiro_contato.py` follow 1–4.**
- Depende do hook `followup` (com `attempt_number`, task de cadência, métrica JSONL, mover deal e, em
  F4 sem resposta, "Perdido" + nutrição). Envio legado em `~1698-1705`; shadow em `~1739`.
- Preservar o **manifesto aprovado com hash SHA256** (`~773-797`): o texto final validado deve ser o
  que entra na fila; o worker não revalida, então o produtor precisa garantir o texto correto no
  enqueue (fail-closed continua no produtor).
- Delays por tentativa são maiores (até 240–360s). Confirmar que segurar o worker por esse tempo em
  `_send_parts_sequence` (que usa `time.sleep`) é aceitável dentro do limite de 10 conversas
  simultâneas — senão, modelar como partes agendadas (`scheduled_at`) em vez de sleep no worker.
- Flag `ZYDON_CADENCIA_WORKER_OWNED` + teste de cutover.

**Fase 3 — Diagnóstico/PDF (mídia).**
- Maior complexidade (mídia real, não só texto). O worker hoje só faz `/send` texto
  (`_default_transport:68-69`). Precisa de transporte de mídia + completion `diagnostico` antes de
  migrar. Manter por último; até lá continua legado/shadow.

**Regras de segurança da migração (todas as fases).**
- Uma flag por fluxo; nunca migrar dois de uma vez.
- Cada fase entra só depois do `release_gate` + `safe_deploy stage` verdes; **promoção para produção
  é decisão do Dexter/Hermes, não do Claude Code** (CLAUDE.md §5).
- Completion sempre grava ledger/task **após** envio confirmado (padrão já usado em
  `whatsapp_worker_completions.py`), para não reintroduzir reenvio nem card fantasma.
- Manter dedupe da fila (`dedupe_key`/`logical_message_id`, janela 6h) como trava contra duplicidade
  durante a coexistência shadow+legado.

---

## Requisitos omnichannel (painel SDRs Zydon: auditoria + dia a dia do vendedor)

Focado em auditoria confiável e uso diário, respeitando as regras invioláveis (só realidade, sem
texto técnico, sem grupo, sem chat íntimo).

**Privacidade como invariante de plataforma (base de tudo).**
- Uma única fronteira de "conversa admissível": operacional (iniciada por automação Zydon ou envio
  manual pelo painel) **e** não-grupo **e** não-interna. Toda origem de canal (WhatsApp hoje;
  e-mail/telefone/outros amanhã) atravessa a mesma fronteira antes de virar card/bolha.
- Detalhe de conversa continua "só bolha real do device; ledger/fila só enriquece" — este contrato já
  está bem coberto e deve ser o modelo replicado para novos canais.

**Auditoria (visão de gestão).**
- Linha do tempo unificada por lead/deal cruzando canais, sempre a partir de eventos reais + ledger
  interno, sem expor termos técnicos (respeitar `FORBIDDEN_VISIBLE_TECH_TERMS`).
- Rastreabilidade de disparo → resposta confiável: corrigir R3 para que atribuição de resposta nunca
  conte grupo. Métrica de retorno por SDR/porta/origem precisa ser à prova de grupo/interno.
- Painel de saúde do centralizador (fila): volume por `origin`/`owner`/`port`, throughput, itens
  `blocked` e **motivo** do bloqueio (grupo/interno/incompleto) — reaproveitar `queue_metrics`/
  `dispatch_queue_snapshot`, mantendo o resumo sem prompt completo (o gate já garante isso para
  crons; aplicar o mesmo cuidado à fila).

**Dia a dia do vendedor.**
- Inbox fiel a WhatsApp (bolha, horário, anexo, resposta reais) — já é a direção; manter latência
  `/api/messages` < 1.5s e nunca trocar erro por "Sem mensagens" (CLAUDE.md §6).
- Estado de envio transparente sem jargão: quando o sistema confirmou envio mas a bolha do device
  ainda não chegou, mostrar como mensagem enviada normal (regra §7), inclusive para itens em fila
  worker_owned ainda não entregues.
- Ações do vendedor pelo painel (envio manual) devem entrar na **mesma fila central** (origin
  `manual_operacional` já existe na lista de origins), para unificar dedupe, limite por chip e
  auditoria — em vez de um caminho de envio paralelo.

**Extensão a novos canais (quando houver).**
- Cada canal novo precisa: adaptador de "history real" próprio, mapeamento para a fila central com
  `origin` dedicado, guarda de privacidade equivalente e teste de "não inventar mensagem". Não abrir
  canal novo sem esses quatro itens.

---

## Próximos passos (arquivos/funções a mudar primeiro)

Ordem recomendada, do que fecha risco imediato para o que habilita evolução:

1. **Fonte única da blocklist interna.** Extrair `INTERNAL_WPP_DIGITS`
   (`scripts/channel_panel_v2.py:~3648-3655`) para um módulo compartilhado (ex.
   `scripts/whatsapp_jid_utils.py`) e expor `is_internal_communicator(jid)` ao lado de
   `is_group_or_broadcast`. — fecha divergência de R1.
2. **Guarda única de destino no caminho de disparo.** Em `scripts/whatsapp_dispatch_flow.py`
   (`record_dispatch_shadow` e `record_dispatch_worker_owned:68-75`) e em
   `scripts/whatsapp_dispatch_worker.py` (`_validate_live_row:123-132`), substituir os
   `endswith('@g.us')` + set de 2 números por `is_group_or_broadcast()` + `is_internal_communicator()`.
   Fazer `record_dispatch_worker_owned` passar pela mesma checagem de destino que `_from_row`. —
   fecha R1/R2/R4.
3. **Invariante na fila.** Em `scripts/whatsapp_dispatch_queue.py` (`enqueue_dispatch`/
   `build_dispatch_row`), rejeitar destino grupo/broadcast/interno como faz com `origin` inválido —
   defesa em profundidade. — fecha R4.
4. **Corrigir atribuição de resposta.** Em `scripts/channel_panel_v2.py`
   `_dispatch_response_attribution` (~2543-2548), `continue` quando `is_group_or_broadcast(chat)`. —
   fecha R3.
5. **Testes de Prioridade 1 e 2** (seção Testes recomendados) junto de cada mudança acima; rodar
   `python3 -m unittest tests.test_whatsapp_dispatch_queue tests.test_channel_v2_core -v` local.
6. **Completion hooks** em `scripts/whatsapp_worker_completions.py`: adicionar `proatividade`/
   `first_contact` (Fase 1) e `followup` (Fase 2), no mesmo padrão de `_complete_agenda_queue`/
   `_complete_non_mql`. Só então habilitar as flags `ZYDON_DISPARO_DINAMICO_WORKER_OWNED` e
   `ZYDON_CADENCIA_WORKER_OWNED`.
7. **Cutover tests** espelhando `tests/test_non_mql_worker_owned_cutover.py` e
   `tests/test_agenda_queue_worker_owned_cutover.py` para cada fluxo migrado (legacy send proibido +
   enqueue worker_owned + completion pós-envio).
8. **Validação obrigatória antes de concluir qualquer etapa** (CLAUDE.md): `scripts/channel_v2_release_gate.sh`
   e `scripts/channel_v2_safe_deploy.sh stage`. Promoção pública fica com Dexter/Hermes.

### Observações finais
- Nada aqui exige reiniciar bridge, enviar WhatsApp ou promover deploy; todas as mudanças de fluxo
  ficam atrás de flag e passam por stage antes de qualquer promoção.
- O maior ganho de segurança com menor esforço é **consolidar a guarda de privacidade em um único
  helper e alinhar as três cópias (painel, flow, worker)** — hoje elas divergem, e é essa divergência
  (não a ausência de defesa) que representa o risco real de grupo/chat interno escapar quando o
  volume novo migrar para o worker.
