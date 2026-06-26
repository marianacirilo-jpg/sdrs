# -*- coding: utf-8 -*-
"""Generate + render a single lead PDF using the official motor (gen.py + render.py)."""
import os, sys
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))  # motor/
PROJ = os.path.dirname(OUT)
sys.path.insert(0, OUT)
from gen import build_html

LEAD = {
    "slug": "lumaville",
    "theme": "dark",
    "empresa": "Luma Ville",
    "contato": "Lucilene",
    "cargo_area": "Confecção / Indústria têxtil (moda feminina)",
    "local": "Divinópolis, MG",
    "telefone": "",
    "site": "lumaville.com.br",
    "sobre": ("A Luma Ville (Confecções Luma Ville Indústria e Comércio Ltda) é uma indústria confeccionista "
              "de moda feminina sediada em Divinópolis/MG — um dos maiores polos atacadistas de jeans do país. "
              "Fundada em 1994, fabrica as próprias peças (marca Denim LV) e opera com showroom próprio e "
              "e-commerce. Sua operação combina venda direta ao consumidor e abastecimento de lojistas e "
              "revendedores."),
    "sobre_fonte": "econodata.com.br (CNPJ 00.336.481/0001-00), modanobrasil.com.br, lumaville.com.br/quem-somos + diagnóstico Zydon",
    "vende_para": "Lojistas e revendedores de moda (atacado B2B) + consumidor final (D2C)",
    "como_vende": "Showroom + e-commerce próprio + pedidos por WhatsApp/vendedor",
    "loja_virtual": "Sim (e-commerce próprio)",
    "vendedores": "2 a 5 internos",
    "time_total": "10 a 20 pessoas",
    "faturamento": "R$ 1 mi a R$ 5 mi por ano",
    "compra_sozinho": "A confirmar",
    "self_serve_resp": "",
    "dor": "",
    "encontramos": [
        "Catálogo digital B2B por coleção (jeans/moda feminina) com tabela de preço exclusiva por lojista e desconto por volume de peças",
        "Integração nativa com o Bling para sincronizar estoque, tabela de preços e pedidos em tempo real, sem retrabalho",
        "Self-service de pedidos e reposição de coleção para revendedores, com acompanhamento de produção e entrega",
    ],
    "detalhe": "",
    "conta": ("Cada pedido de atacado que passa pelo showroom ou WhatsApp consome 30 a 60 minutos de um vendedor "
              "e trava o atendimento de outras revendas. Num polo atacadista como Divinópolis, onde a revenda "
              "compra coleção o tempo todo, um portal B2B com tabela por lojista deixa a revendedora comprar "
              "sozinha, a qualquer hora — e libera o time para fechar novos clientes."),
    "pot_low": "R$ 500 mil", "pot_high": "R$ 1,5 mi",
    "deixa_mes": "R$ 42 mil a R$ 125 mil",
    "pot_base": ("Estimativa baseada em aumento de 10% a 15% na recompra digital de atacado + redução das horas "
                 "do time comercial gastas em tirar pedido. O número real depende da base de lojistas ativos e da "
                 "frequência de compra por coleção."),
    "significa": ("Um portal B2B com catálogo por coleção e tabela por revendedora recupera a recompra que hoje "
                  "fica presa no showroom e no WhatsApp."),
    "erp": "Bling",
    "erp_integ": "Bling — nativa",
    "erp_golive": "7 a 14 dias",
    "erp_dev": "Não (nativo)",
    "erp_line": ("A Zydon tem integração nativa com Sankhya, Omie, Olist e Bling — go-live mais rápido, "
                 "sem projeto customizado. ERPs diferentes são suportados sob avaliação."),
    "pushpull": ("Indústria confeccionista num polo atacadista: a demanda é parcialmente puxada pelas revendas que "
                 "compram coleção, mas o pedido ainda depende de showroom e vendedor. Um portal transforma a "
                 "recompra de coleção em fluxo puxado pela própria lojista."),
    "food": False,
}

# 1. Build + write HTML
html = build_html(LEAD)
html_path = os.path.join(OUT, "lumaville.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote", html_path)

# 2. Render to PDF
pdf_path = os.path.join(PROJ, "Potencial-Digitalizacao-lumaville.pdf")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("file://" + html_path, wait_until="networkidle")
    pg.pdf(path=pdf_path, width="210mm", height="297mm", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print("PDF:", pdf_path, os.path.getsize(pdf_path), "bytes")
