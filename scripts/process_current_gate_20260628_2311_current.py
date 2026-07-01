#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa gate atual 2026-06-28 23:11 UTC.
Pesquisa pública real feita no ciclo por web_search/web_extract/curl e consolidada abaixo.
"""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'scripts'))
import process_gate_once as p  # noqa: E402

p.RESEARCH['contato@porummundomelhor.net'] = {
    'slug': 'por-um-mundo-melhor-arnaldo-de-freitas',
    'mql': True,
    'empresa_real': 'Por um Mundo Melhor — distribuidora de alimentos B2B em São Paulo, com foco em abastecimento de restaurantes, padarias, pizzarias, hamburguerias, cozinhas industriais e franquias.',
    'dominio_site': 'porummundomelhor.net — site oficial ativo. A página se posiciona como distribuidora de alimentos B2B em SP, divulga catálogo, cotação por WhatsApp, faturamento PJ, pedido mínimo, logística refrigerada própria e distribuição autorizada de Scala e Aurora, além de marcas como Solito, Camil, Galo e Andorinha.',
    'redes': 'Pesquisa real no ciclo: web_extract de https://porummundomelhor.net/. O site informa WhatsApp corporativo +55 11 95608-3848, e-mail contato@porummundomelhor.net, CNPJ 13.485.739/0001-82 e endereço na Vila Matilde/SP. Observação: o campo company do formulário veio como Assembleia Legislativa de São Paulo, mas o domínio/e-mail e o site demonstram a operação da distribuidora Por um Mundo Melhor.',
    'segmento': 'Distribuidora atacadista de alimentos, carnes, laticínios, hortifruti e frios para cozinhas profissionais, restaurantes, padarias e franquias, com reposição recorrente e abastecimento de estoque.',
    'motivo': 'Qualificado no crivo MQL acirrado: distribuidora B2B com catálogo de alimentos, pedido mínimo, faturamento PJ, logística refrigerada e clientes que compram recorrente para abastecer cozinhas/estoque. ERP Omie no formulário acelera, mas o que qualifica é o ICP de distribuição/abastecimento B2B.',
    'insight': 'restaurantes, padarias e cozinhas industriais cotarem reposição de carnes, laticínios e frios com preço e disponibilidade atualizados sem depender de pedidos soltos no WhatsApp',
    'telefone_publico': 'HubSpot trouxe celular válido +55 11 96443-0677. O site oficial também divulga WhatsApp corporativo +55 11 95608-3848; manter envio no telefone informado pelo lead e registrar o corporativo como referência pública.',
    'whatsapp_publico': '+55 11 95608-3848, fonte pública: botões WhatsApp do site porummundomelhor.net.',
}

p.RESEARCH['robertocarneiro@americasul.com'] = {
    'slug': 'america-sul-roberto-carneiro',
    'mql': True,
    'empresa_real': 'América Sul Semijoias / AmericaSul indústria e comércio — operação de semijoias/acessórios de moda voltada a lojas de bijuterias e semijoias em todo o Brasil.',
    'dominio_site': 'americasul.com — domínio corporativo localizado. No momento do ciclo a home retornou “Account Suspended” via extração, mas resultados públicos indexados e páginas sociais do domínio apontam catálogo em americasul.com/catalogos e contato comercial vendas@americasul.com / +55 19 3490-0009.',
    'redes': 'Pesquisa real no ciclo: web_search por americasul.com/semijoias encontrou Facebook oficial América Sul Semi Joias com chamada “Veja o catálogo de semijoias em nosso site americasul.com/catalogos” e “Líder no mercado B2B”; resultados públicos também apontam empresa em Limeira/SP no segmento de acessórios/semijoias. O formulário declara venda para “Lojas de bijuterias e semijoias em todo Brasil”, ERP Bling, faturamento R$1–5M, 11–25 pessoas e dor de escalar sem contratar.',
    'segmento': 'Indústria/comércio B2B de semijoias para lojas, revendas e varejistas de bijuterias, com catálogo de produtos e recompra de estoque.',
    'motivo': 'Qualificado no crivo MQL acirrado: indústria/comércio de produto físico, venda declarada para lojas de bijuterias e semijoias em todo Brasil, catálogo B2B público, ERP Bling e porte compatível. Há potencial real para digitalizar catálogo, preço e pedidos recorrentes de reposição para lojistas.',
    'insight': 'lojistas de bijuterias e semijoias recomprarem peças por catálogo digital, com preço e disponibilidade claros, sem depender de mostruário físico e atendimento manual a cada reposição',
    'telefone_publico': 'HubSpot trouxe celular válido +55 19 98224-8424; página pública de contato indexada informa telefone corporativo +55 19 3490-0009, não usado porque o telefone do lead é válido.',
    'whatsapp_publico': 'Não usado; telefone do HubSpot é celular válido do lead. Referência pública de contato corporativo: +55 19 3490-0009 em americasul.com/contato nos snippets.',
}

p.RESEARCH['contato@deliciasdointerior.com.br'] = {
    'slug': 'delicias-do-interior-fernando-ruiz',
    'mql': True,
    'empresa_real': 'Delícias do Interior — operação de alimentos/doces com venda declarada para padarias, conveniências, mercados e adegas.',
    'dominio_site': 'deliciasdointerior.com.br — domínio corporativo do e-mail. A tentativa de web_extract e curl no ciclo expirou/time-out; não foi possível confirmar conteúdo do site dentro da janela do cron.',
    'redes': 'Pesquisa real no ciclo: web_search por Delícias do Interior/Fernando Ruiz retornou poucos sinais úteis e o site oficial não respondeu dentro do timeout. O formulário, porém, veio como MQL manual/humano no HubSpot e declara venda para padarias, conveniência, mercados e adegas, entrada por campanha MQL e dor de escalar sem contratar.',
    'segmento': 'Alimentos para canais comerciais como padarias, conveniências, mercados e adegas; potencial de reposição B2B se a operação for realmente distribuidora/fornecedora para esses pontos.',
    'motivo': 'Qualificado por status MQL manual recente no HubSpot e declaração operacional do formulário: vende para padarias, conveniências, mercados e adegas. Observação operacional: a prova pública ficou limitada porque o site oficial não respondeu no ciclo; seguir com cuidado comercial e validar contexto na conversa.',
    'insight': 'padarias, mercados e conveniências consultarem sabores, disponibilidade e reposição de produtos sem depender de atendimento presencial a cada pedido',
    'telefone_publico': 'HubSpot trouxe celular válido +55 14 99751-1020; busca pública não encontrou número corporativo mais seguro dentro da janela do ciclo.',
    'whatsapp_publico': 'Não encontrado com segurança; usar telefone válido do HubSpot.',
}

if __name__ == '__main__':
    p.main()
