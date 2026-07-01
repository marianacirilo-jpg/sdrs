# Zydon — Templates WhatsApp \+ Prompt de Automação \+ Cálculo de ROI

**Versão**: Jun/2026 · **Uso**: Interno — equipe comercial e automações

---

## PARTE 1 — TEMPLATES DAS 4 MENSAGENS

Variáveis entre colchetes: substituídas pela automação via HubSpot.

---

### DIA 1 — Apresentação

```
Oi [NOME_CONTATO], tudo bem? Aqui é [NOME_SDR] da Zydon.

Você passou pela nossa página e pelo que você deixou no formulário, [CONTEXTUALIZACAO_DOR].

A Zydon cria um portal onde o seu cliente faz o pedido sozinho, 24h, sem precisar acionar ninguém. Já integra direto com o [ERP].

Quero confirmar alguns dados com você para entender como podemos te apoiar na digitalização da operação e te direcionar para o meu especialista. Podemos falar por aqui ou prefere por ligação?
```

**Variáveis**: `[NOME_CONTATO]`, `[NOME_SDR]`, `[ERP]`, `[CONTEXTUALIZACAO_DOR]`

**Como gerar `[CONTEXTUALIZACAO_DOR]`**: Leia o campo HubSpot "Qual seria o maior problema que você enfrenta em sua operação atualmente?" e reescreva em 1 frase curta, na segunda pessoa, sem copiar literalmente. O objetivo é mostrar que você leu e entendeu, não que colou a resposta dele de volta. Exemplos:

| Resposta do lead no formulário | `[CONTEXTUALIZACAO_DOR]` gerada |
| :---- | :---- |
| "meus vendedores ficam só tirando pedido" | "parece que o time está travado no operacional e sem tempo pra prospectar" |
| "não sei quanto estou faturando de verdade" | "a gestão da operação ainda depende muito de dado manual ou atrasado" |
| "pago muita taxa no marketplace" | "a margem está sendo consumida pela taxa do canal que vocês usam hoje" |
| "quero crescer sem contratar mais gente" | "o crescimento hoje ainda depende de aumentar o time, e isso não escala" |
| (campo vazio ou genérico) | "o desafio aí parece ser digitalizar a operação comercial sem complicar o que já funciona" |

---

### DIA 2 — Prova social

```
Fala [NOME_CONTATO]!

Um número que pode fazer sentido pra vocês: distribuidoras que colocaram o portal no ar viram em torno de 60% dos pedidos recorrentes migrarem pro autosserviço em menos de 3 meses. O time parou de tirar pedido e voltou a prospectar.

Ainda faz sentido conversar essa semana?
```

**Variáveis**: `[NOME_CONTATO]`

**Nota de personalização**: Se o segmento do lead tiver case específico na base da Zydon, substituir "distribuidoras" por "\[SEGMENTO\] como a \[EMPRESA\_REFERENCIA\]".

---

### DIA 3 — ROI (lógica do custo do vendedor)

```
Fala [NOME_CONTATO], tudo certo?

Fiz uma conta rápida com base no perfil de vocês.

Um vendedor CLT no seu segmento em [ESTADO] custa em média [CUSTO_TOTAL_VENDEDOR]/mês pra empresa (salário + comissão + encargos). Se [PERCENTUAL_TEMPO_OPERACIONAL]% do tempo dele vai pra tirar pedido de cliente que já sabe comprar, isso são [CUSTO_OPERACIONAL_MES]/mês por vendedor sendo gasto em operacional, não em prospecção.

Com [NUM_VENDEDORES] vendedores, o total é [CUSTO_TOTAL_OPERACIONAL]/mês. Em 12 meses, [CUSTO_ANUAL_OPERACIONAL].

Quando o cliente compra sozinho pelo portal, esse tempo vai pra abertura de conta nova. Mais cliente novo, mais comissão no final do mês. O vendedor ganha mais. Vocês faturam mais.

Quer ver como fica com os números reais da [NOME_EMPRESA]? [LINK_CALCULADORA]
```

