#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-28 12:41 BRT — Delícias do Interior."""
import sys
from pathlib import Path
PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p

p.RESEARCH['contato@deliciasdointerior.com.br'] = {
    'slug': 'delicias-do-interior-fernando-ruiz',
    'mql': False,
    'empresa_real': 'Delícias do Interior / Fernando Henrique Ruiz — empresa ativa em Bauru/SP, CNPJ 37.277.513/0001-54, fundada em 2020, vinculada ao contato Fernando Henrique Ruiz. O formulário informa atuação com padarias, conveniências, mercados e adegas, mas a presença pública encontrada é limitada a cadastros de CNPJ e não confirma operação atacadista/distribuidora estruturada.',
    'dominio_site': 'deliciasdointerior.com.br — domínio do e-mail do lead; tentativas de acesso ao domínio raiz e páginas de contato retornaram timeout/sem conteúdo útil no ciclo. Não foi localizado site institucional/e-commerce/catálogo ativo com evidência de atacado, distribuição, fábrica ou canal de revenda.',
    'redes': 'Pesquisa pública real neste ciclo: buscas por "Delícias do Interior" + Fernando Ruiz + contato@deliciasdointerior.com.br, CNPJ 37.277.513/0001-54, Bauru e termos de alimentos. Resultados úteis encontrados em Serasa Experian, Econodata, Jusbrasil e Casa dos Dados confirmam razão/nome fantasia, CNPJ ativo e localização em Bauru/SP. Não foram encontrados Instagram/site/catálogo público confiáveis da empresa, nem evidência pública de venda recorrente para revendas/lojistas ou abastecimento de estoque. O domínio informado ficou indisponível/sem scrape útil no ciclo.',
    'segmento': 'Alimentos/doces/mercearia com possível venda local para padarias, conveniências, mercados e adegas segundo o formulário, mas com faturamento baixo (R$250 mil a R$500 mil/ano), equipe de 1 a 10 pessoas, 1 vendedor, venda presencial, sem loja virtual e ERP Outro. A pesquisa pública não confirmou indústria, distribuidor, importador ou atacado T1 com catálogo, tabela de preço, estoque e pedidos recorrentes digitalizáveis.',
    'motivo': 'Fail-closed pelo crivo MQL acirrado: embora o formulário cite clientes como padarias, conveniências, mercados e adegas, faltou evidência pública de operação T1 de indústria/distribuição/atacado ou canal de revenda estruturado. O porte informado é pequeno, a venda principal é presencial, não há loja virtual, o ERP é Outro e o domínio/site não confirmou catálogo, atacado ou distribuição recorrente. Como há dúvida relevante sobre ICP e potencial real de digitalização B2B, não marcar MQL e não enviar diagnóstico ao lead.',
    'insight': '',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 14 99751-1020. Bases públicas exibem dados parcialmente mascarados/indiretos; não usei para contato externo porque o lead foi classificado como não-MQL.',
    'whatsapp_publico': 'Não foi necessário buscar/usar WhatsApp público para disparo, pois o lead foi reprovado no crivo MQL; telefone do formulário é celular válido, mas bloqueado para abordagem externa por regra de não-MQL.',
}

if __name__ == '__main__':
    p.main()
