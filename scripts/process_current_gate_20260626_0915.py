#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Process current gate leads from 2026-06-26 09:15Z with real Claude/web research."""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p

p.RESEARCH['fabio@camiladiniz.com.br'] = {
    'slug': 'camila-diniz-fabio-luanes',
    'mql': False,
    'empresa_real': 'Camila Diniz — marca/loja de semijoias e acessórios de moda; CNPJ 22.934.144/0001-58 citado em fontes públicas',
    'dominio_site': 'camiladiniz.com.br; site oficial com vitrine/loja B2C, produtos com preço unitário, parcelamento, frete grátis e SAC',
    'redes': 'Fontes pesquisadas via Claude Code/WebSearch/WebFetch e extração local: site oficial camiladiniz.com.br, página Sobre, Produtos, Instagram @camiladiniz.brand, Facebook Camila Diniz e snippets públicos. O site divulga SAC/WhatsApp (11) 91733-4752 e email camiladiniz@camiladiniz.com.br.',
    'segmento': 'Semijoias/acessórios de moda — marca de varejo/e-commerce direto ao consumidor, com design autoral e coleção própria',
    'motivo': "Pesquisa pública real confirmou empresa/marca legítima, mas o canal visível é varejo B2C: loja online com preços unitários, parcelamento, frete grátis e discurso de marca para consumidor final. O formulário informa Bling, R$1 a R$5 milhões e representantes comerciais, mas não há evidência clara de indústria/distribuidor/importador/atacado vendendo para revendas/lojistas com abastecimento recorrente de estoque. Pelo crivo MQL acirrado/fail-closed, sem prova de canal B2B recorrente, não qualifica.",
    'insight': '',
    'telefone_publico': 'SAC/WhatsApp público do site: +55 11 91733-4752; telefone do formulário/HubSpot: +55 11 94742-1636',
    'whatsapp_publico': 'WhatsApp público do site: +55 11 91733-4752; não usado porque o lead foi reprovado no crivo MQL acirrado',
}

p.RESEARCH['leandro.gerencia@qualityfishpescados.com.br'] = {
    'slug': 'quality-fish-leandro-cotrim',
    'mql': True,
    'empresa_real': 'Quality Fish Distribuidora Ltda — CNPJ 25.295.306/0001-43, Colômbia/SP, distribuidora atacadista de pescados e frutos do mar',
    'dominio_site': 'qualityfishpescados.com.br; site oficial confirma atuação há mais de 9 anos em distribuição de pescados/frutos do mar, área de atuação em SP/MG/PR, frota própria refrigerada e catálogo de produtos',
    'redes': 'Fontes pesquisadas via Claude Code/WebSearch/WebFetch e extração local: site oficial qualityfishpescados.com.br, páginas Quality Fish, Contato, Receitas e Área de Atuação, Instagram @fish.quality, Facebook fish.quality, Econodata/CNPJá/EmpresAqui com CNAE 4634-6/03 comércio atacadista de pescados e frutos do mar.',
    'segmento': 'Distribuidora atacadista de pescados, frutos do mar e congelados para food service/comércio, com estoque refrigerado, frota própria e venda B2B recorrente para restaurantes, revendas/lojas de alimentos e clientes comerciais',
    'motivo': 'Pesquisa pública real confirmou ICP T1: distribuidora atacadista de pescados e frutos do mar, compra direto do produtor, possui catálogo variado, frota refrigerada própria, atuação regional em SP/MG/PR e chamada explícita para clientes/comércios/restaurantes disponibilizarem os produtos. A operação envolve clientes B2B recorrentes, reposição de estoque de alimentos congelados e alto giro para food service/comércio. O formulário reforça porte forte com faturamento de R$10 a R$50 milhões, 11 a 25 pessoas e vendas por WhatsApp. Mesmo com ERP informado como Outro, o fit vem do atacado B2B de alimentos congelados com recompra recorrente.',
    'insight': 'restaurantes, lojas de alimentos e clientes comerciais recomprarem pescados e congelados por um canal próprio, com catálogo, preço e disponibilidade atualizados sem travar cada pedido no WhatsApp',
    'telefone_publico': 'Site oficial divulga atendimento +55 17 3335-1737 e WhatsApp +55 17 98106-0186; telefone do formulário/HubSpot também é +55 17 98106-0186',
    'whatsapp_publico': 'WhatsApp público corporativo +55 17 98106-0186 localizado no site oficial qualityfishpescados.com.br e igual ao telefone do formulário',
}

if __name__ == '__main__':
    p.main()
