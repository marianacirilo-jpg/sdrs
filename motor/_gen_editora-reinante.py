# -*- coding: utf-8 -*-
import os
import gen  # motor oficial: build_html + TEMPLATE

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)

l = {
    "slug": "editora-reinante",
    "theme": "dark",
    "empresa": "Editora Reinante",
    "contato": "Bruno Silva",
    "cargo_area": "Edição e comercialização de livros (atacado B2B)",
    "local": "Rio de Janeiro, RJ",
    "telefone": "",
    "site": "editorareinante.com.br",
    "sobre": (
        "A Editora Reinante é uma editora brasileira sediada no Rio de Janeiro (RJ) que publica e "
        "comercializa livros. Como toda editora, o grosso da operação é B2B: o catálogo de títulos "
        "abastece livrarias, distribuidoras, escolas e redes de ensino, que revendem ou adotam as "
        "obras e repõem os títulos que mais giram. Cada título é, na prática, um SKU estável (um "
        "ISBN) que se repõe em ciclos — um mix recorrente de catálogo que hoje é trabalhado por "
        "representante comercial, pedido por WhatsApp, e-mail e telefone, e depois digitado no ERP."
    ),
    "sobre_fonte": "Fontes: domínio corporativo editorareinante.com.br e dados do diagnóstico comercial Zydon, cruzados com o modelo de distribuição B2B do mercado editorial brasileiro. Catálogo e porte a confirmar no diagnóstico completo.",
    "vende_para": "Livrarias, distribuidoras, escolas e redes de ensino (atacado B2B)",
    "como_vende": "Representantes comerciais + pedidos por WhatsApp, e-mail e telefone",
    "loja_virtual": "A confirmar",
    "vendedores": "A confirmar",
    "time_total": "A confirmar",
    "faturamento": "A confirmar no diagnóstico",
    "compra_sozinho": "A confirmar",
    "encontramos": [
        "Catálogo de títulos (cada obra = um ISBN) que pode virar uma vitrine B2B com a tabela de cada cliente, disponibilidade de estoque e lançamentos — pronto para a livraria ou escola montar o pedido sozinha.",
        "Reposição recorrente: livrarias repõem os títulos que mais giram em ciclos previsíveis, mas hoje cada reposição depende da visita ou do contato do representante comercial.",
        "Pedido ainda entra por WhatsApp, e-mail e telefone e é redigitado no ERP — sem um canal de autoatendimento que separe livraria, distribuidora e escola com a tabela e a condição de cada uma.",
    ],
    "conta": (
        "Cada livraria, distribuidora e escola recompra os mesmos títulos do catálogo da Reinante em "
        "ciclos previsíveis — mas hoje boa parte desse giro passa por representante, WhatsApp e "
        "planilha. Com um portal B2B onde o cliente consulta o catálogo, vê a disponibilidade e repõe "
        "sozinho o mix dele, com a tabela e o crédito certos, a Editora Reinante transforma a reposição "
        "recorrente de títulos em fluxo automático e libera o comercial para abrir conta nova e empurrar "
        "lançamentos para toda a carteira."
    ),
    "pot_low": "R$ 150 mil",
    "pot_high": "R$ 600 mil",
    "deixa_mes": "R$ 12 mil a R$ 50 mil",
    "pot_base": (
        "Estimativa ilustrativa para uma editora independente de pequeno/médio porte, baseada na "
        "recuperação da reposição recorrente de títulos (livrarias, distribuidoras e escolas) via "
        "autoatendimento, no patamar de receita digital de editoras e distribuidores que já abriram "
        "o canal B2B. O número real depende da carteira e do catálogo da Reinante."
    ),
    "significa": (
        "Para a Editora Reinante, abrir um canal B2B de autoatendimento significa capturar a reposição "
        "recorrente de títulos que hoje depende do representante e do pedido manual, e dar a cada "
        "livraria, distribuidora e escola um catálogo sempre disponível, com a tabela e a condição de "
        "cada uma."
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
        "A operação ainda empurra o pedido: a reposição dos títulos do catálogo passa por representante "
        "comercial, WhatsApp e telefone, e é redigitada no ERP. Como livrarias e escolas recompram os "
        "mesmos títulos em ciclos previsíveis, digitalizar o canal de recompra faz o pedido passar a "
        "PUXAR — a própria livraria consulta o catálogo, vê a disponibilidade e repõe o mix dela a "
        "qualquer hora, com a tabela dela."
    ),
    "food": False,
}

# 1) HTML pelo motor oficial
html = gen.build_html(l)
html_path = os.path.join(OUT, f"{l['slug']}.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML escrito:", html_path)

# 2) PDF via Playwright (210mm x 297mm, fundo, margem zero)
pdf_path = os.path.join(ROOT, "pdfs", f"Potencial-Digitalizacao-{l['slug']}.pdf")
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto("file://" + html_path, wait_until="networkidle")
        pg.pdf(path=pdf_path, width="210mm", height="297mm", print_background=True,
               margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        b.close()
    print("PDF escrito (playwright):", pdf_path)
except ModuleNotFoundError:
    # Fallback: mesmo motor de render (Chromium do Playwright) acionado headless via subprocess.
    # @page{size:210mm 297mm;margin:0} no template define a página; print-color-adjust:exact garante o fundo escuro.
    import glob, subprocess
    chrome = next(iter(glob.glob("/root/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")), None)
    if not chrome:
        raise RuntimeError("Nem playwright nem Chromium em cache encontrados")
    subprocess.run([
        chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
        "--no-pdf-header-footer", "--print-to-pdf-no-header",
        "--print-to-pdf=" + pdf_path, "file://" + html_path,
    ], check=True, capture_output=True)
    print("PDF escrito (chromium headless fallback):", pdf_path)
