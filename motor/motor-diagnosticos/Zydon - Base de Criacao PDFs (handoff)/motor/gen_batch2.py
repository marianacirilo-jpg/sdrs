# -*- coding: utf-8 -*-
import os
from playwright.sync_api import sync_playwright
import gen

OUT=os.path.dirname(os.path.abspath(__file__))
DEST=os.path.join(OUT,"Potencial Digitalização B2B - MQLs")
GEN_ERP=("A Zydon integra <b>nativamente via API com Bling, Olist, Omie e Sankhya</b> &mdash; e conecta outros ERPs sob consulta. "
         "Seja qual for o sistema da {emp}, pedido, estoque e tabela passam a conversar em tempo real com o portal.")

LEADS=[
 {"slug":"alimentos-ideal","theme":"dark","food":True,"empresa":"Alimentos Ideal","contato":"Rodrigo Ferreira",
  "cargo_area":"Atacado distribuidor de alimentos","local":"Brasil",
  "sobre":("A Alimentos Ideal é um <b>atacado distribuidor de alimentos</b> de grande porte (faixa de R$ 50 a R$ 500 milhões/ano), "
           "abastecendo <b>supermercados, restaurantes, açougues e hotéis</b>. É o perfil de food service + varejo alimentar &mdash; "
           "o maior segmento do atacado distribuidor do país &mdash; com recompra semanal e alto giro."),
  "sobre_fonte":"Fontes: site alimentosideal.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Supermercados, restaurantes, açougues e hotéis","como_vende":"Ligação (televendas)","loja_virtual":"Não possui",
  "erp":"Outro (não informado)","vendedores":"1 interno","time_total":"+151 pessoas","faturamento":"R$ 50 mi a R$ 500 mi",
  "compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Alimentos Ideal abastece <b>supermercados, restaurantes, açougues e hotéis</b> &mdash; clientes que <b>recompram alimentos toda semana</b>, com alto giro e ticket recorrente.",
   "A venda depende de <b>ligação/televendas</b> &mdash; e, numa operação de +151 pessoas, a recompra previsível ainda passa por contato manual.",
   "Não há loja virtual. Cada pedido de reposição ocupa o televendas, mesmo quando o cliente já sabe exatamente o que quer."],
  "pushpull":("A demanda é fortemente <b>puxada</b>: supermercado e restaurante <b>não podem ficar sem</b> os itens de giro &mdash; "
              "a recompra é certa e semanal. Com você afirmando, no diagnóstico, que o cliente <b>compraria sozinho</b>, o potencial de "
              "digitalizar a maior parte dos pedidos é altíssimo: o televendas sai de tirador de pedido e passa a abrir conta e cuidar de carteira."),
  "conta":("Quando o alimento é item de giro, o pedido é repetido e previsível &mdash; mas ainda ocupa uma ligação a cada reposição. "
           "Colocar essa recompra num canal digital 24/7 <b>libera o time para vender mais e atender mais clientes</b>, sem perder "
           "nenhum pedido recorrente &mdash; exatamente o que sustenta o crescimento de um atacadista desse porte."),
  "significa":("A Alimentos Ideal está no perfil que mais cresce com digitalização: <b>atacado de alimentos com cliente que "
               "recompra toda semana, alto giro e cliente que já compraria sozinho.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":GEN_ERP.format(emp="Alimentos Ideal")},

 {"slug":"okinawa-foods","theme":"light","food":True,"empresa":"Okinawa Foods","contato":"Rafael",
  "cargo_area":"Distribuição de alimentos","local":"Brasil",
  "sobre":("A Okinawa Foods é <b>distribuidora de alimentos</b> (linha oriental), abastecendo <b>distribuidores, supermercados, "
           "padarias e restaurantes</b>. Opera com loja virtual e atende uma carteira mista &mdash; do food service ao varejo &mdash; "
           "em um nicho de produtos com recompra recorrente."),
  "sobre_fonte":"Fontes: site okinawafoods.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Distribuidores, supermercados, padarias e restaurantes","como_vende":"Forma convencional (vendedor)","loja_virtual":"Possui",
  "erp":"Outro (não informado)","vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi",
  "compra_sozinho":"Clientes menores compram sozinhos",
  "encontramos":[
   "A Okinawa Foods distribui <b>alimentos</b> para distribuidores, supermercados, padarias e restaurantes &mdash; carteira que <b>recompra o ano inteiro</b>.",
   "A venda roda de <b>forma convencional</b> com retaguarda enxuta (1 pessoa) &mdash; e a dor declarada é clara: <b>falta controle e visão dos pedidos</b>.",
   "Já existe loja virtual, mas o pedido do cliente ainda se mistura entre canais, sem visão única."],
  "pushpull":("A demanda é <b>puxada</b>: alimento é item de giro e recompra. Você mesmo nos disse que <b>clientes menores já compram"
              "sozinhos</b> &mdash; é exatamente esse pedaço que um canal digital captura primeiro. Com a dor de <b>falta de controle "
              "dos pedidos</b>, um portal único organiza a entrada e dá visão em tempo real, sem depender de remontar pedido à mão."),
  "conta":("Pedido espalhado em canais diferentes não tem controle nem visão &mdash; e cada reposição vira retrabalho para uma "
           "retaguarda de 1 pessoa. Um canal digital único <b>organiza a entrada do pedido, dá visão em tempo real</b> e libera o "
           "time, começando pelos clientes menores que já comprariam sozinhos."),
  "significa":("A Okinawa Foods tem o cenário onde o canal digital entrega rápido: <b>alimento com recompra recorrente, clientes "
               "menores que já comprariam sozinhos e uma dor clara de controle/visão dos pedidos.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":GEN_ERP.format(emp="Okinawa Foods")},

 {"slug":"tobee-lazer","theme":"light","food":False,"empresa":"Tobee Lazer","contato":"Geverson Costa",
  "cargo_area":"Artigos de praia e lazer","local":"Santa Catarina",
  "sobre":("A Tobee Lazer fornece <b>artigos de praia e piscina</b> &mdash; guarda-sóis, ombrelones, espreguiçadeiras e acessórios "
           "&mdash; vendidos por meio de <b>revendedores e lojas</b> em todo o país, com portal exclusivo para o revendedor."),
  "sobre_fonte":"Fontes: site tobeelazer.com.br, portal do revendedor (tobeelazer.rep.br), Facebook da empresa e respostas do diagnóstico Zydon.",
  "vende_para":"Lojas de bazar e revendedores (praia e lazer)","como_vende":"Representante comercial","loja_virtual":"Não possui",
  "erp":"Omie","vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi",
  "compra_sozinho":"Ainda não tem certeza",
  "encontramos":[
   "A Tobee fornece <b>artigos de praia e piscina</b> (guarda-sóis, espreguiçadeiras, ombrelones) para <b>lojas de bazar e revendedores</b> &mdash; recompra sazonal e recorrente.",
   "A venda roda por <b>representante comercial</b>, com retaguarda de 1 pessoa &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Não há canal digital de pedido B2B: o lojista depende do representante chegar para repor."],
  "pushpull":("A demanda é <b>puxada</b>: loja de bazar recompra item de catálogo (guarda-sol, espreguiçadeira) conforme a temporada "
              "&mdash; o cliente sabe o que quer. Com a dor de <b>escalar sem contratar</b>, um portal de recompra deixa o lojista "
              "montar o pedido sozinho e <b>multiplica o alcance do representante</b> sem inflar o time."),
  "conta":("Quando a recompra depende da rota do representante, o teto é a agenda dele &mdash; e na alta temporada isso vira pedido "
           "perdido. Um catálogo digital na mão do lojista <b>reativa a recompra sazonal</b> e escala as vendas sem contratar mais gente."),
  "significa":("A Tobee tem o cenário ideal para um canal digital de recompra: <b>catálogo definido, revenda que recompra por "
               "temporada e uma dor clara de escala.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":("A Tobee roda no <b>Omie</b> &mdash; e a Zydon tem <b>integração nativa via API com o Omie</b>. "
              "Catálogo, preço, estoque e pedido sincronizados em tempo real, sem desenvolvimento e sem retrabalho.")},

 {"slug":"hoppe","theme":"dark","food":False,"empresa":"Hoppe","contato":"Alan Prestes",
  "cargo_area":"Acessórios para esquadrias de alumínio","local":"Brasil",
  "sobre":("A Hoppe atua no fornecimento de <b>acessórios para esquadrias de alumínio</b>, atendendo <b>distribuidores e fábricas "
           "de esquadrias</b>. É um nicho técnico de B2B, com catálogo de componentes e recompra recorrente por parte de quem produz esquadrias."),
  "sobre_fonte":"Fontes: site hoppe-tec.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Distribuidores e fábricas de esquadrias de alumínio","como_vende":"Network / indicação","loja_virtual":"Possui",
  "erp":"Outro (não informado)","vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi",
  "compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Hoppe fornece <b>acessórios para esquadrias de alumínio</b> a distribuidores e fábricas &mdash; componentes técnicos com <b>recompra recorrente</b> conforme a produção do cliente.",
   "A venda hoje vem por <b>network/indicação</b>, com operação enxuta (1 pessoa) &mdash; escala depende de relacionamento, não de canal.",
   "Já há loja virtual, mas o pedido recorrente do distribuidor/fábrica ainda pode ser digitalizado por completo."],
  "pushpull":("A demanda é <b>puxada</b>: fábrica de esquadria recompra os mesmos componentes conforme produz &mdash; sabe exatamente "
              "o código que precisa. Você nos disse que o cliente <b>compraria sozinho</b>. Em catálogo técnico assim, <b>a "
              "digitalização da recompra é altíssima</b>: o cliente monta o pedido por código e o time foca em conta nova."),
  "conta":("Componente técnico de esquadria é compra por código e repetida &mdash; não precisa de vendedor para cada reposição. "
           "Um portal B2B deixa o distribuidor/fábrica recomprar sozinho, <b>libera a operação enxuta</b> e abre espaço para crescer sem contratar."),
  "significa":("A Hoppe tem o perfil de <b>recompra técnica recorrente</b>: catálogo de componentes, cliente profissional que compra "
               "por código e que já compraria sozinho."),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":GEN_ERP.format(emp="Hoppe")},

 {"slug":"inplastic","theme":"light","food":False,"empresa":"Inplastic","contato":"Denis Moreira",
  "cargo_area":"Indústria de produtos plásticos","local":"São Paulo, SP",
  "sobre":("A Inplastic é <b>indústria de produtos plásticos</b> &mdash; pallets, caixas, bins e linha de PDV &mdash; para "
           "<b>indústria e agronegócio</b>, com fabricação própria e foco em soluções logísticas recicláveis. Atende todo o Brasil, com loja online."),
  "sobre_fonte":"Fontes: site inplastic.com.br, LinkedIn da empresa (CNPJ 19.959.992/0001-07) e respostas do diagnóstico Zydon.",
  "vende_para":"Indústria e agronegócio","como_vende":"Online","loja_virtual":"Possui",
  "erp":"Omie","vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 500 mil a R$ 1 mi",
  "compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Inplastic <b>fabrica pallets, caixas e bins plásticos</b> para indústria e agronegócio &mdash; itens de uso contínuo, com <b>recompra recorrente</b> de quem mantém operação logística.",
   "A venda já é <b>online</b>, com 2 a 5 vendedores &mdash; base sólida para escalar por canal digital B2B.",
   "Tem loja virtual, mas o pedido recorrente do cliente industrial pode ganhar um canal B2B com tabela e crédito próprios."],
  "pushpull":("A demanda é <b>puxada</b>: indústria e agro repõem pallets e caixas conforme a operação &mdash; compra recorrente e "
              "previsível. Mesmo você achando hoje que o cliente não compraria sozinho, o histórico de <b>venda online</b> mostra o "
              "contrário para o item de reposição: um portal B2B com tabela e crédito do cliente digitaliza essa recompra e sobe o ticket."),
  "conta":("Pallet e caixa plástica são compra de reposição que se repete &mdash; colocar num canal B2B com a tabela e o crédito do "
           "cliente <b>tira o pedido recorrente do atendimento manual</b> e abre espaço para o vendedor focar em projetos maiores e novas contas."),
  "significa":("A Inplastic tem base pronta para o B2B digital: <b>fabricação própria, item de recompra recorrente e operação que já vende online.</b>"),
  "pot_low":"R$ 70 mil","pot_high":"R$ 140 mil","deixa_mes":"R$ 5,8 mil a R$ 11,7 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 500 mil a R$ 1 milhão ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":("A Inplastic roda no <b>Omie</b> &mdash; e a Zydon tem <b>integração nativa via API com o Omie</b>. "
              "Catálogo, preço, estoque e pedido sincronizados em tempo real, sem desenvolvimento e sem retrabalho.")},

 {"slug":"drm-rolamentos","theme":"dark","food":False,"empresa":"DRM Rolamentos","contato":"Roger Lima",
  "cargo_area":"Distribuição de rolamentos e peças industriais","local":"Curitiba, PR",
  "sobre":("A DRM Rolamentos é <b>importadora e distribuidora de rolamentos e mancais</b> de Curitiba (PR), no mercado desde "
           "<b>1985</b>. Catálogo técnico amplo &mdash; rolamentos, mancais, retentores, correias, polias e lubrificantes &mdash; "
           "para <b>indústrias e revendas de peças</b> de todo o país."),
  "sobre_fonte":"Fontes: site drmrolamentos.com.br, Instagram @drm_rolamentos e respostas do diagnóstico Zydon.",
  "vende_para":"Indústrias e revendas de peças (distribuidores de rolamentos)","como_vende":"WhatsApp, e-mail e balcão","loja_virtual":"Não possui",
  "erp":"Outro (não informado)","vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 1 mi a R$ 5 mi",
  "compra_sozinho":"Preocupa-se com a mão de obra para preparar pedidos",
  "encontramos":[
   "A DRM distribui <b>rolamentos, mancais e peças industriais</b> para indústrias e revendas desde 1985 &mdash; compra <b>por código</b>, técnica e recorrente.",
   "Os pedidos chegam por <b>WhatsApp, e-mail e balcão</b> &mdash; três canais que viram retrabalho e dependem de mão de obra para montar cada pedido.",
   "Não há loja virtual. Cada cotação e separação de pedido consome o tempo do time."],
  "pushpull":("A demanda é <b>puxada e por código</b>: a indústria/revenda sabe exatamente o rolamento que precisa (referência exata) "
              "e recompra. É o cenário de digitalização mais favorável que existe: <b>o cliente monta o pedido por código sozinho</b>, "
              "sem vendedor para cada reposição. A sua própria preocupação &mdash; <b>mão de obra para preparar pedidos</b> &mdash; é o que um canal digital resolve."),
  "conta":("Pedido de rolamento é por referência: o cliente já sabe o código. Receber isso por WhatsApp/e-mail/balcão e remontar à "
           "mão é puro retrabalho. Um portal onde o cliente pesquisa por código e fecha sozinho <b>elimina a digitação manual e a mão "
           "de obra de preparar pedido</b> &mdash; exatamente a dor declarada."),
  "significa":("A DRM tem o caso clássico de alta digitalização: <b>compra técnica por código, cliente que sabe o que quer e recompra, "
               "e uma dor direta de mão de obra para preparar pedidos.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":GEN_ERP.format(emp="DRM Rolamentos")},
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
