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
 {"slug":"hpr","theme":"light","food":False,"empresa":"HPR Representações","contato":"Henrique Pescara","cargo_area":"Representação comercial — setor automotivo","local":"Brasil",
  "sobre":("A HPR Representações atua como <b>representante comercial no setor automotivo</b>, atendendo <b>centros automotivos, mecânicas, "
           "autopeças, frotistas, usinas e transportadoras</b>. Conecta marcas e produtos do aftermarket a uma carteira que recompra conforme a manutenção das frotas."),
  "sobre_fonte":"Fontes: site mauer.com.br (marca representada), perfis públicos e respostas do diagnóstico Zydon.",
  "vende_para":"Centros automotivos, mecânicas, autopeças, frotistas e transportadoras","como_vende":"Ligação e visitas","loja_virtual":"Não possui","erp":"Omie",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A HPR atende <b>oficinas, autopeças, frotistas e transportadoras</b> &mdash; clientes que recompram peças e insumos por código conforme a manutenção.",
   "A venda roda por <b>ligação e visita</b>, com 1 pessoa na operação &mdash; e a dor é <b>vendedor gasta tempo só tirando pedido</b>.",
   "Não há canal digital: cada recompra técnica passa pelo contato."],
  "pushpull":("A demanda é <b>puxada e por código</b>: oficina e frotista sabem a peça que precisam e recompram na manutenção. Com <b>vendedor "
              "só tirando pedido</b>, é exatamente a recompra previsível que um portal digitaliza: o cliente monta o pedido por referência e o representante foca em abrir conta."),
  "conta":("Peça automotiva é compra por código e repetida &mdash; ocupar a operação com isso, sendo 1 pessoa, é o teto do negócio. Um portal "
           "por código <b>tira a recompra do telefone</b> e multiplica quantos clientes a HPR atende sem contratar."),
  "significa":("A HPR tem o caso forte de digitalização: <b>compra técnica por código, carteira que recompra e uma operação enxuta que precisa de alavanca.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":native("Omie","HPR")},

 {"slug":"ki-belleza","theme":"dark","food":False,"empresa":"Ki-belleza","contato":"Fabio Cota","cargo_area":"Distribuição de cosméticos e higiene","local":"Brasil",
  "sobre":("A Ki-belleza é <b>distribuidora de cosméticos, beleza e higiene</b>, atendendo <b>supermercados, farmácias e mercearias</b>. "
           "Opera com loja virtual e catálogo de itens de giro do varejo de beleza, com recompra recorrente."),
  "sobre_fonte":"Fontes: site kibelleza.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Supermercados, farmácias e mercearias","como_vende":"Vendedor presencial","loja_virtual":"Possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"1 a 10 pessoas","faturamento":"Até R$ 250 mil","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Ki-belleza distribui <b>cosméticos e higiene</b> para supermercados, farmácias e mercearias &mdash; itens de giro de recompra frequente.",
   "A venda é <b>presencial</b>, com 1 pessoa &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Tem loja virtual, mas a recompra do lojista (B2B) ainda depende da visita."],
  "pushpull":("A demanda é <b>puxada</b>: o varejo recompra os mesmos itens de beleza/higiene &mdash; sabe o que quer. Você nos disse que o "
              "cliente <b>compraria sozinho</b>: um portal B2B deixa o lojista repor sozinho e <b>escala a distribuição sem contratar</b>, exatamente a dor declarada."),
  "conta":("Reposição de cosmético é previsível &mdash; depender da visita presencial limita quantos pontos a operação de 1 pessoa atende. Um "
           "catálogo B2B <b>multiplica o alcance</b> sem aumentar a equipe."),
  "significa":("A Ki-belleza tem o perfil para escalar no digital: <b>itens de giro, recompra do varejo e cliente que já compraria sozinho com time enxuto.</b>"),
  "pot_low":"R$ 17 mil","pot_high":"R$ 35 mil","deixa_mes":"R$ 1,4 mil a R$ 2,9 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (até R$ 250 mil ao ano), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Ki-belleza")},

 {"slug":"valesul","theme":"light","food":False,"empresa":"Valesul Chevrolet","contato":"Clever Nabhan","cargo_area":"Concessionária e atacado de peças (GM)","local":"Curitiba, PR",
  "sobre":("A Valesul Chevrolet é <b>concessionária e distribuidora de peças automotivas (GM)</b> em Curitiba (PR), com operação de "
           "<b>peças e funilaria</b> que atende oficinas e funilarias. Opera com mais de 150 colaboradores e canal de peças B2B."),
  "sobre_fonte":"Fontes: site valesulchevrolet.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Oficinas, funilarias e autopeças","como_vende":"90% vendedores / 10% sistema","loja_virtual":"Possui","erp":"TOTVS",
  "vendedores":"21 a 100 internos","time_total":"+151 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Acredita que sim",
  "encontramos":[
   "A Valesul tem <b>operação de peças e funilaria (GM)</b> que abastece oficinas e funilarias &mdash; compra por código, técnica e recorrente na reparação.",
   "A venda ainda é <b>90% por vendedor</b> e só 10% por sistema &mdash; e a dor é <b>vendedor gasta tempo só tirando pedido</b>.",
   "Mesmo com loja virtual, a maior parte da recompra de peças passa pelo balcão/vendedor."],
  "pushpull":("A demanda é <b>puxada e por código</b>: a oficina sabe a peça GM que precisa (referência exata) e recompra na reparação. Com "
              "<b>90% da venda no vendedor</b> e a dor de só tirar pedido, há um potencial enorme de inverter para o digital: você acredita que "
              "o cliente <b>compraria sozinho</b>, e um portal por código move o grosso da recompra para o autoatendimento."),
  "conta":("Peça é compra por referência &mdash; manter 90% disso no vendedor é prender um time grande na digitação. Um portal por código "
           "<b>libera dezenas de vendedores</b> para venda ativa e captura a recompra 24/7, num volume de R$ 50 a 500 milhões."),
  "significa":("A Valesul tem o caso de maior alavanca: <b>compra por código, time grande preso em tirar pedido e cliente que compraria sozinho.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":SOB[0],"erp_golive":SOB[1],"erp_dev":SOB[2],"erp_line":sob("TOTVS","Valesul")},

 {"slug":"hiperpack","theme":"dark","food":False,"empresa":"Hiperpack","contato":"Guilherme Piccoli","cargo_area":"Distribuição de embalagens e descartáveis","local":"Caxias do Sul, RS",
  "sobre":("A Hiperpack é <b>distribuidora de embalagens e descartáveis</b> de Caxias do Sul (RS), atendendo <b>distribuidores e padarias</b>. "
           "Catálogo amplo de embalagem e descartável &mdash; insumo de giro com recompra recorrente do varejo e do food service."),
  "sobre_fonte":"Fontes: site hiperpack.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Distribuidores e padarias","como_vende":"Presencial","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"51 a 150 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Hiperpack distribui <b>embalagens e descartáveis</b> para distribuidores e padarias &mdash; insumo de giro que o cliente repõe sempre.",
   "A venda é <b>presencial</b> &mdash; e a dor declarada é <b>carteira de clientes parada</b>.",
   "Não há loja virtual. Fora da visita, a recompra de embalagem esfria."],
  "pushpull":("A demanda é <b>puxada</b>: padaria e distribuidor recompram embalagem e descartável de forma recorrente &mdash; sabem o que "
              "precisam. Carteira parada quase sempre é <b>carteira sem canal de recompra</b>: um portal B2B reativa essa recompra previsível sem depender da visita."),
  "conta":("Embalagem é compra repetida e de baixo valor unitário &mdash; depender do presencial para isso é caro e deixa a carteira esfriar. "
           "Um canal digital <b>reativa a recompra</b> e libera o vendedor para o que tem margem, num porte de R$ 50 a 500 milhões."),
  "significa":("A Hiperpack tem porte e recompra para o B2B digital: <b>insumo de giro, cliente que repõe sempre e uma carteira parada esperando um canal.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Hiperpack")},

 {"slug":"potencia","theme":"light","food":False,"empresa":"Potência Compensados","contato":"Alessandro Crestani","cargo_area":"Indústria de compensados de madeira","local":"Inácio Martins, PR",
  "sobre":("A Potência Compensados é <b>indústria de compensados de madeira</b> de Inácio Martins (PR). Fornece chapas e compensados para "
           "<b>distribuidoras, madeireiras e obras</b>, com fabricação própria e volume voltado à construção."),
  "sobre_fonte":"Fontes: site potenciamadeiras.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Distribuidoras de compensados, madeireiras e obras","como_vende":"WhatsApp","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"51 a 150 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Potência fabrica <b>compensados de madeira</b> para distribuidoras, madeireiras e obras &mdash; produto de recompra conforme o ritmo da construção.",
   "Os pedidos chegam por <b>WhatsApp</b>, com 1 pessoa na frente comercial &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Não há loja virtual. Cada pedido é remontado à mão, com risco de erro de medida/quantidade."],
  "pushpull":("A demanda é <b>puxada</b>: distribuidora e madeireira recompram chapa e compensado conforme a obra anda &mdash; sabem a "
              "especificação. Um portal B2B com catálogo e tabela <b>organiza o pedido</b> que hoje se perde no WhatsApp e padroniza a recompra, sem depender de uma só pessoa."),
  "conta":("Pedido de compensado por WhatsApp/telefone/planilha vira retrabalho e erro de medida &mdash; e erro em madeira é troca e frete. "
           "Um canal digital <b>padroniza o pedido e dá rastreabilidade</b>, liberando a operação enxuta para crescer."),
  "significa":("A Potência tem fabricação própria e recompra do setor de construção: <b>produto de giro, cliente profissional e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Potência Compensados")},

 {"slug":"social-pet","theme":"dark","food":False,"empresa":"Social Pet","contato":"Ricardo Martins","cargo_area":"Distribuição de produtos pet","local":"Vinhedo, SP",
  "sobre":("A Social Pet é <b>distribuidora atacadista de produtos pet</b> de Vinhedo (SP), no mercado desde 2009, atendendo <b>pet shops, "
           "clínicas veterinárias e agropecuárias</b>. Distribui marcas como PremieRpet e Zoetis, com infraestrutura logística moderna."),
  "sobre_fonte":"Fontes: site socialpet.com.br, Econodata (CNPJ 10.824.634/0001-12), Instagram da empresa e respostas do diagnóstico Zydon.",
  "vende_para":"Pet shops, clínicas veterinárias e agropecuárias","como_vende":"Visita de vendedor","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"+151 pessoas","faturamento":"R$ 50 mi a R$ 500 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Social Pet distribui <b>ração e produtos veterinários</b> (PremieRpet, Zoetis) para pet shops, clínicas e agropecuárias &mdash; recompra semanal e de alto giro.",
   "A venda é por <b>visita de vendedor</b>, e a dor é <b>vendedor gasta tempo só tirando pedido</b>.",
   "Não há loja virtual. Cada reposição de ração ocupa um vendedor."],
  "pushpull":("A demanda é fortemente <b>puxada</b>: pet shop e clínica recompram ração e itens de giro &mdash; produto que não pode faltar. "
              "Com <b>vendedor só tirando pedido</b>, é a recompra previsível que um portal digitaliza primeiro: o lojista monta o pedido sozinho "
              "e os vendedores passam a abrir conta e cuidar de carteira, num volume de R$ 50 a 500 milhões."),
  "conta":("Reposição de ração é repetida e previsível &mdash; ocupar a visita do vendedor com isso é o desperdício mais caro de um distribuidor "
           "desse porte. Um portal B2B <b>tira a recompra da rota</b> e transforma o time em vendas ativas."),
  "significa":("A Social Pet está no perfil que mais cresce com digitalização: <b>alto giro, recompra semanal e um time grande que pode sair de tirar pedido para vender.</b>"),
  "pot_low":"R$ 7 mi","pot_high":"R$ 70 mi","deixa_mes":"R$ 583 mil a R$ 5,8 mi",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Social Pet")},

 {"slug":"alvorada","theme":"light","food":False,"empresa":"Distribuidora Alvorada","contato":"Roger Debona","cargo_area":"Distribuição multicategoria (agro, construção, ferragens)","local":"Brasil",
  "sobre":("A Distribuidora Alvorada é <b>distribuidora regional multicategoria</b>, atendendo <b>agropecuárias, lojas de material de "
           "construção, ferragens e pequenos mercados</b>. Catálogo amplo de itens de giro, com recompra recorrente do varejo do interior."),
  "sobre_fonte":"Fontes: site distribuidoraalvorada.com.br e respostas do diagnóstico comercial Zydon.",
  "vende_para":"Agropecuárias, material de construção, ferragens e pequenos mercados","como_vende":"Vendedores externos","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"11 a 25 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "A Alvorada distribui <b>itens de agro, construção, ferragens e mercearia</b> para o varejo do interior &mdash; carteira que recompra de tudo um pouco, sempre.",
   "A venda é por <b>vendedor externo</b>, com retaguarda enxuta &mdash; e a dor é <b>perder vendas pela demora no atendimento</b>.",
   "Não há loja virtual. Fora da rota, o lojista repõe com quem responder primeiro."],
  "pushpull":("A demanda é <b>puxada</b>: o pequeno varejo recompra item de giro &mdash; sabe o que quer e quando. <b>Perder venda pela "
              "demora</b> é o sinal de que o cliente quer comprar e o atendimento não chega a tempo. Você nos disse que ele <b>compraria sozinho</b>: "
              "um portal B2B captura essa recompra 24/7 sem depender da rota."),
  "conta":("Carteira multicategoria com vendedor externo tem teto na agenda do time &mdash; e cada demora é venda que vai pro concorrente. Um "
           "catálogo B2B <b>captura a recompra fora da rota</b> e multiplica o alcance da operação enxuta."),
  "significa":("A Alvorada tem o cenário onde o digital paga rápido: <b>varejo que recompra de tudo, cliente que compraria sozinho e uma dor clara de venda perdida por demora.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Distribuidora Alvorada")},

 {"slug":"apolo","theme":"dark","food":False,"empresa":"Apolo Algodão","contato":"Rodrigo Lanna Neto","cargo_area":"Indústria têxtil de algodão e higiene","local":"Cataguases, MG",
  "sobre":("A Apolo (Companhia Manufatora de Tecidos de Algodão) é <b>indústria têxtil de algodão e produtos de higiene/beleza</b> de "
           "Cataguases (MG), fundada em <b>1943</b>. A marca Apolo é referência nacional em <b>algodão e cuidado pessoal</b>, atendendo os "
           "canais de varejo, perfumaria, farmácia e hospitalar."),
  "sobre_fonte":"Fontes: site apolo.net.br, varejo (Magazine Luiza), LinkedIn da empresa e respostas do diagnóstico Zydon.",
  "vende_para":"Distribuidores dos canais de varejo, perfumaria e farmácia","como_vende":"Representantes PJ","loja_virtual":"Não possui","erp":"TOTVS",
  "vendedores":"1 interno","time_total":"+151 pessoas","faturamento":"R$ 10 mi a R$ 50 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Apolo fabrica <b>algodão e produtos de higiene/beleza</b> (marca consolidada desde 1943) para distribuidores de varejo, perfumaria e farmácia &mdash; produto de recompra recorrente.",
   "A venda é por <b>representantes PJ</b>, e a dor declarada é diferente: <b>dependência de poucos clientes grandes</b>.",
   "Não há canal digital de pedido: a base de clientes menores fica difícil de atender com eficiência."],
  "pushpull":("A demanda é <b>puxada</b>: o distribuidor/varejo recompra algodão e itens de higiene &mdash; produto de giro constante. O ponto-chave "
              "aqui é a <b>concentração</b>: depender de poucos clientes grandes é risco. Um canal B2B digital permite atender <b>muitos clientes "
              "menores com baixo custo</b> &mdash; é assim que se dilui a dependência sem inchar a equipe de representantes."),
  "conta":("Atender cliente pequeno via representante custa caro &mdash; por isso a base se concentra nos grandes. Um portal B2B <b>torna viável "
           "vender para a cauda longa</b> de pequenos e médios, diluindo o risco de depender de poucos e aumentando o número de pedidos sem custo proporcional."),
  "significa":("A Apolo tem marca forte e produto de recompra, mas concentração de risco: <b>um canal B2B digital diversifica a carteira atendendo "
               "os pequenos com eficiência</b> &mdash; o caminho para reduzir a dependência dos grandes."),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":SOB[0],"erp_golive":SOB[1],"erp_dev":SOB[2],"erp_line":sob("TOTVS","Apolo")},
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
