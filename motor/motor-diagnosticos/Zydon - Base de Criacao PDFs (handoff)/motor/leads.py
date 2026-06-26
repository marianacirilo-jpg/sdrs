# -*- coding: utf-8 -*-
# Dados dos 4 leads do piloto (MQLs 12-13/06/2026), com pesquisa web e potencial calculado.

LEADS = [
    {
        "slug": "nacional-carnes",
        "theme": "dark",
        "empresa": "Nacional Carnes",
        "contato": "Junior Sandes",
        "cargo_area": "Distribuição de proteína animal e alimentos",
        "local": "Teresina, PI",
        "telefone": "+55 86 99968-5515",
        "site": "nacionalcarness.com.br",
        "sobre": ("A Nacional Carnes (Distribuidora de Alimentos Nacional Carnes Ltda) atua desde 2010 "
                  "no <b>atacado distribuidor de alimentos</b>, com base em Teresina e operação por "
                  "<b>4 filiais</b> no Piauí (Teresina e Parnaíba). Abastece food service e varejo "
                  "alimentar &mdash; o maior segmento do atacado distribuidor do país."),
        "sobre_fonte": "Fontes: site/registro público (CNPJ 11.697.339/0001-05) e respostas do diagnóstico Zydon.",
        "vende_para": "Restaurantes, bares, padarias, mercados, supermercados, frigoríficos e hotéis",
        "como_vende": "Venda externa (RCAs)",
        "loja_virtual": "Não possui",
        "vendedores": "2 a 5 internos",
        "time_total": "51 a 150 pessoas",
        "faturamento": "R$ 50 mi a R$ 500 mi",
        "compra_sozinho": "Cliente compraria sozinho",
        "self_serve_resp": "sim",
        "dor": "Minha carteira de clientes está parada",
        "encontramos": [
            "A Nacional Carnes distribui alimentos para <b>restaurantes, mercados, supermercados, padarias e hotéis</b> &mdash; cliente que repõe estoque toda semana, o ano inteiro.",
            "A venda hoje roda na <b>venda externa via RCAs</b>, com apenas <b>2 a 5 vendedores internos</b> sustentando o pedido de uma operação de mais de 50 pessoas e 4 filiais.",
            "Não existe loja virtual. <b>O pedido depende do representante ir até o cliente.</b> Fora da rota, a recompra esfria."
        ],
        "detalhe": ("O próprio Junior apontou a dor: <b>a carteira de clientes está parada</b>. E respondeu que o "
                    "cliente <b>compraria sozinho</b>. Ou seja: a demanda de recompra existe &mdash; falta o canal "
                    "para ela acontecer sem depender da rota do representante."),
        "conta": ("Quando a recompra depende da visita do RCA, o teto é o nº de visitas que a equipe faz na semana. "
                  "Cliente que precisa repor no domingo, à noite ou entre uma rota e outra <b>simplesmente não pede</b> &mdash; "
                  "ou pede no concorrente que atende. Carteira parada quase sempre é carteira sem canal de recompra."),
        "pot_low": "R$ 7 mi", "pot_high": "R$ 70 mi",
        "deixa_mes": "R$ 580 mil a R$ 5,8 mi",
        "pot_base": "14% aplicado sobre a faixa de faturamento informada (R$ 50 mi a R$ 500 mi), com base no benchmark de distribuidores já digitalizados.",
        "significa": ("A Nacional Carnes está no perfil exato que mais cresce com digitalização: <b>distribuidor de alimentos "
                      "com entrega, no maior segmento do país, com cliente que recompra toda semana e que já compraria sozinho.</b>"),
        "erp": "TOTVS",
        "erp_integ": "Sob consulta",
        "erp_golive": "Sob avaliação",
        "erp_dev": "Escopo caso a caso",
        "erp_line": ("A Nacional Carnes roda no <b>TOTVS</b> &mdash; e a integração com o TOTVS é avaliada <b>sob consulta</b>. "
                     "A Zydon conecta o portal ao ERP para sincronizar estoque, tabela de preço, regras comerciais e pedidos, "
                     "com o escopo validado caso a caso pelo time técnico."),
        "pushpull": ("A venda hoje é <b>empurrada pelo RCA</b>, mas a demanda é <b>puxada</b>: food service recompra toda semana "
                     "e o próprio Junior diz que o cliente <b>compraria sozinho</b>. Quando a demanda é de recompra, o potencial de "
                     "digitalizar a maior parte dos pedidos é alto &mdash; o RCA deixa de só tirar pedido e vira gestor de carteira."),
    },
    {
        "slug": "clsp-distribuidora",
        "theme": "light",
        "empresa": "CLSP Distribuidora",
        "contato": "Ericka Monti",
        "cargo_area": "Distribuição de equipamentos e produtos para saúde",
        "local": "São Paulo, SP",
        "telefone": "+55 11 99892-3348",
        "site": "clsp.com.br",
        "sobre": ("A CLSP (Comércio e Distribuição de Equipamentos e Produtos para Saúde Ltda) atua desde 2010 como "
                  "<b>a maior distribuidora de produtos NSK e da linha DMC Laser</b> no Brasil. Vende equipamentos "
                  "odontológicos e de saúde a profissionais e clínicas, com catálogo técnico e cursos de apoio."),
        "sobre_fonte": "Fontes: site clsp.com.br, registro público (CNPJ 12.456.013/0001-59) e respostas do diagnóstico Zydon.",
        "vende_para": "Profissionais e clínicas da área da saúde (odontologia)",
        "como_vende": "Anúncio Meta + atendimento",
        "loja_virtual": "Não possui",
        "vendedores": "6 a 20 internos",
        "time_total": "11 a 25 pessoas",
        "faturamento": "R$ 1 mi a R$ 5 mi",
        "compra_sozinho": "Hoje acredita que não",
        "self_serve_resp": "nao",
        "dor": "Vendedores gastam tempo só tirando pedido",
        "encontramos": [
            "A CLSP distribui equipamentos e insumos para <b>dentistas, clínicas e profissionais de saúde</b> &mdash; compra técnica e recorrente, com reposição de consumíveis.",
            "A entrada de demanda vem de <b>anúncio no Meta</b>, mas o pedido fecha no atendimento: são <b>6 a 20 vendedores internos</b>, boa parte do tempo <b>só tirando pedido</b>.",
            "Não há loja virtual. Cada reposição simples de consumível ocupa um vendedor que poderia estar fechando equipamento de ticket alto."
        ],
        "detalhe": ("A Ericka foi sincera: hoje <b>não acredita</b> que o cliente compraria sozinho. Faz sentido em venda técnica. "
                    "Mas a dor declarada &mdash; <b>vendedores gastam tempo só tirando pedido</b> &mdash; mostra onde o autoatendimento entra: "
                    "não para vender o equipamento complexo, e sim para tirar a <b>reposição repetida</b> das costas do time."),
        "conta": ("Cada consumível recomprado por telefone custa o tempo de um vendedor técnico. Esse mesmo tempo, aplicado em "
                  "equipamento NSK/DMC de ticket alto, vale muito mais. <b>Autoatendimento na reposição libera o time para a venda "
                  "consultiva</b> &mdash; sem perder o toque humano onde ele realmente importa."),
        "pot_low": "R$ 140 mil", "pot_high": "R$ 700 mil",
        "deixa_mes": "R$ 12 mil a R$ 58 mil",
        "pot_base": "14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
        "significa": ("A CLSP tem o cenário ideal para um canal digital de <b>reposição</b>: catálogo técnico definido, cliente "
                      "profissional que sabe o que quer e recompra consumível com frequência &mdash; tudo o que o autoatendimento resolve bem."),
        "erp": "Omie",
        "erp_integ": "Nativa via API",
        "erp_golive": "20 a 30 dias",
        "erp_dev": "Zero. Sem projeto de TI",
        "erp_line": ("A CLSP roda no <b>Omie</b> &mdash; e a Zydon tem <b>integração nativa via API com o Omie</b>. "
                     "Catálogo, preço, cliente e pedido sincronizados em tempo real, sem desenvolvimento e sem retrabalho."),
        "pushpull": ("A venda do <b>equipamento</b> é consultiva (e deve seguir sendo). Mas a <b>reposição de consumível</b> é "
                     "puxada pelo cliente e hoje ocupa vendedor tirando pedido. É exatamente na recompra que dá para digitalizar "
                     "<b>70% a 90% dos pedidos</b> &mdash; sem tocar na venda técnica de ticket alto."),
    },
    {
        "slug": "construfort",
        "theme": "dark",
        "empresa": "Construfort",
        "contato": "Ricardo Sampaio",
        "cargo_area": "Distribuição de materiais de construção",
        "local": "Fortaleza, CE",
        "telefone": "+55 85 98771-0073",
        "site": "construfort.net.br",
        "sobre": ("Fundada em 1996, a Construfort é uma das <b>maiores distribuidoras de materiais de construção do Ceará</b>, "
                  "com <b>mais de 3.000 itens</b> em mix e <b>frota logística própria</b>. Tem presença digital ativa "
                  "(mais de 7 mil seguidores no Instagram) e posicionamento de referência regional em qualidade e atendimento."),
        "sobre_fonte": "Fontes: site/registro público (CNPJ 01.048.599/0001-04), Instagram @construfortoficial e respostas do diagnóstico Zydon.",
        "vende_para": "Lojas de materiais de construção e revendas",
        "como_vende": "Presencial",
        "loja_virtual": "Não possui",
        "vendedores": "21 a 100 internos",
        "time_total": "51 a 150 pessoas",
        "faturamento": "R$ 10 mi a R$ 50 mi",
        "compra_sozinho": "Ainda não sabe",
        "self_serve_resp": "naosei",
        "dor": "Dificuldade de escalar sem contratar mais gente",
        "encontramos": [
            "A Construfort distribui <b>mais de 3.000 itens</b> de construção com <b>frota própria</b> para lojas e revendas do Ceará &mdash; volume e recompra altos.",
            "A venda é <b>presencial</b>, sustentada por um time grande: <b>21 a 100 vendedores internos</b>. Crescer hoje significa <b>contratar mais gente</b>.",
            "Não há loja virtual. Com 3.000 SKUs, o catálogo vive na cabeça do vendedor &mdash; o que limita o ticket e trava a escala."
        ],
        "detalhe": ("O Ricardo apontou a dor central: <b>dificuldade de escalar sem contratar mais gente</b>. Com 3.000 itens e "
                    "venda 100% presencial, cada real a mais de faturamento puxa mais um vendedor. <b>É justamente o gargalo que "
                    "um canal digital quebra:</b> mais pedidos sem proporcionalmente mais headcount."),
        "conta": ("Quando a venda é presencial, o teto de crescimento é o tamanho do time. Cliente que quer repor um item de "
                  "3.000 do catálogo, conferir preço ou pedir fora do horário <b>espera o vendedor</b>. Com catálogo digital na mão, "
                  "o cliente monta o pedido sozinho e o vendedor foca em ticket e novas contas &mdash; escala sem inflar a folha."),
        "pot_low": "R$ 1,4 mi", "pot_high": "R$ 7 mi",
        "deixa_mes": "R$ 117 mil a R$ 583 mil",
        "pot_base": "14% aplicado sobre a faixa de faturamento informada (R$ 10 mi a R$ 50 mi), com base no benchmark de distribuidores já digitalizados.",
        "significa": ("A Construfort tem tudo para escalar por canal digital: <b>mix amplo (3.000+ itens), logística própria, "
                      "marca regional forte e cliente que recompra.</b> Falta tirar o catálogo da boca do vendedor e colocar na mão do cliente."),
        "erp": "TOTVS",
        "erp_integ": "Sob consulta",
        "erp_golive": "Sob avaliação",
        "erp_dev": "Escopo caso a caso",
        "erp_line": ("A Construfort roda no <b>TOTVS</b> &mdash; e a integração com o TOTVS é avaliada <b>sob consulta</b>. "
                     "Validado o escopo, os 3.000+ itens, com preço e estoque, sobem para o portal e ficam sincronizados em tempo real."),
        "pushpull": ("A venda presencial hoje <b>empurra</b>, mas o cliente (loja/revenda) <b>recompra item de catálogo o tempo "
                     "todo</b> &mdash; demanda puxada. Digitalizar a recompra tira o vendedor do papel de tirador de pedido e o "
                     "libera para diferenciação, ticket e novas contas. Potencial alto de digitalizar o grosso dos pedidos."),
    },
    {
        "slug": "zotto-comercial",
        "theme": "light",
        "empresa": "Zotto Comercial",
        "contato": "William Morila",
        "cargo_area": "Distribuição de bebidas e alimentos",
        "local": "São Paulo, SP",
        "telefone": "+55 11 94712-4771",
        "site": "zottocomercial.com.br",
        "sobre": ("A Zotto Comercial atua na <b>distribuição para supermercados, pequenos varejistas, adegas de bebidas e "
                  "grandes contas regionais</b>. É uma operação de atacado distribuidor com carteira mista &mdash; do pequeno "
                  "varejo ao key account &mdash; um perfil clássico de recompra recorrente."),
        "sobre_fonte": "Fonte: respostas do diagnóstico comercial Zydon (perfil digital público em construção).",
        "vende_para": "Supermercados, pequenos varejistas, adegas de bebidas e grandes contas regionais",
        "como_vende": "Vendedor externo",
        "loja_virtual": "Não possui",
        "vendedores": "1 interno",
        "time_total": "11 a 25 pessoas",
        "faturamento": "R$ 1 mi a R$ 5 mi",
        "compra_sozinho": "Hoje acredita que não",
        "self_serve_resp": "nao",
        "dor": "Pedidos chegam desorganizados (WhatsApp, telefone, planilha)",
        "encontramos": [
            "A Zotto distribui para <b>supermercados, pequenos varejistas e adegas</b>, além de grandes contas regionais &mdash; carteira que recompra o ano inteiro.",
            "A venda roda no <b>vendedor externo</b>, com apenas <b>1 pessoa interna</b> dando conta da retaguarda de uma carteira ampla.",
            "Os <b>pedidos chegam desorganizados</b> &mdash; WhatsApp, telefone e planilha &mdash; o que gera retrabalho, erro de digitação e pedido perdido."
        ],
        "detalhe": ("O William cravou a dor: <b>os pedidos chegam por WhatsApp, telefone e planilha</b> e viram bagunça. "
                    "Com <b>1 só pessoa interna</b>, cada pedido remontado à mão é tempo perdido e risco de erro. "
                    "Um canal digital padroniza a entrada do pedido e devolve esse tempo para o comercial."),
        "conta": ("Pedido que entra por três canais diferentes precisa ser redigitado, conferido e corrigido &mdash; e ainda assim "
                  "escapa. Cada erro de digitação é margem que vira troca, e cada pedido perdido no WhatsApp é recompra que foi "
                  "para o concorrente. <b>Canal digital único transforma a entrada do pedido em algo organizado e rastreável.</b>"),
        "pot_low": "R$ 140 mil", "pot_high": "R$ 700 mil",
        "deixa_mes": "R$ 12 mil a R$ 58 mil",
        "pot_base": "14% aplicado sobre a faixa de faturamento informada (R$ 1 mi a R$ 5 mi), com base no benchmark de distribuidores já digitalizados.",
        "significa": ("A Zotto tem o cenário onde o canal digital entrega valor rápido: <b>carteira que recompra, retaguarda enxuta "
                      "(1 pessoa) e pedidos hoje espalhados em três canais.</b> Organizar a entrada já destrava tempo e reduz perda."),
        "erp": "Outro (não informado)",
        "erp_integ": "Nativa via API",
        "erp_golive": "20 a 30 dias",
        "erp_dev": "Zero. Sem projeto de TI",
        "erp_line": ("A Zydon integra <b>nativamente via API com Bling, Olist, Omie e Sankhya</b> &mdash; e conecta outros ERPs, "
                     "como o TOTVS, <b>sob consulta</b>. Seja qual for o sistema da Zotto, pedido, estoque e tabela passam a "
                     "conversar em tempo real com o portal."),
        "pushpull": ("A venda é por <b>representante externo (empurra)</b>, mas a carteira recompra e os pedidos já chegam do cliente "
                     "por WhatsApp, telefone e planilha (<b>puxa</b>) &mdash; só que desorganizados. Organizar essa entrada digitaliza "
                     "a maior parte dos pedidos recorrentes e acaba com o retrabalho de 1 só pessoa na retaguarda."),
    },
]
