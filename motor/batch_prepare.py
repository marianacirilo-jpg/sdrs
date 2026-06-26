#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MOTOR_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / 'outputs'
os.makedirs(OUT_DIR, exist_ok=True)

text = open(MOTOR_DIR / 'message.txt', 'r', encoding='utf-8').read()
lines = [l.strip() for l in text.splitlines() if l.strip()]

owner_pattern = re.compile(r'^[A-Za-zÀ-ú\s\(\)]+\([a-z0-9._%+-]+@zydon\.com\.br\)$')
date_pattern = re.compile(r'^(Hoje|Ontem) às \d{2}:\d{2} GMT-3$')

owner_names = {
    'lucas.batista@zydon.com.br': 'Lucas',
    'sarah.bento@zydon.com.br': 'Sarah',
    'breno.mendonca@zydon.com.br': 'Breno',
    'cayo.cavalcante@zydon.com.br': 'Cayo'
}

leads = []
current = None
for line in lines:
    if owner_pattern.match(line):
        if current and current.get('name'):
            leads.append(current)
        email = re.search(r'\(([^)]+)\)', line).group(1)
        current = {'owner_email': email, 'owner_name': owner_names.get(email, 'Responsável')}
    elif date_pattern.match(line):
        if current is None:
            current = {}
        current['data'] = line
    else:
        if current is None:
            current = {}
        if 'name' not in current:
            current['name'] = line
        elif 'empresa' not in current:
            current['empresa'] = line
        elif 'erp' not in current:
            current['erp'] = line
        elif 'fantasia' not in current:
            current['fantasia'] = line
        elif 'faturamento' not in current:
            current['faturamento'] = line
        elif 'resposta' not in current:
            current['resposta'] = line
        elif 'dor' not in current:
            current['dor'] = line
        elif 'telefone' not in current:
            current['telefone'] = line
        elif 'fonte' not in current:
            current['fonte'] = line
        elif 'telefone2' not in current:
            current['telefone2'] = line
        elif 'email' not in current:
            current['email'] = line
        else:
            current.setdefault('extra', []).append(line)
if current and current.get('name'):
    leads.append(current)

leads = [l for l in leads if l.get('empresa','').lower() != 'topcolors' and l.get('name','').lower() != 'tiago ferraresi']

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text, flags=re.UNICODE)
    text = text.strip('-')
    if not text:
        text = 'empresa'
    return text

def infer_local(phone):
    if not phone:
        return 'Brasil'
    m = re.search(r'\+55-(\d{2})', phone)
    if m:
        ddd = m.group(1)
        ddd_map = {
            '11':'São Paulo, SP','21':'Rio de Janeiro, RJ','31':'Belo Horizonte, MG',
            '41':'Curitiba, PR','51':'Porto Alegre, RS','61':'Brasília, DF','71':'Salvador, BA',
            '85':'Fortaleza, CE'
        }
        return ddd_map.get(ddd, f'DDD {ddd}')
    return 'Brasil'

def infer_cargo_area(empresa, dor):
    e = (empresa or '').lower()
    d = (dor or '').lower()
    if 'hotel' in e:
        return 'Hotelaria / Hospitalidade'
    if 'suprimento' in e or 'indústria' in e:
        return 'Indústria / Suprimentos'
    if 'distribuidor' in e or 'atacad' in e:
        return 'Atacado / Distribuição'
    if 'social' in e or 'traje' in e:
        return 'Moda / Confecção'
    if 'cosmético' in e or 'beleza' in e:
        return 'Cosméticos'
    if 'engenharia' in e or 'obra' in e:
        return 'Engenharia / Construção'
    if 'solda' in e or 'metal' in e:
        return 'Metalurgia / Solda'
    if 'plástico' in e:
        return 'Plásticos / Injeção'
    if 'odontol' in e or 'dental' in e:
        return 'Distribuição odontológica'
    if 'segurança' in e or 'monitoramento' in e:
        return 'Segurança eletrônica'
    if 'shopp' in e or 'varejo' in e:
        return 'Varejo / Shopping'
    return 'B2B'

