#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-off do ciclo gate 2026-06-26 20:31 BRT com pesquisas reais via Claude Code."""
import importlib.util
from pathlib import Path

_module_path = Path(__file__).resolve().parent / 'process_gate_once.py'
_spec = importlib.util.spec_from_file_location('process_gate_once', _module_path)
p = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(p)

p.RESEARCH.update({
    'rodrigobidoia@bmsdobrasil.com.br': {
        'slug': 'rodrigo-bidoia-bms-corretora-seguros',
        'mql': False,
        'empresa_real': 'BMS do Brasil Corretora de Seguros (BMS do Brasil Franchising e Soluções Digitais), vinculada publicamente a Rodrigo Bidoia',
        'dominio_site': 'bmsdobrasil.com.br — site institucional confirma corretora de seguros/soluções financeiras, não operação de estoque ou produto físico',
        'redes': 'Pesquisa pública real via Claude Code/WebSearch/WebFetch neste ciclo: site bmsdobrasil.com.br/quem-somos, LinkedIn de Rodrigo Bidoia, LinkedIn da BMS do Brasil Corretora de Seguros, Instagram/Facebook BMS do Brasil e ZoomInfo. Fontes confirmam corretora de seguros desde 2016, com seguradoras parceiras e serviços financeiros.',
        'segmento': 'Corretagem de seguros e soluções financeiras (consórcio, crédito e investimentos), serviço B2B/B2C sem catálogo de produto físico, estoque ou revenda/lojistas.',
        'motivo': 'Pesquisa pública confirmou empresa real, mas é corretora de seguros/serviços financeiros. Não vende produto físico, não tem estoque, catálogo, preço e pedido recorrente para revendas/lojistas ou abastecimento de estoque. A dor de carteira parada é comercial/relacionamento, não digitalização B2B de pedidos. Pelo crivo MQL acirrado/fail-closed, serviço fica não qualificado.',
        'insight': '',
        'telefone_publico': 'Telefone público localizado: (44) 3622-5380; WhatsApp público localizado: (44) 98806-8997. Não usado porque o lead foi reprovado no crivo MQL.',
        'whatsapp_publico': 'WhatsApp público (44) 98806-8997 localizado nas fontes da BMS; contato ao lead bloqueado por não-MQL.',
    },
    'marcio@comprarbem.com.br': {
        'slug': 'marcio-melo-novaplast-comercial',
        'mql': True,
        'empresa_real': 'Novaplast Comercial Ltda — comercial/distribuidora de insumos para comunicação visual, serigrafia, sublimação, insulfilm, envelopamento, tapeçaria e artesanato, ligada publicamente a Márcio José de Melo',
        'dominio_site': 'novaplastcomercial.com.br e loja comprarbem.com.br/novaplast.lojaintegrada.com.br — presença pública indica catálogo/e-commerce de insumos; algumas páginas tiveram redirect/conexão recusada no momento da pesquisa, mas fontes públicas externas confirmaram a operação',
        'redes': 'Pesquisa pública real via Claude Code/WebSearch/WebFetch neste ciclo: site Novaplast Comercial, LinkedIn Novaplast Comercial confirmando Márcio José de Melo, Instagram @novaplastcom, Facebook Novaplast, CNPJ 22.060.776/0001-30, loja Novaplast na Loja Integrada e página de parceria Gênesis Tintas.',
        'segmento': 'Comércio/distribuição de insumos de alto giro para comunicação visual, serigrafia, sublimação, insulfilm/envelopamento, tapeçaria, espumas e artesanato; abastece profissionais, aplicadores, oficinas/lojas e compradores recorrentes com vinis, lonas, adesivos, tintas e películas.',
        'motivo': 'Pesquisa pública confirmou operação comercial estabelecida desde 1986, com catálogo amplo de insumos consumíveis e venda para profissionais/aplicadores de comunicação visual, serigrafia, insulfilm e envelopamento. O formulário reforça fit: faturamento de R$1 a R$5 milhões, dor de demora no atendimento e cliente que compraria sozinho 24h. Passa no crivo MQL acirrado por distribuição/comércio técnico de produto físico de alto giro, com recompra e potencial claro de digitalizar catálogo, preço e pedido recorrente.',
        'insight': 'aplicadores e profissionais de comunicação visual recomprarem vinil, tintas e películas por catálogo digital com preço e disponibilidade, reduzindo a demora no atendimento e pedidos manuais no balcão ou WhatsApp',
        'telefone_publico': 'Telefones públicos localizados: (35) 3722-2760 e (35) 3721-6473; WhatsApp público não confirmado com segurança. Telefone do formulário/HubSpot é celular válido: +55 35 88175-922.',
        'whatsapp_publico': 'WhatsApp público não confirmado com segurança; usar telefone celular válido informado no formulário/HubSpot: +55 35 88175-922.',
    },
})

if __name__ == '__main__':
    p.main()
