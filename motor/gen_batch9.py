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
 {"slug":"panos","theme":"light","food":False,"empresa":"Ateliê Panos","contato":"Wanessa","cargo_area":"Têxtil para food service (panos, toalhas, uniformes)","local":"Brasil",
  "sobre":("A Ateliê Panos fornece <b>enxoval e têxtil para restaurantes</b> (panos, toalhas e uniformes), trabalhando por <b>contratos</b> de "
           "fornecimento. Produto que <b>desgasta e é reposto</b> com frequência, com loja virtual e recompra recorrente."),
  "sobre_fonte":"Fontes: site ateliepanos.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Restaurantes e food service","como_vende":"Contratos de fornecimento","loja_virtual":"Possui","erp":"Bling",
  "vendedores":"2 a 5 internos","time_total":"51 a 150 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Ateliê Panos fornece <b>têxtil para restaurantes</b> (panos, toalhas, uniformes) &mdash; consumível que desgasta e é reposto sempre.",
   "A venda é por <b>contrato</b> &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Tem loja virtual, mas a reposição recorrente do restaurante ainda passa por canais soltos."],
  "pushpull":("A demanda é <b>puxada</b>: restaurante repõe o têxtil que desgasta &mdash; recompra previsível. Você nos disse que o cliente "
              "<b>compraria sozinho</b>; um portal B2B com a reposição do contrato organiza o pedido que hoje se perde no WhatsApp."),
  "conta":("Reposição de têxtil é repetida &mdash; pedido desorganizado vira retrabalho e ruptura no cliente. Um canal B2B <b>padroniza a "
           "recompra do contrato</b> e dá previsibilidade ao fornecimento."),
  "significa":("A Ateliê Panos tem reposição recorrente sob contrato: <b>consumível que desgasta, cliente que compra sozinho e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","Ateliê Panos")},

 {"slug":"patria-pampa","theme":"dark","food":False,"empresa":"Patria Pampa","contato":"Roque Mello","cargo_area":"Distribuição de artigos gaúchos (nicho tradicionalista)","local":"Brasil",
  "sobre":("A Patria Pampa é <b>distribuidora de artigos gaúchos</b> (segmento super nichado do tradicionalismo), atendendo <b>lojas "
           "especializadas</b> com vendedor externo e interno. Catálogo de itens de giro do nicho, com recompra recorrente."),
  "sobre_fonte":"Fontes: site patriapampa.com e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Lojas de artigos gaúchos (nicho)","como_vende":"Vendedor externo e interno (50/50)","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Ainda não sabe",
  "encontramos":[
   "A Patria Pampa distribui <b>artigos gaúchos</b> para lojas especializadas &mdash; nicho fiel, com recompra recorrente do varejo.",
   "A venda é <b>50% externa / 50% interna</b> &mdash; e a dor é <b>vendedor gasta tempo só tirando pedido</b>.",
   "Não há loja virtual. A recompra da loja especializada depende do vendedor."],
  "pushpull":("A demanda é <b>puxada</b>: a loja de artigos gaúchos recompra os mesmos itens de giro &mdash; nicho fiel que sabe o que quer. Com "
              "<b>vendedor só tirando pedido</b>, um portal B2B digitaliza a recompra previsível e libera o time para abrir conta nova."),
  "conta":("Reposição do nicho é repetida &mdash; ocupar o vendedor com isso é desperdício. Um portal B2B <b>tira a recompra do vendedor</b> e "
           "transforma o time em venda ativa, num nicho com cliente fiel."),
  "significa":("A Patria Pampa tem nicho fiel e recompra: <b>cliente especializado que repõe sempre e uma dor clara de vendedor preso em tirar pedido.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Patria Pampa")},

 {"slug":"agrotech","theme":"light","food":False,"empresa":"Agrotech","contato":"Vagner Pereira","cargo_area":"Distribuição de peças e implementos agrícolas","local":"Carazinho, RS",
  "sobre":("A Agrotech é <b>distribuidora de peças e implementos para máquinas agrícolas</b> de Carazinho (RS), atendendo <b>revendas de "
           "máquinas</b>. Catálogo técnico com recompra por código conforme a manutenção do campo."),
  "sobre_fonte":"Fontes: site agrotech.net.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Revendas de máquinas agrícolas","como_vende":"WhatsApp","loja_virtual":"Não possui","erp":"Omie",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Agrotech distribui <b>peças e implementos agrícolas</b> para revendas de máquinas &mdash; compra <b>por código</b>, técnica e recorrente.",
   "A venda roda por <b>WhatsApp</b> &mdash; e a dor é <b>vendedor gasta tempo só tirando pedido</b>.",
   "Não há loja virtual. Cada reposição por código passa pela conversa."],
  "pushpull":("A demanda é <b>puxada e por código</b>: a revenda sabe a peça que precisa e recompra na manutenção. Com <b>vendedor só tirando "
              "pedido</b> e você dizendo que o cliente <b>compraria sozinho</b>, um portal por código digitaliza a recompra e libera o vendedor."),
  "conta":("Peça agrícola é compra por referência e repetida &mdash; ocupar o WhatsApp com isso limita. Um portal por código <b>captura a "
           "recompra 24/7</b> e tira o vendedor da digitação."),
  "significa":("A Agrotech tem o caso técnico clássico: <b>compra por código, revenda que recompra e cliente que compraria sozinho.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Omie","Agrotech")},

 {"slug":"ortofen","theme":"dark","food":False,"empresa":"ORTOFEN","contato":"Armando Padilha","cargo_area":"Indústria de produtos orto-hospitalares","local":"Brasil",
  "sobre":("A ORTOFEN é <b>indústria de produtos orto-hospitalares</b> há mais de <b>50 anos</b> (algodão, gazes, ataduras, compressas, aventais "
           "e toalhas), com fábrica própria e registro ANVISA. Atende <b>distribuidores, hospitais e clínicas</b>, com representantes em todo o Brasil."),
  "sobre_fonte":"Fontes: site ortofen.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Distribuidores, hospitais e clínicas","como_vende":"Ligação ao cliente","loja_virtual":"Possui","erp":"Sankhya",
  "vendedores":"6 a 20 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A ORTOFEN fabrica <b>consumíveis orto-hospitalares</b> (algodão, gaze, ataduras) para distribuidores, hospitais e clínicas &mdash; compra técnica e <b>de recompra recorrente</b>.",
   "A venda é por <b>ligação</b>, com 6 a 20 vendedores &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Já tem loja virtual, mas a recompra institucional ainda depende do contato."],
  "pushpull":("A demanda é <b>puxada</b>: hospital e distribuidor repõem consumível médico de giro &mdash; produto que não pode faltar e se "
              "compra por especificação. Você nos disse que o cliente <b>compraria sozinho</b>; um portal B2B digitaliza a recompra e <b>escala sem contratar</b>."),
  "conta":("Consumível hospitalar é recompra previsível &mdash; ocupar a ligação com isso limita o crescimento. Um portal B2B <b>tira a recompra "
           "do telefone</b> e libera o time para abrir novas contas institucionais."),
  "significa":("A ORTOFEN tem produto de recompra e marca de 50 anos: <b>consumível institucional, cliente que compra sozinho e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":sankhya("ORTOFEN")},

 {"slug":"nagahama","theme":"light","food":True,"empresa":"Biscoitos Nagahama","contato":"Pedro Nagahama","cargo_area":"Indústria de biscoitos e sequilhos","local":"Brasil",
  "sobre":("A Indústria de Biscoitos Nagahama <b>fabrica biscoitos e sequilhos</b>, vendendo para <b>distribuidores, representantes, "
           "supermercados e comércio em geral</b>. Produto de giro do varejo alimentar, com recompra recorrente."),
  "sobre_fonte":"Fonte: respostas do diagnóstico comercial Zydon.",
  "vende_para":"Distribuidores, representantes, supermercados e comércio","como_vende":"Distribuidores e representantes","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"11 a 25 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Nagahama <b>fabrica biscoitos e sequilhos</b> para distribuidores, representantes e supermercados &mdash; produto de giro do varejo alimentar.",
   "A venda é por <b>distribuidores e representantes</b>, com 1 pessoa &mdash; e a dor é <b>dependência de poucos clientes grandes</b>.",
   "Não há canal digital de pedido: atender muitos pequenos é caro hoje."],
  "pushpull":("A demanda é <b>puxada</b>: supermercado e comércio recompram biscoito de giro &mdash; produto que vende sempre. O ponto-chave é a "
              "<b>concentração</b>: depender de poucos grandes é risco. Um portal B2B torna viável atender <b>muitos pequenos com baixo custo</b>, "
              "diluindo a dependência e aumentando o número de pedidos."),
  "conta":("Atender o pequeno comércio via representante custa caro &mdash; por isso a base se concentra. Um portal B2B <b>viabiliza a cauda "
           "longa</b> de mercados e comércios, diversificando a carteira da fábrica."),
  "significa":("A Nagahama tem produto de giro, mas concentração de risco: <b>um canal B2B diversifica a carteira atendendo os pequenos com eficiência.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Nagahama")},

 {"slug":"dec-eldorado","theme":"dark","food":True,"empresa":"Dec Eldorado","contato":"Juscelino Junior","cargo_area":"Atacado distribuidor (alimentos e varejo)","local":"Minas Gerais",
  "sobre":("A Dec Eldorado é <b>atacadista distribuidora</b> que abastece <b>supermercados, farmácias, padarias e restaurantes</b>, com venda "
           "presencial e porte robusto (faixa de R$ 50 a 500 milhões/ano). Catálogo amplo de itens de giro e recompra recorrente."),
  "sobre_fonte":"Fontes: site deceldorado.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Supermercados, farmácias, padarias e restaurantes","como_vende":"Venda presencial","loja_virtual":"Não possui","erp":"Sankhya",
  "vendedores":"1 interno","time_total":"51 a 150 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Talvez",
  "encontramos":[
   "A Dec Eldorado abastece <b>supermercados, farmácias, padarias e restaurantes</b> &mdash; recompra recorrente e de alto volume do varejo.",
   "A venda é <b>presencial</b> &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Não há loja virtual. Crescer hoje significa mais vendedor em rota."],
  "pushpull":("A demanda é <b>puxada</b>: o varejo recompra item de giro &mdash; sabe o que precisa toda semana. Quando a recompra é tão "
              "previsível, <b>digitalizar a maior parte dos pedidos é natural</b>: o cliente monta o pedido sozinho e o vendedor escala sem contratar."),
  "conta":("Reposição de varejo é repetição &mdash; depender do presencial põe teto no crescimento. Um portal de recompra <b>escala as vendas sem "
           "inflar a folha</b>, num porte de R$ 50 a 500 milhões que justifica de sobra."),
  "significa":("A Dec Eldorado tem porte e recompra para o B2B digital: <b>varejo que recompra sempre e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":sankhya("Dec Eldorado")},

 {"slug":"esteves","theme":"light","food":False,"empresa":"Esteves","contato":"R. Chiurco","cargo_area":"Distribuição de material de construção","local":"Brasil",
  "sobre":("A Esteves é <b>distribuidora de material de construção</b>, atendendo lojas e obras por televendas. Operação de porte (faixa de R$ 50 "
           "a 500 milhões/ano) com catálogo amplo e recompra recorrente do setor."),
  "sobre_fonte":"Fontes: site esteves.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Lojas e obras (material de construção)","como_vende":"Telefone","loja_virtual":"Não possui","erp":"Omie",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Esteves distribui <b>material de construção</b> para lojas e obras &mdash; recompra recorrente conforme o ritmo das construções.",
   "A venda roda por <b>telefone</b> &mdash; e a dor é <b>carteira de clientes parada</b>.",
   "Não há loja virtual. Fora da ligação, a recompra esfria."],
  "pushpull":("A demanda é <b>puxada</b>: loja e obra recompram material de giro &mdash; sabem o que precisam. Carteira parada quase sempre é "
              "<b>carteira sem canal de recompra</b>: um portal B2B reativa essa recompra sem depender do telefone."),
  "conta":("Quando a recompra depende da ligação, o teto é o time &mdash; e a carteira esfria. Um portal B2B <b>reativa a carteira parada</b> e "
           "captura a recompra 24/7, num porte de R$ 50 a 500 milhões."),
  "significa":("A Esteves tem porte e recompra do setor de construção: <b>material de giro, cliente que recompra e uma carteira parada esperando um canal.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Omie","Esteves")},

 {"slug":"rmg8","theme":"dark","food":False,"empresa":"RMG8 Fit","contato":"Rafael Magid","cargo_area":"Equipamentos e acessórios fitness","local":"Brasil",
  "sobre":("A RMG8 Fit fornece <b>equipamentos e acessórios fitness</b> para <b>varejo, condomínios e academias</b>, vendendo por marketplaces e "
           "loja própria. Produto de recompra de quem mantém espaços de treino."),
  "sobre_fonte":"Fontes: site rmg8fit.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Varejo, condomínios e academias","como_vende":"Marketplace","loja_virtual":"Possui","erp":"Olist (Tiny)",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 250 mil a R$ 500 mil","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A RMG8 Fit fornece <b>equipamentos e acessórios fitness</b> para academias, condomínios e varejo &mdash; recompra de quem mantém espaços de treino.",
   "A venda depende de <b>marketplaces</b> &mdash; com comissão &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Tem loja virtual, mas falta um canal B2B próprio para a recompra de academias e condomínios."],
  "pushpull":("A demanda é <b>puxada</b>: academia e condomínio repõem equipamento e acessório &mdash; sabem o que precisam. Você nos disse que o "
              "cliente <b>compraria sozinho</b>; um canal B2B próprio organiza o pedido e digitaliza a recompra <b>sem a comissão do marketplace</b>."),
  "conta":("Pedido espalhado entre marketplace e WhatsApp é comissão e retrabalho. Um portal B2B próprio <b>traz a recompra para casa</b>, organiza "
           "o pedido e melhora a margem da operação enxuta."),
  "significa":("A RMG8 Fit tem recompra de academias e condomínios: <b>produto que se repõe, cliente que compra sozinho e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 35 mil","pot_high":"R$ 70 mil","deixa_mes":"R$ 2,9 mil a R$ 5,8 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 250 mil a R$ 500 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Olist (Tiny)","RMG8 Fit")},
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
