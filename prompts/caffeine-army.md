# TAREFA: Lead Caffeine army (caffeine-army) — pesquisa web + PDF + mensagem WhatsApp

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Helper: motor/render_one.py.

## DADOS HUBSPOT (VERDADE DO LEAD — confie no form)
- Empresa: Caffeine army
- Contato: Amanda Borges
- ERP: TOTVS (sob projeto)
- Faturamento: De R$50 a R$500 milhoes ao ano (PORTE GRANDE)
- Como vende: WhatsApp
- Pessoas: 51 a 150
- Loja virtual: nao
- Local: Salvador, BA
- Tel: 71993247570
- Owner: 86265630, ja e MQL

## PASSO 1 — Pesquisar (WEB SEARCH OBRIGATORIO)
Use WebSearch e WebFetch para pesquisar "Caffeine army" (caffeinearmy.com.br, Salvador/BA). E uma marca de energeticos/suplementos/bebidas. Descubra: o que faz, segmento exato (bebidas/energetico/suplemento?), modelo de operacao B2B (distribuidores/atacado/revenda), porte. Salve em pesquisas/caffeine-army.md com fontes.

## PASSO 2 — Decidir MQL
E MQL (industria de bebidas/suplementos com revenda B2B por WhatsApp, faturamento R$50-500mi, 51-150 pessoas). Continue.

## PASSO 3 — Montar dict
Leia motor/gen.py e motor/leads.py. Monte dict completo:
slug="caffeine-army", theme="dark", empresa="Caffeine Army", contato="Amanda", cargo_area=(da pesquisa), local="Salvador, BA", telefone="", site="caffeinearmy.com.br", sobre=(2-3 frases da PESQUISA), sobre_fonte=(fonte real), vende_para=(distribuidores/atacadistas B2B da pesquisa), como_vende="WhatsApp", loja_virtual="Nao", vendedores="Nao informado", time_total="51 a 150 pessoas", faturamento="De R$50 a R$500 milhoes por ano", compra_sozinho="A confirmar", encontramos=[3 itens ESPECIFICOS da pesquisa, NAO genericos], conta=(frase especifica), pot_low/pot_high/deixa_mes/pot_base/significa=(ROI ousado: faturamento R$50-500mi -> potencial R$8 milhoes-R$50 milhoes/ano), pushpull=(classificacao empurra/puxa), food=true (bebida).

### REGRA ERP (TOTVS -> sob projeto)
erp="TOTVS", erp_integ="Integracao sob projeto", erp_golive="30 a 60 dias", erp_dev="Sim (projeto)", erp_line="A Zydon avalia a integracao com TOTVS sob projeto tecnico. Prazo medio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."

## PASSO 4 — Gerar PDF
Salve dict em motor/caffeine-army_lead.json. Rode: python3 motor/render_one.py caffeine-army motor/caffeine-army_lead.json. Confirme pdfs/Potencial-Digitalizacao-caffeine-army.pdf (ls -la).

## PASSO 5 — Mensagem WhatsApp (HOJE E SEGUNDA, MANHA -> "jaja")
Bom dia, Amanda, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da Caffeine Army. Te mando em PDF aqui.

Em resumo, da pra [INSIGHT ESPECIFICO da pesquisa de energetico/bebida, 1 beneficio tangivel, sem ERP/go-live]. Um consultor nosso JAJA entra em contato com voce para fazer um diagnostico mais completo da Caffeine Army e te mostrar isso na pratica. Pode ser?

Salve em pesquisas/caffeine-army_msg.txt

## REGRAS INVIOLAVEIS
1. Insight ESPECIFICO da empresa, nunca generico.
2. Mensagem SEM ERP/go-live/jargao.
3. Rodape PDF: 30 a 60 dias (sob projeto).
4. "jaja entra em contato com voce" (dia util, manha).
5. Sem travessao/emoji/icone.

## SAIDA: MQL SIM, resumo pesquisa, dict, texto msg, confirmacao PDF.