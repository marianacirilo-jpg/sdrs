# Zydon Channel — Backlog de Geração de Demanda

Data: 2026-06-24
PO/direção: Rafael. Implementação: Claude Code. Tester/PO operacional: Hermes.

> Objetivo: transformar o Channel na **central de gestão da geração de demanda completa** — inbound entra → qualifica MQL → dispara diagnóstico → segue follow-up/cadência → Introdução/agendamento/no-show/perda/nutrição — preservando HubSpot como fonte de integridade e privacidade das conversas.

## Contexto e gargalo atual

- **Gargalo nº1 — Primeiro Contato:** ~300 deals acumulados, muitos 72h+ ficando de canto, porque o time prioriza naturalmente leads novos, respostas recentes e etapas avançadas.
- O dry-run de cadência (`docs/cadencia-primeiro-contato.md`, `docs/cadencia-primeiro-contato-automatica.md`) já existe: 19 aptos para 2º contato, 14 aguardando janela 24h, 3 responderam, **264 sem primeiro contato registrado no ledger** (lacuna a sanear antes de qualquer disparo em massa).
- Capacidade nova possível: **+3-4 chips mensageiros aquecidos**, com Rafael/Mariana/Lucas Resende podendo atuar como mensageiros — **somente auditoria/envio operacional, nunca conversa pessoal/institucional privada**.
- Restrição de segurança de envio: **não disparar 300 de uma vez**, **nem 50/dia por chip**; precisa estratégia, limites por chip/hora/dia, e prints/alertas quando houver levantada de mão.
- Orquestração centralizada: gestores (Rafael/Mariana/Lucas Resende) configuram diagnóstico automático, primeiro follow-up automático e cadências numa tela de login; SDRs executam/acompanham.

## Princípios (herdados e específicos)

1. **Dry-run + prévia antes de qualquer envio real.** Nada de blast. Default sempre simulação.
2. **Não mexer nos crons vivos sem aprovação explícita.** O qualificador/envio de diagnóstico e o primeiro follow-up automático em horário de trabalho do SDR já estão funcionando; qualquer tela futura de parametrização deve ser camada de configuração/visualização, não alteração direta desses crons.
3. **HubSpot é a fonte de integridade.** Sem CRM paralelo; toda tentativa vira task/atividade auditável no HubSpot.
4. **Privacidade de conversa é inviolável.** Mensageiro (gestor) só faz envio operacional/auditoria; nunca lê/age em conversa institucional privada.
5. **Limites conservadores e governados.** Por chip, por hora, por dia, por SDR — abortar na primeira falha de bridge.
6. **Respeito ao estado real do lead.** Não tocar quem respondeu, mudou de etapa, teve ligação/reunião/task humana após o último envio.
7. **Levantada de mão é prioridade máxima.** Resposta de lead em cadência gera alerta imediato e sai da automação.

## Prioridade dos épicos

| Prioridade | Épico | Por quê agora |
|---|---|---|
| P0 | E1 — Saneamento do backlog de Primeiro Contato | Sem isso, cadência dispara em cima de 264 deals sem D0 confiável |
| P0 | E2 — Cadência 2º/3º/4º contato + despedida/nutrição | É o gargalo direto; já tem script em dry-run |
| P1 | E3 — Capacidade de chips e mensageiros com privacidade | Limita o throughput seguro de toda a operação |
| P1 | E4 — Console de orquestração para gestores | Tira a lógica de negócio do script e dá controle a Rafael/Mariana/Lucas |
| P2 | E5 — Alertas de levantada de mão e SLA | Garante que volume não enterra o lead quente |
| P2 | E6 — Funil end-to-end de geração de demanda | Liga as pontas: inbound → MQL → diagnóstico → cadência → agenda/perda/nutrição |
| P3 | E7 — Métricas e observabilidade do funil | Mede o que cada etapa converte e onde limar entrada ruim |

---

## E1 — Saneamento do backlog de Primeiro Contato (P0)

**Problema:** 264 dos ~300 deals em Primeiro Contato não têm primeiro contato registrado no ledger (`controle/wpp_envios.json`). Pode ser deal de automação antiga sem ledger, ou deal realmente sem abordagem SDR. Disparar cadência neles é arriscado (pode ser 1º contato disfarçado de 2º, ou cobrança indevida).

