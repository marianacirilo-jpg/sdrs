#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-28 18:36 BRT — RTL, SolarPV, Bakof.
Pesquisa pública real via Claude Code/WebSearch/WebFetch + buscas web executadas no ciclo.
"""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

p.RESEARCH['alvaro@rtldistribuidora.com.br'] = {
    'slug': 'rtl-comercial-racoes-alvaro-teixeira',
    'mql': True,
    'empresa_real': 'RTL Comercial de Rações Teixeira LTDA / RTL Distribuidora — distribuidora de rações e artigos para cães, gatos, pássaros e cavalos, com operação em Fortaleza/Eusébio-CE.',
    'dominio_site': 'rtldistribuidora.com.br; Instagram oficial @rtldistribuidora.',
    'redes': 'Pesquisa pública real no ciclo: Instagram @rtldistribuidora informa rações e artigos para cães, gatos, pássaros e cavalos, atendimento de segunda a sexta 7h30-17h e WhatsApps (85) 99444-8128 / (85) 99933-4853; bases públicas/Yelp/Serasa/TRC confirmam RTL Comercial de Rações Teixeira LTDA ativa e endereço no CE.',
    'segmento': 'Distribuidora/atacado de rações e artigos pet/agro para lojas agropecuárias e petshops, com catálogo de produtos físicos, reposição recorrente de estoque e equipe de venda tirando pedidos.',
    'motivo': 'Crivo T1 atendido: o formulário informa lojas agropecuárias e petshop, ERP Bling, 21 a 100 pessoas, dor de vendedores gastando tempo só tirando pedido e cliente compraria sozinho 24h. A pesquisa pública confirmou empresa real de distribuição de rações/artigos para pets e agro, com atendimento por WhatsApp e mix de produtos de reposição recorrente para lojistas. Há potencial claro para digitalizar catálogo, preço, disponibilidade e pedidos de reposição de lojas agropecuárias/petshops. | HubSpot está como MQL: não rebaixar para Não-MQL; seguir diagnóstico.',
    'insight': 'lojas agropecuárias e petshops consultarem catálogo, preço e disponibilidade de rações para repor estoque sem depender de cada pedido manual ao vendedor',
    'telefone_publico': 'Telefone válido do HubSpot/formulário: +55 85 99444-8379. Instagram oficial publica WhatsApps corporativos alternativos +55 85 99444-8128 e +55 85 99933-4853.',
    'whatsapp_publico': 'Usar primeiro o telefone válido do HubSpot/formulário: +55 85 99444-8379; alternativos públicos no Instagram oficial: +55 85 99444-8128 / +55 85 99933-4853.',
}

p.RESEARCH['washington@solarpv.com.br'] = {
    'slug': 'solarpv-washington-santos',
    'mql': True,
    'empresa_real': 'SolarPV / Solar PV Geração de Energia LTDA — empresa mineira de energia solar com showroom em Belo Horizonte e centro de distribuição em Contagem, citada publicamente como distribuidora de equipamentos/kits fotovoltaicos para integradores.',
    'dominio_site': 'solarpv.com.br — site/domínio institucional; LinkedIn SolarPV informa showroom em BH, centro de distribuição em Contagem e mais de 10 anos de mercado.',
    'redes': 'Pesquisa pública real no ciclo: LinkedIn SolarPV descreve showroom em Belo Horizonte, centro de distribuição em Contagem e atuação em energia solar; Abrasel VDA/MG lista Solar PV com contato Washington Santos, e-mail washington@solarpv.com.br, celular/WhatsApp 31 98270-0866; PDF público de garantia do domínio solarpv.com.br confirma Solar PV Geração de Energia LTDA, endereço em Contagem/MG e telefone +55 31 2111-0063; Facebook/Instagram públicos comunicam soluções para projetos/geradores fotovoltaicos.',
    'segmento': 'Distribuidora/fornecedora de equipamentos e kits de energia solar fotovoltaica para integradores e projetos B2B, com catálogo técnico, orçamento, disponibilidade e recorrência por carteira de integradores.',
    'motivo': 'Crivo T1 atendido apesar do formulário pouco preenchido: o e-mail corporativo e fonte pública da Abrasel vinculam diretamente Washington Santos à SolarPV; a presença pública confirma empresa real com centro de distribuição, showroom e oferta de geradores/kits fotovoltaicos para integradores/projetos. É uma operação de distribuição técnica B2B com catálogo, preço, disponibilidade e cotações recorrentes, não apenas serviço pessoal. | HubSpot está como MQL: não rebaixar para Não-MQL; seguir diagnóstico.',
    'insight': 'integradores consultarem kits, disponibilidade e condições de equipamentos solares para fechar projetos sem depender de cada cotação manual por WhatsApp',
    'telefone_publico': 'Telefone válido do HubSpot/formulário e fonte pública Abrasel: +55 31 98270-0866. PDF público do site informa telefone institucional +55 31 2111-0063.',
    'whatsapp_publico': 'Usar o telefone/celular de Washington confirmado no HubSpot e na Abrasel: +55 31 98270-0866.',
}

p.RESEARCH['marcelo.freddi@bakof.com.br'] = {
    'slug': 'bakof-plasticos-marcelo-freddi',
    'mql': True,
    'empresa_real': 'Bakof Tec / Bakof Plásticos — indústria brasileira de reservatórios, caixas d’água, cisternas, fossas, filtros e soluções em polietileno/PRFV para construção, saneamento e revendas.',
    'dominio_site': 'bakof.com.br — site oficial ativo com catálogo e página de contato; página pública informa +55 55 3744 9900 e bakof@bakof.com.br.',
    'redes': 'Pesquisa pública real no ciclo: site oficial bakof.com.br e /contato confirmam a marca Bakof Tec, catálogo e contato +55 55 3744 9900; Instagram/Facebook oficiais Bakof Tec confirmam presença da indústria; resultados públicos mostram produtos vendidos por lojas de construção/revendas. Busca adicional encontrou post público com WhatsApp de diretor comercial, mas não usei automaticamente por não ser número corporativo/contato direto do lead.',
    'segmento': 'Indústria/fabricante de reservatórios, caixas d’água e soluções para construção/saneamento, com venda B2B para lojas de material de construção, revendas e distribuidores em escala nacional.',
    'motivo': 'Crivo T1 atendido: formulário informa lojas de materiais de construção, R$10 a R$50 milhões/ano, +151 pessoas, 6 a 20 vendedores, loja virtual e telemarketing. Pesquisa pública confirmou fabricante real com catálogo amplo e produtos físicos de reposição/compra técnica vendidos por revendas e lojas de construção. Há potencial claro para digitalizar catálogo, preço, disponibilidade e pedidos recorrentes de revendas. Porém o telefone recebido no HubSpot é fixo/inválido para WhatsApp, e a busca pública não encontrou WhatsApp corporativo seguro do próprio contato/empresa para envio automático. | HubSpot está como MQL: não rebaixar para Não-MQL; seguir diagnóstico apenas quando houver WhatsApp válido.',
    'insight': 'revendas e lojas de construção consultarem modelos, volumes e disponibilidade de reservatórios para repor pedidos sem depender de cada atendimento por telemarketing',
    'telefone_publico': 'Site oficial bakof.com.br publica telefone fixo +55 55 3744 9900 e e-mail bakof@bakof.com.br. Não encontrei WhatsApp corporativo seguro do contato Marcelo Freddi; post público com WhatsApp de diretor comercial não foi usado por não ser contato direto/canal corporativo geral seguro para este lead.',
    'whatsapp_publico': 'Não localizado WhatsApp corporativo seguro para envio automático ao lead; manter diagnóstico pendente e mover negócio para Leads Inválidos até confirmar WhatsApp válido.',
}

# Bakof: não permitir que a rotina tente “corrigir” fixo adicionando 9 ou use um celular de terceiro.
_orig_lookup = p.lookup_public_phone
def _safe_lookup_public_phone(email, company, research):
    if (email or '').lower() == 'marcelo.freddi@bakof.com.br':
        return None
    return _orig_lookup(email, company, research)
p.lookup_public_phone = _safe_lookup_public_phone

_orig_phone_variants = p.phone_variants_with_optional_9
def _safe_phone_variants(raw):
    # Evita transformar o fixo da Bakof (55 3744-9956 / 55 3744-9900) em celular inexistente.
    d = p.only_digits(raw)
    if d in {'5537449956', '555537449956', '5537449900', '555537449900'}:
        return []
    return _orig_phone_variants(raw)
p.phone_variants_with_optional_9 = _safe_phone_variants

if __name__ == '__main__':
    p.main()
