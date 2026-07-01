#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa o gate atual para Petgarden com pesquisa pública do ciclo 2026-06-30."""
from pathlib import Path
import sys
ROOT = Path('/root/.hermes/zydon-prospeccao')
sys.path.insert(0, str(ROOT / 'scripts'))
import process_gate_once as p

p.RESEARCH['junior@petgardens.com.br'] = {
    'slug': 'petgarden-adonis-marega-junior',
    'mql': True,
    'empresa_real': 'Pet Garden / Petgarden — operação com domínio oficial petgardens.com.br, loja online de produtos pet, jardinagem e hobby, contato Adonis Marega Junior.',
    'dominio_site': 'petgardens.com.br — site oficial ativo. A página inicial tem o título “Pet Garden | Sua loja de produtos pet, jardinagem e hobby”, loja/carrinho, categorias Pet e Jardinagem e menu “Compre no Atacado”. A página Sobre Nós traz “Atacado para Revenda” e descreve produtos para supermercados, agropecuárias, petshops e grandes redes, com frota própria, entregas e equipe de merchandising para abastecimento e organização no ponto de venda. A página Fale Conosco publica contato@petgardens.com.br e telefone/WhatsApp (19) 3579-2952.',
    'redes': 'Pesquisa pública real neste ciclo: web_search/web_extract gerenciados falharam por billing externo; fallback local por urllib/curl acessou https://petgardens.com.br, /sobre-nos/, /fale-conosco/ e /categoria-produto/atacado/. O site confirmou e-commerce WooCommerce com categorias pet e jardinagem, página de atacado, atacado para revenda, atendimento a supermercados, agropecuárias, petshops e grandes redes, frota própria, suporte de merchandising e telefone/WhatsApp corporativo. Buscas textuais via Bing foram pouco úteis/ruidosas, então a fonte confiável usada foi o site oficial e os campos do formulário.',
    'segmento': 'Fornecedor/atacado para revenda de produtos pet e jardinagem, atendendo supermercados, agropecuárias, petshops e grandes redes; produto físico de reposição, catálogo, preço, estoque, entrega e abastecimento do ponto de venda.',
    'motivo': 'Passa no crivo MQL acirrado: o formulário recente informa atuação em supermercados, 11 a 25 pessoas, 2 a 5 vendedores, faturamento de R$500 mil a R$1 milhão/ano, venda hoje por e-mail, dor de depender de poucos clientes grandes e crença de que o cliente compraria sozinho 24h. A pesquisa pública confirmou site oficial ativo com “Compre no Atacado” e “Atacado para Revenda”, produtos para supermercados, agropecuárias, petshops e grandes redes, além de frota própria e equipe de merchandising para abastecimento e organização no ponto de venda. Há fit claro para digitalizar catálogo, tabela, disponibilidade e pedidos recorrentes de clientes comerciais.',
    'insight': 'supermercados, agropecuárias, petshops e grandes redes consultarem catálogo, preço e disponibilidade de itens pet e jardinagem para repor o ponto de venda sem depender de cada pedido por e-mail',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 19 97406-2555; site oficial publica telefone/WhatsApp corporativo (19) 3579-2952.',
    'whatsapp_publico': 'Usar o celular válido recebido no HubSpot/formulário: +55 19 97406-2555.',
}

if __name__ == '__main__':
    p.main()