**Histórias / tarefas:**
- E1.1 Classificar os ~300 deals em buckets: `tem_D0_ledger`, `D0_inferível_por_bridge` (existe mensagem de saída no histórico mas não no ledger), `sem_qualquer_abordagem`, `já_respondeu`, `mudou_de_etapa`.
- E1.2 Reconciliar histórico da bridge × ledger para recuperar D0 inferível e gravar marcação de origem.
- E1.3 Para `sem_qualquer_abordagem`: tratar como **primeiro contato real** (não 2º contato), entrando na fila de D0, não na cadência.
- E1.4 Relatório de saneamento revisável no Channel (fila/contagem por bucket) antes de liberar cadência.

**Critérios de aceite:**
- Todo deal em Primeiro Contato tem bucket atribuído e origem do D0 registrada.
- Nenhum deal entra na cadência de 2º+ contato sem D0 confiável (ledger ou inferido e marcado).
- Relatório mostra contagem por bucket e é validável por Hermes/Rafael antes do go-live.

**Riscos:**
- Inferir D0 errado → cobrar lead como 2º contato sendo 1º. Mitigar com marcação explícita e revisão humana do bucket inferido.
- Deal antigo/morto poluindo a base → permitir descartar/arquivar no saneamento.

---

## E2 — Cadência 2º/3º/4º contato + despedida/nutrição (P0)

**Base existente:** `scripts/cadencia_primeiro_contato.py` (dry-run/send/mark-nurture), `docs/cadencia-primeiro-contato.md`. Falta operacionalizar com segurança, mensagens aprovadas e despedida.

**Histórias / tarefas:**
- E2.1 Banco de mensagens aprovadas para 2º/3º/4º contato, **variadas por dia e por lead** (sem blast idêntico), por SDR/tom Zydon.
- E2.2 Mensagem de **despedida/break-up** (5ª interação): encerra cobrança SDR e transfere para nutrição/material rico/marketing.
- E2.3 Janela e ritmo: D+1 / D+2 / D+3-4, mínimo ~20h entre tentativas, máximo 4 tentativas contando D0.
- E2.4 Limites de envio: máx. conservador por hora, **máximo diário por chip bem abaixo de 50** (alvo inicial ~30/chip/dia, ver E3), aborta na 1ª falha de bridge.
- E2.5 Regras duras de exclusão (já especificadas): não tocar quem respondeu, mudou de etapa, teve ligação/reunião/task humana ou conversa institucional privada após o último envio.
- E2.6 Auditoria de cada envio real: `msg_type=primeiro_contato_cadencia`, `attempt_number`, `campaign_id`, `deal_id`, `contact_id`, `sender_name`, `bridge_port`, `send_response`; task COMPLETED no HubSpot (contato typeId 204 / deal typeId 216); linha em `controle/cadencia_primeiro_contato_metrics.jsonl`.
- E2.7 Prévia no Channel (Foco SDR/Playbooks) antes de ativar cron; cron só em horário comercial, lote pequeno.

**Critérios de aceite:**
- Primeiro lançamento roda **dry-run** e gera prévia revisável; nenhum envio automático sem aprovação explícita (`--send`).
- Nenhum lead recebe mensagem idêntica em dias diferentes.
- Após 4 tentativas sem resposta, lead sai da fila SDR e recebe marcação de nutrição (sem novo WhatsApp).
- Toda tentativa real é auditável no HubSpot e no ledger.
- Limite por chip/hora/dia respeitado; processo aborta na primeira falha de bridge.

**Riscos:**
- Encavalamento com lotes manuais grandes do SDR no mesmo chip → não rodar cadência simultânea a disparo manual; janela coordenada.
- Bloqueio de chip por volume → limites conservadores + score de saúde do chip (E3).
- Mensagem fora de contexto para lead que avançou → reforçar checagem de estado em tempo de envio, não só no dry-run.

---

## E3 — Capacidade de chips e mensageiros com privacidade (P1)

**Objetivo:** aumentar throughput seguro conectando +3-4 chips aquecidos e habilitando Rafael/Mariana/Lucas Resende como **mensageiros operacionais**, sem nunca expor conversa pessoal.

