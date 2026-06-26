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
 {"slug":"quality","theme":"light","food":False,"empresa":"Quality Representações","contato":"José Cícero","cargo_area":"Distribuição multicategoria","local":"Brasil",
  "sobre":("A Quality Representações (Grupo Elo) é <b>distribuidora multicategoria</b>, atendendo <b>supermercados, atacados, panificadoras, "
           "restaurantes, lojas de utilidades, material de construção, piscinas e agropecuária</b>. Catálogo amplo de itens de giro com recompra recorrente."),
  "sobre_fonte":"Fontes: site grupoelo.net.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Supermercados, atacados, panificadoras, restaurantes, construção, piscinas e agro","como_vende":"Presencial e WhatsApp","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Quality distribui <b>itens de várias categorias</b> para um varejo amplo &mdash; carteira que recompra de tudo um pouco, sempre.",
   "A venda é <b>presencial e WhatsApp</b> &mdash; e a dor é <b>carteira de clientes parada</b>.",
   "Não há loja virtual. Fora do contato, a recompra esfria."],
  "pushpull":("A demanda é <b>puxada</b>: o varejo recompra item de giro &mdash; sabe o que quer. Carteira parada quase sempre é <b>carteira sem "
              "canal de recompra</b>: você nos disse que o cliente <b>compraria sozinho</b>, e um portal B2B reativa essa recompra sem depender da visita."),
  "conta":("Carteira multicategoria com presencial/WhatsApp tem teto na agenda do time &mdash; e cada demora é venda perdida. Um catálogo B2B "
           "<b>reativa a carteira parada</b> e multiplica o alcance da operação."),
  "significa":("A Quality tem recompra de um varejo amplo: <b>itens de giro, cliente que compra sozinho e uma carteira parada esperando um canal.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Quality Representações")},

 {"slug":"sq-imports","theme":"dark","food":False,"empresa":"SQ Imports","contato":"Equipe SQ Imports","cargo_area":"Distribuição de som e acessórios automotivos","local":"Brasil",
  "sobre":("A SQ Imports é <b>distribuidora/importadora de som e acessórios automotivos</b>, atendendo <b>lojas do setor</b>. Catálogo técnico de "
           "produtos de giro, com recompra recorrente do varejo automotivo."),
  "sobre_fonte":"Fontes: site sqimports.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Lojas de acessórios e som automotivo","como_vende":"Telefone e WhatsApp","loja_virtual":"Não possui","erp":"Bling",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A SQ Imports distribui <b>som e acessórios automotivos</b> para lojas &mdash; produto técnico de giro, de recompra recorrente.",
   "A venda roda por <b>telefone e WhatsApp</b>, com 1 pessoa &mdash; e a dor é <b>perder vendas pela demora no atendimento</b>.",
   "Não há loja virtual. Cliente que quer comprar agora não espera a resposta."],
  "pushpull":("A demanda é <b>puxada</b>: a loja sabe o produto que precisa e recompra. <b>Perder venda pela demora</b> mostra que o cliente quer "
              "fechar e o atendimento não chega a tempo &mdash; você nos disse que ele <b>compraria sozinho</b>. Um portal B2B 24/7 captura essa venda."),
  "conta":("Cada minuto de espera é um pedido que vai pro concorrente que respondeu antes. Um canal B2B que vende sozinho <b>recupera a venda "
           "perdida pela demora</b> e libera a operação enxuta."),
  "significa":("A SQ Imports tem recompra técnica e dor clara: <b>produto de giro, cliente que compra sozinho e venda perdida por demora no atendimento.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Bling","SQ Imports")},

 {"slug":"plasmontec","theme":"light","food":False,"empresa":"Plasmontec","contato":"Bruno Silva","cargo_area":"Fabricação de uniformes","local":"Brasil",
  "sobre":("A Plasmontec <b>fabrica uniformes</b>, atendendo empresas com venda física. Produto com reposição recorrente (desgaste, novos "
           "colaboradores), de compra programada da base corporativa."),
  "sobre_fonte":"Fontes: site plasmontec.com e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Empresas (uniformes corporativos)","como_vende":"Venda física","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"11 a 25 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Plasmontec fabrica <b>uniformes</b> para empresas &mdash; reposição recorrente por desgaste e novos colaboradores.",
   "A venda é <b>física</b>, com 1 pessoa &mdash; e a dor é <b>dependência de poucos clientes grandes</b>.",
   "Não há canal digital: atender muitas empresas menores é caro hoje."],
  "pushpull":("A demanda tem um lado <b>puxado</b>: a reposição de uniforme (desgaste, novos funcionários) é recorrente e previsível. O ponto-chave "
              "é a <b>concentração</b>: depender de poucos grandes é risco. Um portal B2B de reposição torna viável atender <b>muitas empresas "
              "menores com baixo custo</b>, diluindo a dependência."),
  "conta":("Atender o cliente pequeno na venda física custa caro &mdash; por isso a base se concentra. Um portal de reposição de uniforme "
           "<b>viabiliza a cauda longa</b> de empresas menores e dá previsibilidade à fábrica."),
  "significa":("A Plasmontec tem reposição recorrente, mas concentração de risco: <b>um canal B2B diversifica a carteira atendendo os pequenos com eficiência.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Plasmontec")},

 {"slug":"sunnyvale","theme":"dark","food":False,"empresa":"Sunnyvale","contato":"João Fortes","cargo_area":"Automação industrial e consumíveis de fim de linha","local":"Brasil",
  "sobre":("A Sunnyvale (desde <b>1978</b>) atua em <b>automação de fim de linha</b> &mdash; codificação, inspeção, embalagem e robótica &mdash; "
           "com equipamentos e <b>consumíveis</b> para indústria, supermercados e food service. Tem rede de 23 distribuidores e loja online."),
  "sobre_fonte":"Fontes: site sunnyvale.com.br, loja.sunnyvale.com.br e respostas do diagnóstico Zydon.",
  "vende_para":"Indústria, supermercados e food service","como_vende":"Visita técnica","loja_virtual":"Possui","erp":"TOTVS",
  "vendedores":"6 a 20 internos","time_total":"51 a 150 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Alguns produtos sim",
  "encontramos":[
   "A Sunnyvale fornece <b>equipamentos e consumíveis de codificação/embalagem</b> para indústria e varejo &mdash; o <b>consumível</b> (tinta, ribbon, etiqueta) é recompra recorrente.",
   "A venda é por <b>visita técnica</b> &mdash; e a dor é <b>carteira de clientes parada</b>.",
   "Já há loja online, mas a recompra do consumível ainda passa muito pelo vendedor."],
  "pushpull":("A demanda do <b>consumível</b> é <b>puxada</b>: a indústria que usa o equipamento recompra tinta/ribbon/etiqueta sempre &mdash; sabe "
              "exatamente o que precisa. Você disse que <b>alguns produtos já compram sozinhos</b>: é nesse consumível que um portal B2B reativa a "
              "carteira parada, enquanto o equipamento segue com a venda técnica consultiva."),
  "conta":("Consumível de codificação é recompra previsível &mdash; depender da visita para isso deixa a carteira esfriar. Um portal B2B "
           "<b>captura a recompra do consumível 24/7</b> e libera o time técnico para o equipamento, num porte de R$ 50 a 500 milhões."),
  "significa":("A Sunnyvale tem recompra de consumível e marca de 1978: <b>insumo que se repõe sempre, alguns clientes já comprando sozinhos e uma carteira a reativar.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":SOB[0],"erp_golive":SOB[1],"erp_dev":SOB[2],"erp_line":sob("TOTVS","Sunnyvale")},

 {"slug":"natural-health","theme":"light","food":True,"empresa":"Natural Health","contato":"Danillo Lobo","cargo_area":"Produção de sucos naturais","local":"Brasil",
  "sobre":("A Natural Health produz <b>sucos naturais</b>, atuando no varejo e <b>entrando no atacado</b>, com vendedor de rua e representante. "
           "Produto de giro do food service e varejo, com recompra recorrente."),
  "sobre_fonte":"Fonte: respostas do diagnóstico comercial Zydon.",
  "vende_para":"Varejo e atacado (sucos naturais)","como_vende":"Vendedor de rua e representante","loja_virtual":"Não possui","erp":"Omie",
  "vendedores":"2 a 5 internos","time_total":"1 a 10 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Natural Health produz <b>sucos naturais</b> e está <b>entrando no atacado</b> &mdash; produto de giro com recompra recorrente.",
   "A venda é por <b>vendedor de rua e representante</b> &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Não há canal digital: a expansão para o atacado depende de mais vendedores."],
  "pushpull":("A demanda é <b>puxada</b>: o ponto de venda recompra suco de giro &mdash; produto que sai sempre. Para <b>entrar no atacado sem "
              "inchar o time</b>, um portal B2B é a alavanca: o cliente monta o pedido sozinho e o vendedor foca em abrir novos pontos."),
  "conta":("Escalar o atacado com vendedor de rua tem teto na equipe. Um portal B2B <b>digitaliza a recompra</b> e permite multiplicar pontos de "
           "venda sem contratar proporcionalmente &mdash; exatamente a fase de crescimento da Natural Health."),
  "significa":("A Natural Health tem produto de giro e está escalando: <b>recompra recorrente, entrada no atacado e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Omie","Natural Health")},

 {"slug":"ccn","theme":"dark","food":True,"empresa":"CCN Distribuidora","contato":"Marina Barreto","cargo_area":"Atacado distribuidor (mercados e padarias)","local":"Brasil",
  "sobre":("A CCN Distribuidora abastece <b>mercados e padarias</b>, com venda externa e porte robusto (faixa de R$ 50 a 500 milhões/ano). "
           "Catálogo de itens de giro do varejo alimentar, com recompra recorrente e loja online."),
  "sobre_fonte":"Fontes: site novamixnf.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Mercados e padarias","como_vende":"Venda externa","loja_virtual":"Possui","erp":"Outro (não informado)",
  "vendedores":"6 a 20 internos","time_total":"+151 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A CCN abastece <b>mercados e padarias</b> &mdash; recompra recorrente e de alto volume do varejo alimentar.",
   "A venda é <b>externa</b> &mdash; e a dor é <b>vendedor gasta tempo só tirando pedido</b>.",
   "Já há loja online, mas a maior parte da recompra ainda passa pela rota do vendedor."],
  "pushpull":("A demanda é <b>puxada</b>: mercado e padaria recompram item de giro toda semana &mdash; sabem o que precisam. Com <b>vendedor só "
              "tirando pedido</b> e você dizendo que o cliente <b>compraria sozinho</b>, o potencial de digitalizar a maior parte dos pedidos é altíssimo."),
  "conta":("Reposição de mercado é repetida e previsível &mdash; ocupar 6 a 20 vendedores com isso é o desperdício mais caro de um distribuidor "
           "desse porte. Um portal B2B <b>tira a recompra da rota</b> e transforma o time em venda ativa."),
  "significa":("A CCN tem porte e recompra do varejo alimentar: <b>alto giro, cliente que compra sozinho e um time grande que pode sair de tirar pedido para vender.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="CCN Distribuidora")},

 {"slug":"grupo-rj","theme":"light","food":False,"empresa":"Grupo RJ","contato":"Zé Carlos","cargo_area":"Automação comercial e PDV","local":"Brasil",
  "sobre":("O Grupo RJ (PDV em Foco) fornece <b>soluções de automação comercial e PDV</b> (equipamentos e insumos de ponto de venda) para "
           "<b>empresas de médio e grande porte</b>, buscando alcançar novos perfis de cliente. Insumos de PDV têm recompra recorrente."),
  "sobre_fonte":"Fontes: site pdvemfoco.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Empresas de médio e grande porte (automação/PDV)","como_vende":"Contato direto","loja_virtual":"Possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 1 mi a R$ 5 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "O Grupo RJ fornece <b>automação comercial e PDV</b> &mdash; equipamentos e <b>insumos</b> (bobinas, etiquetas) de recompra recorrente.",
   "A venda é por <b>contato direto</b> &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Tem loja virtual, mas a recompra de insumo do cliente ainda se mistura nos canais."],
  "pushpull":("A demanda do <b>insumo de PDV</b> é <b>puxada</b>: a empresa repõe bobina/etiqueta sempre &mdash; sabe o que precisa. Você nos disse "
              "que o cliente <b>compraria sozinho</b>; um portal B2B organiza o pedido que hoje se perde e digitaliza a recompra recorrente, abrindo espaço para novos perfis."),
  "conta":("Insumo de PDV é recompra repetida &mdash; pedido desorganizado vira retrabalho. Um canal B2B <b>padroniza a recompra</b> e libera o "
           "time para prospectar os novos perfis que o Grupo RJ quer alcançar."),
  "significa":("O Grupo RJ tem recompra de insumo e quer crescer: <b>insumo de PDV que se repõe, cliente que compra sozinho e foco declarado em novos perfis.</b>"),
  "pot_low":"R$ 140 mil","pot_high":"R$ 700 mil","deixa_mes":"R$ 11,7 mil a R$ 58 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Grupo RJ")},

 {"slug":"macal","theme":"dark","food":False,"empresa":"Macal Madeiras","contato":"Guilherme Caus","cargo_area":"Distribuição de madeiras e materiais para construção","local":"Belo Horizonte, MG",
  "sobre":("A Macal Madeiras é <b>distribuidora de madeiras e materiais para construção</b> de Belo Horizonte (MG), atendendo <b>engenheiros, "
           "obras e consumidor final</b>. Produto de recompra conforme o andamento das construções, com loja online."),
  "sobre_fonte":"Fontes: site macalmadeiras.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Engenheiros, obras e consumidor final","como_vende":"WhatsApp e telefone","loja_virtual":"Possui","erp":"Outro (não informado)",
  "vendedores":"6 a 20 internos","time_total":"21 a 100 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Macal distribui <b>madeiras e materiais para construção</b> para engenheiros, obras e consumidor &mdash; recompra conforme a obra avança.",
   "A venda roda por <b>WhatsApp e telefone</b>, com 6 a 20 vendedores &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Tem loja online, mas a recompra profissional (engenheiro/obra) ainda passa pelo atendimento."],
  "pushpull":("A demanda é <b>puxada</b>: engenheiro e obra recompram material conforme o cronograma &mdash; sabem a especificação. Um portal B2B "
              "com tabela do profissional digitaliza a recompra e <b>escala sem contratar</b>, exatamente a dor declarada."),
  "conta":("Atender a recompra por WhatsApp/telefone com vários vendedores tem teto na equipe. Um portal B2B <b>tira a recompra do atendimento "
           "manual</b> e libera o time para projetos maiores."),
  "significa":("A Macal tem recompra do setor de construção: <b>material de giro, cliente profissional e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Macal Madeiras")},
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
