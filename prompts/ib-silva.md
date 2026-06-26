# TAREFA: Lead I B silva (ib-silva) — pesquisa web + PDF + mensagem WhatsApp

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Existe um helper motor/render_one.py que renderiza UM lead a partir de um JSON dict (nao edite leads.py).

## PASSO 1 — Ler dados HubSpot
Leia o arquivo /root/zydon-prospeccao/pesquisas/ib-silva_hubspot.json. Use os dados reais (empresa, faturamento, ERP, forma de venda, time, area) no PDF.

## PASSO 2 — Pesquisar a empresa (WEB SEARCH OBRIGATORIO)
Use WebSearch e WebFetch para pesquisar "I B silva" (dica: guia de fornecedores/distribuicao industrial). Descubra: o que faz, segmento, porte, area de atuacao, modelo de operacao, distribuicao. Salve resumo em /root/zydon-prospeccao/pesquisas/ib-silva.md com fontes.
Se a pesquisa retornar dados fracos, informe mas NAO invente insight generico.

## PASSO 3 — Decidir MQL
Apos a pesquisa, decida: a empresa e atacado/distribuidor/industria B2B com fito? Se NAO for MQL (fora do perfil, varejo puro, etc.), ESCREVA "NAO_MQL: <motivo>" na primeira linha da saida e NAO gere PDF. Se for MQL, continue.

## PASSO 4 — Montar dicionario lead
Leia motor/gen.py e motor/leads.py para entender a estrutura. Monte um dict completo. Chaves obrigatorias:
slug="ib-silva", theme="dark", empresa="I B silva", contato="Vando", cargo_area=(da pesquisa), local=(da pesquisa), telefone="", site="guiafornecedoresic.com.br", sobre=(2-3 frases da PESQUISA), sobre_fonte=(fonte real), vende_para=(pesquisa+hubspot), como_vende="Carteira de cliente + feiras do setor", loja_virtual="nao", vendedores="1 a 10", time_total="1 a 10 pessoas", faturamento="Ate R$250 mil por ano", compra_sozinho="A confirmar", encontramos=[3 itens ESPECIFICOS baseados na pesquisa, NAO genericos], conta=(frase especifica), pot_low/pot_high/deixa_mes/pot_base/significa=(ROI ousado conforme faturamento ate R$250k -> potencial R$50k-R$200k/ano), pushpull=(classificacao empurra/puxa).

### REGRA ERP (CRITICO — ERP do HubSpot: Outro)
erp="Outro", erp_integ="Integracao sob projeto", erp_golive="30 a 60 dias", erp_dev="Sim (projeto)", erp_line="A Zydon avalia a integracao com Outro sob projeto tecnico. Prazo medio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."

## PASSO 5 — Gerar PDF
1. Salve o dict em /root/zydon-prospeccao/motor/ib-silva_lead.json
2. Rode: python3 /root/zydon-prospeccao/motor/render_one.py ib-silva /root/zydon-prospeccao/motor/ib-silva_lead.json
3. Confirme o PDF em /root/zydon-prospeccao/pdfs/Potencial-Digitalizacao-ib-silva.pdf (ls -la)

## PASSO 6 — Mensagem WhatsApp (template EXATO)
Oi, Vando, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da I B silva. Te mando em PDF aqui.

Em resumo, da pra [INSIGHT ESPECIFICO da pesquisa, 1 beneficio tangivel, sem ERP/go-live]. Um consultor nosso te chama na segunda-feira para fazer um diagnostico mais completo da I B silva e te mostrar isso na pratica. Pode ser?

Salve em /root/zydon-prospeccao/pesquisas/ib-silva_msg.txt

## REGRAS INVIOLAVEIS
1. Insight DEVE ser especifico da empresa (da pesquisa), nunca generico.
2. A mensagem ao lead NAO pode mencionar ERP/nome do sistema.
3. NUNCA mencione go-live em 48h. No PDF rodape: 30 a 60 dias (sob projeto).
4. Assinatura sempre "Aqui e a Mariana, da Zydon". Saudacao sempre "Oi, Vando, tudo bem?".
5. Sem travessao, sem emoji, sem icone, sem ERP/go-live/prazo na mensagem.

## SAIDA (texto)
1. MQL: SIM ou NAO_MQL: <motivo>
2. Resumo pesquisa (2-3 linhas + fontes)
3. Dict montado (chaves+valores)
4. Texto EXATO da mensagem
5. Confirmacao do PDF (caminho + tamanho)
