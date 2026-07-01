#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-28 23:41 UTC com pesquisa pública real do ciclo."""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

# Reusa pesquisas reais consolidadas no ciclo imediatamente anterior para leads que retornaram no gate,
# e acrescenta Gerva Service pesquisado por curl direto no site oficial neste ciclo.
p.RESEARCH['contato@porummundomelhor.net'] = {
    'slug': 'por-um-mundo-melhor-arnaldo-de-freitas',
    'mql': True,
    'empresa_real': 'Por um Mundo Melhor — distribuidora de alimentos B2B em São Paulo, com foco em abastecimento de restaurantes, padarias, pizzarias, hamburguerias, cozinhas industriais e franquias.',
    'dominio_site': 'porummundomelhor.net — site oficial ativo. A página se posiciona como distribuidora de alimentos B2B em SP, divulga catálogo, cotação por WhatsApp, faturamento PJ, pedido mínimo, logística refrigerada própria e distribuição autorizada de Scala e Aurora, além de marcas como Solito, Camil, Galo e Andorinha.',
    'redes': 'Pesquisa real no ciclo: tentativa web_search falhou por billing do provedor, então foi usado acesso direto/curl/site oficial e histórico de pesquisa salvo. O site porummundomelhor.net informa WhatsApp corporativo +55 11 95608-3848, e-mail contato@porummundomelhor.net, CNPJ 13.485.739/0001-82 e endereço na Vila Matilde/SP. O campo company do formulário veio como Assembleia Legislativa de São Paulo, mas o domínio/e-mail e o site demonstram a operação da distribuidora Por um Mundo Melhor.',
    'segmento': 'Distribuidora atacadista de alimentos, carnes, laticínios, hortifruti e frios para cozinhas profissionais, restaurantes, padarias e franquias, com reposição recorrente e abastecimento de estoque.',
    'motivo': 'Qualificado no crivo MQL acirrado: distribuidora B2B com catálogo de alimentos, pedido mínimo, faturamento PJ, logística refrigerada e clientes que compram recorrente para abastecer cozinhas/estoque. ERP Omie no formulário acelera, mas o que qualifica é o ICP de distribuição/abastecimento B2B.',
    'insight': 'restaurantes, padarias e cozinhas industriais cotarem reposição de carnes, laticínios e frios com preço e disponibilidade atualizados sem depender de pedidos soltos no WhatsApp',
    'telefone_publico': 'HubSpot trouxe celular válido +55 11 96443-0677. O site oficial também divulga WhatsApp corporativo +55 11 95608-3848; manter envio no telefone informado pelo lead e registrar o corporativo como referência pública.',
    'whatsapp_publico': '+55 11 95608-3848, fonte pública: botões WhatsApp do site porummundomelhor.net.',
}

p.RESEARCH['wellington@gervaservice.com.br'] = {
    'slug': 'gerva-service-wellington-ribeiro',
    'mql': False,
    'empresa_real': 'Gerva Service — empresa de venda, remanufatura, manutenção e assistência técnica de equipamentos fitness, atendendo academias e estúdios com peças, manutenção preventiva/corretiva e serviços técnicos.',
    'dominio_site': 'gervaservice.com.br — site oficial ativo. Título: “Venda de equipamentos novos e remanofaturados, especialista em remanofatura de equipamentos fitness”. Home e menu exibem peças para esteiras, bikes e musculação, loja WooCommerce, montagem/reforma de equipamentos, visita técnica para orçamentos e troca de peças.',
    'redes': 'Pesquisa pública real neste ciclo: acesso direto via Python/urllib a https://gervaservice.com.br retornou HTTP 200. Texto do site confirma “Atendemos academias e estúdios com peças originais, manutenção preventiva e assistência técnica especializada”, “Peças para Esteiras”, “Peças para Bikes”, “Peças para Musculação” e “Manutenção Preventiva e corretiva”. O formulário informa faturamento “Ainda não faturamos”, 1 vendedor, 1 a 10 pessoas, ERP Outro e área “outros”.',
    'segmento': 'Serviço/assistência técnica e comércio de peças/equipamentos fitness para academias e estúdios. Há e-commerce e produtos físicos, mas a operação pública é majoritariamente serviço/manutenção/remanufatura, não indústria/distribuidor/importador/atacado T1 vendendo para revendas/lojistas com abastecimento recorrente de estoque.',
    'motivo': 'Reprovado no crivo MQL acirrado/fail-closed: apesar de site ativo e venda de peças/equipamentos, a empresa se posiciona como serviço técnico/remanufatura/manutenção para academias e estúdios; o formulário informa que ainda não fatura e área “outros”. Não há evidência clara de ICP T1 de atacado/distribuição/indústria/importação com venda recorrente para revendas/lojistas ou abastecimento de estoque. Portanto não recebe diagnóstico externo automático.',
    'insight': '',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 11 94030-9026; não usado para contato externo porque o lead foi classificado como não-MQL.',
    'whatsapp_publico': 'Não necessário para envio; contato externo bloqueado por não-MQL.',
}

p.RESEARCH['contato@deliciasdointerior.com.br'] = {
    'slug': 'delicias-do-interior-fernando-ruiz',
    'mql': True,
    'empresa_real': 'Delícias do Interior — operação de alimentos/doces com venda declarada para padarias, conveniências, mercados e adegas.',
    'dominio_site': 'deliciasdointerior.com.br — domínio corporativo do e-mail. No ciclo atual, tentativas diretas em https/http via Python/urllib terminaram em timeout; não foi possível confirmar conteúdo do site dentro da janela do cron.',
    'redes': 'Pesquisa real no ciclo: tentativa web_search falhou por billing do provedor; foram feitas tentativas diretas de acesso ao domínio deliciasdointerior.com.br, que expiraram. O formulário veio como MQL manual/humano no HubSpot e declara venda para padarias, conveniência, mercados e adegas, entrada por campanha MQL e dor de escalar sem contratar.',
    'segmento': 'Alimentos para canais comerciais como padarias, conveniências, mercados e adegas; potencial de reposição B2B se a operação for realmente distribuidora/fornecedora para esses pontos.',
    'motivo': 'Qualificado por status MQL manual recente no HubSpot e declaração operacional do formulário: vende para padarias, conveniências, mercados e adegas. Observação operacional: a prova pública ficou limitada porque o site oficial não respondeu no ciclo; seguir com cuidado comercial e validar contexto na conversa.',
    'insight': 'padarias, mercados e conveniências consultarem sabores, disponibilidade e reposição de produtos sem depender de atendimento presencial a cada pedido',
    'telefone_publico': 'HubSpot trouxe celular válido +55 14 99751-1020; busca pública não encontrou número corporativo mais seguro dentro da janela do ciclo.',
    'whatsapp_publico': 'Não encontrado com segurança; usar telefone válido do HubSpot.',
}

if __name__ == '__main__':
    p.main()
