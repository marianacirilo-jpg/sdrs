# -*- coding: utf-8 -*-
import os
import gen  # motor oficial: build_html + TEMPLATE
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)

l = {
    "slug": "reptec",
    "theme": "dark",
    "empresa": "Reptec",
    "contato": "Tiago Miranda",
    "cargo_area": "Fabricação e distribuição de EPIs e uniformes profissionais",
    "local": "Uberlândia, MG",
    "telefone": "",
    "site": "reptec.com.br",
    "sobre": (
        "A Reptec é fabricante e distribuidora de EPIs (Equipamentos de Proteção Individual) e uniformes "
        "profissionais, no mercado há mais de duas décadas (desde 2002), com sede em Uberlândia (MG) e um "
        "galpão de cerca de 10.000 m². São mais de 900 colaboradores e mais de 10.000 clientes ativos, com "
        "presença nacional — forte em MG, SP e MT — e exportação para África e América Latina. O portfólio "
        "cobre proteção de cabeça, olhos/face, ouvidos, mãos, pés, corpo inteiro e respiratória, além das "
        "linhas SMS, Fire (combate a incêndio), Área de Vivência, Luvas, Vestimentas e Uniformes. Atende "
        "indústria, agronegócio, construção e energia em B2B, e mantém um programa de Revenda para "
        "distribuidores."
    ),
    "sobre_fonte": "Fontes: site oficial reptec.com.br (home, /sobre, /catalogos), LinkedIn da Reptec — cruzados com o diagnóstico comercial Zydon.",
    "vende_para": "Indústria, agronegócio, construção e energia + rede de revenda (distribuidores B2B)",
    "como_vende": "Vendedores + rede de revenda (atacado B2B) + loja virtual",
    "loja_virtual": "Sim",
    "vendedores": "Estimativa: 20+ no comercial (porte nacional)",
    "time_total": "+900 colaboradores (diretos + indiretos) · +151 no diagnóstico",
    "faturamento": "De R$5 a R$10 milhões ao ano",
    "compra_sozinho": "Vende em loja virtual (sim); reposição B2B recorrente ainda passa por vendedor e rede de revenda",
    "encontramos": [
        "Catálogo amplo de EPI por parte do corpo (cabeça, olhos/face, ouvidos, mãos, pés, corpo inteiro, respiratória) e linhas SMS, Fire, Luvas, Vestimentas e Uniformes — mix que vira vitrine B2B com a tabela e os itens de cada cliente já salvos para recompra direta.",
        "Mais de 10.000 clientes ativos de indústria, agro, construção e energia que repõem EPI por exigência das NRs em ciclos curtos e obrigatórios — base ideal para um portal de reposição recorrente sem depender de vendedor a cada pedido.",
        "Programa de Revenda com distribuidores espalhados pelo país, hoje sem um canal B2B de autoatendimento onde o revendedor reponha estoque 24/7 com a tabela e o crédito dele.",
    ],
    "conta": (
        "EPI não é compra de oportunidade: cada indústria, fazenda ou obra é obrigada por norma (NRs) a "
        "repor luvas, capacetes, protetores, botas e uniformes em ciclos curtos e previsíveis — e hoje boa "
        "parte desse giro ainda passa por vendedor ou pela rede de revenda no telefone. Com um portal B2B "
        "onde o cliente e o revendedor repõem sozinhos o mesmo mix, com a tabela e o crédito deles, a Reptec "
        "transforma a recompra obrigatória de EPI em fluxo automático e libera o comercial para abrir conta "
        "nova nos 10.000+ clientes."
    ),
    "pot_low": "R$ 1 milhão",
    "pot_high": "R$ 4 milhões",
    "deixa_mes": "R$ 80 mil a R$ 330 mil",
    "pot_base": (
        "Estimativa baseada no porte (900+ colaboradores, 10.000+ clientes, fabricação própria + revenda) e "
        "na recuperação da recompra recorrente e obrigatória de EPI via autoatendimento, no patamar de "
        "receita digital de fabricantes e distribuidores que já abriram o canal B2B."
    ),
    "significa": (
        "Para a Reptec, abrir um canal B2B de autoatendimento significa capturar a reposição recorrente e "
        "obrigatória de EPI que hoje depende de vendedor e da rede de revenda, e dar aos 10.000+ clientes e "
        "aos distribuidores a mesma facilidade de comprar sozinhos, com a tabela e o crédito de cada um."
    ),
    "erp": "Outro",
    "erp_integ": "Sob projeto",
    "erp_golive": "30 a 60 dias",
    "erp_dev": "Sim (projeto)",
    "erp_line": (
        "A Reptec informou usar 'Outro' ERP — e na Zydon a regra é clara: outros ERPs = integração sob "
        "projeto técnico. Prazo médio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, "
        "Olist e Bling."
    ),
    "pushpull": (
        "A operação ainda empurra o pedido: a reposição de EPI dos clientes industriais, do agro e da "
        "construção, além do abastecimento da rede de revenda, passa por vendedor e telefone. Como esses "
        "clientes são obrigados por norma a repor o mesmo mix de luvas, capacetes, protetores e uniformes em "
        "ciclo curto, digitalizar o canal de recompra faz o pedido passar a PUXAR — o próprio cliente e o "
        "revendedor repõem a qualquer hora, com a tabela deles."
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
