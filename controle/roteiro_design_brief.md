# Brief de redesign — Roteiro Comercial Zydon

Escopo rígido: mexer somente no projeto Roteiro (`scripts/roteiro_panel.py` e testes próprios `tests/test_roteiro_panel.py`). Não alterar Channel, WhatsApp, SDRs/Foco/Gestão ou `channel_panel_v2.py`.

## Problema atual
A UI parece amadora/poluída: cards demais, informação repetida, linha do tempo em grade confusa, perguntas soltas, chips de owner com IDs numéricos e pouca sensação de linha de produção. O vendedor não entende rapidamente o que precisa fazer antes/durante/depois da apresentação.

## Produto desejado
O Roteiro é uma linha de produção comercial para apresentações B2B. A Zydon é especialista em e-commerce B2B. O vendedor chega na apresentação e precisa seguir uma jornada guiada, mas adaptável ao segmento, necessidade e dores do cliente.

## Usuários e permissões
- Rafael, Lucas Resende e líder de Growth veem todos os negócios.
- Demais executivos comerciais veem apenas sua própria carteira HubSpot.

## Jornada principal
1. Primeira tela: fila de negócios em `Apresentação Comercial 🎯` por proprietário.
2. Vendedor seleciona uma empresa.
3. Clica em `Iniciar apresentação`.
4. O app monta um cockpit da reunião:
   - quem é a empresa/deal
   - o que confirmar antes de demonstrar
   - pesquisa/investigação da empresa (mesmo que inicialmente pendente do Claude)
   - trilha de apresentação a seguir
5. O vendedor conduz a apresentação pela linha do tempo, uma etapa por vez.
6. O roteiro oficial vem do PDF: Big Four ERP, white label, vitrine, login/acesso, home inteligente, checkout, pedidos, financeiro, app, WhatsApp e Admin.

## Requisitos UX
- Reduzir poluição visual.
- Trocar grade de tampinhas por uma jornada clara: fases/etapas com estado ativo e checklist.
- Mostrar no topo da área central um resumo da empresa e um CTA principal.
- Fila à esquerda deve ser elegante e escaneável, com filtro de proprietário usando nomes quando disponíveis; se owner desconhecido, mostrar `Owner 76764091`, não apenas número solto.
- Painel de preparação deve separar: `Pesquisa`, `Hipóteses`, `Perguntas de descoberta`.
- Durante a apresentação, foco deve ser uma etapa ativa grande, com etapas seguintes em trilho lateral ou horizontal.
- Editor do roteiro deve existir, mas não dominar a tela. Deve ficar em seção recolhível/aba secundária, pois a tela principal é de execução.
- Visual: premium B2B, limpo, institucional, paleta Zydon (preto/verde lima) com bastante branco, sem gradiente exagerado, sem glassmorphism, sem emoji visual excessivo.
- Mobile precisa continuar usável.

## Requisitos técnicos
- Manter app standalone na porta 8290.
- Não adicionar dependências externas.
- Manter endpoints existentes:
  - `/api/roteiro`
  - `/api/presentation-deals`
  - `/api/start-presentation`
  - `/health`
- Atualizar/expandir testes próprios do Roteiro.
- Rodar `scripts/roteiro_release_gate.sh`.
