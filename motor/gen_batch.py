# -*- coding: utf-8 -*-
import os
from playwright.sync_api import sync_playwright
import gen  # build_html, TEMPLATE, logos

OUT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(OUT, "Potencial Digitalização B2B - MQLs")

NATIVE = ("A integração é <b>nativa via API</b>", "20 a 30 dias", "Zero. Sem projeto de TI")

LEADS = [
 {  # 1 - PRETO
  "slug":"gran-arthurium","theme":"dark","food":False,
  "empresa":"Gran Arthurium","contato":"Mateus Junqueira",
  "cargo_area":"Indústria de bebidas — licores premium","local":"Sete Lagoas, MG",
  "sobre":("A Gran Arthurium (Junqueira e Lobo Soluções em Bebidas) é uma <b>indústria de licores premium</b> "
           "de Sete Lagoas (MG), fundada em 2021. Seus rótulos premiados já estão em <b>mais de 200 pontos de venda</b> "
           "&mdash; empórios, restaurantes, churrascarias e supermercados premium &mdash; e a empresa investe em "
           "<b>fábrica própria</b>, mirando dobrar o faturamento em 2026."),
  "sobre_fonte":"Fontes: site granarthurium.com.br, Diário do Comércio, registro público (CNPJ 44.682.638/0001-25) e respostas do diagnóstico Zydon.",
  "vende_para":"Empórios, restaurantes e supermercados (B2B) + consumidor final (B2C)",
  "como_vende":"B2B e B2C","loja_virtual":"Possui","erp":"Olist (Tiny)",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 500 mil a R$ 1 mi",
  "compra_sozinho":"Hoje acredita que não",
  "encontramos":[
    "A Gran Arthurium é <b>indústria de licor premium</b>, com marca premiada e presença em <b>200+ pontos</b> &mdash; empórios, restaurantes e supermercados que recompram o produto.",
    "Vende em dois canais (<b>B2B e B2C</b>) com uma <b>operação enxuta (1 pessoa)</b> &mdash; e os pedidos chegam <b>desorganizados</b> (WhatsApp, telefone, planilha).",
    "Já tem loja virtual para o B2C, mas o pedido do empório/lojista (B2B) ainda passa pelo atendimento manual &mdash; cada pedido recriado à mão é tempo e risco de erro."],
  "pushpull":("Aqui a demanda é claramente <b>puxada</b>: licor premium e premiado é produto que o cliente <b>quer e procura</b> "
              "&mdash; empório e restaurante recompram para repor a prateleira. Quando o produto é diferenciado assim, o pedido "
              "não precisa ser empurrado: <b>a probabilidade de digitalizar o B2B é altíssima</b>. Um portal de recompra para os "
              "200+ pontos tira o pedido do WhatsApp e sustenta a expansão sem inflar a equipe."),
  "conta":("Com uma pessoa cuidando de tudo, cada pedido que entra por WhatsApp/telefone precisa ser conferido e relançado à mão "
           "&mdash; e, no meio de uma fábrica em expansão, é justamente esse gargalo que trava o crescimento. <b>Um canal digital "
           "de recompra para os pontos B2B</b> organiza a entrada do pedido e devolve tempo para vender mais."),
  "significa":("A Gran Arthurium tem o cenário ideal para um canal digital B2B: <b>marca premium desejada, 200+ pontos que "
               "recompram e operação enxuta que precisa escalar sem inchar.</b>"),
  "pot_low":"R$ 70 mil","pot_high":"R$ 140 mil","deixa_mes":"R$ 5,8 mil a R$ 11,7 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 500 mil a R$ 1 milhão ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":("A Gran Arthurium roda no <b>Olist (Tiny)</b> &mdash; e a Zydon tem <b>integração nativa via API com o Olist/Tiny</b>. "
              "Catálogo, preço, estoque e pedido sincronizados em tempo real, sem desenvolvimento e sem retrabalho."),
 },
 {  # 2 - BRANCO
  "slug":"kaja-vet","theme":"light","food":False,
  "empresa":"Kaja Vet","contato":"Cassiano Pelegrini",
  "cargo_area":"Farmácia veterinária — linha equina e pet","local":"São José do Rio Preto, SP",
  "sobre":("A Kaja Vet é uma <b>farmácia veterinária</b> de São José do Rio Preto (SP), no mercado desde <b>2008</b>, "
           "especializada na <b>linha equina</b> e também em produtos pet. Atende todo o Brasil, com loja virtual, retirada "
           "e drive-through, e mantém nota <b>4,5/5</b> nas avaliações de clientes."),
  "sobre_fonte":"Fontes: site kajavet.com.br, Facebook/LinkedIn da empresa e respostas do diagnóstico Zydon.",
  "vende_para":"Criadores, haras, clínicas e tutores (linha equina e pet)",
  "como_vende":"Telefone e internet","loja_virtual":"Possui","erp":"Bling",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"Até R$ 250 mil",
  "compra_sozinho":"Acredita que sim",
  "encontramos":[
    "A Kaja Vet vende <b>medicamentos e acessórios veterinários</b> (linha equina e pet) para todo o Brasil &mdash; compra técnica e <b>recorrente</b> de quem já sabe o que quer.",
    "A venda roda por <b>telefone e internet</b>, com 2 a 5 vendedores &mdash; e a própria empresa apontou a dor: <b>perde vendas pela demora no atendimento</b>.",
    "Já existe loja virtual, mas boa parte do pedido ainda depende de alguém responder &mdash; e cliente que quer comprar agora não espera."],
  "pushpull":("A demanda é <b>puxada</b>: o cliente sabe o medicamento ou acessório que precisa e recompra. A dor declarada "
              "&mdash; <b>perde venda pela demora</b> &mdash; é a prova: o cliente quer fechar e o atendimento humano não dá conta na hora. "
              "Quando a demanda é puxada assim, <b>o autoatendimento captura a venda que hoje escapa</b> &mdash; e você mesmo, "
              "no diagnóstico, acredita que o cliente compraria sozinho."),
  "conta":("Cada minuto de espera no atendimento é um pedido que pode ir para o concorrente que respondeu primeiro. Tirar a "
           "recompra previsível do atendimento manual e colocá-la num canal que vende 24/7 <b>recupera a venda perdida pela "
           "demora</b> &mdash; sem tirar o time das vendas que realmente precisam de orientação."),
  "significa":("A Kaja Vet tem o perfil onde o canal digital paga rápido: <b>cliente que sabe o que quer, recompra recorrente "
               "e uma dor clara de venda perdida por demora.</b>"),
  "pot_low":"R$ 17 mil","pot_high":"R$ 35 mil","deixa_mes":"R$ 1,4 mil a R$ 2,9 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (até R$ 250 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":("A Kaja Vet roda no <b>Bling</b> &mdash; e a Zydon tem <b>integração nativa via API com o Bling</b>. "
              "Catálogo, preço, estoque e pedido sincronizados em tempo real, sem desenvolvimento e sem retrabalho."),
 },
 {  # 3 - PRETO
  "slug":"tokyo-foods","theme":"dark","food":True,
  "empresa":"Tokyo Foods","contato":"Claudio Fukushima",
  "cargo_area":"Distribuição de alimentos orientais","local":"São Paulo, SP",
  "sobre":("A Tokyo Foods é <b>distribuidora de alimentos orientais</b> em São Paulo (Bosque da Saúde), braço da MAC Oriental Food. "
           "Abastece restaurantes e supermercados com ingredientes japoneses &mdash; <b>sakes, dashis, molhos, algas, arroz e "
           "conservas</b> de marcas como Hakutsuru, Marutomo e Ebara."),
  "sobre_fonte":"Fontes: site tokyofoods.com.br, Econodata (CNPJ 17.289.923/0001-08), Instagram @tokyofoodsbr e respostas do diagnóstico Zydon.",
  "vende_para":"Restaurantes e supermercados (gastronomia oriental)",
  "como_vende":"Representantes e vendedores externos","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 10 mi a R$ 50 mi",
  "compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
    "A Tokyo Foods distribui <b>ingredientes orientais</b> para restaurantes e supermercados &mdash; clientes de gastronomia japonesa que <b>repõem o estoque toda semana</b>.",
    "A venda roda por <b>representantes e vendedores externos</b>, e a dor declarada é clássica: <b>vendedores gastam tempo só tirando pedido</b>.",
    "Não há loja virtual. Cada reposição de ingrediente ocupa um vendedor que poderia estar abrindo conta nova ou subindo ticket."],
  "pushpull":("A demanda é fortemente <b>puxada</b>: restaurante de comida japonesa <b>não pode ficar sem</b> sake, dashi ou alga "
              "&mdash; a recompra é certa e recorrente. Com a dor de <b>vendedor só tirando pedido</b> e você mesmo nos dizendo que "
              "o cliente <b>compraria sozinho</b>, o potencial de digitalizar a maior parte dos pedidos é altíssimo: o vendedor sai "
              "de tirador de pedido e vira gestor de carteira."),
  "conta":("Quando o ingrediente é insumo crítico de cozinha, o pedido é repetido e previsível &mdash; e mesmo assim ocupa o tempo "
           "de um vendedor a cada reposição. Colocar essa recompra num catálogo digital <b>libera o time externo para abrir conta e "
           "subir ticket</b>, sem perder nenhum pedido recorrente."),
  "significa":("A Tokyo Foods está no perfil que mais cresce com digitalização: <b>distribuidor de alimentos com cliente que "
               "recompra toda semana, dor de vendedor-tirador-de-pedido e cliente que já compraria sozinho.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":("A Zydon integra <b>nativamente via API com Bling, Olist, Omie e Sankhya</b> &mdash; e conecta outros ERPs sob consulta. "
              "Seja qual for o sistema da Tokyo Foods, pedido, estoque e tabela passam a conversar em tempo real com o portal."),
 },
 {  # 4 - BRANCO
  "slug":"plac","theme":"light","food":False,
  "empresa":"Plac","contato":"Claudinei Comachio",
  "cargo_area":"Indústria de artigos para festa","local":"Ribeirão Preto, SP",
  "sobre":("A Plac é uma <b>indústria de artigos para festa</b> de Ribeirão Preto (SP), fundada em <b>1991</b>, com "
           "<b>mais de 600 itens</b> em catálogo (descartáveis, decoração, formas para bolo) e capital social de ~R$ 1,9 milhão. "
           "Vende para todo o Brasil por meio de <b>revendedores e lojas de festa</b>."),
  "sobre_fonte":"Fontes: site plac.com.br, Econodata/Serasa (CNPJ 65.917.171/0001-25), Instagram @placfestas e respostas do diagnóstico Zydon.",
  "vende_para":"Lojas de festa e distribuidores",
  "como_vende":"Representante","loja_virtual":"Não possui","erp":"Sankhya",
  "vendedores":"2 a 5 internos","time_total":"51 a 150 pessoas","faturamento":"R$ 10 mi a R$ 50 mi",
  "compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
    "A Plac fabrica <b>600+ itens de festa</b> e vende para <b>lojas de festa e distribuidores</b> de todo o país &mdash; cliente que recompra item de catálogo o ano inteiro.",
    "A venda é por <b>representante</b>, com 2 a 5 vendedores internos sustentando uma operação de 51 a 150 pessoas &mdash; e a dor apontada é <b>carteira parada</b>.",
    "Não há loja virtual. Com 600+ SKUs, o catálogo depende do representante chegar &mdash; fora da rota, a recompra esfria."],
  "pushpull":("A demanda é <b>puxada</b>: loja de festa recompra item de catálogo (copo, prato, forma, decoração) de forma "
              "recorrente &mdash; o cliente sabe o que quer. Você nos disse que ele <b>compraria sozinho</b>. Carteira parada "
              "quase sempre é <b>carteira sem canal de recompra</b>: com um portal, o lojista monta o pedido dos 600 itens sozinho "
              "e a recompra volta a girar."),
  "conta":("Quando a recompra depende da visita ou do contato do representante, o teto é a agenda do time. A loja que precisa repor "
           "entre uma rota e outra <b>simplesmente não pede</b> &mdash; ou pede no concorrente. Um catálogo digital com os 600 itens "
           "na mão do cliente <b>reativa a carteira parada</b> sem contratar mais representante."),
  "significa":("A Plac tem tudo para escalar por canal digital: <b>indústria própria, 600+ itens, marca consolidada desde 1991 e "
               "revendedores que recompram.</b> Falta tirar o catálogo da rota do representante e colocar na mão do lojista."),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":("A Plac roda no <b>Sankhya</b> &mdash; e a Zydon <b>nasceu dentro do Sankhya</b>, com <b>integração nativa via API</b>. "
              "Os 600+ itens, com preço e estoque, sobem para o portal e ficam sincronizados em tempo real, sem projeto de TI."),
 },
 {  # 5 - PRETO
  "slug":"ambiental-geo-lider","theme":"dark","food":False,
  "empresa":"Ambiental Geo Líder","contato":"André Luciano",
  "cargo_area":"Materiais para poços artesianos","local":"São José do Rio Preto, SP",
  "sobre":("A A. L. de Almeida opera como <b>Ambiental Geo Líder</b>, fornecedora de <b>materiais e equipamentos para poços "
           "artesianos</b> em São José do Rio Preto (SP). Catálogo técnico amplo &mdash; <b>tubos e filtros de PVC, painéis, cabos, "
           "motobombas, viscosificantes e aditivos de perfuração</b> &mdash; para perfuradores e lojas do setor, com entrega para todo o país."),
  "sobre_fonte":"Fontes: site ambientalgeolider.com.br, Instagram/LinkedIn da empresa e respostas do diagnóstico Zydon.",
  "vende_para":"Perfuradores de poços artesianos e lojas do setor",
  "como_vende":"Telefone","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"6 a 20 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 10 mi a R$ 50 mi",
  "compra_sozinho":"Ainda não sabe",
  "encontramos":[
    "A Ambiental Geo Líder fornece <b>insumos técnicos para perfuração e manutenção de poços</b> &mdash; tubos, filtros, motobombas e aditivos &mdash; para <b>perfuradores e lojas</b> que recompram conforme a obra.",
    "A venda roda por <b>telefone</b>, com 6 a 20 vendedores &mdash; e a dor central é <b>dificuldade de escalar sem contratar mais gente</b>.",
    "Não há loja virtual. Cada cotação e pedido técnico passa por um vendedor ao telefone &mdash; o que limita quantos clientes o time atende por dia."],
  "pushpull":("Tem os dois lados: a <b>primeira especificação</b> do poço é consultiva (e deve seguir com o vendedor), mas a "
              "<b>reposição de insumo</b> &mdash; tubo, filtro, aditivo &mdash; é <b>puxada e recorrente</b>: o perfurador sabe o que "
              "precisa para tocar a obra. É exatamente nessa recompra técnica que dá para <b>digitalizar o grosso dos pedidos</b> e "
              "escalar sem inflar o time &mdash; sem tirar o vendedor da venda que exige orientação."),
  "conta":("Quando todo pedido passa pelo telefone, crescer significa contratar mais gente para atender. Mas boa parte é "
           "<b>reposição que o cliente já conhece</b>: colocar esse catálogo técnico num portal deixa o perfurador montar o pedido "
           "sozinho e <b>libera os 6 a 20 vendedores</b> para cotações novas e contas maiores &mdash; escala sem proporcionalmente mais headcount."),
  "significa":("A Ambiental Geo Líder tem o cenário de <b>reposição técnica recorrente</b>: catálogo definido, cliente profissional "
               "que recompra e uma dor clara de escala. É onde o canal digital tira o pedido repetido das costas do time."),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":("A Zydon integra <b>nativamente via API com Bling, Olist, Omie e Sankhya</b> &mdash; e conecta outros ERPs sob consulta. "
              "Seja qual for o sistema da Ambiental Geo Líder, pedido, estoque e tabela passam a conversar em tempo real com o portal."),
 },
]

NICE = {"gran-arthurium":"Gran Arthurium","kaja-vet":"Kaja Vet","tokyo-foods":"Tokyo Foods",
        "plac":"Plac","ambiental-geo-lider":"Ambiental Geo Líder"}

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    for l in LEADS:
        html = gen.build_html(l)
        hp = os.path.join(OUT, f"{l['slug']}.html")
        open(hp,"w",encoding="utf-8").write(html)
        pg.goto("file://"+hp, wait_until="networkidle")
        out = os.path.join(DEST, f"{NICE[l['slug']]} - Potencial de Digitalização B2B.pdf")
        pg.pdf(path=out, width="210mm", height="297mm", print_background=True,
               margin={"top":"0","bottom":"0","left":"0","right":"0"})
        print("PDF:", os.path.basename(out))
    b.close()
