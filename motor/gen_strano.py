# -*- coding: utf-8 -*-
"""Gera PDF do diagnóstico para Strano (Yhuri / YA Grupo)"""
import os, sys, json, subprocess

OUT = os.path.dirname(os.path.abspath(__file__))

# Import template functions
sys.path.insert(0, OUT)
from gen import build_html, TEMPLATE

HOJE = "24 jun 2026"

lead = {
    "slug": "strano",
    "theme": "dark",
    "empresa": "Strano",
    "contato": "Yhuri",
    "cargo_area": "Distribuição de EPI / Calçados de segurança",
    "local": "Interior de SP (DDD 16)",
    "telefone": "(16) 99301-3899",
    "site": "stranodistribuidora.com.br",
    "sobre": ("A Strano é uma distribuidora especializada em EPI — botas e coturnos de segurança certificados "
              "para construção civil, indústria, agrícola e motoclubes. Opera e-commerce próprio (plataforma Shoppub) "
              "e marketplace, com opção de atacado. Marcas como Cartom, entrega via correio e transportadoras, "
              "pagamento PIX (5% desc.) e todos os cartões."),
    "sobre_fonte": "site oficial stranodistribuidora.com.br + dados do diagnóstico Zydon",
    "vende_para": "Compradores de EPI (B2B atacado) e consumidores finais (B2C varejo) — construção civil, indústria, agrícola",
    "como_vende": "E-commerce próprio + Marketplace (atacado e varejo)",
    "loja_virtual": "Sim (e-commerce Shoppub ativo)",
    "erp": "Olist (Tiny)",
    "vendedores": "1 a 3",
    "time_total": "1 a 10 pessoas",
    "faturamento": "R$ 1 milhão a R$ 5 milhões por ano",
    "compra_sozinho": "Sim — cliente já compra sozinho pela loja virtual e marketplace",
    "encontramos": [
        "Catálogo digital de EPI com 3 categorias (botas, sapatos, nobuck) e filtro por tamanho — pronto para um portal B2B de autoatendimento",
        "Opção de atacado já existe como canal — volume B2B que ganha escala com cotação e tabela de preço por cliente no portal",
        "ERP Olist (Tiny) integrado nativamente à Zydon — pedidos de e-commerce, marketplace e atacado entram direto, sem retrabalho manual entre canais",
        "Depoimentos positivos e logística própria via correio + transportadora — base de clientes ativa pronta para recompra digital"
    ],
    "conta": ("Quando atacado e varejo rodam em canais separados, o pedido B2B que vem por WhatsApp ou telefone "
              "precisa ser digitado à mão no sistema. Um portal B2B no canal digital recebe o pedido do cliente "
              "direto — o time foca em fechar negócio, não em copiar pedido."),
    "pot_low": "R$ 200 mil",
    "pot_high": "R$ 800 mil",
    "deixa_mes": "R$ 16 mil a R$ 66 mil",
    "pot_base": "Estimativa baseada em faturamento de R$1-5M/ano e potencial de digitalização do canal B2B.",
    "significa": ("Unificar atacado, e-commerce e marketplace num só portal B2B com a Zydon recupera de 8% a 15% "
                  "do faturamento que hoje se perde com retrabalho entre canais e pedidos manuais."),
    "erp_integ": "Olist (Tiny) — nativa",
    "erp_golive": "7 a 14 dias",
    "erp_dev": "Não (nativo)",
    "erp_line": ("A Zydon tem integração nativa com Olist, Sankhya, Omie e Bling — go-live mais rápido, "
                 "sem projeto customizado. ERPs diferentes são suportados sob avaliação."),
    "pushpull": ("A Strano já empurra catálogo via e-commerce e marketplace (pull digital), mas o atacado ainda "
                 "depende de contato manual — o portal B2B fecha esse gap e unifica os dois modelos."),
}

# Override HOJE in gen module
import gen
gen.HOJE = HOJE

# Generate HTML
html = build_html(lead)
html_path = os.path.join(OUT, "strano.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"HTML written: {html_path}")

# Verify no "A confirmar"
count = html.count("A confirmar")
print(f"'A confirmar' count: {count}")
assert count == 0, "PROIBIDO 'A confirmar' no PDF!"
