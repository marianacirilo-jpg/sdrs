#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-26 11:10Z com pesquisas reais via Claude Code."""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p

# Pesquisa real feita via Claude Code/WebSearch/WebFetch em 2026-06-26 11:10Z.
p.RESEARCH['michele@franquiasorpack.com'] = {
    'slug':'sorpack-embalagens-michele-reis',
    'mql': True,
    'empresa_real':'Sorpack Embalagens — rede de franquias/lojas de atacado e atacarejo de embalagens, descartáveis, higiene, limpeza e itens para food service; matriz em Cuiabá e expansão por unidades Smart/Store, incluindo operação em Campo Grande/MS',
    'dominio_site':'sorpack.com.br é o site institucional/comercial da rede; franquiasorpack.com é o portal de expansão/franqueamento; ambos confirmam operação de embalagens e modelo de franquias',
    'redes':'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: site Sorpack Sobre Nós, Portal do Franchising/ABF, Encontre Sua Franquia, Instagram @sorpackembalagens e página da rede/franquia Sorpack',
    'segmento':'Atacado/distribuidor de embalagens, descartáveis, higiene, limpeza e itens para food service, com venda B2B recorrente para bares, restaurantes, padarias, hotéis, transportadoras, indústrias de alimentos e clientes de reposição de estoque',
    'motivo':'Pesquisa pública real confirmou ICP T1: rede de atacado/distribuição de embalagens com lojas físicas, catálogo amplo e estoque recorrente, vendendo para empresas que recompram insumos de consumo constante. O formulário reforça fit com faturamento de R$1 a R$5 milhões, 11 a 25 pessoas, venda por telelevendas e representantes e ausência de loja virtual. ERP Outro não substitui nem bloqueia o ICP; a qualificação se sustenta pelo canal B2B recorrente e pelo giro de embalagens.',
    'insight':'clientes como restaurantes, padarias e hotéis recomprarem embalagens antes de ficar sem estoque, com menos pedido solto por telefone e mais previsibilidade para o time comercial',
    'telefone_publico':'Telefones públicos da rede/expansão encontrados em ficha de franquia: +55 31 3654-5664 e +55 31 99936-4602; telefone do formulário/HubSpot: +55 65 98475-7060',
    'whatsapp_publico':'Não localizei WhatsApp corporativo direto da franqueada com segurança; telefone do formulário é celular válido e será usado para envio',
}

p.RESEARCH['logistica@agrosaovalentim.com'] = {
    'slug':'agroveterinaria-sao-valentim-pablo',
    'mql': True,
    'empresa_real':'Agroveterinária São Valentim — empresa familiar de São Lourenço do Oeste/SC, com cerca de 8 anos de operação e unidades em SC/PR, atendendo produtores rurais com nutrição animal, sementes, medicamentos veterinários, minerais e serviços técnicos',
    'dominio_site':'agrosaovalentim.com.br é o site oficial; agrosaovalentim.com/produtos também aparece em resultados públicos e redes da empresa; o e-mail corporativo logistica@agrosaovalentim.com confere com a operação',
    'redes':'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: site oficial agrosaovalentim.com.br, página de produtos, Instagram @agrosaovalentim, Facebook Agroveterinária São Valentim, LinkedIn Agroveterinaria São Valentim e ficha pública de revenda/autorizada Husqvarna/Econodata',
    'segmento':'Distribuição/varejo agropecuário com estoque físico e reposição recorrente para produtores rurais: nutrição animal, rações, sementes de milho, medicamentos veterinários, minerais, pet shop, equipamentos e serviços técnicos para gado de corte, leite e agricultura',
    'motivo':'Pesquisa pública real confirmou ICP válido no agro: empresa estruturada, multiunidade, com mix físico de insumos rurais, sementes, minerais, medicamentos veterinários e nutrição animal para produtores de gado de corte, leite e agricultura. Esses clientes recompram itens de abastecimento/estoque com recorrência e precisam de atendimento técnico, disponibilidade e reposição. O formulário reforça porte de R$10 a R$50 milhões/ano, 11 a 25 pessoas e ausência de loja virtual; ERP Outro não substitui o ICP, mas também não bloqueia.',
    'insight':'produtores rurais e fazendas consultarem sementes, rações, minerais e medicamentos por unidade, com reposição recorrente sem depender de cada pedido manual no WhatsApp',
    'telefone_publico':'Site oficial informa unidade São Lourenço do Oeste (49) 3344-7555, Palmas (46) 98803-9090 e WhatsApp principal +55 49 99952-0023; telefone do formulário/HubSpot: +55 49 99927-2127',
    'whatsapp_publico':'WhatsApp corporativo principal +55 49 99952-0023 divulgado no site oficial via link api.whatsapp.com/send/?phone=5549999520023; telefone do formulário é celular válido e será usado para envio ao contato',
}

if __name__ == '__main__':
    p.main()
