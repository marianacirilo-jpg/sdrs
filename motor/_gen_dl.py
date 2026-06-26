# -*- coding: utf-8 -*-
"""Generate + render the DL Distribuidora PDF using the official motor (gen.py + render.py)."""
import os, sys
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))  # motor/
PROJ = os.path.dirname(OUT)
sys.path.insert(0, OUT)
from gen import build_html

l = {
    "slug": "dl-distribuidora",
    "theme": "dark",
    "empresa": "DL Distribuidora",
    "contato": "Daniel Pessoa",
    "cargo_area": "Distribuição de peças de motos (motopeças)",
    "local": "Recife, PE",
    "telefone": "",
    "site": "",
    "sobre": ("A DL Distribuidora é uma distribuidora de peças de motos (motopeças) da região de "
              "Recife/PE, listada no site oficial da Shineray do Brasil como concessionária de peças "
              "Shineray (CNPJ 12.482.805/0001-06). Opera no balcão e na rua, abastecendo oficinas e "
              "revendas com peças de reposição Shineray e multimarcas. A venda é feita por representante "
              "externo e WhatsApp/telefone, sem loja virtual."),
    "sobre_fonte": "shineray.com.br/_local/dl-distribuidora (CNPJ 12.482.805/0001-06), e-mail dldistripecas@dl.com.br, DDD 81 = Recife/PE + diagnóstico Zydon",
    "vende_para": "Oficinas de motos, mecânicos, revendas de peças e instaladores (atacado B2B)",
    "como_vende": "Representante externo + pedidos por telefone/WhatsApp",
    "loja_virtual": "Não",
    "vendedores": "1 a 3 internos",
    "time_total": "1 a 10 pessoas",
    "faturamento": "R$ 250 mil a R$ 500 mil por ano",
    "compra_sozinho": "A confirmar",
    "self_serve_resp": "",
    "dor": "",
    "encontramos": [
        "Catálogo digital B2B de motopeças filtrável por modelo, ano e cilindrada da moto (Shineray + multimarcas), com tabela e desconto por oficina",
        "Integração nativa com o Bling para mostrar estoque e preço em tempo real no portal, sem cotação manual por WhatsApp",
        "Self-service de recompra e reposição para oficinas e revendas, com histórico de pedidos e itens de desgaste recorrentes a um clique",
    ],
    "detalhe": "",
    "conta": ("Cada oficina recompra os mesmos itens de desgaste — óleo, filtro, pastilha, relação, "
              "lâmpada — toda semana, mas o representante externo só passa de vez em quando. Entre as "
              "visitas, o mecânico manda WhatsApp e o pedido vai para quem responder primeiro com preço "
              "e estoque. Um portal B2B com a tabela e o histórico de cada oficina deixa o cliente repor "
              "sozinho a qualquer hora, e devolve as horas que o representante gasta tirando pedido."),
    "pot_low": "R$ 50 mil", "pot_high": "R$ 250 mil",
    "deixa_mes": "R$ 4 mil a R$ 21 mil",
    "pot_base": ("Estimativa baseada em recuperação de 10% a 15% da recompra de reposição que hoje "
                 "escapa entre as visitas do representante + redução das horas do time gastas tirando "
                 "pedido por WhatsApp. O número real depende da base de oficinas ativas e da frequência "
                 "de recompra."),
    "significa": ("Um portal B2B de motopeças, com catálogo por modelo/ano e tabela por oficina, recupera "
                  "a recompra de reposição que hoje fica presa no WhatsApp e na agenda do representante."),
    "erp": "Bling",
    "erp_integ": "Bling - nativa",
    "erp_golive": "7 a 14 dias",
    "erp_dev": "Não (nativo)",
    "erp_line": ("A Zydon tem integração nativa com Sankhya, Omie, Olist e Bling — go-live mais rápido, "
                 "sem projeto customizado. ERPs diferentes são suportados sob avaliação."),
    "pushpull": ("Distribuidora de motopeças: a reposição é naturalmente puxada pelas oficinas, que "
                 "recompram os mesmos itens de desgaste em ciclo previsível. Hoje esse fluxo depende do "
                 "representante e do WhatsApp; um portal transforma a recompra em fluxo puxado pela "
                 "própria oficina."),
    "food": False,
}

# 1. Build + write HTML
html = build_html(l)
html_path = os.path.join(OUT, "dl-distribuidora.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote", html_path)

# 2. Render to PDF
pdf_path = os.path.join(PROJ, "pdfs", "Potencial-Digitalizacao-dl-distribuidora.pdf")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("file://" + html_path, wait_until="networkidle")
    pg.pdf(path=pdf_path, width="210mm", height="297mm", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print("PDF:", pdf_path, os.path.getsize(pdf_path), "bytes")
