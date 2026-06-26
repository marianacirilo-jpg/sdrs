# -*- coding: utf-8 -*-
import os
from gen import build_html  # motor oficial: build_html + TEMPLATE
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)
PDF_DIR = os.path.join(ROOT, "pdfs")

l = {
    "slug": "plasthome",
    "theme": "dark",
    "empresa": "Plasthome",
    "contato": "Paulo Granussio",
    "cargo_area": "Indústria e comércio de plásticos",
    "local": "Piracicaba, SP",
    "telefone": "",
    "site": "",
    "sobre": (
        "A Plasthome é uma indústria de plásticos de Piracicaba/SP em operação desde 1996 — quase 30 anos "
        "de mercado. A empresa combina a recuperação e o reprocessamento de materiais plásticos (reciclagem) "
        "com a fabricação de artefatos plásticos de uso doméstico e de escovas, pincéis e vassouras, além do "
        "comércio atacadista de resinas, elastômeros e sucatas plásticas. É uma operação B2B de atacado: "
        "vende resina reciclada e artefatos para indústrias, revendas, distribuidores e comércio que "
        "recompram com recorrência."
    ),
    "sobre_fonte": (
        "Fontes: cadastro público CNPJ 01.371.759/0001-43 (Econodata), CNAE principal 3832-7/00 e secundárias "
        "— cruzados com as respostas no diagnóstico comercial Zydon."
    ),
    "vende_para": "Indústrias, supermercados, revendas, distribuidores (atacado B2B)",
    "como_vende": "Venda direta",
    "loja_virtual": "Não",
    "vendedores": "1 interno",
    "time_total": "1 a 10 pessoas",
    "faturamento": "R$ 1 milhão a R$ 5 milhões por ano",
    "compra_sozinho": "A confirmar",
    "encontramos": [
        "Catálogo digital de artefatos plásticos e resina reciclada por linha (utilidades domésticas, "
        "escovas e vassouras, resinas/elastômeros), com tabela e preço por cliente, para a revenda "
        "recomprar sem reorçar item a item a cada pedido.",
        "Portal B2B onde indústrias, revendas e distribuidores fazem o pedido de reposição sozinhos, "
        "24/7, com a tabela e o crédito deles já cadastrados — sem depender do único vendedor interno "
        "estar disponível.",
        "Acompanhamento de pedido, produção e entrega em autoatendimento para os clientes que recompram "
        "resina e artefatos plásticos de forma recorrente, tirando essa rotina do telefone e do WhatsApp.",
    ],
    "conta": (
        "Cada revenda e cada cliente industrial da Plasthome recompra os mesmos itens de plástico mês a mês, "
        "mas hoje cada pedido passa pelo único vendedor interno. Com um portal B2B onde o cliente repõe "
        "sozinho — com a tabela e o crédito dele já cadastrados — a recompra recorrente vira fluxo "
        "automático e o vendedor é liberado para abrir e desenvolver novas contas, sem contratar mais gente."
    ),
    "pot_low": "R$ 80 mil",
    "pot_high": "R$ 400 mil",
    "deixa_mes": "R$ 6 mil a R$ 33 mil",
    "pot_base": (
        "Estimativa baseada no faturamento anual de R$ 1 mi a R$ 5 mi e na recuperação da recompra recorrente "
        "de revendas e clientes industriais via autoatendimento, no patamar de receita digital de indústrias "
        "de plásticos que já abriram o canal B2B."
    ),
    "significa": (
        "Para a Plasthome, abrir um canal B2B de autoatendimento significa capturar a recompra recorrente de "
        "revendas e indústrias que hoje depende de um único vendedor interno, sem perder o relacionamento "
        "direto que sustenta a operação há quase 30 anos."
    ),
    "erp": "Outro",
    "erp_integ": "Sob projeto",
    "erp_golive": "30 a 60 dias",
    "erp_dev": "Sim (projeto)",
    "erp_line": (
        "A Zydon avalia a integração com 'Outro' sob projeto técnico. Prazo médio: 30 a 60 dias para go-live. "
        "ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."
    ),
    "pushpull": (
        "Hoje a operação empurra cada pedido: a venda é direta, sem loja virtual, e tudo passa pelo único "
        "vendedor interno. A revenda que recompra resina e artefatos plásticos todo mês ainda depende de "
        "alguém atender. Digitalizar o canal de recompra faz o pedido passar a PUXAR — o próprio cliente "
        "repõe, na tabela dele, a qualquer hora."
    ),
    "food": False,
}

html = build_html(l)
html_path = os.path.join(OUT, f"{l['slug']}.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML escrito:", html_path)

pdf_path = os.path.join(PDF_DIR, f"Potencial-Digitalizacao-{l['slug']}.pdf")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("file://" + html_path, wait_until="networkidle")
    pg.pdf(path=pdf_path, width="210mm", height="297mm", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print("PDF:", pdf_path)
