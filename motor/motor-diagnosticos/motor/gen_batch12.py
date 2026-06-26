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
def sob(erp,emp): return (f"A {emp} roda no <b>{erp}</b> &mdash; e a integração com o {erp} é avaliada <b>sob consulta</b>. A Zydon conecta "
        "o portal ao ERP para sincronizar estoque, tabela de preço e pedidos, com o escopo validado caso a caso pelo time técnico.")
NAT=("Nativa via API","20 a 30 dias","Zero. Sem projeto de TI"); SOB=("Sob consulta","Sob avaliação","Escopo caso a caso")

LEADS=[
 {"slug":"retratecc","theme":"dark","food":False,"empresa":"Retratecc Peças","contato":"Rodrigo Vidal","cargo_area":"Distribuição de autopeças","local":"Brasil",
  "sobre":("A Retratecc Peças é <b>distribuidora de autopeças</b>, atendendo o varejo automotivo por televendas. Catálogo técnico com "
           "recompra por código conforme a manutenção dos veículos."),
  "sobre_fonte":"Fonte: respostas do diagnóstico comercial Zydon.",
  "vende_para":"Autopeças e oficinas","como_vende":"Televendas","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"6 a 20 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Retratecc distribui <b>autopeças</b> &mdash; compra <b>por código</b>, técnica e recorrente na manutenção.",
   "A venda roda por <b>televendas</b> &mdash; e a dor declarada é direta: <b>não consigo vender fora do horário comercial</b>.",
   "Não há loja virtual. Tudo que entra fora do expediente fica para o dia seguinte &mdash; ou vai pro concorrente."],
  "pushpull":("A demanda é <b>puxada e por código</b>: a oficina/autopeça sabe a referência que precisa e recompra. A dor é a prova do potencial: "
              "<b>vender fora do horário</b> só é possível com um portal &mdash; o cliente fecha o pedido por código a qualquer hora, sem depender do televendas."),
  "conta":("Cada pedido que chega à noite ou no fim de semana e não é atendido é venda perdida. Um portal por código <b>vende 24/7</b> e captura "
           "exatamente a recompra que hoje escapa fora do expediente."),
  "significa":("A Retratecc tem o caso direto de digitalização: <b>compra por código, recompra recorrente e uma dor explícita de não vender fora do horário comercial.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Retratecc")},

 {"slug":"qc","theme":"light","food":False,"empresa":"QC","contato":"Laura Costa","cargo_area":"Fornecimento industrial B2B","local":"Brasil",
  "sobre":("A QC é <b>fornecedora industrial B2B</b>, atendendo <b>a indústria</b> com representantes técnicos. Catálogo de insumos/componentes "
           "de uso recorrente na produção do cliente, com compra por especificação."),
  "sobre_fonte":"Fonte: respostas do diagnóstico comercial Zydon.",
  "vende_para":"Indústria","como_vende":"B2B com representantes técnicos","loja_virtual":"Não possui","erp":"Sankhya",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A QC fornece <b>insumos/componentes industriais</b> para a indústria &mdash; compra técnica, por especificação e de recompra recorrente.",
   "A venda é <b>B2B com representantes técnicos</b> &mdash; o pedido recorrente ainda passa pelo representante.",
   "Não há canal digital de pedido: a recompra programada depende do contato."],
  "pushpull":("A demanda é <b>puxada</b>: a indústria repõe o insumo conforme a produção &mdash; compra previsível e por especificação. Um portal "
              "B2B digitaliza a recompra programada e libera o representante técnico para o que exige consultoria, sem perder pedido recorrente."),
  "conta":("Insumo de produção é recompra planejada &mdash; passar isso pelo representante a cada ciclo ocupa o time com o previsível. Um portal "
           "B2B <b>automatiza a recompra</b> e dá previsibilidade à fábrica do cliente."),
  "significa":("A QC tem recompra industrial por especificação: <b>insumo de produção, cliente que repõe sempre e um pedido B2B pronto para digitalizar.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":sankhya("QC")},

 {"slug":"retenlins","theme":"dark","food":False,"empresa":"Retenlins","contato":"Luis Carlos Leal","cargo_area":"Soluções industriais de vedação","local":"Brasil",
  "sobre":("A Retenlins &mdash; Soluções Industriais fornece <b>itens de vedação e reposição industrial</b> (retentores, juntas e correlatos) "
           "para <b>indústrias</b>. Catálogo técnico com recompra por código conforme a manutenção das máquinas."),
  "sobre_fonte":"Fontes: site retenlins.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Indústrias","como_vende":"Telefone e e-mail","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"6 a 20 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 500 mil a R$ 1 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Retenlins fornece <b>itens de vedação industrial</b> (retentores, juntas) &mdash; compra <b>por código</b>, técnica e recorrente na manutenção.",
   "A venda roda por <b>telefone e e-mail</b> &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Não há loja virtual. Cada pedido por código é remontado à mão, com risco de erro de referência."],
  "pushpull":("A demanda é <b>puxada e por código</b>: a indústria sabe a peça de vedação que precisa e recompra na manutenção. Pedido "
              "desorganizado por telefone/e-mail multiplica o erro de referência: um portal por código <b>organiza o pedido e elimina o erro</b>."),
  "conta":("Item de vedação é compra por referência exata &mdash; errar o código é máquina parada. Receber por telefone/e-mail/planilha é "
           "retrabalho. Um portal onde o cliente seleciona por código <b>padroniza o pedido e dá rastreabilidade</b>."),
  "significa":("A Retenlins tem o caso técnico clássico: <b>compra por código, indústria que recompra e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 70 mil","pot_high":"R$ 140 mil","deixa_mes":"R$ 5,8 mil a R$ 11,7 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 500 mil a R$ 1 milhão ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Retenlins")},

 {"slug":"fenix-gifts","theme":"light","food":False,"empresa":"Fênix Gifts","contato":"Kamila Soares Queiroz","cargo_area":"Brindes promocionais corporativos","local":"São Paulo, SP",
  "sobre":("A Fênix Gifts fornece <b>brindes promocionais personalizados para empresas</b>, captando por anúncio no Google e carteira de "
           "clientes. Produto de recompra recorrente (campanhas, eventos, datas) do cliente corporativo."),
  "sobre_fonte":"Fontes: site fenixgifts.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Empresas (brindes promocionais)","como_vende":"Google Ads e carteira","loja_virtual":"Não possui","erp":"Olist (Tiny)",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 500 mil a R$ 1 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Fênix Gifts fornece <b>brindes promocionais</b> para empresas &mdash; recompra recorrente em campanhas, eventos e datas comemorativas.",
   "A captação vem de <b>Google Ads e carteira</b> &mdash; e a dor é <b>carteira de clientes parada</b>.",
   "Não há canal B2B de recompra: o cliente corporativo precisa falar com o vendedor para repedir."],
  "pushpull":("A demanda é <b>puxada</b>: a empresa recompra brinde em datas e campanhas &mdash; sabe o que quer e repete. Carteira parada é "
              "<b>carteira sem canal de recompra</b>: um portal B2B com o histórico do cliente reativa o repedido (mesma arte, mesmo produto) sem depender do vendedor."),
  "conta":("Recompra de brinde é repetível (mesma arte, nova campanha) &mdash; depender do vendedor para isso esfria a carteira. Um portal de "
           "recompra <b>reativa o cliente corporativo</b> e libera o time para captar conta nova."),
  "significa":("A Fênix Gifts tem recompra corporativa: <b>brinde que se repete por campanha, cliente que repede e uma carteira parada esperando um canal.</b>"),
  "pot_low":"R$ 70 mil","pot_high":"R$ 140 mil","deixa_mes":"R$ 5,8 mil a R$ 11,7 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 500 mil a R$ 1 milhão ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Olist (Tiny)","Fênix Gifts")},

 {"slug":"vigodent","theme":"dark","food":False,"empresa":"Vigodent","contato":"Claudio Loureiro Nunes","cargo_area":"Indústria de produtos odontológicos","local":"Brasil",
  "sobre":("A Vigodent é <b>indústria de produtos odontológicos</b>, atendendo <b>distribuidores e o canal dental</b> com venda externa. "
           "Consumíveis e materiais de uso recorrente em clínicas, com recompra previsível."),
  "sobre_fonte":"Fontes: site vigodent.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Distribuidores e canal odontológico","como_vende":"Venda externa","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"51 a 150 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Vigodent fabrica <b>produtos odontológicos</b> para distribuidores e o canal dental &mdash; consumível de recompra recorrente em clínicas.",
   "A venda é <b>externa</b> &mdash; e a dor é <b>dependência de poucos clientes grandes</b>.",
   "Não há canal digital: atender muitos distribuidores e clínicas menores é caro hoje."],
  "pushpull":("A demanda é <b>puxada</b>: clínica e distribuidor recompram consumível odonto de giro &mdash; produto que não pode faltar. O "
              "ponto-chave é a <b>concentração</b>: depender de poucos grandes é risco. Um portal B2B torna viável atender <b>muitos clientes "
              "menores com baixo custo</b>, diluindo a dependência."),
  "conta":("Atender o cliente pequeno por venda externa custa caro &mdash; por isso a base se concentra. Um portal B2B <b>viabiliza a cauda "
           "longa</b> de distribuidores e clínicas, diversificando a carteira da indústria."),
  "significa":("A Vigodent tem produto de recompra, mas concentração de risco: <b>um canal B2B diversifica a carteira atendendo os pequenos com eficiência.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Vigodent")},

 {"slug":"royalfix","theme":"light","food":False,"empresa":"Royalfix","contato":"Vera Carletti","cargo_area":"Produtos para funilaria e repintura automotiva","local":"São Paulo, SP",
  "sobre":("A Royalfix fornece <b>produtos para funilaria e repintura automotiva</b> (massas, abrasivos e correlatos), atendendo "
           "<b>funilarias e oficinas</b>. Insumo técnico de uso contínuo, com recompra recorrente do reparador."),
  "sobre_fonte":"Fontes: site Royalfix e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Funilarias e oficinas","como_vende":"Vendedores","loja_virtual":"Não possui","erp":"TOTVS",
  "vendedores":"2 a 5 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Royalfix fornece <b>insumos para funilaria e repintura</b> &mdash; produto técnico de uso contínuo, de recompra recorrente do reparador.",
   "A venda roda por <b>vendedores</b> &mdash; e a dor declarada é direta: <b>não consigo vender fora do horário comercial</b>.",
   "Não há loja virtual. O pedido que surge fora do expediente fica para depois."],
  "pushpull":("A demanda é <b>puxada</b>: a funilaria recompra a mesma massa/abrasivo conforme o serviço &mdash; sabe o que usa. Você nos disse que "
              "o cliente <b>compraria sozinho</b>, e a dor confirma: <b>vender fora do horário</b> só com um portal &mdash; o reparador fecha o pedido a qualquer hora."),
  "conta":("Cada pedido que aparece fora do expediente e não é atendido é recompra que escapa. Um portal B2B <b>vende 24/7</b> e captura a "
           "reposição que hoje fica parada esperando o vendedor."),
  "significa":("A Royalfix tem recompra técnica e dor explícita: <b>insumo de uso contínuo, cliente que compra sozinho e a necessidade de vender fora do horário comercial.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":SOB[0],"erp_golive":SOB[1],"erp_dev":SOB[2],"erp_line":sob("TOTVS","Royalfix")},

 {"slug":"papelaria101","theme":"light","food":False,"empresa":"Papelaria101","contato":"Luciano","cargo_area":"Distribuição de papelaria","local":"Brasil",
  "sobre":("A Papelaria101 é <b>distribuidora de artigos de papelaria</b> para o varejo, captando por WhatsApp e redes sociais. Catálogo de "
           "itens de giro de recompra recorrente."),
  "sobre_fonte":"Fonte: respostas do diagnóstico comercial Zydon.",
  "vende_para":"Varejo de papelaria","como_vende":"WhatsApp e redes sociais","loja_virtual":"Não possui","erp":"Bling",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 250 mil a R$ 500 mil","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Papelaria101 distribui <b>artigos de papelaria</b> para o varejo &mdash; itens de giro de recompra frequente.",
   "A venda vem de <b>WhatsApp e redes</b> &mdash; e a dor é <b>carteira de clientes parada</b>.",
   "Não há loja virtual. Fora da conversa, a recompra esfria."],
  "pushpull":("A demanda é <b>puxada</b>: o varejo recompra papelaria de giro &mdash; sabe o que vende. Carteira parada é <b>carteira sem canal "
              "de recompra</b>: um portal B2B reativa essa recompra sem depender do WhatsApp."),
  "conta":("Recompra por WhatsApp/redes vira bagunça e a carteira esfria. Um portal B2B <b>reativa a carteira e organiza o pedido</b>, "
           "multiplicando o alcance da operação enxuta."),
  "significa":("A Papelaria101 tem recompra do varejo: <b>item de giro, lojista que recompra e uma carteira parada esperando um canal.</b>"),
  "pot_low":"R$ 35 mil","pot_high":"R$ 70 mil","deixa_mes":"R$ 2,9 mil a R$ 5,8 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 250 mil a R$ 500 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","Papelaria101")},

 {"slug":"mibis","theme":"light","food":False,"empresa":"Mibis","contato":"Ismael Vitor Ferreira","cargo_area":"Venda direta via revendedoras","local":"Brasil",
  "sobre":("A Mibis atua na <b>venda direta por revendedoras (porta a porta)</b>, com catálogo de produtos de giro. As revendedoras recompram "
           "para abastecer suas vendas, de forma recorrente."),
  "sobre_fonte":"Fonte: respostas do diagnóstico comercial Zydon.",
  "vende_para":"Revendedoras (porta a porta)","como_vende":"Porta a porta","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"6 a 20 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Mibis vende por <b>revendedoras porta a porta</b> &mdash; a revendedora recompra para repor o que vende, de forma recorrente.",
   "A operação é <b>porta a porta</b> &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Não há canal digital: cada recompra da revendedora passa pela estrutura interna."],
  "pushpull":("A demanda é <b>puxada</b>: a revendedora recompra o produto de giro para abastecer suas vendas &mdash; sabe o que sai. Um <b>portal "
              "B2B para as revendedoras</b> digitaliza a recompra e <b>escala a rede sem contratar</b>, exatamente a dor declarada."),
  "conta":("Atender a recompra de muitas revendedoras pela estrutura interna tem teto. Um portal onde a revendedora monta o pedido sozinha "
           "<b>escala a rede</b> e libera a equipe para recrutar e ativar novas revendedoras."),
  "significa":("A Mibis tem recompra de uma rede de revendedoras: <b>produto de giro, recompra recorrente e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Mibis")},

 {"slug":"vovo-lela","theme":"dark","food":True,"empresa":"Vovó Lela Alimentos","contato":"Alexandre Junqueira","cargo_area":"Produção e distribuição de alimentos","local":"Brasil",
  "sobre":("A Vovó Lela Alimentos produz e distribui <b>alimentos</b> para <b>supermercados, hortifrútis, padarias e restaurantes</b>, com venda "
           "por telefone e loja online. Produto de giro do varejo alimentar, com recompra recorrente."),
  "sobre_fonte":"Fontes: site vovolela.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Supermercados, hortifrútis, padarias e restaurantes","como_vende":"Telefone","loja_virtual":"Possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Vovó Lela distribui <b>alimentos</b> para supermercados, hortifrútis, padarias e restaurantes &mdash; produto de giro, recompra recorrente.",
   "A venda é por <b>telefone</b>, com 1 pessoa &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Já tem loja online, mas o pedido B2B do varejo ainda passa por canais soltos."],
  "pushpull":("A demanda é <b>puxada</b>: o varejo recompra alimento de giro &mdash; sabe o que precisa. Você nos disse que o cliente "
              "<b>compraria sozinho</b>; um portal B2B organiza o pedido que hoje se perde e digitaliza a recompra, sem ocupar a única pessoa da retaguarda."),
  "conta":("Reposição de alimento é repetida e previsível &mdash; receber por telefone/WhatsApp/planilha com 1 pessoa é o gargalo. Um portal B2B "
           "<b>organiza a entrada do pedido e dá visão</b>, liberando a operação para crescer."),
  "significa":("A Vovó Lela tem recompra do varejo alimentar: <b>produto de giro, cliente que compra sozinho e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Vovó Lela")},

 {"slug":"dp-armacoes","theme":"light","food":False,"empresa":"DP Armações","contato":"Douglas Procopio","cargo_area":"Distribuição de armações (óptica)","local":"Brasil",
  "sobre":("A DP Armações distribui <b>armações e óculos</b> para o varejo óptico, com loja física. Produto de giro do setor óptico, com "
           "recompra recorrente das óticas."),
  "sobre_fonte":"Fonte: respostas do diagnóstico comercial Zydon.",
  "vende_para":"Óticas e varejo óptico","como_vende":"Loja física","loja_virtual":"Não possui","erp":"Bling",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"Até R$ 250 mil","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A DP Armações distribui <b>armações e óculos</b> para o varejo óptico &mdash; produto de giro de recompra recorrente das óticas.",
   "A venda passa pela <b>loja física</b> &mdash; e a dor é <b>dependência de poucos clientes grandes</b>.",
   "Não há loja virtual. Atender muitas óticas menores é difícil hoje."],
  "pushpull":("A demanda é <b>puxada</b>: a ótica recompra armação de giro &mdash; repõe o que vende. O ponto-chave é a <b>concentração</b>: "
              "depender de poucos grandes é risco. Um portal B2B torna viável atender <b>muitas óticas menores com baixo custo</b>, diluindo a dependência."),
  "conta":("Atender a ótica pequena pela loja física custa caro &mdash; por isso a base se concentra. Um portal B2B <b>viabiliza a cauda longa</b> "
           "de óticas, diversificando a carteira."),
  "significa":("A DP Armações tem produto de giro, mas concentração de risco: <b>um canal B2B diversifica a carteira atendendo as óticas menores com eficiência.</b>"),
  "pot_low":"R$ 17 mil","pot_high":"R$ 35 mil","deixa_mes":"R$ 1,4 mil a R$ 2,9 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (até R$ 250 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","DP Armações")},
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
