# -*- coding: utf-8 -*-
import os
from playwright.sync_api import sync_playwright
import gen
OUT=os.path.dirname(os.path.abspath(__file__)); DEST=os.path.join(OUT,"Potencial Digitalização B2B - MQLs")
def native(erp,emp): return (f"A {emp} roda no <b>{erp}</b> &mdash; e a Zydon tem <b>integração nativa via API com o {erp}</b>. "
        "Catálogo, preço, estoque e pedido sincronizados em tempo real, sem desenvolvimento e sem retrabalho.")
GEN=("A Zydon integra <b>nativamente via API com Bling, Olist, Omie e Sankhya</b> &mdash; e conecta outros ERPs sob consulta. "
     "Seja qual for o sistema da {emp}, pedido, estoque e tabela passam a conversar em tempo real com o portal.")
def sob(erp,emp): return (f"A {emp} roda no <b>{erp}</b> &mdash; e a integração com o {erp} é avaliada <b>sob consulta</b>. A Zydon conecta "
        "o portal ao ERP para sincronizar estoque, tabela de preço e pedidos, com o escopo validado caso a caso pelo time técnico.")
NAT=("Nativa via API","20 a 30 dias","Zero. Sem projeto de TI"); SOB=("Sob consulta","Sob avaliação","Escopo caso a caso")

