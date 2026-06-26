# Playbook — Material "Potencial de Digitalização B2B" (Zydon)

Documento de regras + processo para gerar, em escala, os **PDFs de prospecção personalizados por lead (MQL)** e as **mensagens de WhatsApp** pareadas. Serve para o time técnico **automatizar** o pipeline.

---

## 1. Objetivo
Para cada lead qualificado (MQL) que preencheu o diagnóstico, gerar:
1. Um **PDF de 3 páginas** "Potencial de digitalização da operação B2B da [Empresa]", hiper-personalizado.
2. Uma **mensagem de WhatsApp** curta, pareada com o PDF, para o time de prospecção ativa enviar.

O material é **enviado ao cliente** (não é uso interno). Logo: linguagem em 2ª pessoa ("você"), sem jargão interno.

---

## 2. Recorte da base (ICP) — quem entra
Fonte: export HubSpot **`todos-os-contatos.csv`** (≈447 colunas) + **`todos-os-negocios.csv`**.

Filtros, na ordem:
1. **Fase do ciclo de vida = "Lead qualificado para marketing"** (MQL).
2. **Mês alvo**: coluna `Data que entrou em "Lead qualificado para marketing..."` dentro do mês (ex.: junho/2026). Ordenar **mais novos primeiro** (entrada; desempate = data de criação).
3. **Formulário completo** (sem isso não há diagnóstico): precisa ter `faturamento` + `como vende` + `maior problema` + (`vende para` ou `área de atuação`). Caso contrário, descartar.
4. **Remover inválidos**: domínio `@zydon` (lead interno); sem nome de empresa; faturamento "ainda não faturamos" (pré-receita); nome de empresa claramente inválido/piada.
5. **Remover perdidos e clientes**: cruzar pelo **e-mail** (campo `Associated Contact` do export de negócios, formato "Nome (email)"). Etapa `Negócio perdido` → remover; `Negócio fechado` → já é cliente, remover. Mantém quem tem negócio em **etapa aberta** ou sem negócio.
6. **Fora do ICP** (marcar, NÃO gerar): empresas que **não são distribuição/indústria B2B** — consultoria, mídia/rádio/publicidade, varejo B2C puro, etc. Um diagnóstico de digitalização de distribuição não cabe.

> No recorte de junho/2026: 305 MQLs no total → 208 em junho → 98 válidos (com formulário, sem perdidos) → **92 PDFs gerados** + 6 marcados (3 "revisar por falta de dado", 3 "fora do ICP").

---

## 3. Campos do formulário usados (HubSpot)
| Campo no PDF | Coluna de origem |
|---|---|
| Empresa / Contato | `Nome da empresa` / `Nome`+`Sobrenome` |
| Quem atende | `Você vende para quem?` (fallback `Qual a área de atuação`) |
| Como vende | `De qual forma mais vende hoje em dia?` |
| ERP | `Qual ERP utiliza?` / `Selecione o sistema de gestão (ERP)` |
| Faturamento | `...faturamento ANUAL...` / `Selecione a faixa de faturamento...` |
| Maior problema | `Qual seria o maior problema...` (vem codificado) |
| Vendedores internos | `Quantos vendedores internos...` |
| Time total | `Quantas pessoas atuam...` |
| Loja virtual | `Vende em loja virtual?` |
| Compra autônoma | `Você acredita que o seu cliente compraria sozinho...` |
| WhatsApp / Site | `Número de telefone do WhatsApp` / `URL do site` (ou `Domínio de e-mail`) |

---

## 4. Enriquecimento (pesquisa web) — obrigatório
Para cada empresa: pesquisar **site, redes sociais, CNPJ, ano de fundação, porte, nº de filiais, mix de produtos, segmento**. Cruzar com o segmento declarado.
- **Nunca inventar dado.** CNPJ/ano/filiais só se confirmados em fonte pública. Citar a fonte no bloco "Sobre".
- Site vazio/ambíguo ou produto não identificável → **marcar "perguntar ao contato o que vende"**, não gerar genérico.

---

## 5. Estrutura do PDF (3 páginas)
- **Pág. 1 — Capa / Perfil:** título; breadcrumb (Empresa / segmento / cidade-UF); "Preparado para [Nome]"; bloco **Sobre** (pesquisa + fonte); cards do perfil (quem atende, como vende, loja virtual, **ERP**, vendedores, time, faturamento, compra autônoma).
- **Pág. 2 — Diagnóstico:** "O que encontramos" (3 bullets); **CALLOUT "Esta operação empurra ou puxa pedido?"** (eixo central); "A conta que quase ninguém faz"; stats de mercado (R$ 443 bi atacado 2024 +9,78%; 14% já é e-commerce B2B; +62% crescimento do canal digital; +da metade das grandes compras por autoatendimento — fontes ABAD/NielsenIQ 2025 e Forrester).
- **Pág. 3 — Potencial & Integração:** **"O que fica na mesa"** por ano e por mês; checklist de ganhos; **caixa de ERP**.

---

