#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-off cron cycle processor for the current gate lead global@globalcomercioservicos.com.br.
Uses process_gate_once.py functions and injects the real Claude Code web research for this lead.
"""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p

p.RESEARCH['global@globalcomercioservicos.com.br'] = {
    'slug': 'global-crs-carlos-pragana',
    'mql': False,
    'empresa_real': "Global CRS LTDA — operação não confirmada publicamente a partir do domínio/e-mail globalcomercioservicos.com.br",
    'dominio_site': "globalcomercioservicos.com.br — não foi encontrado site/domínio ativo confiável ligado à operação do lead nas buscas públicas deste ciclo",
    'redes': "Pesquisa via Claude Code/WebSearch/WebFetch: buscas por Global CRS LTDA, globalcomercioservicos.com.br, Carlos Pragana, telefone DDD 81 e bases públicas/snippets; não houve fonte oficial que comprovasse indústria, distribuidor, importador ou atacado. Resultado aproximado CRS Comércio e Serviços em Recife não comprovou vínculo com o e-mail e aparece como varejo/atividade não aderente.",
    'segmento': "Indeterminado; sem evidência pública segura de operação B2B de estoque/catálogo, distribuição, importação, indústria ou atacado",
    'motivo': "Pesquisa pública real não confirmou empresa operacional aderente ao ICP T1. O domínio do e-mail não trouxe site ativo confiável, não houve CNPJ/site/rede social oficial da Global CRS LTDA e os resultados aproximados não comprovam distribuidor, importador, indústria ou atacado vendendo para revendas/lojistas/clientes recorrentes de estoque. O formulário mostra faturamento de R$5 a R$10 milhões, 11 a 25 pessoas e venda por WhatsApp, mas ERP 'Outro' e venda direta por contato não substituem ICP; pelo crivo MQL acirrado/fail-closed, dúvida relevante bloqueia qualificação.",
    'insight': '',
    'telefone_publico': "Não confirmado em fonte pública segura; telefone válido disponível apenas pelo formulário/HubSpot: +55 81 9577-1949",
    'whatsapp_publico': "Não confirmado publicamente; contato ao lead bloqueado por não-MQL",
}

if __name__ == '__main__':
    p.main()
