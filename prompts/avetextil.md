# TAREFA: Lead Ave Textil (avetextil) — pesquisa web + PDF + mensagem WhatsApp

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Existe um helper motor/render_one.py que renderiza UM lead a partir de um JSON dict (nao edite leads.py).

## PASSO 1 — Ler dados HubSpot
Leia o arquivo /root/zydon-prospeccao/pesquisas/avetextil_hubspot.json. Use os dados reais (empresa, faturamento, ERP, forma de venda, time, area) no PDF.

## PASSO 2 — Pesquisar a empresa (WEB SEARCH OBRIGATORIO)
Use WebSearch e WebFetch para pesquisar "Ave Textil" (dica de dominio: avetextil.com.br). Ave Textil e uma industria textil em Santa Catarina. Descubra: o que faz/tece, segmento, porte, area de atuacao, modelo de operacao, como vende. Salve resumo em /root/zydon-prospeccao/pesquisas/avetextil.md com fontes.
Se a pesquisa retornar dados fracos, informe mas NAO invente insight generico.

## PASSO 3 — Montar dicionario lead
Leia motor/gen.py e motor/leads.py para entender a estrutura. Monte um dict completo para Ave Textil (use "glassway" e "marck-suprimentos" em leads.py como modelo de chaves). Chaves obrigatorias:
slug="avetextil", theme="dark", empresa="Ave Textil", contato="Amanda", cargo_area=(da pesquisa), local="Santa Catarina", telefone="5548991744106", site="avetextil.com.br", sobre=(2-3 frases da PESQUISA), sobre_fonte=(fonte real), vende_para=(pesquisa+hubspot), como_vende="WhatsApp" (hubspot), loja_virtual="Nao" (hubspot), vendedores="Nao informado", time_total="1 a 10 pessoas" (hubspot), faturamento="De R$1 milhao a R$5 milhoes por ano" (hubspot), compra_sozinho="A confirmar", encontramos=[3 itens especificos da industria textil baseados na pesquisa, NAO genericos], conta=(frase especifica), pot_low/pot_high/deixa_mes/pot_base/significa=(ROI ousado conforme faturamento R$1-5M), pushpull=(classificacao empurra/puxa), food=false.

### REGRA ERP (CRITICO — ERP do HubSpot: Outro → classificacao: sobprojeto)
erp="Outro", erp_integ="Integracao sob projeto", erp_golive="30 a 60 dias", erp_dev="Sim (projeto)", erp_line="A Zydon avalia a integracao com 'Outro' sob projeto tecnico. Prazo medio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."

## PASSO 4 — Gerar PDF
1. Salve o dict em /root/zydon-prospeccao/motor/avetextil_lead.json
2. Rode: python3 /root/zydon-prospeccao/motor/render_one.py avetextil /root/zydon-prospeccao/motor/avetextil_lead.json
3. Confirme o PDF em /root/zydon-prospeccao/pdfs/Potencial-Digitalizacao-avetextil.pdf (ls -la)

## PASSO 5 — Mensagem WhatsApp (template EXATO)
Oi, Amanda, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da Ave Textil. Te mando em PDF aqui.

Em resumo, da pra [INSIGHT ESPECIFICO da industria textil, da pesquisa, 1 beneficio tangivel, sem ERP/go-live]. Um consultor nosso te chama na segunda-feira para fazer um diagnostico mais completo da Ave Textil e te mostrar isso na pratica. Pode ser?

Salve em /root/zydon-prospeccao/pesquisas/avetextil_msg.txt

## REGRAS INVIOLAVEIS
1. Insight DEVE ser especifico da empresa (da pesquisa), nunca generico.
2. A mensagem ao lead NAO pode mencionar ERP/nome do sistema.
3. NUNCA mencione go-live em 48h. No PDF rodape: 30 a 60 dias (sob projeto).
4. Assinatura sempre "Aqui e a Mariana, da Zydon". Saudacao sempre "Oi, Amanda, tudo bem?".
5. Sem travessao, sem emoji, sem icone, sem ERP/go-live/prazo na mensagem.

## SAIDA (texto)
1. Resumo pesquisa (2-3 linhas + fontes)
2. Dict montado (chaves+valores)
3. Texto EXATO da mensagem
4. Confirmacao do PDF (caminho + tamanho)
5. Duvidas/limitacoes