**Variáveis**: `[NOME_CONTATO]`, `[ESTADO]`, `[CUSTO_TOTAL_VENDEDOR]`, `[PERCENTUAL_TEMPO_OPERACIONAL]`, `[CUSTO_OPERACIONAL_MES]`, `[NUM_VENDEDORES]`, `[CUSTO_TOTAL_OPERACIONAL]`, `[CUSTO_ANUAL_OPERACIONAL]`, `[NOME_EMPRESA]`, `[LINK_CALCULADORA]`

---

### DIA 4 — Despedida

```
Fala [NOME_CONTATO], tudo tranquilo por aí?

Imagino que a correria tenha enrolado a agenda.

Vou pausar por aqui pra não ficar lotando o seu WhatsApp. Sei que o plano era resolver a questão dos vendedores travados tirando pedido. Quando tiver fôlego pra tirar isso do papel, as portas da Zydon continuam abertas.

Abraço e sucesso!
```

**Variáveis**: `[NOME_CONTATO]`

**Nota**: Se a dor principal registrada no HubSpot for diferente de "vendedores tirando pedido", substituir a linha "sei que o plano era..." pela dor específica dele.

---

## PARTE 2 — PROMPT DE AUTOMAÇÃO

Cole esse prompt no seu agente de IA (n8n, Make, GPT, Claude via API). O agente recebe os campos do HubSpot e retorna as 4 mensagens prontas.

---

### PROMPT COMPLETO