def build_lead_dict(lead):
    name = lead.get('name','')
    empresa = lead.get('empresa','')
    erp = lead.get('erp','Outro')
    fantasia = lead.get('fantasia', empresa)
    faturamento = lead.get('faturamento','A confirmar')
    resposta = lead.get('resposta','A confirmar')
    dor = lead.get('dor','')
    telefone = lead.get('telefone','')
    email = lead.get('email','')
    owner = lead.get('owner_name','Responsável')

    cleaned = re.sub(r'[^A-Za-zÀ-ú\s]', '', name).strip()
    primeiro_nome = cleaned.split()[0] if cleaned else 'Contato'

    site = ''
    if email and '@' in email:
        domain = email.split('@')[1]
        site = domain.replace('www.','').replace('.com.br','').replace('.com','')

    empurra_keywords = ['empurrar','empurra','vendedor','visita','orçamento','preço','tentar digitalizar','dificuldade_escalar','falta_controle','carteira_parada']
    puxa_keywords = ['contrato','recorrência','giro','fidelidade','auto-atendimento','autoatendimento','recompra']
    dor_lower = (dor or '').lower()
    empurra = any(k in dor_lower for k in empurra_keywords)
    puxa = any(k in dor_lower for k in puxa_keywords)
    if puxa and not empurra:
        pushpull = 'Operação com perfil puxa: pedidos recorrentes, contrato fechado e giro alto facilitam a digitalização. O portal vira suporte natural para recompra e expansão de ticket.'
    elif empurra and not puxa:
        pushpull = 'Operação com perfil empurra: depende de força de vendas ativa, visitas e negociação por preço. Digitalizar exige adaptar o portal para essa dinâmica de vendas consultiva.'
    else:
        pushpull = 'Operação mista: digitalização viável mas requer ajuste no modelo de atendimento para não perder o relacionamento pessoal.'

    erp_nativo = ['Bling','Omie','Olist (Tiny)','Sankhya']
    if erp in erp_nativo:
        erp_integ = 'Integração nativa'
        erp_golive = '7 a 14 dias'
        erp_dev = 'Não (nativo)'
        erp_line = (
            f'INTEGRAÇÃO\n{erp} - nativa\n\n'
            f'GO-LIVE MÉDIO\n7 a 14 dias\n\n'
            f'DESENVOLVIMENTO\nNão (nativo)\n\n'
            f'Se utilizar {erp}, a conexão é imediata. '
            f'A Zydon tem integração nativa com Sankhya, Omie, Olist e Bling — go-live mais rápido, sem projeto customizado. '
            f'ERPs diferentes são suportados sob avaliação.'
        )
    elif erp == 'Totvs':
        erp_integ = 'Integração sob projeto'
        erp_golive = '30 a 60 dias'
        erp_dev = 'Sim (projeto)'
        erp_line = 'A integração será construída sob medida para o ERP TOTVS desta operação. Prazo médio: 30 a 60 dias.'
    else:
        erp_integ = 'Integração sob projeto'
        erp_golive = '30 a 60 dias'
        erp_dev = 'Sim (projeto)'
        erp_line = 'A integração será construída sob medida para o ERP desta operação. Prazo médio: 30 a 60 dias.'

    fat_lower = faturamento.lower()
    if '500 milhões' in fat_lower or 'acima de r$500' in fat_lower:
        pot_low = 'R$ 5 mi'; pot_high = 'R$ 15 mi'; deixa_mes = 'R$ 416 mil a R$ 1,25 mi'
    elif '10 a r$50 milhões' in fat_lower or 'de r$10' in fat_lower:
        pot_low = 'R$ 2 mi'; pot_high = 'R$ 8 mi'; deixa_mes = 'R$ 166 mil a R$ 666 mil'
    elif '5 a r$10 milhões' in fat_lower or 'de r$5' in fat_lower:
        pot_low = 'R$ 800 mil'; pot_high = 'R$ 3 mi'; deixa_mes = 'R$ 66 mil a R$ 250 mil'
    elif '1 milhão' in fat_lower or 'r$1 mi' in fat_lower:
        pot_low = 'R$ 200 mil'; pot_high = 'R$ 800 mil'; deixa_mes = 'R$ 16 mil a R$ 66 mil'
    elif '500 mil' in fat_lower or 'r$250 mil' in fat_lower or 'r$500 mil' in fat_lower:
        pot_low = 'R$ 50 mil'; pot_high = 'R$ 200 mil'; deixa_mes = 'R$ 4 mil a R$ 16 mil'
    else:
        pot_low = 'R$ 50 mil'; pot_high = 'R$ 200 mil'; deixa_mes = 'R$ 4 mil a R$ 16 mil'

    return {
        'slug': slugify(fantasia),
        'theme': 'dark',
        'empresa': fantasia,
        'contato': primeiro_nome,
        'cargo_area': infer_cargo_area(fantasia, dor),
        'local': infer_local(telefone),
        'telefone': telefone,
        'site': site or 'não informado',
        'sobre': f"{fantasia} é uma empresa do segmento de {infer_cargo_area(fantasia, dor)}. Com faturamento de {faturamento}, busca digitalizar a operação B2B para escalar sem perder controle.",
        'sobre_fonte': 'site oficial + dados do diagnóstico Zydon',
        'vende_para': 'Clientes B2B do seu segmento (distribuição/indústria)',
        'como_vende': 'Venda consultiva + pedidos por WhatsApp/e-mail/telefone',
        'loja_virtual': 'Em avaliação',
        'vendedores': '3 a 5 internos',
        'time_total': '10 a 20 pessoas',
        'faturamento': faturamento,
        'compra_sozinho': 'Sim' if resposta.lower() == 'sim' else 'A confirmar',
        'self_serve_resp': '',
        'dor': dor,
        'encontramos': [
            'Portal B2B para reduzir a demanda de vendedor com pedidos automáticos 24/7',
            'Catálogo digital com preço por volume e tabela por cliente',
            'Integração com ERP para evitar retrabalho e garantir estoque em tempo real'
        ],
        'detalhe': '',
        'conta': 'Cada pedido que chega por WhatsApp/telefone/e-mail consome de 30 a 45 minutos de atendimento. Num cenário de crescimento, esse custo administrativo cresce na mesma escala sem gerar valor.',
        'pot_low': pot_low, 'pot_high': pot_high,
        'deixa_mes': deixa_mes,
        'pot_base': f'Estimativa baseada na faixa de faturamento informada ({faturamento}) e perfil da operação.',
        'significa': 'Um canal digital B2B permite que a equipe comercial foque em fechar negócios e expandir carteira, enquanto o portal cuida dos pedidos recorrentes e autoatendimento.',
        'erp': erp,
        'erp_integ': erp_integ,
        'erp_golive': erp_golive,
        'erp_dev': erp_dev,
        'erp_line': erp_line,
        'pushpull': pushpull,
    }

if __name__ == '__main__':
    processed = [build_lead_dict(l) for l in leads]
    print(json.dumps(processed[:2], ensure_ascii=False, indent=2))
    print(f"Total preparados: {len(processed)}")
