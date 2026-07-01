#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate 2026-06-28 19:08 BRT — Coletek, Team Six, KS/Martins.
Pesquisa real: Claude Code com WebSearch/WebFetch + web_search/web_extract do ciclo.
"""
import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

# OBSOLETO/CORRIGIDO 2026-06-28:
# Este script pontual gerou confusão no caso KS/Martins. A regra final é:
# MQL manual/humano recente no HubSpot vence; MQL antigo/herdado de entrada
# não vence sozinho. Mantemos histórico, mas não usar este script em produção.
try:
    gate = json.loads(p.GATE.read_text(encoding='utf-8'))
    changed = False
    for lead in gate.get('leads', []):
        if (lead.get('email') or '').lower() == 'eltonjonis@ksdistribuidora.com.br':
            lead['gate_trigger'] = 'form_reentry_strict_review'
            props = lead.get('properties') or {}
            props['lifecyclestage'] = 'lead'
            changed = True
    if changed:
        p.GATE.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding='utf-8')
except Exception as e:
    print(f'ERRO preparando gate estrito KS: {e}')

p.RESEARCH['sato.marketing@coletek.com.br'] = {
    'slug': 'coletek-eduardo-sato',
    'mql': True,
    'empresa_real': 'Coletek / Coleção Indústria e Comércio de Informática, Telecomunicações e Eletrônica — empresa nacional fundada em 2003 em Varginha/MG, com escritório em São Paulo, presença em São Bento do Sul e unidade em Taiwan para desenvolvimento/comércio exterior.',
    'dominio_site': 'coletek.com.br — site oficial; página pública de carregadores informa indústria com área de 110.000 m², unidade em Taiwan e linhas de tecnologia. LinkedIn público descreve atuação baseada em indústria, distribuição e produtos de tecnologia.',
    'redes': 'Pesquisa pública real no ciclo: Claude Code/WebSearch/WebFetch; WebSearch por Coletek e Eduardo Sato; WebExtract de coletek.com.br/carregadores; resultados de LinkedIn, site oficial e catálogo público. Fontes confirmam empresa real de tecnologia/eletrônicos, marcas próprias e operação de indústria/distribuição. O formulário declara grandes varejos, lojas de informática e eletrônicos, sellers de marketplace e distribuidores regionais, coerente com a operação pública.',
    'segmento': 'Indústria e distribuidora de informática/eletrônicos/hardware, com venda B2B para grandes varejos, lojas de informática, sellers e distribuidores regionais; catálogo físico, preço, disponibilidade e conflito/abastecimento de canal são centrais.',
    'motivo': 'Crivo T1 atendido: empresa real e de porte, e-mail corporativo no domínio oficial, formulário declara grandes varejos, lojas de informática/eletrônicos, sellers de marketplace e distribuidores regionais, +151 pessoas, R$50 a R$500 milhões e loja virtual. Pesquisa pública confirmou indústria/distribuição de tecnologia e produtos físicos. Há potencial claro para digitalizar catálogo, preço, disponibilidade e pedidos de canais B2B/marketplace/revendas.',
    'insight': 'varejos, sellers e distribuidores regionais consultarem catálogo, preço e disponibilidade dos produtos Coletek para repor estoque sem depender de cada atendimento manual',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 11 98253-0509. Pesquisa pública confirmou domínio/empresa; nenhum WhatsApp corporativo alternativo mais seguro foi necessário.',
    'whatsapp_publico': 'Usar o celular válido informado no HubSpot/formulário: +55 11 98253-0509.',
}

p.RESEARCH['contato@team6.com.br'] = {
    'slug': 'team-six-guilherme-krieger',
    'mql': True,
    'empresa_real': 'Team Six / Teamsix Indústria e Comércio de Peças do Vestuário — marca brasileira de camisetas e roupas tático/militar/outdoor, com operação DTC e canal B2B de atacado.',
    'dominio_site': 'b2b-team6.com.br e teamsixbrasil.com.br — portal B2B público informa atacado, revenda e distribuição de camisetas masculinas e tático militar; preços exigem login/cadastro; site B2B lista combos, kits, camisetas e produtos para revenda.',
    'redes': 'Pesquisa pública real no ciclo: Claude Code/WebSearch/WebFetch; WebSearch por Team Six/Team6; WebExtract de b2b-team6.com.br. Fontes públicas confirmam canal B2B com “Atacado, Revenda e Distribuição”, kits/combos, catálogo de vestuário e preços fechados por login. Formulário declara lojas de roupas, ERP Bling, loja virtual e autosserviço.',
    'segmento': 'Marca/indústria/comércio de vestuário com canal atacado B2B para revendedores/lojas, além de DTC e marketplace; catálogo amplo de peças, grades, combos, preço e disponibilidade para reposição.',
    'motivo': 'Crivo T1 atendido apesar de borderline pelo porte: empresa real, canal B2B/atacado explícito, venda para revenda/distribuição, ERP Bling, faturamento R$1 a R$5 milhões e loja virtual. O portal B2B exige login para preço e mostra kits/combos para revendedores, caracterizando operação com tabela, catálogo e pedidos recorrentes. Há potencial para digitalizar pedido recorrente e sincronização de estoque/preço entre atacado, loja própria e marketplace.',
    'insight': 'revendedores e lojas consultarem grades, combos, preço e disponibilidade das camisetas para repor estoque sem depender de cada atendimento por WhatsApp',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 47 98832-1932. Pesquisa pública confirmou canal B2B; nenhum WhatsApp corporativo alternativo mais seguro foi necessário.',
    'whatsapp_publico': 'Usar o celular válido informado no HubSpot/formulário: +55 47 98832-1932.',
}

p.RESEARCH['eltonjonis@ksdistribuidora.com.br'] = {
    'slug': 'ks-distribuidora-elton-jonis',
    'mql': False,
    'empresa_real': 'Identidade não verificada com segurança. O formulário usa “Martins Comércio e Serviço de Distribuição”, mas o e-mail/domínio é ksdistribuidora.com.br; Martins Distribuidor é uma empresa pública distinta e muito maior. O site ksdistribuidora.com.br não apresentou evidência pública suficiente neste ciclo e há múltiplas KS Distribuidora sem vínculo claro com Elton Jonis.',
    'dominio_site': 'ksdistribuidora.com.br — domínio do e-mail, mas a pesquisa pública/Claude Code indicou site inacessível ou sem confirmação operacional segura; martinsdistribuidor.com.br confirma o grupo Martins, porém não comprova vínculo com este lead/domínio.',
    'redes': 'Pesquisa pública real no ciclo: Claude Code/WebSearch/WebFetch; WebSearch por KS Distribuidora, Elton Jonis, ksdistribuidora.com.br e Martins Comércio e Serviço de Distribuição. Resultados confirmaram o Martins Atacado como grande atacadista/distribuidor, mas não confirmaram Elton Jonis ou ksdistribuidora.com.br como parte do Martins. Foram encontradas múltiplas empresas “KS Distribuidora”, sem vínculo inequívoco.',
    'segmento': 'Possível distribuição/atacado para supermercados via representantes comerciais, mas sem identidade positiva do lead/empresa neste ciclo.',
    'motivo': 'MQL no HubSpot era antigo/herdado da entrada, não marcação manual recente do time. Reprovado no crivo fail-closed por conflito de identidade pública neste ciclo.',
    'insight': '',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 11 99843-4989; não usado para contato externo porque o lead foi classificado como não-MQL por conflito de identidade.',
    'whatsapp_publico': 'Não usado para contato externo; exige validação humana do vínculo real antes de qualquer diagnóstico.',
}

if __name__ == '__main__':
    p.main()
