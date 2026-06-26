# -*- coding: utf-8 -*-
import os
import gen  # motor oficial: build_html + TEMPLATE
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)

l = {
    "slug": "libera-pro",
    "theme": "dark",
    "empresa": "Líbera Pro",
    "contato": "Maikel Ronqui",
    "cargo_area": "Distribuição B2B de linha profissional",
    "local": "Santa Catarina",
    "telefone": "",
    "site": "lbrpro.com.br",
    "sobre": (
        "A Líbera Pro é uma operação catarinense que trabalha uma linha profissional vendida no canal B2B — "
        "revendas, lojistas e profissionais que reabastecem a marca de forma recorrente. É o perfil clássico "
        "de quem vive de recompra: o mesmo cliente repõe o mesmo mix em ciclos curtos e previsíveis. Esse tipo "
        "de canal ganha escala quando o pedido sai do telefone, do WhatsApp e da planilha do vendedor e passa "
        "para um canal de compra que o próprio cliente acessa sozinho, com a tabela e o crédito dele."
    ),
    "sobre_fonte": "Fontes: domínio corporativo lbrpro.com.br e sinais públicos (marca de linha profissional, base em Santa Catarina) — cruzados com as respostas do diagnóstico comercial Zydon. Perfil a calibrar com a Líbera Pro.",
    "vende_para": "Revendas, lojistas e profissionais que reabastecem a linha Líbera Pro (canal B2B)",
    "como_vende": "Vendedor + contato direto (WhatsApp/telefone)",
    "loja_virtual": "A confirmar",
    "vendedores": "A confirmar",
    "time_total": "A confirmar",
    "faturamento": "A confirmar no diagnóstico",
    "compra_sozinho": "A confirmar",
    "encontramos": [
        "Portfólio de linha profissional que pode virar uma vitrine B2B com a tabela e o mix de cada cliente já salvos, pronto para recompra direta sem refazer o pedido toda vez.",
        "Canal de revenda e profissionais que repõe o mesmo mix em ciclos curtos — base ideal para um portal de reposição recorrente que roda sozinho, sem depender do vendedor a cada pedido.",
        "Hoje o pedido provavelmente ainda passa por vendedor, WhatsApp e telefone, sem um canal B2B de autoatendimento onde o cliente compra com a tabela e o crédito dele, a qualquer hora.",
    ],
    "conta": (
        "Cada revenda e cada profissional que trabalha a Líbera Pro recompra o mesmo mix em ciclos curtos e "
        "previsíveis — mas boa parte desse giro ainda passa por vendedor, WhatsApp e telefone. Com um portal "
        "B2B onde o cliente repõe sozinho o mesmo mix, com a tabela e o crédito dele, a Líbera Pro transforma "
        "essa recompra recorrente em fluxo automático e libera o comercial para abrir cliente novo em vez de "
        "ficar tirando pedido de reposição."
    ),
    "pot_low": "R$ 180 mil",
    "pot_high": "R$ 720 mil",
    "deixa_mes": "R$ 15 mil a R$ 60 mil",
    "pot_base": (
        "Estimativa ilustrativa e conservadora, adotada por ainda não termos o faturamento confirmado: "
        "baseia-se na recuperação da recompra recorrente do canal de revenda via autoatendimento, no patamar "
        "de receita digital de distribuidores que já abriram o canal B2B. O número real será calibrado com a "
        "base de clientes e o mix da Líbera Pro no diagnóstico."
    ),
    "significa": (
        "Para a Líbera Pro, abrir um canal B2B de autoatendimento significa capturar a reposição recorrente do "
        "canal de revenda que hoje depende de vendedor e WhatsApp, e dar a cada cliente profissional a "
        "facilidade de comprar sozinho, a qualquer hora, com a tabela e o crédito dele."
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
        "A operação ainda empurra o pedido: a reposição do canal de revenda passa por vendedor, WhatsApp e "
        "telefone. Como revendas e profissionais recompram o mesmo mix em ciclo curto, digitalizar o canal de "
        "recompra faz o pedido passar a PUXAR — o próprio cliente repõe a linha Líbera Pro a qualquer hora, "
        "com a tabela dele, e o vendedor entra só onde agrega."
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
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("file://" + html_path, wait_until="networkidle")
    pg.pdf(path=pdf_path, width="210mm", height="297mm", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print("PDF escrito:", pdf_path)
