# TAREFA: Lead Brotitos Alimentos / William Almeida (brotitos-alimentos) — pesquisa web + PDF + mensagem

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Helper: motor/render_one.py. WEB SEARCH OBRIGATORIO.

## DADOS HUBSPOT (verdade do lead)
- Empresa: Brotitos Alimentos (dominio: brotitos.com.br)
- Contato: William Almeida
- ERP: Outro (sob projeto)
- Faturamento: Ate R$250 mil ao ano
- Como vende: "Vendedor porta a porta"
- Pessoas: 1 a 10
- Loja virtual: Sim
- Tel: 31985247783 (celular MG)
- Lifecycle: lead
- OBS: FORCAR MQL (aprovado pelo gestor) — processar como MQL.

## PASSO 1 — Pesquisar (WEB SEARCH OBRIGATORIO)
Use WebSearch/WebFetch em "Brotitos Alimentos" e "brotitos.com.br". Descubra: o que vende (probavel snacks/biscoitos/petiscos alimenticios), segmento exato, modelo de negocio (atacado/distribuicao/varejo?), para quem vende, porte. Salve em pesquisas/brotitos-alimentos.md com fontes.

## PASSO 2 — Decidir MQL
FORCAR MQL (gestor aprovou). Mesmo com faturamento pequeno e venda porta a porta, investigue o potencial B2B (atacado para revendas/mercados/lanchonetes). Continue.

## PASSO 3 — Montar dict
Leia motor/gen.py e motor/leads.py. Monte dict:
slug="brotitos-alimentos", theme="dark", empresa="Brotitos Alimentos", contato="William", cargo_area=(da pesquisa), local="MG", telefone="", site="brotitos.com.br", sobre=(2-3 frases da PESQUISA), sobre_fonte=(fonte real), vende_para=(da pesquisa), como_vende="Porta a porta e loja virtual", loja_virtual="Sim", vendedores="1 a 10", time_total="1 a 10 pessoas", faturamento="Ate R$250 mil por ano", compra_sozinho="A confirmar", encontramos=[3 itens ESPECIFICOS da pesquisa, NAO genericos], conta=(frase especifica), pot_low/pot_high/deixa_mes/pot_base/significa=(ROI ousado: R$250k -> potencial R$50k-R$150k/ano), pushpull=(classificacao), food=true.

### REGRA ERP (Outro -> sob projeto)
erp="Outro", erp_integ="Integracao sob projeto", erp_golive="30 a 60 dias", erp_dev="Sim (projeto)", erp_line="A Zydon avalia a integracao com Outro sob projeto tecnico. Prazo medio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."

## PASSO 4 — Gerar PDF
Salve dict em motor/brotitos-alimentos_lead.json. Rode: python3 motor/render_one.py brotitos-alimentos motor/brotitos-alimentos_lead.json. Confirme pdfs/Potencial-Digitalizacao-brotitos-alimentos.pdf (ls -la).

## PASSO 5 — Mensagem WhatsApp (HOJE SEGUNDA TARDE -> "Boa tarde", "jaja")
Boa tarde, William, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da Brotitos Alimentos. Te mando em PDF aqui.

Em resumo, da para [INSIGHT ESPECIFICO de alimentos/snacks da pesquisa, 1 beneficio tangivel, sem ERP/go-live]. Um consultor nosso jaja entra em contato com voce para fazer um diagnostico mais completo da Brotitos Alimentos e te mostrar isso na pratica. Pode ser?

Salve em pesquisas/brotitos-alimentos_msg.txt

## REGRAS INVIOLAVEIS
1. Insight ESPECIFICO da empresa, nunca generico.
2. Mensagem SEM ERP/go-live/jargao.
3. Rodape PDF: 30 a 60 dias (sob projeto).
4. "jaja entra em contato com voce" (dia util a tarde).
5. Sem travessao/emoji/icone. Acentos OK (á é ó ç).

## SAIDA: MQL SIM, resumo pesquisa, dict, texto msg, confirmacao PDF.
