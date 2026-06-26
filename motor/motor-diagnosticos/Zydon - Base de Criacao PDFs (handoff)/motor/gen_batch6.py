# -*- coding: utf-8 -*-
import os
from playwright.sync_api import sync_playwright
import gen
OUT=os.path.dirname(os.path.abspath(__file__)); DEST=os.path.join(OUT,"Potencial Digitalização B2B - MQLs")
def native(erp,emp): return (f"A {emp} roda no <b>{erp}</b> &mdash; e a Zydon tem <b>integração nativa via API com o {erp}</b>. "
        "Catálogo, preço, estoque e pedido sincronizados em tempo real, sem desenvolvimento e sem retrabalho.")
def painint(erp,emp): return (f"Você apontou que <b>integrar com o ERP é caro e complicado</b> &mdash; com a Zydon não é. A integração com o "
        f"<b>{erp}</b> é <b>nativa via API</b>, no ar em <b>20 a 30 dias</b> e sem projeto de TI: catálogo, preço, estoque e pedido sincronizados em tempo real.")
GEN=("A Zydon integra <b>nativamente via API com Bling, Olist, Omie e Sankhya</b> &mdash; e conecta outros ERPs sob consulta. "
     "Seja qual for o sistema da {emp}, pedido, estoque e tabela passam a conversar em tempo real com o portal.")
def sob(erp,emp): return (f"A {emp} roda no <b>{erp}</b> &mdash; e a integração com o {erp} é avaliada <b>sob consulta</b>. A Zydon conecta "
        "o portal ao ERP para sincronizar estoque, tabela de preço e pedidos, com o escopo validado caso a caso pelo time técnico.")
NAT=("Nativa via API","20 a 30 dias","Zero. Sem projeto de TI"); SOB=("Sob consulta","Sob avaliação","Escopo caso a caso")

