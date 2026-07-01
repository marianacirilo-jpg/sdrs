#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-27 09:00 BRT com pesquisa real via Claude Code/WebSearch/WebFetch."""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p

p.RESEARCH['jose.carlos@grgrupo.com.br'] = {
    'slug': 'gr-grupo-brasil-agropecuaria-jose-carlos',
    'mql': True,
    'empresa_real': 'GR Grupo / Grande Rio — grupo brasileiro ligado à Grande Rio Reciclagem Ambiental, GR Higiene e Limpeza e BAP Brasil Agropecuária; operação industrial e atacadista de bens de consumo/insumos, com histórico desde 1972/1977 e contato público José Carlos de Carvalho no domínio grgrupo.com.br.',
    'dominio_site': 'grgrupo.com.br e compragr.com.br — site oficial do GR Grupo/GR Higiene e Limpeza; compraGR é loja B2B/e-commerce da GR Higiene e Limpeza. ABRA/Brazilian Renderers também vincula jose.carlos@grgrupo.com.br à Grande Rio Reciclagem Ambiental e ao site granderioambiental.com.br.',
    'redes': 'Pesquisa pública real neste ciclo via Claude Code/WebSearch/WebFetch: site grgrupo.com.br/a-empresa informa origem em 1977 na coleta de osso e sebo em frigoríficos, açougues e supermercados; compragr.com.br e LinkedIn público associam GR Higiene e Limpeza a marcas Barra, BioBrilho, Faísca, Pelouche e Bica; ABRA/Brazilian Renderers confirma Grande Rio Reciclagem Ambiental desde 1972, coleta diária de ossos e sebo bovino, processamento em farinha de carne e ossos/sebo para fabricação de rações, frota própria com 120 caminhões e contato José Carlos de Carvalho no e-mail jose.carlos@grgrupo.com.br.',
    'segmento': 'Indústria, atacado e distribuição B2B de produtos de higiene e limpeza e insumos/derivados de reciclagem animal, com marcas próprias, força de vendas CLT e representantes, venda para supermercados/varejo/atacado e reposição recorrente de estoque.',
    'motivo': 'O formulário declara faturamento de R$50 a R$500 milhões ao ano, +151 pessoas, 21 a 100 vendedores, venda por CLT e representantes, loja virtual ativa e dor de tentativa anterior de digitalização. A pesquisa pública confirmou empresa real e estruturada, domínio corporativo, e-commerce/loja B2B, marcas próprias e operação industrial/atacadista com venda recorrente para supermercados, varejo e atacado. Passa no crivo MQL acirrado por indústria/distribuição/atacado com alto giro, tabela/catálogo/preço e pedidos recorrentes de reposição de estoque.',
    'insight': 'supermercados, atacadistas e representantes comprarem/recomprarem pelo catálogo B2B com preço e disponibilidade corretos, sem repetir a digitalização frustrada em mais um canal manual',
    'telefone_publico': 'Telefone válido informado no HubSpot/formulário: +55 21 99851-5798. Fontes públicas da ABRA/Brazilian Renderers para José Carlos de Carvalho também mostram +55 49 99989-0578 e +55 48 99833-1919; site GR Grupo divulga SAC 0800 023 8247.',
    'whatsapp_publico': 'Não encontrei WhatsApp corporativo oficial publicado para o número do formulário; usar o celular válido do formulário +55 21 99851-5798. Como contatos públicos alternativos de José Carlos em associação setorial constam +55 49 99989-0578 e +55 48 99833-1919.',
}

if __name__ == '__main__':
    p.main()
