#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate 2026-06-28 22:36 UTC — ItQuality, SectorOne, Smarthie.
Pesquisa real: Claude Code com WebSearch/WebFetch + web_search/web_extract do ciclo.
Crivo atual do cron: fail-closed T1; os 3 foram classificados como não-MQL.
"""
import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

# O gate veio como manual_hubspot_mql/lifecyclestage MQL, mas a instrução deste ciclo
# explicitou crivo MQL acirrado/fail-closed. Para impedir envio externo indevido,
# neutralizamos apenas a cópia local do gate deste ciclo; não fazemos downgrade no HubSpot.
try:
    gate = json.loads(p.GATE.read_text(encoding='utf-8'))
    for lead in gate.get('leads', []):
        email = (lead.get('email') or '').lower()
        if email in {
            'contato@itqinformatica.com.br',
            'ekizian@sectorone.com.br',
            'karina@charthie.com.br',
        }:
            lead['gate_trigger'] = 'strict_fail_closed_review'
            props = lead.setdefault('properties', {})
            props['lifecyclestage'] = 'lead'
    p.GATE.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding='utf-8')
except Exception as e:
    print(f'ERRO preparando gate fail-closed: {e}')

p.RESEARCH['contato@itqinformatica.com.br'] = {
    'slug': 'itquality-informatica-rodrigo-fernandes',
    'mql': False,
    'empresa_real': 'Itquality Informática Ltda / ITQ Informática — empresa ativa em São Paulo/SP, fundada em 2018, vinculada publicamente a Rodrigo Fernandes e ao domínio itqinformatica.com.br.',
    'dominio_site': 'itqinformatica.com.br; loja/marketplaces públicos como Mercado Livre e Americanas; bases públicas Casa dos Dados/Econodata confirmam CNPJ 30.472.134/0001-76.',
    'redes': 'Pesquisa pública real no ciclo: Claude Code com WebSearch/WebFetch encontrou site itqinformatica.com.br, LinkedIn de Rodrigo Fernandes/CEO, Facebook, loja Mercado Livre/Americanas e bases Casa dos Dados/Econodata. Casa dos Dados lista CNAE principal de comércio varejista especializado de equipamentos e suprimentos de informática; o formulário informa marketplace e WhatsApp, Olist/Tiny, 1 a 10 pessoas e ainda não faturamos.',
    'segmento': 'Comércio varejista/e-commerce de suprimentos de informática, impressão, cartuchos/toners e papelaria, com venda por marketplace e WhatsApp.',
    'motivo': 'Reprovado no crivo MQL acirrado/fail-closed: apesar de empresa real e celular válido, a evidência pública aponta para varejo/marketplace pequeno de informática e suprimentos, não indústria, distribuidor, importador ou atacado abastecendo revendas/lojistas com recorrência de estoque. O próprio formulário informa equipe pequena e ainda sem faturamento. Não deve receber diagnóstico externo automático.',
    'insight': '',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 11 98808-9767. Casa dos Dados exibe telefone cadastral/WhatsApp fixo +55 11 2306-5532, mas não usado por ser não-MQL.',
    'whatsapp_publico': 'Não usado para contato externo; contato bloqueado por não-MQL.',
}

p.RESEARCH['ekizian@sectorone.com.br'] = {
    'slug': 'sectorone-brand-business-fabio-ekizian',
    'mql': False,
    'empresa_real': 'SectorOne Brand&Business DVLP — agência/escritório de marketing, branding e desenvolvimento de marca ligada a Fabio Ekizian, com domínio sectorone.com.br.',
    'dominio_site': 'sectorone.com.br; LinkedIn público SectorOne Brand&Business DVLP classifica a empresa em Advertising Services, 11 a 50 funcionários; RocketReach/ZoomInfo e portfólio público citam marketing agency, branding, business e conteúdo.',
    'redes': 'Pesquisa pública real no ciclo: Claude Code com WebSearch/WebFetch; buscas por SectorOne, sectorone.com.br e Fabio Ekizian. Resultados públicos encontrados: LinkedIn da empresa, RocketReach, ZoomInfo e posts/portfólio que associam Fabio Ekizian à SectorOne Brand&Business em campanhas e produção de conteúdo/brand work. A atividade real encontrada é marketing/branding, não autopeças.',
    'segmento': 'Serviços de marketing, publicidade, branding, conteúdo e desenvolvimento de marca.',
    'motivo': 'Reprovado no crivo MQL acirrado/fail-closed: o formulário marcou autopeças e ERP Omie, mas a pesquisa pública confirmou que a empresa real do domínio é agência de marketing/branding (Advertising Services). Serviço/consultoria/marketing não é ICP T1 de indústria, distribuidor, importador ou atacado com catálogo, preço, estoque e pedidos recorrentes de revendas/lojistas. Não deve receber diagnóstico externo automático.',
    'insight': '',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 11 99533-0099. Claude Code também encontrou WhatsApp público do site +55 11 96607-0110, mas não usado por ser não-MQL.',
    'whatsapp_publico': 'Não usado para contato externo; contato bloqueado por não-MQL.',
}

p.RESEARCH['karina@charthie.com.br'] = {
    'slug': 'smarthie-karina-martins',
    'mql': False,
    'empresa_real': 'Smarthie / SMARTHIE LTDA — empresa de brindes corporativos personalizados, uniformes, presentes corporativos e estratégias de product marketing; domínio público smarthie.com.br e loja minhasmarthie.com.br.',
    'dominio_site': 'smarthie.com.br e minhasmarthie.com.br — site oficial informa brindes personalizados, kits corporativos, sistema de loja para empresas, +10.000 empresas atendidas, +10 anos de mercado e +5.000 produtos em linha; página A Smarthie relata evolução da Fabio’s Brindes para Smarthie.',
    'redes': 'Pesquisa pública real no ciclo: WebExtract do site smarthie.com.br, página A Smarthie e loja minhasmarthie.com.br; WebSearch por Smarthie/brindes/Karina/Charthie. Fontes confirmam atuação com brindes corporativos, presentes, uniformes, product marketing e lojas/kits para empresas; WhatsApp público +55 16 99196-6702. O e-mail do lead usa charthie.com.br, vinculado publicamente à Karina/consultoria de gestão, aumentando a cautela.',
    'segmento': 'Brindes corporativos personalizados e product marketing vendidos diretamente a empresas para campanhas, equipes, eventos e relacionamento, com componente de serviço/customização.',
    'motivo': 'Reprovado no crivo MQL acirrado/fail-closed: embora seja empresa real, com produto físico e venda B2B para empresas, a operação pública é de brindes personalizados/marketing promocional para cliente final corporativo, não indústria/distribuidor/importador/atacado abastecendo revendas/lojistas ou clientes recorrentes para estoque. Há componente forte de serviço, kit sob medida e campanha. Como há dúvida relevante sobre ICP T1, não deve receber diagnóstico externo automático.',
    'insight': '',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 11 98876-8020. Site oficial Smarthie publica WhatsApp corporativo +55 16 99196-6702, mas não usado por ser não-MQL.',
    'whatsapp_publico': 'Não usado para contato externo; contato bloqueado por não-MQL.',
}

if __name__ == '__main__':
    p.main()
