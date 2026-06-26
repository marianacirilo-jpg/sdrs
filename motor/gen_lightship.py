# -*- coding: utf-8 -*-
import os
import gen  # usa build_html + TEMPLATE do motor oficial

OUT = os.path.dirname(os.path.abspath(__file__))

lead = {
    "slug": "lightship-embalagens",
    "theme": "dark",
    "empresa": "LightShip Embalagens",
    "contato": "Eduardo",
    "cargo_area": "Fabricante de embalagens personalizadas B2B (caixas, sacolas kraft, envelopes)",
    "local": "São Paulo, SP",
    "site": "lightshipdescartaveis.com.br",
    "sobre": (
        "A LightShip é fabricante de embalagens personalizadas — caixas kraft, sacolas, envelopes com lacre "
        "de segurança e sacos plásticos com a arte da marca do cliente. Fundada em 2014 e sediada em São "
        "Paulo, atende e-commerces, lojas de roupas e pequenas empresas que querem embalagem com a própria "
        "identidade visual. Criou o Clube da Embalagem, programa que permite que empresas pequenas comprem "
        "personalizado sem grandes volumes mínimos. Opera por loja virtual própria e atendimento direto via "
        "WhatsApp, com nichos verticais em odonto, saúde/hospitalar e EPIs."
    ),
    "sobre_fonte": "site oficial lightshipdescartaveis.com.br, LinkedIn (lightshipdescartaveis) — cruzados com o diagnóstico comercial Zydon.",
    "vende_para": "E-commerces, lojas de roupas e pequenas empresas (B2B) que querem embalagem com a própria marca",
    "como_vende": "Loja virtual própria + WhatsApp + Clube da Embalagem (programa de assinatura para pequenas empresas)",
    "loja_virtual": "Sim",
    "vendedores": "Atendimento direto via WhatsApp",
    "time_total": "1 a 10 pessoas",
    "faturamento": "Até R$ 250 mil por ano",
    "compra_sozinho": "A confirmar",
    "erp": "Outro",
    "encontramos": [
        "Catálogo digital de embalagens personalizadas por tipo (caixas, sacolas, envelopes) com a arte salva por cliente, para recompra sem reorçar a personalização a cada pedido.",
        "Portal B2B para os clientes do Clube da Embalagem fazerem pedido recorrente sozinhos, com a arte e o volume já cadastrados — reposição automática mensal sem idas e vindas no WhatsApp.",
        "Self-service de status de personalização, produção e entrega para os clientes que pedem embalagem com marca própria todo mês.",
    ],
    "conta": (
        "Cada cliente e-commerce recompra embalagem com a própria marca todo mês, mas hoje precisa "
        "reorçar e confirmar pelo WhatsApp a cada pedido. Com um portal B2B onde o cliente repõe "
        "sozinho — com a arte salva e o volume padrão — a LightShip transforma a recompra recorrente "
        "em fluxo automático e libera o atendimento para captar novos clientes."
    ),
    "pot_low": "R$ 50 mil",
    "pot_high": "R$ 200 mil",
    "deixa_mes": "R$ 4 mil a R$ 16 mil",
    "pot_base": "Estimativa baseada em faturamento anual até R$ 250 mil e na recuperação de recompra recorrente dos clientes do Clube da Embalagem via autoatendimento, no patamar de receita digital de fabricantes de embalagens que já digitalizaram o canal B2B. O número real depende da base de clientes ativos e do mix de personalização.",
    "significa": (
        "Para a LightShip, abrir um canal B2B de autoatendimento significa capturar a recompra mensal que "
        "hoje depende de WhatsApp e transformar o Clube da Embalagem em assinatura automática — sem perder "
        "o atendimento personalizado que é a marca da empresa."
    ),
    "erp_integ": "Integração sob projeto",
    "erp_golive": "30 a 60 dias",
    "erp_dev": "Sim (projeto)",
    "erp_line": (
        "A Zydon avalia a integração com o ERP desta operação sob projeto técnico. Prazo médio: 30 a 60 dias "
        "para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."
    ),
    "pushpull": (
        "A operação ainda empurra cada pedido pelo WhatsApp, mesmo com loja virtual e o Clube da Embalagem "
        "já estruturados. O cliente que recompra embalagem personalizada todo mês ainda depende de "
        "reorçamento manual. Digitalizar o canal de recompra faz o pedido passar a PUXAR — o próprio "
        "cliente repõe com a arte salva, no volume padrão, a qualquer hora."
    ),
    "food": False,
}

html = gen.build_html(lead)
path = os.path.join(OUT, f"{lead['slug']}.html")
with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print("HTML escrito:", path)