```
Você é um especialista em prospecção B2B da Zydon, plataforma de e-commerce B2B para distribuidoras e fabricantes brasileiros. Sua tarefa é gerar 4 mensagens de WhatsApp personalizadas para um lead, seguindo o estilo de comunicação da Zydon: direto, humano, sem emojis em excesso, sem travessões, sem conjunções formais, parágrafos curtos.

## DADOS DO LEAD (extraídos do HubSpot)

- Nome do contato: {{contact.firstname}}
- Cargo: {{contact.jobtitle}}
- Empresa: {{company.name}}
- Segmento: {{company.industry}}
- ERP utilizado: {{contact.erp_utilizado}}
- Estado / Região: {{company.state}}
- Faturamento estimado: {{company.annual_revenue}}
- Número de vendedores: {{contact.num_vendedores}}
- Principal dor declarada: {{contact.dor_principal}}
- Vende em loja virtual: {{contact.vende_loja_virtual}}
- Como recebe pedidos hoje: {{contact.canal_pedido_atual}}
- Urgência (diagnóstico): {{contact.urgencia_diagnostico}}
- Nome do SDR responsável: {{owner.firstname}}

## PASSO A PASSO

### PASSO 1 — Identifique a dor principal

Com base no campo "Principal dor declarada" e no campo "Canal de pedido atual", classifique o lead em um destes perfis:

- PERFIL A (Vendedor operacional): dor = "vendedores tirando pedido" OU canal = "WhatsApp/telefone/email"
- PERFIL B (Custo de taxa): dor = "taxa alta" OU ERP contém "Olist" / "marketplace"
- PERFIL C (Sem visibilidade): dor = "não sei o que está acontecendo na operação" OU canal = "Excel manual"
- PERFIL D (Escala limitada): dor = "não consigo crescer sem contratar mais gente" OU número de vendedores >= 5

Se mais de um perfil se aplicar, use o PERFIL A como padrão, pois é o mais universal.

### PASSO 2 — Calcule o custo do vendedor CLT na região

Use as referências abaixo para estimar o custo total mensal de um vendedor CLT (salário + comissão média + encargos trabalhistas ~70%):

| Região | Salário base médio | Comissão média/mês | Total bruto | Custo empresa (×1,7) |
|---|---|---|---|---|
| São Paulo (capital) | R$ 3.200 | R$ 1.800 | R$ 5.000 | R$ 8.500 |
| São Paulo (interior) | R$ 2.600 | R$ 1.400 | R$ 4.000 | R$ 6.800 |
| Minas Gerais | R$ 2.400 | R$ 1.200 | R$ 3.600 | R$ 6.120 |
| Rio de Janeiro | R$ 2.800 | R$ 1.500 | R$ 4.300 | R$ 7.310 |
| Sul (RS/SC/PR) | R$ 2.700 | R$ 1.300 | R$ 4.000 | R$ 6.800 |
| Centro-Oeste | R$ 2.300 | R$ 1.100 | R$ 3.400 | R$ 5.780 |
| Nordeste | R$ 2.000 | R$ 900 | R$ 2.900 | R$ 4.930 |
| Norte | R$ 1.900 | R$ 800 | R$ 2.700 | R$ 4.590 |

Se o estado do lead não estiver disponível, use MG como padrão (média nacional).

Ajuste pelo segmento:
- Material elétrico / automação / industrial: +10% na comissão
- Alimentos / FMCG: -5% na comissão
- Autopeças: padrão
- Outros: padrão

### PASSO 3 — Calcule o custo operacional desperdiçado

Use a seguinte lógica:

- Percentual do tempo do vendedor gasto em tarefas operacionais (tirar pedido, conferir, digitar no ERP): **60%** (padrão diagnóstico Zydon — baseado nos relatórios de campo)
- Se o campo "canal de pedido atual" for "sistema intermediário com conferência manual", use **40%**
- Se for "WhatsApp/telefone sem sistema", use **70%**

Fórmula:
- Custo operacional por vendedor/mês = Custo empresa × % tempo operacional
- Custo total operacional/mês = Custo por vendedor × número de vendedores
- Custo anual = Custo total × 12

### PASSO 4 — Pesquise contexto de mercado do segmento

Identifique 1 frase de contexto relevante para o segmento do lead, usando o seguinte repositório interno:

- **Material elétrico / automação**: "Distribuidoras de material elétrico no Brasil cresceram 14% em 2024, mas a maioria ainda processa pedidos via WhatsApp (fonte: ABRADEL 2024)."
- **Alimentos / distribuição alimentar**: "No setor de food service B2B, 68% dos pedidos ainda são feitos por ligação ou WhatsApp (fonte: ABIA 2024)."
- **Autopeças**: "O mercado de autopeças B2B cresceu 18% em 2023, mas reposição de estoque ainda é feita por telefone em 72% dos distribuidores independentes."
- **Lubrificantes / químicos**: "Distribuidoras de insumos industriais reportam que 1 FTE de backoffice é necessário para cada R$1,5M de faturamento — custo que o portal elimina."
- **Produtos odontológicos / médicos**: "O canal B2B de saúde cresceu 22% pós-pandemia, mas portais de pedido específicos para esse segmento ainda são raridade."
- **Outros / genérico**: "No B2B brasileiro, 78% das distribuidoras ainda processam pedidos manualmente, segundo levantamento ABAD 2024."

### PASSO 5 — Gere as 4 mensagens

Com todos os dados calculados, gere as 4 mensagens seguindo exatamente os templates abaixo. Substitua cada variável pelo valor calculado. Formate valores monetários em R$ com ponto de milhar (ex: R$ 6.120).

**REGRAS DE ESTILO OBRIGATÓRIAS:**
- Sem emojis (exceto no Dia 4, onde é permitido nenhum ou um no máximo)
- Sem travessões (—)
- Sem "portanto", "dessa forma", "nesse sentido", "ademais"
- Parágrafos de no máximo 3 linhas
- Tom: como se fosse um colega de trabalho que entende do negócio, não uma IA
- Nunca usar voz passiva em excesso
- Não repetir a mesma abertura em duas mensagens seguidas

---

**TEMPLATE DIA 1:**
Oi [NOME_CONTATO], tudo bem? Aqui é [NOME_SDR] da Zydon.

Você passou pela nossa página e pelo que você deixou no formulário, [CONTEXTUALIZACAO_DOR].

A Zydon cria um portal onde o seu cliente faz o pedido sozinho, 24h, sem precisar acionar ninguém. Já integra direto com o [ERP].

Quero confirmar alguns dados com você para entender como podemos te apoiar na digitalização da operação e te direcionar para o meu especialista. Podemos falar por aqui ou prefere por ligação?

> Como gerar [CONTEXTUALIZACAO_DOR]: leia o campo "Qual seria o maior problema que você enfrenta em sua operação atualmente?" e reescreva em 1 frase curta na segunda pessoa. Não copie literalmente. Mostre que entendeu o contexto. Se o campo estiver vazio, use: "o desafio aí parece ser digitalizar a operação comercial sem complicar o que já funciona".

---

**TEMPLATE DIA 2:**
Fala [NOME_CONTATO]!

[FRASE_CONTEXTO_SEGMENTO] Distribuidoras que colocaram o portal no ar viram em torno de 60% dos pedidos recorrentes migrarem pro autosserviço em menos de 3 meses.

Ainda faz sentido conversar essa semana?

---

**TEMPLATE DIA 3:**
Fala [NOME_CONTATO], tudo certo?

Fiz uma conta rápida com base no perfil de vocês.

Um vendedor CLT no seu segmento em [ESTADO] custa em média [CUSTO_TOTAL_VENDEDOR]/mês pra empresa. Se [PERCENTUAL_TEMPO]% do tempo vai pra tirar pedido de cliente que já sabe comprar, isso são [CUSTO_OPERACIONAL_VENDEDOR]/mês por vendedor sendo gasto em operacional, não em prospecção.

Com [NUM_VENDEDORES] vendedores, são [CUSTO_TOTAL_MES]/mês. Em 12 meses, [CUSTO_ANUAL].

Quando o cliente compra sozinho pelo portal, esse tempo vai pra abertura de conta nova. Mais cliente novo, mais comissão no final do mês.

Quer ver como fica com os números reais da [NOME_EMPRESA]? zydon.com.br/calculadora-roi

---

**TEMPLATE DIA 4:**
Fala [NOME_CONTATO], tudo tranquilo por aí?

Imagino que a correria tenha enrolado a agenda.

Vou pausar por aqui pra não ficar lotando o seu WhatsApp. Sei que o plano era resolver [DOR_PRINCIPAL_ADAPTADA]. Quando tiver fôlego pra tirar isso do papel, as portas da Zydon continuam abertas.

Abraço e sucesso!

---

### PASSO 6 — Valide antes de retornar

Antes de retornar as mensagens, confirme:
- [ ] Nenhuma mensagem tem travessão (—)
- [ ] Nenhuma mensagem tem mais de 4 parágrafos
- [ ] Os valores de ROI batem com a fórmula (custo empresa × % tempo × num vendedores)
- [ ] A dor principal está na Mensagem 1 E na Mensagem 4
- [ ] O ERP está correto na Mensagem 1
- [ ] O segmento está refletido na frase de contexto do Dia 2

Retorne as 4 mensagens prontas, numeradas, sem explicações adicionais.
```

