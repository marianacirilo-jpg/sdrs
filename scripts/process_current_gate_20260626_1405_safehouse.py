#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-26 14:05 BRT com pesquisa real via Claude Code/WebSearch/WebFetch."""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p

p.RESEARCH['contato@safehouseshop.com.br'] = {
    'slug': 'safe-house-safe-grill-rodolfo-viacelli',
    'mql': False,
    'empresa_real': 'Safe House / Safe Grill — fabricante de churrasqueiras automáticas giratórias e acessórios de churrasco, com site oficial safegrill.com.br e loja/domínio safehouseshop.com.br vinculada, em Garça/SP.',
    'dominio_site': 'safegrill.com.br — site oficial com modelos de churrasqueira automática giratória, acessórios e contato por WhatsApp; safehouseshop.com.br aparece vinculado ao grupo mas não abriu conteúdo confiável por problema de TLS.',
    'redes': 'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo: site oficial safegrill.com.br, safehouseshop.com.br, resultados públicos CNPJ/Econodata/CNPJ Biz/JusBrasil ligando Safe House LTDA/Safe Grill ao CNPJ 45.513.346/0001-21 e Rodolfo Viacelli Junior. O formulário informa revendedores de ecommerce, WhatsApp como canal atual, ERP Outro, 1 a 10 pessoas, 1 vendedor, sem loja virtual e ainda sem faturamento.',
    'segmento': 'Fabricante pequeno/inicial de churrasqueiras automáticas e acessórios; produto durável de compra esporádica, vendido por cotação/WhatsApp, sem evidência pública suficiente de canal atacadista recorrente de alto giro para revendas/lojistas abastecerem estoque.',
    'motivo': 'Pesquisa pública confirmou empresa real e indústria, mas o produto principal é durável/alto ticket e de baixo giro, com compra pontual. O formulário indica operação ainda sem faturamento, 1 vendedor, sem loja virtual e sem prova de revenda/atacado recorrente já estabelecido. Pelo crivo MQL acirrado/fail-closed, indústria só qualifica quando há evidência clara de catálogo/preço/pedido recorrente para revendas/lojistas/clientes de estoque; aqui essa evidência ainda é fraca.',
    'insight': '',
    'telefone_publico': 'WhatsApp público no site oficial safegrill.com.br: +55 14 99815-9223. Telefone do formulário/HubSpot: +55 14 98191-4624.',
    'whatsapp_publico': 'WhatsApp público corporativo +55 14 99815-9223 localizado no site safegrill.com.br; não usado porque o lead foi reprovado no crivo MQL acirrado.',
}

if __name__ == '__main__':
    p.main()
