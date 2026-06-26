# TAREFA: Lead Retifica Fronza / Vitor (retifica-fronza) — pesquisa web + PDF + mensagem

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Helper: motor/render_one.py. WEB SEARCH OBRIGATORIO.

## DADOS HUBSPOT (verdade do lead)
- Empresa: Retifica Fronza (dominio: retificafronza.com.br)
- Contato: Vitor
- ERP: Bling (NATIVO Zydon)
- Faturamento: De R$1 milhao a R$5 milhoes ao ano
- Como vende: Mercado Livre
- Pessoas: 1 a 10
- Loja virtual: Sim
- Tel: 48998640038 (celular SC)
- Lifecycle: marketingqualifiedlead

## PASSO 1 — Pesquisar (WEB SEARCH OBRIGATORIO)
Use WebSearch/WebFetch em "Retifica Fronza" e "retificafronza.com.br". Descubra: o que faz (retifica de motores automotivos), segmento exato (autopecas/retifica/servicos de motor), modelo B2B (para quem vende — oficinas/revendas/autopecas?), porte, produtos/servicos. Salve em pesquisas/retifica-fronza.md com fontes.

## PASSO 2 — Decidir MQL
MQL se atacado/distribuidor/industria B2B. Retifica de motores com R$1-5M vendendo no Mercado Livre = MQL forte (autopecas B2B). Continue.

## PASSO 3 — Montar dict
Leia motor/gen.py e motor/leads.py. Monte dict:
slug="retifica-fronza", theme="dark", empresa="Retifica Fronza", contato="Vitor", cargo_area=(da pesquisa), local="SC", telefone="", site="retificafronza.com.br", sobre=(2-3 frases da PESQUISA), sobre_fonte=(fonte real), vende_para=(da pesquisa B2B), como_vende="Mercado Livre", loja_virtual="Sim", vendedores="1 a 10", time_total="1 a 10 pessoas", faturamento="De R$1 milhao a R$5 milhoes por ano", compra_sozinho="A confirmar", encontramos=[3 itens ESPECIFICOS da pesquisa, NAO genericos], conta=(frase especifica), pot_low/pot_high/deixa_mes/pot_base/significa=(ROI ousado: R$1-5M -> potencial R$200k-R$800k/ano), pushpull=(classificacao), food=false.

### REGRA ERP (Bling = NATIVO)
erp="Bling", erp_integ="Integracao nativa Zydon", erp_golive="Imediato", erp_dev="Nao (nativo)", erp_line="A Zydon tem integracao nativa com o Bling. Go-live imediato, sem projeto de integracao."

## PASSO 4 — Gerar PDF
Salve dict em motor/retifica-fronza_lead.json. Rode: python3 motor/render_one.py retifica-fronza motor/retifica-fronza_lead.json. Confirme pdfs/Potencial-Digitalizacao-retifica-fronza.pdf (ls -la).

## PASSO 5 — Mensagem WhatsApp (HOJE SEGUNDA TARDE -> "Boa tarde", "jaja")
Boa tarde, Vitor, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da Retifica Fronza. Te mando em PDF aqui.

Em resumo, da para [INSIGHT ESPECIFICO de retifica/autopecas/motores da pesquisa, 1 beneficio tangivel, sem ERP/go-live]. Um consultor nosso jaja entra em contato com voce para fazer um diagnostico mais completo da Retifica Fronza e te mostrar isso na pratica. Pode ser?

Salve em pesquisas/retifica-fronza_msg.txt

## REGRAS INVIOLAVEIS
1. Insight ESPECIFICO da empresa, nunca generico.
2. Mensagem SEM ERP/go-live/jargao.
3. Rodape PDF: integracao nativa Bling (go-live imediato, sem projeto).
4. "jaja entra em contato com voce" (dia util a tarde).
5. Sem travessao/emoji/icone. Acentos OK (á é ó ç).

## SAIDA: MQL SIM/NAO, resumo pesquisa, dict, texto msg, confirmacao PDF.