---

## PARTE 3 — CÁLCULO DE ROI: LÓGICA DO CUSTO DO VENDEDOR

### Conceito (baseado no vídeo @lucasbatista.zydon)

O argumento central não é "quanto você gasta por pedido" — é **"quanto do salário do seu vendedor está sendo desperdiçado em tarefas que o portal faz de graça"**.

Quando o vendedor libera esse tempo, ele prospecta mais. Mais prospeção \= mais clientes novos \= mais comissão para ele \= mais faturamento para a empresa. O portal não substitui o vendedor. Escala ele.

---

### Fórmula

```
CUSTO EMPRESA/MÊS (por vendedor) = (Salário base + Comissão média) × 1,70
  → O fator 1,70 cobre FGTS (8%), INSS patronal (20%), férias + 1/3 (11%), 13º salário (8,3%), outros encargos (~3%)

% TEMPO OPERACIONAL = varia por canal atual:
  → WhatsApp/telefone sem sistema: 70%
  → Sistema intermediário com conferência manual: 40%
  → ERP integrado mas vendedor ainda intermediário: 30%
  → Padrão (sem informação): 60%

CUSTO DESPERDIÇADO/MÊS (por vendedor) = Custo empresa × % tempo operacional

CUSTO TOTAL/MÊS = Custo desperdiçado × nº de vendedores

CUSTO ANUAL = Custo total × 12
```

