# -*- coding: utf-8 -*-
import os
from playwright.sync_api import sync_playwright
import gen
OUT=os.path.dirname(os.path.abspath(__file__)); DEST=os.path.join(OUT,"Potencial Digitalização B2B - MQLs")
def native(erp,emp): return (f"A {emp} roda no <b>{erp}</b> &mdash; e a Zydon tem <b>integração nativa via API com o {erp}</b>. "
        "Catálogo, preço, estoque e pedido sincronizados em tempo real, sem desenvolvimento e sem retrabalho.")
GEN=("A Zydon integra <b>nativamente via API com Bling, Olist, Omie e Sankhya</b> &mdash; e conecta outros ERPs sob consulta. "
     "Seja qual for o sistema da {emp}, pedido, estoque e tabela passam a conversar em tempo real com o portal.")
NAT=("Nativa via API","20 a 30 dias","Zero. Sem projeto de TI")
SOB=("Sob consulta","Sob avaliação","Escopo caso a caso")

LEADS=[
 {"slug":"texmedy","theme":"light","food":False,"empresa":"TexMEDY","contato":"Eustachio Fonseca",
  "cargo_area":"Indústria têxtil hospitalar","local":"Belo Horizonte, MG",
  "sobre":("A TexMEDY é <b>indústria têxtil hospitalar</b> de Belo Horizonte (MG), pioneira no Brasil em <b>enxoval e uniformes "
           "hospitalares personalizados</b> desde 1986. Fornece enxoval, uniformes e mobiliário para <b>hospitais e lavanderias</b>, com linhas próprias (SuperTexMEDy®)."),
  "sobre_fonte":"Fontes: site texmedy.com.br, registro público (CNPJ 30.235.701/0001-70) e respostas do diagnóstico Zydon.",
  "vende_para":"Hospitais e lavanderias","como_vende":"Visita externa (olho no olho)","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"11 a 25 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A TexMEDY fornece <b>enxoval e uniformes hospitalares</b> para hospitais e lavanderias &mdash; têxtil que <b>desgasta e é reposto</b> com frequência.",
   "A venda é <b>olho no olho</b>, viajando atrás do cliente, com 1 pessoa na retaguarda &mdash; e a dor é <b>perder vendas pela demora no atendimento</b>.",
   "Não há canal digital: a reposição do enxoval depende de o vendedor estar disponível."],
  "pushpull":("Tem os dois lados: a <b>especificação inicial</b> do enxoval/uniforme é consultiva (e deve seguir com o vendedor), mas a "
              "<b>reposição</b> &mdash; o têxtil que desgasta no uso hospitalar &mdash; é <b>puxada e recorrente</b>. É nessa recompra que "
              "mora a venda perdida pela demora: um portal deixa o hospital/lavanderia repor sozinho, sem esperar a visita."),
  "conta":("Quando a reposição depende da viagem do vendedor, cada dia de espera é um pedido que esfria &mdash; e com 1 pessoa na "
           "retaguarda, o teto é baixo. Um canal de recompra para o enxoval <b>captura a venda perdida pela demora</b> e libera o time para a venda consultiva nova."),
  "significa":("A TexMEDY tem reposição têxtil recorrente e marca consolidada: <b>consumível que desgasta, cliente institucional que recompra e uma dor clara de venda perdida por demora.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="TexMEDY")},

 {"slug":"df-farma","theme":"dark","food":False,"empresa":"DF Farma","contato":"Carlos Bento da Silva",
  "cargo_area":"Distribuição farmacêutica","local":"Brasil",
  "sobre":("A DF Comércio de Produtos Farmacêuticos é <b>distribuidora farmacêutica</b>, atendendo <b>farmácias</b> por televendas. "
           "Catálogo de medicamentos e produtos de saúde &mdash; compra por código, técnica e de recompra recorrente do varejo farmacêutico."),
  "sobre_fonte":"Fontes: site dffarma.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Farmácias","como_vende":"Televendas","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"6 a 20 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A DF Farma distribui <b>medicamentos e produtos de saúde</b> para <b>farmácias</b> &mdash; compra por código (EAN), técnica e de <b>recompra recorrente</b>.",
   "A venda roda por <b>televendas</b> com 6 a 20 vendedores &mdash; e a dor declarada é <b>carteira de clientes parada</b>.",
   "Não há loja virtual. Fora da ligação, a farmácia repõe no concorrente que atende."],
  "pushpull":("A demanda é <b>puxada e por código</b>: a farmácia sabe o produto/EAN que precisa e recompra. Carteira parada quase sempre é "
              "<b>carteira sem canal de recompra</b>: você nos disse que o cliente <b>compraria sozinho</b>, e um portal por código reativa essa carteira sem depender de cada ligação."),
  "conta":("Medicamento é compra por código e recorrente &mdash; ocupar o televendas com isso limita quantas farmácias entram por dia. Um "
           "portal onde a farmácia pesquisa por EAN e fecha sozinha <b>reativa a carteira parada</b> e libera o time para abrir e recuperar clientes."),
  "significa":("A DF Farma tem o caso clássico de digitalização: <b>compra por código, farmácia que recompra e uma carteira parada esperando um canal próprio.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="DF Farma")},

 {"slug":"centro-das-maquinas","theme":"light","food":False,"empresa":"Centro das Máquinas","contato":"Mayrus Gomes",
  "cargo_area":"Distribuição de máquinas, equipamentos e ferramentas","local":"Brasil",
  "sobre":("A Eletro Seguro (marca <b>Centro das Máquinas</b>) é <b>distribuidora de máquinas, equipamentos e ferramentas</b>, vendendo "
           "por e-commerce para <b>casas agropecuárias e lojas de ferramentas</b>. Catálogo amplo de itens técnicos com recompra do varejo especializado."),
  "sobre_fonte":"Fontes: site centrodasmaquinas.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Casas agropecuárias e lojas de ferramentas","como_vende":"E-commerce","loja_virtual":"Possui","erp":"Bling",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 250 mil a R$ 500 mil","compra_sozinho":"Em parte (sim e não)",
  "encontramos":[
   "A Centro das Máquinas distribui <b>máquinas, equipamentos e ferramentas</b> para casas agropecuárias e lojas de ferramentas &mdash; itens técnicos de recompra do varejo.",
   "A venda já é <b>e-commerce</b>, com 2 a 5 vendedores &mdash; base sólida para um canal B2B dedicado ao lojista.",
   "Tem loja virtual (B2C), mas a recompra do lojista/revenda ainda não tem tabela e condição próprias de atacado."],
  "pushpull":("A demanda é <b>puxada</b>: a loja de ferramentas/agropecuária recompra os mesmos itens conforme vende &mdash; sabe o que quer. "
              "O histórico de <b>e-commerce</b> mostra que o cliente compra sozinho; falta um canal <b>B2B</b> com tabela do lojista para digitalizar a recompra do atacado e separá-la do varejo."),
  "conta":("Vender no mesmo balcão digital para consumidor e para lojista mistura preço e condição. Um canal B2B próprio, com tabela e "
           "crédito do revendedor, <b>organiza o atacado e sobe o ticket</b> &mdash; aproveitando que o cliente já está acostumado a comprar online."),
  "significa":("A Centro das Máquinas tem base digital pronta: <b>catálogo técnico, cliente que já compra online e recompra do varejo especializado esperando um canal B2B.</b>"),
  "pot_low":"R$ 35 mil","pot_high":"R$ 70 mil","deixa_mes":"R$ 2,9 mil a R$ 5,8 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 250 mil a R$ 500 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","Centro das Máquinas")},

 {"slug":"latte-foods","theme":"dark","food":True,"empresa":"Latté Foods","contato":"Gustavo Soares",
  "cargo_area":"Indústria de ingredientes para alimentos","local":"Contagem, MG",
  "sobre":("A GGC Alimentos (marca <b>Latté Foods</b>) é <b>indústria de ingredientes para alimentos</b> de Contagem (MG). Desenvolve "
           "<b>soluções lácteas e cremes</b> (linhas GranLatté e GranCrema) para <b>indústrias de alimentos e bebidas</b>, sorveterias, açaí, padarias e foodservice."),
  "sobre_fonte":"Fontes: site lattefoods.com.br, Econodata (CNPJ 42.971.278/0001-56) e respostas do diagnóstico Zydon.",
  "vende_para":"Indústrias de alimentos e bebidas","como_vende":"Representação comercial","loja_virtual":"Não possui","erp":"Omie",
  "vendedores":"1 interno","time_total":"21 a 100 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Latté Foods fornece <b>ingredientes (soluções lácteas e cremes)</b> para indústrias de alimentos e bebidas &mdash; insumo de produção, comprado de forma <b>recorrente e programada</b>.",
   "A venda roda por <b>representação comercial</b>, com retaguarda enxuta (1 interno) &mdash; o pedido B2B do industrial ainda passa pelo representante.",
   "Não há canal digital de pedido: o cliente industrial depende do representante para repor insumo."],
  "pushpull":("A demanda é <b>puxada</b>: indústria de alimentos repõe ingrediente conforme a produção &mdash; compra programada e previsível. "
              "Você nos disse que o cliente <b>compraria sozinho</b>; em insumo de produção, um portal B2B com tabela e contrato do cliente digitaliza a recompra e dá previsibilidade à fábrica."),
  "conta":("Ingrediente de produção é pedido recorrente e planejado &mdash; passar isso pelo representante a cada ciclo é ocupar a operação "
           "com o previsível. Um canal B2B <b>automatiza a recompra programada</b> e libera a representação para abrir novas indústrias, num porte (R$ 50 a 500 mi) que justifica de sobra."),
  "significa":("A Latté Foods está no perfil de alta digitalização: <b>insumo industrial de recompra programada, cliente que compra sozinho e porte que pede um canal B2B próprio.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Omie","Latté Foods")},

 {"slug":"mileva","theme":"light","food":False,"empresa":"Mileva","contato":"Bruno Capeletti",
  "cargo_area":"Distribuição de produtos pet","local":"Brasil",
  "sobre":("A Mileva é <b>distribuidora de produtos para pet shops</b>, vendendo por WhatsApp e loja virtual. Catálogo de itens de giro do "
           "varejo pet &mdash; ração, acessórios e higiene &mdash; com recompra recorrente das lojas."),
  "sobre_fonte":"Fontes: site milevastore.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Pet shops","como_vende":"WhatsApp","loja_virtual":"Possui","erp":"Olist (Tiny)",
  "vendedores":"1 interno","time_total":"11 a 25 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Mileva distribui <b>produtos pet</b> para <b>pet shops</b> &mdash; itens de giro que a loja recompra toda semana.",
   "A venda roda por <b>WhatsApp</b> e a dor é clássica: <b>vendedores gastam tempo só tirando pedido</b>.",
   "Tem loja virtual, mas a recompra do pet shop (B2B) ainda trava no WhatsApp."],
  "pushpull":("A demanda é fortemente <b>puxada</b>: pet shop recompra ração e itens de giro &mdash; sabe exatamente o que quer. Com "
              "<b>vendedor só tirando pedido</b> e você dizendo que o cliente <b>compraria sozinho</b>, o potencial de digitalizar a maior parte dos pedidos é altíssimo: o vendedor vira gestor de carteira."),
  "conta":("Reposição de pet shop é repetida e previsível &mdash; ocupar vendedor com isso é desperdício. Um portal B2B onde o lojista monta "
           "o pedido sozinho <b>tira a recompra do WhatsApp</b> e libera o time para abrir conta e subir ticket."),
  "significa":("A Mileva tem o perfil que mais cresce com digitalização: <b>giro alto, recompra semanal do pet shop e cliente que já compraria sozinho.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Olist (Tiny)","Mileva")},

 {"slug":"coferpan","theme":"dark","food":True,"empresa":"Coferpan","contato":"Flávio Augusto Esteves",
  "cargo_area":"Distribuição de insumos para panificação","local":"Londrina, PR",
  "sobre":("A Coferpan é <b>distribuidora de insumos para panificação e confeitaria</b> desde <b>1976</b>, uma das maiores do setor, com "
           "centros em <b>Londrina, Curitiba e Blumenau</b>. Fornece fermentos, ingredientes, utensílios e embalagens para <b>padarias e confeitarias</b>."),
  "sobre_fonte":"Fontes: site coferpan.com.br, Instagram @coferpan.londrina, registro público (CNPJ 76.273.762/0001-23) e respostas do diagnóstico Zydon.",
  "vende_para":"Padarias e confeitarias","como_vende":"Presencial","loja_virtual":"Não possui","erp":"TOTVS",
  "vendedores":"2 a 5 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Em parte",
  "encontramos":[
   "A Coferpan abastece <b>padarias e confeitarias</b> com fermentos, ingredientes e embalagens &mdash; insumo de produção com <b>recompra semanal</b>.",
   "A venda é <b>presencial</b>, e a dor é <b>dificuldade de escalar sem contratar mais gente</b> &mdash; crescer hoje significa mais vendedor em rota.",
   "Não há loja virtual. A padaria depende da visita para repor o insumo do dia a dia."],
  "pushpull":("A demanda é <b>puxada</b>: padaria repõe fermento, farinha e embalagem toda semana &mdash; é o insumo do negócio dela, compra "
              "certa. Quando a recompra é tão previsível, <b>digitalizar a maior parte dos pedidos é natural</b>: o cliente monta sozinho o "
              "pedido recorrente e o vendedor presencial passa a abrir conta e vender mix novo, escalando sem contratar."),
  "conta":("Insumo de padaria é recompra diária/semanal &mdash; e se isso depende da rota do vendedor, o teto é o tamanho do time. Um portal "
           "de recompra para as padarias <b>escala as vendas sem inflar a folha</b> e garante que a padaria nunca fique sem o item de produção."),
  "significa":("A Coferpan tem porte e recompra para o B2B digital: <b>insumo de produção, padaria que recompra toda semana e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":SOB[0],"erp_golive":SOB[1],"erp_dev":SOB[2],
  "erp_line":("A Coferpan roda no <b>TOTVS</b> &mdash; e a integração com o TOTVS é avaliada <b>sob consulta</b>. A Zydon conecta o portal "
              "ao ERP para sincronizar estoque, tabela de preço e pedidos, com o escopo validado caso a caso pelo time técnico.")},

 {"slug":"rf-roto-frank","theme":"light","food":False,"empresa":"RF (Roto Frank)","contato":"Marlon Neves",
  "cargo_area":"Ferragens e sistemas para esquadrias","local":"Brasil",
  "sobre":("A RF (Roto Frank do Brasil) fornece <b>ferragens e sistemas para esquadrias</b> de alumínio e PVC, atendendo <b>serralheiros e "
           "fabricantes de esquadrias</b>. Componentes técnicos de marca global, com recompra recorrente conforme a produção do cliente."),
  "sobre_fonte":"Fontes: site roto-frank.com e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Serralheiros e fábricas de esquadrias","como_vende":"Equipe técnica de vendas","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"6 a 20 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Mais da metade compraria sozinho",
  "encontramos":[
   "A RF fornece <b>ferragens e sistemas para esquadrias</b> a serralheiros e fábricas &mdash; componentes técnicos de <b>recompra recorrente</b> por código.",
   "Os pedidos chegam <b>desorganizados</b> (WhatsApp, telefone, planilha), com 6 a 20 vendedores &mdash; retrabalho e risco de erro de referência.",
   "Não há loja virtual. Cada pedido técnico é remontado à mão, com risco de trocar a peça errada."],
  "pushpull":("A demanda é <b>puxada e por código</b>: o serralheiro sabe a ferragem exata que precisa para o projeto e recompra. Você nos "
              "disse que <b>mais da metade compraria sozinho</b> &mdash; e em componente técnico isso é natural: um portal por código "
              "<b>organiza o pedido e elimina o erro de referência</b>, tirando o vendedor da digitação repetida."),
  "conta":("Ferragem é compra por referência exata &mdash; errar o código é troca, atraso e prejuízo na obra. Receber isso por "
           "WhatsApp/telefone/planilha multiplica o erro. Um portal onde o cliente seleciona por código <b>padroniza o pedido, zera o retrabalho</b> e dá rastreabilidade, num volume de R$ 10 a 50 milhões."),
  "significa":("A RF tem o caso forte de digitalização: <b>compra técnica por código, cliente que em boa parte compra sozinho e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="RF")},

 {"slug":"connect","theme":"dark","food":False,"empresa":"Connect","contato":"Frederico Augusto",
  "cargo_area":"Distribuição de CFTV e ar-condicionado","local":"Brasil",
  "sobre":("A Connect é <b>distribuidora de equipamentos de segurança eletrônica (CFTV) e ar-condicionado</b>, atendendo <b>instaladores de "
           "câmeras e de climatização</b>. Catálogo técnico com recompra recorrente do profissional instalador."),
  "sobre_fonte":"Fontes: site connectcenter.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Instaladores de câmeras e ar-condicionado","como_vende":"WhatsApp","loja_virtual":"Não possui","erp":"Olist (Tiny)",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Connect distribui <b>CFTV e ar-condicionado</b> para <b>instaladores</b> &mdash; compra técnica por especificação, recorrente conforme os serviços.",
   "A venda roda por <b>WhatsApp</b> e a dor é clássica: <b>vendedores gastam tempo só tirando pedido</b>.",
   "Não há loja virtual. Cada pedido do instalador trava na conversa do WhatsApp."],
  "pushpull":("A demanda é <b>puxada</b>: o instalador sabe a câmera/equipamento que precisa para o serviço e recompra. Com <b>vendedor só "
              "tirando pedido</b> e você dizendo que o cliente <b>compraria sozinho</b>, o potencial de digitalizar é altíssimo: o instalador "
              "monta o pedido por especificação e o vendedor foca em projeto e conta nova."),
  "conta":("Equipamento de CFTV/clima é compra por spec, repetida a cada instalação &mdash; ocupar vendedor com isso é desperdício. Um portal "
           "onde o instalador escolhe por especificação e fecha sozinho <b>tira a recompra do WhatsApp</b> e libera o time para vender mais."),
  "significa":("A Connect tem o perfil de alta digitalização: <b>compra técnica do instalador, recompra por serviço e cliente que já compraria sozinho.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Olist (Tiny)","Connect")},
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
