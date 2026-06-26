# Briefing para Claude Code — Redesign Zydon Channel V2

## Contexto

O usuário Rafael considera o design atual do Zydon Channel fraco: “parece trabalho de faculdade”. O objetivo é gerar uma experiência premium para o time comercial usar todo dia.

Produto: inbox comercial WhatsApp multi-chip/multi-SDR para Zydon.

Arquivos relevantes:
- `scripts/channel_panel.py` — painel atual em Python stdlib + HTML/CSS/JS inline.
- `scripts/import_channel_history.py` — importa histórico dos dois crons.
- `docs/channel-evolution-plan.md` — plano de evolução do produto.

## Pedido

Criar um mockup HTML/CSS/JS premium, self-contained, para `design/channel-v2-mockup.html`.

Não precisa alterar produção agora. O objetivo é design exploratório de alta qualidade para aprovação.

## Referências de produto

Concorrentes/padrões estudados:
- Respond.io: omnichannel inbox, routing, automation, HubSpot integration, analytics.
- Intercom/Crisp: conversa + contexto + IA + handoff claro.
- Front/Superhuman: inbox rápida, premium, keyboard-first.
- Linear: dark UI precisa, limpa, com hierarquia forte.
- Kommo/HubSpot Conversations: conversa conectada a pipeline comercial.

## Direção visual

Mistura desejada:
- Linear/Superhuman: dark, premium, preciso, bordas sutis, tipografia forte.
- Intercom: conversa e contexto comercial amigável.
- Zydon: preto profundo + verde #CDEB00 como accent, não como carnaval.

Design tokens sugeridos:
- Background principal: #06080A / #08090A
- Painel: #0E1114
- Surface: rgba(255,255,255,0.035)
- Border: rgba(255,255,255,0.08)
- Texto principal: #F4F7F5
- Texto secundário: #A7B0AA
- Texto muted: #68736D
- Accent Zydon: #CDEB00
- Success: #20C997
- Warning: #F7B955
- Danger: #FF6B6B
- Font: Inter

## Layout esperado

Desktop-first, 4 zonas:

1. Sidebar compacta
   - Logo Zydon Channel.
   - Filas: Responder agora, Meus leads, Sem resposta, Diagnóstico enviado, 1º contato SDR, Resolvidas, Erros/Offline.
   - Contadores.
   - Status dos chips.

2. Lista de conversas
   - Busca grande.
   - Filtros chips/SDR/status.
   - Cards de conversa com:
     - Empresa
     - Contato
     - Badge MQL/1º contato/Diagnóstico/Resposta
     - Última mensagem com data/hora relativa
     - Owner/SDR
     - SLA ou tempo sem resposta
     - Indicador se há resposta do lead.
   - Deve parecer uma inbox moderna, não tabela.

3. Área de conversa
   - Header com empresa, contato, telefone, owner, status.
   - Timeline com separadores por dia.
   - Eventos automáticos com cards: “Diagnóstico enviado”, “PDF enviado”, “1º contato SDR”.
   - Bolhas de mensagem limpas.
   - PDF card bonito.
   - Resposta do lead visualmente destacada.
   - Composer premium: quick replies, anexar arquivo, enviar, nota interna.

4. Painel de contexto comercial
   - Score/etiquetas.
   - HubSpot: owner, deal stage, lifecycle, última atividade.
   - Próxima ação sugerida.
   - Notas internas.
   - Histórico de automações.
   - Saúde do chip.

## Conteúdo mockado

Use exemplos reais/representativos:
- LightShip Embalagens — diagnóstico enviado.
- IA Crono — primeiro contato Breno.
- HIPER STOK — primeiro contato Lucas.
- Grupo Maranno — diagnóstico Sarah 2.
- Lead com resposta: “Tenho interesse, consigo ver amanhã?”

## Requisitos de UX

- O SDR deve saber em 5 segundos o que responder.
- Não mostrar JID bruto na interface principal.
- Porta/chip aparecem como metadado discreto.
- Conversas com resposta de lead no topo.
- Botões claros: Responder, Agendar, Criar tarefa, Resolver.
- Visual precisa parecer SaaS premium B2B, não dashboard amador.
- Responsivo: em mobile, lista -> conversa -> contexto via drawer.

## Entregáveis

1. Criar `design/channel-v2-mockup.html` self-contained.
2. Criar `design/channel-v2-notes.md` explicando decisões de design e próximos passos para implementar em `scripts/channel_panel.py`.
3. Não alterar arquivos de produção.
4. Se possível, incluir dados mockados no JS para simular filtro/seleção.

## Restrições

- Sem dependências build/npm.
- HTML/CSS/JS puro.
- Não usar imagens externas obrigatórias.
- Pode usar Google Fonts Inter.
- Não tocar nos processos/bridges.
