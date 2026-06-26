#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa /tmp/gate_qualified.json para o ciclo autônomo Zydon.
One-off/cron helper: HubSpot lifecycle+owner, PDF, WhatsApp, atividades e controles.
"""
import json, os, re, sys, time, shutil, subprocess, urllib.request, urllib.error, fcntl, atexit
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PROJ = Path(__file__).resolve().parents[1]
GATE = Path('/tmp/gate_qualified.json')
PROCESSED = PROJ/'controle'/'processed_emails.txt'
WPP = PROJ/'controle'/'wpp_envios.json'
PESQ = PROJ/'pesquisas'
PDFS = PROJ/'pdfs'
MOTOR = PROJ/'motor'
GROUP = '120363408131718880@g.us'
HS = 'https://api.hubapi.com'
DEALS_PIPELINE_ID = '671008549'
DEALSTAGE_LEADS_INVALIDOS = '1388724005'
TOKEN_PATH = Path('/root/.hermes/credentials/hubspot.env')
OWNER_MAP = {
    '88063842': {'nome':'Sarah', 'porta':4601, 'portas':[4601], 'assinatura':'Aqui é a Sarah, da Zydon', 'agenda':'https://meetings.hubspot.com/sarah-bento'},
    # Breno usa somente o chip ativo 4605; 4602 foi removido/desativado.
    '86265630': {'nome':'Breno', 'porta':4605, 'portas':[4605], 'assinatura':'Aqui é o Breno, da Zydon', 'agenda':'https://meetings.hubspot.com/breno-mendonca'},
    '85778446': {'nome':'Lucas Batista', 'porta':4603, 'assinatura':'Aqui é o Lucas Batista, da Zydon', 'agenda':'https://meetings.hubspot.com/lucas-alcantara-nogueira-batista'},
}
INSTITUTIONAL_PORTS = {
    4600: {'nome':'Mariana', 'assinatura':'Aqui é a Mariana, da Zydon'},
    4606: {'nome':'Lucas Resende', 'assinatura':'Aqui é o Lucas Resende, da Zydon'},
    4607: {'nome':'Rafael', 'assinatura':'Aqui é o Rafael, da Zydon'},
    4609: {'nome':'João Pedro', 'assinatura':'Aqui é o João Pedro, da Zydon'},
    4610: {'nome':'Gustavo', 'assinatura':'Aqui é o Gustavo, da Zydon'},
}
INSTITUTIONAL_ROTATION_PORTS = [4600, 4606, 4607, 4609, 4610]
DEFAULT_OWNER = {'nome':'Institucional', 'porta':4600, 'portas':INSTITUTIONAL_ROTATION_PORTS, 'assinatura':'Aqui é a Mariana, da Zydon'}
# Não-MQL: aviso no grupo sai pela rotação institucional/comunicadores.
# 4604 foi removido/desativado e deve ser ignorado no SAF/MQL.
# A task de não-MQL também NÃO deve ser atribuída ao SDR (Sarah/Breno/Lucas Batista)
# — 'owner_id' None = não atribui ao SDR.
NON_MQL_NOTIFY_OWNER = {'nome':'Institucional', 'porta':4600, 'portas':INSTITUTIONAL_ROTATION_PORTS, 'assinatura':'Aqui é a Mariana, da Zydon', 'owner_id': None}

# Pesquisa feita via Claude Code neste ciclo (salva também em pesquisas/*.md)
RESEARCH = {
 'contato@ceramicaanaclaudia.com.br': {
   'slug':'ceramica-ana-claudia', 'mql': True,
   'empresa_real':'Cerâmica Ana Cláudia (Ceramica Ana Claudia Ltda) — fabricante de cerâmica decorativa de Porto Ferreira-SP, com produção própria para linhas Home, Cozinha, Festa e Garden',
   'dominio_site':'ceramicaanaclaudia.com.br — site oficial; pesquisa pública também confirmou a marca em guias locais e em varejistas/revendas de decoração que vendem produtos Cerâmica Ana Cláudia',
   'redes':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo: site oficial ceramicaanaclaudia.com.br, Instagram @ceramicaanaclaudia, Facebook oficial, Guia Porto Ferreira/Guiandu, Pistache Casa e Ponto da Porcelana vendendo/listando a marca; CNPJ/razão social Ceramica Ana Claudia Ltda apareceu em bases públicas. Cuidado: não confundir com Ana Atacado, outra empresa de Porto Ferreira.',
   'segmento':'Indústria/fabricante de cerâmica decorativa em Porto Ferreira-SP que abastece lojistas, decoradores e revendas por representantes e WhatsApp, com produtos de catálogo e reposição recorrente de estoque.',
   'motivo':'Pesquisa pública real confirmou ICP T1: fabricante de cerâmica decorativa com produção própria, presença em revendas/lojas de decoração e modelo informado no formulário de venda por representantes e WhatsApp. O formulário reforça fit com público de lojistas de decoração, sem loja virtual e cliente com potencial de compra sozinho 24h. Mesmo com faturamento baixo e ERP Outro, passa no crivo acirrado por indústria vendendo produto físico de catálogo para lojistas/revendas com reposição recorrente de estoque.',
   'insight':'lojistas de decoração consultarem catálogo, linhas e reposição de peças de cerâmica sozinhos, diminuindo pedidos soltos pelo WhatsApp e a dependência do representante para cada recompra',
   'telefone_publico':'Telefone público em ficha local: +55 19 3581-3125; telefone do formulário/HubSpot é celular válido: +55 19 99207-0375',
   'whatsapp_publico':'WhatsApp público em ficha local vinculada ao domínio oficial: +55 19 97172-9683; para lead, usar celular válido informado no formulário/HubSpot: +55 19 99207-0375',
 },
 'alkcosmeticos@alk.com.br': {
   'slug':'alk-cosmeticos-exohair-distribuidor-rj', 'mql': True,
   'empresa_real':'ALK Cosméticos — Exohair Distribuidor Rio de Janeiro, distribuidor regional da Exo Hair/Koosmetics para salões de beleza no RJ',
   'dominio_site':'Sem site próprio confiável confirmado para ALK Cosméticos; pesquisa pública apontou redes oficiais Exohair Distribuidor Rio de Janeiro e a página da Exo Hair/Koosmetics. Ressalva: o domínio alk.com.br pertence a uma agência de marketing em Montes Claros/MG e não comprova a distribuidora.',
   'redes':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo: Instagram @exo_distribuidor_rio, Facebook “Exohair Distribuidor Rio de Janeiro” e página pública da Exo Hair sobre rede de distribuidores autorizados por região. O formulário informa Exohair Distribuidor Rio de Janeiro, salões de beleza, Omie, venda porta a porta/WhatsApp e faturamento de R$1 a R$5 milhões.',
   'segmento':'Distribuidor de cosméticos capilares profissionais para salões de beleza no Rio de Janeiro, com revenda B2B recorrente para reposição de estoque de produtos de tratamento/alisamento.',
   'motivo':'Pesquisa pública real confirmou operação aderente ao ICP: distribuidor regional de cosméticos profissionais para salões, com venda B2B recorrente e necessidade de catálogo, preço, condição comercial e reposição de produtos. O formulário reforça fit com Omie, faturamento de R$1 a R$5 milhões e venda por porta a porta/WhatsApp. A ressalva é o domínio do e-mail, que não comprova a empresa, mas as redes e o formulário sustentam a qualificação.',
   'insight':'salões consultarem catálogo, condições e disponibilidade de produtos Exo Hair para reposição sem depender de cada pedido solto pelo WhatsApp ou visita do distribuidor',
   'telefone_publico':'Não localizado publicamente com segurança; telefone do formulário/HubSpot é celular válido: +55 21 98212-4947',
   'whatsapp_publico':'Não localizado publicamente com segurança; usar telefone celular válido informado no formulário/HubSpot',
 },
 'diego@scbeauty.com.br': {
   'slug':'sc-beauty-distribuidora-sc', 'mql': True,
   'empresa_real':'SC Beauty Comércio de Cosméticos Ltda — distribuidora de cosméticos profissionais em Santa Catarina',
   'dominio_site':'scbeauty.com.br; página pública da distribuidora e portal de pedidos scbeauty.meuspedidos.com.br confirmam operação com catálogo/pedido digital para clientes B2B.',
   'redes':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo: site SC Beauty, portal/app de pedidos meuspedidos, página Nupedido listando SC Beauty como Distribuidora de Cosméticos em Florianópolis e Facebook SC Beauty oficial. O formulário informa salões de beleza e lojas, Bling, venda por vendedor na rua, loja virtual ativa e faturamento de R$1 a R$5 milhões.',
   'segmento':'Distribuidora atacadista de cosméticos profissionais para salões, esteticistas, terapeutas capilares e lojas em Santa Catarina, com marcas profissionais e recompra recorrente.',
   'motivo':'Pesquisa pública real confirmou ICP T1: distribuidora oficial de marcas profissionais de cosméticos, com portal/app de pedidos B2B, catálogo, promoções e venda recorrente para salões e profissionais. O formulário reforça fit com Bling, loja virtual, faturamento de R$1 a R$5 milhões e dor de escalar sem contratar mais gente. Atende ao crivo acirrado por distribuição B2B de produto físico e recompra de estoque.',
   'insight':'salões e lojas recomprarem produtos profissionais por catálogo digital com preço e promoção atualizados, reduzindo dependência do vendedor na rua para cada reposição',
   'telefone_publico':'Não localizado publicamente com segurança; telefone do formulário/HubSpot é celular válido: +55 48 98441-3003',
   'whatsapp_publico':'Não localizado publicamente com segurança; usar telefone celular válido informado no formulário/HubSpot',
 },
 'iris@iriscosmeticos.com.br': {
   'slug':'iris-cosmeticos-iris-alves-frazao', 'mql': True,
   'empresa_real':'Iris Cosméticos — marca/operação de cosméticos naturais com domínio próprio iriscosmeticos.com.br, atendimento por WhatsApp e presença pública vinculada a Iris Alves Frazão',
   'dominio_site':'iriscosmeticos.com.br — site oficial em manutenção programada, mas com botão de WhatsApp direto para +55 91 98400-0765; domínio corporativo confere com o e-mail do lead',
   'redes':'Pesquisa pública real neste ciclo: busca web localizou o site oficial iriscosmeticos.com.br, Instagram @use_iris (“Íris | Shampoo e Condicionador em Barra”) e resultado público citando Iris Alves Frazão e trabalho com revendedoras na região; Facebook público “Distribuidora Iris” também aparece associado a Iris Alves Frazão',
   'segmento':'Distribuidora/marca de cosméticos naturais e produtos de higiene/beleza com venda por WhatsApp e canal declarado de revendedoras, gerando recompra de estoque por revenda e potencial de catálogo B2B simples',
   'motivo':'Pesquisa pública real confirmou empresa real com domínio próprio e WhatsApp oficial, além de evidência externa de atuação com revendedoras. O formulário reforça o fit: área “revendedoras”, faturamento de R$500 mil a R$1 milhão, 2 a 5 vendedores, dor de pedidos desorganizados por WhatsApp/telefone/planilha e cliente que compraria sozinho 24h. Mesmo com operação pequena e ERP “Outro”, passa no crivo acirrado por venda recorrente para revendedoras e necessidade de digitalizar catálogo, condição e pedido de reposição.',
   'insight':'revendedoras consultarem catálogo, preços e reposição de cosméticos sozinhas, diminuindo pedidos soltos no WhatsApp e acelerando recompra de estoque',
   'telefone_publico':'WhatsApp público oficial no site: +55 91 98400-0765; coincide com o telefone calculado completo do HubSpot/formulário',
   'whatsapp_publico':'WhatsApp público oficial https://api.whatsapp.com/send?phone=5591984000765 encontrado no site iriscosmeticos.com.br',
 },
 'waals@waals.com.br': {
   'slug':'waals-marcel-cavalcante', 'mql': True,
   'empresa_real':'Waals (Delicia Fefe Comércio de Alimentos EIRELI) — marca/e-commerce de acessórios para café e panificação artesanal, com canal declarado de atacado',
   'dominio_site':'waals.com.br — site oficial com loja virtual, carrinho, rastreio, conta, categorias de produtos e banner principal “ATACADO NO WHATSAPP” com “Mais que 50% de desconto sobre o preço do varejo”',
   'redes':'Site oficial waals.com.br, Instagram @waals_co, WhatsApp público +55 11 98987-7002 e revendedores que listam a marca; validação manual Rafael 26/06/2026 pelo banner de atacado no próprio site',
   'segmento':'Marca/e-commerce de acessórios e equipamentos para café e panificação artesanal, com catálogo de V60, decanters, panificação e outros itens; venda B2C no site e atacado explicitamente via WhatsApp para lojistas/revendas/cafeterias',
   'motivo':'Correção Rafael 26/06/2026: não reprovar como D2C quando o próprio site declara ATACADO NO WHATSAPP e desconto superior a 50% sobre varejo. Há loja virtual, categorias de catálogo, WhatsApp de atacado e evidência de revendedores. Mesmo com operação pequena, o sinal de canal atacadista/revenda é explícito e deve qualificar como MQL para diagnóstico de digitalização B2B.',
   'insight':'lojistas, cafeterias e revendedores acessarem catálogo e condições de atacado de acessórios de café/panificação por um portal próprio, reduzindo pedidos soltos no WhatsApp e separando varejo de atacado',
   'telefone_publico':'WhatsApp público/site: +55 11 98987-7002; telefone do formulário/HubSpot: +55 11 95466-5175',
   'whatsapp_publico':'WhatsApp público oficial +55 11 98987-7002 no site; para lead, usar telefone do formulário/HubSpot quando válido: +55 11 95466-5175',
 },
 'contato@lojabombasking.com.br': {
   'slug':'bombas-king-adriano', 'mql': True,
   'empresa_real':'Bombas King — indústria brasileira de bombas hidráulicas fundada em 1961 no Ceará, com fábrica/escritório central, e-commerce e linha ampla de bombas centrífugas, submersas, periféricas, piscina, incêndio e irrigação',
   'dominio_site':'lojabombasking.com.br é o e-commerce oficial e bombasking.com.br é o site institucional/fábrica; fontes públicas indicam mais de 90 tipos e cerca de 1800 versões de bombas, venda online e atendimento comercial por WhatsApp',
   'redes':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo: sites oficiais lojabombasking.com.br e bombasking.com.br, Instagram @bombasking, Facebook @bombaskingce, YouTube @BombasKing e LinkedIn Bombasking',
   'segmento':'Indústria/fabricante de bombas hidráulicas com catálogo amplo para irrigação, uso doméstico/industrial, combate a incêndio e home center; venda B2B por representantes, revendas autorizadas, lojas de irrigação, indústrias e home centers, com reposição e abastecimento de estoque técnico',
   'motivo':'Pesquisa pública real confirmou ICP T1: indústria/fabricante estruturada, linha ampla de produtos físicos e canal B2B declarado no formulário para lojas de irrigação, indústrias e home centers. O formulário reforça venda por representantes e venda interna, loja virtual ativa, 51 a 150 pessoas e faturamento de R$1 a R$5 milhões. Pelo crivo acirrado, qualifica por fabricante com revendas/lojistas/clientes recorrentes e potencial de digitalizar catálogo, preço, disponibilidade e pedido recorrente.',
   'insight':'lojas de irrigação, home centers e clientes industriais consultarem catálogo, preço e disponibilidade de bombas para reposição sem depender de cada cotação manual com representante',
   'telefone_publico':'WhatsApp/e-commerce público e telefone do formulário: +55 85 98139-6557; fábrica/escritório central também divulga +55 85 3285-0550 e comercial +55 85 98159-9527',
   'whatsapp_publico':'WhatsApp público oficial +55 85 98139-6557 localizado nos sites oficiais e coincidente com o telefone do formulário/HubSpot',
 },
 'jerson@busca.legal': {
   'slug':'busca-legal-jerson-prochnow', 'mql': False,
   'empresa_real':'Busca.Legal — LegalTech/TaxTech brasileira criada por ex-sócios da FISCOSOFT e SYSTAX, com soluções de inteligência artificial para as áreas tributária, fiscal, contábil e jurídica',
   'dominio_site':'busca.legal — site oficial com soluções Busca.Legal T1/T2/ST, jurisprudência, boletim diário e workflow tributário; clientes citados incluem Ambev, Mercado Livre, IBM, Ipiranga e Bayer',
   'redes':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo: site oficial busca.legal, LinkedIn público de Jerson Prochnow e ficha pública TOTVS do Classificador Fiscal by Busca.Legal',
   'segmento':'SaaS/LegalTech/TaxTech de inteligência tributária e workflow fiscal; venda de software/assinatura, não operação de estoque físico, atacado ou distribuição de mercadorias',
   'motivo':'Pesquisa pública real confirmou empresa estruturada, mas o modelo é tecnologia/SaaS para consulta tributária, jurisprudência, boletim e workflow fiscal. Não há evidência de indústria, distribuidor, importador ou atacado com catálogo de produtos físicos, reposição de estoque e pedidos recorrentes para revendas/lojistas/clientes B2B. Os sinais do formulário (representantes, 27 UFs, +151 pessoas e alto faturamento) refletem abrangência comercial de software, não ICP T1 de estoque. Pelo crivo MQL acirrado/fail-closed, fica não qualificado.',
   'insight':'',
   'telefone_publico':'WhatsApp/telefone público oficial no site: +55 11 4114-1115; telefone do formulário: +55 11 99618-9001',
   'whatsapp_publico':'WhatsApp público oficial +55 11 4114-1115, não usado porque o lead foi reprovado no crivo MQL acirrado',
 },
 'hasama@tuzzon.com.br': {
   'slug':'tuzzon-confeccoes-hasama-teixeira', 'mql': True,
   'empresa_real':'Tuzzon Confecções / Fortiori Camisetas — indústria têxtil/confecção de Caetité-BA, com fábrica de tecidos esportivos, produção de roupas, estamparia e atuação em private label',
   'dominio_site':'tuzzon.com.br — site oficial descreve fábrica de tecidos esportivos, confecção interna robusta, 30 anos de experiência, estamparia, sublimação e bordado; perfil B2B público ForneceB2B lista Tuzzon/Fortiori como fabricante, atacado/distribuição, private label e fornecedor para revenda online',
   'redes':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo: site oficial Tuzzon, ForneceB2B, LinkedIn Fortiori Camisetas, Econodata/QuemFornece/eGuias e cadastros públicos; Hasama Teixeira aparece ligada à administração/sociedade',
   'segmento':'Indústria têxtil/confecção com atacado, private label, terceirização para marcas próprias e venda de vestuário para revendas/lojistas/B2B; produto físico com produção e reposição recorrente',
   'motivo':'Pesquisa pública real confirmou ICP T1: fabricante/indústria têxtil com estrutura fabril, malharia/confecção/estamparia, produção de roupas e presença em canal atacadista/private label para marcas, revendas e clientes B2B. Embora o lead tenha vindo por reunião e sem formulário/telefone, a operação pública sustenta venda recorrente de produto físico/catálogo/estoque para terceiros. Pelo crivo MQL acirrado, qualifica.',
   'insight':'revendas e marcas acompanharem catálogo, pedidos e reposição de camisetas e peças produzidas pela fábrica sem depender de cada solicitação manual ao comercial',
   'telefone_publico':'Telefones públicos encontrados em fontes de empresa: +55 77 3454-1004 e +55 77 3454-4105; não encontrei WhatsApp corporativo público seguro',
   'whatsapp_publico':'Não localizado com segurança; telefones públicos são fixos, então o diagnóstico ao lead fica bloqueado se não houver WhatsApp válido no HubSpot',
 },
 'comercial@lunarrepresentacao.com.br': {
   'slug':'lunar-equipamentos-andre-sanches', 'mql': True,
   'empresa_real':'Lunar Equipamentos Ltda — comércio atacadista de roupas e acessórios para uso profissional e segurança do trabalho, em São Paulo/SP, ligada publicamente a André Luis Sanches',
   'dominio_site':'lunarrepresentacao.com.br não apresentou site institucional válido na consulta; pesquisa pública por CNPJ/razão social confirmou Lunar Equipamentos Ltda, CNPJ 40.940.004/0001-74, CNAE principal 4642-7/02 comércio atacadista de roupas e acessórios para uso profissional e de segurança do trabalho',
   'redes':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo: Econodata, Serasa Experian e cnpj.biz; site lunarrepresentacao.com.br não mostrou página comercial confiável',
   'segmento':'Atacado/distribuição de EPIs, uniformes e acessórios de segurança do trabalho para distribuidoras, revendas, construtoras, empreiteiras, concessionárias, pavimentação e condomínios; produto físico de recompra recorrente',
   'motivo':'Pesquisa pública real confirmou ICP T1: CNAE principal de comércio atacadista de roupas/acessórios profissionais e segurança do trabalho, e o formulário declara venda para distribuidoras, revendas, construtoras, empreiteiras e concessionárias. EPIs e uniformes têm recompra recorrente e potencial claro para catálogo, preço, pedido e reativação de carteira. ERP Bling e venda por WhatsApp aceleram, mas a qualificação se sustenta pelo atacado B2B recorrente.',
   'insight':'clientes e revendas recomprarem EPIs e uniformes no momento certo, reativando carteira parada com catálogo e disponibilidade sem depender de cada pedido solto pelo WhatsApp',
   'telefone_publico':'Fontes públicas gratuitas mostram telefone móvel parcialmente mascarado (11) 96423-****; telefone completo do formulário/HubSpot: +55 11 98704-5720',
   'whatsapp_publico':'Não localizado publicamente com segurança; telefone do formulário/HubSpot é celular válido e será usado para envio',
 },
 'michele@franquiasorpack.com': {
   'slug':'sorpack-embalagens-michele-reis', 'mql': True,
   'empresa_real':'Sorpack Smart CGMS 02 Comércio Atacadista de Embalagens Ltda — unidade franqueada Smart da rede Sorpack Embalagens, em Campo Grande/MS; Michele dos Reis aparece em cadastro público como sócia-administradora da unidade',
   'dominio_site':'franquiasorpack.com é o portal de franqueamento da rede; sorpack.com.br é o site institucional/comercial da Sorpack Embalagens, com página da loja Campo Grande',
   'redes':'Pesquisa pública via Claude Code/WebSearch/WebFetch: site Sorpack, página de franquia Sorpack, loja Sorpack Campo Grande, Instagram @sorpackembalagens e @sorpackembalagenscg, Facebook Sorpack Embalagens, LinkedIn Sorpack Embalagens CG e cadastros públicos ProcuroAcho/Casa dos Dados/cnpj.biz',
   'segmento':'Comércio atacadista/distribuidor de embalagens, descartáveis, higiene/limpeza e itens para preparo de alimentos; modelo Smart com venda atacadista para PJ como restaurantes, padarias, hotéis, transportadoras e indústrias de alimentos, com reposição recorrente de estoque',
   'motivo':'Pesquisa pública real confirmou ICP T1: atacado/distribuição de embalagens para empresas que recompram insumos de consumo recorrente para abastecer operação/estoque. O formulário reforça fit com faturamento de R$1 a R$5 milhões, 11 a 25 pessoas, venda por telelevendas e representantes e ausência de loja virtual. ERP “Outro” não é decisivo; a qualificação se sustenta pelo canal B2B recorrente e catálogo de embalagens.',
   'insight':'clientes como restaurantes, padarias e hotéis recomprarem embalagens antes de ficar sem estoque, com menos pedido solto por telefone e mais previsibilidade para o time comercial',
   'telefone_publico':'Telefone público da unidade Campo Grande em cadastro CNPJ/ProcuroAcho: +55 67 3306-9697; telefone do formulário/HubSpot: +55 65 98475-7060',
   'whatsapp_publico':'Não localizei WhatsApp corporativo direto da unidade com segurança; telefone do formulário é celular válido e será usado para envio',
 },
 'fabio@solnascent.com.br': {
   'slug':'sol-nascente-fabio-kuschel', 'mql': True,
   'empresa_real':'Sol Nascente Distribuidora de Calçados, de Criciúma/SC; domínio solnascent.com.br e Fabio Kuschel aparecem publicamente ligados à direção comercial da operação',
   'dominio_site':'solnascent.com.br — site oficial com portal de vendas, representantes e marcas de calçados como Kesttou, GASF e GASF Kids',
   'redes':'Fontes pesquisadas neste ciclo: site oficial solnascent.com.br, LinkedIn público de Fabio Kuschel e ZoomInfo público indicando Fabio Kuschel ligado à Sol Nascente',
   'segmento':'Distribuição/atacado de calçados, pantufas e galochas para revendas e lojistas, com catálogo, representantes e pedidos recorrentes de reposição de estoque',
   'motivo':'Pesquisa pública real confirmou ICP T1: distribuidora/atacado de calçados com portal de vendas, rede de representantes, marcas próprias e venda para revendas/lojistas que recompram estoque. O formulário informa ERP Olist/Tiny, venda por WhatsApp, faturamento de R$500 mil a R$1 milhão e telefone celular válido; o fit se sustenta pelo canal atacadista e pela recorrência de catálogo, preço e reposição para lojistas.',
   'insight':'lojistas consultarem catálogo, preço e disponibilidade de pantufas e galochas para repor estoque sem depender de pedidos soltos pelo WhatsApp',
   'telefone_publico':'Telefone público comercial encontrado no site: +55 48 3478-3553; telefone do formulário/HubSpot: +55 48 99148-7635',
   'whatsapp_publico':'Não encontrei WhatsApp público corporativo no site; telefone do formulário é celular válido e será usado para envio',
 },
 'carlosquites@liapp.com.br': {
   'slug':'li-plataforma-logistica-integrada-carlos', 'mql': False,
   'empresa_real':'LI Plataforma de Logística Integrada Ltda, de Curitiba/PR — app liapp.com.br que conecta clientes a profissionais para entregas, fretes e mudanças',
   'dominio_site':'liapp.com.br — site/app público de logística integrada; Google Play mostra aplicativo de logística/entregas',
   'redes':'Fontes pesquisadas neste ciclo: site liapp.com.br e página do aplicativo LI na Google Play',
   'segmento':'Logística sob demanda, marketplace/app de serviços de entrega, frete e mudança; plataforma de serviço, não operação de estoque físico',
   'motivo':'Pesquisa pública confirmou empresa real, mas o modelo é app/serviço de logística conectando clientes a profissionais para entregas, fretes e mudanças. Não há evidência de indústria, distribuidor, importador ou atacado vendendo produtos físicos para revendas/lojistas com catálogo, preço e pedidos recorrentes de abastecimento de estoque. Pelo crivo acirrado/fail-closed, serviço/logística/app fica não qualificado.',
   'insight':'',
   'telefone_publico':'Não encontrei telefone/WhatsApp público seguro em fontes abertas; telefone do formulário/HubSpot: +55 41 98834-9867',
   'whatsapp_publico':'Não localizado com segurança; não usado porque o lead foi reprovado no crivo MQL acirrado',
 },
 'julio@rainoah.com.br': {
   'slug':'rainoah-julio-barbosa', 'mql': True,
   'empresa_real':'Rainoah / R.B.S. Comércio Ltda — indústria brasileira de produtos de saúde e bem-estar, com mais de 30 anos de mercado, sede em Cambé-PR e operação pública de fábrica própria',
   'dominio_site':'rainoah.com.br; site oficial confirma fabricação própria de produtos de bem-estar, loja/catálogo, rede de distribuidores autônomos em todos os estados e alguns países da América do Sul, programas de afiliado/embaixador e contato corporativo por WhatsApp',
   'redes':'Fontes pesquisadas neste ciclo: site oficial rainoah.com.br, página Contato/Quem Somos, loja.rainoah.com.br/contato, página Afiliados, página Embaixador, Instagram @rainoahbemestar e LinkedIn público de Julio Cesar Barbosa ligado à Rainoah',
   'segmento':'Indústria/fabricante de produtos de saúde e bem-estar, massageadores, palmilhas, mantas/colchonetes e eletroestimuladores, com rede nacional de distribuidores, revendedores, lojistas, afiliados e canais de recompra de produto físico',
   'motivo':'Pesquisa pública real confirmou ICP T1: fabricante com fábrica própria, linha ampla de produtos físicos, rede de distribuidores autônomos em todos os estados e venda para revendedores/lojistas/afiliados que precisam recomprar e abastecer estoque. O contato Julio usa e-mail corporativo e aparece publicamente ligado à gestão comercial da Rainoah. Mesmo sem formulário de diagnóstico e sem ERP informado no HubSpot, o domínio e a operação pública sustentam a qualificação pelo canal B2B recorrente e pelo potencial de digitalizar catálogo, preço, disponibilidade e reposição por canal.',
   'insight':'distribuidores e lojistas consultarem catálogo, preço e disponibilidade para recomprar produtos de bem-estar sem depender de planilhas ou pedidos soltos no atendimento',
   'telefone_publico':'WhatsApp corporativo oficial divulgado na página de contato do site: +55 43 3371-6900; e-mail público sac@rainoah.com.br; loja oficial também divulga central (43) 3371-6900',
   'whatsapp_publico':'WhatsApp corporativo oficial +55 43 3371-6900 localizado em https://rainoah.com.br/contato/ com link api.whatsapp.com/send/?phone=554333716900',
 },
 'direroria@hlcortetransportes.com.br': {
   'slug':'helena-cortez-hl-cortez-transportes', 'mql': False,
   'empresa_real':'HL Cortez Transportes / Helena Cortez Transportes, Armazenagens e Logísticas Ltda — transportadora e operador logístico com unidades/atuação em MT, SP, MS, GO, PA e DF',
   'dominio_site':'hlcorteztransportes.com.br — site oficial confirma transporte rodoviário de cargas, armazenagem, frota própria, cross docking, logística reversa, carga fracionada/lotação e soluções para o agro; domínio do e-mail confere com a empresa',
   'redes':'Fontes públicas pesquisadas neste ciclo: site oficial HL Cortez Transportes, Instagram/Facebook @hlcorteztransportes, LinkedIn HL Cortez Transportes, Guia do TRC/CNPJ e Transvias',
   'segmento':'Transporte rodoviário de cargas, armazenagem e logística para empresas; operação B2B de serviço logístico, não venda de produtos físicos/catálogo para revendas ou reposição de estoque',
   'motivo':'Pesquisa pública confirmou empresa real e estruturada de transporte/logística, com 15+ anos, frota própria, armazenagem e serviços nacionais. Porém o crivo MQL acirrado exige indústria, distribuidor, importador ou atacado com catálogo/produtos e pedidos recorrentes de abastecimento para revendas, lojistas ou clientes de estoque. A HL Cortez presta serviço logístico e transporte por cotação/projeto, sem evidência de venda recorrente de produto físico/catálogo B2B para digitalização de tabela, preço e pedido. ERP Outro e venda por WhatsApp não substituem ICP. Pelo fail-closed, fica não qualificado.',
   'insight':'',
   'telefone_publico':'Telefone do formulário/HubSpot: +55 65 99974-359; site/Guia do TRC também indicam telefone fixo (65) 3684-2786 e e-mail diretoriacomercial@transcortez.com',
   'whatsapp_publico':'Não usado neste ciclo; contato ao lead bloqueado por não-MQL',
 },
 'adm-financeiro@globalcut.com.br': {
   'slug':'marcio-torloni-globalcut', 'mql': False,
   'empresa_real':'GLOBALTEC SISTEMAS E MAQUINAS LTDA (marca GlobalCut), CNPJ 01.195.795/0001-01, Franca-SP, ativa desde 1996',
   'dominio_site':'globalcut.com.br; site oficial confirma fabricante/distribuidora de máquinas e mesas de corte industriais',
   'redes':'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: site oficial globalcut.com.br, Instagram @globalcut.machines, YouTube GlobalCut e base pública Econodata/CNPJ; Marcio Torloni aparece publicamente ligado à GLOBALTEC/INTERGROUP',
   'segmento':'Fabricante/distribuidor de máquinas e mesas de corte industriais para calçados, têxtil, móveis, comunicação visual e embalagens; venda B2B por orçamento de bens de capital de alto ticket',
   'motivo':'Pesquisa pública real confirmou empresa legítima e B2B, mas o modelo é venda pontual de máquinas industriais de corte por cotação. Não há evidência de catálogo de alto giro, estoque/preço/pedido recorrente para revendas, lojistas ou abastecimento recorrente. Pelo crivo MQL acirrado/fail-closed, indústria de bens de capital sob orçamento não entra como ICP T1.',
   'insight':'',
   'telefone_publico':'Telefone público no site: +55 16 3403-3496; WhatsApps públicos: +55 16 99413-9010 e +55 16 98210-0654',
   'whatsapp_publico':'WhatsApp público +55 16 98210-0654 (mesmo telefone do HubSpot) e +55 16 99413-9010; não usado porque o lead foi reprovado no crivo MQL acirrado',
 },
 'alberto@cerratense.rep.br': {
   'slug':'alberto-cerratense-abracerva', 'mql': False,
   'empresa_real':'Alberto Nascimento — diretor de Relações Institucionais da Abracerva e sommelier de cervejas ligado à Cervejaria Goyaz / Cerveja Colombina; o domínio cerratense.rep.br indica possível representação comercial, mas o site não estava ativo e a operação de estoque/distribuição não foi comprovada',
   'dominio_site':'cerratense.rep.br — domínio do e-mail, indisponível/inativo na consulta; Abracerva é associação setorial, não operação comercial do lead',
   'redes':'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: Abracerva, perfil público de Alberto Nascimento como sommelier na Cervejaria Goyaz/Colombina, matéria sobre profissionalização da cerveja artesanal e Congresso Cerveja Brasil 2026',
   'segmento':'Cerveja artesanal, associação setorial, relações institucionais, sommelier/educação e possível representação comercial não comprovada',
   'motivo':'Pesquisa pública real confirmou vínculo com associação, eventos, educação/sommelier e relações institucionais. O domínio .rep.br sugere representação comercial, mas não comprovou distribuidora/atacado com estoque, catálogo e abastecimento recorrente para revendas/lojistas. Pelo crivo acirrado/fail-closed, associação/serviço/evento/representante sem operação de estoque clara não qualifica.',
   'insight':'',
   'telefone_publico':'Telefone do formulário/HubSpot: +55 62 98304-8535; não usado porque o lead foi reprovado no crivo MQL acirrado',
   'whatsapp_publico':'Não usado neste ciclo; contato ao lead bloqueado por não-MQL',
 },
 'li.dias@gldmaq.com.br': {
   'slug':'gld-acessorios-brutos', 'mql': True,
   'empresa_real':'GLD Acessórios e Brutos — ECD Comércio de Acessórios, Bijuterias e Folheados Ltda, Limeira/SP, ligada a Elisandra Cristina Dias; operação pública de atacado e fabricação própria desde 2013',
   'dominio_site':'gldacessorios.com.br é a vitrine pública; gldmaq.com.br, domínio do e-mail, responde restrito/401. A operação comercial visível roda em gldacessorios.com.br e Instagram @gldacessorios',
   'redes':'Fontes pesquisadas via Claude Code/WebSearch/WebFetch: site oficial gldacessorios.com.br, Instagram @gldacessorios com bio “Atacado de acessórios & brutos / fabricação própria desde 2013”, Facebook GLD Acessórios | Limeira SP e Econodata/CNPJ',
   'segmento':'Indústria/atacado de brutos, componentes, acessórios, bijuterias e folheados para montagem de semijoias, com fabricação própria em Limeira e catálogo amplo para lojistas, fabricantes e revendedores recomprarem estoque',
   'motivo':'Pesquisa pública real confirmou ICP T1: a própria empresa se declara atacado de acessórios e brutos com fabricação própria, catálogo amplo de milhares de itens e venda para quem monta, folheia e revende semijoias. O formulário reforça a dor: vendedor ainda digita pedido manual porque a loja online é de varejo. Bling, faturamento de R$1 a R$5 milhões, 11 a 25 pessoas e loja virtual aceleram, mas a qualificação se sustenta pelo canal atacadista e recompra recorrente de estoque.',
   'insight':'lojistas e fabricantes de semijoias recomprarem brutos e acessórios por preço de atacado, com repetição de compra e catálogo B2B, sem o vendedor redigitar cada pedido manualmente',
   'telefone_publico':'Telefone do formulário/HubSpot: +55 19 98323-1001; WhatsApp público corporativo divulgado no site: +55 19 98973-5455',
   'whatsapp_publico':'WhatsApp público corporativo +55 19 98973-5455 localizado no site oficial gldacessorios.com.br; telefone do formulário +55 19 98323-1001 também é celular válido',
 },
 'hasama@fortiori.com.br': {
   'slug':'tuzzon-confeccoes-fortiori', 'mql': False,
   'empresa_real':'Tuzzon Confecções / Fortiori Confecções — indústria têxtil verticalizada em Caetité/BA, ligada à família Teixeira e à marca Fortiori Camisetas/Fortiori Clothing',
   'dominio_site':'fortiori.com.br é o domínio ativo da operação; tuzzon.com.br aparece como site antigo/cadastro público. O email hasama@fortiori.com.br confere com a empresa',
   'redes':'Instagram @fortiori.camisetas, Facebook Fortiori Camisetas/Fortiori Clothing, LinkedIn Fortiori e presença pública em B2Brazil/cadastros CNPJ',
   'segmento':'Indústria/confecção têxtil de grande estrutura, com malharia, tinturaria, corte, estampa e costura. Produz camisetas, abadás, uniformes, promocionais e moda; há indício de marca própria com pontos de revenda, mas o núcleo público parece encomenda/personalização sob demanda',
   'motivo':'Pesquisa pública real do ciclo confirmou empresa grande e industrial, porém o crivo MQL acirrado exige evidência clara de venda recorrente de estoque para revendas/lojistas. No material público, o motor principal da Fortiori parece ser peça personalizada sob encomenda para eventos, uniformes e promocionais; o canal de coleção própria/revenda existe como sinal secundário, mas não foi conclusivo como operação principal. Pelo fail-closed, fica não qualificado até confirmar que Hasama cuida do atacado/linha própria para lojistas com reposição recorrente.',
   'insight':'',
   'telefone_publico':'Telefone do formulário/HubSpot: +55 77 99624-175; telefone válido, mas não utilizado porque o lead foi reprovado no crivo MQL acirrado',
   'whatsapp_publico':'Não usado neste ciclo; contato ao lead bloqueado por não-MQL',
 },
 'douglasbarreto1998@gmail.com': {
   'slug':'liso-confeccoes-douglas', 'mql': False,
   'empresa_real':'Liso Confecções Ltda — empresa recém-aberta em Apucarana/PR, CNPJ 61.259.962/0001-54, fundada em 11/06/2025',
   'dominio_site':'Sem domínio corporativo informado; e-mail pessoal Gmail. O campo empresa veio como CNPJ e a pesquisa pública identificou Liso Confecções Ltda em bases cadastrais',
   'redes':'Não foram localizados site oficial, loja, Instagram/Facebook ou presença pública conclusiva demonstrando canal B2B de revenda/atacado',
   'segmento':'Confecção/vestuário presumida pelo CNAE/nome público, mas sem formulário de diagnóstico, sem telefone e sem evidência de indústria/distribuidor/atacado com pedidos recorrentes para revendas/lojistas',
   'motivo':'Pesquisa pública encontrou apenas cadastro CNPJ da Liso Confecções, empresa muito recente, sem site/domínio corporativo, sem telefone no contato, sem respostas de diagnóstico e sem prova de canal B2B recorrente. Pelo crivo acirrado/fail-closed, lead sem vínculo operacional e sem WhatsApp válido não qualifica.',
   'insight':'',
   'telefone_publico':'Não localizado telefone/WhatsApp público seguro vinculado à empresa nas buscas deste ciclo; HubSpot veio sem telefone',
   'whatsapp_publico':'Não localizado',
 },
 'atila@safeparksinalizacao.com': {
   'slug':'safe-park-sinalizacao', 'mql': True,
   'empresa_real':'Safe Park Sinalização — operação estruturada de sinalização viária, garagem, estacionamento e segurança em Brasília/DF, ativa desde 2013',
   'dominio_site':'safeparksinalizacao.com; provável variação brasileira safeparksinalizacao.com.br deve ser considerada quando o lead preencher domínio incompleto; domínio do e-mail confere com a marca',
   'redes':'Instagram @safeparksinalizacao, Facebook Safe Park Sinalização, LinkedIn Safe Park Sinalização e YouTube oficial localizados na pesquisa pública',
   'segmento':'Fornecedor B2B estruturado de sinalização viária/de trânsito e segurança para condomínios, shoppings, supermercados, escolas, garagens, estacionamentos e operações com compra recorrente de placas, cones, barreiras, balizadores e itens de acessibilidade',
   'motivo':'Correção Rafael: não reprovar por leitura estreita nem por domínio possivelmente digitado sem .com.br. O formulário mostra Omie, loja virtual, faturamento de R$10 a R$50 milhões/ano, 21 a 100 pessoas e dor explícita: hoje vende boleto parcelado só via WhatsApp, gerando gargalo operacional. Empresa grande/estruturada, B2B, com catálogo amplo e potencial claro de digitalização de pedido, crédito/condição, orçamento e recompra. Qualifica como MQL.',
   'insight':'clientes recorrentes consultarem catálogo de sinalização, placas, cones e equipamentos, com condição de crédito/boleto parcelado e pedido digital sem travar tudo no WhatsApp',
   'telefone_publico':'Site oficial divulga (61) 3297-6853 e (61) 98290-2525; telefone do formulário/lead: +55 61 99809-9258',
   'whatsapp_publico':'WhatsApp ativo no site de contato; telefone do formulário +55 61 99809-9258 deve ser usado/validado para envio',
 },
 'contato@mcbkitalimentos.com.br': {
   'slug':'mcb-kit-alimentos', 'mql': True,
   'empresa_real':'MCB Kit Alimentos — fornecedora/montadora de cestas básicas e kits corporativos de alimentos em Curitiba/PR',
   'dominio_site':'mcbkitalimentos.com.br; loja online paralela mcbkitloja.com.br; domínio corporativo do e-mail confere com a empresa',
   'redes':'Instagram @mcbkitalimentos e Facebook MCB Kit Alimentos localizados na pesquisa pública',
   'segmento':'Fornecedor B2B estruturado de cestas básicas, kits alimentares, kits corporativos e programas mensais recorrentes para empresas, RH, campanhas, benefícios e ações corporativas',
   'motivo':'Correção Rafael: não reprovar por não ser revenda/atacado clássico. O site confirma soluções alimentares corporativas, cestas básicas corporativas, kits personalizados, logística centralizada, frota própria, programas mensais recorrentes, atendimento B2B especializado e WhatsApp público. Formulário tem ERP Omie, faturamento R$1 a R$5 milhões, venda por Site/WhatsApp e domínio corporativo. Empresas que vendem explicitamente para empresas/restaurantes/condomínios/benefícios corporativos também são bons MQLs quando há recorrência, orçamento e operação estruturada.',
   'insight':'empresas clientes montarem, orçarem e recomprarem cestas e kits corporativos recorrentes em um portal B2B, com condições, quantidades e logística sem depender de cada orçamento manual no WhatsApp',
   'telefone_publico':'WhatsApp público no site/Google/Instagram: (41) 99754-0587; telefone do formulário veio (41) 99693-4229',
   'whatsapp_publico':'WhatsApp público: https://wa.me/5541997540587 e também botão wa.me/message no site; usar número público se HubSpot não trouxer telefone válido',
 },
 'mmoraes@pattaro.com.br': {
   'slug':'pattaro-comercio-servicos', 'mql': True,
   'empresa_real':'Pattaro Comércio e Serviços Ltda — distribuidora/representante B2B de equipamentos, insumos e consumíveis industriais para circuitos impressos, cartões plásticos, corte laser/plasma, soldagem, automação e tratamento de superfícies, sediada em São Caetano do Sul/SP',
   'dominio_site':'pattaro.com.br; site oficial com páginas de produtos, linha de produtos e contato; domínio corporativo do e-mail mmoraes@pattaro.com.br confere com cadastro público CNPJ 01.862.837/0001-02',
   'redes':'Fontes públicas pesquisadas via Claude Code/WebSearch/WebFetch: site oficial pattaro.com.br, página Linha de Produtos Pattaro, página Contato Pattaro, LinkedIn Pattaro Comercio e Servicos, Econodata/CNPJ e Portal da Transparência; não foram localizadas redes sociais fortes no site',
   'segmento':'Distribuição/representação B2B de máquinas, equipamentos, instrumentos, matéria-prima, materiais de consumo, peças de reposição e consumíveis industriais para clientes recorrentes da indústria',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch confirmou empresa real, domínio oficial e operação de distribuição/representação B2B com catálogo físico. A Pattaro vende não só máquinas de alto ticket, mas também consumíveis de plasma/laser/soldagem, materiais de consumo e peças de reposição, o que cria recompra recorrente e aderência ao crivo T1. O formulário reforça fit: ERP Omie, faturamento de R$5 a R$10 milhões/ano e venda por telefone/e-mail sem loja virtual. Mesmo com equipe enxuta, o conjunto passa no crivo acirrado por distribuidor B2B industrial com estoque/catálogo e pedidos recorrentes.',
   'insight':'clientes industriais recomprarem consumíveis, peças e materiais de corte/soldagem por um catálogo próprio, reduzindo pedidos soltos por telefone e e-mail',
   'telefone_publico':'Telefone público do site/CNPJ: +55 11 5182-9229; WhatsApp público encontrado na página de contato: +55 11 93283-6473',
   'whatsapp_publico':'WhatsApp público corporativo +55 11 93283-6473; telefone do HubSpot do contato +55 11 98149-6377 também é celular válido',
 },
 'vendas@br1led.com.br': {
   'slug':'br1-led', 'mql': False,
   'empresa_real':'BR1 LED / Br1led — operação pública não confirmada de forma segura pelo domínio do lead; há homônimos e um site BR1 América LED com fabricação/instalação de painéis de LED, mas sem vínculo conclusivo com vendas@br1led.com.br',
   'dominio_site':'br1led.com.br não carregou na pesquisa via Claude Code; busca externa encontrou br1americaleds.com.br como homônimo/possível relacionado, com atuação em fabricação e instalação de painéis de LED por projeto',
   'redes':'Instagram/Facebook de homônimos BR1 LED/BR1 LEDs encontrados, sem vínculo público seguro com o email vendas@br1led.com.br e o telefone 11 99595-3838',
   'segmento':'Iluminação/painéis de LED, aparentemente microempresa de venda direta/projeto sob demanda; sem evidência segura de canal atacadista, revenda ou abastecimento recorrente de estoque',
   'motivo':'Pesquisa pública real via Claude Code/WebSearch/WebFetch e busca externa não confirmou vínculo operacional seguro do e-mail/telefone com empresa estruturada. O formulário reforça baixo fit: ERP Outro, faturamento até R$250 mil/ano, equipe 1 a 10, sem loja virtual e vendas por WhatsApp/boca a boca. Mesmo considerando o homônimo BR1 América LED, a atuação pública é fabricação/instalação de painéis de LED sob projeto para clientes comerciais/corporativos, não distribuição/atacado com pedidos recorrentes de estoque para revendas/lojistas. Pelo crivo MQL acirrado/fail-closed, não há evidência clara de ICP T1.',
   'insight':'',
   'telefone_publico':'Não localizado com vínculo seguro ao email do lead; homônimo BR1 América LED divulga 11 94307-5492, mas não foi usado por não haver vínculo conclusivo',
   'whatsapp_publico':'Não confirmado publicamente para o lead; número do HubSpot 11 99595-3838 válido, mas sem evidência pública',
 },
 'comercial@barulhinhobom.com.br': {
   'slug':'barulhinho-bom', 'mql': True,
   'empresa_real':'Barulhinho Bom | Chips Naturais — indústria de snacks naturais/chips de banana, batata-doce, mandioca/macaxeira e inhame, com fábrica própria em Marechal Deodoro/AL',
   'dominio_site':'barulhinhobom.com.br; site oficial com loja online e página de contato; produtos também encontrados em varejo/supermercados como Palato',
   'redes':'Instagram @barulhinhobomoficial e Facebook oficial; publicações e snippets públicos chamam mercados, empórios, lojas de produtos naturais e revendedores para vender Barulhinho Bom',
   'segmento':'Indústria de alimentos/snacks naturais, com venda D2C e canal B2B para supermercados, empórios, lojas de produtos naturais e revendedores; produto consumível de reposição recorrente',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch confirmou empresa real, fábrica própria e canal de revenda: os snippets públicos dizem “Seja um revendedor” e “Perfeitos para mercados, empórios, lojas de produtos naturais”, além de presença em supermercado. O formulário reforça fit com ERP Bling, faturamento de R$500 mil a R$1 milhão/ano, 11 a 25 pessoas, loja virtual ativa e venda por aplicativos/contato direto. Passa no crivo acirrado por indústria de produto consumível vendendo para revendas/lojistas/clientes recorrentes de estoque.',
   'insight':'mercados, empórios e lojas de produtos naturais recomprarem chips e acompanharem mix/disponibilidade em um canal próprio, sem depender de cada pedido manual pelo WhatsApp',
   'telefone_publico':'WhatsApp/telefone público e telefone do lead: +55 82 99960-5686; fontes: site oficial/página de contato e snippets públicos',
   'whatsapp_publico':'WhatsApp público +55 82 99960-5686',
 },
 'jeanvtr21@ullian.com.br': {
   'slug':'ullian-portas-janelas-jean', 'mql': True,
   'empresa_real':'Ullian Portas e Janelas — indústria/fabricante de portas e janelas em aço e alumínio, ativa desde 1949, dona das marcas Lucasa e Riobras, com presença nas melhores lojas do Brasil',
   'dominio_site':'ullian.com.br; domínio corporativo do e-mail do lead. O campo empresa veio inconsistente como Radio Globo Rio Preto, mas por regra Rafael prevalece o domínio corporativo quando aponta para indústria/distribuidora real e grande',
   'redes':'Site oficial Ullian; Instagram @ullianportasejanelas; LinkedIn Ullian Portas e Janelas. Fontes públicas confirmam fabricante de portas e janelas, marcas Lucasa/Riobras e presença em lojas do Brasil',
   'segmento':'Indústria/fabricante B2B de portas e janelas de aço e alumínio, com portfólio de produtos físicos, canal para lojas/revendas e reposição/cotação recorrente',
   'motivo':'Pesquisa pública e domínio corporativo ullian.com.br confirmam empresa industrial real, tradicional e aderente ao ICP. O campo empresa do HubSpot veio errado/inconsistente, mas o e-mail corporativo deve prevalecer sobre o campo digitado quando o domínio aponta para indústria/distribuidora grande. A operação tem produto físico, catálogo de portas/janelas, marcas próprias e presença em lojas do Brasil, qualificando para diagnóstico de digitalização B2B.',
   'insight':'lojistas, revendas e compradores consultarem catálogo, linha de portas e janelas, disponibilidade e condições de recompra em um canal próprio, sem depender de cada cotação manual pelo WhatsApp',
   'telefone_publico':'Telefone do lead +55 17 99273-8224; contato público Ullian: +55 17 98155-2700 e sac@ullian.com.br',
   'whatsapp_publico':'Contato público Ullian +55 17 98155-2700',
 },
 'marcelo@boutiquedearomas.com': {
   'slug':'boutique-de-aromas-marcelo', 'mql': True,
   'empresa_real':'Boutique de Aromas — marca/indústria de aromas para ambiente, cosméticos e aromaterapia, com fábrica em Panambi/RS, e-commerce próprio e rede de franquias/lojas',
   'dominio_site':'boutiquedearomas.com.br; site oficial com loja online e páginas de lojas/franquia; domínio do e-mail é coerente com a marca',
   'redes':'Instagram @boutiquedearomas, Facebook Boutique de Aromas, TikTok @boutiquedearomasoficial, YouTube oficial e presença em marketplace',
   'segmento':'Indústria/marca de aromas, perfumaria e cosméticos, com produtos consumíveis de recompra e abastecimento recorrente para franquias, lojas e canais digitais',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch confirmou empresa real, fábrica própria, e-commerce e rede de franquias/lojas. A origem é formulário de demonstração no site, o telefone informado bate com a região da sede e há produtos consumíveis com recompra recorrente. O fit vem da indústria/marca que abastece lojas/franquias e canais digitais, com potencial de digitalizar catálogo, disponibilidade, pedidos recorrentes e reposição entre canais; lacunas de ERP/faturamento no formulário não bloqueiam porque a operação pública é clara.',
   'insight':'unificar a reposição de aromas entre fábrica, franquias, lojas e e-commerce, com menos pedido manual e mais visibilidade de estoque por canal',
   'telefone_publico':'Telefone do lead +55 55 99717-5688; canais públicos encontrados na pesquisa: WhatsApp atendimento +55 55 99125-8902 e vendas corporativas +55 55 99175-6723',
   'whatsapp_publico':'WhatsApp atendimento +55 55 99125-8902; vendas corporativas +55 55 99175-6723',
 },
 'glauber@grupolesto.com.br': {
   'slug':'grupo-lesto', 'mql': True,
   'empresa_real':'Lesto Indústria Comércio e Serviços Industriais Ltda (Grupo Lesto) — fabricante de máquinas e equipamentos industriais para moagem, reciclagem de plásticos e usinagem em Franco da Rocha-SP',
   'dominio_site':'grupolesto.com.br — site institucional com portfólio industrial; HubSpot já está como MQL e owner Breno',
   'redes':'Instagram @grupo_lesto e Facebook Lesto Usinagem; presença pública com máquinas, moinhos, granuladores, aglutinadores, picotadores, facas industriais e serviços de usinagem/moagem',
   'segmento':'Indústria/fabricante de máquinas e equipamentos industriais para reciclagem/moagem de plásticos, com potencial de catálogo técnico para máquinas, facas, peças, manutenção, assistência e reposição',
   'motivo':'Correção operacional: HubSpot está MQL e o alerta mostrou conflito com o registro antigo de não-MQL. Embora a venda de máquinas possa ser pontual, o diagnóstico deve explorar a parte que define fit: recorrência em facas/peças de desgaste, manutenção, assistência, reforma, moagem/usinagem e clientes industriais que voltam a comprar ou cotar. Qualificado como MQL de validação para o Breno abrir esse tema com precisão.',
   'insight':'separar máquinas/equipamentos de venda consultiva dos itens e serviços recorrentes, como facas industriais, peças de reposição, manutenção e assistência, criando um canal para consulta de catálogo técnico e recompra sem depender de cada cotação manual',
 },
 'paulo.oliveira@gupy.com.br': {
   'slug':'gupy-paulo-oliveira', 'mql': False,
   'empresa_real':'Gupy — plataforma de tecnologia para RH, recrutamento, seleção, admissão, treinamento, engajamento e desenvolvimento de pessoas',
   'dominio_site':'gupy.com.br / gupy.io; site oficial confirma software/plataforma SaaS de RH para empresas, não operação de estoque físico',
   'redes':'LinkedIn Gupy e site oficial indicam plataforma número 1 da América Latina para recrutar, admitir, treinar, engajar e desenvolver pessoas; não foi localizado canal de atacado/distribuição ou catálogo de produtos físicos ligado ao contato',
   'segmento':'Software/SaaS e serviços de tecnologia para RH; venda de plataforma e soluções digitais, sem produto físico, revenda/lojista ou abastecimento recorrente de estoque',
   'motivo':'Pesquisa pública em gupy.io/gupy.com.br e LinkedIn confirmou empresa real, porém o modelo é plataforma SaaS de RH. A empresa vende software/serviço de recrutamento, admissão, treinamento e gestão de pessoas para empresas, não indústria, distribuidor, importador ou atacado com catálogo de produtos físicos para revendas/lojistas/clientes recorrentes de estoque. O contato veio sem telefone, sem empresa no cadastro e sem respostas de diagnóstico. Pelo crivo acirrado/fail-closed, fica fora do perfil T1 da Zydon.',
   'insight':'',
 },
 'flavio@sag.ind.br': {
   'slug':'sag-controle-posicionamento', 'mql': True,
   'empresa_real':'SAG Controle e Posicionamento de Máquinas — SAG Indústria e Comércio de Equipamentos e Automação Industrial Ltda, Curitiba/PR',
   'dominio_site':'sag.ind.br; site oficial confirma indústria/fabricante de sistemas de controle, posicionamento, segurança e ergonomia para máquinas pesadas, com catálogo de produtos, solicitação de cotação e loja/canal digital para linha JUUKO',
   'redes':'LinkedIn SAG no setor de fabricação de máquinas de automação; Instagram/Facebook @sag.ind.br; site oficial com clientes industriais como Vale, Gerdau, Usiminas, WEG, ArcelorMittal, Siemens e Votorantim; formulário público aceita integrador e revendedor',
   'segmento':'Indústria/fabricante e fornecedora B2B de joysticks, controladores industriais, cabines e mesas de comando, encoders, radares, sensores e sistemas para mineração, siderurgia, portos, ferrovias, agricultura e manufatura; operação com catálogo, cotação, assistência técnica e revendedores/integradores',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch confirmou domínio corporativo do e-mail, empresa industrial real, portfólio de produtos para indústria pesada, catálogo/cotação e atendimento nacional. O site informa categorias de cadastro como integrador e revendedor e divulga WhatsApp corporativo. Apesar de parte da venda ser técnica/sob projeto, há catálogo de componentes industriais, revenda/integradores e clientes B2B recorrentes; passa no crivo acirrado por indústria/fabricante B2B com oportunidade de digitalizar catálogo, especificação e recompra.',
   'insight':'clientes industriais e integradores encontrarem o componente certo de comando ou sensor e avançarem a cotação sem depender de troca manual de especificações a cada pedido',
   'whatsapp_publico':'WhatsApp corporativo divulgado no site oficial/rodapé e suporte: +55 41 98809-5846',
   'telefone_publico':'Comercial +55 41 3995-2154; plantão PR/WhatsApp +55 41 98809-5846; fonte: https://sag.ind.br/ e https://sag.ind.br/suporte/',
 },
 'cristiano@metris.digital': {
   'slug':'metris-performance-resultados', 'mql': False,
   'empresa_real':'Metris | Performance para Resultados — consultoria/agência de marketing de performance e e-commerce em Farroupilha/RS, ligada a Cristiano Creczyenski',
   'dominio_site':'metris.digital; site próprio confirma atuação como especialista em tráfego pago, conversão, retenção, otimização e assessoria estratégica para crescimento digital',
   'redes':'Instagram @metris.digital; LinkedIn Metris | Performance para Resultados; YouTube @metris.digital; Facebook Metris. Performance para Resultados; Cristiano Creczyenski aparece publicamente como CEO/host ligado à empresa',
   'segmento':'Agência/consultoria de marketing digital e performance para e-commerce, indústria, educação, negócios locais e SaaS; prestadora de serviço recorrente, não operação de estoque/produto físico',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch e site metris.digital confirmou empresa real, porém o modelo é agência/consultoria de marketing de performance. Ela vende serviço de tráfego, CRO, growth e assessoria a anunciantes/e-commerces, não produto físico para revendas, lojistas ou clientes recorrentes para abastecimento de estoque. O formulário informa ERP Bling e loja virtual, mas ERP/e-commerce não substituem ICP. Pelo crivo acirrado/fail-closed, prestador de serviço/consultoria fica fora do perfil T1 da Zydon.',
   'insight':'',
 },
 'marcelornap@gmail.com': {
   'slug':'marcelo-entendeu', 'mql': False,
   'empresa_real':'Não identificada — campo empresa veio como “entendeu?”, sem organização real confirmada',
   'dominio_site':'Sem domínio corporativo localizado; e-mail pessoal Gmail',
   'redes':'Nenhuma rede social, site, CNPJ ou presença pública conclusiva vinculando o e-mail ou “entendeu?” a uma operação comercial',
   'segmento':'Indeterminado; origem conversations, sem telefone, sem formulário e sem evidência de operação B2B',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch não encontrou empresa real associada ao e-mail marcelornap@gmail.com ou ao nome “entendeu?”. O contato veio sem telefone, sem respostas de diagnóstico e sem domínio corporativo. Não há evidência de indústria, distribuidor, importador ou atacado vendendo para revendas/lojistas/clientes recorrentes. Pelo crivo fail-closed, lead sem vínculo operacional comprovado não qualifica.',
   'insight':'',
 },
 'tankforceservice@gmail.com': {
   'slug':'tank-force', 'mql': False,
   'empresa_real':'Tank Force Service — operação não confirmada como empresa formal; perfil Instagram @tankforceservice encontrado ligado ao e-mail do lead',
   'dominio_site':'Sem domínio corporativo ou site próprio localizado; presença pública principal é Instagram @tankforceservice com telefone divulgado em snippets públicos',
   'redes':'Instagram @tankforceservice localizado; resultados públicos indicam atuação com tanques de combustível, tanques aéreos e serviços ligados a postos/empresas, mas sem site, CNPJ ou catálogo B2B verificável',
   'segmento':'Serviços/venda técnica de tanques de combustível; operação parece projeto/serviço sob orçamento, sem evidência clara de atacado, distribuição ou pedidos recorrentes de estoque',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch e buscas externas: há indícios de Tank Force Service no Instagram oferecendo soluções em tanques de combustível e atendimento por telefone, mas não foi encontrado site próprio, CNPJ, domínio corporativo, formulário, ERP, faturamento ou evidência de venda para revendas/lojistas com abastecimento recorrente de estoque. Pelo crivo acirrado/fail-closed, serviço/venda técnica sob orçamento e sem canal B2B recorrente claro não qualifica.',
   'insight':'',
 },
 'sac@lovearomas.com.br': {
   'slug':'love-aromas', 'mql': True,
   'empresa_real':'Love Aromas — marca de aromatização de ambientes de Praia Grande/SP, ligada ao CNPJ 42.206.992/0001-58',
   'dominio_site':'lovearomas.com.br; loja própria em Vendizap com produtos e kits de atacado para revenda',
   'redes':'Instagram @lovearomasoficial; loja oficial Shopee /lovearomasoficial',
   'segmento':'Aromatização de ambientes — difusores elétricos e essências concentradas, com kits de atacado para lojistas, perfumarias, lojas de decoração/presentes, artesãos e revendedores',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: o site lovearomas.com.br confirma loja própria e um kit chamado “O Melhor do Atacado para Seu Negócio”, direcionado a lojistas, perfumarias, lojas de decoração e presentes, artesãos e empreendedores da aromatização. O formulário reforça operação digital com ERP Bling, loja virtual ativa e venda por Instagram que cai no WhatsApp. Apesar do porte pequeno, há canal explícito de revenda, produto de reposição recorrente e oportunidade clara de digitalizar catálogo e recompras.',
   'insight':'transformar os leads do Instagram que caem no WhatsApp em um catálogo de reposição, para o lojista refazer pedidos de essências sem você anotar tudo de novo',
 },
 'wilson@dwtools.com.br': {
   'slug':'dwtools', 'mql': False,
   'empresa_real':'DWTOOLS (Dwtools Emphlower LTDA, São Paulo/SP)',
   'dominio_site':'dwtools.com.br; site próprio com e-commerce complementar e foco em soluções industriais para usinagem/CNC',
   'redes':'LinkedIn de Wilson Sergio; Facebook DW Tools oficial; presença pública e CNPJ localizados',
   'segmento':'Soluções industriais para usinagem e metal-mecânica, com ferramentas de corte CNC, insertos, simuladores/software, consultoria, treinamento e suporte técnico; e-commerce complementar de poucos SKUs',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: o site dwtools.com.br e fontes públicas confirmam empresa real no universo de ferramentas/usinagem, porém o posicionamento aparece mais como consultoria, treinamento, suporte técnico e venda técnica para indústrias usuárias finais de CNC do que como distribuidor/atacado com catálogo de alto giro para revendas ou lojistas. O formulário reforça baixo fit para o crivo acirrado: ainda não fatura, equipe 1 a 10, venda por visita e sem evidência clara de canal B2B recorrente para abastecimento de estoque. Pelo fail-closed, a dúvida relevante sobre canal de revenda e maturidade comercial impede qualificação.',
   'insight':'',
 },
 'tiago.miranda@reptec.com.br': {
   'slug':'reptec-reentrada', 'mql': True,
   'empresa_real':'Reptec — Equipamentos de Proteção e Uniformes',
   'dominio_site':'reptec.com.br; site próprio com catálogo de EPIs, uniformes e canais de atendimento/pedido',
   'redes':'Site oficial reptec.com.br e atendimento/pedido por WhatsApp; presença pública confirma atuação B2B em proteção e uniformização',
   'segmento':'Indústria e distribuidora de EPIs, uniformes profissionais e itens de proteção, com revenda e venda B2B para grandes contas',
   'motivo':'Pesquisa pública confirmou fabricação própria de EPIs/uniformes e distribuição de marcas líderes, com segmento explícito de revenda e venda B2B para grandes contas. EPIs são consumíveis de alto giro e reposição recorrente, com catálogo extenso, tabela de preço e pedidos recorrentes. O formulário reforça fit: mais de 151 pessoas, faturamento de R$50 a R$500 milhões/ano, venda por equipes de vendedores e sem loja virtual. Qualificado por indústria/distribuidora B2B com canal de revenda, abastecimento recorrente e oportunidade clara de digitalizar catálogo e pedidos.',
   'insight':'clientes, revendas e vendedores consultarem catálogo, preço e disponibilidade de EPIs de alto giro sem depender de cada pedido manual',
 },
 'alex@tudorpiracicaba.com.br': {
   'slug':'tudor-piracicaba', 'mql': False,
   'empresa_real':'Tudor Baterias Piracicaba Ltda — revenda/distribuidor regional da marca Tudor em Piracicaba/SP',
   'dominio_site':'tudorpiracicaba.com.br; site próprio voltado a atendimento regional por telefone/WhatsApp',
   'redes':'Instagram @tudorpiracicaba e Facebook Tudor Piracicaba localizados na pesquisa pública',
   'segmento':'Revenda/distribuidor local de baterias automotivas, com perfil de ponto de venda regional e atendimento presencial',
   'motivo':'Pesquisa pública confirmou empresa real e distribuidor exclusivo Tudor em Piracicaba desde 1993, mas o conjunto aponta operação local de pequeno porte e venda ao consumidor final por telefone/WhatsApp. O formulário informa faturamento de R$500 mil a R$1 milhão/ano, 11 a 25 pessoas, venda presencial e sem loja virtual. Não houve evidência clara de atacado ou venda recorrente para revendas/lojistas com abastecimento de estoque em escala. Pelo crivo MQL acirrado, revenda/varejo local sem canal B2B claro não qualifica.',
   'insight':'',
 },
 'loja@colornail.shop': {
   'slug':'colornail-premium', 'mql': False,
   'empresa_real':'Premium / ColorNail — operação não confirmada publicamente',
   'dominio_site':'colornail.shop; site encontrado com template de loja não configurado, sem evidência de operação comercial ativa',
   'redes':'Nenhuma rede social ou presença pública conclusiva de operação atacadista, industrial ou distribuidora ligada ao lead',
   'segmento':'E-commerce D2C de nicho em estágio pré-operacional, sem faturamento e sem canal B2B comprovado',
   'motivo':'Pesquisa pública encontrou o domínio colornail.shop com vitrine genérica/template não configurado, sem loja real validada. O formulário informa que ainda não fatura, tem 1 a 10 pessoas, vende direto, tem e-commerce e telefone inválido/fixo. Não há evidência de indústria, distribuidor, importador ou atacado vendendo para revendas/lojistas, nem operação recorrente de abastecimento. Pelo crivo fail-closed, micro D2C pré-receita com contato inconsistente não qualifica.',
   'insight':'',
 },
 'alex@panflight.com': {
   'slug':'panflight-sensors-reentrada-2', 'mql': True,
   'empresa_real':'Panflight Sensors — indústria de sensores, placas eletrônicas, HMIs e joysticks para máquinas pesadas, com operação em Piracicaba/SP e centro de distribuição Panflight USA',
   'dominio_site':'panflight.com; site próprio com portfólio técnico para máquinas pesadas e atuação em OEM e reposição',
   'redes':'LinkedIn PANFLIGHT SENSORS; Instagram @panflightsensors; Facebook Panflight; YouTube @PanflightSensors',
   'segmento':'Indústria de componentes eletrônicos para máquinas pesadas, agro/cana, mineração, construção e energia, com canal de reposição via distribuidores/revendedores e clientes recorrentes',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo confirmou a Panflight como indústria de sensores, placas eletrônicas e HMIs para máquinas pesadas, com dois canais: OEM sob projeto e reposição para distribuidores/revendedores. O braço de reposição enquadra o lead no crivo acirrado: revendas precisam consultar preço, código equivalente e disponibilidade para repor estoque de peças de alto giro. O formulário reforça fit: faturamento R$1 a R$5 milhões/ano, 51 a 150 pessoas, venda por WhatsApp/telefone/e-mail e loja virtual ativa.',
   'insight':'revendas consultarem códigos equivalentes, preço e disponibilidade de sensores de reposição sem depender de cada cotação manual quando uma máquina pesada para',
 },
 'financeiro@baltikbrasil.com.br': {
   'slug':'baltik-brasil', 'mql': False,
   'empresa_real':'Indeterminada — não foi possível confirmar empresa operacional vinculada ao domínio Baltik Brasil',
   'dominio_site':'baltikbrasil.com.br; domínio não carregou corretamente na pesquisa do ciclo por erro de certificado TLS',
   'redes':'Nenhuma rede social oficial localizada para Baltik Brasil; resultados públicos encontrados eram homônimos sem vínculo com o domínio',
   'segmento':'Não identificado; sem evidência pública de produto, catálogo, indústria, distribuição, importação ou atacado',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo não confirmou operação real: contato sem nome, empresa, telefone ou formulário; domínio baltikbrasil.com.br com problema de certificado; sem redes, CNPJ, catálogo ou presença pública conclusiva. Pelo crivo MQL acirrado/fail-closed, sem prova de indústria, distribuidor, importador ou atacado B2B com revendas/lojistas/clientes recorrentes, não qualifica.',
   'insight':'',
 },
 'julietakim@rawraw.com.br': {
   'slug':'raw-raw', 'mql': True,
   'empresa_real':'Raw Raw — marca/fabricante de alimentação bioapropriada e petiscos naturais para pets',
   'dominio_site':'rawraw.com.br; site próprio com canal B2B explícito para revendedores e criadores',
   'redes':'Instagram @rawraw.pet; Facebook @rawraw.pet',
   'segmento':'Indústria/marca de alimento natural e petiscos para pets, consumível de alto giro com revenda e recompra recorrente',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: o site rawraw.com.br tem menu Revendedores com link “sou revendedor” (/b2b), seção Criadores e venda por assinatura/recorrência. O formulário reforça fit: ERP Olist/Tiny, faturamento de R$1 a R$5 milhões/ano, loja virtual ativa e venda por e-commerce + WhatsApp. Qualificado por fabricante de produto consumível recorrente com canal de revenda claro, catálogo e pedidos recorrentes digitalizáveis.',
   'insight':'revendedores e criadores recomprarem ração e petiscos em um canal próprio, sem depender de cada pedido manual pelo WhatsApp',
 },
 'comercial@brisker.com.br': {
   'slug':'brisker-group', 'mql': True,
   'empresa_real':'Brisker Group Ltda / Brisker Aftermarket & Solutions — distribuidor de peças de ar-condicionado automotivo',
   'dominio_site':'brisker.com.br; site próprio com páginas institucionais e catálogo/atendimento para aftermarket automotivo',
   'redes':'LinkedIn Brisker Group; Facebook Brisker Group; loja Mercado Livre /brisker',
   'segmento':'Distribuidor atacadista de peças de ar-condicionado automotivo para oficinas, frotas e mercado de reposição',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: páginas do site brisker.com.br confirmam distribuidor de peças de ar-condicionado automotivo com centros de distribuição em SP e MG, atendimento a oficinas e frotas em todo o Brasil e presença pública como comércio atacadista de peças automotivas. O formulário informa ERP Olist/Tiny, loja virtual ativa e venda hoje por ligação. Embora o faturamento declarado seja baixo, o modelo de distribuição para oficinas/frotas, catálogo de peças e reposição recorrente é aderente ao ICP.',
   'insight':'oficinas e frotas consultarem peças de ar-condicionado e fazerem reposição sem depender de ligação para cada pedido',
 },
 'jedson.maroto@ktr.group': {
   'slug':'ktr-group', 'mql': True,
   'empresa_real':'KTR Group — operação brasileira de importação, distribuição e fornecimento de máquinas/produtos para indústria de transformação',
   'dominio_site':'ktr.group; site próprio com portfólio de máquinas e soluções industriais',
   'redes':'LinkedIn KTR Group; presença pública como fornecedor para setores industriais, transporte e automotivo',
   'segmento':'Importadora/distribuidora/fornecedora industrial B2B com venda para indústria de transformação e clientes recorrentes por proposta, pedido e nota fiscal',
   'motivo':'Pesquisa pública localizou a KTR Group com posicionamento de fornecimento industrial e portfólio para setores como transporte, automotivo e indústria de transformação. O formulário reforça porte e dor: faturamento de R$5 a R$10 milhões/ano, 21 a 100 pessoas, venda por WhatsApp com proposta, pedido e nota fiscal, ERP Outro e sem loja virtual. Qualificado por operação B2B industrial com volume comercial e processo manual que tende a ganhar muito com canal digital.',
   'insight':'transformar o fluxo de cotação, proposta, pedido e nota em um canal de compra mais rápido para clientes industriais recorrentes',
 },
 'moacyr@norimport.com.br': {
   'slug':'nor-import-moacyr', 'mql': True,
   'empresa_real':'Nor Import Comercial de Alimentos Ltda — importadora e distribuidora atacadista de alimentos finos em São Paulo/SP, ativa desde 2005',
   'dominio_site':'norimport.com.br; CNPJ público 07.635.660/0001-98; site próprio da importadora/distribuidora',
   'redes':'Instagram @nor_import; Facebook Nor Importadora; LinkedIn Nor Import Comercial de Alimentos',
   'segmento':'Importadora/distribuidora/atacado de alimentos finos, bebidas e conservas, com marcas próprias/importadas e venda B2B por representantes',
   'motivo':'Pesquisa pública em site, redes e bases cadastrais confirmou a Nor Import como importadora e atacadista de alimentos finos, com oito linhas de produtos e marcas vendidas para varejo, food service e lojistas. O formulário reforça o fit: venda por representantes, ERP TOTVS, faturamento de R$5 a R$10 milhões/ano, 11 a 25 pessoas e sem loja virtual. Qualificado por encaixe direto em importador/distribuidor com alto giro, catálogo/tabela de preços e pedidos recorrentes para abastecimento de estoque.',
   'insight':'os representantes e clientes B2B consultarem preço, mix e disponibilidade das oito linhas de importados em um canal próprio, sem depender de planilhas e pedidos soltos',
 },
 'kleyton@kmdrimotec.com.br': {
   'slug':'kleyton-marcelino-kmdrimotec', 'mql': False,
   'empresa_real':'KM Drimotec (KM Motores Elétricos, Bombas e Redutores) — Kleyton David Marcelino, Limeira-SP',
   'dominio_site':'kmdrimotec.com.br',
   'redes':'Facebook KM Motores Elétricos / KM Drimotec; presença pública local em Limeira-SP',
   'segmento':'Oficina de manutenção e conserto de motores elétricos, bombas e redutores, com loja de balcão de peças e motores (serviço + varejo local)',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: o domínio kmdrimotec.com.br exibe a KM Drimotec/KM Motores Elétricos como oficina de conserto e manutenção de motores elétricos, bombas e redutores em Limeira-SP, com rebobinagem, manutenção preventiva/corretiva, usinagem, montagem de painéis e uma loja de balcão de peças/motores. Não houve evidência de indústria, distribuidor, importador ou atacadista vendendo para revendas/lojistas com pedidos recorrentes para abastecimento de estoque. O formulário reforça porte pequeno: faturamento até R$250 mil/ano, equipe 1 a 10, sem loja virtual e venda por WhatsApp e balcão. Pelo crivo MQL acirrado/fail-closed, oficina/serviço local com varejo de balcão e sem canal de revenda claro não qualifica.',
   'insight':'',
 },
 'licinio@meelflores.com.br': {
   'slug':'meel-flores', 'mql': False,
   'empresa_real':'Meel Flores',
   'dominio_site':'meelflores.com.br (domínio provável; site respondeu com problema de certificado no ciclo)',
   'redes':'Perfis públicos homônimos/localizados na pesquisa: Instagram @meel_flores04, TikTok @meelflores3 e Facebook Meel Flores; presença pública aponta floricultura/varejo de flores, mas sem evidência de atacado ou distribuição B2B',
   'segmento':'Floricultura / varejo de flores, buquês e arranjos, com venda direta ao consumidor por Instagram, WhatsApp e loja virtual',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: a operação encontrada para Meel Flores é de floricultura/varejo de presentes e arranjos, voltada a consumidor final e datas comemorativas. O formulário informa venda por Instagram e WhatsApp, loja virtual ativa, ERP TOTVS, equipe de 1 a 10 pessoas e faturamento de R$250 mil a R$500 mil/ano. Apesar de existir operação digital, não houve evidência clara de indústria, distribuidor, importador ou atacado que abasteça revendas/lojistas com alto giro e pedidos recorrentes. Pelo crivo MQL acirrado/fail-closed, pequeno D2C de nicho sem canal de revenda claro não qualifica.',
   'insight':'',
 },
 'danielfreitas.fermontes2025@gmail.com': {
   'slug':'daniel-freitas', 'mql': False,
   'empresa_real':'Não confirmada — possível pista indireta para Fermontes Comércio Ltda, sem vínculo público com o contato',
   'dominio_site':'Sem domínio corporativo do lead; e-mail Gmail pessoal',
   'redes':'Nenhuma presença pública conclusiva ligando Daniel Freitas a uma empresa aderente',
   'segmento':'Indeterminado; possível atacado alimentício não comprovado',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: o e-mail pessoal não comprova empresa, o campo empresa repete o nome da pessoa e o telefone informado é apenas “55”. O token “fermontes2025” sugere possível relação com Fermontes Comércio Ltda, atacado de farinhas/féculas/fermentos em Montes Claros/MG, mas não foi encontrada evidência pública vinculando Daniel Freitas a essa empresa. Sem domínio corporativo, telefone real, formulário ou vínculo comprovado, não há base segura para qualificar.',
   'insight':'',
 },
 'manut2@bananinhaparaibuna.com.br': {
   'slug':'bananinha-paraibuna', 'mql': True,
   'empresa_real':'Bananinha Paraibuna — indústria alimentícia de doces de banana em Paraibuna/SP, ativa desde 1975',
   'dominio_site':'bananinhaparaibuna.com.br; domínio corporativo e site próprio da fabricante',
   'redes':'LinkedIn Bananinha Paraibuna; Facebook Bananinha Paraibuna; matérias públicas em InvestNews/Terra sobre a operação',
   'segmento':'Indústria alimentícia com distribuição B2B/atacado, PDV, varejo natural e exportação',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: domínio corporativo do e-mail confere com empresa real e ativa; a Bananinha Paraibuna é fabricante tradicional de doces de banana desde 1975, com estrutura industrial, presença pública sólida, distribuição para pontos de venda/lojas naturais e expansão/exportação. A entrada veio por portal do cliente, mas sem telefone e sem formulário. Qualificado pelo fit forte de indústria alimentícia e distribuição B2B, com ressalva de que o e-mail “manut2” parece ser de manutenção e o decisor comercial deve ser identificado.',
   'insight':'dar aos pontos de venda e revendedores um caminho mais direto para recomprar produtos recorrentes, sem depender de cada pedido cair manualmente no atendimento',
 },
 'comercial.asb.gerencia@gmail.com': {
   'slug':'fernando-carvalho-asb', 'mql': False,
   'empresa_real':'Não confirmada — sigla ASB ambígua em bases públicas',
   'dominio_site':'Sem domínio corporativo; e-mail Gmail genérico',
   'redes':'Nenhuma rede ou fonte pública conclusiva vinculando Fernando Carvalho a uma empresa ASB específica',
   'segmento':'Indeterminado; múltiplas empresas ASB possíveis, sem vínculo comprovado',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: o e-mail é Gmail, a empresa veio vazia, não há telefone nem formulário, e “ASB” aparece em múltiplas empresas públicas sem prova de vínculo com Fernando Carvalho. Sem domínio próprio, CNPJ/empresa confirmada ou evidência de operação atacadista, distribuidora, industrial ou canal B2B aderente, não há base mínima para qualificar.',
   'insight':'',
 },
 'claudioigino@norimport.com.br': {
   'slug':'nor-import', 'mql': True,
   'empresa_real':'Nor Import Comercial de Alimentos Ltda — importadora e distribuidora de bebidas em São Paulo/SP',
   'dominio_site':'norimport.com.br; site próprio ativo da importadora/distribuidora',
   'redes':'Instagram @norimport; Facebook Nor Import; LinkedIn Nor Import localizados na pesquisa pública',
   'segmento':'Importação e distribuição de bebidas — atacado/distribuição B2B com mix de marcas importadas',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: domínio corporativo norimport.com.br confirma empresa real; presença em redes e bases públicas aponta importadora/distribuidora de bebidas com estrutura e operação B2B. Embora o contato tenha vindo por conversations sem formulário e sem telefone, o domínio e a operação pública confirmam fit forte de atacado/distribuição.',
   'insight':'dar aos revendedores e clientes recorrentes um catálogo de bebidas importadas para consultar mix, disponibilidade e fazer pedidos com menos dependência de troca manual no atendimento',
 },
 'dreambmx@dreambmx.com.br': {
   'slug':'dream-bmx', 'mql': True,
   'empresa_real':'Dream BMX — importadora/distribuidora e loja especializada em BMX no Brasil',
   'dominio_site':'dreambmx.com.br; site próprio com loja virtual e página institucional',
   'redes':'Instagram @dreambmx e Facebook Dream BMX localizados na pesquisa pública',
   'segmento':'Importador/distribuidor especializado em BMX, com loja física, e-commerce e canal de revenda para lojistas',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: site próprio confirma a Dream BMX como operação real no nicho de BMX, com e-commerce, loja física e atuação como importadora/distribuidora exclusiva de marcas. O formulário reforça fit: venda em loja física e e-commerce, loja virtual ativa, faturamento R$500 mil a R$1 milhão/ano e ERP Outro. Qualificado por distribuição especializada e canal digital existente, apesar da equipe enxuta.',
   'insight':'sincronizar estoque e pedidos entre loja física, e-commerce e lojistas que compram marcas de BMX mais nichadas, sem depender de cada conversa manual',
 },
 'andre@andrelavor.com': {
   'slug':'andre-lavor-moinho-centro-norte', 'mql': False,
   'empresa_real':'Moinho Centro Norte Ltda aparece em bases públicas em recuperação judicial; o domínio andrelavor.com é site pessoal de palestras/consultoria de André Lavor',
   'dominio_site':'andrelavor.com; site pessoal, não domínio operacional do moinho/indústria',
   'redes':'Instagram/Facebook/LinkedIn com referências a Moinho Centro Norte e presença pessoal de André Lavor, mas sem canal comercial B2B ativo vinculado ao lead',
   'segmento':'Indústria moageira de trigo em situação pública sensível / lead aparenta vir por marca pessoal de consultoria',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: embora o formulário declare Moinho Centro Norte, Omie e faturamento alto, o e-mail usa domínio pessoal andrelavor.com, voltado a palestras e advisory, e a empresa industrial aparece em recuperação judicial. Sem domínio operacional ativo do negócio comprando, telefone inválido e sem loja/canal digital, não há segurança para qualificar como oportunidade comercial B2B da Zydon neste ciclo.',
   'insight':'',
 },
 'rafael@tddistribuidora.com.br': {
   'slug':'rafael-leal-tddistribuidora', 'mql': True,
   'empresa_real':'TD Distribuidora Ltda (TD Produtos de Limpeza e Descartáveis) — CNPJ 13.146.468/0001-30, Mooca/São Paulo-SP',
   'dominio_site':'tddistribuidora.com.br; site próprio com catálogo amplo de produtos de limpeza, descartáveis, embalagens e utilidades domésticas',
   'redes':'Facebook oficial: facebook.com/distribuidora.td',
   'segmento':'Distribuidora/atacado de produtos de limpeza, descartáveis, embalagens e utilidades domésticas; CNAE público de comércio atacadista',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: domínio do e-mail confere com o site tddistribuidora.com.br; a TD Distribuidora aparece como empresa ativa na Mooca/São Paulo-SP, CNPJ 13.146.468/0001-30, com catálogo de mais de 1.600 itens entre limpeza, descartáveis e embalagens e presença no Facebook. O formulário reforça o fit: venda por pedidos, ERP Outro, faturamento de R$5 a R$10 milhões/ano, 11 a 25 pessoas e sem loja virtual. Qualificado por atacado/distribuição real, porte compatível, mix amplo e oportunidade clara de digitalizar pedidos recorrentes.',
   'insight':'dar mais autonomia para clientes recorrentes montarem pedidos em um catálogo guiado de mais de 1.600 itens, reduzindo idas e vindas no WhatsApp',
 },
 'roberto@montibeler.com.br': {
   'slug':'montibeler-equipamentos', 'mql': True,
   'empresa_real':'Montibeler Equipamentos de Segurança — Montibeler Equipamentos Ltda, Blumenau/SC, empresa de EPIs e segurança do trabalho ativa desde 1997',
   'dominio_site':'montibeler.com.br; site/loja virtual própria com catálogo de EPIs, sinalização, ergonomia, óculos, calçados e vestimentas profissionais',
   'redes':'Instagram @montibelerequipamentos; Facebook Montibeler Equipamentos; LinkedIn Montibeler Equipamentos',
   'segmento':'Distribuidora/revenda B2B de EPIs, sinalização e ergonomia para segurança do trabalho, com venda por WhatsApp e e-commerce',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: domínio do e-mail confere com site próprio e loja virtual da Montibeler Equipamentos; presença ativa em Instagram, Facebook e LinkedIn; empresa de Blumenau/SC atua desde 1997 com catálogo amplo de EPIs, sinalização e ergonomia. O formulário reforça o fit: venda por WhatsApp e e-commerce, loja virtual ativa, faturamento de R$1 a R$5 milhões/ano e equipe enxuta. Qualificado por operação B2B real, canal digital existente e oportunidade clara de organizar recompras recorrentes de empresas compradoras de EPIs.',
   'insight':'transformar o catálogo grande de EPIs em uma experiência de recompra mais guiada, para empresas acharem rápido o que precisam sem depender de cada conversa no WhatsApp',
 },
 'alexandre@sigaatacado.com.br': {
   'slug':'siga-atacado', 'mql': True,
   'empresa_real':'Siga Atacado — operação de atacado/distribuição em São Paulo vinculada ao domínio sigaatacado.com.br',
   'dominio_site':'sigaatacado.com.br; domínio próprio do e-mail do lead, mas site público não respondeu/não apareceu indexado no ciclo',
   'redes':'Nenhuma rede social oficial conclusiva localizada para Siga Atacado no ciclo; resultados similares encontrados eram de outras empresas e foram descartados',
   'segmento':'Atacado/distribuição B2B; formulário informa venda hoje por WhatsApp, sem loja virtual, 11 a 25 pessoas e faturamento de R$10 a R$50 milhões/ano',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: não houve vitrine pública ativa em sigaatacado.com.br e as empresas parecidas encontradas não batiam com Alexandre Garrido/Siga Atacado. Ainda assim, o e-mail usa domínio próprio com nome explícito de atacado, o formulário informa operação relevante de R$10 a R$50 milhões/ano, equipe de 11 a 25 pessoas, venda concentrada no WhatsApp e ausência de loja virtual. O conjunto domínio próprio + declaração de atacado + porte alto no formulário torna o lead aderente ao ICP de distribuição B2B e justifica qualificação, com ressalva para confirmar o mix de produtos na conversa comercial.',
   'insight':'abrir um catálogo de pedidos para clientes recorrentes comprarem no horário deles, sem deixar todo o volume preso no WhatsApp',
 },
 'contato@faerytaleliquor.com': {
   'slug':'faerytale-liquor', 'mql': True,
   'empresa_real':'Faery Tale Liquor — marca/produtora de licor artesanal em Presidente Prudente/SP',
   'dominio_site':'faerytaleliquor.com; loja virtual própria ativa da marca Faery Tale Liquor',
   'redes':'Instagram oficial @faerytaleliquor localizado na pesquisa pública',
   'segmento':'Indústria/marca de licor artesanal com canal B2B para bares, restaurantes e eventos, venda por representante e loja virtual',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real confirmada por domínio próprio e Instagram oficial. O formulário informa ERP Bling, faturamento até R$250 mil/ano, equipe de 1 a 10 pessoas, venda por representante e loja virtual ativa. Embora seja pequena, é uma marca/produtora com produto próprio, canal digital e venda recorrente para bares, restaurantes e eventos, aderente ao ICP de indústria/canal B2B em estágio inicial.',
   'insight':'bares, restaurantes e eventos parceiros fazerem pedidos recorrentes em um canal próprio, sem depender da agenda de um único representante',
 },
 'artimundo@dfermetais.com.br': {
   'slug':'dfer-acos-e-metais', 'mql': False,
   'empresa_real':'Dfer Aços e Metais (não confirmada publicamente)',
   'dominio_site':'dfermetais.com.br (domínio do e-mail, mas sem site ativo na pesquisa do ciclo)',
   'redes':'Nenhuma rede social, CNPJ ou presença pública conclusiva localizada para Dfer Aços e Metais no ciclo',
   'segmento':'Aços e metais declarado no cadastro — potencial B2B/distribuição, porém não verificado publicamente',
   'motivo':'Pesquisa pública: o segmento declarado de aços e metais é aderente em tese e o e-mail usa domínio próprio compatível com o nome, mas não foi encontrado site ativo, CNPJ, Facebook, Instagram ou presença pública conclusiva. O formulário informa porte muito pequeno, faturamento até R$250 mil/ano e 1 a 10 pessoas. Sem evidência mínima de operação atacadista/distribuidora/industrial real em escala aderente, não qualificado neste ciclo.',
   'insight':'',
 },
 'juliano@miniclo.com.br': {
   'slug':'miniclo-industria', 'mql': True,
   'empresa_real':'Miniclô Indústria e Comércio de Confecções Ltda — marca Miniclô, indústria nacional de moda bebê com fábrica em Terra Roxa/PR e filial em Curitiba/PR',
   'dominio_site':'miniclo.com.br / institucional.miniclo.com.br; site institucional ativo confirmando 20+ anos de mercado e produção 100% nacional',
   'redes':'Instagram @miniclomodabebe com presença ativa; Facebook Miniclô; presença em revendas/marketplaces de atacado kids',
   'segmento':'Indústria de confecção infantil / moda bebê, com venda atacado B2B para lojistas por representantes e vendedores internos',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: domínio corporativo e site institucional confirmam indústria real de moda bebê, com parque fabril, mais de 20 anos de mercado e venda B2B para lojistas. O formulário reforça o fit: ERP Omie, faturamento de R$1 a R$5 milhões/ano, 21 a 100 pessoas, vendas por representantes e vendedores internos e sem loja virtual. Qualificado por indústria B2B, porte compatível e oportunidade clara de digitalizar pedidos de lojistas e representantes.',
   'insight':'os lojistas e representantes espalhados pelo Brasil fazerem pedidos em um canal único, com mais visibilidade para acompanhar quem está comprando, parando de comprar ou crescendo',
 },
 'fabiomilennials1234@gmail.com': {
   'slug':'fabio-curso', 'mql': False,
   'empresa_real':'Não identificada — não há evidência pública de empresa vinculada ao contato Fabio Curso',
   'dominio_site':'Sem domínio próprio identificado; e-mail pessoal Gmail e nenhum site corporativo associado encontrado',
   'redes':'A única pista pública pelo handle fabiomilennials aponta para perfil pessoal de conteúdo/entretenimento; sem comprovação de operação comercial',
   'segmento':'Indefinido; sem evidência de atacado, distribuição, indústria, operação B2B ou canal digital próprio',
   'motivo':'Pesquisa pública encontrou ausência de empresa real, domínio, CNPJ, loja virtual ou presença comercial ligada ao contato. O cadastro também veio sem respostas de qualificação, com e-mail pessoal, empresa igual ao nome informado e telefone inválido apenas 55. Sem sinais mínimos de operação B2B aderente à Zydon.',
   'insight':'',
 },
 'contato.distribuidoravarejo@outlook.com.br': {
   'slug':'distribuidora-de-varejo-francisco-ronaldo', 'mql': False,
   'empresa_real':'Não identificada — “Distribuidora de varejo” parece nome genérico/placeholder informado no cadastro',
   'dominio_site':'Sem domínio próprio identificado; e-mail gratuito @outlook.com.br; nenhum site/CNPJ correspondente encontrado',
   'redes':'Nenhuma rede social ou presença pública conclusiva localizada para o nome, e-mail ou telefone do lead',
   'segmento':'Indefinido; sem comprovação pública de atacado, distribuição, indústria, B2B ou canal digital',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: buscas por Francisco Ronaldo de Oliveira filho, contato.distribuidoravarejo@outlook.com.br, telefone 55 85 99976-4333 e “Distribuidora de varejo” não encontraram empresa real correspondente, domínio, CNPJ, redes sociais ou operação digital. O cadastro não trouxe respostas de formulário, ERP, faturamento, loja virtual nem segmento. Com e-mail gratuito, nome de empresa genérico e ausência de evidência pública, não há base mínima para qualificar como operação B2B aderente.',
   'insight':'',
 },
 'fernando@conectivasports.com.br': {
   'slug':'conectiva-sports', 'mql': True,
   'empresa_real':'Conectiva Sports (Conectiva Comércio e Confecção de Artigos do Vestuário) — Niterói/RJ',
   'dominio_site':'conectivasports.com.br; site oficial ativo e telefone/WhatsApp público conferindo com o formulário',
   'redes':'Instagram @conectivasports; Facebook barbedoconectiva / uniformesbarbedo.conectiva; LinkedIn Conectiva Sports; WhatsApp público +55 21 99449-5070',
   'segmento':'Confecção/indústria de vestuário esportivo — uniformes de ciclismo personalizados para times, grupos de ciclismo, bike shops e organizadores de evento',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: domínio do email confere com o site oficial conectivasports.com.br, e o telefone do formulário é o mesmo WhatsApp publicado no site. A operação é fabricante/confecção de uniformes personalizados, com venda B2B para times, grupos de ciclismo, bike shops e eventos. O formulário confirma ERP Bling, operação enxuta, venda hoje pelo WhatsApp, sem loja virtual e faturamento até R$250 mil/ano. Qualificado por indústria B2B sob encomenda, domínio próprio e canal digital ainda manual.',
   'insight':'transformar os pedidos de times e bike shops que hoje chegam soltos no WhatsApp num catálogo que recebe e fecha o pedido sozinho',
 },
 'ar@linexgel.com.br': {
   'slug':'linex-gel', 'mql': True,
   'empresa_real':'Linex Gel — fabricante de produtos de higiene e assepsia em Contagem/MG',
   'dominio_site':'linexgel.com.br; site oficial ativo com posicionamento de indústria/fabricante',
   'redes':'Facebook Linex Gel (Contagem/MG); Instagram @linexgel; produtos Linex encontrados em distribuidores e varejistas como Máxima Distribuidora e Lojas Rede',
   'segmento':'Indústria de higiene, limpeza e saneantes — álcool gel 70º, multiuso e sabonete, com venda em atacado/distribuição para supermercados e distribuidores',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: domínio do email confere com o site oficial linexgel.com.br. A empresa se posiciona como indústria fabricante de produtos de desinfecção e higiene, com evidências públicas de venda por distribuidores e redes varejistas. O formulário confirma ERP Bling, 11 a 25 pessoas, faturamento de R$500 mil a R$1 milhão/ano, venda hoje presencial/no balcão e sem loja virtual. Qualificado por indústria B2B/atacado com canal comercial ainda pouco digitalizado.',
   'insight':'abrir um canal de pedidos online para distribuidores e mercados comprarem direto, sem depender só do representante no balcão',
 },
 'mecanicaholz421@gmail.com': {
   'slug':'mario-luiz-holz-auto-mecanica-holz', 'mql': False,
   'empresa_real':'Auto Mecânica Holz (MLH Mecânica LTDA) — oficina mecânica automotiva em Santo Cristo/RS e Santa Rosa/RS, ligada a Mario Luiz Holz',
   'dominio_site':'Sem domínio próprio identificado; presença pública por redes sociais e cadastros CNPJ',
   'redes':'Instagram @holzservicosautomotivosoficial; Facebook HOLZ Serviços Automotivos',
   'segmento':'Serviços de manutenção e reparação mecânica automotiva — oficina local B2C',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: Mario Luiz Holz foi identificado como sócio-administrador da Auto Mecânica Holz / MLH Mecânica LTDA, empresa real de serviços automotivos. Porém o segmento é oficina mecânica local, fora do ICP Zydon de atacado, distribuição, indústria ou canal digital B2B. O lead ainda veio com e-mail Gmail, telefone inválido apenas “55” e sem respostas de formulário, reforçando a não qualificação.',
   'insight':'',
 },
 'luciano@grupotemtudo.com': {
   'slug':'temap-store-grupo-tem-tudo', 'mql': False,
   'empresa_real':'Grupo Tem Tudo — domínio público ligado a agência de marketing, gráfica e serviços digitais em Santo André/SP; Temap Store não confirmada publicamente',
   'dominio_site':'grupotemtudo.com; site público encontrado, mas o conteúdo é de agência/serviços, não de operação de loja/atacado aderente ao ICP',
   'redes':'Site grupotemtudo.com e página de loja interna; não foram encontradas redes/marketplace conclusivos vinculando Luciano ou Temap Store',
   'segmento':'Agência de marketing e serviços gráficos/digitais; operação de e-commerce Temap Store não comprovada publicamente',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: o domínio grupotemtudo.com existe, mas a presença pública encontrada é de agência de marketing/gráfica, criação de sites/e-commerce, foto e vídeo. Não foi encontrada evidência conclusiva de Temap Store, de Luciano ou de uma loja virtual B2B/atacado operando com estrutura própria. Apesar do formulário declarar Bling, loja virtual e venda por marketplace/rede social, há divergência forte entre o cadastro e a realidade pública e o porte informado é até R$250 mil/ano, 1 a 10 pessoas. Sem confirmação do negócio descrito, não qualificado como MQL neste ciclo.',
   'insight':'',
 },
 'leonardo@garaviniagricola.com.br': {
   'slug':'garaviniagricola', 'mql': True,
   'empresa_real':'Garavini Agrícola — Máquinas Agrícolas Garavini, empresa familiar fundada em 1931 em Ponte Nova/MG',
   'dominio_site':'garaviniagricola.com.br; site próprio com catálogo em 13 categorias, produtos com CTA de compra e páginas de máquinas, implementos, sementes, fertilizantes, irrigação, ferramentas, ferragens e insumos agropecuários',
   'redes':'Facebook Garavini Agrícola, Instagram @garavini.maquinas.oficial e site oficial com unidades/endereços e WhatsApp comercial público',
   'segmento':'Distribuidora B2B do agronegócio, máquinas agrícolas, implementos, insumos, sementes, fertilizantes, irrigação, ferramentas e componentes para produtores rurais, revendas regionais e clientes recorrentes com abastecimento de estoque/reposição',
   'motivo':'Pesquisa pública confirmou operação real e tradicional no agronegócio: fundada em 1931, com mais de 90 anos, catálogo amplo de máquinas, implementos, insumos, sementes, fertilizantes, irrigação e componentes, além de CTAs de compra/e-commerce no site. O formulário veio de “Tenho estrutura física e quero vender online B2B”. Qualificado por distribuidora agrícola com catálogo físico amplo, compra recorrente, abastecimento de estoque e oportunidade clara de digitalizar consulta de produtos, preço, disponibilidade e pedidos.',
   'insight':'produtores rurais e clientes recorrentes consultarem catálogo, preço e disponibilidade de insumos, peças, máquinas e implementos, fazendo pedidos recorrentes e reposição de estoque sem depender de cada orçamento manual',
 },
 'vendas4@sealalimentos.com.br': {
   'slug':'seal-alimentos', 'mql': True,
   'empresa_real':'Seal Indústria e Comércio de Alimentos Ltda — SEAL Allergen Free Foods, indústria/fabricante de alimentos sem glúten e livres de alergênicos em Tatuí/SP',
   'dominio_site':'sealalimentos.com.br; site oficial ativo com páginas institucionais, produtos e contato comercial',
   'redes':'Instagram @casaraonaocontemgluten; Facebook casaraosemgluten; telefone/WhatsApp público confere com o formulário',
   'segmento':'Indústria de alimentos sem glúten e alergênicos, com venda recorrente para empórios, lojas de produtos naturais e varejo especializado por representantes e loja virtual',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real confirmada pelo domínio oficial sealalimentos.com.br e CNPJ público 15.473.032/0001-81 em Tatuí/SP. A operação é fabricante de alimentos sem glúten e livres de alergênicos, com produtos físicos de recompra recorrente. O formulário reforça o fit: faturamento de R$1 a R$5 milhões/ano, 11 a 25 pessoas, venda por representantes, loja virtual ativa e telefone móvel válido. Qualificado por indústria B2B com canal digital e carteira de reposição previsível.',
   'insight':'empórios e lojas de produtos naturais recomprarem os itens sem glúten em um canal próprio, sem depender da próxima visita do representante',
 },
 'eduardo@belezadagente.com.br': {
   'slug':'beleza-da-gente-toctus-sp', 'mql': True,
   'empresa_real':'Beleza da Gente — loja virtual de cosméticos e produtos de beleza profissional em Campinas/SP, operada por Eduardo, também ligada à distribuição regional Toctus São Paulo e Grande ABC',
   'dominio_site':'belezadagente.com.br; domínio corporativo do e-mail e loja virtual própria de cosméticos profissionais',
   'redes':'Instagram @toctus_saopaulo; Facebook Toctus Vegano SP; LinkedIn Toctus Cosméticos',
   'segmento':'Cosméticos e beleza profissional — distribuição regional para salões e profissionais, combinada com e-commerce próprio',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: domínio do e-mail confirma loja virtual real de cosméticos profissionais em Campinas/SP, com telefone público compatível com o formulário. A empresa informada no formulário, Toctus São Paulo e Grande ABC, indica atuação como distribuição regional de cosméticos profissionais, com presença pública em Instagram/Facebook. O formulário reforça fit de canal digital: ERP Bling, loja virtual ativa, venda por visita/WhatsApp e faturamento de R$500 mil a R$1 milhão/ano. Qualificado por estrutura real, canal próprio e operação de distribuição/beleza profissional.',
   'insight':'separar os pedidos dos salões e da loja online em um fluxo mais organizado, com catálogo e condições certas para cada tipo de cliente',
 },
 'fgardin@rokane.com.br': {
   'slug':'rokane-international-business', 'mql': True,
   'empresa_real':'Rokane International Business Ltda — empresa brasileira de atacado/exportação com atuação em matérias-primas agrícolas, minérios e proteína animal',
   'dominio_site':'rokane.com.br; domínio corporativo do e-mail; presença pública em B2Brazil ligada à Rokane',
   'redes':'B2Brazil/hotsite Rokane; referência pública ao Fabricio Gardin da Rocha vinculada à empresa',
   'segmento':'Atacado e exportação de commodities e insumos B2B, com operação comercial de distribuição/exportação',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e ativa, com CNPJ público, domínio próprio e mais de 20 anos de operação. Fabricio Gardin da Rocha aparece publicamente vinculado à Rokane, confirmando o lead. O formulário informa venda no balcão, faturamento de R$500 mil a R$1 milhão/ano, 11 a 25 pessoas e sem loja virtual; a presença pública e o segmento de atacado/exportação tornam o lead aderente ao ICP de distribuição B2B.',
   'insight':'saber na hora o que está disponível para vender e fechar pedido no balcão sem deixar o cliente esperando',
 },
 'alan@grupack.com.br': {
   'slug':'rodelli-grupack-embalagens', 'mql': True,
   'empresa_real':'Rodelli Comércio de Embalagens Ltda / Grupack Embalagens e Produtos de Limpeza Ltda — comércio atacadista de embalagens em Marília/SP',
   'dominio_site':'grupack.com.br; domínio corporativo do e-mail; empresa confirmada em bases públicas pelo CNPJ 47.949.697/0001-05',
   'redes':'Instagram @rodelli.embalagens; cadastro público em Econodata/Serasa Experian com razão social e endereço em Marília/SP',
   'segmento':'Comércio atacadista/distribuição B2B de embalagens e produtos de limpeza',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e ativa, com CNPJ, endereço fixo em Marília/SP, domínio de e-mail grupack.com.br coerente com a razão social Grupack Embalagens e presença pública como Rodelli Embalagens. A atividade principal é comércio atacadista de embalagens, aderente ao ICP B2B/distribuição. O formulário HubSpot reforça a oportunidade: faturamento de R$1 a R$5 milhões/ano, venda hoje por WhatsApp, equipe enxuta e ainda sem loja virtual.',
   'insight':'organizar o mix de embalagens em um catálogo de pedido para clientes recorrentes fecharem compras sem depender de troca manual no WhatsApp',
 },
 'contato@mnaconnectconsultoria.com.br': {
   'slug':'mna-connect', 'mql': False,
   'empresa_real':'MNA Connect — não foi possível confirmar operação comercial pública ativa',
   'dominio_site':'mnaconnectconsultoria.com.br (inativo/retornando 404 na pesquisa do ciclo)',
   'redes':'Nenhuma rede social ou perfil público conclusivo localizado na pesquisa via Claude Code/WebSearch/WebFetch',
   'segmento':'Consultoria/empresa não identificada; sem evidência pública de atacado, distribuição, indústria ou canal digital próprio',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: domínio provável mnaconnectconsultoria.com.br sem site ativo (404), sem redes sociais, CNPJ ou pegada pública conclusiva de operação MNA Connect. O formulário informa ERP Outro, faturamento de R$500 mil a R$1 milhão, 11 a 25 pessoas, venda presencial balcão e sem loja virtual, mas não há evidência de atacado/distribuição/indústria nem canal digital próprio aderente ao ICP Zydon. Lead não qualificado como MQL neste momento.',
   'insight':'',
 },
 'alessandra@moveispontual.com.br': {
   'slug':'moveis-pontual', 'mql': True,
   'empresa_real':'Pontual Cadeiras / Móveis Pontual — fabricante de cadeiras de escritório em Americana-SP, com mais de 20 anos de mercado e venda online própria',
   'dominio_site':'moveispontual.com.br; pontualcadeiras.com.br; loja virtual própria e presença ativa no Mercado Livre',
   'redes':'Instagram @pontual.cadeiras; Facebook Pontual Cadeiras; TikTok @pontual.cadeiras',
   'segmento':'Indústria/fabricante de cadeiras e móveis para escritório, com linha corporativa/ergonômica, loja virtual própria e marketplace ativo',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e ativa em Americana/SP, fabricante de cadeiras de escritório há mais de 20 anos, com domínio próprio, loja virtual e presença forte no Mercado Livre. O formulário declara venda pelo Meli, loja virtual ativa, ERP Bling, 1 a 10 pessoas e faturamento até R$250 mil/ano. Mesmo com porte declarado pequeno, a evidência pública mostra estrutura de fabricante com canal digital próprio, aderente ao ICP de indústria com venda digital.',
   'insight':'trazer para o canal próprio parte dos clientes que hoje compram pelo Mercado Livre, aumentando a margem e facilitando recompras de cadeiras corporativas',
 },
 'contato@casadosfiltrosrj.com.br': {
   'slug':'casa-dos-filtros', 'mql': True,
   'empresa_real':'Casa dos Filtros (revenda autorizada Everest) — loja em Rio das Ostras/RJ com venda de purificadores de água, máquinas de gelo e filtros para uso residencial e comercial',
   'dominio_site':'casadosfiltrosrj.com.br; site próprio com catálogo/loja e presença pública ativa',
   'redes':'Instagram oficial https://www.instagram.com/casadosfiltrosrj/; Facebook https://www.facebook.com/casadosfiltrosrj/',
   'segmento':'Varejo especializado de purificadores de água, máquinas de gelo e filtros, com venda multicanal por WhatsApp, telefone, loja física, Mercado Livre e loja virtual',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e ativa, com domínio próprio, loja em Rio das Ostras/RJ e redes sociais operacionais. O formulário declara venda multicanal (WhatsApp, telefone, loja física e Mercado Livre), loja virtual ativa, ERP Olist/Tiny, 1 a 10 pessoas e faturamento até R$250 mil/ano. Embora seja varejo pequeno, já está marcado como MQL no HubSpot e tem canais digitais suficientes para justificar o diagnóstico.',
   'insight':'centralizar os pedidos do WhatsApp, Mercado Livre e loja física em um só fluxo para vender em todos os canais sem perder cliente nem deixar produto faltar',
 },
 'sandro@rjnatural.com.br': {
   'slug':'rj-natural', 'mql': True,
   'empresa_real':'RJ Natural Distribuidora de Produtos Naturais — distribuidora de produtos naturais no Rio de Janeiro',
   'dominio_site':'rjnatural.com.br; presença pública em diretórios locais e redes sociais',
   'redes':'Instagram https://www.instagram.com/rjnaturaldistribuidora/; Facebook https://www.facebook.com/rjnaturaldistribuidora/',
   'segmento':'Distribuição/atacado B2B de produtos naturais, orgânicos, sem glúten e sem lactose para lojistas e revendedores no Rio de Janeiro',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: distribuidora/atacado B2B real, com site próprio, presença em Vargem Pequena/RJ e perfil ativo @rjnaturaldistribuidora atendendo lojistas/revendedores. O formulário declara venda por equipe externa e faturamento de R$1 a R$5 milhões/ano, perfil aderente ao ICP prioritário de atacado/distribuição. Mesmo usando ERP Outro e sem loja virtual declarada, domínio, redes, porte e operação B2B justificam qualificação como MQL.',
   'insight':'equipar a equipe externa com um catálogo digital de pedidos para fechar venda na rua e agilizar a entrega ao lojista',
 },
 'zionsensors@gmail.com': {
   'slug':'casa-dos-filtros-rj', 'mql': True,
   'empresa_real':'Casa dos Filtros (Brasiltech Supply LTDA) — revenda autorizada Everest no RJ/ES, com loja física e venda online de purificadores, bebedouros e máquinas de gelo',
   'dominio_site':'casadosfiltrosrj.com.br; site próprio/loja virtual ativa com produtos, atendimento e presença multicanal',
   'redes':'Instagram oficial @casadosfiltrosrj e Facebook Casa dos Filtros RJ encontrados na pesquisa pública',
   'segmento':'Revenda de purificadores de água, bebedouros e máquinas de gelo — operação multicanal com WhatsApp, telefone, loja física, Mercado Livre e loja virtual',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real com domínio próprio, site/loja virtual ativa, redes sociais e presença multicanal. O formulário confirma Olist/Tiny, loja virtual, WhatsApp, telefone, loja física e Mercado Livre. Embora o porte seja pequeno e o faturamento informado seja até R$250 mil/ano, há estrutura digital real e múltiplos canais de pedido, qualificando como MQL de diagnóstico no limite inferior do ICP.',
   'insight':'centralizar os pedidos do site, WhatsApp, loja física e Mercado Livre em um fluxo mais organizado, sem perder venda entre canais',
 },
 'sandro@rjnatural.com.br': {
   'slug':'rj-natural-distribuidora', 'mql': True,
   'empresa_real':'RJ Natural Distribuidora de Produtos Naturais — distribuidora no Rio de Janeiro com foco em produtos naturais, orgânicos, sem glúten e sem lactose',
   'dominio_site':'rjnatural.com.br; site próprio da distribuidora com dados institucionais e endereço em Vargem Pequena/RJ',
   'redes':'Instagram @rjnaturaldistribuidora e Facebook RJ Natural Distribuidora encontrados na pesquisa pública',
   'segmento':'Distribuição B2B de produtos naturais, orgânicos, sem glúten e sem lactose, com venda por equipe externa',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e aderente ao ICP prioritário por ser distribuidora B2B, com domínio próprio, site, endereço físico e redes sociais. O formulário confirma faturamento de R$1 milhão a R$5 milhões/ano, venda por equipe externa e telefone móvel válido. Mesmo sem loja virtual, a natureza de distribuidora e o canal comercial externo tornam o lead MQL.',
   'insight':'os clientes recorrentes montarem pedidos de produtos naturais com mais autonomia, enquanto a equipe externa foca nas visitas que geram mais venda',
 },
 'zionsensors@gmail.com': {
   'slug':'zion-decoracao-3d', 'mql': True,
   'empresa_real':'Zion Decoração 3D / ZION INDUSTRIA E COMERCIO LTDA — loja online de móveis e decoração com venda direto de fábrica, CNPJ 55.954.099/0001-52, Itapoá/SC',
   'dominio_site':'lojazion.com.br; loja virtual própria em Loja Integrada com carrinho, categorias, pagamentos, frete e páginas institucionais',
   'redes':'Instagram oficial indicado no site: @lojazion2024; telefone/WhatsApp e e-mail batem com o HubSpot',
   'segmento':'Móveis e decoração — comércio/indústria com venda online direto de fábrica, catálogo de móveis, decoração, cama/mesa/banho, banheiro, cozinha e quarto',
   'motivo':'Pesquisa web real via WebSearch/WebFetch após falha de quota do Claude Code: o e-mail e telefone do HubSpot aparecem no site oficial lojazion.com.br e em cadastro público da ZION INDUSTRIA E COMERCIO LTDA. O site tem loja virtual ativa, carrinho, categorias de produtos, pagamento via Pix/cartão, frete nacional e narrativa de venda online direto de fábrica. Embora os campos do formulário tenham vindo vazios e o canal pareça majoritariamente B2C, há domínio/site próprio, CNPJ, operação de indústria/comércio e catálogo estruturado de móveis e decoração, suficiente para qualificar como MQL de diagnóstico no limite do ICP.',
   'insight':'organizar o catálogo de móveis e decoração em uma experiência de compra mais guiada, ajudando o cliente a fechar pedidos com menos conversas soltas no WhatsApp',
 },
 'dirceu.junior@wapssolutions.com.br': {
   'slug':'waps-solutions', 'mql': True,
   'empresa_real':'WAPS Solutions LTDA — empresa de Taboão da Serra/SP, ativa desde 2008, com comércio e serviços de informática, telecom e eletroeletrônicos para clientes corporativos',
   'dominio_site':'wapssolutions.com.br; loja virtual em wapssolutions.com.br/shop',
   'redes':'LinkedIn WAPS Solutions; Instagram @waps.solutions; CNPJ público 09.649.603/0001-93 em bases cadastrais',
   'segmento':'Comércio e serviços de informática, telecom e eletroeletrônicos — venda, locação, reparo/refurbish e terceirização BPO, atendendo empresas',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e ativa (CNPJ 09.649.603/0001-93, Taboão da Serra/SP, fundada em 2008, porte público 11-50 pessoas / cerca de 32 funcionários). Site próprio e loja virtual confirmam venda de equipamentos novos e seminovos, além de atendimento corporativo em locação, reparo/refurbish e BPO. Embora os campos do formulário tenham vindo vazios, a evidência pública confirma operação B2B estruturada e aderente ao ICP Zydon.',
   'insight':'estruturar um canal digital para empresas comprarem equipamentos novos e seminovos da WAPS com menos dependência de atendimento manual',
 },
 'psiupsiu@psiupsiu.com': {
   'slug':'maquiadora-commerce-psiu-psiu', 'mql': False,
   'empresa_real':'Psiu Psiu / Maquiadora Company Ltda — marca de maquiagem e cosméticos com lojas/quiosques em Aracaju/SE, Lagarto/SE e Salvador/BA',
   'dominio_site':'psiupsiu.com.br (domínio público citado; site indisponível/conexão recusada no ciclo)',
   'redes':'Instagram @psiumaquiadora (~38 mil seguidores), Facebook Psiu Psiu Maquiadora, presença em páginas de shoppings RioMar Aracaju e Shopping Jardins',
   'segmento':'Varejo B2C de cosméticos/maquiagem — rede de lojas e quiosques físicos de preço baixo, com expansão por afiliados/franqueados',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e consolidada (Psiu Psiu / Maquiadora Company Ltda, Aracaju/SE, desde 2008), com lojas e quiosques em shoppings e presença pública forte. Weslley Rezende aparece como sócio-administrador de empresas Maquiadora Afiliada, coerente com o lead. Porém o formulário informa venda presencial nas lojas, sem loja virtual, 1 a 10 pessoas, e a pesquisa não encontrou evidência de atacado/distribuição/indústria ou operação B2B/canal digital aderente ao ICP atual. Lead real, mas fora do recorte MQL Zydon neste momento.',
   'insight':'',
 },
 'cavallieri-exodo@vendasbrinquedos.com.br': {
   'slug':'vendasbrinquedos-cavallieri', 'mql': True,
   'empresa_real':'Marketing Brinquedos Educativos e Pedagógicos (vendasbrinquedos.com.br)',
   'dominio_site':'vendasbrinquedos.com.br (domínio corporativo do e-mail; site não respondeu/ECONNREFUSED na pesquisa do ciclo)',
   'redes':'Não foram encontradas redes sociais com vínculo conclusivo no ciclo',
   'segmento':'Comércio de brinquedos educativos e pedagógicos, com venda via WhatsApp e potencial atendimento a escolas, creches e revendedores',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: domínio próprio usado no e-mail corporativo confirma empresa real e o segmento de brinquedos educativos/pedagógicos tem potencial de venda recorrente para escolas, creches e revendas. O footprint público é fraco (site indisponível no momento e sem redes conclusivas) e o porte informado é pequeno, mas há telefone móvel válido, origem por formulário e dor clara de venda concentrada no WhatsApp, qualificando como MQL de entrada para diagnóstico.',
   'insight':'organizar os produtos em um catálogo próprio e transformar as conversas do WhatsApp em pedidos mais rápidos, sem anotar tudo à mão',
 },
 'usebotina@usebotina.com.br': {
   'slug':'usebotina', 'mql': True,
   'empresa_real':'Use Botina (Martins & Augusto Ltda)',
   'dominio_site':'usebotina.com.br; loja virtual ativa e área de lojista/revendedor',
   'redes':'Site próprio ativo; Instagram não confirmado com evidência conclusiva no ciclo',
   'segmento':'Calçados — fabricação/venda de botinas masculinas e femininas em couro, com canal próprio de e-commerce e área do lojista/revendedor B2B/atacado',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real com domínio e loja virtual ativos, vendendo botinas e com área do lojista/revendedor, o que caracteriza operação B2B/atacado além do varejo digital. O formulário informa loja virtual ativa e 11 a 25 pessoas; apesar de declarar ainda não faturar, há estrutura digital e canal de revenda aderentes ao ICP.',
   'insight':'centralizar pedidos de revenda e de clientes finais num só canal, respondendo mais rápido pelo WhatsApp sem perder venda',
 },
 'gustavo.martins@nf3d.com.br': {
   'slug':'martins-solucoes-comercio-nf3d', 'mql': True,
   'empresa_real':'Martins Soluções e Comércio Ltda. — empresa com domínio corporativo nf3d.com.br e telefone móvel válido no DDD 22',
   'dominio_site':'nf3d.com.br (domínio corporativo do e-mail; WebFetch não renderizou/timeout no ciclo)',
   'redes':'Não encontradas com evidência conclusiva no ciclo; domínio próprio e razão social LTDA foram os sinais públicos disponíveis',
   'segmento':'Comércio/distribuição B2B provável, com domínio próprio e operação a validar no diagnóstico comercial',
   'motivo':'Pesquisa via Claude Code/WebSearch: domínio corporativo próprio nf3d.com.br, razão social LTDA de comércio e telefone móvel válido (+55 22 99958-3187, DDD 22) indicam empresa real com estrutura mínima; o site não renderizou na consulta e não houve redes conclusivas, então o MQL é por estrutura/domínio e contato válido, com ressalva de footprint público fraco.',
   'insight':'apresentar seus produtos em um canal próprio e capturar pedidos de clientes sem depender de conversas soltas no WhatsApp',
 },
 'rafael.soligo@metodomoveis.com.br': {
   'slug':'metodo-moveis-de-aco', 'mql': True,
   'empresa_real':'Método Móveis — fabricante de móveis de aço e soluções corporativas em Mogi Mirim/SP',
   'dominio_site':'metodomoveis.com.br; loja virtual própria ativa; páginas institucionais e catálogo de produtos',
   'redes':'Reclame Aqui Método Móveis; presença pública vinculada ao domínio e canais de atendimento',
   'segmento':'Indústria/fabricante de móveis de aço, sistemas de armazenagem e mobiliário corporativo, com venda B2B e loja virtual',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: domínio do e-mail bate com fabricante real e ativo, site institucional com loja virtual, página Quem Somos informa operação desde 1987 e estrutura industrial em Mogi Mirim/SP, catálogo de móveis de aço e atendimento comercial. O formulário confirma B2B, R$10–50 milhões/ano, 51–150 pessoas, loja virtual ativa e telefone válido. Encaixe forte no ICP de indústria B2B com canal digital.',
   'insight':'clientes corporativos montarem cotações e recompras de móveis de aço em um canal próprio, sem depender de orçamento manual a cada pedido',
 },
 'renatomarquesdeoliveira734@gmail.com': {
   'slug':'renato-marques-de-oliveira', 'mql': False,
   'empresa_real':'Não identificável a partir do lead',
   'dominio_site':'Sem domínio corporativo; e-mail Gmail genérico',
   'redes':'Não encontradas com vínculo conclusivo para este lead',
   'segmento':'Indefinido / pessoa física ou cadastro incompleto',
   'motivo':'Pesquisa via Claude Code/WebSearch: e-mail gratuito com sufixo numérico, telefone inválido (apenas “55”, sem DDD/número), sem dados de formulário, sem domínio corporativo e sem vínculo confirmável com empresa específica. Há homônimos públicos, mas sem prova de relação com este cadastro. Não há base para qualificar como operação B2B.',
   'insight':'',
 },
 'contato@espiritodocha.com.br': {
   'slug':'espirito-do-cha', 'mql': True,
   'empresa_real':'Espírito do Chá Comércio de Produtos Alimentícios Ltda ME — marca de chás premium no RJ, com CNPJ público 38.468.661/0001-19, domínio próprio, e-commerce ativo e canal de revenda',
   'dominio_site':'espiritodocha.com.br; loja.espiritodocha.com.br; espiritodocha.com.br/segmento/revenda',
   'redes':'Facebook Espírito do Chá; loja virtual própria; site com segmento Revenda e venda a granel',
   'segmento':'Marca/indústria de alimentos — chás premium, infusões e blends, com venda direta, clientes fixos recorrentes e canal de revenda B2B',
   'motivo':'Empresa real confirmada por domínio próprio, e-commerce ativo, Facebook e página de Revenda/venda a granel. O telefone público confere com o HubSpot e o formulário informa clientes fixos que recompram pelo WhatsApp. Apesar do porte/faturamento ainda baixo, há operação digital real e recorrência B2B de revendedores, aderente ao ICP no limite inferior.',
   'insight':'reunir revendedores e clientes fixos em um catálogo próprio de recompra, reduzindo pedidos manuais no WhatsApp e abrindo espaço para vender mais linhas de chá',
 },
 'hidrauforca@hidrauforca.com.br': {
   'slug':'hidrauforca', 'mql': True,
   'empresa_real':'Hidrauforça (WD Indústria e Comércio de Equipamentos de Pintura) — fabricante de equipamentos para pintura industrial e sinalização viária, fundada em 1987, sediada em Engenheiro Coelho/SP',
   'dominio_site':'hidrauforca.com.br; hidrauforca.com.br/contato/; hidrauforca.com.br/categoria-produto/reposicao-de-pecas/sgk/',
   'redes':'Instagram @hidrauforca; Facebook Hidrauforca; presença em AECweb',
   'segmento':'Indústria — fabricação de equipamentos para pintura industrial (pistolas, tanques de pressão, agitadores pneumáticos) e sinalização/demarcação viária, com venda B2B e reposição de peças',
   'motivo':'Domínio próprio ativo com catálogo estruturado por categoria de produto e linha de reposição de peças; indústria/fabricante B2B atendendo clientes industriais e de infraestrutura, com canal digital já em uso (Google Ads gerando leads via WhatsApp). Faturamento na faixa de milhões e perfil de canal digital encaixam no ICP Zydon de indústria/distribuição B2B.',
   'insight':'transformar o catálogo de peças e equipamentos em pedidos B2B online, capturando os leads que hoje só chegam pelo WhatsApp',
 },
 'carol@hanpa.com.br': {
   'slug':'hanpa-solucoes-graficas', 'mql': True,
   'empresa_real':'HANPA Soluções Gráficas',
   'dominio_site':'hanpa.com.br; hanpa.com.br/sobre.html; hanpa.com.br/equipamentos.html',
   'redes':'Instagram @hanpa_bureau; Facebook Hanpa Bureau; LinkedIn Hanpa Bureau',
   'segmento':'Indústria gráfica B2B — impressão offset e digital, pré-impressão CTP e acabamento',
   'motivo':'Domínio próprio e site institucional ativos confirmam empresa real no ABC paulista, com páginas de serviços, equipamentos e contato. A operação tem cerca de 25 anos, certificações ISO 9001 e FSC e parque gráfico com Heidelberg Speedmaster, CTP Kodak e impressão digital Konica. Mesmo com porte declarado menor no formulário, é operação B2B industrial estruturada e compatível com o ICP Zydon.',
   'insight':'clientes recorrentes solicitarem orçamentos e aprovarem novos pedidos gráficos em um canal próprio, com menos idas e vindas no atendimento',
 },
 'f4b3033060c7d6138da89b909c50f185@pcm.com.br': {
   'slug':'nao-registrado-pcm', 'mql': False,
   'empresa_real':'Lead não identificável (domínio pcm.com.br sem comprovação de empresa específica)',
   'dominio_site':'pcm.com.br (site em manutenção/sob construção; domínio genérico para a sigla PCM)',
   'redes':'Não encontradas com evidência conclusiva para este lead',
   'segmento':'Não identificado',
   'motivo':'Lead não identificável: e-mail anonimizado/hash, nome "nao registrado", empresa vazia, sem telefone e sem respostas de formulário; origem integration. O domínio pcm.com.br não comprova estrutura nem operação B2B/canal digital do ICP.',
   'insight':'',
 },
 'loja@babyartetrico.com.br': {
   'slug':'baby-arte-trico', 'mql': True,
   'empresa_real':'Baby Arte Tricô',
   'dominio_site':'babyartetrico.com.br; babyartetrico.com.br/quem-somos/',
   'redes':'Instagram/TikTok/Pinterest/YouTube @babyartetrico; Facebook',
   'segmento':'Marca/loja online de roupas e enxoval de tricô artesanal para bebê, com fabricação própria e venda digital',
   'motivo':'Domínio próprio e operação real verificável: loja virtual ativa com catálogo, página institucional e presença em redes sociais. O formulário informa loja virtual ativa, venda via Shopee, ERP Bling e telefone válido. Embora seja operação de pequeno porte, há estrutura digital real e canal próprio, qualificando como MQL no limite inferior do ICP.',
   'insight':'concentrar os pedidos do site, da Shopee e das redes em um canal próprio, mantendo o cuidado artesanal como diferencial e reduzindo conversas manuais',
 },
 'cesar@coldsmoke.com.br': {
   'slug':'coldsmoke', 'mql': False,
   'empresa_real':'Coldsmoke Fabricação de Produtos de Carne Eireli — charcutaria artesanal de defumados, embutidos e curados em Vinhedo/SP',
   'dominio_site':'coldsmoke.com.br; páginas públicas de loja, food service e quem somos',
   'redes':'Site próprio Coldsmoke; presença pública de charcutaria premium',
   'segmento':'Fabricante artesanal premium de bacon, guanciale, copa, salame e curados, com e-commerce próprio e food service pontual',
   'motivo':'Pesquisa pública confirmou fabricante de marca própria artesanal premium vendendo direto ao consumidor pelo e-commerce e fechando por WhatsApp. Embora exista página de food service para restaurantes, não há evidência clara de distribuidor, atacado ou canal de revenda/lojistas para abastecimento recorrente de estoque. Pelo crivo acirrado, produção D2C/nicho com baixo SKU e sem revenda B2B clara fica fora do MQL.',
   'insight':'',
 },
 'gerencia.vendas@intimapassion.com.br': {
   'slug':'intima-passion', 'mql': True,
   'empresa_real':'Íntima Passion Lingerie (fabricante de moda íntima, Juruaia/MG)',
   'dominio_site':'intimapassion.com.br; loja.intimapassion.com.br; intimapassionlingerie.com.br',
   'redes':'Instagram oficial @intimapassionoficial; presença em portais de atacado/revenda',
   'segmento':'Indústria/confecção de moda íntima com operação B2B de atacado para lojistas e revendedores; linhas de lingerie, moda praia, loungewear e pijamas',
   'motivo':'Fabricante de moda íntima com operação B2B estruturada: domínio próprio, loja virtual de atacado, linha de produtos definida, mais de 18 anos de mercado e rede de lojistas/revendedores. Encaixa no ICP Zydon de indústria/atacado com estrutura, domínio e canal digital. O formulário informa WhatsApp como canal atual e loja virtual ativa; há divergência com o campo de faturamento "ainda não faturamos", mas a presença pública indica operação consolidada.',
   'insight':'os lojistas e revendedores recomprarem as linhas de lingerie em um canal próprio, com menos pedidos manuais pelo WhatsApp',
 },
 'comercial@studiocasadecor.com.br': {
   'slug':'studio-casa-decor', 'mql': True,
   'empresa_real':'Studio Casa Decor / Studio Casa Móveis',
   'dominio_site':'studiocasadecor.com.br (site próprio ativo; referência também em studiocasamoveis.com.br)',
   'redes':'Facebook Studio Casa Decor; Pinterest Studio Casa Decor; referência ABIMAD associada Studio Casa',
   'segmento':'Móveis planejados e decoração, com atendimento residencial e projetos comerciais; formulário declara venda B2B e B2C pelo WhatsApp',
   'motivo':'Empresa real validada por domínio próprio, presença pública e responsável identificável. O formulário declara venda B2B e B2C pelo WhatsApp, loja virtual ativa, ERP Bling e faturamento pós-receita. Apesar de porte pequeno, tem operação real e uso de ERP nativo, então entra como MQL.',
   'insight':'reunir os móveis e itens de decoração num catálogo digital onde o cliente comercial fecha o pedido sozinho, sem depender do WhatsApp',
 },
 'luiz@iinno-led.com': {
   'slug':'iinno-ltda', 'mql': True,
   'empresa_real':'Iinno Ltda / IINNO Lighting',
   'dominio_site':'iinno-led.com (domínio real; redireciona/relaciona com iinno-lighting.com)',
   'redes':'Facebook iinnolight; site público com linhas de produtos e clientes/parceiros',
   'segmento':'Iluminação LED comercial/industrial, fabricante/distribuidor com operação B2B para projetos, revendas e parceiros',
   'motivo':'Domínio real e presença pública de fabricante/distribuidor de iluminação LED comercial e industrial, com rede de parceiros e revendas. O formulário indica ERP Omie, faturamento R$1–5 milhões e venda por atendimento direto. Encaixe forte no ICP de indústria/distribuição B2B; MQL.',
   'insight':'deixar revendas e parceiros montando o pedido das luminárias num catálogo com preço próprio, em vez de tudo passar pelo atendimento direto',
 },
 'cavallieri-exodo@vendasbrinquedos.com.br': {
   'slug':'marketing-brinquedos-educativos', 'mql': False,
   'empresa_real':'Marketing Brinquedos Educativos e Pedagógicos (nome do formulário; presença pública/operacional não confirmada na pesquisa)',
   'dominio_site':'vendasbrinquedos.com.br (domínio do e-mail; pesquisa Claude Code/WebSearch indicou domínio sem site/loja ativa acessível)',
   'redes':'Nenhuma rede social ou presença pública vinculada localizada com evidência conclusiva',
   'segmento':'Revenda/varejo de brinquedos educativos e pedagógicos, microoperação',
   'motivo':'Pesquisa via Claude Code/WebSearch: embora tenha domínio próprio no e-mail e telefone móvel válido, o domínio não apresentou site/loja ativa, não foram encontradas redes ou presença operacional, e o formulário informa faturamento até R$250 mil/ano, 1 a 10 pessoas, venda apenas por WhatsApp e sem loja virtual. Sem estrutura digital nem operação B2B/atacado/distribuição comprovada, fica fora do ICP Zydon neste momento.',
   'insight':'',
 },
 'usebotina@usebotina.com.br': {
   'slug':'use-botina-martins-augusto', 'mql': True,
   'empresa_real':'Use Botina / Martins & Augusto Ltda — marca/fabricante de botinas de couro com venda direta de fábrica',
   'dominio_site':'usebotina.com.br (domínio e loja própria da marca; WebFetch teve bloqueio, mas WebSearch confirmou presença da marca)',
   'redes':'Presença online da marca confirmada em resultados públicos; Instagram específico não confirmado no ciclo',
   'segmento':'Indústria/marca de calçados — botinas de couro masculinas e femininas, com loja virtual própria',
   'motivo':'Pesquisa via Claude Code/WebSearch: marca real com domínio e loja virtual próprios, operação de botinas de couro/venda direta de fábrica e formulário com 11 a 25 pessoas e loja virtual ativa. Apesar de estar em fase inicial de faturamento, há estrutura digital e produto próprio, encaixando no ICP de indústria/marca com canal digital.',
   'insight':'transformar a loja própria em um canal mais forte para clientes comprarem e recomprar botinas de couro sem depender de atendimento manual',
 },
 'leandro@designemoveis.com.br': {
   'slug':'design-moveis-corporativo', 'mql': True,
   'empresa_real':'Design Móveis Corporativo (Macaé/RJ)',
   'dominio_site':'designemoveis.com.br (domínio do lead; no momento da pesquisa retornou conexão recusada)',
   'redes':'Facebook designmoveiscorporativo; diretórios locais Macaé.net.br e TodosNegócios; HubSpot declara venda pela Amazon e loja virtual ativa',
   'segmento':'Móveis corporativos e mobiliário para escritório, com atendimento a empresas e operação multicanal (loja física, marketplace e loja virtual)',
   'motivo':'Empresa real de móveis corporativos com presença pública em redes/diretórios, atuação B2B para escritórios/empresas, domínio próprio informado, loja virtual declarada no formulário, venda pela Amazon, ERP Bling e faturamento de R$1 a R$5 milhões/ano. Apesar de o site do domínio estar indisponível na consulta, o conjunto formulário + presença pública + canal digital indica MQL compatível com ICP Zydon.',
   'insight':'as empresas que já compram móveis corporativos fecharem o pedido inteiro em um canal próprio, sem depender da vitrine da Amazon nem de orçamento manual no balcão',
 },
 'luis@armazemsaovito.com.br': {
   'slug':'armazem-sao-vito', 'mql': True,
   'empresa_real':'Armazém São Vito',
   'dominio_site':'saovito.com (e-commerce próprio) / armazemsaovito.com.br (domínio do e-mail do lead)',
   'redes':'Instagram @armazemsaovito (~181 mil seguidores); Facebook Armazém São Vito; LinkedIn Armazém São Vito',
   'segmento':'Atacado e varejo de produtos naturais, orgânicos, suplementos e alimentos sem glúten/lactose, com B2B e B2C na Zona Cerealista de São Paulo',
   'motivo':'ICP forte: atacadista/distribuidor B2B com estrutura real, e-commerce próprio, 3 lojas físicas, mais de 3000 itens, venda atacado para todo o Brasil, mais de 151 pessoas e equipe de vendas interna e externa. Domínio próprio e presença digital robusta confirmam operação consolidada.',
   'insight':'clientes de atacado recomprarem os mais de 3000 itens de produtos naturais em um canal próprio, sem depender sempre da equipe interna e externa',
 },
 'adm@aglc.com.br': {
   'slug':'alc-aglc-com-br', 'mql': False,
   'empresa_real':'Indeterminada — domínio aglc.com.br sem site ativo e sem presença web rastreável; homônimos encontrados não confirmam correspondência com este lead',
   'dominio_site':'aglc.com.br (sem site ativo/conexão recusada na pesquisa)',
   'redes':'Nenhuma rede social identificada para este lead específico',
   'segmento':'Não confirmado; perfil de microempresa/revenda, ERP Tiny/Olist, sem loja virtual declarada',
   'motivo':'Fora do ICP de atacado/distribuidor/indústria B2B: faturamento até R$250 mil/ano, 1 a 10 pessoas, sem loja virtual, domínio sem site ativo e operação B2B não comprovada. O ERP Olist/Tiny ajuda, mas não compensa a ausência de porte, estrutura digital e evidência pública de operação B2B.',
   'insight':'centralizar pedidos e atendimento em um canal próprio para reduzir conversas manuais',
 },
 'gustavo.martins@nf3d.com.br': {
   'slug':'luiz-gustavo-martins-solucoes-comercio', 'mql': False,
   'empresa_real':'Indeterminada — Martins Soluções e Comércio Ltda.; domínio nf3d.com.br não acessível na pesquisa pública',
   'dominio_site':'nf3d.com.br (timeout/não acessível nas tentativas de WebFetch/WebSearch)',
   'redes':'Nenhuma presença social atribuível encontrada',
   'segmento':'Não identificado; formulário sem ERP, faturamento, porte, loja virtual ou canal B2B declarado',
   'motivo':'Possui e-mail com domínio próprio, mas o site nf3d.com.br não carregou, não houve redes/presença pública verificável e o formulário não declarou operação B2B, porte, faturamento ou canal digital. Sem evidência suficiente de atacado, distribuição, indústria ou operação digital compatível com o ICP Zydon.',
   'insight':'centralizar pedidos e estoque em um canal próprio para vender mais rápido e com menos retrabalho manual',
 },
 'rafael.soligo@metodomoveis.com.br': {
   'slug':'rafael-soligo-metodo-moveis', 'mql': True,
   'empresa_real':'Método Móveis e Sistemas de Armazenagem — fabricante de móveis de aço e sistemas de armazenagem em Mogi-Mirim/SP',
   'dominio_site':'metodomoveis.com.br; metodomoveis.com.br/quemsomos',
   'redes':'Instagram @metodo.moveisarmazenagem; Facebook /MetodoMoveis; LinkedIn Método Móveis e Sistemas de Armazenagem',
   'segmento':'Indústria/fabricante B2B de móveis de aço e sistemas de armazenagem (estantes, pallet racks, roupeiros e mezaninos), com loja virtual e venda para empresas/lojistas',
   'motivo':'Empresa real e estabelecida, com site, loja virtual e redes ativas. Fabricante industrial com venda B2B declarada no formulário, ERP TOTVS, faturamento de R$10 a R$50 milhões/ano, 51 a 150 pessoas e loja virtual ativa. Encaixe forte no ICP Zydon de indústria B2B com operação digital.',
   'insight':'lojistas e empresas comprarem móveis de aço e estruturas de armazenagem sozinhos a qualquer hora, sem depender do vendedor para fechar pedido',
 },
 'renatomarquesdeoliveira734@gmail.com': {
   'slug':'renato-marques-de-oliveira', 'mql': False,
   'empresa_real':'Não identificada — nome da empresa igual ao nome da pessoa e e-mail Gmail pessoal',
   'dominio_site':'Nenhum domínio próprio; e-mail Gmail pessoal',
   'redes':'Nenhuma presença atribuível com confiança; homônimos não vinculados ao lead',
   'segmento':'Não identificado',
   'motivo':'Lead sem empresa verificável, sem domínio próprio, sem respostas de formulário e telefone incompleto apenas como "55". Não há evidência pública confiável de operação B2B, atacado, distribuidor, indústria ou canal digital. Dados insuficientes para qualificar.',
   'insight':'qualificar a empresa e o canal de venda antes de qualquer abordagem comercial',
 },
 'ed@botpag.com.br': {
   'slug':'botpag', 'mql': False,
   'empresa_real':'BotPag — BOT PAG MEIOS DE PAGAMENTOS E SERVIÇOS LTDA, fintech de meios de pagamento e serviços digitais',
   'dominio_site':'botpag.com.br ativo; também botpag.com; subdomínios operacionais de parcelamento/recibo',
   'redes':'Facebook, LinkedIn, YouTube, TikTok, Medium e Reclame Aqui verificado; presença comercial nacional',
   'segmento':'Fintech / meios de pagamento e serviços financeiros digitais para IPVA, multas, licenciamento, crédito, seguros, guias fiscais e APIs de pagamento',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: BotPag é fintech de meios de pagamento/serviços financeiros, não atacado, distribuidor, indústria nem comércio B2B de produtos físicos com necessidade de catálogo/canal digital Zydon. Há divergência entre formulário pequeno (1 a 10 pessoas, R$250 mil a R$500 mil/ano, loja virtual) e empresa pública de pagamentos com presença nacional, então fica fora do ICP de prospecção inbound.',
   'insight':'',
 },
 'rodolfomarques@iacrono.com.br': {
   'slug':'rodolfo-marques-ia-crono', 'mql': True,
   'empresa_real':'IA Crono Cosméticos — marca própria de cosméticos com loja oficial, linha profissional/home care e programa de distribuidores',
   'dominio_site':'iacrono.com.br; loja virtual oficial com carrinho, cálculo de frete e pagamento online; programa Seja Um Distribuidor',
   'redes':'Facebook Iacrono Cosméticos; WhatsApp público +55 19 99153-9533',
   'segmento':'Indústria/marca própria de cosméticos (skincare e haircare) com venda direta e canal B2B de distribuição',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: domínio próprio iacrono.com.br confirma empresa real; o site é a loja oficial da IA Crono Cosméticos, com linha home care, linha profissional e fármacos, e-commerce completo e programa explícito Seja Um Distribuidor, evidenciando canal B2B/atacado além do varejo direto. O e-mail é corporativo no domínio da empresa e o formulário confirma loja virtual ativa, venda atual por WhatsApp, ERP Olist/Tiny, faturamento R$250 mil a R$500 mil/ano e 1 a 10 pessoas. É marca/indústria com canal digital estruturado e potencial de escala em distribuição, aderente ao ICP Zydon.',
   'insight':'distribuidores e clientes recorrentes fazerem pedidos da linha de cosméticos em um canal próprio, sem depender de conversas soltas no WhatsApp',
 },
 'lucia.dafunails@dafu.com.br': {
   'slug':'lu-paes-dafu', 'mql': True,
   'empresa_real':'DAFU / DAFU Nails — importadora, atacadista e marca de produtos de beleza, unhas, cílios, maquiagem e acessórios',
   'dominio_site':'dafu.com.br; dafuatacado.com.br com canal de atacado e pedido mínimo',
   'redes':'Instagram @dafu.com.br; presença pública Dafu Nails/Beauty Fair e rede de revendedores',
   'segmento':'Importadora/atacadista de beleza com forte canal B2B, venda física e atacado online',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: há divergência no formulário, que trouxe empresa como Claro Brasil, mas o e-mail lucia.dafunails@dafu.com.br e o domínio corporativo ligam a lead à DAFU/DAFU Nails. O site dafu.com.br e o atacado dafuatacado.com.br confirmam operação real de importação/atacado de beleza, com lojas físicas em São Paulo, canal B2B, pedido mínimo e marca distribuída em revendedores. O formulário informa faturamento R$500 mil a R$1 milhão/ano, 51 a 150 pessoas e venda por WhatsApp, coerente com operação comercial estruturada. Domínio, canal atacado e porte tornam o lead MQL forte apesar do ruído no campo empresa.',
   'insight':'lojistas e revendedores montarem pedidos de beleza no atacado com mais autonomia, reduzindo cotações manuais pelo WhatsApp',
 },
 'bivarneto@hiperstok.com.br': {
   'slug':'hiper-stok', 'mql': True,
   'empresa_real':'Hiper Stok Atacado e Varejo de Móveis Ltda (CNPJ 38.181.758/0001-46)',
   'dominio_site':'hiperstok.com.br; hiper-stok.lojaintegrada.com.br aparece indisponível/bloqueada; domínio corporativo confirmado pelo e-mail do lead',
   'redes':'Instagram @hiper_stok; LinkedIn Hiper Stok Atacado; presença pública em Econodata, Casa dos Dados e Serasa',
   'segmento':'Atacado e varejo de móveis e colchões — distribuidor B2B com base em São Paulo/SP, atendendo lojistas e revendedores em SP capital, Grande SP e interior',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e ativa, confirmada pelo site oficial hiperstok.com.br, Instagram, LinkedIn e cadastros públicos. Encaixa no ICP prioritário da Zydon por ser atacadista/distribuidora de móveis e colchões para lojistas e revendedores. O formulário reforça o fit: faturamento de R$10 a R$50 milhões/ano, 21 a 100 pessoas, venda hoje presencial com entrega logística, ERP Outro e sem loja virtual. A loja antiga na Loja Integrada aparece indisponível, indicando espaço claro para canal digital de pedidos B2B próprio.',
   'insight':'abrir um canal digital onde os lojistas façam os próprios pedidos a qualquer hora, liberando os vendedores para focar em quem compra mais',
 },
 'joelcastro@viperacessorios.com.br': {
   'slug':'viper-acessorios', 'mql': True,
   'empresa_real':'Viper Acessórios, Importação e Comércio Ltda — Bauru/SP, loja especializada em acessórios para card games/TCG',
   'dominio_site':'viperacessorios.com.br; site próprio ativo com loja virtual, páginas Quem Somos e Contato',
   'redes':'Instagram @viperacessorios; presença pública vinculada ao domínio oficial',
   'segmento':'E-commerce especializado em acessórios para card games/TCG, com sleeves, deckboxes, playmats, pastas, dados e top loaders; venda direta pelo site e pré-venda para clientes maiores',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e ativa em Bauru/SP, com domínio próprio viperacessorios.com.br, loja virtual operante, páginas institucionais e Instagram @viperacessorios. O formulário confirma ERP Bling, faturamento de R$1 milhão a R$5 milhões/ano, 1 a 10 pessoas, loja virtual ativa e venda por pré-venda para clientes maiores mais site. Apesar de ser um nicho especializado, há operação digital própria, recorrência em lançamentos e clientes maiores, tornando o lead MQL para diagnóstico Zydon.',
   'insight':'organizar as pré-vendas dos clientes maiores e os pedidos do site em um fluxo único, sem deixar pedido escapar nos lançamentos de cartas',
 },
 'diretoria2@grupomaranno.com.br': {
   'slug':'grupo-maranno', 'mql': True,
   'empresa_real':'Maranno / Grupo Maranno — marca premium de enxovais de cama, mesa, banho e decoração, com produção própria, lojas físicas em shoppings no Nordeste e loja virtual de alcance nacional',
   'dominio_site':'maranno.com.br; domínio corporativo do grupo no e-mail do lead; loja virtual própria ativa',
   'redes':'Instagram @marannohome e @marannoriomarrecife localizados na pesquisa pública via Claude Code/WebSearch/WebFetch',
   'segmento':'Varejo e marca de enxovais e decoração premium, com fabricação/curadoria própria, múltiplas lojas físicas, e-commerce nacional, vendedores internos e representantes',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: domínio do formulário e dados públicos apontam para a operação Maranno/Grupo Maranno, marca real e consolidada de enxovais premium com site próprio, e-commerce, lojas em shoppings e presença no Instagram. O formulário confirma ERP Bling, faturamento de R$1 milhão a R$5 milhões/ano, 21 a 100 pessoas, loja virtual ativa e venda por vendedor interno e representante. A combinação de estrutura pública, canal digital próprio, lojas físicas e representantes caracteriza operação multicanal com volume e fit para diagnóstico Zydon.',
   'insight':'alinhar preço, estoque e pedidos entre lojas de shopping, e-commerce nacional e representantes para vender mais sem perder margem',
 },
 'vendasonline@renovasaudenutricao.com.br': {
   'slug':'renova-saude-nutricao', 'mql': True,
   'empresa_real':'Renova Saúde e Nutrição — comércio de suplementos, vitaminas e nutrição clínica no Rio de Janeiro, com e-commerce, loja física em Botafogo e canal B2B para distribuidores e prefeituras',
   'dominio_site':'renovasaudenutricao.com.br; site próprio ativo com loja virtual, páginas institucionais, loja física e página para fornecedores/prefeituras/distribuidores',
   'redes':'Instagram @renovasaudenutricao; Facebook Renova Saúde Nutrição; telefone e WhatsApp públicos coerentes com o formulário',
   'segmento':'Comércio de suplementos, vitaminas e nutrição clínica especializada, com e-commerce, delivery, loja física e braço B2B para distribuidores e prefeituras',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e ativa, com site próprio e loja virtual de suplementos, vitaminas e nutrição clínica. Tem loja física em Botafogo/RJ, entrega rápida no Rio e página dedicada a fornecedores para prefeituras e distribuidores, com desconto por volume, apoio em licitações e logística nacional. O formulário confirma loja virtual ativa, venda por delivery/WhatsApp, ERP Bling, telefone móvel válido e porte pequeno. Apesar do faturamento menor, o canal digital real e a frente B2B/atacado sustentam a qualificação.',
   'insight':'atender os pedidos online do Rio e as compras de distribuidores e prefeituras em um fluxo mais organizado, sem perder pedido no caminho',
 },
 'info@54wines.com': {
   'slug':'54wines', 'mql': True,
   'empresa_real':'54wines — importadora e distribuidora de vinhos e espumantes em Camboriú/SC',
   'dominio_site':'54wines.com.br; site próprio ativo, venda B2B para lojas, distribuidores e restaurantes com CNPJ; o domínio .com do e-mail parece divergente do site público .com.br',
   'redes':'Instagram @54wines; Facebook 54wines; telefone público (47) 99668-5400 confere com o formulário',
   'segmento':'Importação e distribuição B2B/atacado de vinhos e espumantes, com venda por representantes para lojistas, distribuidores e restaurantes',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e ativa, com site próprio, Instagram e Facebook. A operação se posiciona como importadora/distribuidora de vinhos e vende somente para lojas, distribuidores e restaurantes com CNPJ, aderente ao perfil prioritário de atacado/distribuição B2B. O telefone do formulário confere com o site. O formulário informa venda por representante, sem loja virtual, ERP Outro, porte pequeno e faturamento menor; ainda assim o modelo B2B de distribuição justifica MQL e mostra oportunidade clara de canal digital de pedidos.',
   'insight':'lojistas e restaurantes fazerem pedidos de reposição de vinhos em um canal próprio, sem depender sempre do representante',
 },
 'oswaldo.ferreira@tes.com.br': {
   'slug':'tes-tecnologia', 'mql': True,
   'empresa_real':'TES Tecnologia — empresa brasileira de soluções audiovisuais e educacionais, fundada em 1990, com atuação B2B para revendedores, representantes e setor público',
   'dominio_site':'tes.com.br; loja.tes.com.br; site e loja virtual oficiais ativos',
   'redes':'LinkedIn TES Tecnologia; Facebook TES Tecnologia; loja oficial loja.tes.com.br',
   'segmento':'Indústria/distribuição B2B de soluções audiovisuais e educacionais, como projetores, telas interativas e lousas digitais, com venda para órgãos públicos via pregão eletrônico e rede de revendedores',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e ativa, fundada em 1990, com site próprio, loja virtual, LinkedIn e Facebook. Atua como fabricante/distribuidora B2B de soluções audiovisuais e educacionais, com rede de representantes/revendedores e vendas para setor público por pregão eletrônico. O formulário confirma faturamento de R$10 a R$50 milhões/ano, 21 a 100 pessoas, ERP Omie e venda hoje por pregão eletrônico. Encaixe forte no ICP Zydon por porte, estrutura, operação B2B e oportunidade de canal digital próprio.',
   'insight':'revendedores e compradores públicos consultarem produtos e avançarem pedidos com mais autonomia, reduzindo retrabalho em cotações e propostas',
 },
 'vendas@idealferragens.com.br': {
   'slug':'ideal-ferragens-casa-do-puxador', 'mql': True,
   'empresa_real':'Nova Ideal Ferragens Ind Com Ltda — fabricante de ferragens em inox que opera a marca A Casa do Puxador como braço de venda online',
   'dominio_site':'idealferragens.com.br; casadopuxador.com.br; loja Shopee /casadopuxador',
   'redes':'Instagram @ideal_ferr_; Facebook Ideal Ferragens; loja Shopee A Casa do Puxador localizada na pesquisa pública',
   'segmento':'Indústria/fabricante de puxadores e acessórios em aço inox, com operação multicanal: atende lojas de ferragens e distribuidores e também vende direto ao consumidor pela Shopee e loja virtual',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: a empresa real é fabricante de ferragens em inox em São Paulo, com site próprio e presença pública ligada à marca A Casa do Puxador. Não parece varejo puro: o site informa atendimento a lojistas/distribuidores e o formulário confirma loja virtual, ERP Bling, equipe de 11 a 25 pessoas e venda hoje concentrada na Shopee. Qualificado por indústria com canal digital ativo e oportunidade clara de separar revenda/lojista de consumidor final.',
   'insight':'identificar quando pedidos da Shopee são de lojistas com potencial de recompra e puxar esses clientes para um canal próprio, com preço e atendimento de revenda',
 },
 'guilherme.ribeiro@jcdecaux.com': {
   'slug':'jcdecaux', 'mql': False,
   'empresa_real':'JCDecaux Brasil — operação de mídia exterior/OOH e DOOH, parte de grupo global presente no Brasil',
   'dominio_site':'jcdecaux.com.br; site institucional ativo da JCDecaux Brasil',
   'redes':'Presença institucional em LinkedIn, Instagram e Facebook da marca JCDecaux; site público confirma mídia exterior/OOH',
   'segmento':'Mídia exterior / publicidade Out-of-Home, venda de espaços e projetos de comunicação para anunciantes e agências',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real e robusta, mas o segmento é publicidade/mídia exterior, fora do ICP prioritário da Zydon (atacado, distribuição ou indústria com venda B2B de produtos). O formulário informa faturamento de R$250 mil a R$500 mil/ano, 1 a 10 pessoas e venda por PAP/WhatsApp, dados incompatíveis com o porte público da multinacional, sugerindo cadastro desalinhado ou pessoal. Não qualificado para diagnóstico comercial neste ciclo.',
   'insight':'juntar os leads que chegam por PAP e WhatsApp em um funil só e descobrir mais cedo quem ficou sem resposta',
 },
 'geraldo@surgic.com.br': {
   'slug':'surgic', 'mql': True,
   'empresa_real':'Surgic Distribuidora e Importadora de OPME e Medicamentos Ltda — distribuidora/importadora médico-hospitalar ativa em Volta Redonda/RJ',
   'dominio_site':'surgic.com.br; site próprio ativo e CNPJ público 33.498.926/0001-08',
   'redes':'Site próprio ativo; redes sociais oficiais não ficaram conclusivas na pesquisa pública do ciclo',
   'segmento':'Distribuição/importação B2B de materiais cirúrgicos, OPME, insumos, implantes e medicamentos para clínicas e hospitais',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: encaixe forte no ICP por ser distribuidor/importador B2B de insumos médico-hospitalares, com domínio próprio, site real e CNPJ ativo. O formulário reforça a aderência: ERP Bling, faturamento de R$1 a R$5 milhões/ano, venda hoje visitando clientes e ausência de loja virtual. A oportunidade é digitalizar pedidos recorrentes e cotações que hoje dependem da visita e do WhatsApp.',
   'insight':'atender clínica e hospital sem nenhum pedido de OPME se perder entre a visita do vendedor e a conversa solta no WhatsApp',
 },
 'contato@bhturbinas.com.br': {
   'slug':'bht-turbinas-e-bombas', 'mql': True,
   'empresa_real':'Belo Horizonte Comércio de Turbinas e Bombas Ltda — BHT Turbinas e Bombas, revenda e reparação de turbocompressores e bombas em Belo Horizonte/MG',
   'dominio_site':'bhturbinas.com.br; site próprio ativo e CNPJ público 06.156.363/0001-05',
   'redes':'Facebook BHT Turbinas ativo; site próprio e presença pública em bases cadastrais/Reclame Aqui',
   'segmento':'Autopeças diesel / revenda e reparação de turbocompressores e bombas, com atendimento B2B para oficinas, frotistas e caminhoneiros',
   'motivo':'Pesquisa via Claude Code/WebSearch/WebFetch: empresa real com domínio próprio, site, Facebook e CNPJ ativo desde 2004. Atua em autopeças/turbinas e bombas, segmento aderente por revenda técnica B2B com recorrência de cotação e urgência. O formulário confirma venda por loja física, telefone e WhatsApp, faturamento de R$500 mil a R$1 milhão/ano e ausência de loja virtual, indicando oportunidade de centralizar cotações e pedidos.',
   'insight':'responder cada cotação de turbo na hora, antes do caminhoneiro desligar e ligar para o concorrente',
 },
 'claudioigino@norimport.com.br': {
   'slug':'norimport', 'mql': True,
   'empresa_real':'Nor-Import Comercial de Alimentos Ltda — importadora e distribuidora atacadista de alimentos e bebidas premium em São Paulo/SP',
   'dominio_site':'norimport.com.br; site institucional próprio da Nor-Import',
   'redes':'Instagram @nor_import; Facebook Nor Importadora; LinkedIn da empresa e do contato Claudio Igino como gerente de vendas',
   'segmento':'Importadora e distribuidora atacadista de alimentos e bebidas premium para restaurantes, revendedores e clientes B2B',
   'motivo':'Empresa real confirmada por domínio próprio, CNPJ público, presença social e vínculo público do Claudio Igino como gerente de vendas. Atua com portfólio importado de alimentos e bebidas para restaurantes e revendedores, com entrega nacional e operação atacadista. Mesmo sem formulário completo, o segmento e o cargo do contato indicam fit forte com venda B2B recorrente.',
   'insight':'clientes B2B recomprarem alimentos e bebidas importadas em um canal próprio, com menos atrito para consultar portfólio e fechar pedidos recorrentes',
 },
 'dreambmx@dreambmx.com.br': {
   'slug':'dream-bmx', 'mql': True,
   'empresa_real':'Dream BMX — importadora e distribuidora de BMX freestyle em São Paulo/SP, ativa desde 2007',
   'dominio_site':'dreambmx.com.br; dreambmxdistro.com.br para lojistas e revendedores',
   'redes':'Instagram @dreambmx; Facebook Dream BMX; YouTube The Dream BMX',
   'segmento':'Importação e distribuição de bicicletas, peças, proteção e acessórios de BMX para varejo e lojistas/revendedores',
   'motivo':'Empresa real com domínio próprio, loja física, e-commerce e portal separado para revenda. O próprio site convida lojistas a solicitarem acesso ao canal de distribuidor, confirmando venda B2B além do varejo. O formulário reforça operação digital ativa, faturamento de R$500 mil a R$1 milhão/ano e loja virtual.',
   'insight':'unificar o varejo e os pedidos de lojistas em um fluxo mais claro, para revendedores comprarem peças de BMX com mais autonomia e menos troca manual de mensagens',
 },
 'andre@andrelavor.com': {
   'slug':'moinho-centro-norte', 'mql': True,
   'empresa_real':'Moinho Centro Norte — indústria de moagem de trigo em Goiânia/GO, com atuação regional e atendimento a padarias e indústrias de panificação',
   'dominio_site':'moinhocentronorte.com; site oficial com WhatsApp comercial público',
   'redes':'Instagram @moinhocentronorte; Facebook Moinho Centro Norte; LinkedIn Moinho Centro Norte',
   'segmento':'Indústria de alimentos / moinho de trigo, com venda atacadista de farinha para padarias, fábricas de alimentos e clientes B2B',
   'motivo':'Empresa real confirmada por site oficial, CNPJ público, redes sociais e vínculo do André Lavor Pagels Barbosa como liderança da companhia. O formulário indica ERP Omie, faturamento de R$50 a R$500 milhões/ano, venda por visita e ausência de loja virtual, o que mostra indústria B2B relevante com oportunidade clara de digitalizar pedidos recorrentes de padarias e indústrias.',
   'insight':'padarias e indústrias de panificação repetirem pedidos de farinha em um canal próprio, sem depender apenas da próxima visita comercial',
 },
 'leonardo@sucessonaweb.com.br': {
   'slug':'grupo-snw', 'mql': False,
   'empresa_real':'Grupo SNW / Sucesso na Web',
   'dominio_site':'gruposnw.com.br; domínio corporativo ligado ao grupo Sucesso na Web',
   'redes':'LinkedIn Grupo SNW; Instagram @gruposnw e @snwsol localizados na pesquisa pública',
   'segmento':'Agência de marketing/comunicação e tecnologia para o setor solar fotovoltaico, incluindo serviços digitais e plataforma SaaS',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: a empresa é de serviços de marketing, comunicação e tecnologia para o setor solar, não indústria, distribuidor, importador ou atacadista vendendo produtos para revendas/lojistas com abastecimento de estoque. O formulário informa fase sem faturamento e operação enxuta. Pelo crivo acirrado, e-commerce/plataforma não substitui ICP T1 B2B de catálogo e pedido recorrente de estoque.',
   'insight':'',
 },
 'industrial@artetilica.com.br': {
   'slug':'artetilica',
   'mql': True,
   'empresa_real':'Artetílica Indústria Metalúrgica Ltda — fabricante de luminárias e perfis LED em Bento Gonçalves/RS',
   'dominio_site':'artetilica.com.br; site próprio com catálogo institucional e linhas de produtos de iluminação',
   'redes':'Facebook Artetílica Oficial; LinkedIn Artetílica Indústria Metalúrgica localizados na pesquisa pública',
   'segmento':'Indústria metalúrgica/fabricante de luminárias, perfis LED e soluções de iluminação para mobiliário, marcenarias, indústria moveleira e lojas de iluminação',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: domínio próprio e fontes públicas confirmam indústria metalúrgica ativa em Bento Gonçalves, no polo moveleiro, com catálogo de luminárias e perfis LED. O formulário reforça fit forte: faturamento de R$5 a R$10 milhões/ano, 21 a 100 pessoas, loja virtual ativa e pedidos por WhatsApp/e-mail. Qualificado por indústria B2B com venda recorrente para marcenarias, indústria moveleira, revendas/lojas de iluminação e oportunidade clara de digitalizar catálogo, preço e pedidos.',
   'insight':'marcenarias e lojas de iluminação consultarem linhas de luminárias e perfis LED em um catálogo próprio, fechando pedidos recorrentes sem depender do vai-e-volta por WhatsApp e e-mail',
 },
 'contato@porummundomelhor.net': {
   'slug':'por-um-mundo-melhor',
   'mql': False,
   'empresa_real':'Por um Mundo Melhor — distribuidora de alimentos B2B em São Paulo/SP; empresa declarada no formulário como Assembleia Legislativa de São Paulo não foi considerada confiável',
   'dominio_site':'porummundomelhor.net; site próprio de distribuidora de alimentos B2B em SP com carnes, hortifruti e frios, pedido mínimo e retirada/entrega na Grande SP',
   'redes':'Presença pública confirmada limitada ao próprio site; homônimos em redes sociais não foram atribuídos ao lead',
   'segmento':'Distribuidora/atacado de alimentos para food service — restaurantes e padarias que consomem/transformam insumos, não revenda/lojistas de estoque',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: o e-mail aponta para porummundomelhor.net, uma distribuidora de alimentos B2B em SP, mas a empresa informada no formulário (Assembleia Legislativa de São Paulo) é inconsistente. O site mostra venda de carnes, hortifruti e frios para restaurantes e padarias, pedido mínimo e caixas fechadas. Pelo crivo acirrado, apesar de ser distribuidora, a base evidenciada é food service que consome/transforma insumos, não revendas/lojistas/clientes de abastecimento de estoque para revenda; além disso o lead é pequeno, sem loja virtual e com baixa qualidade cadastral. Não qualificado neste ciclo.',
   'insight':'',
 },
 'compras@mcacomercial.com.br': {
   'slug':'mca-comercial',
   'mql': False,
   'empresa_real':'MCA Comercial — Equipamentos de Segurança (EPI)',
   'dominio_site':'mcacomercial.com.br; site próprio de comércio de EPIs, ferramentas e sinalização para segurança do trabalho',
   'redes':'Instagram @mcacomercialepi; Facebook público associado a Rogerio/EPI localizado na pesquisa',
   'segmento':'Comércio de EPIs, ferramentas e itens de segurança do trabalho para pequenas e médias empresas compradoras',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: o domínio mcacomercial.com.br identifica a MCA Comercial como comércio de EPIs, ferramentas e sinalização. O site indica atendimento a pequenas e médias empresas e menciona linha de atacado, mas a evidência pública aponta principalmente venda para empresas que compram EPI para uso próprio dos colaboradores, não venda clara para revendas/lojistas que recompram para abastecimento de estoque. O formulário reforça operação pequena: faturamento de R$250 mil a R$500 mil ao ano, equipe de 1 a 10, venda por WhatsApp, sem loja virtual e ERP Outro. Pelo crivo MQL acirrado/fail-closed, não há evidência clara de ICP T1 de indústria/distribuidor/importador/atacado com canal de revenda e alto giro recorrente.',
   'insight':'',
 },
 'maycon@pr1medistribuidora.com.br': {
   'slug':'prime-distribuidora',
   'mql': True,
   'empresa_real':'Prime Distribuidora de Suplementos',
   'dominio_site':'pr1medistribuidora.com.br; site próprio da distribuidora, com página institucional de atacado e loja virtual',
   'redes':'Instagram @distribuidoraprimeoficial localizado na pesquisa pública',
   'segmento':'Distribuidora de suplementos alimentares e alimentos, com venda no atacado para academias, mercados e lojas especializadas',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo confirmou identidade pelo telefone do site (35) 99959-1314 igual ao telefone do lead (35999591314) e domínio igual ao e-mail. A página institucional declara atuação em atacado para academias, mercados e lojas especializadas, além do varejo. Produtos de consumo recorrente e alto giro, formulário com Bling, faturamento R$5 a R$10 milhões/ano e loja virtual ativa. Qualificado por distribuidora com canal claro para revendas/lojistas, catálogo e pedidos recorrentes.',
   'insight':'academias e mercados comprarem no atacado com tabela e cadastro próprios, em vez de usar um checkout de varejo e fechar pedidos de volume pelo WhatsApp',
 },
 'mfbrinquedos321@gmail.com': {
   'slug':'mf-brinquedos',
   'mql': True,
   'empresa_real':'MF Brinquedos (atacado)',
   'dominio_site':'mfbrinquedos.catalogomobile.com.br; catálogo digital/e-commerce mobile da marca MF Brinquedos',
   'redes':'Instagram @mfbrinquedosatacado e Facebook MF Atacadistas localizados na pesquisa pública',
   'segmento':'Atacadista/distribuidor de brinquedos na Galeria Pagé/Brás, vendendo para lojistas e revendedores',
   'motivo':'Pesquisa pública associou MF Brinquedos a uma operação pública de atacado de brinquedos: Instagram @mfbrinquedosatacado, loja física na Galeria Pagé/Brás e catálogo digital próprio. O modelo é venda a lojistas/revendedores, com itens de alto giro e potencial claro de catálogo, tabela e pedido recorrente. O WhatsApp existe no catálogo público e o HubSpot também foi atualizado com celular válido; diagnóstico já pode ser enviado ao lead.',
   'insight':'lojistas navegarem o catálogo de brinquedos e fecharem pedidos de reposição com tabela e carrinho próprios, sem depender de cada conversa manual no WhatsApp',
   'whatsapp_publico':'Catálogo público MF Brinquedos: https://wa.me/55914819702; HubSpot atualizado com celular 55 11 94719-5184',
   'telefone_publico':'Catálogo público MF Brinquedos: 55 91 4819-702; HubSpot: 55 11 94719-5184',
   },
   'alexandre@novotempo.art.br': {
   'slug':'novo-tempo-artesanato',
   'mql': True,
   'empresa_real':'Novo Tempo Artesanato Ltda — operação Novo Tempo de artigos esotéricos, aromas, decoração e presentes em São Paulo/SP',
   'dominio_site':'novotempo.art.br; site oficial com área de acesso exclusivo para lojistas e distribuidores, catálogo digital B2B e categorias de aromas, esotérico, radiestesia, vidros, ateliês, decoração e presentes',
   'redes':'Instagram @novotempo_br localizado; cadastro público confirma Novo Tempo Artesanato Ltda ativa desde 1996, CNPJ 01.042.366/0001-96',
   'segmento':'Distribuidor/atacado de artigos esotéricos, aromaterapia, radiestesia, decoração, vidros e presentes para lojistas, distribuidores e revendas',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: o domínio novotempo.art.br tem área de acesso exclusivo para lojistas e distribuidores e catálogo digital B2B com dezenas de categorias. A empresa pública Novo Tempo Artesanato Ltda está ativa há muitos anos. O conjunto confirma atacado/distribuição vendendo para revendas/lojistas, com mix amplo, itens de consumo/reposição e potencial claro de digitalizar catálogo, tabela e pedidos recorrentes. O telefone do formulário é celular válido, mas não foi confirmado publicamente; será usado porque veio do formulário.',
   'insight':'lojistas e distribuidores consultarem o catálogo de aromas, decoração e presentes com tabela própria e reporem itens de alto giro sem depender de cada conversa manual',
   'telefone_publico':'não localizado com segurança; telefone usado vem do formulário HubSpot: +55 11 96960-5852',
   'whatsapp_publico':'não localizado com segurança',
 },
 'joaoroberto@vallemetais.com.br': {
   'slug':'valle-metais',
   'mql': True,
   'empresa_real':'Valle Metais Home Design — marca/fabricante nacional de acessórios metálicos para cozinhas e banheiros no Rio de Janeiro/RJ',
   'dominio_site':'vallemetais.com.br; site oficial confirma produção 100% nacional, linhas de produtos com códigos, página de representantes e chamada “Quer ter produtos da Valle Metais em sua loja?”',
   'redes':'Instagram @vallemetais, Facebook Valle Metais e LinkedIn Valle Metais Home Design localizados na pesquisa pública',
   'segmento':'Indústria/fabricante de acessórios metálicos para banheiro e cozinha, barras de apoio, grelhas e linhas de metais, abastecendo lojas, representantes e distribuidores',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch: site oficial confirma fabricação própria, catálogo por linhas/códigos, rede de representantes/distribuidores e presença em lojas como Leroy Merlin, Obramax, Chatuba e outras. O formulário reforça fit: R$1 a R$5 milhões/ano, 11 a 25 pessoas, ERP Outro e venda recorrente para clientes antigos sem visitas. Qualificado por indústria B2B com canal de lojas/revendas, catálogo e recompra de referências.',
   'insight':'lojas e representantes recomprarem linhas de metais e barras de apoio por código, com preço e disponibilidade, sem depender de ligação para cada reposição',
   'telefone_publico':'+55 21 3570-2144',
   'whatsapp_publico':'+55 21 99672-2592',
 },
 'hamilton@bioconect.com.br': {
   'slug':'bioconect-implantes',
   'mql': True,
   'empresa_real':'Bioconect Indústria e Comércio de Produtos Médicos e Odontológicos Ltda, fabricante de implantes e instrumentais médico-odontológicos em Itapira/SP, administrada por Hamilton Del Monaco Filho',
   'dominio_site':'bioconect.com.br; site ativo da empresa; também há bioconectshop.com.br e bioparts.com.br ligados à operação',
   'redes':'Facebook Bioconect Indústria e Comércio de Produtos Médicos Ltda e LinkedIn Bioconect localizados; revenda pública Dental Conecta vendendo implantes Bioconect',
   'segmento':'Indústria/fabricante de implantes dentários e instrumentais médico-odontológicos, com venda B2B para distribuidores e revendas odontológicas, além de canal próprio',
   'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo: domínio bioconect.com.br confirma fabricante real de produtos médico-odontológicos desde 2007; CNPJ público é Indústria e Comércio; Dental Conecta aparece revendendo implantes Bioconect. O formulário reforça fit: vende hoje direto ao distribuidor, ERP Bling, loja virtual ativa, 11 a 25 pessoas e faturamento de R$250 mil a R$500 mil/ano. Qualificado por indústria B2B com produto físico recorrente para abastecimento de distribuidores/revendas odontológicas.',
   'insight':'distribuidores e revendas odontológicas consultarem implantes e instrumentais com preço e disponibilidade, fazendo reposição sem depender de cada pedido manual',
   'telefone_publico':'(19) 3843-6765; fonte: site oficial bioconect.com.br/empresa',
   'whatsapp_publico':'atalhos WhatsApp públicos no site oficial: wa.link/jzio1a e wa.link/camqeq; telefone do formulário +55 11 98270-0146 não foi confirmado publicamente',
   },
   'comercial@lemoncaps.com.br': {
     'slug':'lemon-caps',
     'mql': True,
     'empresa_real':'Lemon Caps — indústria de nutracêuticos/suplementos no MT, com produção, branding e logística para criação de marcas próprias',
     'dominio_site':'lemoncaps.com.br; site oficial com fluxo de iniciar projeto e WhatsApp público wa.me/5565998443031',
     'redes':'Instagram @lemoncaps.br e LinkedIn LemonCaps; posicionamento público como indústria de nutracêuticos e ecossistema para construir marcas de suplementos',
     'segmento':'Indústria/fabricante B2B de suplementos encapsulados e gotas para empreendedores/produtores criarem e revenderem marca própria, com desenvolvimento, produção, design, regularização e logística',
     'motivo':'Pesquisa pública confirmou indústria/fornecedora B2B com produção de suplementos, suporte de marca, logística e integração comercial para clientes criarem produtos para vender. O formulário reforça fit: venda B2B, produtores que querem produção, revenda de produtos, loja virtual ativa, 11 a 25 pessoas e faturamento R$1 a R$5 milhões/ano. Qualificado por fabricante B2B com recorrência de pedidos e oportunidade de digitalizar catálogo, status de produção e recompra.',
     'insight':'marcas e revendedores acompanharem projetos, fórmulas, pedidos e reposições de suplementos em um portal B2B, sem depender de troca manual no WhatsApp a cada orçamento',
     'telefone_publico':'WhatsApp público do site: +55 65 99844-3031; telefone do formulário: +55 65 99804-1355',
     'whatsapp_publico':'+55 65 99844-3031; +55 65 99804-1355',
   },
   'marcelo.feitoza@mjxpetroleoegas.com.br': {
     'slug':'mjx-petroleo-e-gas',
     'mql': True,
     'empresa_real':'MJX Petróleo e Gás — distribuidor/fabricante de tubos de aço, conexões, válvulas e acessórios industriais',
     'dominio_site':'mjxpetroleo.com.br; site oficial com produtos, orçamento e WhatsApp público',
     'redes':'Instagram e site público indicam fornecimento de válvulas, tubos e acessórios industriais, inclusive fornecedor Petrobras',
     'segmento':'Distribuidor/fabricante B2B industrial de tubos, conexões, válvulas, flanges, parafusos, cabos e suprimentos para indústria, petróleo e gás',
     'motivo':'Pesquisa pública atual corrigiu o ciclo anterior: o site mjxpetroleo.com.br está ativo e descreve a MJX como fabricante e distribuidora de soluções em peças técnicas, tubos e acessórios industriais, com catálogo de produtos e solicitação de orçamento. Há WhatsApp público igual ao telefone do formulário (+55 21 99759-0108). Qualificado por distribuidor/fabricante industrial B2B com recorrência de cotações e reposição técnica.',
     'insight':'compradores industriais consultarem tubos, conexões e válvulas por categoria e abrirem cotações recorrentes em um canal próprio, sem perder histórico em e-mails e WhatsApp',
     'telefone_publico':'WhatsApp/orçamento público: +55 21 99759-0108; suporte: +55 21 97135-2019',
     'whatsapp_publico':'+55 21 99759-0108',
   },
   'daniel@mjxpetroleo.com.br': {
      'slug':'mjx-petroleo',
      'mql': True,
      'empresa_real':'MJX Petróleo — fabricante e distribuidora de soluções técnicas para petróleo, gás e indústria',
      'dominio_site':'mjxpetroleo.com.br; site oficial com produtos, orçamento e WhatsApp público',
      'redes':'Instagram e site público indicam fornecimento de válvulas, tubos e acessórios industriais, inclusive fornecedor Petrobras',
      'segmento':'Distribuidor/fabricante B2B industrial de tubos, conexões, válvulas, flanges, parafusos, cabos e suprimentos para indústria, petróleo e gás',
      'motivo':'Pesquisa pública atual corrigiu o ciclo anterior: o site mjxpetroleo.com.br está ativo e descreve a MJX como fabricante e distribuidora de soluções em peças técnicas, tubos e acessórios industriais, com catálogo de produtos e solicitação de orçamento. Há WhatsApp público igual ao telefone do formulário (+55 21 99759-0108). Qualificado por distribuidor/fabricante industrial B2B com recorrência de cotações e reposição técnica.',
      'insight':'compradores industriais consultarem tubos, conexões e válvulas por categoria e abrirem cotações recorrentes em um canal próprio, sem perder histórico em e-mails e WhatsApp',
      'telefone_publico':'WhatsApp/orçamento público: +55 21 99759-0108; suporte: +55 21 97135-2019',
      'whatsapp_publico':'+55 21 99759-0108',
    },
   'leonardo@vivantoestofados.com.br': {
      'slug':'vivanto-estofados',
      'mql': True,
      'empresa_real':'Vivanto Estofados Ltda — fabricante de móveis/estofados em Astolfo Dutra-MG, CNPJ 09.641.534/0001-71, ativa desde 2008',
      'dominio_site':'vivantoestofados.com.br; domínio corporativo do e-mail. Bases públicas CNPJá/Econodata confirmam empresa ativa, CNAE principal fabricação de móveis com predominância de madeira, e atividade secundária comércio varejista de móveis',
      'redes':'Resultados públicos no Instagram/Facebook mostram Leonardo Gravina como diretor da Vivanto Estofados visitando/vendendo para o Galpão Estofados; snippets indicam parceria/fornecedor para loja de estofados',
      'segmento':'Indústria/fabricante de estofados e móveis, com venda B2B para lojas/revendas de móveis e estofados; operação comercial por visita externa, catálogo físico e pedidos recorrentes de modelos, tecidos e reposição para lojistas',
      'motivo':'Pesquisa pública neste ciclo confirmou empresa real e ativa por CNPJ/bases cadastrais, com atividade principal de fabricação de móveis. Também há evidência pública do Leonardo, diretor da Vivanto, indo vender para o time do Galpão Estofados, caracterizando canal B2B para loja/revenda. O formulário reforça fit: ERP Olist/Tiny, 21 a 100 pessoas, faturamento de R$500 mil a R$1 milhão/ano e venda por visita externa. Qualificado por indústria/fabricante B2B com canal de lojistas/revendas e oportunidade de digitalizar catálogo, preço e pedidos recorrentes.',
      'insight':'lojistas consultarem modelos, tecidos, medidas e condições em um catálogo próprio, fechando reposições de estofados sem depender de cada visita externa',
      'telefone_publico':'CNPJá/CNPJ.info: (32) 3451-1068; telefone do formulário: +55 19 97411-0405',
    },
   'adm@gufebrasil.com.br': {
       'slug':'gufe-brasil',
       'mql': True,
       'empresa_real':'GUFE Brasil / GUFE Indústria e Comércio de Plásticos Ltda — fabricante e distribuidora de embalagens plásticas em Bauru/SP',
       'dominio_site':'gufebrasil.com.br; site oficial com catálogo institucional, contato comercial e CNPJ ativo desde 1998',
       'redes':'Site oficial GUFE Brasil; presença pública/cadastral como indústria de embalagens plásticas e comércio atacadista; atendimento Brasil todo via representantes e frota própria',
       'segmento':'Indústria/fabricante e distribuidora de embalagens plásticas, sacos de lixo em rolo, sacolas e bobinas picotadas; atende revendas, lojistas e indústrias em todo o Brasil por representantes e frota própria',
       'motivo':'Pesquisa pública via Claude Code/WebSearch/WebFetch confirmou empresa real e ativa, domínio corporativo, site oficial e CNPJ. O site posiciona a GUFE como fabricante/distribuidora de embalagens plásticas, com atendimento a revendas, lojistas e indústrias no Brasil todo; CNAEs públicos incluem fabricação de embalagens plásticas e comércio atacadista. O formulário reforça porte alto (R$50 a R$500 milhões/ano, +151 pessoas) e venda por representante. Sacos de lixo, sacolas e bobinas são consumíveis de alto giro, com recompra recorrente para abastecimento de estoque. Qualificado por indústria/distribuidora B2B com catálogo, tabela e pedidos recorrentes claros.',
       'insight':'revendas e lojistas recomprarem sacos, sacolas e bobinas em um catálogo próprio, com tabela e pedido mais rápidos para repor estoque sem depender de cada conversa com o representante',
       'telefone_publico':'Site oficial: (14) 3411-1600; telefone do formulário/HubSpot: (14) 98147-7779',
       'whatsapp_publico':'Site oficial: (14) 99137-7680 e (14) 99725-0360',
     },
   'gustavo@casadocampo.vet.br': {
       'slug':'casa-do-campo-gustavo-freitas',
       'mql': True,
       'empresa_real':'Grupo Casa do Campo — rede agropecuária/veterinária estruturada no Vale do Mucuri/MG, com múltiplas lojas em Teófilo Otoni, Carlos Chagas, Nanuque e Pavão',
       'dominio_site':'casadocampo.vet.br; domínio corporativo do e-mail e site oficial com várias unidades, telefones/WhatsApps por loja e presença institucional',
       'redes':'Instagram @grupocasadocampo com 4,3k seguidores, 567 posts e categoria Agricultura; conteúdos de produtos para produtor rural, lavoura, rebanho, pets, dedetização, sementes, medicamentos veterinários, rações e equipamentos; Facebook Grupo Casa do Campo',
       'segmento':'Rede agropecuária/veterinária multiunidade, com venda recorrente de insumos rurais, medicamentos veterinários, rações, sementes, ferramentas/equipamentos e produtos para fazendas, produtores rurais, prestadores de serviço e clientes B2B recorrentes',
       'motivo':'Correção Rafael: empresas como essa são MQL. Pesquisa pública confirma empresa grande e estruturada, com muitas sedes/unidades, domínio corporativo próprio, presença social ativa e portfólio agro/vet para produtor rural, fazendas, prestadores e clientes recorrentes. Mesmo com venda de balcão, o modelo tem recorrência, mix amplo, reposição e atendimento técnico, com potencial claro de catálogo digital, preço/condição e recompra para clientes rurais. O porte e a operação multiunidade prevalecem sobre uma leitura estreita de varejo.',
       'insight':'produtores, fazendas, prestadores e clientes recorrentes consultarem medicamentos veterinários, rações, sementes, equipamentos e itens de reposição em um canal próprio, sem depender de ligação ou WhatsApp para cada recompra',
       'telefone_publico':'Site oficial: (33) 3522-9330; WhatsApps públicos por loja: (33) 98827-4659, (33) 98750-0050 e link principal (33) 98827-4655; telefone do lead/HubSpot +55 33 98827-4655',
       'whatsapp_publico':'WhatsApp principal/site: +55 33 98827-4655; Nanuque: +55 33 98827-4659; Pavão: +55 33 98750-0050',
    },
    'lintrieri@policrombr.com': {
       'slug':'policrom-south-america-leonardo-intrieri', 'mql': True,
       'empresa_real':'Policrom Screens South America / Policrom South America Comércio, Importação e Exportação de Produtos Gráficos Ltda, filial/representante sul-americana da Policrom com operação no Brasil desde 2013 em São Paulo-SP',
       'dominio_site':'policrombr.com e policrom.com/worldwide; site oficial confirma produtos para mercado gráfico, insumos gráficos, Tech Films e mangueiras industriais; página mundial confirma POLICROM SCREENS SOUTH AMERICA COMÉRCIO, IMPORTAÇÃO E EXPORTAÇÃO DE PRODUTOS GRÁFICOS LTDA.',
       'redes':'Fontes pesquisadas neste ciclo: site oficial policrombr.com (home/produtos/sobre/contato), página Worldwide da Policrom internacional, Drupa 2024 e LinkedIn público da Policrom Screens South America; Leonardo Intrieri aparece como Sales Director/Comercial com WhatsApp +55 11 98156-5258.',
       'segmento':'Importadora/distribuidora B2B de insumos gráficos, materiais para pré-impressão/serigrafia/impressão digital, produtos gráficos e mangueiras industriais para gráficas e indústrias, com recompra recorrente de consumíveis, peças e materiais técnicos.',
       'motivo':'Pesquisa pública real confirmou empresa B2B de importação/distribuição no mercado gráfico e industrial, com domínio próprio, presença internacional da Policrom, operação brasileira desde 2013 e linha de insumos/consumíveis para gráficas e indústrias. O formulário reforça fit: ERP Omie, faturamento de R$5 a R$10 milhões, venda por WhatsApp/e-mail/visita com vendedor externo e telefone celular válido do diretor comercial. Passa no crivo acirrado por importadora/distribuidora B2B com catálogo técnico, preço e recompra recorrente de materiais/insumos.',
       'insight':'gráficas e clientes industriais consultarem catálogo, preço e disponibilidade de insumos e mangueiras para recomprar com menos dependência de e-mail, visita e pedido manual pelo WhatsApp',
       'telefone_publico':'Página Worldwide da Policrom divulga telefone geral +55 11 3333-3130 e Leonardo Intrieri Mobile & WhatsApp +55 11 98156-5258; telefone do formulário/HubSpot: +55 11 98156-5258.',
       'whatsapp_publico':'WhatsApp público corporativo de Leonardo Intrieri +55 11 98156-5258 em https://policrom.com/worldwide/; coincide com o telefone completo do HubSpot.',
    },
 'contato@kingtalhas.com.br': {
   'slug':'king-talhas-americo', 'mql': True,
   'empresa_real':'King Talhas — distribuidor/revendedor especializado em equipamentos de movimentação de cargas, talhas elétricas e manuais, guinchos, acessórios e peças de reposição, com manutenção e assistência técnica própria em São Paulo/SP',
   'dominio_site':'kingtalhas.com.br — site oficial; lojadastalhas.com é a loja virtual vinculada à King Talhas com catálogo, preços, carrinho, produtos em estoque, telefone/WhatsApp e compra online',
   'redes':'Pesquisa pública via Claude Code/WebSearch/WebFetch neste ciclo: site oficial King Talhas, loja virtual lojadastalhas.com, LinkedIn King Talhas e Instagram @reidastalhas. A loja mostra produtos, preços, compra pelo site e WhatsApp Business público +55 11 95415-1000.',
   'segmento':'Distribuidor/revendedor B2B de talhas, guinchos, equipamentos industriais de elevação, acessórios e peças de reposição para empresas, linhas de produção e manutenção industrial, com catálogo técnico e compras recorrentes de reposição.',
   'motivo':'Pesquisa pública real confirmou ICP T1: distribuidor/revenda de equipamentos industriais com loja virtual ativa, catálogo com preço e pedido online, WhatsApp Business público, acessórios e peças de reposição. O lead veio do Facebook sem respostas de formulário, mas a operação pública sustenta venda B2B de catálogo, cotação, disponibilidade e reposição para clientes industriais. O telefone informado no formulário é fixo/PABX, então foi usado o WhatsApp corporativo público da loja virtual.',
   'insight':'clientes industriais consultarem catálogo, preço e disponibilidade de talhas, guinchos e peças de reposição sem depender de cada cotação manual pelo telefone ou WhatsApp',
   'telefone_publico':'PABX no site: +55 11 2628-2320; WhatsApp Business público seguro na loja virtual: +55 11 95415-1000',
   'whatsapp_publico':'WhatsApp público oficial +55 11 95415-1000 encontrado na loja virtual lojadastalhas.com; substitui o telefone do HubSpot, que veio como fixo/PABX +55 11 2628-2320',
 },
}


def token():
    val = os.environ.get('HUBSPOT_API_KEY','')
    if val: return val
    if TOKEN_PATH.exists():
        for line in TOKEN_PATH.read_text().splitlines():
            if line.startswith('HUBSPOT_API_KEY='):
                return line.split('=',1)[1].strip().strip('"').strip("'")
    raise RuntimeError('sem HUBSPOT_API_KEY')
TOK = token()
HEAD = {'Authorization':'Bearer '+TOK, 'Content-Type':'application/json'}

def hs(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(HS+path, data=data, headers=HEAD, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            b = r.read().decode()
            return r.status, json.loads(b) if b else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        raise RuntimeError(f'HubSpot {method} {path} -> {e.code}: {body[:500]}')


def parse_hs_dt(value):
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo('America/Sao_Paulo'))
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=ZoneInfo('America/Sao_Paulo')).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def load_processed():
    if not PROCESSED.exists(): return {}
    out = {}
    for ln in PROCESSED.read_text().splitlines():
        if not ln.strip():
            continue
        fields = [x.strip() for x in ln.split('|')]
        emails = []
        for field in fields:
            low = field.lower()
            if '@' in low and '.' in low.split('@')[-1]:
                emails.append(low)
        if not emails:
            continue
        ts = None
        for field in fields:
            ts = parse_hs_dt(field)
            if ts:
                break
        for email in emails:
            old = out.get(email)
            if old is None or (ts and old and ts > old) or (old is None and ts):
                out[email] = ts
    return out

def append_processed(email, slug, status, tel, empresa):
    # Reentradas legítimas de formulário podem repetir email em outro horário; o
    # timestamp novo passa a ser o dedup para não repetir a mesma conversão.
    with open(PROCESSED,'a',encoding='utf-8') as f:
        f.write(f"{email.lower()}|{slug}|{datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M')}|{status}|{tel or ''}|{empresa or ''}\n")


def load_wpp():
    if not WPP.exists(): return []
    d = json.loads(WPP.read_text() or '[]')
    return d.get('envios',[]) if isinstance(d, dict) else (d if isinstance(d,list) else [])

def envio_datetime_brt(e):
    raw_tz = str((e or {}).get('date_tz') or '').strip()
    if raw_tz:
        try:
            dt = datetime.fromisoformat(raw_tz.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo('America/Sao_Paulo'))
            return dt.astimezone(ZoneInfo('America/Sao_Paulo'))
        except Exception:
            pass
    raw = str((e or {}).get('date') or '').strip()
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(raw[:19], fmt).replace(tzinfo=ZoneInfo('America/Sao_Paulo'))
        except Exception:
            pass
    return None

MAX_EXTERNAL_PER_PORT_HOUR = 3
MAX_EXTERNAL_PER_PORT_DAY = 30

def is_direct_external_envio(e):
    if not isinstance(e, dict):
        return False
    to = str(e.get('to') or e.get('jid') or e.get('lead_jid') or '')
    if to.endswith('@g.us'):
        return False
    if not e.get('bridge_port'):
        return False
    status = str(e.get('status') or '').lower()
    msg_type = str(e.get('msg_type') or '').lower()
    return bool(e.get('text_status') or e.get('text_message_id') or e.get('messageId') or msg_type or status in {'enviado_lead','enviado_mql','enviado','sent'})

def port_within_external_limits(envios, port, max_per_hour=MAX_EXTERNAL_PER_PORT_HOUR, max_per_day=MAX_EXTERNAL_PER_PORT_DAY):
    now = datetime.now(ZoneInfo('America/Sao_Paulo'))
    hour = day = 0
    for e in envios:
        if not is_direct_external_envio(e):
            continue
        try:
            if int(e.get('bridge_port')) != int(port):
                continue
        except Exception:
            continue
        dt = envio_datetime_brt(e)
        if not dt:
            continue
        delta = (now - dt).total_seconds()
        if 0 <= delta < 3600:
            hour += 1
        if dt.date() == now.date():
            day += 1
    ok = hour < max_per_hour and day < max_per_day
    return ok, f'porta {port}: {hour}/{max_per_hour} na última hora, {day}/{max_per_day} hoje'

def save_wpp(items):
    # Preserva o schema histórico {"envios": [...]}; alguns dashboards/relatórios esperam essa chave.
    WPP.write_text(json.dumps({'envios': items}, ensure_ascii=False, indent=2), encoding='utf-8')

def only_digits(x): return re.sub(r'\D','', x or '')

def phone_variants_with_optional_9(raw):
    """Variações BR conservadoras: com/sem 9 depois do DDD antes de invalidar WhatsApp."""
    d = only_digits(raw)
    if d.startswith('55') and len(d) in (12, 13):
        d = d[2:]
    if len(d) not in (10, 11):
        return []
    ddd = d[:2]
    if ddd == '00' or ddd.startswith('0') or int(ddd) < 11 or int(ddd) > 99:
        return []
    local = d[2:]
    variants = []
    def add(n):
        n = normalize_br_phone(n)
        if n and n not in variants:
            variants.append(n)
    add(d)
    if len(d) == 10:
        add(ddd + '9' + local)
    elif len(d) == 11 and local.startswith('9'):
        add(ddd + local[1:])
    return variants


def jid_from_phone(p):
    variants = phone_variants_with_optional_9(p)
    d = variants[0] if variants else only_digits(p)
    if len(d)==11: d='55'+d
    return d+'@c.us'

FREE_EMAIL_DOMAINS = {
    'gmail.com','hotmail.com','outlook.com','outlook.com.br','yahoo.com','yahoo.com.br',
    'icloud.com','live.com','bol.com.br','uol.com.br','terra.com.br','proton.me'
}

PHONE_RE = re.compile(r'(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?(?:9\s*)?\d{4}[-.\s]?\d{4}')


def normalize_br_phone(raw):
    d = only_digits(raw)
    if not d:
        return ''
    if d.startswith('55') and len(d) in (12, 13):
        d = d[2:]
    # descarta placeholders curtos/longos demais; aceita fixo apenas se contexto indicar WhatsApp.
    if len(d) not in (10, 11):
        return ''
    ddd = d[:2]
    if ddd == '00' or ddd.startswith('0') or int(ddd) < 11 or int(ddd) > 99:
        return ''
    if len(d) == 11 and d[2] == '9':
        return '55' + d
    if len(d) == 10:
        return '55' + d
    return ''


def phone_is_mobile_br(phone):
    d = only_digits(phone)
    if d.startswith('55') and len(d) == 13:
        d = d[2:]
    return len(d) == 11 and d[2] == '9'


def candidate_domain(email, research):
    dom = ''
    if '@' in (email or ''):
        dom = email.split('@', 1)[1].lower().strip()
    text = (research or {}).get('dominio_site') or ''
    m = re.search(r'([a-z0-9][a-z0-9-]+\.(?:com\.br|com|net\.br|net|ind\.br|shop|digital|br))', text.lower())
    if m:
        dom = m.group(1)
    if dom in FREE_EMAIL_DOMAINS:
        return ''
    return dom


def extract_public_phone_from_text(text, source):
    text = text or ''
    candidates = []
    for m in PHONE_RE.finditer(text):
        raw = m.group(0)
        norm = normalize_br_phone(raw)
        if not norm:
            continue
        ctx = text[max(0, m.start()-80):m.end()+80].lower()
        has_wa = any(k in ctx for k in ('whatsapp','whats','wpp','wa.me','api.whatsapp'))
        is_mobile = phone_is_mobile_br(norm)
        # Para envio automático ao WhatsApp: celular é seguro; fixo só se a própria fonte indica WhatsApp.
        if is_mobile or has_wa:
            candidates.append({'phone': norm, 'raw': raw.strip(), 'source': source, 'whatsapp_hint': has_wa, 'is_mobile': is_mobile})
    if not candidates:
        return None
    # Prioridade: celular com menção a WhatsApp > celular > fixo com menção explícita a WhatsApp.
    candidates.sort(key=lambda c: (not (c['is_mobile'] and c['whatsapp_hint']), not c['is_mobile'], not c['whatsapp_hint']))
    best = dict(candidates[0])
    best.pop('is_mobile', None)
    return best


def fetch_public_url(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 ZydonBot phone lookup'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            ctype = resp.headers.get('content-type','')
            if 'text' not in ctype and 'html' not in ctype and 'json' not in ctype:
                return ''
            return resp.read(350000).decode('utf-8', errors='ignore')
    except Exception:
        return ''


def strip_html(text):
    text = re.sub(r'<script\b[^>]*>.*?</script>', ' ', text or '', flags=re.I|re.S)
    text = re.sub(r'<style\b[^>]*>.*?</style>', ' ', text, flags=re.I|re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&#39;', "'").replace('&quot;', '"')
    return re.sub(r'\s+', ' ', text)


def search_engine_phone(company, domain):
    import urllib.parse
    terms = []
    if company:
        terms.append(company)
    if domain:
        terms.append(domain)
    base = ' '.join(t for t in terms if t).strip()
    if not base:
        return None
    queries = [
        f'{base} telefone WhatsApp',
        f'{base} contato celular',
        f'{base} whatsapp comercial',
    ]
    engines = [
        'https://www.google.com/search?q={q}',
        'https://www.bing.com/search?q={q}',
        'https://duckduckgo.com/html/?q={q}',
    ]
    for q in queries:
        qenc = urllib.parse.quote(q)
        for tmpl in engines:
            url = tmpl.format(q=qenc)
            html = fetch_public_url(url)
            if not html:
                continue
            txt = strip_html(html)
            found = extract_public_phone_from_text(txt, f'busca pública: {q}')
            if found:
                return found
    return None


def lookup_public_phone(email, company, research):
    """Busca telefone público quando HubSpot não trouxe WhatsApp válido.

    Camadas conservadoras: pesquisa já salva/base local → site público do domínio.
    Retorna número normalizado 55DDDN... e fonte; não inventa, não usa número sem fonte.
    """
    blobs = []
    base = ' | '.join(str((research or {}).get(k) or '') for k in ('empresa_real','dominio_site','redes','motivo','segmento','telefone_publico','whatsapp_publico','public_phone','public_whatsapp'))
    if base:
        blobs.append(('pesquisa do ciclo', base))
    dom = candidate_domain(email, research)
    if dom:
        for p in PESQ.glob('*.md'):
            try:
                txt = p.read_text(errors='ignore')
            except Exception:
                continue
            hay = txt.lower()
            if dom in hay or (company and company.lower()[:18] in hay):
                blobs.append((f'base local {p.name}', txt[:200000]))
                break
    for source, txt in blobs:
        found = extract_public_phone_from_text(txt, source)
        if found:
            return found
    if dom:
        urls = []
        for scheme in ('https://','http://'):
            root = scheme + dom
            urls.extend([root, root + '/contato', root + '/contatos', root + '/fale-conosco', root + '/atendimento'])
        seen = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            txt = fetch_public_url(url)
            if not txt:
                continue
            found = extract_public_phone_from_text(txt, url)
            if found:
                return found
    found = search_engine_phone(company or (research or {}).get('empresa_real'), dom)
    if found:
        return found
    return None

def slugify(s):
    import unicodedata
    s = ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+','-',s).strip('-') or 'empresa'

def br_greeting():
    now=datetime.now(ZoneInfo('America/Sao_Paulo'))
    # Regra Rafael: bom dia 05:00 até antes das 13:00; boa tarde 13:00 até antes das 18:00;
    # boa noite das 18:00 em diante e também de 00:00 até antes das 05:00.
    if 5 <= now.hour < 13: return 'Bom dia'
    if 13 <= now.hour < 18: return 'Boa tarde'
    return 'Boa noite'


def fmt_created_brt(createdate):
    """Formata createdate do HubSpot para o grupo entender hora/dia de entrada do lead."""
    if not createdate:
        return 'não informado'
    try:
        raw = createdate.replace('Z', '+00:00')
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M BRT')
    except Exception:
        return str(createdate)


def traffic_creative_line(props):
    """Resumo da origem/criativo para ajudar Rafael a cruzar com criativo do Facebook."""
    props = props or {}
    original_source = props.get('hs_analytics_source') or ''
    original_1 = props.get('hs_analytics_source_data_1') or ''
    original_2 = props.get('hs_analytics_source_data_2') or ''
    latest_source = props.get('hs_latest_source') or ''
    latest_1 = props.get('hs_latest_source_data_1') or ''
    latest_2 = props.get('hs_latest_source_data_2') or ''

    # O campo *_data_2 normalmente carrega campanha/conjunto/anúncio; é o mais útil para criativo.
    creative = latest_2 or original_2
    source = latest_source or original_source
    source_1 = latest_1 or original_1
    pieces = []
    if source or source_1:
        pieces.append(' / '.join(x for x in [source, source_1] if x))
    if creative:
        pieces.append(creative)
    return ' | '.join(pieces) if pieces else 'não informado'


def group_erp_line(props):
    """Linha opcional de ERP somente para a mensagem interna do grupo."""
    props = props or {}
    values = []
    for key in ('qual_erp_utiliza_', 'selecione_o_sistema_de_gesto_erp', 'selecione_o_sistema_de_gesto'):
        val = str(props.get(key) or '').strip()
        if not val or val.lower() in ('none', 'null', 'não informado', 'nao informado'):
            continue
        if val not in values:
            values.append(val)
    return f"ERP informado: {', '.join(values)}\n" if values else ''


def is_work_hours_brt():
    now=datetime.now(ZoneInfo('America/Sao_Paulo'))
    # Horário de trabalho Rafael: seg-sex, 07:00 até antes de 18:00 BRT.
    return now.weekday() < 5 and 7 <= now.hour < 18

def timing_first_person():
    now=datetime.now(ZoneInfo('America/Sao_Paulo'))
    # seg-sex 7-18 => jaja; sábado => segunda; domingo/noite => amanhã
    if is_work_hours_brt():
        return 'Eu te chamo jaja'
    if now.weekday() == 5:
        return 'Eu te chamo na segunda-feira'
    return 'Eu te chamo amanhã'

def bridge_me(port):
    try:
        out = subprocess.check_output(['curl','-s',f'http://127.0.0.1:{port}/me'], timeout=15, text=True)
        d=json.loads(out)
        # /me com {"phone": null} é sessão morta/needsQR; não pode ser aceito como online.
        if d.get('error') or 'Cannot read properties' in out or not (d.get('id') or d.get('name')):
            return False, out
        return True, out
    except Exception as e:
        return False, str(e)

def pick_online_port(owner_info, envios):
    """Escolhe a porta online menos usada para o SDR.

    Para Breno, usa somente 4605. Para os demais, mantém a porta única.
    """
    ports = owner_info.get('portas') or [owner_info['porta']]
    def used_count(port):
        return sum(1 for e in envios if isinstance(e, dict) and e.get('bridge_port') == port)
    offline = []
    for port in sorted(ports, key=lambda p: (used_count(p), p)):
        ok, me = bridge_me(port)
        if ok:
            return port, True, me, ''
        offline.append(f'porta {port}: {me}')
    return ports[0], False, offline[-1] if offline else 'sem portas configuradas', '; '.join(offline)


def post_group_with_rotation(text, envios):
    """Envia ao grupo tentando comunicadores online; se forbidden/não membro, tenta o próximo."""
    ports = NON_MQL_NOTIFY_OWNER.get('portas') or [NON_MQL_NOTIFY_OWNER['porta']]
    def used_count(port):
        return sum(1 for e in envios if isinstance(e, dict) and (e.get('group_bridge_port') == port or (e.get('to') == GROUP and e.get('bridge_port') == port)))
    attempts = []
    for group_port in sorted(ports, key=lambda p: (used_count(p), p)):
        ok, me = bridge_me(group_port)
        if not ok:
            attempts.append({'port': group_port, 'status': 'offline', 'detail': me})
            continue
        resp = post_bridge(group_port, '/send', {'to': GROUP, 'text': text})
        attempts.append({'port': group_port, 'response': resp})
        if message_ok(resp):
            return group_port, resp, attempts
        # Se a conta não está no grupo ou falhou, tenta outro comunicador.
        if 'forbidden' in json.dumps(resp, ensure_ascii=False).lower() or 'not a participant' in json.dumps(resp, ensure_ascii=False).lower():
            continue
    return None, {'error': 'grupo não enviado por nenhum comunicador', 'attempts': attempts}, attempts


def post_bridge(port, path, payload):
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            txt = r.read().decode()
            try: return json.loads(txt)
            except Exception: return {'raw': txt}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        try:
            data = json.loads(body)
        except Exception:
            data = {'raw': body}
        data['http_error'] = e.code
        return data
    except Exception as e:
        return {'error': str(e)}

def message_ok(resp):
    txt=json.dumps(resp, ensure_ascii=False)
    # Nunca aceitar success:true sozinho; exigir messageId real ou status do WhatsApp.
    return ('messageId' in txt or '"status": 1' in txt or '"status":2' in txt or '"status": 2' in txt)


def post_bridge_with_retries(port, path, payload, attempts=3, delay=12):
    """Envia via bridge com retentativas curtas antes de fallback.

    WhatsApp/Baileys às vezes retorna timeout/Connection Closed/HTTP 500 mesmo com
    o chip online. Para SDR dono em horário comercial, não trocar para institucional
    no primeiro erro: retenta no próprio chip.
    """
    responses = []
    for attempt in range(1, attempts + 1):
        resp = post_bridge(port, path, payload)
        responses.append({'attempt': attempt, 'response': resp})
        if message_ok(resp):
            return resp, responses
        # força leitura do estado da bridge e dá tempo do Baileys reconectar.
        try:
            bridge_me(port)
        except Exception:
            pass
        if attempt < attempts:
            time.sleep(delay)
    return responses[-1]['response'] if responses else {'error':'sem tentativa'}, responses


def get_contact(cid):
    props = ['email','firstname','lastname','company','hubspot_owner_id','lifecyclestage']
    qs='&'.join('properties='+p for p in props)
    return hs('GET', f'/crm/v3/objects/contacts/{cid}?{qs}')[1]

def patch_contact(cid, props):
    return hs('PATCH', f'/crm/v3/objects/contacts/{cid}', {'properties':props})[1]

def contact_deals(cid):
    try:
        d=hs('GET', f'/crm/v4/objects/contacts/{cid}/associations/deals')[1]
        return [str(r['toObjectId']) for r in d.get('results',[])]
    except Exception:
        return []

def get_deal(did):
    return hs('GET', f'/crm/v3/objects/deals/{did}?properties=dealname,hubspot_owner_id,createdate')[1]

def patch_deal(did, props):
    return hs('PATCH', f'/crm/v3/objects/deals/{did}', {'properties':props})[1]


def move_deals_to_invalid_stage(deal_ids, reason=''):
    """Move negócios associados para a fase Leads Inválidos quando não há contato/WhatsApp válido."""
    actions = []
    for did in deal_ids or []:
        try:
            patch_deal(did, {'pipeline': DEALS_PIPELINE_ID, 'dealstage': DEALSTAGE_LEADS_INVALIDOS})
            actions.append(f'deal {did}: Leads Inválidos' + (f' ({reason})' if reason else ''))
        except Exception as e:
            actions.append(f'deal {did}: erro ao mover para Leads Inválidos: {str(e)[:160]}')
    if not actions:
        actions.append('sem negócio associado para mover para Leads Inválidos')
    return actions


def deal_meetings(did):
    try:
        d=hs('GET', f'/crm/v4/objects/deals/{did}/associations/meetings')[1]
        return [str(r['toObjectId']) for r in d.get('results',[])]
    except Exception:
        return []

def meeting_owner(mid):
    d=hs('GET', f'/crm/v3/objects/meetings/{mid}?properties=hubspot_owner_id')[1]
    return (d.get('properties') or {}).get('hubspot_owner_id')

def sync_agenda_owner(cid):
    actions=[]
    cowner=(get_contact(cid).get('properties') or {}).get('hubspot_owner_id') or ''
    for did in contact_deals(cid):
        deal=get_deal(did); downer=(deal.get('properties') or {}).get('hubspot_owner_id') or ''
        mids=deal_meetings(did)
        if not mids:
            actions.append(f'deal {did}: sem reunião')
            continue
        owner=None
        for mid in mids:
            owner=meeting_owner(mid)
            if owner: break
        if not owner:
            actions.append(f'deal {did}: reunião sem owner')
            continue
        if downer != owner:
            patch_deal(did, {'hubspot_owner_id':owner}); actions.append(f'deal {did}: owner {downer or "vazio"}->{owner}')
        if cowner != owner:
            patch_contact(cid, {'hubspot_owner_id':owner}); cowner=owner; actions.append(f'contato: owner->{owner}')
        if downer == owner and cowner == owner:
            actions.append(f'deal {did}: owner ok {owner}')
    return actions or ['sem negócio associado']


def resolve_business_owner(cid, deal_ids, contact_owner=''):
    """Escolhe o owner para mensagem/agenda priorizando o DONO DO NEGÓCIO.

    Regra Rafael: o link de agenda enviado ao lead deve ser do dono do negócio,
    independente do remetente WhatsApp. Se houver múltiplos negócios, pega o mais
    novo com hubspot_owner_id. Se nenhum negócio tiver owner, cai para owner do contato.
    """
    candidates=[]
    notes=[]
    for did in deal_ids:
        try:
            deal=get_deal(did)
            props=deal.get('properties') or {}
            downer=props.get('hubspot_owner_id') or ''
            created=props.get('createdate') or ''
            notes.append(f'deal {did}: owner {downer or "vazio"}')
            if downer:
                candidates.append((created, did, downer))
        except Exception as e:
            notes.append(f'deal {did}: owner erro {e}')
    if candidates:
        candidates.sort(reverse=True)
        created, did, owner = candidates[0]
        if contact_owner != owner:
            try:
                patch_contact(cid, {'hubspot_owner_id': owner})
                notes.append(f'contato alinhado ao dono do negócio {did}: {owner}')
            except Exception as e:
                notes.append(f'contato não alinhado ao dono do negócio {did}: {e}')
        return owner, notes
    return contact_owner or '', notes or ['sem negócio associado']


def wait_for_business_owner(cid, initial_owner='', timeout_sec=300, interval_sec=15):
    """Espera a automação do HubSpot criar/atribuir o negócio após MQL.

    O contato normalmente nasce sem dono. Depois que marcamos MQL, o HubSpot cria
    o negócio e atribui owner. Para não enviar agenda errada/vazia, esperamos até
    5min pelo owner do NEGÓCIO antes de mandar o WhatsApp ao lead.
    """
    deadline=time.time()+timeout_sec
    notes=[]
    last_owner=initial_owner or ''
    last_deals=[]
    attempt=0
    while True:
        attempt += 1
        try:
            fresh=get_contact(cid)
            contact_owner=((fresh.get('properties') or {}).get('hubspot_owner_id') or last_owner or '')
            deals=contact_deals(cid)
            owner, owner_notes = resolve_business_owner(cid, deals, contact_owner)
            last_owner=owner or contact_owner or ''
            last_deals=deals
            notes.append(f'tentativa {attempt}: owner {last_owner or "vazio"}; deals {len(deals)}; ' + '; '.join(owner_notes[:3]))
            # Só segue quando o dono do negócio é um SDR conhecido com agenda.
            if last_owner in OWNER_MAP:
                return last_owner, deals, notes
        except Exception as e:
            notes.append(f'tentativa {attempt}: erro {e}')
        if time.time() >= deadline:
            return last_owner, last_deals, notes + [f'timeout owner negócio após {timeout_sec}s']
        time.sleep(interval_sec)

def create_task(cid, deal_ids, subject, body, owner_id=None, attachment_ids=None):
    props={
      'hs_timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
      'hs_task_subject': subject,
      'hs_task_body': body,
      'hs_task_status': 'COMPLETED',
      'hs_task_priority': 'MEDIUM',
      'hs_task_type': 'TODO',
    }
    if owner_id: props['hubspot_owner_id']=str(owner_id)
    if attachment_ids:
        # HubSpot tasks/engagements attach files via semicolon-separated file IDs.
        props['hs_attachment_ids']=';'.join(str(x) for x in attachment_ids if x)
    ass=[{'to':{'id':str(cid)}, 'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':204}]}]
    for did in deal_ids:
        ass.append({'to':{'id':str(did)}, 'types':[{'associationCategory':'HUBSPOT_DEFINED','associationTypeId':216}]})
    return hs('POST','/crm/v3/objects/tasks', {'properties':props, 'associations':ass})[1].get('id')

def hubspot_file_meta(file_id):
    """Busca metadados do arquivo no HubSpot Files."""
    if not file_id:
        return {}
    req=urllib.request.Request(f'https://api.hubapi.com/files/v3/files/{file_id}', headers={'Authorization':'Bearer '+TOK})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def hubspot_file_url(file_id):
    """Busca URL pública e estável do arquivo no HubSpot Files (best-effort)."""
    if not file_id:
        return ''
    try:
        data=hubspot_file_meta(file_id)
        # Para PUBLIC_NOT_INDEXABLE, `url` e `defaultHostingUrl` são o link público.
        # Para PRIVATE, `url` vira signed-url-redirect e pode quebrar/404 na UI; rejeitar.
        if data.get('access') != 'PUBLIC_NOT_INDEXABLE':
            return ''
        return data.get('defaultHostingUrl') or data.get('url') or ''
    except Exception:
        return ''


def fallback_timing_for_owner(original_sdr):
    """Texto de próximo contato quando diagnóstico não deve prometer contato em 1ª pessoa."""
    now=datetime.now(ZoneInfo('America/Sao_Paulo'))
    # Quando souber o SDR dono, nomear quem vai chamar para reduzir confusão.
    # Sem dono, usar consultor genérico.
    if original_sdr == 'Breno':
        pessoa = 'O Breno, consultor da Zydon'
    elif original_sdr == 'Sarah':
        pessoa = 'A Sarah, consultora da Zydon'
    elif original_sdr in {'Lucas', 'Lucas Batista'}:
        pessoa = 'O Lucas Batista, consultor da Zydon'
    else:
        pessoa = 'O consultor responsável da Zydon'
    if is_work_hours_brt():
        when = 'jaja'
    elif now.weekday() == 5:
        when = 'na segunda-feira'
    else:
        when = 'amanhã'
    return f'{pessoa} te chama {when}'


def strict_icp_check(props, research):
    """Crivo MQL acirrado Rafael: só MQL se for T1 B2B de alto giro/estoque.

    Fail-closed: se não houver evidência clara de indústria/distribuidor/importador/atacado
    vendendo para revendas/lojas/clientes recorrentes com abastecimento de estoque, não marca MQL.
    ERP nativo/e-commerce ajudam, mas NÃO substituem ICP.
    """
    props = props or {}
    research = research or {}
    form_fields = [
        'company', 'email', 'de_qual_forma_mais_vende_hoje_em_dia',
        'qual_a_area_de_atuacao_de_sua_empresa_',
        'qual_a_rea_de_atuao_de_sua_empresa',
        'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados',
        'voc_vende_para_quem',
        'voc_vende_para_quem_ex_padarias_restaurantes_petshop_autopeas_supermercados',
        'vende_em_loja_virtual_',
        'voc_acredita_que_o_seu_cliente_compraria_sozinho',
        'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor',
        'qual_seria_o_maior_problema', 'principais_dores',
        'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente',
        'quantos_vendedores_internos', 'quantos_vendedores_internos_sua_empresa_possui',
        'quantas_pessoas_atuam_na_sua_empresa',
        'qual_o_faturamento_anual_da_sua_empresa_', 'e_qual_faturamento_anual_da_sua_empresa',
        'selecione_a_faixa_de_faturamento', 'selecione_a_faixa_de_faturamento_atual_por_ano_da_sua_empresa',
    ]
    text = ' '.join(str(x or '') for x in [
        *[props.get(k) for k in form_fields],
        research.get('empresa_real'), research.get('segmento'), research.get('motivo'),
        research.get('insight'), research.get('dominio_site'), research.get('redes'),
    ]).lower()
    blockers = ['consultoria', 'palestra', 'advisory', 'site pessoal', 'pessoal/consultoria', 'recuperação judicial', 'recuperacao judicial', 'serviço local', 'servico local']
    if any(b in text for b in blockers):
        return False, 'bloqueio ICP: consultoria/site pessoal/serviço ou situação sensível; não é oportunidade T1 clara de abastecimento B2B'
    business_terms = ['distribuidor', 'distribuidora', 'distribuição', 'distribuicao', 'indústria', 'industria', 'fabricante', 'fabricação', 'fabricacao', 'importador', 'importadora', 'atacado', 'atacadista', 'wholesale']
    replenishment_terms = ['revenda', 'revendas', 'revendedor', 'revendedores', 'lojista', 'lojistas', 'lojas', 'varejo', 'canal de distribuidor', 'canal distribuidor', 'representante', 'representantes', 'integrador', 'integradores', 'abastecimento de estoque', 'reposição de estoque', 'reposicao de estoque', 'reposição técnica', 'reposicao tecnica', 'reposições', 'reposicoes', 'cotações recorrentes', 'cotacoes recorrentes', 'compradores industriais', 'catálogo para lojistas', 'catalogo para lojistas', 'pedido recorrente de revenda', 'pedidos recorrentes de revenda']
    industrial_b2b_terms = ['máquinas pesadas', 'maquinas pesadas', 'automação industrial', 'automacao industrial', 'controle e posicionamento', 'joystick', 'controladores industriais', 'encoders', 'radares', 'sensores', 'segurança industrial', 'seguranca industrial', 'siderurgia', 'mineração', 'mineracao', 'portos', 'ferrovias', 'manufatura', 'cotação', 'cotacao', 'catálogo de produtos', 'catalogo de produtos', 'clientes industriais']
    enterprise_client_terms = ['gerdau', 'siemens', 'ternium', 'vale', 'weg', 'arcelormittal', 'usiminas', 'votorantim', 'anglo american', 'thyssen', 'rumo']
    has_business = any(t in text for t in business_terms)
    has_replenishment = any(t in text for t in replenishment_terms)
    has_industrial_b2b = any(t in text for t in industrial_b2b_terms) and any(t in text for t in ['indústria', 'industria', 'fabricante', 'fabricação', 'fabricacao', 'fornecedora', 'b2b'])
    has_enterprise_clients = any(t in text for t in enterprise_client_terms)
    agro_multiunit_signal = all(t in text for t in ['agro', 'multiunidade']) and any(t in text for t in ['fazendas', 'produtor rural', 'produtores rurais', 'prestadores de serviço', 'clientes b2b recorrentes']) and any(t in text for t in ['medicamentos veterinários', 'medicamentos veterinarios', 'rações', 'racoes', 'sementes', 'equipamentos', 'insumos rurais'])
    if agro_multiunit_signal and any(t in text for t in ['domínio corporativo', 'dominio corporativo', 'site oficial', 'múltiplas lojas', 'multiplas lojas', 'várias unidades', 'varias unidades']):
        return True, 'rede agro/vet multiunidade com clientes rurais recorrentes, mix amplo e reposição; qualifica por porte e recorrência B2B rural'
    structured_b2b_supplier_signal = any(t in text for t in ['fornecedor b2b estruturado', 'empresa grande/estruturada', 'faturamento de r$10 a r$50', '21 a 100 pessoas']) and any(t in text for t in ['loja virtual', 'omie', 'bling', 'whatsapp', 'boleto parcelado']) and any(t in text for t in ['catálogo amplo', 'catalogo amplo', 'pedido digital', 'compra recorrente', 'clientes recorrentes', 'orçamento', 'orcamento', 'recompra'])
    if structured_b2b_supplier_signal and any(t in text for t in ['sinalização', 'sinalizacao', 'equipamentos', 'placas', 'cones', 'segurança', 'seguranca']):
        return True, 'fornecedor B2B estruturado com porte, ERP/e-commerce e dor explícita de pedidos no WhatsApp; qualifica por digitalização de catálogo, condição e recompra'
    corporate_recurring_b2b_signal = any(t in text for t in ['fornecedor b2b estruturado', 'soluções alimentares corporativas', 'solucoes alimentares corporativas', 'programas mensais recorrentes', 'benefícios corporativos', 'beneficios corporativos', 'empresas clientes', 'cliente empresa', 'rh']) and any(t in text for t in ['omie', 'site/whatsapp', 'whatsapp público', 'whatsapp publico', 'domínio corporativo', 'dominio corporativo']) and any(t in text for t in ['recorrentes', 'orçamento', 'orcamento', 'recompra', 'portal b2b', 'logística', 'logistica'])
    if corporate_recurring_b2b_signal:
        return True, 'B2B recorrente para empresas com domínio, ERP/WhatsApp e orçamento/logística; não depende de revenda literal'
    apparel_factory_b2b_signal = any(t in text for t in ['fábrica', 'fabrica', 'confecção', 'confeccao', 'private label', 'tecidos esportivos']) and any(t in text for t in ['bling', 'b2b', '21 a 100 pessoas', 'atacado', 'revenda', 'grandes marcas'])
    if apparel_factory_b2b_signal:
        return True, 'confecção/fábrica B2B com ERP, porte e canal para marcas/revendas; qualifica como MQL'
    erp = (props.get('qual_erp_utiliza_') or props.get('selecione_o_sistema_de_gesto_erp') or '').strip().lower()
    native_erp = any(x in erp for x in ('bling', 'omie', 'olist', 'tiny', 'sankhya'))
    ecommerce = (props.get('vende_em_loja_virtual_') or '').strip().lower() in {'sim', 'yes', 'true'} or any(t in text for t in ['e-commerce', 'ecommerce', 'loja virtual'])
    people = (props.get('quantas_pessoas_atuam_na_sua_empresa') or '').strip()
    revenue = (props.get('qual_o_faturamento_anual_da_sua_empresa_') or props.get('selecione_a_faixa_de_faturamento') or '').lower()
    size_signal = people in {'11_a_25','21_a_100_','26_a_50','51_a_100','101_a_150','+151'} or any(x in revenue for x in ['r$500 mil a r$1', 'r$1 a r$5', 'r$5 a r$10', 'r$10 a r$50', 'r$50 a r$500', '500 milhões'])
    if not has_business:
        return False, 'não evidenciou ser indústria/distribuidor/importador/atacado'
    if has_industrial_b2b and has_enterprise_clients:
        return True, 'indústria/fabricante B2B técnico com catálogo/cotação e clientes industriais grandes; não depende de palavra revenda/lojista'
    if not has_replenishment:
        return False, 'não evidenciou venda para revendas/lojistas/integradores ou abastecimento recorrente de estoque'
    public_distributor_signal = any(t in text for t in ['distribuidora atacadista', 'distribuidor atacadista', 'importadora e distribuidora', 'fabricante e distribuidora', 'fabricante e distribuidor', 'distribuidor/fabricante', 'operação atacadista', 'operacao atacadista', 'entrega nacional', 'clientes b2b recorrentes', 'venda b2b recorrente', 'tubos e acessórios industriais', 'tubos e acessorios industriais', 'suprimentos para indústria', 'suprimentos para industria'])
    if public_distributor_signal and any(t in text for t in ['domínio próprio', 'dominio proprio', 'site oficial', 'cnpj', 'empresa real', 'linkedin']):
        return True, 'distribuidora/importadora B2B validada publicamente; formulário incompleto não bloqueia MQL'
    if not (native_erp or ecommerce or size_signal or (has_industrial_b2b and has_enterprise_clients)):
        return False, 'ICP aderente, mas sem sinal suficiente de ERP nativo, e-commerce, porte T1 ou clientes industriais relevantes'
    return True, 'passou crivo ICP: operação B2B de estoque/alto giro com sinal de ERP/e-commerce/porte'


def business_clean(text, limit=220):
    """Deixa o motivo legível para o grupo interno: curto, sem jargão técnico."""
    text = (text or '').strip()
    replacements = [
        ('Pesquisa via Claude Code/WebSearch/WebFetch:', ''),
        ('Pesquisa via Claude Code/WebSearch:', ''),
        ('Pesquisa web real via WebSearch/WebFetch após falha de quota do Claude Code:', ''),
        ('via Claude Code/WebSearch/WebFetch', ''),
        ('via Claude Code/WebSearch', ''),
        ('WebSearch/WebFetch', 'pesquisa pública'),
        ('WebFetch', 'pesquisa pública'),
        ('WebSearch', 'pesquisa pública'),
        ('HubSpot', 'formulário'),
        ('lifecyclestage', 'etapa'),
        ('ICP Zydon', 'perfil ideal da Zydon'),
        ('ICP', 'perfil ideal'),
        ('MQL', 'qualificado'),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    text = re.sub(r'\s+', ' ', text).strip(' :-')
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(' ', 1)[0]
    return cut.rstrip('.,;:') + '...'


def group_reason_bullets(research, mql=True):
    """Resumo objetivo para pessoas de negócio no grupo, com quebra de linha."""
    bullets = []
    segmento = business_clean(research.get('segmento'), 120)
    dominio = business_clean(research.get('dominio_site'), 130)
    redes = business_clean(research.get('redes'), 110)
    insight = business_clean(research.get('insight'), 130)
    motivo = business_clean(research.get('motivo'), 220)

    if mql:
        if segmento:
            bullets.append(f'• Perfil aderente: {segmento}')
        if dominio:
            bullets.append(f'• Empresa validada: {dominio}')
        elif redes:
            bullets.append(f'• Presença pública validada: {redes}')
        if insight:
            bullets.append(f'• Oportunidade: {insight}')
        if not bullets and motivo:
            bullets.append(f'• {motivo}')
    else:
        if motivo:
            bullets.append(f'• {motivo}')
        elif segmento:
            bullets.append(f'• Fora do perfil ideal: {segmento}')
        if dominio and len(bullets) < 3:
            bullets.append(f'• Evidência pública: {dominio}')
    return '\n'.join(bullets[:3])


def upload_pdf_to_hubspot(pdf_path, slug):
    """Sobe PDF ao HubSpot Files e retorna file_id. Requer scopes files/files.ui_hidden.write."""
    pdf_path=str(pdf_path)
    if not os.path.exists(pdf_path):
        return None, f'PDF não encontrado: {pdf_path}'
    boundary='----zydonpdf'+re.sub(r'[^a-zA-Z0-9]','',slug)[:24]
    filename=os.path.basename(pdf_path)
    def part(name, value, filename=None, ctype=None):
        head=f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        if filename:
            head += f'; filename="{filename}"'
        head += '\r\n'
        if ctype:
            head += f'Content-Type: {ctype}\r\n'
        head += '\r\n'
        if isinstance(value, str):
            value=value.encode('utf-8')
        return head.encode('utf-8') + value + b'\r\n'
    try:
        file_bytes=Path(pdf_path).read_bytes()
        body=b''.join([
            part('file', file_bytes, filename, 'application/pdf'),
            part('folderPath', '/zydon-diagnosticos'),
            # Sem Content-Type JSON o HubSpot pode ignorar `options` e subir PRIVATE,
            # o que gera link 404/quebrado na task. Sempre validar após upload.
            part('options', json.dumps({'access':'PUBLIC_NOT_INDEXABLE'}), ctype='application/json'),
            f'--{boundary}--\r\n'.encode('utf-8'),
        ])
        req=urllib.request.Request(
            'https://api.hubapi.com/files/v3/files', data=body,
            headers={'Authorization':'Bearer '+TOK, 'Content-Type':f'multipart/form-data; boundary={boundary}'},
            method='POST')
        with urllib.request.urlopen(req, timeout=120) as resp:
            data=json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            data=json.loads(e.read().decode(errors='replace'))
        except Exception:
            return None, f'HubSpot Files HTTP {e.code}'
    except Exception as e:
        return None, f'erro upload HubSpot Files: {e}'
    if data.get('id'):
        file_id=str(data['id'])
        try:
            meta=hubspot_file_meta(file_id)
            if meta.get('access') != 'PUBLIC_NOT_INDEXABLE':
                return None, f"HubSpot Files subiu como {meta.get('access') or 'sem access'}; link público não confiável"
            url=meta.get('defaultHostingUrl') or meta.get('url') or ''
            if not url:
                return None, 'HubSpot Files sem URL pública após upload'
        except Exception as e:
            return None, f'erro validando arquivo HubSpot Files {file_id}: {e}'
        return file_id, None
    if data.get('category') == 'MISSING_SCOPES':
        return None, 'HubSpot PAT sem scope files/files.ui_hidden.write para anexar PDF'
    return None, 'HubSpot Files upload sem id: '+json.dumps(data, ensure_ascii=False)[:500]

def generate_pdf(lead, research, sdr):
    sys.path.insert(0, str(MOTOR))
    from batch_prepare import build_lead_dict
    import gen as gen_module
    props=lead['properties']; company=(props.get('company') or lead.get('company') or '').strip()
    def first_prop(*keys, default=''):
        for key in keys:
            val = props.get(key)
            if val not in (None, ''):
                return val
        return default
    phone=lead.get('phone') or props.get('hs_searchable_calculated_phone_number') or props.get('phone')
    raw={
      'name': (props.get('firstname') or lead.get('firstname') or 'Contato'),
      'empresa': company,
      'fantasia': company,
      'erp': props.get('qual_erp_utiliza_') or props.get('selecione_o_sistema_de_gesto_erp') or 'Outro',
      'faturamento': first_prop('qual_o_faturamento_anual_da_sua_empresa_', 'e_qual_faturamento_anual_da_sua_empresa', 'selecione_a_faixa_de_faturamento', 'selecione_a_faixa_de_faturamento_atual_por_ano_da_sua_empresa', default='Estimativa: não informado'),
      'resposta': first_prop('de_qual_forma_mais_vende_hoje_em_dia', default='Estimativa: não informado'),
      'dor': first_prop('qual_seria_o_maior_problema', 'principais_dores', 'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente', 'de_qual_forma_mais_vende_hoje_em_dia'),
      'telefone': phone, 'email': lead['email'], 'owner_name': sdr,
      'vendedores': first_prop('quantos_vendedores_internos', 'quantos_vendedores_internos_sua_empresa_possui', default='Estimativa: 1 a 3'),
      'pessoas': props.get('quantas_pessoas_atuam_na_sua_empresa') or 'Estimativa: 10 a 20',
      'loja': props.get('vende_em_loja_virtual_') or 'Não informado',
      'autosservico': first_prop('voc_acredita_que_o_seu_cliente_compraria_sozinho', 'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor', default='Estimativa: sim, para pedidos recorrentes'),
      'cargo_area': first_prop('qual_a_rea_de_atuao_de_sua_empresa', 'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados', 'qual_a_area_de_atuacao_de_sua_empresa_', default=research['segmento']),
      'vende_para': first_prop('voc_vende_para_quem', 'voc_vende_para_quem_ex_padarias_restaurantes_petshop_autopeas_supermercados', default='Clientes B2B do atacado/distribuição'),
    }
    d=build_lead_dict(raw)
    d['slug']=research['slug']
    d['empresa']=company or research['empresa_real']
    d['site']=research['dominio_site'].split()[0]
    d['sobre']=f"{research['empresa_real']} atua em {research['segmento']}. Pesquisa pública: {research['dominio_site']}; {research['redes']}. Pelo diagnóstico, opera com {raw['resposta']} e tem faixa de faturamento {raw['faturamento']}."
    d['sobre_fonte']='Pesquisa web + diagnóstico HubSpot'
    d['vende_para']=raw['vende_para']
    d['como_vende']=raw['resposta']
    d['loja_virtual']=raw['loja']
    d['time_total']=raw['pessoas'].replace('_',' a ')
    d['compra_sozinho']=raw['autosservico']
    d['encontramos']=[
      'Catálogo B2B para o cliente pedir sozinho entre uma visita e outra',
      'Regras comerciais por cliente e região para reduzir retrabalho do representante',
      'Canal digital próprio para transformar visitas presenciais em recompra recorrente'
    ]
    d['significa']='A equipe comercial mantém o relacionamento, mas deixa de carregar pedidos manuais repetitivos. O cliente ganha autonomia e a operação escala sem depender de mais visitas presenciais.'
    d['detalhe']=research['motivo']
    html=gen_module.build_html(d).replace('A confirmar','Estimativa: não informado')
    html_path=MOTOR/f"{d['slug']}.html"; html_path.write_text(html, encoding='utf-8')
    if 'A confirmar' in html:
        raise RuntimeError('HTML ainda contém A confirmar')
    pdf_path=PDFS/f"Potencial-Digitalizacao-{d['slug']}.pdf"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b=p.chromium.launch(); pg=b.new_page(); pg.set_content(html, wait_until='networkidle')
            pg.pdf(path=str(pdf_path), width='210mm', height='297mm', print_background=True, margin={'top':'0','bottom':'0','left':'0','right':'0'})
            b.close()
    except ModuleNotFoundError:
        import glob
        chrome = next(iter(glob.glob('/root/.cache/ms-playwright/chromium-*/chrome-linux*/chrome')), None)
        if not chrome:
            raise RuntimeError('Nem playwright Python nem Chromium em cache encontrados para renderizar PDF')
        subprocess.run([
            chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
            '--no-pdf-header-footer', '--print-to-pdf-no-header',
            '--print-to-pdf=' + str(pdf_path), 'file://' + str(html_path),
        ], check=True, capture_output=True)
    safe_company=re.sub(r'[\\/]+','-', company or research['empresa_real']).strip()
    pretty=PDFS/f"{safe_company} - Potencial de Digitalizacao B2B.pdf"
    shutil.copy(pdf_path, pretty)
    return d['slug'], str(pdf_path), str(pretty)

def gen_thumb(pdf, slug):
    """Gera thumbnail ~320px sem depender de pdftoppm/convert (usa PyMuPDF+Pillow)."""
    try:
        import fitz
        from PIL import Image
        thumb=f'/tmp/{slug}_thumb.jpg'
        doc = fitz.open(pdf)
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        img.thumbnail((320, 320))
        img.save(thumb, 'JPEG', quality=70, optimize=True)
        doc.close()
        return thumb
    except ModuleNotFoundError:
        import glob
        thumb=f'/tmp/{slug}_thumb.png'
        chrome = next(iter(glob.glob('/root/.cache/ms-playwright/chromium-*/chrome-linux*/chrome')), None)
        html_path = MOTOR/f'{slug}.html'
        if not chrome or not html_path.exists():
            raise RuntimeError('Sem dependências para gerar thumbnail do PDF')
        subprocess.run([
            chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
            '--window-size=320,453', '--screenshot=' + thumb, 'file://' + str(html_path),
        ], check=True, capture_output=True)
        return thumb

def save_research(email, lead, research):
    PESQ.mkdir(exist_ok=True); PDFS.mkdir(exist_ok=True)
    (PESQ/(research['slug']+'.md')).write_text('\n'.join([
      f"# {lead.get('company') or (lead.get('properties') or {}).get('company')}",
      f"Email: {email}", f"Empresa real: {research['empresa_real']}", f"Domínio/site: {research['dominio_site']}", f"Redes: {research['redes']}", f"Segmento: {research['segmento']}", f"MQL: {research['mql']}", f"Motivo: {research['motivo']}", f"Insight: {research['insight']}",
    ]), encoding='utf-8')
    (PESQ/(research['slug']+'_hubspot.json')).write_text(json.dumps(lead, ensure_ascii=False, indent=2), encoding='utf-8')

GLOBAL_SEND_LOCK = '/tmp/zydon_external_whatsapp_send.lock'
_GLOBAL_LOCK_FH = None


def acquire_global_send_lock(blocking=True):
    """Lock global entre diagnóstico/PDF e primeiro contato SDR.

    Evita que dois crons externos decidam/enviem WhatsApp para o mesmo lead no
    mesmo intervalo antes do ledger ser atualizado.
    """
    global _GLOBAL_LOCK_FH
    _GLOBAL_LOCK_FH = open(GLOBAL_SEND_LOCK, 'w')
    flags = 0 if blocking else fcntl.LOCK_NB
    try:
        fcntl.flock(_GLOBAL_LOCK_FH, fcntl.LOCK_EX | flags)
    except BlockingIOError:
        return False
    _GLOBAL_LOCK_FH.write(f"process_gate_once pid={os.getpid()} at={datetime.now(timezone.utc).isoformat()}\n")
    _GLOBAL_LOCK_FH.flush()
    def _release():
        try:
            fcntl.flock(_GLOBAL_LOCK_FH, fcntl.LOCK_UN)
            _GLOBAL_LOCK_FH.close()
        except Exception:
            pass
    atexit.register(_release)
    return True


def main():
    if not acquire_global_send_lock(blocking=True):
        print('[SILENT]')
        return
    gate=json.loads(GATE.read_text())
    reports=[]; envios=load_wpp(); processed=load_processed()
    for lead in gate.get('leads',[]):
        email=lead['email'].lower(); props=lead['properties']; cid=str(lead['id']); phone=lead.get('phone') or props.get('hs_searchable_calculated_phone_number') or props.get('phone')
        r=RESEARCH.get(email)
        if not r:
            reports.append(f'{email} | ERRO sem pesquisa Claude')
            continue
        save_research(email, lead, r)
        processed_at = processed.get(email)
        recent_at = parse_hs_dt(props.get('recent_conversion_date'))
        created_at = parse_hs_dt(props.get('createdate') or lead.get('createdate'))
        is_reentry = bool(recent_at and created_at and (recent_at - created_at).total_seconds() > 300 and (processed_at is None or recent_at > processed_at))
        if email in processed and not is_reentry:
            continue
        # Crivo Rafael: pesquisa pode sugerir MQL, mas o script só marca MQL se passar
        # ICP T1 B2B de alto giro/abastecimento (indústria/distribuidor/importador/atacado
        # vendendo para revendas/lojas/clientes recorrentes). Fail-closed.
        strict_ok, strict_reason = strict_icp_check(props, r) if r.get('mql') else (False, 'pesquisa classificou como não-MQL')
        if r.get('mql') and not strict_ok:
            r = dict(r)
            r['mql'] = False
            r['motivo'] = (r.get('motivo') or '') + f' | Reprovado no crivo MQL acirrado: {strict_reason}'
            r['insight'] = ''
        elif r.get('mql'):
            r = dict(r)
            r['motivo'] = (r.get('motivo') or '') + f' | Crivo MQL acirrado: {strict_reason}'
        # Qualificação e lifecycle rápido
        lifecycle_before=(props.get('lifecyclestage') or '')
        lifecycle_mark='não'
        if r['mql'] and lifecycle_before.lower()!='marketingqualifiedlead':
            try:
                patch_contact(cid, {'lifecyclestage':'marketingqualifiedlead'}); lifecycle_mark='sim'
            except Exception as e:
                # HubSpot pode bloquear downgrade de estágios posteriores (ex.: opportunity -> MQL).
                # Não abortar o ciclo: registrar e seguir, porque o contato já está em estágio comercial posterior.
                lifecycle_mark=f'não alterado ({lifecycle_before or "vazio"}; erro HubSpot: {str(e)[:180]})'
        elif r['mql']:
            lifecycle_mark='já era MQL'
        # agenda=owner
        owner_actions=sync_agenda_owner(cid)
        fresh=get_contact(cid)
        contact_owner=((fresh.get('properties') or {}).get('hubspot_owner_id') or props.get('hubspot_owner_id') or '')
        deals=contact_deals(cid)
        owner, business_owner_notes = resolve_business_owner(cid, deals, contact_owner)
        owner_actions += business_owner_notes
        company=(props.get('company') or lead.get('company') or r.get('empresa_real') or '').strip()
        if not r['mql']:
            # Não-MQL: avisa o grupo SEMPRE pela Mariana/porta 4600, ignorando o hubspot_owner_id do lead.
            invalid_stage_actions = []
            invalid_stage_line = ''
            if not lead.get('phone_valid', True):
                invalid_reason = lead.get('phone_invalid_reason') or 'sem contato/WhatsApp válido'
                invalid_stage_actions = move_deals_to_invalid_stage(deals, invalid_reason)
                owner_actions += invalid_stage_actions
                invalid_stage_line = 'Fase HubSpot: Leads Inválidos\n'
            port, ok, me, offline_detail = pick_online_port(NON_MQL_NOTIFY_OWNER, envios)
            if ok:
                notify_info = INSTITUTIONAL_PORTS.get(port, NON_MQL_NOTIFY_OWNER)
            if not ok:
                reports.append(f"{r['slug']} | MQL não | lifecycle não alterado | owner sync: {'; '.join(owner_actions)} | ERRO bridge institucional offline para grupo ({offline_detail or me})")
                continue
            text=(f"❌ Lead não qualificado\n"
                  f"Empresa: {company}\n"
                  f"Contato: {props.get('firstname') or ''}\n"
                  f"Email: {email}\n"
                  f"{group_erp_line(props)}"
                  f"Entrada: {fmt_created_brt(props.get('recent_conversion_date') or props.get('createdate') or lead.get('createdate'))}\n"
                  f"Criativo/origem: {traffic_creative_line(props)}\n"
                  f"{invalid_stage_line}\n"
                  f"Por que não qualificou:\n{group_reason_bullets(r, mql=False)}\n\n"
                  f"Responsável: sem responsável comercial")
            resp=post_bridge(port,'/send', {'to':GROUP,'text':text})
            # Task de não-MQL NÃO é atribuída ao SDR (owner do lead); usa o owner de notificação (Mariana).
            task_body = text + (("\n\nHubSpot: " + '; '.join(invalid_stage_actions)) if invalid_stage_actions else '')
            tid=create_task(cid, deals, "Qualificação Zydon — lead não-MQL", task_body, NON_MQL_NOTIFY_OWNER['owner_id'])
            append_processed(email, r['slug'], 'nao_mql_grupo', phone, company)

            # Regra do ciclo autônomo atual: Não-MQL NÃO recebe mensagem externa.
            # Apenas resumo interno no grupo + task de qualificação.
            outreach_summary = 'não enviado ao lead; somente aviso interno conforme regra do ciclo'
            envios.append({'date': datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M'), 'email':email, 'slug':r['slug'], 'status':'nao_mql_grupo', 'to':GROUP, 'bridge_port':port, 'response':resp, 'task_id':tid, 'hubspot_invalid_stage_actions': invalid_stage_actions, 'non_mql_outreach': outreach_summary})
            reports.append(f"{r['slug']} | MQL não | lifecycle não alterado ({lifecycle_before or 'vazio'}) | owner sincronizado: {'; '.join(owner_actions)} | grupo interno enviado; sem contato ao lead")
            continue
        if not lead.get('phone_valid', True):
            local_variants = phone_variants_with_optional_9(phone or props.get('phone') or props.get('mobilephone') or props.get('hs_searchable_calculated_phone_number'))
            preferred_local = next((v for v in local_variants if len(only_digits(v)) == 13 and only_digits(v)[4] == '9'), None) or (local_variants[0] if local_variants else '')
            if preferred_local:
                phone = preferred_local
                lead['phone_valid'] = True
                props['phone'] = phone
                props['hs_searchable_calculated_phone_number'] = phone
                source_note = f"telefone ajustado por variação com/sem 9 após DDD antes de invalidar: {phone}"
                owner_actions.append(source_note)
                r = dict(r)
                r['motivo'] = (r.get('motivo') or '') + f" | {source_note}"
                try:
                    patch_contact(cid, {'phone': phone})
                except Exception as e:
                    owner_actions.append(f"não consegui atualizar telefone HubSpot: {str(e)[:120]}")
            else:
                public_phone = lookup_public_phone(email, company, r)
                if public_phone:
                    phone = public_phone['phone']
                    lead['phone_valid'] = True
                    props['phone'] = phone
                    props['hs_searchable_calculated_phone_number'] = phone
                    source_note = f"telefone público recuperado: {phone} (fonte: {public_phone['source']}; bruto: {public_phone['raw']})"
                    owner_actions.append(source_note)
                    r = dict(r)
                    r['motivo'] = (r.get('motivo') or '') + f" | {source_note}"
                    try:
                        patch_contact(cid, {'phone': phone})
                    except Exception as e:
                        owner_actions.append(f"não consegui atualizar telefone HubSpot: {str(e)[:120]}")
                else:
                    # MQL com telefone inválido/fixo: não tentar WhatsApp ao lead, mas avisar o grupo.
                    port, ok, me, offline_detail = pick_online_port(NON_MQL_NOTIFY_OWNER, envios)
                    if not ok:
                        reports.append(f"{r['slug']} | MQL sim | lifecycle {lifecycle_mark} | telefone inválido | ERRO bridge institucional offline para grupo ({offline_detail or me})")
                        continue
                    first_parts = (props.get('firstname') or lead.get('firstname') or '').split()
                    first = first_parts[0] if first_parts else 'Contato'
                    invalid_reason = lead.get('phone_invalid_reason') or 'telefone inválido/fixo'
                    invalid_stage_actions = move_deals_to_invalid_stage(deals, invalid_reason)
                    owner_actions += invalid_stage_actions
                    raw_phone = phone or 'não informado'
                    group_summary=(f"✅ Lead qualificado — telefone inválido/fixo\n"
                                   f"Empresa: {company}\n"
                                   f"Contato: {first}\n"
                                   f"Email: {email}\n"
                                   f"{group_erp_line(props)}"
                                   f"Entrada: {fmt_created_brt(props.get('recent_conversion_date') or props.get('createdate') or lead.get('createdate'))}\n"
                                   f"Criativo/origem: {traffic_creative_line(props)}\n"
                                   f"Telefone informado: {raw_phone} — {invalid_reason}\n"
                                   f"Busca pública: não encontrei WhatsApp/telefone público seguro para envio automático\n"
                                   f"Fase HubSpot: Leads Inválidos\n\n"
                                   f"Por que qualificou:\n{group_reason_bullets(r, mql=True)}\n\n"
                                   f"Responsável: {OWNER_MAP.get(owner, {}).get('nome') or 'consultor responsável'}\n"
                                   f"Diagnóstico: pendente até confirmar WhatsApp válido")
                    resp=post_bridge(port,'/send', {'to':GROUP,'text':group_summary})
                    tid=create_task(cid, deals, "Qualificação Zydon — MQL com telefone inválido/fixo", group_summary + "\n\nHubSpot: " + '; '.join(invalid_stage_actions), owner or None)
                    append_processed(email, r['slug'], 'mql_telefone_invalido_grupo', phone, company)
                    envios.append({'date': datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M'), 'email':email, 'slug':r['slug'], 'status':'mql_telefone_invalido_grupo', 'to':GROUP, 'bridge_port':port, 'owner_id':owner, 'phone':phone, 'phone_invalid_reason':invalid_reason, 'hubspot_invalid_stage_actions':invalid_stage_actions, 'public_phone_lookup':'not_found', 'group_summary':group_summary, 'response':resp, 'task_id':tid})
                    reports.append(f"{r['slug']} | MQL sim | lifecycle {lifecycle_mark} | telefone inválido/fixo | busca pública sem achado seguro | Leads Inválidos: {'; '.join(invalid_stage_actions)} | só-grupo")
                    continue
        # MQL: gerar o PDF antes de decidir remetente para dar tempo da automação do HubSpot
        # propagar hubspot_owner_id após lifecyclestage=MQL. Depois do PDF, reler owner.
        slug,pdf,pretty=generate_pdf(lead, r, 'Zydon')
        # PDF gera um buffer inicial, mas nem sempre basta: aguardar explicitamente
        # a criação/atribuição do negócio para capturar o DONO DO NEGÓCIO e agenda correta.
        owner, deals, wait_owner_notes = wait_for_business_owner(cid, owner, timeout_sec=300, interval_sec=15)
        owner_actions += wait_owner_notes
        # Regra Rafael 23/06:
        # - Em horário comercial BRT (seg-sex 07:00-18:00), se o lead já tiver SDR dono,
        #   o diagnóstico para o LEAD sai pelo telefone do SDR dono para evitar duas pessoas
        #   chamando o lead ao mesmo tempo (automação de follow-up separada).
        # - Telefones institucionais (Mariana/Rafael/Lucas Resende) só entram em situação de fallback:
        #   sem dono, fora da janela SDR, ou SDR dono offline/falha de envio.
        # - O GRUPO sempre recebe alerta pela rotação institucional.
        hubspot_owner_info=OWNER_MAP.get(owner)
        original_sdr = hubspot_owner_info['nome'] if hubspot_owner_info else None
        use_sdr_for_lead = bool(hubspot_owner_info) and is_work_hours_brt()
        if use_sdr_for_lead:
            lead_owner_info=hubspot_owner_info
            port, ok, me, offline_detail = pick_online_port(lead_owner_info, envios)
            if ok:
                owner_info=lead_owner_info; sdr=owner_info['nome']; consultant_fallback=False
                # Quando o diagnóstico sai pelo próprio SDR dono, a mensagem deve falar em
                # primeira pessoa ("eu te chamo/sigo contigo"), porque quem escreve já é o SDR.
                # Só comunicadores institucionais (Mariana/Lucas Resende/Rafael) devem dizer
                # que Sarah/Breno/Lucas Batista vai chamar.
                fallback_note=f'envio ao lead pelo SDR dono em horário comercial BRT; grupo institucional; texto em 1ª pessoa do próprio SDR'
            else:
                # Regra Rafael 24/06: nossos telefones/institucionais só entram em fallback.
                # Se o SDR dono estiver offline no horário comercial, usar rotação institucional
                # explicitamente registrada como fallback (não como rota principal).
                owner_info=DEFAULT_OWNER; sdr=owner_info['nome']
                port, ok, me, offline_detail = pick_online_port(owner_info, envios)
                if ok:
                    inst_info = INSTITUTIONAL_PORTS.get(port, {'nome':'Institucional', 'assinatura':owner_info['assinatura']})
                    owner_info = {**owner_info, **inst_info, 'porta': port}
                    sdr = owner_info['nome']
                consultant_fallback=True
                fallback_note=f'FALLBACK institucional: SDR dono {original_sdr} offline/indisponível em horário comercial ({offline_detail or me})'
        else:
            owner_info=DEFAULT_OWNER; sdr=owner_info['nome']
            port, ok, me, offline_detail = pick_online_port(owner_info, envios)
            if ok:
                inst_info = INSTITUTIONAL_PORTS.get(port, {'nome':'Institucional', 'assinatura':owner_info['assinatura']})
                owner_info = {**owner_info, **inst_info, 'porta': port}
                sdr = owner_info['nome']
            fallback_note=f'owner HubSpot: {original_sdr}; envio ao lead pela rotação institucional' if original_sdr else 'envio ao lead pela rotação institucional'
            consultant_fallback=True
        if not ok:
            reports.append(f"{r['slug']} | MQL sim | lifecycle {lifecycle_mark} | owner sincronizado: {'; '.join(owner_actions)} | ERRO sem remetente online para lead ({offline_detail or me})")
            continue
        port_ok, port_reason = port_within_external_limits(load_wpp(), port)
        if not port_ok:
            reports.append(f"{r['slug']} | MQL sim | lifecycle {lifecycle_mark} | PULADO limite global do chip antes do diagnóstico ({port_reason})")
            continue
        thumb=gen_thumb(pdf, slug)
        greeting=br_greeting(); timing=timing_first_person(); first=(props.get('firstname') or lead.get('firstname') or '').strip().split()
        first = first[0] if first else ''
        if consultant_fallback:
            timing=fallback_timing_for_owner(original_sdr)
        agenda_url = (hubspot_owner_info or {}).get('agenda')
        agenda_line = f"\nSe quiser adiantar e já garantir o melhor horário para atendimento, pode marcar direto aqui: {agenda_url}" if agenda_url else ''
        greeting_line = f"{greeting}, {first}, tudo bem?" if first else f"{greeting}, tudo bem?"
        msg=(f"{greeting_line} {owner_info['assinatura']}.\n"
             f"Fizemos uma leitura da operação da {company} e montei um diagnóstico em PDF com oportunidades bem práticas de digitalização B2B.\n"
             f"O ponto que mais chamou atenção foi: dá pra {r['insight']}.\n"
             f"Te mandei o PDF aqui porque acho que vai fazer sentido para vocês. {timing} para conversar sobre isso e ver onde está o maior ganho. Pode ser?{agenda_line}")
        (PESQ/(slug+'_msg.txt')).write_text(msg, encoding='utf-8')
        phone_variants = phone_variants_with_optional_9(phone) or [only_digits(phone)]
        jid = jid_from_phone(phone_variants[0])
        resp1, lead_text_attempts = post_bridge_with_retries(port,'/send', {'to':jid,'text':msg}, attempts=3, delay=12)
        if not message_ok(resp1) and len(phone_variants) > 1:
            variant_errors = [{'jid': jid, 'resp': resp1}]
            for alt_phone in phone_variants[1:]:
                alt_jid = jid_from_phone(alt_phone)
                alt_resp, alt_attempts = post_bridge_with_retries(port,'/send', {'to':alt_jid,'text':msg}, attempts=2, delay=10)
                lead_text_attempts += alt_attempts
                if message_ok(alt_resp):
                    jid = alt_jid
                    phone = alt_phone
                    resp1 = alt_resp
                    owner_actions.append(f'envio WhatsApp funcionou com variação com/sem 9: {phone}')
                    try:
                        patch_contact(cid, {'phone': phone})
                    except Exception as e:
                        owner_actions.append(f"não consegui atualizar telefone HubSpot após variação: {str(e)[:120]}")
                    break
                variant_errors.append({'jid': alt_jid, 'resp': alt_resp})
            if not message_ok(resp1):
                owner_actions.append(f'variações com/sem 9 também falharam: {variant_errors}')
        if not message_ok(resp1) and owner_info is not DEFAULT_OWNER:
            # Nossos telefones/institucionais só entram como fallback: se o envio pelo SDR dono falhar
            # antes de gerar messageId/status, tenta rotação institucional e registra o motivo.
            fallback_resp = {'final': resp1, 'attempts': lead_text_attempts}
            inst_port, inst_ok, inst_me, inst_offline = pick_online_port(DEFAULT_OWNER, envios)
            if inst_ok:
                inst_limit_ok, inst_limit_reason = port_within_external_limits(load_wpp(), inst_port)
                if not inst_limit_ok:
                    reports.append(f"{slug} | MQL sim | lifecycle {lifecycle_mark} | fallback institucional bloqueado por limite global do chip ({inst_limit_reason})")
                    continue
                inst_info = INSTITUTIONAL_PORTS.get(inst_port, {'nome':'Institucional', 'assinatura':DEFAULT_OWNER['assinatura']})
                owner_info = {**DEFAULT_OWNER, **inst_info, 'porta': inst_port}
                port = inst_port
                sdr = owner_info['nome']
                fallback_note = (fallback_note + f'; fallback institucional após falha no envio SDR: {fallback_resp}') if fallback_note else f'fallback institucional após falha no envio SDR: {fallback_resp}'
                timing = fallback_timing_for_owner(original_sdr)
                msg=(f"{greeting_line} {owner_info['assinatura']}.\n"
                     f"Fizemos uma leitura da operação da {company} e montei um diagnóstico em PDF com oportunidades bem práticas de digitalização B2B.\n"
                     f"O ponto que mais chamou atenção foi: dá pra {r['insight']}.\n"
                     f"Te mandei o PDF aqui porque acho que vai fazer sentido para vocês. {timing} para conversar sobre isso e ver onde está o maior ganho. Pode ser?{agenda_line}")
                (PESQ/(slug+'_msg.txt')).write_text(msg, encoding='utf-8')
                resp1, fallback_text_attempts = post_bridge_with_retries(port,'/send', {'to':jid,'text':msg}, attempts=2, delay=10)
        if not message_ok(resp1):
            reports.append(f"{slug} | MQL sim | lifecycle {lifecycle_mark} | owner sincronizado | ERRO texto lead sem messageId/status: {resp1}"); continue
        # Rafael pediu em 24/06: deixar o envio parecer natural.
        # Primeiro manda o texto, espera pelo menos 1 minuto, depois manda o PDF.
        time.sleep(60)
        resp2, lead_file_attempts = post_bridge_with_retries(port,'/send-file', {'to':jid,'filePath':pretty,'fileName':f'{company} - Potencial de Digitalizacao B2B.pdf','thumbnailPath':thumb}, attempts=3, delay=12)
        if not message_ok(resp2):
            reports.append(f"{slug} | MQL sim | lifecycle {lifecycle_mark} | owner sincronizado | ERRO PDF lead sem messageId/status após retentativas: {lead_file_attempts}"); continue
        # grupo: NÃO recebe o texto do lead nem PDF — apenas resumo curto de status (sem send-file)
        group_summary=(f"✅ Lead qualificado\n"
                       f"Empresa: {company}\n"
                       f"Contato: {first}\n"
                       f"Email: {email}\n"
                       f"{group_erp_line(props)}"
                       f"Entrada: {fmt_created_brt(props.get('recent_conversion_date') or props.get('createdate') or lead.get('createdate'))}\n"
                       f"Criativo/origem: {traffic_creative_line(props)}\n\n"
                       f"Por que qualificou:\n{group_reason_bullets(r, mql=True)}\n\n"
                       f"Responsável: {original_sdr or 'consultor responsável'}\n"
                       f"Diagnóstico enviado por: {sdr}")
        group_port, g_resp, group_attempts = post_group_with_rotation(group_summary, envios)
        # Upload no HubSpot usa o arquivo canônico sem acentos/espaços no nome.
        # O arquivo bonito (`pretty`) continua sendo usado só no WhatsApp para o lead.
        file_id, upload_err = upload_pdf_to_hubspot(pdf, slug)
        task_body = f'Enviado texto + PDF para {jid} pela porta {port} ({sdr}).'
        file_url = hubspot_file_url(file_id) if file_id else ''
        if file_id:
            task_body += f'\nPDF do diagnóstico: {file_url}' if file_url else ''
            task_body += f'\nArquivo anexado no HubSpot Files: {file_id}.'
        elif upload_err:
            task_body += f'\nPDF salvo local/Drive, mas não anexado no HubSpot: {upload_err}.'
        tid=create_task(cid, deals, "WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead.", task_body, owner or None, [file_id] if file_id else None)
        append_processed(email, slug, 'enviado_lead', phone, company)
        envios.append({'date': datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M'), 'email':email, 'slug':slug, 'status':'enviado_lead', 'to':jid, 'group':GROUP, 'bridge_port':port, 'group_bridge_port': group_port if 'group_port' in locals() else None, 'owner_id':owner, 'fallback_note': fallback_note, 'text': msg, 'group_summary': group_summary, 'pdf_path': str(pretty), 'hubspot_file_id': file_id, 'hubspot_file_error': upload_err, 'text_response':resp1, 'file_response':resp2, 'group_summary_response':g_resp, 'task_id':tid})
        reports.append(f"{slug} | MQL sim | lifecycle {lifecycle_mark} | owner sincronizado: {'; '.join(owner_actions)} | disparado ({sdr}/porta {port})" + (f" | {fallback_note}" if fallback_note else ""))
        time.sleep(1)
    save_wpp(envios)
    print('\n'.join(reports) if reports else '[SILENT]')

if __name__ == '__main__':
    main()