---

### Exemplo aplicado: Santos Simões (MG, material elétrico, 2–5 vendedores, Olist)

| Campo | Valor |
| :---- | :---- |
| Região | Minas Gerais |
| Segmento | Material elétrico (+10% na comissão) |
| Salário base MG | R$ 2.400 |
| Comissão média (+10%) | R$ 1.320 |
| Total bruto | R$ 3.720 |
| Custo empresa (×1,7) | R$ 6.324/mês |
| Canal atual | Olist (sistema intermediário \+ conferência manual) → 40% |
| Custo operacional/vendedor | R$ 6.324 × 40% \= **R$ 2.530/mês** |
| Com 3 vendedores (meio da faixa 2–5) | **R$ 7.590/mês** |
| Em 12 meses | **R$ 91.080/ano** |

**Mensagem Dia 3 resultante:**

Fala Túlio, tudo certo?

Fiz uma conta rápida com base no perfil de vocês.

Um vendedor CLT no segmento de material elétrico em MG custa em média R$ 6.300/mês pra empresa. Se 40% do tempo vai pra tirar pedido de cliente que já sabe comprar, isso são R$ 2.500/mês por vendedor sendo gasto em operacional, não em prospecção.

Com 3 vendedores, são R$ 7.500/mês. Em 12 meses, R$ 90.000.

Quando o cliente compra sozinho pelo portal, esse tempo vai pra abertura de conta nova. Mais cliente novo, mais comissão no final do mês.

Quer ver como fica com os números reais da Santos Simões? zydon.com.br/calculadora-roi

---

### Tabela de referência rápida por região e segmento

| Região | Segmento | Custo empresa/mês | 40% tempo | 60% tempo | 70% tempo |
| :---- | :---- | :---- | :---- | :---- | :---- |
| São Paulo capital | Industrial/elétrico | R$ 9.350 | R$ 3.740 | R$ 5.610 | R$ 6.545 |
| São Paulo interior | Industrial/elétrico | R$ 7.480 | R$ 2.992 | R$ 4.488 | R$ 5.236 |
| Minas Gerais | Material elétrico | R$ 6.324 | R$ 2.530 | R$ 3.794 | R$ 4.427 |
| Minas Gerais | Alimentos | R$ 5.814 | R$ 2.326 | R$ 3.488 | R$ 4.070 |
| Sul (RS/SC/PR) | Genérico | R$ 6.800 | R$ 2.720 | R$ 4.080 | R$ 4.760 |
| Centro-Oeste | Genérico | R$ 5.780 | R$ 2.312 | R$ 3.468 | R$ 4.046 |
| Nordeste | Genérico | R$ 4.930 | R$ 1.972 | R$ 2.958 | R$ 3.451 |

---

## PARTE 4 — MAPA DE VARIAÇÕES POR DOR PRINCIPAL

Para o Dia 1 e Dia 4, a segunda linha muda conforme a dor registrada no HubSpot:

| Dor principal (HubSpot) | Linha de dor para Dia 1 | Linha para Dia 4 |
| :---- | :---- | :---- |
| Vendedores tirando pedido | "o desafio aí parece ser o time travado tirando pedido em vez de prospectar" | "Sei que o plano era resolver a questão dos vendedores travados tirando pedido." |
| Taxa alta / margem apertada | "o desafio aí parece ser a taxa que vocês pagam por pedido hoje, que come margem direto" | "Sei que o plano era parar de pagar 5% por pedido pra quem não entende de atacado." |
| Sem visibilidade / gestão no feeling | "o desafio parece ser tomar decisão sem dado — sem saber quem está em churn, sem enxergar a operação em tempo real" | "Sei que o plano era ter visibilidade real da operação sem depender de Excel." |
| Escala sem contratar | "o desafio parece ser que crescer hoje significa contratar mais gente, e isso não escala" | "Sei que o plano era dobrar o volume sem precisar dobrar o time." |

---

*Documento interno Zydon — Jun/2026*  
