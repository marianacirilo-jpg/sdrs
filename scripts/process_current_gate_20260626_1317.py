#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-26 13:17Z com pesquisa real via Claude Code/WebSearch/WebFetch."""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p

# Pesquisa real feita via Claude Code/WebSearch/WebFetch em 2026-06-26 13:17Z.
p.RESEARCH['jerson@busca.legal'] = {
    'slug': 'busca-legal-jerson-prochnow',
    'mql': False,
    'empresa_real': 'Busca.Legal — legaltech/taxtech de inteligência fiscal, tributária e jurídica baseada em IA, fundada por ex-sócios da FiscoSoft/Systax; Jerson Prochnow aparece publicamente ligado à empresa.',
    'dominio_site': 'busca.legal — site oficial da plataforma de busca e inteligência legal/tributária; domínio do e-mail confere com a empresa.',
    'redes': 'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: site oficial Busca.Legal, LinkedIn público de Jerson Prochnow e notícia sobre parceria Sescon-SP/Systax/Busca.Legal.',
    'segmento': 'SaaS/serviço de inteligência fiscal, tributária e jurídica; legaltech/taxtech baseada em IA, sem produto físico/catálogo de estoque.',
    'motivo': 'Pesquisa pública confirmou empresa real, porém o modelo é software/serviço de informação tributária e jurídica. Não há evidência de indústria, distribuidor, importador ou atacado vendendo produto físico para revendas/lojistas ou abastecimento recorrente de estoque. Pelo crivo MQL acirrado/fail-closed, SaaS/consultoria/serviço fica não qualificado, mesmo com formulário indicando representantes, 27 UFs e porte alto.',
    'insight': '',
    'telefone_publico': 'Não localizado telefone/WhatsApp público corporativo seguro; telefone do formulário/HubSpot: +55 11 99618-9001.',
    'whatsapp_publico': 'Não localizado com segurança; não usado porque o lead foi reprovado no crivo MQL acirrado.',
}

p.RESEARCH['hasama@tuzzon.com.br'] = {
    'slug': 'tuzzon-confeccoes-hasama-teixeira',
    'mql': False,
    'empresa_real': 'Tuzzon Confecções LTDA, operação pública como Fortiori Camisetas/Fortiori Clothing, em Caetité-BA; Hasama Teixeira aparece publicamente como diretor geral da Fortiori Camisetas.',
    'dominio_site': 'fortiori.com.br é o domínio ativo da operação; tuzzon.com.br aparece como domínio/cadastro antigo relacionado. O e-mail do lead usa tuzzon.com.br.',
    'redes': 'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: site oficial Fortiori/Contato, Instagram @fortiori.camisetas, Facebook Fortiori Camisetas, LinkedIn Fortiori, cnpj.biz e Econodata.',
    'segmento': 'Confecção/indústria têxtil de camisetas, fardamentos, abadás, uniformes e promocionais personalizados sob encomenda, com serigrafia, sublimação e bordado.',
    'motivo': 'Pesquisa pública confirmou empresa industrial madura, mas a operação evidenciada é confecção personalizada sob demanda para eventos, escolas, empresas, times e promocionais. Não há evidência clara de venda recorrente de produtos prontos para revendas/lojistas com reposição de estoque. O CNAE atacadista aparece como secundário e não comprova canal ativo de revenda. Pelo crivo acirrado/fail-closed, reprova até confirmar atacado/linha própria para lojistas.',
    'insight': '',
    'telefone_publico': 'Telefone público corporativo no site: +55 77 3454-5550; WhatsApp público corporativo: +55 77 99959-9855. HubSpot veio sem telefone.',
    'whatsapp_publico': 'WhatsApp público +55 77 99959-9855 localizado no site oficial Fortiori/Contato; não usado porque o lead foi reprovado no crivo MQL acirrado.',
}

p.RESEARCH['comercial@lunarrepresentacao.com.br'] = {
    'slug': 'lunar-equipamentos-andre-sanches',
    'mql': True,
    'empresa_real': 'Lunar Equipamentos LTDA, CNPJ 40.940.004/0001-74, São Paulo/SP, Vila Aricanduva; operação pública ligada a EPI, uniformes e acessórios de segurança do trabalho.',
    'dominio_site': 'lunarequipamentos.com.br — site público da empresa; e-mail do lead usa lunarrepresentacao.com.br, coerente com operação comercial/representação.',
    'redes': 'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: Casa dos Dados, Econodata, cnpj.biz, site Lunar Equipamentos e Instagram @lunar.equipamentos.',
    'segmento': 'Comércio atacadista/distribuição de EPI, roupas e acessórios para uso profissional e segurança do trabalho; produto físico de recompra recorrente para construtoras, empreiteiras, concessionárias, revendas e distribuidores.',
    'motivo': 'Pesquisa pública confirmou CNAE principal de comércio atacadista de roupas e acessórios para uso profissional e segurança do trabalho. O formulário reforça venda por WhatsApp, ERP Bling, clientes como distribuidoras, revendas, construtoras, empreiteiras, concessionárias e pavimentação, e dor de carteira parada. Mesmo sendo pequena, há evidência clara de atacado/distribuição B2B com produto físico recorrente e potencial de digitalizar catálogo, preço e recompra para clientes de estoque.',
    'insight': 'revendas, construtoras e empreiteiras recomprarem EPIs e uniformes com catálogo e preço atualizados sem depender de cada pedido solto no WhatsApp',
    'telefone_publico': 'Não localizei WhatsApp público integral seguro; bases públicas mostram telefone parcialmente mascarado. Telefone do formulário/HubSpot é celular válido: +55 11 98704-5720.',
    'whatsapp_publico': 'Não localizado publicamente com segurança; será usado o celular válido informado no formulário/HubSpot.',
}

if __name__ == '__main__':
    p.main()