## 6. REGRAS DE NEGÓCIO (críticas — não quebrar)
1. **Empurra × puxa é o eixo do argumento.** Produto diferenciado/recompra (cliente *quer* tirar o pedido) = demanda **puxada** = potencial de digitalização **altíssimo**. Venda empurrada / cotação de preço / cliente sem fidelidade = mais difícil (depende do vendedor). Sempre classificar e explicar.
2. **"Deixa na mesa" = 14%** da faixa de faturamento (benchmark de distribuidores que já digitalizaram), apresentado **por ano e por mês**. Sempre rotular como "estimativa ilustrativa; o número real depende da base e do mix".
3. **ERP:**
   - **Nativos via API**: Bling, Olist (Tiny), Omie, Sankhya → caixa "Nativa via API · go-live 20 a 30 dias · zero projeto de TI". Reforço: "a Zydon nasceu dentro do Sankhya".
   - **TOTVS = SOB CONSULTA** (NUNCA "nativo"): caixa "Sob consulta · Sob avaliação · Escopo caso a caso".
   - **"Outro/não informado"**: texto genérico — "integra nativamente com Bling, Olist, Omie e Sankhya; outros ERPs (como o TOTVS) sob consulta".
   - Se a dor declarada for "integrar com ERP é caro/complicado" → responder isso direto na caixa.
4. **Tratamento:** falar com a pessoa por **"você"**. Nunca "o lead" / "o cliente em 3ª pessoa".
5. **Marca:** logo oficial Zydon (branca no tema escuro, preta no claro — extrair do material oficial, não recriar); verde-limão **#CDEB00**; fonte de apoio **Manrope** (Poppins como substituta). Rodapé: "Material de briefing produzido pela Zydon" + "zydon.com.br" — **sem** "uso interno de prospecção".
6. **Teste A/B:** alternar tema **preto/branco** entre os leads para medir conversão.
7. **Dados inconsistentes** (ex.: faturamento "até R$ 250 mil" para empresa de +151 pessoas): não usar o número cru; estimar com ressalva explícita e recomendar recalcular.

---

## 7. Mensagem de WhatsApp
- Assinada pelo remetente real (ex.: "Aqui é a Mariana, da Zydon").
- **Curta, humana, sem ícones, sem travessão (—).**
- Estrutura: saudação pelo 1º nome → "preparei um material sobre o potencial de digitalização B2B da [Empresa]. Te mando em PDF aqui." → 1 frase de benefício (a dor declarada virada em ganho) → "Um consultor nosso entra em contato para fazer um diagnóstico mais completo da [Empresa]" (+ "na segunda-feira" se o lead entrou no fim de semana) → "Pode ser?".
- O **número** ("deixa na mesa") fica no PDF, não na mensagem.
- **Envio:** o texto pode ser pré-preenchido via link `wa.me/<num>?text=...`. **O anexo do PDF exige gesto humano** — o WhatsApp Web bloqueia envio de mídia por automação. Para automação ponta-a-ponta (texto + documento, em escala, sem risco de ban), usar a **WhatsApp Business Cloud API** com templates aprovados. **Não** automatizar disparo em massa no WhatsApp Web fingindo digitação humana (banimento de número).

---

## 8. Como rodar (técnico)
- **Stack:** Python 3 · `pandas`, `openpyxl` · `playwright` + Chromium (`python -m playwright install chromium`).
- **Fluxo:** dados do lead em dicts (ver `gen_batch*.py`) → `gen.py` (`build_html`) monta o HTML a partir do `TEMPLATE` → `render.py` converte HTML→PDF via Chromium headless (210×297 mm, print_background).
- **Saída:** `"{Empresa} - Potencial de Digitalização B2B.pdf"`.
- **Fila/controle:** `_fila/fila_junho.csv` (lead a lead, com tema A/B e status do PDF) e `_Índice MQLs Junho (98).xlsx`.

---

## 9. Estrutura dos arquivos (neste pacote)
- `motor/gen.py` — template + todas as regras de layout/marca/ERP/potencial.
- `motor/render.py` — HTML → PDF (Chromium/Playwright).
- `motor/leads.py` — dados dos 4 do piloto (exemplo de estrutura de lead).
- `motor/gen_batch*.py` — dados + copy personalizada de cada lote de empresas.
- `assets/logo/`, `assets/fonts/` — logo oficial e fonte.
- `dados/fila_junho.csv`, `dados/wpp_envios.json`, `dados/_Índice MQLs Junho (98).xlsx`.
- `exemplos/` — 3 PDFs prontos (tema escuro, claro e um com TOTVS "sob consulta").
- `PLAYBOOK.md` (este arquivo) e `README.md` (quickstart).

---

## 10. Próximo nível de automação (sugestão)
Pipeline recomendado:
1. **HubSpot API** puxa os MQLs do período + cruza negócios (perdidos/clientes).
2. **Enriquecimento web** automatizado por empresa (site/CNPJ/redes).
3. **LLM** gera a copy personalizada por lead **seguindo as regras da seção 6** (empurra×puxa, ERP, "deixa na mesa", tom "você").
4. `gen.py` + `render.py` produzem o PDF.
5. **WhatsApp Business Cloud API** dispara mensagem + documento (template aprovado).
6. Atualiza o índice/CRM com status.
