# -*- coding: utf-8 -*-
import os
import gen  # motor oficial: build_html + TEMPLATE
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)

l = {
    "slug": "coop-caixas-sul",
    "theme": "dark",
    "empresa": "CAAF",
    "contato": "Edson",
    "cargo_area": "Cooperativa de agricultura familiar — hortifrúti e agroindustrializados",
    "local": "Caxias do Sul, RS",
    "telefone": "",
    "site": "caaf.coop.br",
    "sobre": (
        "A CAAF — Cooperativa de Agricultores e Agroindústrias Familiares de Caxias do Sul — reúne mais de "
        "300 famílias cooperadas e 18 agroindústrias associadas da Serra Gaúcha. O catálogo vai do hortifrúti "
        "in natura (uva, tomate, abóbora, feijão, alface, radicchio, repolho) e da linha de minimamente "
        "processados embalados a vácuo aos agroindustrializados das associadas — pães, pão de polvilho, "
        "massas, tortéi, bolos, cucas, biscoitos, chimias e extrato de tomate. O grosso da operação é "
        "institucional: abastece a alimentação escolar de 205 escolas das redes estadual e municipal de "
        "Caxias do Sul e região, além de hospitais, quartéis e prefeituras, via PNAE e PAA. A 'Feira em Casa' "
        "atende, em paralelo, o consumidor final com cestas a domicílio."
    ),
    "sobre_fonte": "Fontes: site oficial caaf.coop.br e feiraemcasa.caaf.coop.br, Sescoop/RS, contrato PNAE IFRS 210/2025 e Instagram (@caafcaxias) — cruzados com o diagnóstico comercial Zydon.",
    "vende_para": "Escolas, hospitais, quartéis e prefeituras (institucional/atacado via PNAE e PAA)",
    "como_vende": "Chamadas públicas e contratos institucionais + entregas recorrentes",
    "loja_virtual": "Sim (B2C — Feira em Casa)",
    "vendedores": "Equipe própria da cooperativa",
    "time_total": "300+ famílias cooperadas e 18 agroindústrias",
    "faturamento": "Contratos institucionais recorrentes (PNAE/PAA)",
    "compra_sozinho": "A confirmar",
    "encontramos": [
        "Catálogo institucional de hortifrúti, minimamente processados e agroindustrializados (pães, massas, tortéi, chimias, extrato) que pode virar uma vitrine B2B com a tabela e a cota de contrato de cada escola, hospital ou secretaria já cadastradas para reposição direta.",
        "Mais de 205 escolas, além de hospitais e quartéis, repondo o mesmo mix de merenda em ciclos semanais previsíveis — base ideal para um portal de reposição recorrente sem montar cada pedido na planilha a cada entrega.",
        "Plataforma 'Feira em Casa' (feiraemcasa.caaf.coop.br) já no ar para o consumidor final, mas sem um canal B2B de autoatendimento que organize o pedido institucional recorrente e a separação por agroindústria associada.",
    ],
    "conta": (
        "Cada escola, hospital ou secretaria recompra o mesmo mix de hortifrúti e agroindustrializados em "
        "ciclos semanais previsíveis — mas hoje boa parte desse pedido institucional ainda é montada na mão, "
        "por planilha, telefone e e-mail, a cada chamada pública e a cada entrega. Com um portal B2B onde o "
        "comprador institucional repõe sozinho o mesmo mix, com a tabela e a cota de contrato dele, a CAAF "
        "transforma a entrega recorrente da merenda em fluxo automático, organiza a separação por agroindústria "
        "associada e libera a equipe do retrabalho de digitar pedido por pedido."
    ),
    "pot_low": "R$ 200 mil",
    "pot_high": "R$ 800 mil",
    "deixa_mes": "R$ 18 mil a R$ 65 mil",
    "pot_base": (
        "Estimativa baseada no volume de contratos institucionais recorrentes (205 escolas, hospitais e "
        "quartéis via PNAE/PAA) e na recuperação da reposição semanal via autoatendimento, no patamar de "
        "receita digital de cooperativas e distribuidores de alimentos que já abriram o canal B2B."
    ),
    "significa": (
        "Para a CAAF, abrir um canal B2B de autoatendimento significa tirar o pedido institucional da planilha "
        "e do telefone, dar ao comprador da escola, do hospital ou da secretaria a mesma facilidade que a "
        "'Feira em Casa' já oferece no varejo, e organizar a separação por agroindústria associada — sem "
        "depender de digitar cada reposição na mão."
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
        "A operação ainda empurra o pedido: mesmo com a 'Feira em Casa' no varejo, a reposição institucional "
        "das 205 escolas, hospitais e quartéis é montada por planilha, telefone e e-mail a cada chamada "
        "pública e a cada entrega. Como esses compradores repõem o mesmo mix de hortifrúti e "
        "agroindustrializados em ciclo semanal, digitalizar o canal de recompra faz o pedido passar a PUXAR — "
        "o próprio comprador institucional repõe a qualquer hora, com a tabela e a cota de contrato dele."
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
