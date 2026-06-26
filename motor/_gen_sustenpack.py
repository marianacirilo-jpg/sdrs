# -*- coding: utf-8 -*-
import os
import gen  # motor oficial: build_html + TEMPLATE
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)

l = {
    "slug": "sustenpack",
    "theme": "dark",
    "empresa": "Sustenpack",
    "contato": "Moises Gil",
    "cargo_area": "Fabricação de embalagens sustentáveis para food service",
    "local": "São Paulo, SP",
    "telefone": "",
    "site": "sustenpack.com.br",
    "sobre": (
        "A Sustenpack é referência nacional em embalagens sustentáveis para food service — biocopos, "
        "biocanudos de papel, talheres, caixas de pizza/hambúrguer/sushi e biopotes para sorvete e açaí, "
        "todos biodegradáveis, compostáveis ou recicláveis. Faz parte do Grupo Fulpel (mais de 30 anos no "
        "setor de papel e embalagem) e atende mais de 5.000 clientes ativos em 27 estados, de restaurantes "
        "e dark kitchens a grandes redes de varejo e franquias. Vende por loja virtual própria, contratos "
        "B2B com entrega programada e venda direta de atacado."
    ),
    "sobre_fonte": "Fontes: site oficial sustenpack.com.br e loja.sustenpack.com.br, LinkedIn e Instagram (@sustenpack) — cruzados com o diagnóstico comercial Zydon.",
    "vende_para": "Restaurantes, delivery, supermercados, distribuidores (atacado B2B)",
    "como_vende": "Representantes externos + vendedores internos (6 a 20)",
    "loja_virtual": "Sim",
    "vendedores": "6 a 20 internos",
    "time_total": "51 a 150 pessoas",
    "faturamento": "R$ 10 milhões a R$ 50 milhões por ano",
    "compra_sozinho": "A confirmar",
    "encontramos": [
        "Catálogo de food service por categoria (biocopos, biocanudos, talheres, caixas de pizza/hambúrguer/sushi, biopotes) que pode virar vitrine B2B com a tabela e o mix de cada cliente já salvos para recompra direta.",
        "Mais de 5.000 clientes ativos em 27 estados repondo o mesmo mix de embalagens em ciclos curtos — base ideal para um portal de reposição recorrente sem depender de representante a cada pedido.",
        "Loja virtual própria (loja.sustenpack.com.br) já no ar para pequenas quantidades, mas sem um canal B2B de autoatendimento que atenda o contrato com entrega programada dos grandes clientes food service.",
    ],
    "conta": (
        "Cada restaurante, rede ou dark kitchen recompra biocopos, biocanudos, marmitas/caixas e biopotes "
        "em ciclos curtos e previsíveis — mas hoje boa parte desse giro ainda passa por representante ou "
        "vendedor interno. Com um portal B2B onde o cliente repõe sozinho o mesmo mix, com a tabela e o "
        "crédito dele, a Sustenpack transforma a recompra recorrente do food service em fluxo automático e "
        "libera o comercial para abrir conta nova nos 27 estados."
    ),
    "pot_low": "R$ 300 mil",
    "pot_high": "R$ 1,2 milhão",
    "deixa_mes": "R$ 25 mil a R$ 100 mil",
    "pot_base": (
        "Estimativa baseada em faturamento anual de R$ 10 a 50 milhões e na recuperação da recompra "
        "recorrente de food service (restaurantes, redes e dark kitchens) via autoatendimento, no patamar "
        "de receita digital de fabricantes e distribuidores que já abriram o canal B2B."
    ),
    "significa": (
        "Para a Sustenpack, abrir um canal B2B de autoatendimento significa capturar a reposição recorrente "
        "de embalagens que hoje depende de representante e vendedor interno, e estender para a carteira de "
        "5.000+ clientes a mesma facilidade que a loja virtual já oferece no varejo."
    ),
    "erp": "Outro",
    "erp_integ": "Sob projeto",
    "erp_golive": "30 a 60 dias",
    "erp_dev": "Sim (projeto)",
    "erp_line": (
        "A Zydon avalia a integração com 'Outro' sob projeto técnico. Prazo médio: 30 a 60 dias para "
        "go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."
    ),
    "pushpull": (
        "A operação ainda empurra o pedido: mesmo com loja virtual no varejo, a reposição dos grandes "
        "clientes food service passa por representante e vendedor interno via contrato com entrega "
        "programada. Como restaurantes e dark kitchens recompram o mesmo mix de embalagens em ciclo curto, "
        "digitalizar o canal de recompra faz o pedido passar a PUXAR — o próprio cliente repõe biocopos, "
        "caixas e biopotes a qualquer hora, com a tabela dele."
    ),
    "food": True,
}

# 1) HTML pelo motor oficial
html = gen.build_html(l)
html_path = os.path.join(OUT, f"{l['slug']}.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML escrito:", html_path)

# 2) PDF via Playwright (210mm x 297mm, fundo, margem zero)
pdf_path = os.path.join(ROOT, "pdfs", f"Potencial-Digitalizacao-{l['slug']}.pdf")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("file://" + html_path, wait_until="networkidle")
    pg.pdf(path=pdf_path, width="210mm", height="297mm", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print("PDF escrito:", pdf_path)
