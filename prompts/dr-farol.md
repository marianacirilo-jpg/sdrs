# TAREFA: Lead Dr Farol / Caio Teixeira (dr-farol) — pesquisa web + PDF + mensagem

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Helper: motor/render_one.py. WEB SEARCH OBRIGATORIO.

## DADOS HUBSPOT (verdade do lead)
- Empresa: Dr Farol (company="Dr Farol")
- Contato: Caio Teixeira
- ERP: Bling (NATIVO Zydon)
- Faturamento: De R$10 a R$50 milhoes ao ano
- Como vende: "Vendemos dentro da rede de franquias"
- Pessoas: 1 a 10
- Loja virtual: Sim
- Tel: 169914174176 (celular)
- Lifecycle: marketingqualifiedlead

## PASSO 1 — Pesquisar (WEB SEARCH OBRIGATORIO)
Use WebSearch/WebFetch em "Dr Farol" (rede de franquias, provavel automotivo/eletricidade/farois de veiculos). Descubra: o que faz, segmento exato (rede de franquias de quê?), modelo B2B (para quem vende/loja), porte, produtos. Salve em pesquisas/dr-farol.md com fontes.

## PASSO 2 — Decidir MQL
MQL se atacado/distribuidor/industria B2B. Rede de franquias automotivas com R$10-50M = MQL forte. Continue.

## PASSO 3 — Montar dict
Leia motor/gen.py e motor/leads.py. Monte dict:
slug="dr-farol", theme="dark", empresa="Dr Farol", contato="Caio", cargo_area=(da pesquisa), local="SP", telefone="", site=(da pesquisa), sobre=(2-3 frases da PESQUISA), sobre_fonte=(fonte real), vende_para=(da pesquisa B2B), como_vende="Rede de franquias", loja_virtual="Sim", vendedores="1 a 10", time_total="1 a 10 pessoas", faturamento="De R$10 a R$50 milhoes por ano", compra_sozinho="A confirmar", encontramos=[3 itens ESPECIFICOS da pesquisa, NAO genericos], conta=(frase especifica), pot_low/pot_high/deixa_mes/pot_base/significa=(ROI ousado: R$10-50M -> potencial R$1M-R$5M/ano), pushpull=(classificacao), food=false.

### REGRA ERP (Bling = NATIVO)
erp="Bling", erp_integ="Integracao nativa Zydon", erp_golive="Imediato", erp_dev="Nao (nativo)", erp_line="A Zydon tem integracao nativa com o Bling. Go-live imediato, sem projeto de integracao."

## PASSO 4 — Gerar PDF
Salve dict em motor/dr-farol_lead.json. Rode: python3 motor/render_one.py dr-farol motor/dr-farol_lead.json. Confirme pdfs/Potencial-Digitalizacao-dr-farol.pdf (ls -la).

## PASSO 5 — Mensagem WhatsApp (HOJE SEGUNDA TARDE -> "Boa tarde", "jaja")
Boa tarde, Caio, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da Dr Farol. Te mando em PDF aqui.

Em resumo, da para [INSIGHT ESPECIFICO da rede de franquias automotivas da pesquisa, 1 beneficio tangivel, sem ERP/go-live]. Um consultor nosso jaja entra em contato com voce para fazer um diagnostico mais completo da Dr Farol e te mostrar isso na pratica. Pode ser?

Salve em pesquisas/dr-farol_msg.txt

## REGRAS INVIOLAVEIS
1. Insight ESPECIFICO da empresa, nunca generico.
2. Mensagem SEM ERP/go-live/jargao.
3. Rodape PDF: integracao nativa Bling (go-live imediato, sem projeto).
4. "jaja entra em contato com voce" (dia util a tarde).
5. Sem travessao/emoji/icone. Acentos OK (á é ó ç).

## SAIDA: MQL SIM/NAO, resumo pesquisa, dict, texto msg, confirmacao PDF.
