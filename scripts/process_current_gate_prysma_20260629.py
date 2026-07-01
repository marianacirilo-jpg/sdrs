#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa o gate atual (Prysma Tech) com pesquisa pública real do ciclo."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import process_gate_once as p  # noqa: E402

p.RESEARCH['contato@prysmatech.com.br'] = {
    'slug': 'prysma-tech-washington-nascimento',
    'mql': True,
    'empresa_real': 'Prysma Tech / W M do Nascimento — distribuidora/e-commerce B2B de equipamentos de fibra óptica e infraestrutura FTTH para provedores de internet, integradores e empresas que compram equipamentos de rede e reposição.',
    'dominio_site': 'prysmatech.com.br — site oficial ativo “Prysma Tech – A sua Loja”, com catálogo de produtos, área do cliente, orçamento, equipe comercial e departamentos como OLT, ONU/ONT, roteadores, switchs, cabos ópticos, caixas ópticas, splitters, conectores e ferramentas. O site publica WhatsApp comercial/central +55 91 3197-2160 e e-mail contato@prysmatech.com.br.',
    'redes': 'Pesquisa pública real neste ciclo: Claude Code com WebFetch/WebSearch acessou o site oficial prysmatech.com.br, a página Equipe Comercial, Produtos e fonte pública de CNPJ. A extração direta do site confirmou loja online estruturada, catálogo grande de OLT, ONU/ONT, GBIC, roteadores, switches, cabos ASU/drop, CTO, DIO, splitters, conectores e ferramentas para fibra, marcas como V-SOL, TP-Link, MikroTik, Huawei, IPCOM e Orientek, área do cliente, orçamento e venda por WhatsApp. Fonte pública de CNPJ indicou W M do Nascimento, CNPJ 12.121.341/0001-02, ativo desde 2010, Castanhal/PA/Ananindeua-PA.',
    'segmento': 'Distribuidora/revenda B2B de equipamentos de telecom e fibra óptica para provedores de internet, integradores e compradores recorrentes que precisam de catálogo, preço, disponibilidade e reposição de estoque de OLT, ONU, cabos, caixas ópticas, conectores, splitters, roteadores, switches e ferramentas.',
    'motivo': 'Passa no crivo MQL acirrado: o formulário informa provedores de internet, faturamento de R$5 a R$10 milhões/ano, venda principalmente por WhatsApp, 2 a 5 vendedores e dor de carteira parada. A pesquisa pública confirmou empresa real com domínio próprio, catálogo amplo de produtos físicos para redes FTTH, área do cliente, orçamento e equipe comercial. Embora o formulário diga “provedores de internet”, a operação pública é distribuidora/revenda B2B para esse mercado, com venda recorrente de estoque técnico e grande potencial para digitalizar catálogo, preço, disponibilidade, cotação e recompra.',
    'insight': 'provedores e integradores consultarem catálogo, preço e disponibilidade de OLT, ONU, cabos e acessórios ópticos para repor estoque sem depender de cada atendimento manual por WhatsApp',
    'telefone_publico': 'HubSpot trouxe celular válido do formulário: +55 91 98255-0017. Site oficial publica central/WhatsApp comercial +55 91 3197-2160 e a pesquisa Claude Code localizou WhatsApps públicos de consultores comerciais: Paola Iguchi +55 91 98431-6577, Helton Martins +55 91 98439-7759 e Ewerton Gadelha +55 91 98484-8975.',
    'whatsapp_publico': 'Usar primeiro o celular válido recebido no HubSpot/formulário: +55 91 98255-0017. WhatsApps públicos corporativos alternativos encontrados no site/equipe comercial: +55 91 98431-6577, +55 91 98439-7759 e +55 91 98484-8975.',
}

if __name__ == '__main__':
    p.main()
