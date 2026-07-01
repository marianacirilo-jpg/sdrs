#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-28 18:05 BRT — Natuflores, Ranalle, Latte Foods.
Pesquisa pública real via Claude Code/WebSearch/WebFetch executada no ciclo.
"""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

p.RESEARCH['comercial@natuflores.com.br'] = {
    'slug': 'natuflores-cosmeticos-wender-rodrigues',
    'mql': True,
    'empresa_real': 'Natuflores Indústria e Comércio de Cosméticos Ltda — indústria/fabricante de cosméticos, perfumaria e higiene pessoal em Goiânia/GO, CNPJ 04.084.834/0001-83, CNAE 2063-1/00.',
    'dominio_site': 'natuflores.com.br — site oficial ativo; presença pública confirma fabricante de cosméticos e canal “Quero Distribuir”.',
    'redes': 'Instagram @natuflorescosmeticosoficial, Facebook Natuflores Oficial e LinkedIn Natuflores. Pesquisa pública também encontrou diretórios empresariais/Econodata confirmando razão social, CNAE e porte.',
    'segmento': 'Indústria de cosméticos com venda B2B para farmácias, redes e distribuidores, além de loja própria. Operação de reposição recorrente e abastecimento de estoque para canais de revenda.',
    'motivo': 'Crivo T1 atendido: é indústria/fabricante de cosméticos com venda para redes, farmácias e distribuidores, canal de distribuição e reposição de estoque. O formulário reforça ICP: redes e farmácias/distribuidor, Sankhya, R$5 a R$10 milhões/ano, 21 a 100 pessoas, 6 a 20 vendedores e loja virtual. | HubSpot está como MQL: não rebaixar para Não-MQL; seguir diagnóstico.',
    'insight': 'farmácias, redes e distribuidores podem fazer reposição de produtos com mais autonomia, sem depender de troca manual de pedidos com cada vendedor',
    'telefone_publico': 'Diretórios públicos apontaram fixos (62) 3920-9450 e (62) 3210-5057; WhatsApp público seguro não localizado. O telefone válido do formulário é celular: 62985829823.',
    'whatsapp_publico': 'Não foi localizado WhatsApp público seguro; usar telefone celular válido informado no HubSpot/formulário: 62985829823.',
}

p.RESEARCH['thiago_@ranalle.com.br'] = {
    'slug': 'ranalle-thiago-ranalle',
    'mql': True,
    'empresa_real': 'Ranalle Componentes Automotivos Ltda — indústria e distribuidora de polias e tensionadores automotivos, fundada em 1993, São Paulo/SP.',
    'dominio_site': 'ranalle.com.br — site institucional ativo com páginas de distribuidora, sobre a empresa e linha de peças automotivas.',
    'redes': 'Instagram @ranalle.poliasetensores, Facebook Ranalle Polias e Tensores, LinkedIn da empresa e perfil público de Thiago Ranalle como diretor/proprietário. Pesquisa pública confirmou endereço e telefone fixo (11) 2020-4208.',
    'segmento': 'Indústria e distribuição de autopeças: polias e tensionadores para linha leve, pesada, agrícola e construção, com venda B2B para aftermarket/reparação em todo o Brasil.',
    'motivo': 'Crivo T1 atendido: fabricante e distribuidora de autopeças desde 1993, com catálogo de itens, estoque e recompra recorrente de revendas/oficinas/distribuidores do aftermarket automotivo. O formulário bate: distribuidoras e autopeças, TOTVS, R$50 a R$500 milhões/ano e 51 a 150 pessoas. | HubSpot está como MQL: não rebaixar para Não-MQL; seguir diagnóstico.',
    'insight': 'revendas e aplicadores conseguem consultar a linha de polias e tensionadores e repor itens de giro sem depender de atendimento manual para cada cotação',
    'telefone_publico': 'Telefone público fixo: (11) 2020-4208. O telefone válido do formulário é celular: 11976496997.',
    'whatsapp_publico': 'Não foi localizado WhatsApp público seguro; usar telefone celular válido informado no HubSpot/formulário: 11976496997.',
}

p.RESEARCH['gustavo@lattefoods.com.br'] = {
    'slug': 'latte-foods-ggc-alimentos-gustavo-soares',
    'mql': True,
    'empresa_real': 'GGC Alimentos Ltda (Latté Foods) — indústria de alimentos em Contagem/MG, CNPJ 42.971.278/0001-56, marca GranLatté.',
    'dominio_site': 'lattefoods.com.br — site oficial ativo, com páginas de contato e sobre a empresa, confirmando atuação em ingredientes lácteos e produtos para foodservice.',
    'redes': 'Instagram @soulattefoods, Facebook soulattefoods e LinkedIn Latté Foods. Pesquisa pública cruzou site oficial, CNPJ.biz e Econodata, confirmando a empresa GGC Alimentos Ltda/Latte Foods.',
    'segmento': 'Indústria de alimentos e bebidas, fabricante de ingredientes/substitutos de leite em pó para sorveterias, açaí, padarias, foodservice, confeitaria e outras operações B2B recorrentes.',
    'motivo': 'Crivo T1 atendido: indústria de alimentos com marca própria, venda B2B recorrente para sorveterias, padarias, foodservice e indústrias, via representantes e com compra online 24h. O formulário confirma: indústria de alimentos e bebidas, Omie, R$50 a R$500 milhões/ano, 21 a 100 pessoas, representação comercial e cliente compraria sozinho 24h. | HubSpot está como MQL: não rebaixar para Não-MQL; seguir diagnóstico.',
    'insight': 'sorveterias, padarias e foodservice podem recomprar ingredientes 24h com o representante acompanhando tudo, sem perder pedido no caminho',
    'telefone_publico': 'Telefone/WhatsApp público do site oficial: (31) 98493-0770; coincide com telefone válido do formulário 31984930770.',
    'whatsapp_publico': '(31) 98493-0770 — publicado no site oficial da Latté Foods como contato.',
}

if __name__ == '__main__':
    p.main()