**Histórias / tarefas:**
- E3.1 Onboarding de 3-4 chips novos aquecidos: QR/reconectar pelo painel, vínculo a owner/SDR, rampa de aquecimento (volume crescente).
- E3.2 Papel de **mensageiro**: gestor pode emprestar capacidade de envio operacional (diagnóstico/cadência) sem acesso à conversa institucional privada do lead.
- E3.3 Roteamento por saúde do chip (já existe `sendPort/sendRoutingReason`, `healthScore`, `loadPct`): distribuir cadência pelos chips saudáveis do owner permitido.
- E3.4 Política de limite por chip parametrizável (alvo ~30/dia, teto duro < 50/dia) e recomendação `adicionar_chip` quando estourar.
- E3.5 Distribuição do backlog ao longo de dias (não 300 de uma vez): planejador que estima dias necessários dado nº de chips × limite/dia.

**Critérios de aceite:**
- Novos chips aparecem no painel com saúde/limite/risco e podem ser conectados sem Discord/telefone físico.
- Mensageiro consegue executar/auditar envio operacional mas recebe 403 ao tentar abrir conversa privada não permitida.
- Cadência distribui carga só por chips saudáveis e dentro do limite; estoura → recomenda adicionar chip.
- Planejador mostra quantos dias o backlog leva no ritmo seguro atual.

**Riscos:**
- Mensageiro ver conversa que não deveria → reforçar regra de privacidade (herda CH-057/CH-058: envio operacional ≠ leitura institucional).
- Chip novo sem aquecimento suficiente → rampa obrigatória antes de entrar na cadência.

---

## E4 — Console de orquestração para gestores (P1)

**Objetivo:** centralizar a lógica de negócio/agendamento numa tela de login onde Rafael/Mariana/Lucas Resende configuram **diagnóstico automático, primeiro follow-up automático e cadências**, sem editar script/JSON. SDRs executam e acompanham; gestores orquestram.

**Histórias / tarefas:**
- E4.1 Tela de configuração (perfil `view_all`/admin) para: ativar/pausar diagnóstico automático, primeiro follow-up automático e cadência 2º/3º/4º.
- E4.2 Parametrizar janelas, limites por chip/hora/dia, mensagens aprovadas e regras de exclusão pela UI (sem mexer em código).
- E4.3 Criar **Playbooks guiados / prompts estruturados** dentro da conversa: em vez de muitos botões soltos ou campo aberto tipo IA, o SDR escolhe um fluxo pré-determinado (ex.: Agendamento/Introdução, No-show, Retomada, Perda/Nutrição), preenche campos obrigatórios e revisa a prévia antes de executar alterações no HubSpot.
- E4.4 Botão global de **kill switch / pausa** de toda automação de envio.
- E4.5 Separação de papéis: gestor configura/orquestra; SDR vê o que está agendado para seus leads e acompanha execução, mas não altera política global.
- E4.6 Prévia obrigatória (dry-run) embutida na tela antes de ligar qualquer cron.
- E4.7 Auditoria de quem ligou/desligou/alterou cada automação.

**Critérios de aceite:**
- Gestor configura e ativa diagnóstico/follow-up/cadência sem tocar em script ou JSON.
- Toda ativação passa por prévia dry-run visível.
- Kill switch pausa todos os envios automáticos imediatamente.
- SDR não-admin recebe 403 em endpoints de política global; vê apenas acompanhamento.
- Mudanças de configuração ficam auditadas (quem/quando/o quê).

**Riscos:**
- UI dar poder de disparo em massa sem trava → manter prévia + limites obrigatórios no backend, não só na tela.
- Configuração divergente do script → fonte única de verdade da política (backend lê da config, não hardcoded).
- Escopo: não mexer em credenciais nem em bridge/cron/watchdog a partir da tela.

---

## E5 — Alertas de levantada de mão e SLA (P2)

**Objetivo:** quando um lead responde (na cadência ou em qualquer fila), o SDR/gestor recebe **print/alerta imediato** e o lead sai da automação.

**Histórias / tarefas:**
- E5.1 Detecção de resposta de lead em cadência → remove da automação e marca `respondeu`.
- E5.2 Alerta/print da levantada de mão para o SDR dono e para o gestor (canal a definir; respeitando privacidade).
- E5.3 Fila de prioridade "Levantou a mão" no topo do Channel.
- E5.4 SLA visível: tempo desde a levantada de mão sem atendimento.

