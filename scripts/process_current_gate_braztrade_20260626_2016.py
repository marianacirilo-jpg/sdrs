#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-26 20:16 UTC — Braztrade."""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

p.RESEARCH['eduardo@braztrade.com.br'] = {
    'slug': 'braztrade-comercio-eduardo',
    'mql': False,
    'empresa_real': 'Braztrade Comércio Ltda ligada ao contato Eduardo Racy Abdalla, telefone DDD 62/Goiânia-GO; cadastro público mais aderente ao lead aponta empresa recente com atividade de comércio varejista pet. Há homônimo Braztrade Ltda em Franca/SP/Itajaí-SC com atividades atacadistas, mas sem vínculo seguro com este email/telefone.',
    'dominio_site': 'braztrade.com.br não apresentou site institucional ativo/confiável na pesquisa; domínio não comprovou operação B2B, atacadista, distribuidora ou importadora ligada ao Eduardo do lead.',
    'redes': 'Pesquisa pública neste ciclo encontrou Instagram @braztrade com descrição genérica sobre produtos naturais/campo ao consumidor; resultados de CNPJ/Econodata/JusBrasil/CNPJ.biz para Braztrade Comércio Ltda associaram Eduardo e o telefone do lead, mas não comprovaram venda B2B recorrente para revendas/lojistas. Também apareceram homônimos/empresas Braztrade de couros/café/calçados em outros estados, tratados como não conclusivos para este contato.',
    'segmento': 'Comércio/varejo pet ou comércio genérico recente, sem evidência clara de indústria, distribuidor, importador ou atacado com catálogo, preço e reposição recorrente para revendas/lojistas.',
    'motivo': 'Classificação fail-closed: o lead entrou por formulário de demonstração, mas os campos de diagnóstico vieram vazios (ERP, faturamento, dor, canal e vende-para). A pesquisa pública não confirmou ICP T1; o registro que mais casa com email/telefone/DDD aponta varejo/comércio, enquanto as evidências atacadistas pertencem a homônimos sem vínculo seguro. Sem prova clara de B2B recorrente/estoque, não marcar como qualificado.',
    'insight': '',
    'telefone_publico': 'Telefone informado no formulário/HubSpot: +55 62 99971-5333; não usado porque o lead foi reprovado no crivo MQL acirrado.',
    'whatsapp_publico': 'Não usado neste ciclo; contato ao lead bloqueado por não-MQL.',
}

if __name__ == '__main__':
    p.main()