LEADS=[
 {"slug":"ks","theme":"light","food":True,"empresa":"KS Distribuidora","contato":"Elton Jonis","cargo_area":"Distribuição para supermercados","local":"Brasil",
  "sobre":("A Martins Comércio e Serviço de Distribuição (KS Distribuidora) é <b>distribuidora atacadista para supermercados</b>, com catálogo "
           "amplo de itens de giro e operação por <b>representantes comerciais</b>. Porte robusto (faixa de R$ 50 a 500 milhões/ano) no abastecimento do varejo alimentar."),
  "sobre_fonte":"Fontes: site ksdistribuidora.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Supermercados","como_vende":"Representante comercial","loja_virtual":"Não possui","erp":"Omie",
  "vendedores":"21 a 100 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Alguns compram sozinho",
  "encontramos":[
   "A KS Distribuidora abastece <b>supermercados</b> com itens de giro &mdash; recompra recorrente e de alto volume do varejo alimentar.",
   "A venda roda por <b>representante comercial</b> &mdash; e a dor declarada é específica: <b>integrar com o ERP é caro e complicado</b>.",
   "Não há canal digital de pedido: a recompra do supermercado depende do representante."],
  "pushpull":("A demanda é <b>puxada</b>: supermercado recompra item de giro toda semana &mdash; sabe o que precisa. Você nos disse que <b>alguns "
              "clientes já compram sozinhos</b>; um portal B2B digitaliza essa recompra previsível e o representante foca em mix e conta nova."),
  "conta":("Reposição de supermercado é volume e repetição &mdash; e travar isso por causa de integração cara é deixar dinheiro na mesa. Com a "
           "integração resolvida, o portal <b>tira a recompra do representante</b> e escala o atacado."),
  "significa":("A KS tem porte e recompra para o B2B digital: <b>supermercado que recompra sempre, alguns já comprando sozinhos e só a integração no caminho.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":painint("Omie","KS Distribuidora")},

 {"slug":"morro-agudo","theme":"dark","food":False,"empresa":"Morro Agudo Minerais","contato":"Mário Camargos","cargo_area":"Mineração — calcário agrícola e corretivos","local":"Minas Gerais",
  "sobre":("A Morro Agudo Minerais é <b>produtora de calcário agrícola e corretivos de solo</b> (calcário dolomítico rico em cálcio e "
           "magnésio). Atende <b>fazendeiros, distribuidores e revendedores</b> do agronegócio, com produto de recompra por safra e alto volume."),
  "sobre_fonte":"Fontes: site morroagudominerais.com e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Fazendeiros, distribuidores e revendedores (agro)","como_vende":"Revendedores","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"+151 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Morro Agudo produz <b>calcário agrícola e corretivos de solo</b> para fazendeiros, distribuidores e revendedores &mdash; insumo de recompra por safra, em volume.",
   "A venda é <b>por revendedores</b>, com 1 pessoa na frente comercial &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Não há loja virtual. Cada pedido do revendedor é remontado à mão, com risco de erro de volume/frete."],
  "pushpull":("A demanda é <b>puxada</b>: fazendeiro e revenda recompram corretivo conforme a safra &mdash; compra programada e previsível. Você "
              "nos disse que o cliente <b>compraria sozinho</b>; um portal B2B <b>organiza o pedido</b> que hoje se perde no WhatsApp e dá previsibilidade ao planejamento de safra."),
  "conta":("Calcário é volume e recompra sazonal &mdash; pedido por WhatsApp/telefone/planilha vira erro de quantidade e frete, que em commodity de "
           "baixo valor por tonelada corrói a margem. Um canal digital <b>padroniza o pedido e dá rastreabilidade</b>, num porte de R$ 50 a 500 milhões."),
  "significa":("A Morro Agudo tem volume e recompra sazonal do agro: <b>insumo programado, revenda que recompra e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Morro Agudo Minerais")},

 {"slug":"dispace","theme":"light","food":False,"empresa":"Dispace","contato":"Adriana Rosa","cargo_area":"Distribuição de peças agrícolas","local":"Concórdia, SC",
  "sobre":("A Dispace é <b>distribuidora de peças agrícolas</b>, atendendo o agronegócio com catálogo técnico de componentes e reposição. "
           "Opera com loja virtual e atende uma base que recompra peças por código conforme a manutenção das máquinas."),
  "sobre_fonte":"Fontes: site skysollaris.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Revendas e produtores (peças agrícolas)","como_vende":"Telefone","loja_virtual":"Possui","erp":"TOTVS",
  "vendedores":"2 a 5 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Ainda não sabe",
  "encontramos":[
   "A Dispace distribui <b>peças agrícolas</b> &mdash; compra técnica <b>por código</b>, recorrente conforme a manutenção das máquinas no campo.",
   "A venda roda por <b>telefone</b>, com 2 a 5 vendedores &mdash; cada reposição passa pela ligação.",
   "Já tem loja virtual, mas a recompra técnica do cliente B2B ainda depende do atendimento."],
  "pushpull":("A demanda é <b>puxada e por código</b>: o cliente sabe a peça que precisa para a máquina e recompra na manutenção. É o cenário mais "
              "favorável à digitalização: um portal por código deixa o cliente fechar sozinho e tira o telefone do caminho, sem perder a venda técnica que exige orientação."),
  "conta":("Peça agrícola é compra por referência e na urgência da safra &mdash; depender do telefone limita e atrasa. Um portal onde o cliente "
           "pesquisa por código e fecha sozinho <b>captura a recompra 24/7</b> e libera o time."),
  "significa":("A Dispace tem o caso técnico clássico: <b>compra por código, cliente que sabe o que precisa e recompra de manutenção esperando um canal.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":SOB[0],"erp_golive":SOB[1],"erp_dev":SOB[2],"erp_line":sob("TOTVS","Dispace")},

 {"slug":"confort-linens","theme":"dark","food":False,"empresa":"Confort Linens","contato":"Equipe Confort Linens","cargo_area":"Enxoval — cama, mesa e banho","local":"Brasil",
  "sobre":("A Confort Linens atua com <b>enxoval (cama, mesa e banho)</b>, vendendo online e para o varejo. Catálogo de itens de giro do "
           "segmento têxtil-lar, com recompra recorrente."),
  "sobre_fonte":"Fontes: site confortlinens.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Varejo de enxoval e cama/mesa/banho","como_vende":"Online","loja_virtual":"Possui","erp":"Olist (Tiny)",
  "vendedores":"1 interno","time_total":"21 a 100 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Confort Linens trabalha com <b>enxoval (cama, mesa e banho)</b> &mdash; itens de giro do têxtil-lar, com recompra recorrente do varejo.",
   "A venda já é <b>online</b>, mas a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha) na ponta B2B.",
   "Falta um canal B2B com tabela do lojista para separar o atacado do varejo."],
  "pushpull":("A demanda é <b>puxada</b>: o lojista recompra enxoval de giro &mdash; sabe o que vende. Você nos disse que o cliente <b>compraria "
              "sozinho</b>, e o histórico online confirma: um portal B2B organiza o pedido que hoje se espalha em vários canais e digitaliza a recompra com tabela própria de atacado."),
  "conta":("Pedido B2B espalhado em WhatsApp/telefone/planilha vira retrabalho com 1 pessoa na retaguarda. Um canal B2B único <b>organiza a "
           "entrada e dá visão</b>, separando atacado de varejo e subindo o ticket."),
  "significa":("A Confort Linens tem base digital e recompra: <b>item de giro, cliente que compra sozinho e uma dor clara de pedidos desorganizados no B2B.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Olist (Tiny)","Confort Linens")},

 {"slug":"mar-rio","theme":"light","food":True,"empresa":"Mar&Rio Pescados","contato":"João Paulo Goulart","cargo_area":"Distribuição de pescados","local":"Brasil",
  "sobre":("A Mar&Rio Pescados é <b>distribuidora de pescados</b>, atendendo varejo, food service e consumidor final. Produto perecível de alto "
           "giro, com recompra recorrente de restaurantes, peixarias e mercados."),
  "sobre_fonte":"Fontes: site mareriopescados.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Restaurantes, peixarias, mercados e consumidor final","como_vende":"WhatsApp e presencial","loja_virtual":"Possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"+151 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Mar&Rio distribui <b>pescados</b> para restaurantes, peixarias, mercados e consumidor final &mdash; perecível de <b>alto giro e recompra frequente</b>.",
   "A venda roda por <b>WhatsApp e presencial</b> &mdash; e a dor é <b>pedidos desorganizados</b> entre canais.",
   "Tem loja virtual, mas o pedido do cliente B2B (restaurante/peixaria) ainda se mistura no WhatsApp."],
  "pushpull":("A demanda é <b>puxada</b>: restaurante e peixaria recompram pescado direto &mdash; produto perecível que precisa girar. Você nos "
              "disse que o cliente <b>compraria sozinho</b>; um portal B2B com tabela e disponibilidade do dia digitaliza a recompra que hoje trava no WhatsApp."),
  "conta":("Pescado é perecível &mdash; pedido desorganizado é venda perdida e perda de produto. Um canal B2B com disponibilidade em tempo real "
           "<b>organiza o pedido, reduz perda e acelera a recompra</b>."),
  "significa":("A Mar&Rio tem giro alto e recompra diária: <b>perecível que não pode parar, cliente que compra sozinho e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Mar&Rio Pescados")},

 {"slug":"fabrica-moldura","theme":"dark","food":False,"empresa":"Fábrica da Moldura","contato":"Marcos Santos","cargo_area":"Indústria de molduras e quadros","local":"Brasil",
  "sobre":("A Fábrica da Moldura é <b>fabricante de molduras e quadros</b>, vendendo por marketplaces, lojas e empresas. Catálogo amplo de "
           "molduras com recompra de lojistas e clientes corporativos."),
  "sobre_fonte":"Fontes: site fabricadamoldura.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Lojas, empresas e marketplaces","como_vende":"Marketplaces, lojas e empresas","loja_virtual":"Possui","erp":"Bling",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Fábrica da Moldura produz <b>molduras e quadros</b> e vende por marketplaces, lojas e empresas &mdash; produto de recompra do lojista e do corporativo.",
   "A venda depende muito de <b>marketplaces</b> &mdash; com comissão sobre cada venda e sem relação direta de recompra.",
   "Tem loja virtual, mas falta um canal B2B próprio para o lojista repor sem intermediário."],
  "pushpull":("A demanda é <b>puxada</b>: a loja recompra moldura de giro e sob medida &mdash; sabe o que precisa. Você nos disse que o cliente "
              "<b>compraria sozinho</b>; um canal B2B próprio digitaliza a recompra <b>sem a comissão do marketplace</b>, melhorando a margem da fabricante."),
  "conta":("Vender só por marketplace é pagar comissão na recompra e não ter o cliente. Um portal B2B próprio <b>traz a recompra para casa</b>, "
           "melhora a margem e cria relação direta com o lojista."),
  "significa":("A Fábrica da Moldura tem fabricação própria e recompra: <b>produto de giro, cliente que compra sozinho e dependência de marketplace que um canal B2B próprio resolve.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","Fábrica da Moldura")},

 {"slug":"fashion-master","theme":"dark","food":False,"empresa":"Fashion Master","contato":"Rodrigo John Cunha","cargo_area":"Artigos de beach tennis e tênis","local":"Brasil",
  "sobre":("A Fashion Master atua no <b>segmento de beach tennis e tênis</b>, fornecendo para <b>arenas e proshops</b> (lojas especializadas). "
           "Catálogo de artigos esportivos com recompra do varejo especializado e das arenas."),
  "sobre_fonte":"Fontes: site fashionmaster.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Arenas de beach tennis e proshops","como_vende":"Carteira de clientes","loja_virtual":"Possui","erp":"Bling",
  "vendedores":"6 a 20 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 250 mil a R$ 500 mil","compra_sozinho":"Foco em educar a carteira e atingir novos clientes",
  "encontramos":[
   "A Fashion Master fornece <b>artigos de beach tennis e tênis</b> para arenas e proshops &mdash; nicho em expansão, com recompra do varejo especializado.",
   "A venda roda na <b>carteira de clientes</b> &mdash; e a dor é <b>carteira parada</b>, com foco declarado em <b>atingir novos clientes</b>.",
   "Tem loja virtual, mas a recompra das arenas/proshops ainda não tem um canal B2B próprio."],
  "pushpull":("A demanda é <b>puxada</b>: arena e proshop recompram material de beach tennis conforme a temporada e o giro &mdash; nicho aquecido. "
              "Carteira parada é <b>carteira sem canal de recompra</b>: um portal B2B reativa a recompra e, principalmente, <b>vira vitrine de prospecção</b> para os novos clientes que você quer atingir."),
  "conta":("Em nicho em crescimento, cada arena/proshop nova é recompra recorrente futura. Um canal B2B <b>reativa a carteira e escala a "
           "aquisição</b>: o novo cliente se cadastra, compra sozinho e entra no ciclo de recompra sem custo de vendedor."),
  "significa":("A Fashion Master está num nicho aquecido com recompra: <b>arenas e proshops em expansão, carteira a reativar e foco em novos clientes &mdash; o que um canal B2B digital acelera.</b>"),
  "pot_low":"R$ 35 mil","pot_high":"R$ 70 mil","deixa_mes":"R$ 2,9 mil a R$ 5,8 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 250 mil a R$ 500 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","Fashion Master")},
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