**Critérios de aceite:**
- Resposta de lead em cadência interrompe novas tentativas no mesmo deal automaticamente.
- Alerta chega ao dono com contexto mínimo (empresa, etapa, última mensagem) sem expor conversa privada a quem não tem permissão.
- Fila "Levantou a mão" reflete em tempo quase real.

**Riscos:**
- Vazar conteúdo privado no alerta → alerta carrega metadado/sinal, não a conversa institucional completa para terceiros.
- Falso positivo (auto-reply/ausência) → heurística de intenção antes de marcar levantada de mão.

---

## E6 — Funil end-to-end de geração de demanda (P2)

**Objetivo:** ligar as etapas numa só visão operável: **inbound entra → qualifica MQL → dispara diagnóstico → follow-up/cadência → Introdução/agendamento/no-show/perda/nutrição**.

**Histórias / tarefas:**
- E6.1 Mapear cada estágio para fila/estado no Channel e ao deal stage no HubSpot.
- E6.2 Inbound → MQL: critério de qualificação e gatilho de diagnóstico automático.
- E6.3 Diagnóstico → primeiro follow-up automático → cadência (handoff entre automações sem duplicar mensagem).
- E6.4 Introdução/agendamento: detectar reunião marcada (já existe em CH-032) e mover de fila.
- E6.5 No-show → retomada/cadência específica; Perda → encerrar; Nutrição → marketing/material rico.
- E6.6 Evitar que um lead esteja em duas automações conflitantes ao mesmo tempo (lock por deal).

**Critérios de aceite:**
- Cada lead tem um estágio único e coerente entre Channel e HubSpot.
- Transições (MQL→diagnóstico→follow-up→cadência→agenda/no-show/perda/nutrição) acontecem sem mensagem duplicada.
- Nenhum lead em duas automações de envio simultâneas.

**Riscos:**
- Dessincronização Channel × HubSpot → HubSpot como fonte de verdade do estágio.
- Complexidade de máquina de estados → começar pelos estágios já existentes e expandir incrementalmente.

---

## E7 — Métricas e observabilidade do funil (P3)

**Objetivo:** medir o que cada etapa converte, identificar perfis e **critérios para limar entrada ruim do funil**.

**Histórias / tarefas:**
- E7.1 Conversão por tentativa: quem responde ao 1º/2º/3º/4º contato.
- E7.2 Conversão por etapa: quem vira Diagnóstico/Introdução, quem agenda, quem dá no-show, quem vai para perda.
- E7.3 Saúde de chip ao longo do tempo: volume/dia, taxa de resposta, erros, risco.
- E7.4 Perfil/ICP que converte vs. entrada ruim → recomendação de filtrar fonte.
- E7.5 Dashboard para Rafael: backlog restante, dias para zerar no ritmo atual, carga por SDR/chip.

**Critérios de aceite:**
- Dashboard mostra conversão por tentativa e por etapa com dados reais.
- Rafael vê backlog restante e estimativa de dias para zerar.
- Métricas alimentam decisão de limites de chip e de corte de entrada ruim.

**Riscos:**
- Métrica sem volume estatístico → sinalizar amostra pequena, não decidir cedo demais.

---

## Dependências e sequência sugerida

1. **E1 (saneamento)** destrava **E2 (cadência real)** — não ativar envio em massa antes de E1.
2. **E3 (capacidade/chips)** define o teto de throughput de E2 e E6.
3. **E4 (console)** tira a política do script; idealmente entra junto/logo após E2 estabilizar em dry-run.
4. **E5/E6/E7** evoluem sobre a base operando.

## Fora de escopo / não fazer

- Não alterar credenciais nem bridge/cron/watchdog a partir das telas.
- Não criar CRM paralelo: HubSpot é a integridade.
- Não disparar 300 de uma vez, nem ultrapassar limite por chip/dia.
- Mensageiro/gestor nunca lê conversa institucional privada — só envio/auditoria operacional.

## Referências

- `docs/cadencia-primeiro-contato.md` — implementação atual da cadência.
- `docs/cadencia-primeiro-contato-automatica.md` — decisão de produto e dry-run inicial.
- `docs/channel-kanban.md` — kanban de lançamento (card CH-065).
- `docs/channel-evolution-plan.md` — visão de produto/UX por fases.
</content>
</invoke>
