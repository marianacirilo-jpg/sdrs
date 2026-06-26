# TAREFA: Lead Copperbrás / Leonardo Schmidt (copperbras) — pesquisa web + PDF + mensagem

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Helper: motor/render_one.py.

## DADOS HUBSPOT (verdade do lead)
- Empresa: Copperbrás (company="copper", dominio copperbras.com.br)
- Contato: Leonardo Schmidt
- ERP: Outro (sob projeto)
- Faturamento: De R$1 milhao a R$5 milhoes ao ano
- Como vende: WhatsApp
- Pessoas: 1 a 10
- Loja virtual: nao
- Tel: 32987070005

## PASSO 1 — Pesquisar (WEB SEARCH OBRIGATORIO)
Use WebSearch e WebFetch para pesquisar "Copperbras" (copperbras.com.br). E provavel industria/distribuidora de cobre/latao/chapas/condutores eletricos. Descubra: o que faz, segmento exato, modelo B2B (para quem vende), porte, produtos. Salve em pesquisas/copperbras.md com fontes.

## PASSO 2 — Decidir MQL
E MQL se for atacado/distribuidor/industria B2B. Copperbras aparenta industria de cobre/metais B2B com faturamento R$1-5M vendendo por WhatsApp. Provavelmente MQL. Continue.

## PASSO 3 — Montar dict
Leia motor/gen.py e motor/leads.py. Monte dict:
slug="copperbras", theme="dark", empresa="Copperbrás", contato="Leonardo", cargo_area=(da pesquisa), local="MG", telefone="", site="copperbras.com.br", sobre=(2-3 frases da PESQUISA), sobre_fonte=(fonte real), vende_para=(da pesquisa B2B), como_vende="WhatsApp", loja_virtual="Nao", vendedores="Nao informado", time_total="1 a 10 pessoas", faturamento="De R$1 milhao a R$5 milhoes por ano", compra_sozinho="A confirmar", encontramos=[3 itens ESPECIFICOS da pesquisa de cobre/metais, NAO genericos], conta=(frase especifica), pot_low/pot_high/deixa_mes/pot_base/significa=(ROI ousado: faturamento R$1-5M -> potencial R$200k-R$800k/ano), pushpull=(classificacao), food=false.

### REGRA ERP (Outro -> sob projeto)
erp="Outro", erp_integ="Integracao sob projeto", erp_golive="30 a 60 dias", erp_dev="Sim (projeto)", erp_line="A Zydon avalia a integracao com Outro sob projeto tecnico. Prazo medio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."

## PASSO 4 — Gerar PDF
Salve dict em motor/copperbras_lead.json. Rode: python3 motor/render_one.py copperbras motor/copperbras_lead.json. Confirme pdfs/Potencial-Digitalizacao-copperbras.pdf (ls -la).

## PASSO 5 — Mensagem WhatsApp (HOJE SEGUNDA MANHA -> "jaja")
Bom dia, Leonardo, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da Copperbrás. Te mando em PDF aqui.

Em resumo, da pra [INSIGHT ESPECIFICO de cobre/metais da pesquisa, 1 beneficio tangivel, sem ERP/go-live]. Um consultor nosso JAJA entra em contato com voce para fazer um diagnostico mais completo da Copperbrás e te mostrar isso na pratica. Pode ser?

Salve em pesquisas/copperbras_msg.txt

## REGRAS INVIOLAVEIS
1. Insight ESPECIFICO da empresa, nunca generico.
2. Mensagem SEM ERP/go-live/jargao.
3. Rodape PDF: 30 a 60 dias (sob projeto).
4. "jaja entra em contato com voce" (dia util, manha).
5. Sem travessao/emoji/icone.

## SAIDA: MQL SIM/NAO, resumo pesquisa, dict, texto msg, confirmacao PDF.