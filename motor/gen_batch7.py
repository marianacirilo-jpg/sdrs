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
 {"slug":"fim-de-obra","theme":"light","food":False,"empresa":"Fim de Obra","contato":"Billy Henrique de Gois","cargo_area":"Produtos para limpeza pós-obra e acabamento","local":"Brasil",
  "sobre":("A Fim de Obra atua com <b>produtos de limpeza pós-obra e acabamento</b>, distribuindo para <b>depósitos, casas de tintas, "
           "supermercados, home centers e lojas de limpeza</b> por meio de representantes. Catálogo de itens de giro com recompra recorrente do varejo de materiais."),
  "sobre_fonte":"Fontes: site fimdeobra.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Depósitos, casas de tintas, home centers, supermercados e lojas de limpeza","como_vende":"Representantes comerciais","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"51 a 150 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Fim de Obra vende <b>produtos de limpeza pós-obra e acabamento</b> para depósitos, casas de tintas, home centers e lojas &mdash; itens de giro de recompra frequente.",
   "A venda é por <b>representantes</b> &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Não há loja virtual. Cada pedido do lojista é remontado à mão, com retrabalho e risco de erro."],
  "pushpull":("A demanda é <b>puxada</b>: depósito e home center recompram item de giro &mdash; sabem o que vendem. Pedido desorganizado é onde a "
              "venda se perde: um portal B2B com catálogo e tabela <b>organiza a entrada do pedido</b> e tira a recompra do WhatsApp, liberando o representante para abrir conta."),
  "conta":("Pedido espalhado em WhatsApp/telefone/planilha vira retrabalho e erro. Um canal B2B único <b>padroniza a recompra e dá visão</b>, "
           "deixando o time para o que precisa de atenção."),
  "significa":("A Fim de Obra tem recompra do varejo de materiais: <b>item de giro, lojista que recompra e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Fim de Obra")},

 {"slug":"tamman","theme":"dark","food":False,"empresa":"Tamman","contato":"Sandro Tamman","cargo_area":"Fornecimento B2B — segurança e mobilidade","local":"Brasil",
  "sobre":("A Tamman é <b>fornecedora B2B para os setores de segurança e mobilidade</b>, atendendo <b>empresas dos dois segmentos</b> com venda "
           "direta. Operação de porte (faixa de R$ 50 a 500 milhões/ano) com recompra recorrente da base corporativa."),
  "sobre_fonte":"Fontes: site tamman.net.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Empresas de segurança e mobilidade","como_vende":"Venda direta","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"6 a 20 internos","time_total":"51 a 150 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Tamman fornece para <b>empresas de segurança e mobilidade</b> &mdash; cliente corporativo que recompra de forma recorrente e por especificação.",
   "A venda é <b>direta</b>, com 6 a 20 vendedores &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Não há canal digital de pedido: a recompra corporativa depende do vendedor."],
  "pushpull":("A demanda é <b>puxada</b>: a empresa-cliente sabe o que precisa e recompra por especificação. Você nos disse que o cliente "
              "<b>compraria sozinho</b>; um portal B2B digitaliza a recompra recorrente e <b>escala as vendas sem inflar o time</b>, exatamente a dor declarada."),
  "conta":("Venda direta corporativa tem teto no tamanho do time. Tirar a recompra previsível do vendedor e colocá-la num portal "
           "<b>libera a equipe para abrir conta nova</b> e crescer sem contratar proporcionalmente, num porte de R$ 50 a 500 milhões."),
  "significa":("A Tamman tem porte e recompra corporativa: <b>cliente B2B que compra sozinho, recompra recorrente e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Tamman")},

 {"slug":"pinheirense","theme":"dark","food":False,"empresa":"Pinheirense","contato":"Angela Morgado","cargo_area":"Distribuição para food service e coletividades","local":"São Paulo, SP",
  "sobre":("A Pinheirense é <b>distribuidora de utensílios, descartáveis e equipamentos para food service</b>, atendendo <b>hotéis, bares, "
           "restaurantes, buffets, hospitais, pousadas e cozinhas industriais</b>. Catálogo amplo com recompra recorrente da coletividade."),
  "sobre_fonte":"Fontes: site pinheirense.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Hotéis, bares, restaurantes, buffets, hospitais e cozinhas industriais","como_vende":"WhatsApp","loja_virtual":"Possui","erp":"TOTVS",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Pinheirense distribui <b>utensílios, descartáveis e equipamentos</b> para hotéis, restaurantes, buffets e cozinhas industriais &mdash; recompra recorrente da coletividade.",
   "A venda roda por <b>WhatsApp</b> &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Tem loja online, mas falta um canal B2B com tabela do cliente para digitalizar a recompra do food service."],
  "pushpull":("A demanda é <b>puxada</b>: restaurante e cozinha industrial recompram descartável e utensílio de giro &mdash; sabem o que precisam. "
              "Um portal B2B com a tabela do cliente <b>digitaliza a recompra que hoje passa pelo WhatsApp</b> e escala o atendimento sem contratar mais gente."),
  "conta":("Reposição de food service é repetida e previsível &mdash; ocupar o WhatsApp com isso limita o crescimento. Um portal B2B <b>tira a "
           "recompra da conversa</b> e libera o time para abrir novos pontos da coletividade."),
  "significa":("A Pinheirense tem recompra de coletividade e catálogo amplo: <b>item de giro, cliente que repõe sempre e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":SOB[0],"erp_golive":SOB[1],"erp_dev":SOB[2],"erp_line":sob("TOTVS","Pinheirense")},

 {"slug":"floresta","theme":"light","food":False,"empresa":"Floresta Materiais e Acabamentos","contato":"Junior Dias","cargo_area":"Materiais de construção, acabamentos e pré-moldados","local":"Brasil",
  "sobre":("A Floresta Materiais e Acabamentos fornece <b>materiais de construção, acabamentos e pré-moldados de concreto</b> (linha Real "
           "Premoldados) para <b>empresas e obras</b>. Produto de recompra conforme o andamento das construções."),
  "sobre_fonte":"Fontes: site realpremoldados.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Construtoras, obras e empresas","como_vende":"WhatsApp","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Floresta fornece <b>materiais de construção, acabamentos e pré-moldados</b> para empresas e obras &mdash; recompra conforme a obra avança.",
   "A venda roda por <b>WhatsApp</b> &mdash; e o pedido do cliente B2B ainda passa por contato manual.",
   "Não há loja virtual. Cada pedido recriado à mão consome o time e atrasa a obra."],
  "pushpull":("A demanda é <b>puxada</b>: construtora e obra recompram material conforme o cronograma &mdash; sabem a especificação e o volume. Um "
              "portal B2B com catálogo e tabela <b>organiza o pedido</b> que hoje passa pelo WhatsApp e dá previsibilidade ao fornecimento da obra."),
  "conta":("Material de obra é recompra programada &mdash; depender do WhatsApp gera erro de quantidade e atraso. Um canal digital <b>padroniza o "
           "pedido e dá rastreabilidade</b>, liberando o time para vender mais."),
  "significa":("A Floresta tem recompra do setor de construção: <b>material e pré-moldado de giro, cliente profissional e um pedido B2B pronto para digitalizar.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Floresta")},

 {"slug":"lam","theme":"dark","food":False,"empresa":"LAM Equipamentos","contato":"Ailton José Pimentel","cargo_area":"Equipamentos e materiais para construção","local":"Brasil",
  "sobre":("A LAM Equipamentos fornece <b>equipamentos e materiais para construção</b> a <b>empreiteiras</b>, com venda física e catálogo "
           "técnico. Recompra recorrente conforme as obras das empreiteiras."),
  "sobre_fonte":"Fontes: site lamequipamentos.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Empreiteiras","como_vende":"Loja física","loja_virtual":"Não possui","erp":"Bling",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"Até R$ 250 mil","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A LAM fornece <b>equipamentos e materiais para construção</b> a empreiteiras &mdash; recompra conforme as obras.",
   "A venda é <b>física</b>, com 1 pessoa &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Não há loja virtual. Cada pedido da empreiteira passa pela operação enxuta."],
  "pushpull":("A demanda é <b>puxada</b>: a empreiteira sabe o equipamento/material que precisa e recompra na obra. Você nos disse que o cliente "
              "<b>compraria sozinho</b>; um portal B2B organiza o pedido que hoje se perde e <b>libera a operação de 1 pessoa</b> para crescer."),
  "conta":("Pedido por WhatsApp/telefone/planilha com 1 pessoa é o gargalo. Um catálogo B2B onde a empreiteira monta o pedido sozinha "
           "<b>organiza a recompra</b> e multiplica o alcance sem contratar."),
  "significa":("A LAM tem recompra de empreiteiras e operação enxuta: <b>cliente que compra sozinho e uma dor direta de pedidos desorganizados &mdash; pronta para um canal B2B simples.</b>"),
  "pot_low":"R$ 17 mil","pot_high":"R$ 35 mil","deixa_mes":"R$ 1,4 mil a R$ 2,9 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (até R$ 250 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","LAM Equipamentos")},

 {"slug":"duleo","theme":"light","food":False,"empresa":"Duleo","contato":"Leonardo Fonseca","cargo_area":"Distribuição de materiais de construção","local":"Brasil",
  "sobre":("A Duleo é <b>distribuidora de materiais de construção</b>, atendendo o varejo e obras. Catálogo de itens de giro do setor de "
           "construção, com recompra recorrente."),
  "sobre_fonte":"Fontes: site duleo.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Lojas e obras (materiais de construção)","como_vende":"WhatsApp e ligação","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Ainda não tem certeza",
  "encontramos":[
   "A Duleo distribui <b>materiais de construção</b> para lojas e obras &mdash; itens de giro de recompra recorrente.",
   "A venda roda por <b>WhatsApp e ligação</b> &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Não há loja virtual. Crescer hoje significa mais gente atendendo no WhatsApp."],
  "pushpull":("A demanda é <b>puxada</b>: loja e obra recompram material de construção de giro &mdash; sabem o que precisam. Um portal B2B deixa o "
              "cliente montar o pedido sozinho e <b>escala as vendas sem contratar</b>, exatamente a dor declarada."),
  "conta":("Atender recompra por WhatsApp/ligação tem teto na equipe. Um catálogo B2B <b>tira a recompra do atendimento manual</b> e multiplica "
           "quantos clientes a Duleo atende sem aumentar o time."),
  "significa":("A Duleo tem recompra do setor de construção: <b>item de giro, cliente que recompra e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Duleo")},

 {"slug":"aracruz","theme":"dark","food":False,"empresa":"Aracruz Mangueiras Hidráulicas","contato":"Gustavo Giore","cargo_area":"Mangueiras e conexões hidráulicas (B2B industrial)","local":"Brasil",
  "sobre":("A Aracruz Mangueiras Hidráulicas (SOS Mangueiras) é <b>fornecedora de mangueiras e conexões hidráulicas</b> para a indústria, com "
           "<b>98% de operação B2B</b>: <b>mineração (mármore e granito), energia, siderurgia e offshore</b>. Forte em atendimento, entrega e fidelização."),
  "sobre_fonte":"Fontes: site hidrauservice.com e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Mineração, energia, siderurgia e offshore (98% B2B)","como_vende":"Ligação e visita","loja_virtual":"Não possui","erp":"Omie",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Clientes hoje muito ligados aos vendedores",
  "encontramos":[
   "A Aracruz fornece <b>mangueiras e conexões hidráulicas</b> para mineração, energia, siderurgia e offshore &mdash; compra técnica <b>por especificação</b> e recorrente na manutenção.",
   "A venda é por <b>ligação e visita</b>, com a dor de <b>escalar sem contratar</b> &mdash; e os clientes hoje são muito ligados a cada vendedor.",
   "Não há loja virtual. O conhecimento da conta vive no vendedor, não num sistema."],
  "pushpull":("A demanda é <b>puxada e técnica</b>: a indústria sabe a mangueira/conexão que precisa (especificação) e recompra na manutenção. "
              "Há um ponto estratégico aqui: como os <b>clientes estão ligados aos vendedores</b>, perder um vendedor é risco. Um portal B2B "
              "<b>transfere a relação para a empresa</b> &mdash; o cliente recompra por especificação no sistema &mdash; reduzindo essa dependência sem abrir mão da entrega e da fidelização que já são fortes."),
  "conta":("Quando a conta vive na cabeça do vendedor, escalar significa contratar &mdash; e a saída de um vendedor leva clientes junto. Um portal "
           "onde o cliente recompra por especificação <b>protege a carteira, registra o histórico e escala</b> sem inflar o time."),
  "significa":("A Aracruz tem recompra técnica e entrega forte: <b>compra por especificação, fidelização real e a chance de tirar a dependência do vendedor com um canal B2B próprio.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Omie","Aracruz Mangueiras")},
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
