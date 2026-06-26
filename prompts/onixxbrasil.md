# TAREFA: Lead Onixxbrasil Cosmeticos (onixxbrasil) — pesquisa web + PDF + mensagem WhatsApp

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Existe um helper motor/render_one.py que renderiza UM lead a partir de um JSON dict (nao edite leads.py).

## PASSO 1 — Ler dados HubSpot
Leia o arquivo /root/zydon-prospeccao/pesquisas/onixxbrasil_hubspot.json. Use os dados reais (empresa, faturamento, ERP, forma de venda, time, area) no PDF.

## PASSO 2 — Pesquisar a empresa (WEB SEARCH OBRIGATÓRIO)
Use WebSearch e WebFetch para pesquisar "Onixxbrasil Cosmeticos" (dica de dominio: onixxbrasil.com.br (cosmeticos)). Descubra: o que faz, segmento, porte, area de atuacao, modelo de operacao. Salve resumo em /root/zydon-prospeccao/pesquisas/onixxbrasil.md com fontes.
Se a pesquisa retornar dados fracos, informe mas NAO invente insight generico.

## PASSO 3 — Montar dicionario lead
Leia motor/gen.py e motor/leads.py para entender a estrutura. Monte um dict completo para Onixxbrasil Cosmeticos (use "glassway" e "marck-suprimentos" em leads.py como modelo de chaves). Chaves obrigatorias:
slug="onixxbrasil", theme="dark", empresa="Onixxbrasil Cosmeticos", contato="Cristiano", cargo_area=(da pesquisa), local=(do hubspot city/state), telefone="", site=(dominio), sobre=(2-3 frases da PESQUISA), sobre_fonte=(fonte real), vende_para=(pesquisa+hubspot), como_vende=(hubspot de_qual_forma_mais_vende), loja_virtual=(hubspot vende_em_loja_virtual_), vendedores=(hubspot quantos_vendedores_internos ou "Nao informado"), time_total=(hubspot quantas_pessoas), faturamento=(hubspot faixa), compra_sozinho=(hubspot ou "A confirmar"), encontramos=[3 itens especificos da empresa baseados na pesquisa, NAO genericos], conta=(frase especifica), pot_low/pot_high/deixa_mes/pot_base/significa=(ROI ousado conforme faturamento), pushpull=(classificacao empurra/puxa), food=false (ou true se for atacado alimenticio).

### REGRA ERP (CRITICO — ERP do HubSpot: Bling → classificacao: nativo)
erp="Bling", erp_integ="Integracao nativa", erp_golive="7 a 14 dias", erp_dev="Nao (nativo)", erp_line="A Zydon tem integracao nativa com Sankhya, Omie, Olist e Bling — go-live mais rapido, sem projeto customizado."

## PASSO 4 — Gerar PDF
1. Salve o dict em /root/zydon-prospeccao/motor/onixxbrasil_lead.json
2. Rode: python3 /root/zydon-prospeccao/motor/render_one.py onixxbrasil /root/zydon-prospeccao/motor/onixxbrasil_lead.json
3. Confirme o PDF em /root/zydon-prospeccao/pdfs/Potencial-Digitalizacao-onixxbrasil.pdf (ls -la)

## PASSO 5 — Mensagem WhatsApp (template EXATO)
Escreva seguindo EXATAMENTe o formato aprovado:
Oi, Cristiano, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da Onixxbrasil Cosmeticos. Te mando em PDF aqui.

Em resumo, da pra [INSIGHT ESPECIFICO da pesquisa, 1 beneficio tangivel, sem ERP/go-live]. Um consultor nosso te chama na segunda-feira para fazer um diagnostico mais completo da Onixxbrasil Cosmeticos e te mostrar isso na pratica. Pode ser?

Salve em /root/zydon-prospeccao/pesquisas/onixxbrasil_msg.txt

## REGRAS INVIO LAVEIS
1. Insight DEVE ser especifico da empresa (da pesquisa), nunca generico.
2. A mensagem ao lead NAO pode mencionar ERP/nome do sistema.
3. NUNCA mencione go-live em 48h. No PDF rodape: go-live 7 a 14 dias (nativo) ou 30 a 60 dias (sob projeto).
4. Assinatura sempre "Aqui e a Mariana, da Zydon". Saudacao sempre "Oi, Cristiano, tudo bem?".
5. Sem travessao, sem emoji, sem icone, sem ERP/go-live/prazo na mensagem.

## SAIDA (texto)
1. Resumo pesquisa (2-3 linhas + fontes)
2. Dict montado (chaves+valores)
3. Texto EXATO da mensagem
4. Confirmacao do PDF (caminho + tamanho)
5. Duvidas/limitacoes
