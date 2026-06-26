# -*- coding: utf-8 -*-
import os
import gen  # usa build_html + TEMPLATE do motor oficial

OUT = os.path.dirname(os.path.abspath(__file__))

lead = {
    "slug": "sustenpack",
    "theme": "dark",
    "empresa": "Sustenpack",
    "contato": "Moises",
    "cargo_area": "Embalagens sustentáveis para food service (indústria/fabricante)",
    "local": "Taboão da Serra, SP",
    "site": "sustenpack.com.br",
    "sobre": (
        "A Sustenpack é uma fabricante de embalagens sustentáveis para food service — biocopos, biopotes, "
        "biocanudos de papel, talheres e caixas personalizadas, com matéria-prima certificada FSC e produtos "
        "biodegradáveis, compostáveis ou recicláveis. Pertence ao Grupo Fulpel (mais de 30 anos de mercado), "
        "tem mais de 5.000 clientes ativos, produz 10 milhões de embalagens por mês e atende 27 estados. "
        "Sediada em Taboão da Serra/SP, atende redes de fast-food, restaurantes, dark kitchens, conveniência, "
        "supermercados, franquias nacionais e internacionais e grandes indústrias."
    ),
    "sobre_fonte": "site oficial sustenpack.com.br, LinkedIn e Econodata (CNPJ 33.709.396/0001-08) — cruzados com o diagnóstico comercial Zydon.",
    "vende_para": "Redes de fast-food, restaurantes (casual e fine dining), dark kitchens, conveniência, supermercados, franquias nacionais e internacionais e grandes indústrias (B2B)",
    "como_vende": "Venda direta e consultiva (telefone/e-mail) com representantes e vendedores internos + e-commerce para pequenas quantidades",
    "loja_virtual": "Sim",
    "vendedores": "Representantes + vendedores internos",
    "time_total": "51 a 150 pessoas",
    "faturamento": "R$ 10 mi a R$ 50 mi por ano",
    "compra_sozinho": "A confirmar",
    "erp": "Outro",
    "encontramos": [
        "Catálogo digital de embalagens por uso (copos, potes, canudos, talheres, caixas) com preço por volume e tabela personalizada por cliente",
        "Portal B2B para as redes e franquias fazerem pedido de reposição sozinhas, com a tabela e o crédito de cada conta, direto do celular",
        "Self-service de status de produção, faturamento e entrega para os mais de 5.000 clientes ativos",
    ],
    "conta": (
        "Cada pedido de reposição que chega por representante ou vendedor interno consome tempo da equipe. "
        "Com mais de 5.000 clientes e 10 milhões de embalagens por mês, a reposição das grandes redes é constante "
        "e previsível — o cenário ideal para autoatendimento. Um portal B2B transforma esse fluxo em receita "
        "recorrente sem depender de vendedor para cada pedido."
    ),
    "pot_low": "R$ 2 milhões",
    "pot_high": "R$ 8 milhões",
    "deixa_mes": "R$ 166 mil a R$ 666 mil",
    "pot_base": "Estimativa baseada em aumento de 10% a 15% na recompra digital das contas recorrentes + redução de fricção comercial da equipe de representantes e vendedores internos.",
    "significa": (
        "Um portal B2B de autoatendimento recupera a parcela da receita que se perde em fricção comercial nas "
        "mais de 5.000 contas que já compram da Sustenpack todos os meses."
    ),
    "erp_integ": "Integração sob projeto",
    "erp_golive": "30 a 60 dias",
    "erp_dev": "Sim (projeto)",
    "erp_line": (
        "A Zydon avalia a integração com o ERP desta operação sob projeto técnico. Prazo médio: 30 a 60 dias "
        "para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."
    ),
    "pushpull": (
        "Operação ainda empurrada por representantes e vendedores internos; o e-commerce recente puxa parte "
        "das pequenas quantidades. A reposição das grandes redes de food service é recorrente e previsível — "
        "o cenário ideal para virar fluxo puxado pelo próprio cliente num portal de autoatendimento."
    ),
    "food": False,
}

html = gen.build_html(lead)
path = os.path.join(OUT, f"{lead['slug']}.html")
with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML escrito:", path)
