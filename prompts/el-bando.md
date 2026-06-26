# TAREFA: Lead REparts / El Bando / Flavio Bressan (el-bando) — pesquisa web + PDF + mensagem

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Helper: motor/render_one.py. WEB SEARCH OBRIGATORIO.

## DADOS HUBSPOT (verdade do lead)
- Empresa: REparts Pecas e Acessorios (company="REparts Pecas e Acessorios", dominio elbando.com.br)
- Contato: Flavio Bressan
- ERP: Bling (NATIVO Zydon)
- Faturamento: De R$500 mil a R$1 milhao ao ano
- Como vende: "Loja nuvemshop e pagina no Meli" (Mercado Livre)
- Pessoas: 1 a 10
- Loja virtual: Sim
- Tel: 61984011486 (celular, DF)
- Lifecycle: marketingqualifiedlead

## PASSO 1 — Pesquisar (WEB SEARCH OBRIGATORIO)
Use WebSearch/WebFetch em "REparts pecas e acessorios" e "elbando.com.br". Descubra: o que vende (provavel pecas/acessorios automotivos ou similares), segmento exato, modelo B2B (para quem vende), porte, nuvemshop+Meli. Salve em pesquisas/el-bando.md com fontes.

## PASSO 2 — Decidir MQL
MQL se atacado/distribuidor/industria B2B. E-commerce (nuvemshop+Meli) R$500k-1M de pecas/acessorios = provavel MQL. Continue.

## PASSO 3 — Montar dict
Leia motor/gen.py e motor/leads.py. Monte dict:
slug="el-bando", theme="dark", empresa="REparts", contato="Flavio", cargo_area=(da pesquisa), local="DF", telefone="", site="elbando.com.br", sobre=(2-3 frases da PESQUISA), sobre_fonte=(fonte real), vende_para=(da pesquisa B2B), como_vende="Loja nuvemshop e Mercado Livre", loja_virtual="Sim", vendedores="1 a 10", time_total="1 a 10 pessoas", faturamento="De R$500 mil a R$1 milhao por ano", compra_sozinho="A confirmar", encontramos=[3 itens ESPECIFICOS da pesquisa, NAO genericos], conta=(frase especifica), pot_low/pot_high/deixa_mes/pot_base/significa=(ROI ousado: R$500k-1M -> potencial R$100k-R$300k/ano), pushpull=(classificacao), food=false.

### REGRA ERP (Bling = NATIVO)
erp="Bling", erp_integ="Integracao nativa Zydon", erp_golive="Imediato", erp_dev="Nao (nativo)", erp_line="A Zydon tem integracao nativa com o Bling. Go-live imediato, sem projeto de integracao."

## PASSO 4 — Gerar PDF
Salve dict em motor/el-bando_lead.json. Rode: python3 motor/render_one.py el-bando motor/el-bando_lead.json. Confirme pdfs/Potencial-Digitalizacao-el-bando.pdf (ls -la).

## PASSO 5 — Mensagem WhatsApp (HOJE SEGUNDA TARDE -> "Boa tarde", "jaja")
Boa tarde, Flavio, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da REparts. Te mando em PDF aqui.

Em resumo, da para [INSIGHT ESPECIFICO de e-commerce de pecas/acessorios (nuvemshop+Meli) da pesquisa, 1 beneficio tangivel, sem ERP/go-live]. Um consultor nosso jaja entra em contato com voce para fazer um diagnostico mais completo da REparts e te mostrar isso na pratica. Pode ser?

Salve em pesquisas/el-bando_msg.txt

## REGRAS INVIOLAVEIS
1. Insight ESPECIFICO da empresa, nunca generico.
2. Mensagem SEM ERP/go-live/jargao.
3. Rodape PDF: integracao nativa Bling (go-live imediato, sem projeto).
4. "jaja entra em contato com voce" (dia util a tarde).
5. Sem travessao/emoji/icone. Acentos OK (á é ó ç).

## SAIDA: MQL SIM/NAO, resumo pesquisa, dict, texto msg, confirmacao PDF.
