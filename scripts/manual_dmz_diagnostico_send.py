#!/usr/bin/env python3
import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path('/root/.hermes/zydon-prospeccao')
CID = '232068683571'
DEAL_ID = '61770586497'
EMAIL = 'dmz@dmz.com.br'
PHONE = '16992919340'
JID = '5516992919340@c.us'
OWNER = '85778446'
OWNER_NAME = 'Lucas Batista'
PORT = 4603
GROUP = '120363408131718880@g.us'
COMPANY = 'DMZ'
SLUG = 'dmz-vitor-feriza'

spec = importlib.util.spec_from_file_location('pg', ROOT / 'scripts/process_gate_once.py')
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)


def load_wpp_data():
    p = ROOT / 'controle/wpp_envios.json'
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        data = {'envios': []}
    rows = data.get('envios', []) if isinstance(data, dict) else data
    return p, data, rows


def save_wpp_data(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def bridge(port, path, payload, timeout=90):
    # Faxina segura 2026-06-30: nunca postar direto na bridge.
    # pg.post_bridge usa scripts/whatsapp_safe_send.safe_post_bridge,
    # com PN/LID guard, auditoria, reconciliação e ownSync no bridge.
    return pg.post_bridge(port, path, payload)


def ok(resp):
    return bool(resp and (resp.get('success') or resp.get('messageId') or resp.get('status') == 1))


def now_brt():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M')


def now_brt_iso():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()


def lead_replied_after(after_ts):
    hist = Path('/root/.hermes/whatsapp-extra/channel_data/history_4603.json')
    try:
        rows = json.loads(hist.read_text(encoding='utf-8'))
    except Exception:
        return False, []
    targets = {JID, JID.replace('@c.us', '@s.whatsapp.net')}
    out = []
    for m in rows if isinstance(rows, list) else []:
        if not isinstance(m, dict) or m.get('fromMe') is True:
            continue
        chat = str(m.get('chat') or m.get('remoteJid') or (m.get('rawKey') or {}).get('remoteJid') or '')
        if chat not in targets:
            continue
        try:
            ts = float(m.get('timestamp') or 0)
            if ts > 10000000000:
                ts = ts / 1000
        except Exception:
            continue
        if ts <= after_ts:
            continue
        txt = ''
        for k in ('text', 'body', 'caption', 'content'):
            if isinstance(m.get(k), str) and m.get(k).strip():
                txt = m.get(k).strip()
                break
        out.append({'ts': ts, 'text': txt[:300]})
    return bool(out), out

# Idempotência antes de qualquer envio externo.
wpp_path, wpp_data, envios = load_wpp_data()
for r in envios:
    if isinstance(r, dict) and str(r.get('email') or '').lower() == EMAIL and str(r.get('status') or '') in {'enviado_lead','enviado_mql'}:
        print(json.dumps({'skipped': True, 'reason': 'already_enviado_lead', 'row_date': r.get('date')}, ensure_ascii=False))
        raise SystemExit(0)

# Confirmar estado HubSpot correto.
try:
    pg.patch_contact(CID, {'lifecyclestage': 'marketingqualifiedlead', 'hubspot_owner_id': OWNER})
    pg.patch_deal(DEAL_ID, {'pipeline': '671008549', 'dealstage': '984052829', 'hubspot_owner_id': OWNER})
except Exception as e:
    print(json.dumps({'hubspot_patch_warning': str(e)}, ensure_ascii=False), flush=True)

lead = {
    'email': EMAIL,
    'phone': PHONE,
    'firstname': 'Vitor',
    'company': COMPANY,
    'createdate': '2026-06-29T15:04:30Z',
    'phone_valid': True,
    'properties': {
        'firstname': 'Vitor',
        'lastname': 'Feriza',
        'email': EMAIL,
        'company': COMPANY,
        'phone': PHONE,
        'recent_conversion_date': '2026-06-29T15:04:30Z',
        'recent_conversion_event_name': 'Facebook Lead Ads: FORM VENCEDOR -> 23/06/2026',
        'qual_erp_utiliza_': 'Outro',
        'qual_o_faturamento_anual_da_sua_empresa_': 'De R$10 a R$50 milhões ao ano',
        'quantas_pessoas_atuam_na_sua_empresa': '11_a_25',
        'quantos_vendedores_internos_sua_empresa_possui': '6_a_20_',
        'de_qual_forma_mais_vende_hoje_em_dia': 'Cliente entra em contato e tira o pedido. Entrega no dia seguinte. WhatsApp',
        'vende_em_loja_virtual_': 'não',
        'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor': 'Sim e não. O plano é maior que só isso.',
        'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados': 'Vendo para sorveterias, açaiterias e delivery de açaí e sorvete.',
        'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente': 'pedidos chegam desorganizados (WhatsApp, telefone, planilha)',
    },
}
research = {
    'slug': SLUG,
    'mql': True,
    'empresa_real': 'DMZ — operação de venda/abastecimento para sorveterias, açaiterias e delivery de açaí e sorvete, conforme formulário do lead.',
    'dominio_site': 'dmz.com.br não pôde ser validado publicamente neste ciclo (403/406), então a decisão MQL foi tomada pelo conjunto forte de respostas do formulário e pelo override operacional definido após revisão.',
    'redes': 'Formulário Facebook Lead Ads informa faturamento de R$10M a R$50M/ano, 11 a 25 pessoas, 6 a 20 vendedores internos, venda atual por WhatsApp/atendimento manual, entregas no dia seguinte e dor de pedidos desorganizados por WhatsApp, telefone e planilha.',
    'segmento': 'Fornecedor/abastecimento B2B para sorveterias, açaiterias e operações de delivery de açaí/sorvete, com potencial de pedidos recorrentes e organização de catálogo, preço, disponibilidade e recompras.',
    'motivo': 'Classificado como MQL porque o formulário indica operação B2B de produto físico com alto faturamento, equipe comercial relevante, clientes recorrentes em sorveterias/açaiterias/delivery, pedido manual por WhatsApp e dor clara de desorganização operacional. Embora a validação pública do site tenha falhado, a decisão operacional foi MQL e, por regra, segue até diagnóstico.',
    'insight': 'sorveterias, açaiterias e operações de delivery consultarem catálogo, preço e disponibilidade para repor pedidos sem depender de cada atendimento manual por WhatsApp',
    'telefone_publico': 'Telefone celular válido recebido no HubSpot/formulário: +55 16 99291-9340.',
    'whatsapp_publico': 'Usar o celular válido informado no HubSpot/formulário: +55 16 99291-9340.',
}
slug, pdf, pretty = pg.generate_pdf(lead, research, 'Zydon')
thumb = pg.gen_thumb(pdf, slug)
text = 'Boa tarde, Vitor, tudo bem? Aqui é o Lucas Batista, da Zydon.\n\nFiz uma análise prévia do potencial da digitalização B2B do seu negócio.'
question = 'Como você imagina que a Zydon poderia te apoiar?'
agenda = 'Se quiser garantir o melhor horário para um diagnóstico completo, pode marcar direto aqui: https://meetings.hubspot.com/lucas-alcantara-nogueira-batista'
group_summary = '''✅ Lead qualificado\nEmpresa: DMZ\nContato: Vitor\nEmail: dmz@dmz.com.br\nERP informado: Outro\nEntrada: 29/06/2026 12:04 BRT\nCriativo/origem: Facebook Lead Ads: FORM VENCEDOR -> 23/06/2026\n\nPor que qualificou:\n• Formulário indica venda para sorveterias, açaiterias e delivery de açaí/sorvete.\n• Faturamento R$10M a R$50M/ano, 11 a 25 pessoas e 6 a 20 vendedores internos.\n• Dor direta de pedidos desorganizados por WhatsApp, telefone e planilha; operação sem loja virtual.\n\nResponsável: Lucas Batista\nDiagnóstico enviado por: Lucas Batista\nCadência: texto curto, PDF após 1 min, pergunta após 30s; agenda só após respiro.'''
# marcador inflight para evitar segundo processo durante a cadência
envios.append({'date': now_brt(), 'date_tz': now_brt_iso(), 'email': EMAIL, 'contact_id': CID, 'deal_id': DEAL_ID, 'slug': SLUG, 'status': 'mql_diagnostico_em_andamento', 'to': JID, 'bridge_port': PORT, 'owner_id': OWNER, 'empresa': COMPANY})
save_wpp_data(wpp_path, wpp_data)

resp_text = bridge(PORT, '/send', {'to': JID, 'text': text})
if not ok(resp_text):
    raise RuntimeError(f'text send failed: {resp_text}')
print(json.dumps({'step': 'text_sent', 'resp': resp_text}, ensure_ascii=False), flush=True)
time.sleep(60)
resp_pdf = bridge(PORT, '/send-file', {'to': JID, 'filePath': str(pretty), 'fileName': 'DMZ - Potencial de Digitalizacao B2B.pdf', 'thumbnailPath': thumb}, timeout=120)
if not ok(resp_pdf):
    raise RuntimeError(f'pdf send failed: {resp_pdf}')
pdf_ts = time.time()
print(json.dumps({'step': 'pdf_sent', 'resp': resp_pdf}, ensure_ascii=False), flush=True)
time.sleep(30)
replied, replies = lead_replied_after(pdf_ts)
if replied:
    resp_question = {'skipped': True, 'reason': 'lead_replied_before_question', 'replies': replies}
    question_ts = pdf_ts
else:
    resp_question = bridge(PORT, '/send', {'to': JID, 'text': question})
    question_ts = time.time()
    if not ok(resp_question):
        raise RuntimeError(f'question send failed: {resp_question}')
print(json.dumps({'step': 'question', 'resp': resp_question}, ensure_ascii=False), flush=True)
# Avisar grupo e registrar final OK imediatamente após diagnóstico (agenda é próxima etapa separada por respiro)
try:
    group_resp = bridge(4609, '/send', {'to': GROUP, 'text': group_summary})
except Exception as e:
    group_resp = {'error': str(e)}
try:
    tid = pg.create_task(CID, [DEAL_ID], "WhatsApp — Diagnóstico 'Potencial de Digitalização B2B' enviado ao lead.", 'Diagnóstico DMZ enviado via WhatsApp pelo Lucas Batista. Cadência: texto curto, PDF após 1 min, pergunta após 30s; agenda deve ocorrer só após respiro de 20 min se não houver resposta.', OWNER)
except Exception as e:
    tid = None
    print(json.dumps({'task_warning': str(e)}, ensure_ascii=False), flush=True)
# Atualiza ledger final.
wpp_path, wpp_data, envios = load_wpp_data()
envios.append({'date': now_brt(), 'date_tz': now_brt_iso(), 'email': EMAIL, 'contact_id': CID, 'deal_id': DEAL_ID, 'slug': SLUG, 'status': 'enviado_lead', 'to': JID, 'group': GROUP, 'bridge_port': PORT, 'group_bridge_port': 4609, 'owner_id': OWNER, 'phone': PHONE, 'empresa': COMPANY, 'fallback_note': 'correção Rafael: decisão MQL implica seguir até diagnóstico; conflito antigo nao_mql_grupo resolvido', 'text': text, 'question_text': question, 'agenda_text': agenda, 'cadence': {'text_to_pdf_seconds': 60, 'pdf_to_question_seconds': 30, 'question_to_agenda_seconds': 1200}, 'pdf_path': str(pretty), 'text_response': resp_text, 'file_response': resp_pdf, 'question_response': resp_question, 'group_summary_response': group_resp, 'task_id': tid, 'agenda_pending_after_question_ts': question_ts})
save_wpp_data(wpp_path, wpp_data)
with (ROOT / 'controle/processed_emails.txt').open('a', encoding='utf-8') as f:
    f.write(f'{EMAIL}|{SLUG}|{now_brt()}|enviado_lead|{PHONE}|{COMPANY}\n')
print(json.dumps({'done': True, 'pdf': str(pretty), 'task_id': tid, 'group_resp': group_resp}, ensure_ascii=False), flush=True)