LEADS=[
 {"slug":"carol-beauty","theme":"light","food":False,"empresa":"Carol Beauty Cosméticos","contato":"Karin Kapuscinski","cargo_area":"Distribuição de cosméticos","local":"Brasil",
  "sobre":("A Carol Beauty Cosméticos é <b>distribuidora de cosméticos</b>, atendendo <b>farmácias, supermercados e lojas de cosméticos</b> por "
           "RCA externo. Opera com loja virtual e catálogo de itens de giro do varejo de beleza, com recompra recorrente."),
  "sobre_fonte":"Fontes: site carolbeauty.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Farmácias, supermercados e lojas de cosméticos","como_vende":"RCA externo","loja_virtual":"Possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"21 a 100 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Carol Beauty distribui <b>cosméticos</b> para farmácias, supermercados e lojas &mdash; itens de giro de recompra frequente do varejo de beleza.",
   "A venda roda no <b>RCA externo</b> &mdash; e a dor declarada é <b>carteira de clientes parada</b>.",
   "Tem loja virtual, mas a recompra do lojista (B2B) ainda depende da rota do representante."],
  "pushpull":("A demanda é <b>puxada</b>: o varejo recompra cosmético de giro &mdash; sabe o que vende. Carteira parada quase sempre é <b>carteira "
              "sem canal de recompra</b>: você nos disse que o cliente <b>compraria sozinho</b>, e um portal B2B reativa essa recompra sem depender da visita."),
  "conta":("Quando a recompra depende da rota do RCA, o teto é a agenda dele &mdash; e fora da rota a carteira esfria. Um catálogo B2B na mão do "
           "lojista <b>reativa a carteira parada</b> e libera o representante para abrir conta nova."),
  "significa":("A Carol Beauty tem recompra do varejo de beleza: <b>item de giro, cliente que compra sozinho e uma carteira parada esperando um canal de recompra.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Carol Beauty")},

 {"slug":"print","theme":"dark","food":False,"empresa":"Print","contato":"Max Stewers","cargo_area":"Gráfica e produtos de impressão","local":"São Paulo, SP",
  "sobre":("A Print é uma <b>gráfica / fornecedora de produtos de impressão</b>, vendendo por e-commerce e atendimento para empresas e cliente "
           "final. Catálogo com itens de recompra recorrente de quem imprime com frequência."),
  "sobre_fonte":"Fontes: site print-sp.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Empresas e cliente final (impressão)","como_vende":"E-commerce","loja_virtual":"Possui","erp":"Olist (Tiny)",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Print fornece <b>produtos de impressão</b> por e-commerce e atendimento &mdash; recompra recorrente de empresas que imprimem sempre.",
   "Mesmo com e-commerce, a dor é <b>vendedor gasta tempo só tirando pedido</b> &mdash; a recompra previsível ainda ocupa o time.",
   "Falta um canal B2B com tabela e histórico do cliente recorrente."],
  "pushpull":("A demanda é <b>puxada</b>: quem imprime recompra o mesmo material &mdash; sabe o que quer. Com <b>vendedor só tirando pedido</b> e "
              "você dizendo que o cliente <b>compraria sozinho</b>, um portal B2B com recompra rápida tira o pedido repetido do vendedor e libera o time para conta nova."),
  "conta":("Material de impressão é recompra repetida &mdash; ocupar o vendedor com isso é desperdício. Um portal com pedido recorrente "
           "<b>digitaliza a recompra</b> e deixa o time para o que precisa de orientação."),
  "significa":("A Print já vende online e tem recompra: <b>cliente que repete o pedido, compra sozinho e uma dor clara de vendedor preso em tirar pedido.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Olist (Tiny)","Print")},

 {"slug":"ebplastic","theme":"light","food":False,"empresa":"Ebplastic","contato":"Eduardo Tafner","cargo_area":"Indústria de produtos plásticos","local":"Brasil",
  "sobre":("A Ebplastic é <b>fabricante de produtos plásticos</b> para <b>pequenas indústrias</b>, com venda direta. Componentes e itens "
           "plásticos de uso recorrente na produção do cliente."),
  "sobre_fonte":"Fontes: site ebplastic.com e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Pequenas indústrias","como_vende":"WhatsApp e venda direta","loja_virtual":"Não possui","erp":"Omie",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 500 mil a R$ 1 mi","compra_sozinho":"Ainda não sabe",
  "encontramos":[
   "A Ebplastic fabrica <b>produtos plásticos</b> para pequenas indústrias &mdash; insumo/componente de uso recorrente na produção.",
   "A venda é <b>direta/WhatsApp</b>, com 1 pessoa &mdash; e a dor é <b>carteira de clientes parada</b>.",
   "Não há loja virtual. Fora do contato, a recompra da indústria esfria."],
  "pushpull":("A demanda é <b>puxada</b>: a pequena indústria repõe o mesmo componente conforme produz &mdash; compra previsível. Carteira parada "
              "é <b>carteira sem canal de recompra</b>: um portal B2B reativa essa reposição e tira a recompra do contato manual."),
  "conta":("Componente de produção é recompra repetida &mdash; depender do WhatsApp com 1 pessoa é o gargalo. Um portal B2B <b>reativa a carteira</b> "
           "e libera a operação enxuta para crescer."),
  "significa":("A Ebplastic tem recompra industrial: <b>componente de produção, cliente que repõe e uma carteira parada esperando um canal B2B.</b>"),
  "pot_low":"R$ 70 mil","pot_high":"R$ 140 mil","deixa_mes":"R$ 5,8 mil a R$ 11,7 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 500 mil a R$ 1 milhão ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Omie","Ebplastic")},

 {"slug":"ranalle","theme":"dark","food":False,"empresa":"Ranalle","contato":"Thiago Ranalle","cargo_area":"Indústria e distribuição de autopeças","local":"São Paulo, SP",
  "sobre":("A Ranalle é <b>fabricante e distribuidora de autopeças</b> (polias, tensionadores, bombas d'água e kits de distribuição), fundada "
           "em <b>1993</b>, pioneira na nacionalização de polias e tensionadores, com <b>ISO 9001</b> e presença em 7+ países da América Latina. "
           "Atende <b>distribuidoras e autopeças</b>."),
  "sobre_fonte":"Fontes: site ranalle.com.br, Expo Peças e respostas do diagnóstico Zydon.",
  "vende_para":"Distribuidoras e autopeças","como_vende":"Venda passiva","loja_virtual":"Não possui","erp":"TOTVS",
  "vendedores":"1 interno","time_total":"51 a 150 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Não sabe dizer",
  "encontramos":[
   "A Ranalle fabrica e distribui <b>autopeças</b> (polias, tensionadores, kits) para distribuidoras e autopeças &mdash; compra <b>por código</b>, técnica e recorrente.",
   "A venda é <b>passiva</b> &mdash; e a dor declarada é <b>dependência de poucos clientes grandes</b>.",
   "Não há canal digital de pedido: atender muitos clientes menores é caro hoje."],
  "pushpull":("A demanda é <b>puxada e por código</b>: a autopeça/distribuidora sabe a referência exata e recompra. O ponto-chave é a "
              "<b>concentração</b>: depender de poucos grandes é risco. Um portal B2B torna viável atender <b>muitos clientes menores com baixo custo</b> "
              "&mdash; diluindo a dependência e aumentando o número de pedidos sem inflar a equipe."),
  "conta":("Atender o pequeno por venda passiva/representante custa caro &mdash; por isso a base se concentra. Um portal por código <b>viabiliza a "
           "cauda longa</b> de autopeças e distribuidoras menores, diversificando a carteira de uma indústria de R$ 50 a 500 milhões."),
  "significa":("A Ranalle tem marca forte e produto por código, mas concentração de risco: <b>um canal B2B diversifica a carteira atendendo os pequenos com eficiência.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":SOB[0],"erp_golive":SOB[1],"erp_dev":SOB[2],"erp_line":sob("TOTVS","Ranalle")},

 {"slug":"nsb","theme":"light","food":False,"empresa":"NSB Distribuidora","contato":"Ricardo Maier","cargo_area":"Distribuição de ferragens, construção e elétrica","local":"Brasil",
  "sobre":("A NSB Distribuidora é <b>distribuidora de ferragens, materiais de construção e materiais elétricos</b>, atendendo <b>lojas do setor e "
           "instaladores</b> por televendas. Catálogo técnico amplo, com recompra por código do varejo especializado."),
  "sobre_fonte":"Fontes: site nsbdistribuidora.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Ferragens, lojas de construção, materiais elétricos e instaladores","como_vende":"Televendas","loja_virtual":"Não possui","erp":"TOTVS",
  "vendedores":"6 a 20 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Poucos compram sozinhos hoje",
  "encontramos":[
   "A NSB distribui <b>ferragens, material de construção e elétrico</b> para lojas e instaladores &mdash; compra <b>por código</b>, técnica e recorrente.",
   "A venda roda por <b>televendas</b> com 6 a 20 vendedores &mdash; e a dor é <b>vendedor gasta tempo só tirando pedido</b>.",
   "Não há loja virtual. Cada reposição por código passa pela ligação."],
  "pushpull":("A demanda é <b>puxada e por código</b>: a loja/instalador sabe a referência que precisa e recompra. Com <b>vendedor só tirando "
              "pedido</b>, é a recompra previsível que um portal digitaliza primeiro: o cliente fecha por código sozinho e o televendas vira venda ativa."),
  "conta":("Material elétrico/ferragem é compra por código e repetida &mdash; ocupar 6 a 20 vendedores com isso é caro. Um portal por código "
           "<b>libera o time</b> e captura a recompra 24/7."),
  "significa":("A NSB tem o caso forte de digitalização: <b>compra técnica por código, time grande tirando pedido e recompra recorrente esperando um portal.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":SOB[0],"erp_golive":SOB[1],"erp_dev":SOB[2],"erp_line":sob("TOTVS","NSB Distribuidora")},

 {"slug":"ewwa","theme":"dark","food":False,"empresa":"Ewwá Brasil","contato":"Equipe Ewwá Brasil","cargo_area":"Cosméticos — varejo e atacado","local":"Brasil",
  "sobre":("A Ewwá Brasil atua no <b>varejo e atacado de cosméticos</b>, com loja física e online. Catálogo de itens de giro do varejo de "
           "beleza, com recompra recorrente."),
  "sobre_fonte":"Fontes: site ewwa.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Varejo de cosméticos e revendas","como_vende":"Loja física","loja_virtual":"Possui","erp":"TOTVS",
  "vendedores":"6 a 20 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 500 mil a R$ 1 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Ewwá trabalha <b>cosméticos</b> no varejo e atacado &mdash; itens de giro de recompra frequente.",
   "A venda passa pela <b>loja física</b>, com 6 a 20 vendedores &mdash; e há espaço claro para um canal B2B de recompra.",
   "Tem loja virtual (B2C), mas falta tabela e condição próprias para a revenda."],
  "pushpull":("A demanda é <b>puxada</b>: a revenda recompra cosmético de giro &mdash; sabe o que vende. Você nos disse que o cliente <b>compraria "
              "sozinho</b>: um portal B2B com tabela de atacado digitaliza a recompra e separa o atacado do varejo."),
  "conta":("Atender revenda pela loja física mistura preço e ocupa o time. Um canal B2B com tabela do revendedor <b>organiza o atacado e sobe o "
           "ticket</b>, sem tirar foco do varejo."),
  "significa":("A Ewwá tem recompra de beleza e canais ativos: <b>item de giro, cliente que compra sozinho e a chance de estruturar o atacado num portal B2B.</b>"),
  "pot_low":"R$ 70 mil","pot_high":"R$ 140 mil","deixa_mes":"R$ 5,8 mil a R$ 11,7 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 500 mil a R$ 1 milhão ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":SOB[0],"erp_golive":SOB[1],"erp_dev":SOB[2],"erp_line":sob("TOTVS","Ewwá Brasil")},

 {"slug":"lamy","theme":"light","food":False,"empresa":"Lamy Química","contato":"Ricardo Laneza","cargo_area":"Produtos de limpeza e químicos para food service","local":"Brasil",
  "sobre":("A Lamy Química (Lapalm) fornece <b>produtos de limpeza e químicos</b> para <b>distribuidores, restaurantes e pizzarias</b>. Insumo de "
           "uso contínuo do food service, com recompra recorrente."),
  "sobre_fonte":"Fontes: site lamyquimica.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Distribuidores, restaurantes e pizzarias","como_vende":"WhatsApp","loja_virtual":"Não possui","erp":"Olist (Tiny)",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Lamy Química fornece <b>produtos de limpeza e químicos</b> para distribuidores, restaurantes e pizzarias &mdash; insumo de uso contínuo, com recompra recorrente.",
   "A venda roda por <b>WhatsApp</b> &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Não há loja virtual. Cada reposição é remontada à mão, com retrabalho."],
  "pushpull":("A demanda é <b>puxada</b>: restaurante e distribuidor recompram produto de limpeza de giro &mdash; sabem o que usam. Pedido "
              "desorganizado é onde a venda se perde: um portal B2B <b>organiza a entrada do pedido</b> e tira a recompra do WhatsApp."),
  "conta":("Produto de limpeza é recompra repetida &mdash; receber por WhatsApp/telefone/planilha vira retrabalho e erro. Um canal B2B "
           "<b>padroniza a recompra e dá visão</b>, num faturamento de R$ 10 a 50 milhões que justifica."),
  "significa":("A Lamy tem recompra do food service: <b>insumo de uso contínuo, cliente que repõe sempre e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Olist (Tiny)","Lamy Química")},

 {"slug":"tmb","theme":"dark","food":False,"empresa":"Top Marcas Brasil","contato":"Magnus Dierings","cargo_area":"Distribuição para salões e barbearias","local":"Florianópolis, SC",
  "sobre":("A Top Marcas Brasil (TMB) é <b>distribuidora de produtos para salões e barbearias</b>, de Florianópolis (SC). Catálogo de produtos "
           "profissionais de beleza, com recompra recorrente do varejo profissional."),
  "sobre_fonte":"Fontes: site topmarcasbrasil.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Salões e barbearias","como_vende":"WhatsApp","loja_virtual":"Possui","erp":"Bling",
  "vendedores":"6 a 20 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A TMB distribui <b>produtos profissionais para salões e barbearias</b> &mdash; itens de giro que o profissional recompra sempre.",
   "A venda roda por <b>WhatsApp</b>, com 6 a 20 vendedores &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Tem loja virtual, mas a recompra do salão/barbearia ainda trava no WhatsApp."],
  "pushpull":("A demanda é <b>puxada</b>: salão e barbearia recompram o mesmo produto profissional &mdash; sabem o que usam. Pedido desorganizado "
              "no WhatsApp é venda perdida e retrabalho: um portal B2B <b>organiza a recompra</b> e libera os vendedores para abrir conta nova."),
  "conta":("Reposição de salão é repetida &mdash; receber por WhatsApp/telefone/planilha com vários vendedores vira bagunça. Um canal B2B "
           "<b>padroniza a entrada do pedido</b> e transforma o time em venda ativa."),
  "significa":("A TMB tem recompra do varejo profissional de beleza: <b>item de giro, profissional que repõe sempre e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","Top Marcas Brasil")},
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
