#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-26 10:05Z com pesquisas reais via Claude Code."""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p

p.RESEARCH['ox.grupo@souox.com'] = {
    'slug': 'grupo-ox-maik-nogueira',
    'mql': True,
    'empresa_real': 'Grupo OX / Ox Indústria de Produtos Químicos Ltda — indústria química/automotiva com unidades no Pará, operação própria e portfólio de Arla 32, aditivos, fluidos automotivos, limpeza, água desmineralizada, importação de insumos e embalagens plásticas',
    'dominio_site': 'souox.com; site oficial confirma Grupo OX, indústria no Pará, linhas de produtos OX Auto/Radox/Disox/Gasox/OX Clean/OX Imports/OX Embalagens, certificações e atendimento a postos, distribuidores, revendas e frotas',
    'redes': 'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: site oficial souox.com, páginas Quem Somos e Linha de Produtos, rodapé com Instagram/Facebook/Twitter/WhatsApp e bases públicas Econodata/CNPJ.biz para Ox Indústria de Produtos Químicos Ltda',
    'segmento': 'Indústria química/automotiva e distribuidora B2B de Arla 32, aditivos, fluidos automotivos, produtos de limpeza e embalagens, abastecendo postos de combustível, revendas, distribuidores e frotas com itens de reposição recorrente',
    'motivo': 'Pesquisa pública real confirmou ICP T1: indústria/fabricante com venda B2B recorrente de reposição, abastecendo postos, distribuidores, revendas e frotas em volume contínuo, inclusive embalagens de 5L a 1.000L. A operação tem produto físico de alto giro, portfólio amplo e canal comercial externo/WhatsApp. Mesmo com faturamento declarado menor no formulário, o modelo de indústria/distribuição e recompra de estoque sustenta MQL no crivo acirrado.',
    'insight': 'postos, frotas e distribuidores recomprarem Arla 32 e aditivos por um canal próprio, com catálogo, embalagem, preço e disponibilidade claros sem depender de cada pedido solto no WhatsApp',
    'telefone_publico': 'Telefone público no site/cadastros: +55 91 3712-0031; WhatsApp público divulgado no site: +55 91 9180-8585; telefone do formulário/HubSpot: +55 91 98412-3272',
    'whatsapp_publico': 'WhatsApp público corporativo +55 91 9180-8585 divulgado no rodapé/site souox.com; telefone do formulário +55 91 98412-3272 também é celular válido',
}

p.RESEARCH['lintrieri@policrombr.com'] = {
    'slug': 'policrom-south-america-leo-intrieri',
    'mql': True,
    'empresa_real': 'Policrom Screens South America Comércio, Importação e Exportação de Produtos Gráficos Ltda — braço brasileiro da Policrom Screens S.p.A., importador/distribuidor de insumos gráficos e mangueiras industriais',
    'dominio_site': 'policrombr.com e policrombr.com.br; site oficial confirma produtos para serigrafia, flexografia, impressão digital, telas, filmes e mangueiras industriais; domínio do e-mail confere com a empresa',
    'redes': 'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: site oficial policrombr.com, páginas Produtos e Mangueiras, Instagram @policrom_brasil, Facebook Policrombr, LinkedIn Policrom Screens South America e LinkedIn público de Leonardo Intrieri ligado à área comercial',
    'segmento': 'Importador/distribuidor B2B de insumos e consumíveis para artes gráficas, serigrafia, flexografia, impressão digital e mangueiras industriais, atendendo gráficas, serigrafias e clientes industriais com reposição recorrente',
    'motivo': 'Pesquisa pública real confirmou ICP T1: importador/distribuidor B2B com venda recorrente de consumíveis e insumos gráficos. Clientes como gráficas e serigrafias precisam recomprar telas, filmes, materiais e mangueiras para manter produção/estoque. O formulário reforça aderência: faturamento de R$5 a R$10 milhões, Omie, sem loja virtual, venda por WhatsApp, e-mail e visita com vendedor externo. Mesmo sendo consumidores industriais e não varejo final, a recorrência de estoque e o canal B2B passam no crivo acirrado.',
    'insight': 'gráficas e serigrafias recomprarem telas, filmes e insumos por um canal próprio, com catálogo e histórico de pedidos, sem espalhar cada reposição entre WhatsApp, e-mail e visita externa',
    'telefone_publico': 'Telefone corporativo público no site/cadastros: +55 11 3333-3130; telefone do formulário/HubSpot: +55 11 98156-5258',
    'whatsapp_publico': 'WhatsApp público corporativo não confirmado em fonte pública; número do formulário/HubSpot +55 11 98156-5258 é celular válido do contato',
}

if __name__ == '__main__':
    p.main()
