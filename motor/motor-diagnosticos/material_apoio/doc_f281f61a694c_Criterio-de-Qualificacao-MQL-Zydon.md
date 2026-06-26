# Critério de Qualificação MQL — Zydon

> Regra usada para decidir o **ciclo de vida** de cada contato no HubSpot: **Lead** vs **Marketing Qualified Lead (MQL)**.
> Contexto: a Zydon é uma plataforma de e-commerce B2B para **distribuidoras/atacadistas e indústrias**. O ICP é esse.

---

## É MQL qualificado quando (TODAS as condições)

1. **Preencheu o formulário/diagnóstico** (lead ad).
2. **É distribuição ou indústria B2B** (catálogo + recompra/reposição) **OU** roda um **ERP do big-five** — Bling, Olist/Tiny, Omie, Sankhya, TOTVS (o *"ERP-gate"*).
3. **Já fatura** — NÃO pré-receita (não respondeu *"ainda não faturamos"*).
4. **Tem empresa real e domínio que confere** — não `@zydon`, não gmail/hotmail sem empresa, não domínio que diverge da empresa sem explicação.
5. **Não está em estágio posterior a MQL** (opportunity / cliente / perdido) nem já processado.

## Lead "muito bom" (alta probabilidade)

Distribuidora/indústria com recompra clara (peça, insumo, consumível, embalagem, alimento) **+** loja virtual **+** fatura **> R$5 mi** **+** ERP big-five **+** cliente que *"compraria sozinho"* (demanda puxada / autosserviço).

## Fora do ICP — vira Lead / descarte (não gera material)

- Financeiro / meios de pagamento / fintech
- Mídia / publicidade / agência (marketing, e-commerce, comunicação visual = serviço)
- Varejo B2C puro
- Serviços / consultoria (salvo se rodar ERP big-five)
- Educação / órgão público
- **Pré-receita** ("ainda não faturamos")
- Testes / e-mails internos `@zydon` / dados inválidos

## Revisar (segurar até confirmar — nunca inventar dado)

- Site/domínio vazio ou ambíguo
- Empresa, contato e domínio divergem entre si
- Formulário incompleto

**Regra de ouro: nunca inventar dado.** Na dúvida, vai para *revisar*, não para MQL.

---

## Promover Lead → MQL no HubSpot

Só promover quando **TODAS**:

1. Preencheu o diagnóstico;
2. Está em `lead` ou `subscriber` (nunca re-marcar quem já passou de MQL; nunca mexer em fechado/perdido);
3. Bate no ICP (regra acima);
4. Não está em `processed_emails`.

> Prioriza **precisão** — o Meta aprende com a marcação de MQL, então um MQL errado piora a otimização do anúncio.

---

## Campos do HubSpot usados na qualificação

- **Faturamento:** `qual_o_faturamento_anual_da_sua_empresa_` (e variações de formulário: `selecione_a_faixa_de_faturamento`, `qual_o_faturamento_anual_do_seu_negcio`, `e_qual_faturamento_anual_da_sua_empresa`). Valor de descarte: `Ainda não faturamos`.
- **ERP:** `selecione_o_sistema_de_gesto_erp`, `qual_erp_utiliza_`.
- **Segmento/nicho:** `nicho__subsegmento`, `voc_vende_para_quem_...`.
- **Autosserviço:** `voc_acredita_que_o_seu_cliente_compraria_sozinho...`.
- **Loja virtual:** `vende_em_loja_virtual_`.
- **Ciclo de vida:** `lifecyclestage`.
