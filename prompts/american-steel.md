# TAREFA: Lead American Steel (american-steel) — pesquisa web + PDF + mensagem WhatsApp

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Existe um helper motor/render_one.py que renderiza UM lead a partir de um JSON dict (nao edite leads.py).

## PASSO 1 — Ler dados HubSpot
Leia o arquivo /root/zydon-prospeccao/pesquisas/american-steel_hubspot.json. Use os dados reais (empresa, faturamento, ERP, forma de venda, time) no PDF.

## PASSO 2 — Pesquisar a empresa (WEB SEARCH OBRIGATORIO)
Use WebSearch e WebFetch para pesquisar "American Steel" / "American Steel Incorporation" (dominio provavel: americansteelincorporation.com.br). Descubra: o que faz, segmento (siderurgica/atacado deaco/distribuidor de metais/industria), porte, area de atuacao, modelo de operacao, distribuicao. Salve resumo em /root/zydon-prospeccao/pesquisas/american-steel.md com fontes.
Se a pesquisa retornar dados fracos, informe mas NAO invente insight generico.

## PASSO 3 — Montar dicionario lead
Leia motor/gen.py para entender a estrutura (funcao build_html). Monte um dict JSON completo para American Steel. Chaves obrigatorias:
slug="american-steel", theme="dark", empresa="American Steel", contato="Gian Lucca", cargo_area=(da pesquisa, ex: "Siderurgia / Comercio de Aco"), local=(da pesquisa, ex: "Belo Horizonte, MG" ou cidade que descobrir), telefone="", site="americansteelincorporation.com.br", sobre=(2-3 frases da PESQUISA), sobre_fonte=(fonte real), vende_para=(pesquisa+hubspot), como_vende="Telefone e WhatsApp" (hubspot), loja_virtual="Sim" (hubspot), vendedores="Nao informado", time_total="1 a 10 pessoas" (hubspot), faturamento="De R$500 mil a R$1 milhao por ano" (hubspot), compra_sozinho="A confirmar", encontramos=[3 itens especificos baseados na pesquisa sobre aco/metal/siderurgia, NAO genericos], conta=(frase especifica), pot_low/pot_high/deixa_mes/pot_base/significa=(ROI ousado conforme faturamento R$500k-R$1M -> potencial R$50 mil a R$200 mil/ano), pushpull=(classificacao empurra/puxa baseada na operacao), food=false.

### REGRA ERP (CRITICO — ERP do HubSpot: Outro -> classificacao: sobprojeto)
erp="Outro", erp_integ="Integracao sob projeto", erp_golive="30 a 60 dias", erp_dev="Sim (projeto)", erp_line="A Zydon avalia a integracao com 'Outro' sob projeto tecnico. Prazo medio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."

## PASSO 4 — Gerar PDF
1. Salve o dict em /root/zydon-prospeccao/motor/american-steel_lead.json
2. Rode: python3 /root/zydon-prospeccao/motor/render_one.py american-steel /root/zydon-prospeccao/motor/american-steel_lead.json
3. Confirme o PDF em /root/zydon-prospeccao/pdfs/Potencial-Digitalizacao-american-steel.pdf (ls -la)

## PASSO 5 — Mensagem WhatsApp (template EXATO)
Boa tarde, Gian Lucca, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da American Steel. Te mando em PDF aqui.

Em resumo, da pra [INSIGHT ESPECIFICO da siderurgica/distribuidora de aco, da pesquisa, 1 beneficio tangivel, sem ERP/go-live]. Um consultor nosso jaja entra em contato com voce para fazer um diagnostico mais completo da American Steel e te mostrar isso na pratica. Pode ser?

Salve em /root/zydon-prospeccao/pesquisas/american-steel_msg.txt

## REGRAS INVIOLAVEIS
1. Insight DEVE ser especifico da empresa (da pesquisa), nunca generico.
2. A mensagem ao lead NAO pode mencionar ERP/nome do sistema.
3. NUNCA mencione go-live em 48h. No PDF rodape: 30 a 60 dias (sob projeto).
4. Assinatura sempre "Aqui e a Mariana, da Zydon". Saudacao "Boa tarde, Gian Lucca, tudo bem?".
5. Sem travessao, sem emoji, sem icone, sem ERP/go-live/prazo na mensagem.
6. CONSULTOR TIMING: "jaja" (segunda-feira a tarde, horario comercial).

## SAIDA (texto)
1. Resumo pesquisa (2-3 linhas + fontes)
2. Dict montado (chaves+valores)
3. Texto EXATO da mensagem
4. Confirmacao do PDF (caminho + tamanho)
5. Duvidas/limitacoes
