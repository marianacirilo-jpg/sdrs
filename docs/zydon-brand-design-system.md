# Zydon — design system obrigatório

Fonte: `Manual_Zydon.pdf` enviado por Rafael em 2026-06-30.

## Regra principal

Todo design system, tela, PDF, mockup, gráfico, dashboard, login, card, botão e artefato visual da Zydon deve partir da paleta oficial abaixo. Não criar paletas paralelas, tons “bonitinhos”, gradientes coloridos ou variações fora da marca sem aprovação explícita de Rafael.

## Paleta oficial

| Papel | Nome oficial | HEX | RGB | Observação |
|---|---|---:|---:|---|
| Accent / marca | Lime Green | `#CDEB00` | 205, 235, 0 | Usar com parcimônia: logo, ação primária, prioridade real, destaque essencial. |
| Base / negativo | Neutral Black | `#000000` | 0, 0, 0 | Base institucional; no produto pode ser adaptado para preto profundo próximo, mas sempre dentro da família. |
| Neutro técnico | Tech Gray | `#C3C3C6` | 195, 195, 198 | Texto secundário, bordas, separadores, estados neutros. |
| Neutro claro | Light Gray | `#E6E6E6` | 230, 230, 230 | Fundos claros, divisórias suaves, superfícies neutras. |

## Aplicação em produto digital

- Tema dark/premium pode usar preto profundo derivado do Neutral Black (`#000000`, `#06080A`, `#08090A`, `#0B0F0C`) desde que a família visual continue preta/neutra.
- O verde `#CDEB00` não é decoração. Ele marca ação/atenção/identidade; não usar como carnaval visual.
- Cinzas devem vir da família `#C3C3C6` / `#E6E6E6`, com transparências controladas no dark mode.
- Cores semânticas auxiliares (erro/sucesso/alerta) só entram quando forem necessárias para compreensão operacional e não podem competir com a marca.
- Não usar blocos brancos/cinzas lavados dentro de telas dark; manter contraste e maturidade.

## O que NÃO fazer

- Não inventar paleta nova por inspiração externa.
- Não usar azul/roxo/laranja como linguagem principal da Zydon.
- Não usar gradiente multicolorido ou visual “SaaS genérico”.
- Não usar o manual antigo como fonte de operação atual, funil, cron, HubSpot, WhatsApp ou regras comerciais. O manual enviado é fonte de marca/paleta; informações operacionais antigas/passadas são descartáveis.

## Regra para Claude Code

Ao modificar UI/design no projeto:
1. Ler este arquivo e `CLAUDE.md` antes de editar.
2. Validar que novos tokens visuais respeitam a paleta oficial.
3. Se precisar de cor fora da paleta, justificar no diff/teste e usar apenas como estado semântico discreto.
4. Não promover produção; apenas stage/candidate conforme fluxo seguro.
