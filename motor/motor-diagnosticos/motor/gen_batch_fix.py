# -*- coding: utf-8 -*-
import os
from playwright.sync_api import sync_playwright
import gen
OUT=os.path.dirname(os.path.abspath(__file__)); DEST=os.path.join(OUT,"Potencial Digitalização B2B - MQLs")
GEN=("A Zydon integra <b>nativamente via API com Bling, Olist, Omie e Sankhya</b> &mdash; e conecta outros ERPs sob consulta. "
     "Seja qual for o sistema da {emp}, pedido, estoque e tabela passam a conversar em tempo real com o portal.")
NAT=("Nativa via API","20 a 30 dias","Zero. Sem projeto de TI")

LEADS=[
 {"slug":"rede-centersul","theme":"light","food":False,"empresa":"Rede Centersul","contato":"Edson Friedrich","cargo_area":"Varejo de material de construção","local":"Sinop, MT",
  "sobre":("A Rede Centersul é uma <b>loja de material de construção</b> de Sinop (MT), no mercado desde <b>2011</b>. Atende da fundação ao "
           "acabamento &mdash; <b>elétrico, hidráulico, tintas, ferragens, cerâmica, iluminação e ferramentas</b> &mdash; com entrega na região e atendimento a obras e profissionais."),
  "sobre_fonte":"Fontes: site redecentersul.com.br, registro público (CNPJ 07.693.981/0002-20) e respostas do diagnóstico Zydon.",
  "vende_para":"Consumidor final, obras e profissionais da construção","como_vende":"Presencial e WhatsApp","loja_virtual":"Não possui","erp":"Outro (não informado)",
  "vendedores":"2 a 5 internos","time_total":"11 a 25 pessoas","faturamento":"R$ 5 mi a R$ 10 mi","compra_sozinho":"Hoje acredita que não",
  "encontramos":[
   "A Rede Centersul vende <b>material de construção completo</b> &mdash; do básico ao acabamento &mdash; para consumidor, obras e profissionais que <b>recompram conforme a obra avança</b>.",
   "A venda é <b>presencial e WhatsApp</b> &mdash; e a dor é <b>pedidos desorganizados</b> (WhatsApp, telefone, planilha).",
   "Não há loja virtual. Cada pedido de profissional/obra é remontado à mão, com retrabalho e risco de erro."],
  "pushpull":("Tem os dois lados: o consumidor final é mais reativo, mas o <b>profissional e a obra</b> recompram material de forma recorrente "
              "conforme o cronograma &mdash; demanda puxada. É nessa recompra B2B que um portal entra: o profissional monta o pedido sozinho, "
              "sem ocupar o balcão, e o time foca na venda de maior valor."),
  "conta":("Pedido de obra por WhatsApp/telefone vira retrabalho e erro de quantidade &mdash; e em construção erro é troca e atraso. Um canal de "
           "recompra para o profissional <b>organiza o pedido, reduz erro</b> e tira a reposição repetida do balcão."),
  "significa":("A Rede Centersul tem recompra de profissionais e obras: <b>catálogo amplo, cliente que repõe conforme a obra e uma dor direta de pedidos desorganizados.</b>"),
  "pot_low":"R$ 700 mil","pot_high":"R$ 1,4 mi","deixa_mes":"R$ 58 mil a R$ 117 mil",
  "pot_base":"14% aplicado sobre a faixa de faturamento informada (R$ 5 mi a R$ 10 mi), com base no benchmark de distribuidores já digitalizados.",
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Rede Centersul")},

 {"slug":"grupo-obbia","theme":"dark","food":False,"empresa":"Grupo Obbia","contato":"João César","cargo_area":"Indústria de moda fitness","local":"Brasil",
  "sobre":("O Grupo Obbia é <b>indústria de moda fitness</b>, pioneiro no setor no Brasil desde <b>1986</b>. Vende para <b>multimarcas do "
           "vestuário</b> e online, com tecidos tecnológicos e coleções próprias, atendendo o varejo de moda fitness em todo o país."),
  "sobre_fonte":"Fontes: site obbia.com.br, varejo (Zattini), Instagram @obbiaoficial e respostas do diagnóstico Zydon.",
  "vende_para":"Multimarcas do vestuário (moda fitness)","como_vende":"Representantes","loja_virtual":"Possui","erp":"Outro (não informado)",
  "vendedores":"1 interno","time_total":"+151 pessoas","faturamento":"A confirmar (ver nota)","compra_sozinho":"Cliente compraria sozinho",
  "encontramos":[
   "O Grupo Obbia é <b>marca consolidada de moda fitness desde 1986</b>, vendendo para multimarcas do vestuário &mdash; lojista que recompra coleção e itens de giro.",
   "A venda é por <b>representantes</b> &mdash; e a dor é <b>dificuldade de escalar sem contratar mais gente</b>.",
   "Já tem e-commerce (B2C), mas a recompra do lojista multimarca ainda depende do representante."],
  "pushpull":("A demanda é <b>puxada</b>: a multimarca recompra moda fitness de giro e novas coleções &mdash; marca desejada que o lojista quer ter "
              "na loja. Você nos disse que o cliente <b>compraria sozinho</b>; com marca forte assim, um portal B2B digitaliza a recompra do "
              "lojista e <b>escala a distribuição sem contratar</b>, exatamente a dor declarada."),
  "conta":("A recompra da multimarca depende da agenda do representante &mdash; teto baixo para uma marca nacional. Um portal B2B onde o lojista "
           "monta o pedido sozinho <b>escala a recompra</b> e libera o time para abrir novos pontos de venda."),
  "significa":("O Grupo Obbia tem marca forte e recompra de multimarcas: <b>moda fitness desejada desde 1986, lojista que compra sozinho e uma dor direta de escalar sem contratar.</b>"),
  "pot_low":"R$ 1,4 mi","pot_high":"R$ 7 mi","deixa_mes":"R$ 117 mil a R$ 583 mil",
  "pot_base":("Estimativa conservadora (faixa de R$ 10 a 50 mi). O faturamento informado no formulário (até R$ 250 mil) destoa do porte da "
              "empresa (+151 colaboradores e marca nacional desde 1986) &mdash; recomendamos recalcular com o faturamento real."),
  "erp_integ":NAT[0],"erp_golive":NAT[1],"erp_dev":NAT[2],"erp_line":GEN.format(emp="Grupo Obbia")},
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
