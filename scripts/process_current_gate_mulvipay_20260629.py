#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa o gate atual (MULVI PAY / Banese Card) com pesquisa pública real do ciclo."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import process_gate_once as p  # noqa: E402

p.RESEARCH['ernani.junior@banesecard.com.br'] = {
    'slug': 'mulvi-pay-banese-card-ernani',
    'mql': False,
    'empresa_real': 'MULVI PAY / Banese Card — operação ligada a cartão/meios de pagamento do Banese, com domínio corporativo banesecard.com.br e foco em produtos financeiros/cartões/soluções de pagamento, não em distribuição/indústria/atacado de produtos físicos.',
    'dominio_site': 'banesecard.com.br — site oficial ativo do Banese Card. A página pública se apresenta como Banese Card, com cartões para pessoa física e empresa, app, cartão virtual, fatura, negociação de dívida, benefícios, parceiros e atendimento pelo WhatsApp (79) 4002-2320. Não encontrei no site público evidência de indústria, distribuidora, importadora ou atacadista vendendo catálogo/estoque recorrente para revendas/lojistas.',
    'redes': 'Pesquisa pública real neste ciclo: web_search gerenciado falhou por erro externo de billing/quota, então foi feito acesso direto via urllib/curl ao site oficial https://www.banesecard.com.br/ e buscas Bing por "MULVI PAY"/"Banesecard". O site oficial retornou conteúdo público do Banese Card com descrição de inovação/produtos/serviços financeiros, cartões, aplicativo, cartão virtual, parceiros e atendimento. Busca local em pesquisas anteriores também registrava BANESE CARD como fit fraco para portal B2B de distribuição. Não houve fonte pública segura confirmando operação T1 de produto físico de alto giro, revenda ou abastecimento de estoque.',
    'segmento': 'Serviços financeiros/meios de pagamento/cartões para clientes que aceitam cartão. Embora o formulário declare B2B e faturamento alto, o vínculo operacional identificado é adquirência/cartão/pagamentos, não uma cadeia de produtos físicos com tabela, catálogo, preço e pedido recorrente de estoque para revendas/lojistas.',
    'motivo': 'Reprovado no crivo MQL acirrado/fail-closed: o formulário informa B2B, loja virtual, autosserviço e dor de demora no atendimento, mas a pesquisa pública aponta serviço financeiro/cartão/meio de pagamento. Não há evidência clara de indústria, distribuidor, importador ou atacado vendendo para revendas/lojistas/clientes recorrentes para abastecimento de estoque. Como serviço/fintech/meios de pagamento fica fora do ICP T1 de digitalização de catálogo/pedido B2B recorrente, não deve receber diagnóstico automático.',
    'insight': '',
    'telefone_publico': 'Telefone do formulário/HubSpot: +55 79 99114-6307 (não usado para contato externo porque foi classificado como não-MQL). Site oficial Banese Card publica atendimento (79) 4002-2320.',
    'whatsapp_publico': 'Não buscar/usar WhatsApp público para disparo externo: contato bloqueado por não-MQL. O site oficial publica canal de atendimento (79) 4002-2320, mas é central corporativa de serviços financeiros, não destino de diagnóstico.',
}

if __name__ == '__main__':
    p.main()
