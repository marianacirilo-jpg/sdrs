# -*- coding: utf-8 -*-
import os
from playwright.sync_api import sync_playwright
import gen
OUT=os.path.dirname(os.path.abspath(__file__)); DEST=os.path.join(OUT,"Potencial Digitalização B2B - MQLs")
def native(erp,emp): return (f"A {emp} roda no <b>{erp}</b> &mdash; e a Zydon tem <b>integração nativa via API com o {erp}</b>. "
        "Catálogo, preço, estoque e pedido sincronizados em tempo real, sem desenvolvimento e sem retrabalho.")
def sankhya(emp): return (f"A {emp} roda no <b>Sankhya</b> &mdash; e a Zydon <b>nasceu dentro do Sankhya</b>, com <b>integração nativa via API</b>. "
        "Catálogo, preço, estoque e pedido sincronizados em tempo real, sem projeto de TI.")
GEN=("A Zydon integra <b>nativamente via API com Bling, Olist, Omie e Sankhya</b> &mdash; e conecta outros ERPs sob consulta. "
     "Seja qual for o sistema da {emp}, pedido, estoque e tabela passam a conversar em tempo real com o portal.")
NAT=("Nativa via API","20 a 30 dias","Zero. Sem projeto de TI")

LEADS=[
 {"slug":"galante","theme":"light","food":False,"empresa":"Distribuidora Galante","contato":"Paulo Galante","cargo_area":"Distribuição de material de construção","local":"Brasil",
  "sobre":("A Distribuidora Galante é <b>distribuidora de material de construção</b>, atendendo <b>lojas do setor</b> com pedido direto no "
           "cliente. Opera com loja virtual e catálogo de itens de giro, com recompra recorrente do varejo de construção."),
  "sobre_fonte":"Fontes: site distribuidoragalante.com e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Lojas de material de construção","como_vende":"Pedido direto no cliente","loja_virtual":"Possui","erp":"Olist (Tiny)",
  "vendedores":"2 a 5 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 250 mil a R$ 500 mil","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Galante distribui <b>material de construção</b> para lojas do setor &mdash; itens de giro de recompra recorrente.",
   "A venda é por <b>pedido direto no cliente</b> &mdash; e a recompra da loja ainda depende do contato.",
   "Tem loja virtual, mas falta um canal B2B com tabela do lojista para digitalizar a recompra."],
  "pushpull":("A demanda é <b>puxada</b>: a loja de construção recompra item de giro &mdash; sabe o que vende. Você nos disse que o cliente "
              "<b>compraria sozinho</b>; um portal B2B digitaliza essa recompra e libera o time para abrir conta nova."),
  "conta":("Reposição de material é repetida &mdash; depender do pedido direto põe teto na operação. Um catálogo B2B <b>tira a recompra do "
           "contato manual</b> e multiplica o alcance."),
  "significa":("A Galante tem recompra do varejo de construção: <b>item de giro, lojista que compra sozinho e espaço claro para um canal B2B.</b>"),
  "pot_low":"R$ 35 mil","pot_high":"R$ 70 mil","deixa_mes":"R$ 2,9 mil a R$ 5,8 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 250 mil a R$ 500 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Olist (Tiny)","Distribuidora Galante")},

 {"slug":"ribercon","theme":"dark","food":False,"empresa":"Ribercon","contato":"Marcos Rosa","cargo_area":"Atacado e distribuição","local":"Ribeirão Preto, SP",
  "sobre":("A Ribercon é <b>atacadista distribuidora</b> de Ribeirão Preto (SP), atendendo o varejo da região por WhatsApp e redes sociais. "
           "Catálogo de itens de giro com recompra recorrente da carteira."),
  "sobre_fonte":"Fontes: site ribercon.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Varejo (atacado e distribuição)","como_vende":"WhatsApp e redes sociais","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"6 a 20 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 500 mil a R$ 1 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Ribercon atua no <b>atacado e distribuição</b> para o varejo &mdash; carteira que recompra item de giro.",
   "A venda roda por <b>WhatsApp e redes</b>, com 6 a 20 vendedores &mdash; e a dor é <b>carteira de clientes parada</b>.",
   "Não há loja virtual. Fora do contato, a recompra esfria."],
  "pushpull":("A demanda é <b>puxada</b>: o varejo recompra item de giro &mdash; sabe o que precisa. Carteira parada quase sempre é <b>carteira "
              "sem canal de recompra</b>: um portal B2B reativa essa recompra sem depender da conversa no WhatsApp."),
  "conta":("Recompra por WhatsApp/redes com vários vendedores vira bagunça e a carteira esfria. Um portal B2B <b>reativa a carteira e organiza a "
           "entrada do pedido</b>, liberando o time para venda ativa."),
  "significa":("A Ribercon tem recompra de atacado: <b>item de giro, carteira ampla e uma dor direta de carteira parada esperando um canal.</b>"),
  "pot_low":"R$ 70 mil","pot_high":"R$ 140 mil","deixa_mes":"R$ 5,8 mil a R$ 11,7 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 500 mil a R$ 1 milhão ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Ribercon")},

 {"slug":"morapet","theme":"light","food":False,"empresa":"Morapet","contato":"Equipe Morapet","cargo_area":"Indústria de produtos pet (direto da fábrica)","local":"Brasil",
  "sobre":("A Morapet é <b>fabricante de produtos pet</b> (linha Minha Casa Pets), vendendo direto da fábrica por marketplaces para <b>pet "
           "shops</b>. Produto de giro com recompra recorrente do varejo pet."),
  "sobre_fonte":"Fontes: site minhacasapets.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Pet shops","como_vende":"Marketplace","loja_virtual":"Possui","erp":"Bling",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 500 mil a R$ 1 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Morapet <b>fabrica produtos pet</b> e vende direto da fábrica para pet shops &mdash; produto de giro de recompra recorrente.",
   "A venda depende de <b>marketplaces</b> (com comissão), com 1 pessoa &mdash; e a dor é <b>escalar sem contratar mais gente</b>.",
   "Tem loja virtual, mas falta um canal B2B próprio para a recompra do pet shop."],
  "pushpull":("A demanda é <b>puxada</b>: o pet shop recompra o mesmo produto &mdash; sabe o que vende. Você nos disse que o cliente <b>compraria "
              "sozinho</b>; um canal B2B próprio digitaliza a recompra <b>sem a comissão do marketplace</b> e escala sem contratar."),
  "conta":("Vender só por marketplace é comissão na recompra e sem relação direta. Um portal B2B próprio <b>traz a recompra para casa</b>, melhora "
           "a margem da fábrica e escala a operação enxuta."),
  "significa":("A Morapet tem fabricação própria e recompra pet: <b>produto de giro, cliente que compra sozinho e dependência de marketplace que um canal B2B resolve.</b>"),
  "pot_low":"R$ 70 mil","pot_high":"R$ 140 mil","deixa_mes":"R$ 5,8 mil a R$ 11,7 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 500 mil a R$ 1 milhão ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","Morapet")},

 {"slug":"uni-piscinas","theme":"light","food":False,"empresa":"Uni Piscinas","contato":"Donizete Rossini","cargo_area":"Distribuição de produtos para piscinas","local":"Brasil",
  "sobre":("A Uni Piscinas (Gold Piscinas) é <b>distribuidora de produtos para piscinas</b>, atendendo <b>lojas de piscina</b> por telefone. "
           "Catálogo de equipamentos, acessórios e químicos de recompra recorrente do varejo especializado."),
  "sobre_fonte":"Fontes: site goldpiscinas.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Lojas de piscina","como_vende":"Telefone","loja_virtual":"Não possui","erp":"Omie",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Ainda não sabe",
  "encontramos":[
   "A Uni Piscinas distribui <b>equipamentos, acessórios e químicos de piscina</b> para lojas do setor &mdash; recompra recorrente, com sazonalidade forte no verão.",
   "A venda roda por <b>telefone</b> &mdash; e a dor é <b>perder vendas pela demora no atendimento</b>.",
   "Não há loja virtual. Na alta temporada, a demora no atendimento vira pedido perdido."],
  "pushpull":("A demanda é <b>puxada</b>: a loja de piscina recompra produto de giro &mdash; sabe o que vende. <b>Perder venda pela demora</b> é o "
              "sinal de que o cliente quer comprar e a ligação não dá conta &mdash; um portal B2B 24/7 captura essa venda, ainda mais na alta temporada."),
  "conta":("Produto de piscina tem pico sazonal &mdash; cada demora no telefone na temporada é pedido que vai pro concorrente. Um portal B2B "
           "<b>captura a recompra a qualquer hora</b> e tira o gargalo do atendimento."),
  "significa":("A Uni Piscinas tem recompra sazonal e dor clara: <b>produto de giro, pico no verão e venda perdida por demora no atendimento.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Omie","Uni Piscinas")},

 {"slug":"petronius","theme":"dark","food":True,"empresa":"Petronius","contato":"Rogério Ferreira Lima","cargo_area":"Indústria e distribuição de sucos e bebidas","local":"Brasil",
  "sobre":("A Petronius atua na <b>produção e distribuição de sucos e bebidas</b> para consumo, com venda externa e operação de porte (mais de "
           "150 pessoas). Produto de giro do food service e varejo, com recompra recorrente."),
  "sobre_fonte":"Fontes: site petroniu.tec.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Varejo e food service (sucos e bebidas)","como_vende":"Venda externa","loja_virtual":"Não possui","erp":"Sankhya",
  "vendedores":"6 a 20 internos","time_total":"+151 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Petronius produz e distribui <b>sucos e bebidas</b> &mdash; produto de giro com recompra recorrente do varejo e do food service.",
   "A venda é <b>externa</b>, com 6 a 20 vendedores &mdash; e a dor é <b>dependência de poucos clientes grandes</b>.",
   "Não há canal digital de pedido: atender muitos pontos menores é caro hoje."],
  "pushpull":("A demanda é <b>puxada</b>: o ponto de venda recompra suco/bebida de giro &mdash; produto que vende sempre. O ponto-chave é a "
              "<b>concentração</b>: depender de poucos grandes é risco. Um portal B2B torna viável atender <b>muitos pontos menores com baixo custo</b>, diluindo a dependência."),
  "conta":("Atender o pequeno ponto via vendedor externo custa caro &mdash; por isso a base se concentra. Um portal B2B <b>viabiliza a cauda "
           "longa</b> de bares, mercados e lanchonetes, diversificando a carteira da operação."),
  "significa":("A Petronius tem produto de giro, mas concentração de risco: <b>um canal B2B diversifica a carteira atendendo os pequenos com eficiência.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":sankhya("Petronius")},

 {"slug":"fabiano-junior","theme":"light","food":False,"empresa":"Fabiano Junior Distribuidora","contato":"Lucas Souza","cargo_area":"Distribuição de produtos pet","local":"Joinville, SC",
  "sobre":("A Fabiano Junior Distribuidora é <b>distribuidora atacadista de produtos pet</b> de Joinville (SC), atendendo <b>pet shops</b> com "
           "venda porta a porta. Operação de porte (faixa de R$ 50 a 500 milhões/ano) com recompra recorrente e de alto giro."),
  "sobre_fonte":"Fontes: site fabianojunior.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Pet shops","como_vende":"Vendedor porta a porta","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"51 a 150 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Fabiano Junior distribui <b>produtos pet</b> para pet shops &mdash; recompra semanal e de alto giro do varejo pet.",
   "A venda é <b>porta a porta</b> &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Não há loja virtual. Crescer hoje significa mais vendedor em rota."],
  "pushpull":("A demanda é fortemente <b>puxada</b>: pet shop recompra ração e itens de giro &mdash; produto que não pode faltar. Você nos disse "
              "que o cliente <b>compraria sozinho</b>; um portal B2B digitaliza a recompra previsível e <b>escala sem contratar</b>."),
  "conta":("Reposição porta a porta tem teto no time &mdash; e a recompra é repetida e previsível. Um portal B2B <b>tira a recompra da rota</b> e "
           "transforma os vendedores em venda ativa, num porte de R$ 50 a 500 milhões."),
  "significa":("A Fabiano Junior tem porte e recompra pet: <b>alto giro, cliente que compra sozinho e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Fabiano Junior")},

 {"slug":"biunessa","theme":"dark","food":True,"empresa":"Biunessa Distribuidora","contato":"Ronie Biunessa","cargo_area":"Distribuição para supermercados","local":"Brasil",
  "sobre":("A Biunessa Distribuidora abastece <b>supermercados</b>, com venda presencial e WhatsApp. Catálogo de itens de giro do varejo "
           "alimentar, com recompra recorrente."),
  "sobre_fonte":"Fonte: respostas do diagnóstico comercial Zydon.",
  "vende_para":"Supermercados","como_vende":"Presencial e WhatsApp","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Biunessa abastece <b>supermercados</b> com itens de giro &mdash; recompra recorrente do varejo alimentar.",
   "A venda é <b>presencial e WhatsApp</b> &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Não há loja virtual. Crescer hoje significa mais gente atendendo."],
  "pushpull":("A demanda é <b>puxada</b>: supermercado recompra item de giro toda semana &mdash; sabe o que precisa. Um portal B2B deixa o cliente "
              "montar o pedido sozinho e <b>escala as vendas sem contratar</b>, exatamente a dor declarada."),
  "conta":("Reposição de supermercado é repetição &mdash; depender de presencial/WhatsApp põe teto na equipe. Um portal B2B <b>tira a recompra do "
           "atendimento manual</b> e multiplica quantos clientes a Biunessa atende."),
  "significa":("A Biunessa tem recompra do varejo alimentar: <b>item de giro, supermercado que recompra e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Biunessa")},
]
NICE={l["slug"]:l["empresa"] for l in LEADS}
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page()
    for l in LEADS:
        html=gen.build_html(l); hp=os.path.join(OUT,f"{l['slug']}.html"); open(hp,"w",encoding="utf-8").write(html)
        pg.goto("file://"+hp,wait_until="networkidle")
        out=os.path.join(DEST,f"{NICE[l['slug']]} - Potencial de Digitalização B2B.pdf")
        pg.pdf(path=out,width="210mm",height="297mm",print_background=True,margin={"top":"0","bottom":"0","left":"0","right":"0"})
        print("PDF:",os.path.basename(out))
    b.close()
