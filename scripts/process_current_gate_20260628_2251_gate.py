#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate 2026-06-28 22:51 UTC — American Steel, Elgin, Dovale.
Pesquisa real feita no ciclo com web_search/web_extract e consolidada abaixo.
"""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

p.RESEARCH['contato@americansteelincorporation.com.br'] = {
    'slug': 'american-steel-gian-lucca-barbosa-viana',
    'mql': True,
    'empresa_real': 'American Steel Incorporation / Loja American Steel — empresa de Sorocaba/SP, fundada em 2018, voltada a cubas e tanques de aço inox para cozinha, lavanderia e construção.',
    'dominio_site': 'americansteelincorporation.com.br e lojaamericansteel.com.br; páginas públicas descrevem American Steel Incorporation como fabricante/loja de cubas e tanques em aço inox 304/430, com estoque, e-commerce e venda por WhatsApp.',
    'redes': 'Pesquisa real no ciclo: web_search por americansteelincorporation.com.br/American Steel e web_extract da página institucional da loja. Resultados públicos: site oficial, Facebook American Steel Sorocaba, Instagram @lojaamericansteel, LinkedIn/RocketReach/ZoomInfo. Os snippets públicos citam empresa industrial, inovação em cubas de aço inox, contato comercial e comunicação direcionada a marmorarias, construtoras e marmoristas.',
    'segmento': 'Indústria/e-commerce de cubas e tanques de aço inox, com venda recorrente para marmorarias, construtoras e profissionais que especificam/abastecem obras.',
    'motivo': 'Qualificado no crivo MQL acirrado: operação industrial de produto físico padronizado, catálogo/estoque de cubas e tanques, loja virtual ativa, venda por WhatsApp e público aderente informado no formulário (marmorarias). Há potencial real para digitalizar catálogo, preço e pedidos recorrentes B2B para marmoristas/construtoras.',
    'insight': 'marmorarias e construtoras consultarem cubas por medida, acabamento e estoque sem depender de troca manual de fotos e preços no WhatsApp',
    'telefone_publico': 'HubSpot trouxe celular válido +55 31 98555-0860; pesquisa pública também encontrou WhatsApp/telefone comercial +55 11 97390-6161 em site/Facebook, não usado porque o telefone do lead é válido.',
    'whatsapp_publico': '+55 11 97390-6161 (fonte pública: lojaamericansteel.com.br/Facebook), apenas como referência; envio deve usar telefone válido do HubSpot.',
}

p.RESEARCH['claudio.santos@elgin.com.br'] = {
    'slug': 'elgin-claudio-santos',
    'mql': True,
    'empresa_real': 'Elgin — empresa brasileira de tecnologia, automação comercial, eletroportáteis, climatização, elétrica/iluminação e soluções para empresas.',
    'dominio_site': 'elgin.com.br; página oficial de Automação Comercial apresenta impressoras térmicas, leitores de código de barras, computadores, terminais de autoatendimento, balanças, gavetas e equipamentos de PDV para comércios de todos os portes.',
    'redes': 'Pesquisa real no ciclo: web_search por Elgin automação/revendas/hardware e web_extract da página oficial de automação comercial. Resultados públicos: site oficial elgin.com.br, Instagram Elgin Automação Comercial citando empresa brasileira com 74 anos e 20 anos em automação comercial, página oficial de automação comercial e resultados de revendedores autorizados Elgin.',
    'segmento': 'Fabricante/importadora e distribuidora de tecnologia e hardware para automação comercial, PDV e varejo, com ecossistema de revendas e equipamentos de alto giro para empresas.',
    'motivo': 'Qualificado no crivo MQL acirrado: domínio corporativo oficial e pesquisa pública indicam operação industrial/comercial B2B robusta, catálogo amplo de hardware para automação comercial e canal de revendas/empresas. O formulário cita revendas de tecnologia e hardware, loja virtual e dor de depender de poucos clientes grandes, aderente a pedidos recorrentes e digitalização B2B.',
    'insight': 'revendas e clientes de automação consultarem equipamentos, disponibilidade e condições por conta própria, reduzindo dependência de atendimento presencial e de poucos compradores grandes',
    'telefone_publico': 'HubSpot trouxe celular válido +55 41 99604-6288; não foi necessário recuperar telefone público para envio.',
    'whatsapp_publico': 'Não usado; telefone do HubSpot é válido.',
}

p.RESEARCH['andreza.santos@dovale.com.br'] = {
    'slug': 'dovale-andreza-santos',
    'mql': True,
    'empresa_real': 'Dovale — indústria/distribuidora brasileira especializada em soluções de segurança, chaves, ferragens, máquinas copiadoras, cadeados, fechaduras e acessórios para chaveiros/profissionais.',
    'dominio_site': 'dovale.com.br e loja.dovale.com.br; o site oficial informa atuação desde 1988, duas plantas produtivas, lojas em todos os estados, distribuição em 5 países e posição de maior distribuidora nacional de soluções de segurança; a loja vende tudo para chaveiro com WhatsApp e e-commerce.',
    'redes': 'Pesquisa real no ciclo: web_extract do site oficial Dovale e da loja Dovale Chaves; web_search por Dovale distribuidora nacional/profissionais/ferragens. Fontes públicas confirmam catálogo com máquinas copiadoras, chaves automotivas, cadeados, claviculários, cofres e fechaduras, atendimento para profissionais de chaveiro e loja virtual com WhatsApp +55 12 3212-1000.',
    'segmento': 'Distribuidora/indústria de segurança, ferragens e tecnologia para chaveiros e profissionais, com catálogo amplo, e-commerce e recorrência de reposição/abastecimento.',
    'motivo': 'Qualificado no crivo MQL acirrado: distribuidora nacional/indústria com catálogo amplo, venda para profissionais de chaveiro em todo o Brasil, loja virtual, alto volume operacional e formulário forte (21 a 100 pessoas/vendedores, loja virtual, cliente compra sozinho). Aderência direta a catálogo, preço e pedido recorrente B2B.',
    'insight': 'chaveiros e profissionais comprarem máquinas, chaves e ferragens recorrentes no autosserviço, com preço e disponibilidade atualizados sem sobrecarregar o time comercial',
    'telefone_publico': 'HubSpot trouxe celular válido +55 12 98849-1808; pesquisa pública também confirmou WhatsApp corporativo +55 12 3212-1000 no site/loja, não usado porque o telefone do lead é válido.',
    'whatsapp_publico': '+55 12 3212-1000 (fonte pública: dovale.com.br/loja.dovale.com.br), apenas como referência; envio deve usar telefone válido do HubSpot.',
}

if __name__ == '__main__':
    p.main()
