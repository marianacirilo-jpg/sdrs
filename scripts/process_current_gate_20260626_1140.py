#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-26 11:40Z com pesquisa real via Claude Code/WebSearch/WebFetch."""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p

# Pesquisa real feita via Claude Code/WebSearch/WebFetch em 2026-06-26 11:40Z.
p.RESEARCH['bruno@geralfilmes.com.br'] = {
    'slug': 'bbtudo-bruno-gottardi',
    'mql': False,
    'empresa_real': 'BBTUDO COMÉRCIO LTDA — CNPJ 54.012.436/0001-20, ME, aberta em 21/02/2024, ligada publicamente a Bruno Reis Gottardi; operação de loja online/seller de marketplace.',
    'dominio_site': 'O domínio do e-mail geralfilmes.com.br pertence à Geral Filmes, produtora audiovisual em São Paulo, e não à operação comercial BBTudo. O domínio real do negócio pesquisado é bbtudo.com.br.',
    'redes': 'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: site bbtudo.com.br, página do vendedor BBTudo no Mercado Livre, cadastro público Econodata/CNPJ e site Geral Filmes para checagem do domínio do e-mail.',
    'segmento': 'Varejo B2C/e-commerce multicategoria e seller de marketplace, com produtos de consumo vendidos ao consumidor final; não há evidência pública de atacado, indústria, importador ou distribuição para revendas/lojistas/estoque recorrente.',
    'motivo': 'Pesquisa pública confirmou operação real, porém fora do ICP T1. O negócio aparece como varejo online/seller de marketplace, com CNAEs varejistas e catálogo de consumo final. O campo do formulário “Revenda” indica que a empresa revende produtos, não que vende para revendedores; e “Vendemos para empreiteiros” ficou inconsistente com o domínio/evidência pública. Pelo crivo acirrado/fail-closed, não há prova de venda B2B recorrente de estoque para revendas/lojistas ou abastecimento comercial.',
    'insight': '',
    'telefone_publico': 'Não localizei telefone/WhatsApp público corporativo seguro. Único contato público encontrado foi atendimento@bbtudo.com.br; telefone do formulário/HubSpot: +55 11 98886-8871.',
    'whatsapp_publico': 'Não localizado com segurança; não usado porque o lead foi reprovado no crivo MQL acirrado.',
}

if __name__ == '__main__':
    p.main()
