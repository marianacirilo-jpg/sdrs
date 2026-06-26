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

LEADS=[
 {"slug":"caramarela","theme":"light","food":False,"empresa":"Caramarela","contato":"Cristiano Greve",
  "cargo_area":"Papelaria e artigos de presente","local":"Limeira, SP",
  "sobre":("A Caramarela é uma <b>papelaria e distribuidora de artigos de papelaria e presentes</b> de Limeira (SP), com forte "
           "presença em <b>marketplaces</b> e venda para diversos comércios. Opera com loja virtual própria e catálogo amplo de itens de giro e recompra."),
  "sobre_fonte":"Fontes: site caramarela.com.br, marketplaces e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Comércios e revendas (papelaria e presentes)","como_vende":"Marketplaces","loja_virtual":"Possui","erp":"Olist (Tiny)",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Caramarela vende <b>artigos de papelaria e presentes</b> por marketplaces e para comércios &mdash; itens de giro com <b>recompra frequente</b>.",
   "A venda depende muito de <b>marketplaces</b> e do atendimento &mdash; e a dor declarada é direta: <b>perde vendas pela demora no atendimento</b>.",
   "Tem loja virtual, mas o pedido do lojista/revenda (B2B) ainda passa por atendimento manual."],
  "pushpull":("A demanda é <b>puxada</b>: o comprador de papelaria sabe o que quer e recompra. <b>Perder venda pela demora</b> é o sinal "
              "claro &mdash; o cliente quer fechar e a resposta humana não chega a tempo. Um canal B2B que vende 24/7 captura essa venda "
              "e tira a Caramarela da fila de atendimento, com a vantagem de não pagar comissão de marketplace na recompra."),
  "conta":("Cada minuto de espera é um pedido que vai para quem respondeu antes &mdash; e, no marketplace, ainda há comissão sobre cada "
           "venda. Um canal próprio de recompra <b>captura a venda perdida pela demora e melhora a margem</b>, deixando o time para o que precisa de atenção."),
  "significa":("A Caramarela tem o cenário onde o B2B digital paga rápido: <b>itens de giro, recompra frequente e uma dor clara de venda perdida por demora.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Olist (Tiny)","Caramarela")},

 {"slug":"boost","theme":"dark","food":True,"empresa":"Boost","contato":"Eduardo Mathias Tarouco",
  "cargo_area":"Distribuição de suplementos e produtos naturais","local":"Blumenau, SC",
  "sobre":("A Boost Natural Foods é <b>distribuidora de suplementos e produtos naturais</b> de Blumenau (SC), abastecendo "
           "<b>lojas de suplementos</b>. Opera com loja virtual e catálogo de itens de recompra frequente do varejo fitness/saudável."),
  "sobre_fonte":"Fontes: site boostnaturalfoods.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Lojas de suplementos","como_vende":"WhatsApp","loja_virtual":"Possui","erp":"Bling",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"Até R$ 250 mil","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Boost distribui <b>suplementos e produtos naturais</b> para <b>lojas de suplementos</b> &mdash; varejo que recompra os mesmos itens de giro com frequência.",
   "A venda roda por <b>WhatsApp</b>, com operação enxuta (1 pessoa) &mdash; cada pedido entra e é remontado à mão.",
   "Tem loja virtual, mas a recompra do lojista ainda depende da conversa no WhatsApp."],
  "pushpull":("A demanda é <b>puxada</b>: loja de suplemento recompra os mesmos produtos e sabe o que quer. Você nos disse que o cliente "
              "<b>compraria sozinho</b> &mdash; e é verdade: um portal B2B com a tabela do lojista digitaliza a recompra que hoje trava no "
              "WhatsApp, sem ocupar a única pessoa da retaguarda."),
  "conta":("Pedido por WhatsApp precisa ser lido, conferido e relançado &mdash; e com 1 pessoa, isso é o gargalo. Um catálogo B2B onde o "
           "lojista monta o pedido sozinho <b>tira a recompra do WhatsApp</b> e libera a operação para crescer."),
  "significa":("A Boost tem o perfil ideal para começar pequeno e crescer no digital: <b>itens de recompra, lojista que compra sozinho e retaguarda enxuta que precisa de alavanca.</b>"),
  "pot_low":"R$ 17 mil","pot_high":"R$ 35 mil","deixa_mes":"R$ 1,4 mil a R$ 2,9 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (até R$ 250 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","Boost")},

 {"slug":"casa-dos-batentes","theme":"light","food":False,"empresa":"Casa dos Batentes","contato":"Philippe Esteves",
  "cargo_area":"Distribuição de madeira e beneficiados","local":"Marília, SP",
  "sobre":("A Casa dos Batentes é o braço distribuidor do <b>Grupo SGM Madeiras</b> (no setor madeireiro desde 1982), em Marília (SP). "
           "Fabrica e distribui <b>batentes, alizares e portas maciças</b> e atende <b>exclusivamente madeireiras, construtoras e empresas "
           "do setor</b> em vários estados."),
  "sobre_fonte":"Fontes: site gruposgmmadeiras.com.br, Instagram da Casa dos Batentes e respostas do diagnóstico Zydon.",
  "vende_para":"Madeireiras, construtoras e material de construção","como_vende":"WhatsApp e ligação","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Acredita que sim",
  "encontramos":[
   "A Casa dos Batentes distribui <b>batentes, portas e beneficiados de madeira</b> para madeireiras e construtoras &mdash; cliente profissional que recompra conforme as obras.",
   "Os pedidos chegam por <b>WhatsApp e ligação</b> &mdash; e a dor é clara: <b>pedidos desorganizados</b> entre canais, com retrabalho e risco de erro.",
   "Não há loja virtual. Cada pedido recriado à mão consome o time e atrasa a obra do cliente."],
  "pushpull":("A demanda é <b>puxada</b>: madeireira e construtora recompram batentes e portas conforme a obra anda &mdash; sabem a "
              "especificação que precisam. Você acredita que o cliente <b>compraria sozinho</b>, e faz sentido: um portal B2B com catálogo "
              "e tabela <b>organiza a entrada do pedido</b> e tira a recompra do WhatsApp/telefone, acabando com o retrabalho."),
  "conta":("Pedido de batente e porta espalhado em WhatsApp, telefone e planilha vira retrabalho e erro de medida &mdash; e erro em madeira "
           "é troca e prejuízo. Um canal digital único <b>padroniza o pedido, reduz erro e dá rastreabilidade</b>, num volume de R$ 10 a 50 milhões que justifica de sobra."),
  "significa":("A Casa dos Batentes tem porte e recompra para o B2B digital: <b>cliente profissional, pedido recorrente por obra e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Casa dos Batentes")},

 {"slug":"suprema-caju","theme":"dark","food":True,"empresa":"Suprema Caju","contato":"George Marques",
  "cargo_area":"Indústria de castanha de caju","local":"Pacajus, CE",
  "sobre":("A Suprema Caju é uma <b>indústria de castanha de caju</b> de Pacajus (CE), com quase <b>20 anos de processamento</b> e mais de "
           "50 de cultivo. Vende castanhas e amêndoas para <b>distribuidores, varejo, padarias e restaurantes</b>, com linha de "
           "<b>white label</b>, atacado em caixas e loja online."),
  "sobre_fonte":"Fontes: site supremacaju.com.br, loja.supremacaju.com.br, LinkedIn/Facebook da empresa e respostas do diagnóstico Zydon.",
  "vende_para":"Padarias, restaurantes, distribuidores e varejo","como_vende":"WhatsApp","loja_virtual":"Possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 250 mil a R$ 500 mil","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Suprema Caju produz e distribui <b>castanhas e amêndoas de caju</b> para padarias, restaurantes, distribuidores e varejo &mdash; produto de recompra recorrente, inclusive em <b>white label</b>.",
   "A venda roda por <b>WhatsApp</b>, com 2 a 5 vendedores &mdash; cada pedido de reposição passa pela conversa.",
   "Já tem loja online (B2C), mas o pedido do revendedor/varejo (B2B) ainda depende do atendimento."],
  "pushpull":("A demanda é <b>puxada</b>: padaria e varejo recompram castanha como item de giro &mdash; sabem o que e quando precisam. Você "
              "nos disse que o cliente <b>compraria sozinho</b>. Um portal B2B com a tabela do revendedor digitaliza a recompra que hoje "
              "passa pelo WhatsApp e abre o atacado para mais pontos sem aumentar o time."),
  "conta":("Castanha é recompra previsível &mdash; e mandar isso por WhatsApp é ocupar vendedor com pedido repetido. Um canal B2B tira a "
           "reposição do atendimento e <b>libera o time para abrir novos pontos e o white label</b>, que é onde está a expansão."),
  "significa":("A Suprema Caju tem produto de recompra e marca consolidada: <b>item de giro, cliente que compra sozinho e um canal B2B ainda manual pronto para digitalizar.</b>"),
  "pot_low":"R$ 35 mil","pot_high":"R$ 70 mil","deixa_mes":"R$ 2,9 mil a R$ 5,8 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 250 mil a R$ 500 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Suprema Caju")},

 {"slug":"commandder","theme":"light","food":False,"empresa":"Commandder","contato":"Luciana Martini",
  "cargo_area":"Distribuição de informática e refurbished","local":"Brasil",
  "sobre":("A Alb Soluções (marca <b>Commandder</b>) atua na <b>distribuição de equipamentos de informática, inclusive refurbished</b>, "
           "vendendo para <b>revendas de informática</b>. Opera com catálogo técnico de TI e atende o canal de revenda."),
  "sobre_fonte":"Fontes: site commandder.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Revendas de informática (inclusive refurbished)","como_vende":"Telefone","loja_virtual":"Não possui","erp":"Omie",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 500 mil a R$ 1 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Commandder distribui <b>equipamentos de informática e refurbished</b> para <b>revendas</b> &mdash; compra técnica, por especificação, e recorrente.",
   "A venda roda por <b>telefone</b>, com 2 a 5 vendedores &mdash; cada cotação e pedido passa pela ligação.",
   "Não há canal digital de pedido: a revenda depende de falar com o vendedor para fechar."],
  "pushpull":("A demanda é <b>puxada</b>: a revenda sabe o equipamento/spec que precisa e recompra conforme vende. Você nos disse que o "
              "cliente <b>compraria sozinho</b> &mdash; em catálogo de TI com preço e disponibilidade, isso é natural: um portal B2B deixa a "
              "revenda montar o pedido sozinha e o vendedor foca em negociação maior."),
  "conta":("Cotação de TI por telefone é demorada e some o histórico &mdash; e em refurbished a disponibilidade muda rápido. Um portal com "
           "estoque e preço em tempo real <b>deixa a revenda comprar sozinha</b> e tira o vendedor da cotação repetida."),
  "significa":("A Commandder tem o perfil de <b>recompra técnica por catálogo</b>: revenda profissional que sabe o que quer e já compraria sozinha."),
  "pot_low":"R$ 70 mil","pot_high":"R$ 140 mil","deixa_mes":"R$ 5,8 mil a R$ 11,7 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 500 mil a R$ 1 milhão ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Omie","Commandder")},

 {"slug":"molpec","theme":"dark","food":False,"empresa":"MOLPEC Automotiva","contato":"Joaquim Magalhães Neto",
  "cargo_area":"Distribuição de autopeças","local":"Brasil",
  "sobre":("A MOLPEC Automotiva atua na <b>distribuição de autopeças</b>, atendendo <b>autopeças e transportadoras</b>. Opera por "
           "teleatendimento, com catálogo de peças de reposição &mdash; compra por código e recorrente, típica do setor automotivo."),
  "sobre_fonte":"Fontes: site molpec.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Autopeças e transportadoras","como_vende":"Teleatendimento","loja_virtual":"Não possui","erp":"Olist (Tiny)",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"Até R$ 250 mil","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A MOLPEC distribui <b>autopeças</b> para autopeças e transportadoras &mdash; compra <b>por código</b>, técnica e recorrente conforme a manutenção da frota.",
   "A venda roda por <b>teleatendimento</b> &mdash; e a dor declarada é <b>carteira de clientes parada</b>.",
   "Não há loja virtual. Fora da ligação, a recompra esfria."],
  "pushpull":("A demanda é <b>puxada e por código</b>: a transportadora/autopeça sabe a peça exata que precisa e recompra na manutenção. "
              "Carteira parada quase sempre é <b>carteira sem canal de recompra</b>: você nos disse que o cliente <b>compraria sozinho</b>, e "
              "um portal por código reativa essa carteira sem depender da ligação."),
  "conta":("Peça automotiva é compra por referência &mdash; o cliente já sabe o código. Depender do teleatendimento limita quantos pedidos "
           "entram por dia e deixa a carteira esfriar. Um portal onde o cliente pesquisa por código e fecha sozinho <b>reativa a recompra</b> sem aumentar o time."),
  "significa":("A MOLPEC tem o caso clássico de digitalização: <b>compra por código, cliente que sabe o que quer e uma carteira parada esperando um canal de recompra.</b>"),
  "pot_low":"R$ 17 mil","pot_high":"R$ 35 mil","deixa_mes":"R$ 1,4 mil a R$ 2,9 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (até R$ 250 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Olist (Tiny)","MOLPEC")},

 {"slug":"b2book","theme":"light","food":False,"empresa":"B2Book","contato":"Paulo Favaro",
  "cargo_area":"Distribuição de livros (atacado editorial)","local":"Brasil",
  "sobre":("A B2Book atua na <b>distribuição de livros para livrarias</b> (atacado editorial), com venda direta ao varejo livreiro. "
           "Catálogo amplo de títulos e recompra recorrente conforme o giro das livrarias."),
  "sobre_fonte":"Fontes: site b2book.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Livrarias e varejo livreiro","como_vende":"Venda direta","loja_virtual":"Não possui","erp":"Bling",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A B2Book distribui <b>livros para livrarias</b> &mdash; varejo que recompra títulos conforme o giro, em catálogo amplo.",
   "A venda é <b>direta</b>, com retaguarda de 1 pessoa &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Não há canal digital de pedido B2B: a livraria depende do contato direto para repor."],
  "pushpull":("A demanda é <b>puxada</b>: livraria recompra títulos de giro e novidades &mdash; sabe o que quer (por ISBN/título). Você nos "
              "disse que o cliente <b>compraria sozinho</b>. Com catálogo amplo, um portal B2B onde a livraria monta o pedido sozinha "
              "<b>escala a distribuição sem contratar</b>, exatamente a dor declarada."),
  "conta":("Distribuir livro com 1 pessoa e venda direta tem teto baixo &mdash; cada pedido ocupa a operação. Um catálogo digital por "
           "título/ISBN <b>deixa a livraria comprar sozinha</b> e multiplica quantos clientes a B2Book atende sem aumentar a equipe."),
  "significa":("A B2Book tem o cenário ideal para escalar no digital: <b>catálogo amplo, recompra por título e uma dor direta de escala com time enxuto.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","B2Book")},

 {"slug":"nobrelack","theme":"dark","food":False,"empresa":"Nobrelack","contato":"Jonatan de Almeida",
  "cargo_area":"Tintas, vernizes e acessórios para móveis","local":"Criciúma, SC",
  "sobre":("A Nobrelack Tintas é <b>distribuidora de tintas, vernizes, colas e acessórios para móveis e pintura</b>, de Criciúma (SC) "
           "desde <b>1994</b>, com filiais em São José e Joinville. Atende <b>marcenarias e oficinas de lataria e pintura</b>, vendendo por "
           "marketplaces e loja física."),
  "sobre_fonte":"Fontes: site nobrelack.com.br, LinkedIn da empresa (CNPJ 00.145.483/0001-12) e respostas do diagnóstico Zydon.",
  "vende_para":"Marcenarias e oficinas de lataria e pintura","como_vende":"Marketplaces e loja física","loja_virtual":"Possui","erp":"Olist (Tiny)",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Ainda não tem certeza",
  "encontramos":[
   "A Nobrelack distribui <b>tintas, vernizes, colas e acessórios</b> para marcenarias e oficinas de pintura &mdash; insumos de <b>recompra recorrente</b> do profissional.",
   "Vende por <b>marketplaces e loja física</b> &mdash; e apontou uma dor específica: <b>integrar com o ERP é caro e complicado</b>.",
   "Cada canal hoje exige esforço de integração, e a recompra do profissional ainda não tem um portal B2B próprio."],
  "pushpull":("A demanda é <b>puxada</b>: marcenaria e oficina recompram a mesma tinta/verniz/cola conforme o trabalho &mdash; sabem o "
              "produto que usam. É recompra técnica recorrente, com potencial alto de digitalização: um portal B2B deixa o profissional "
              "repor sozinho, sem ocupar vendedor e sem comissão de marketplace na recompra."),
  "conta":("Insumo de pintura/marcenaria é compra repetida &mdash; e hoje ela se divide entre marketplace (com comissão) e loja física. "
           "Um canal B2B próprio <b>traz a recompra para casa, melhora a margem</b> e organiza o pedido do profissional."),
  "significa":("A Nobrelack tem recompra técnica e marca regional forte: <b>insumo recorrente, profissional que sabe o que usa e venda já espalhada em canais que pedem integração.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":"Nativa via API","erp_golive":"20 a 30 dias","erp_dev":"Zero. Sem projeto de TI",
  "erp_line":("Você apontou que <b>integrar com o ERP é caro e complicado</b> &mdash; é exatamente isso que a Zydon resolve. A integração "
              "com o <b>Olist (Tiny)</b> é <b>nativa via API</b>, no ar em <b>20 a 30 dias</b> e <b>sem projeto de TI</b>: catálogo, preço, "
              "estoque e pedido sincronizados em tempo real.")},
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
