#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GATE DURO de dedup — Zydon prospecção.

Script 100% determinístico (ZERO LLM). Roda ANTES de qualquer agente LLM tocar
nos leads. Busca contatos novos no HubSpot (últimas 48h), aplica dedup estrito
contra os controles locais e escreve até 3 leads qualificados em
/tmp/gate_qualified.json.

Regras de ouro:
- FAIL-CLOSED: qualquer dúvida na leitura do dedup primário => trata TODOS os
  leads como já processados e libera NADA.
- IDEMPOTENTE: rodar 2x sem leads novos = mesmo resultado vazio.
- NUNCA modifica processed_emails.txt nem wpp_envios.json.
- NUNCA envia nada (sem WhatsApp, sem HubSpot write). Só filtra e escreve JSON.

Stdout (contrato com o agente LLM que parseia):
- count == 0  => última linha exatamente: NENHUM_LEAD_NOVO
- count  > 0  => GATE_OK:N leads qualificados -> /tmp/gate_qualified.json
- erro de API => GATE_ERRO:<msg>  (e sys.exit(1))
"""
import os
import re
import sys
import json
import unicodedata
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import urllib.request
import urllib.error

BASE_DIR = Path(__file__).resolve().parent.parent
CONTROLE_DIR = BASE_DIR / 'controle'
PROCESSED_EMAILS = CONTROLE_DIR / 'processed_emails.txt'
WPP_ENVIOS = CONTROLE_DIR / 'wpp_envios.json'
CICLO_LOG = CONTROLE_DIR / 'ciclo.log'
OUTPUT_PATH = '/tmp/gate_qualified.json'

BASE_URL = 'https://api.hubapi.com'
WINDOW_HOURS = 24
MAX_LEADS = 3
HTTP_TIMEOUT = 30

# Propriedades pedidas ao HubSpot — exatamente esta lista.
# IMPORTANTE: phone/hs_whatsapp_phone_number vêm MASCARADOS (PII). O campo
# hs_searchable_calculated_phone_number traz o número COMPLETO — é o que usamos.
PROPERTIES = [
    'firstname', 'lastname', 'email', 'company', 'phone',
    'hs_whatsapp_phone_number', 'hs_searchable_calculated_phone_number',
    'lifecyclestage', 'hs_lead_status',
    'hubspot_owner_id', 'createdate', 'lastmodifieddate', 'hs_lastmodifieddate',
    # Reentrada por formulário em contato já existente: HubSpot mantém o
    # createdate antigo, então o gate precisa olhar a conversão recente também.
    'recent_conversion_date', 'recent_conversion_event_name',
    'num_conversion_events', 'num_unique_conversion_events',
    'hs_calculated_form_submissions',
    # Origem de criação: contatos criados manualmente pela UI do CRM não entram
    # na investigação/prospecção automática; só processar outras origens.
    'hs_object_source', 'hs_object_source_label',
    # Origem/campanha do lead para o grupo entender data/hora e criativo.
    'hs_analytics_source', 'hs_analytics_source_data_1', 'hs_analytics_source_data_2',
    'hs_latest_source', 'hs_latest_source_data_1', 'hs_latest_source_data_2',
    'qual_erp_utiliza_', 'selecione_o_sistema_de_gesto_erp',
    'qual_o_faturamento_anual_da_sua_empresa_', 'e_qual_faturamento_anual_da_sua_empresa',
    'selecione_a_faixa_de_faturamento', 'selecione_a_faixa_de_faturamento_atual_por_ano_da_sua_empresa',
    'qual_seria_o_maior_problema', 'principais_dores',
    'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente',
    'de_qual_forma_mais_vende_hoje_em_dia',
    'quantos_vendedores_internos', 'quantos_vendedores_internos_sua_empresa_possui',
    'quantas_pessoas_atuam_na_sua_empresa',
    'vende_em_loja_virtual_',
    'voc_acredita_que_o_seu_cliente_compraria_sozinho',
    'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor',
    'qual_a_rea_de_atuao_de_sua_empresa',
    'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados',
    'qual_a_area_de_atuacao_de_sua_empresa_',
    'voc_vende_para_quem', 'voc_vende_para_quem_ex_padarias_restaurantes_petshop_autopeas_supermercados',
]

# Propriedades-chave que contam +1 cada no SCORE DE COMPLETUDE (intra-batch dedup).
KEY_PROPS = [
    'qual_erp_utiliza_', 'selecione_o_sistema_de_gesto_erp',
    'qual_o_faturamento_anual_da_sua_empresa_', 'e_qual_faturamento_anual_da_sua_empresa',
    'selecione_a_faixa_de_faturamento', 'selecione_a_faixa_de_faturamento_atual_por_ano_da_sua_empresa',
    'qual_seria_o_maior_problema', 'principais_dores',
    'qual_seria_o_maior_problema_que_voc_enfrenta_em_sua_operao_atualmente',
    'de_qual_forma_mais_vende_hoje_em_dia',
    'quantos_vendedores_internos', 'quantos_vendedores_internos_sua_empresa_possui',
    'quantas_pessoas_atuam_na_sua_empresa',
    'vende_em_loja_virtual_',
    'voc_acredita_que_o_seu_cliente_compraria_sozinho',
    'voc_acredita_que_o_seu_cliente_compraria_sozinho_na_sua_loja_24h_por_dia_sem_precisar_de_vendedor',
    'voc_vende_para_quem', 'voc_vende_para_quem_ex_padarias_restaurantes_petshop_autopeas_supermercados',
    'qual_a_rea_de_atuao_de_sua_empresa',
    'qual_a_rea_de_atuao_de_sua_empresa_ex_nicho_de_autopeas_nicho_de_supermercados',
    'qual_a_area_de_atuacao_de_sua_empresa_',
]

# Peso do estágio do ciclo de vida no score de completude.
LIFECYCLE_RANK = {
    'marketingqualifiedlead': 5,
    'salesqualifiedlead': 5,
    'lead': 3,
    'subscriber': 2,
}


def log(msg):
    """Append uma linha em controle/ciclo.log (best-effort, nunca derruba o gate)."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    try:
        with open(CICLO_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def fail_closed(reason):
    """Em caso de dúvida no dedup: não libera ninguém. Escreve JSON vazio + NENHUM_LEAD_NOVO."""
    log(f'[gate] FAIL-CLOSED: {reason}')
    write_output([])
    print('NENHUM_LEAD_NOVO')
    sys.exit(0)


def only_digits(value):
    return re.sub(r'[^0-9]', '', value or '')


def parse_hs_datetime(value):
    """Parse HubSpot/control datetime; retorna aware UTC ou None.

    HubSpot vem ISO/Z. Já o controle local (`processed_emails.txt`) grava
    `YYYY-MM-DD HH:MM` em America/Sao_Paulo. Tratar esse formato como UTC
    (ou não parsear) faz uma conversão antiga parecer nova e libera reenvio
    indevido de reentradas já processadas.
    """
    if not value:
        return None
    raw = str(value).strip()
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


def strip_accents(value):
    """Remove acentos via NFKD (ex: 'José' -> 'Jose')."""
    decomposed = unicodedata.normalize('NFKD', value or '')
    return ''.join(c for c in decomposed if not unicodedata.combining(c))


def norm_text(value):
    """Normaliza texto p/ comparação: trim, lower, sem acento."""
    return strip_accents((value or '').strip().lower())


def normalize_mobile(raw):
    """
    Normaliza telefone celular para 11 dígitos comparáveis.
    Só dígitos; se 13 dígitos começando com 55, remove o 55 -> 11 dígitos.
    """
    digits = only_digits(raw)
    if len(digits) == 13 and digits.startswith('55'):
        digits = digits[2:]
    return digits


def is_valid_mobile(digits):
    """Celular válido = exatamente 11 dígitos (DDD + 9XXXXXXXX)."""
    return len(digits) == 11


def contact_mobile(props):
    """Telefone celular normalizado do contato (preferindo whatsapp)."""
    # Priorizar hs_searchable_calculated_phone_number (COMPLETO, não mascarado).
    # phone/hs_whatsapp_phone_number vêm mascarados (PII) e só servem de fallback.
    raw = (props.get('hs_searchable_calculated_phone_number')
           or props.get('hs_whatsapp_phone_number') or props.get('phone') or '')
    # Se o campo principal veio mascarado, tentar o calculado.
    if '*' in raw:
        raw = props.get('hs_searchable_calculated_phone_number') or raw
    return normalize_mobile(raw)


def score_completeness(props):
    """
    Score de completude do contato (maior = primário no merge).
    +1 por property-chave preenchida; +rank do lifecycle; +2 se celular válido.
    """
    score = 0
    for key in KEY_PROPS:
        value = props.get(key)
        if value is not None and str(value).strip() != '':
            score += 1
    lifecycle = (props.get('lifecyclestage') or '').strip().lower()
    score += LIFECYCLE_RANK.get(lifecycle, 0)
    if is_valid_mobile(contact_mobile(props)):
        score += 2
    return score


def dup_signals(a, b):
    """
    Sinais de duplicata entre dois leads (cada um com chave 'properties').
    Retorna lista de sinais que bateram: 'telefone_normalizado' e/ou 'nome_empresa'.
    """
    pa, pb = a.get('properties', {}) or {}, b.get('properties', {}) or {}
    signals = []

    ma, mb = contact_mobile(pa), contact_mobile(pb)
    if is_valid_mobile(ma) and ma == mb:
        signals.append('telefone_normalizado')

    fa, fb = norm_text(pa.get('firstname')), norm_text(pb.get('firstname'))
    ca, cb = norm_text(pa.get('company')), norm_text(pb.get('company'))
    da, db = (pa.get('createdate') or '')[:10], (pb.get('createdate') or '')[:10]
    if fa and ca and da and fa == fb and ca == cb and da == db:
        signals.append('nome_empresa')

    return signals


def build_reason(primary, secondary, signals):
    """Texto legível explicando por que primary venceu o merge."""
    parts = []
    if 'nome_empresa' in signals:
        parts.append('mesmo nome+empresa+dia')
    if 'telefone_normalizado' in signals:
        parts.append('mesmo telefone normalizado')

    pp = primary.get('properties', {}) or {}
    filled = sum(
        1 for k in KEY_PROPS
        if pp.get(k) is not None and str(pp.get(k)).strip() != ''
    )
    lifecycle = (pp.get('lifecyclestage') or '').strip().lower()
    lc_abbr = {
        'marketingqualifiedlead': 'MQL', 'salesqualifiedlead': 'SQL',
        'lead': 'lead', 'subscriber': 'subscriber',
    }.get(lifecycle, lifecycle or 'sem lifecycle')

    detail = f'primário com {lc_abbr}'
    if filled:
        detail += f' + {filled} campo(s) de form preenchido(s)'
    parts.append(detail)
    return '; '.join(parts)


def detect_intra_batch_duplicates(candidates):
    """
    Detecta duplicatas DENTRO do batch (entre os próprios candidatos).
    Agrupa por sinais (telefone/nome+empresa+dia), elege primário por score de
    completude (empate -> createdate mais antigo) e devolve:
      (primaries, duplicates)
    onde primaries é a lista de leads a liberar (1 por grupo) e duplicates é a
    lista de registros primário/secundário p/ o output JSON.
    """
    groups = []  # cada grupo é uma lista de leads considerados o mesmo contato
    for lead in candidates:
        placed = False
        for group in groups:
            if any(dup_signals(lead, member) for member in group):
                group.append(lead)
                placed = True
                break
        if not placed:
            groups.append([lead])

    primaries = []
    duplicates = []
    for group in groups:
        if len(group) == 1:
            primaries.append(group[0])
            continue
        # Primário = maior score; empate -> menor createdate (mais antigo).
        ranked = sorted(
            group,
            key=lambda m: (-score_completeness(m.get('properties', {}) or {}),
                           m.get('createdate') or ''),
        )
        primary = ranked[0]
        primary_score = score_completeness(primary.get('properties', {}) or {})
        primaries.append(primary)
        for member in ranked[1:]:
            signals = dup_signals(primary, member) or dup_signals(member, primary)
            duplicates.append({
                'primary_id': primary.get('id'),
                'primary_email': primary.get('email'),
                'primary_score': primary_score,
                'secondary_id': member.get('id'),
                'secondary_email': member.get('email'),
                'secondary_score': score_completeness(member.get('properties', {}) or {}),
                'signals': signals,
                'reason': build_reason(primary, member, signals),
            })
    return primaries, duplicates


def load_processed_emails():
    """
    Dedup primário. Lê processed_emails.txt e devolve dict email -> último timestamp processado.

    Formato MISTO no arquivo:
      pipe:  email@x.com|slug|2026-...Z|status|telefone|Nome
      bare:  email@x.com
      id:    151|email@x.com|slug|2026-...|status|telefone|Nome

    Reenvio de formulário: se recent_conversion_date for posterior ao timestamp
    processado, o contato deve voltar para a fila mesmo com o mesmo email.

    FAIL-CLOSED: se o arquivo não existir ou houver erro de IO, NÃO retorna dict
    vazio — sinaliza falha para o chamador tratar todos como já processados.
    Retorna (dict, ok_bool).
    """
    if not PROCESSED_EMAILS.exists():
        return {}, False
    try:
        processed = {}
        with open(PROCESSED_EMAILS, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                fields = [x.strip() for x in line.split('|')]
                emails = []
                for field in fields:
                    low = field.lower()
                    if '@' in low:
                        domain = low.split('@')[-1]
                        if '.' in domain:
                            emails.append(low)
                if not emails:
                    continue
                # Primeiro datetime parseável da linha costuma ser o momento do processamento.
                ts = None
                for field in fields:
                    ts = parse_hs_datetime(field)
                    if ts:
                        break
                for email in emails:
                    old = processed.get(email)
                    if old is None or (ts and old and ts > old) or (old is None and ts):
                        processed[email] = ts
        return processed, True
    except Exception as e:
        log(f'[gate] erro lendo processed_emails.txt: {e}')
        return {}, False


def load_sent_phones():
    """
    Dedup secundário. Lê wpp_envios.json (lista de dicts com chave 'to') e
    devolve um set de telefones (só dígitos) já disparados.

    Falha aqui NÃO é fail-closed crítico (é uma camada extra de segurança);
    em erro, retorna set vazio e segue só com o dedup primário (estrito).
    """
    if not WPP_ENVIOS.exists():
        return set()
    try:
        with open(WPP_ENVIOS, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        log(f'[gate] erro lendo wpp_envios.json: {e}')
        return set()
    phones = set()
    if isinstance(data, dict):
        envios = data.get('envios', [])
    elif isinstance(data, list):
        envios = data
    else:
        envios = []
    inbound_done_statuses = {
        'enviado_lead',
        'enviado_mql',
        'enviado_lead_manual_mql',
        'manual_nao_mql_convertido_mql',
        'mql_diagnostico_em_andamento',
    }
    for entry in envios:
        if not isinstance(entry, dict):
            continue
        status = (entry.get('status') or entry.get('msg_type') or '').strip().lower()
        # Evita contaminar o dedup inbound com fluxos SDR genéricos sem status
        # de qualificação/diagnóstico. Mas inclui status manuais auditáveis que
        # também significam "este telefone já foi tratado no inbound".
        if status and status not in inbound_done_statuses:
            continue
        for field in ('to', 'phone', 'telefone', 'jid', 'lead_jid'):
            d = only_digits(entry.get(field))
            if d:
                phones.add(d)
                # Normaliza @s.whatsapp.net/@c.us e números BR com 55 para a
                # mesma chave usada pelos leads vindos do HubSpot.
                if d.startswith('55') and len(d) >= 12:
                    phones.add(d[2:])
    return phones


def is_form_reentry_event(props):
    """Retorna True só para conversões recentes que podem ser novo formulário.

    HubSpot também atualiza `recent_conversion_date` para eventos que NÃO são
    novo diagnóstico/formulário, especialmente `Meetings Link: ...`. Usar esses
    eventos como reentrada fura o dedup e reenvia diagnóstico para lead já
    tratado. Reentrada automática é apenas para novo preenchimento/conversão de
    formulário; eventos de agenda/conversa/WhatsApp ficam bloqueados.
    """
    props = props or {}
    event = (props.get('recent_conversion_event_name') or '').strip()
    if not event:
        return False
    norm = norm_text(event)
    non_form_tokens = (
        'meetings link', 'meeting link', 'meeting', 'reuniao', 'reunioes',
        'agenda', 'calendly', 'conversations', 'conversation', 'whatsapp',
        'whats app', 'chat', 'inbox', 'offline', 'offline sources',
    )
    if any(tok in norm for tok in non_form_tokens):
        return False
    return True


def is_forms_channel_lead(props):
    """Trilho principal do Rafael: processar forms/forms/forms.

    Contato criado por FORM entra. Contato antigo só reentra se o evento recente
    parecer formulário real. Eventos offline/conversation/meeting não devem gastar
    qualificação nem pesquisa automática.
    """
    props = props or {}
    source = (props.get('hs_object_source') or '').strip().upper()
    source_label = (props.get('hs_object_source_label') or '').strip().upper()
    if source == 'FORM' or source_label in {'FORM', 'FORMS'}:
        return True
    return is_form_reentry_event(props)


def is_landline(digits):
    """
    Só rejeita formatos obviamente impossíveis.

    Regra Rafael/Zydon: antes de considerar inválido, sempre tentar variações,
    especialmente inserir 9 após o DDD. Um telefone com 10 dígitos pode ser
    WhatsApp válido sem o 9 no campo do HubSpot, então NÃO bloquear aqui.
    Ex.: 55 62 8219-5606 deve virar tentativa 55 62 98219-5606.
    """
    if not digits or len(digits) < 10:
        return True
    if digits.startswith('55') and len(digits) < 12:
        return True
    return False


def get_last_envio_timestamp():
    """
    Timestamp (UTC, ISO 'YYYY-MM-DDTHH:MM:SSZ') do ÚLTIMO envio registrado em
    controle/wpp_envios.json, ou None se o arquivo não existir / estiver vazio /
    não tiver nenhum registro parseável.

    O campo `date` vem em FORMATOS MISTOS:
    - ISO 8601 UTC com Z: '2026-06-22T17:53:38Z'  -> tratado como UTC direto.
    - 'YYYY-MM-DD HH:MM':  '2026-06-23 00:35'      -> tratado como America/Sao_Paulo
      (BRT) e convertido para UTC.
    Registros não parseáveis (ou sem `date`) são IGNORADOS — falha graciosa, nunca
    derruba o gate.
    """
    SP_TZ = ZoneInfo('America/Sao_Paulo')
    if not os.path.exists(WPP_ENVIOS):
        return None
    try:
        with open(WPP_ENVIOS, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        log(f'[gate] erro lendo wpp_envios.json p/ cutoff: {e}')
        return None

    if isinstance(data, dict):
        envios = data.get('envios', [])
    elif isinstance(data, list):
        envios = data
    else:
        envios = []

    best = None
    for entry in envios:
        if not isinstance(entry, dict):
            continue
        # IMPORTANTE: wpp_envios.json também é usado por outros fluxos (ex.: SDR
        # primeiro contato), que gravam registros sem status/email do inbound. Esses
        # registros NÃO podem virar cutoff do gate de prospecção inbound, senão um
        # disparo SDR às 11:06 BRT vira cutoff 14:06 UTC e bloqueia leads novos por
        # horas. Só considerar status do ciclo inbound.
        status = (entry.get('status') or '').strip().lower()
        if status not in {'enviado_lead', 'nao_mql_grupo'}:
            continue
        raw = entry.get('date')
        if not raw or not isinstance(raw, str):
            continue
        raw = raw.strip()
        dt = None
        try:
            # 1) ISO 8601 com Z => UTC.
            dt = datetime.strptime(raw, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                # 2) 'YYYY-MM-DD HH:MM' => America/Sao_Paulo -> UTC.
                dt = datetime.strptime(raw, '%Y-%m-%d %H:%M').replace(tzinfo=SP_TZ).astimezone(timezone.utc)
            except ValueError:
                dt = None
        if dt is None:
            continue
        if best is None or dt > best:
            best = dt

    if best is None:
        return None
    return best.strftime('%Y-%m-%dT%H:%M:%SZ')


def hubspot_search():
    """
    Busca contatos FORM da janela recente inteira, ordenados por createdate ASC.

    REGRA FILA/TRILHO (Rafael 24/06): nunca usar "último envio" como cutoff para
    excluir leads anteriores ainda não processados. O cutoff por último envio causou
    incidente: um lead mais novo processado avançou o corte e pulou um lead mais
    antigo pendente. A fila correta é: buscar janela recente (WINDOW_HOURS), remover
    apenas processed/wpp_envios/customer/CRM_UI, ordenar FIFO e processar até MAX_LEADS.
    """
    token = os.environ.get('HUBSPOT_API_KEY', '')
    if not token:
        sys.stderr.write('[gate] HUBSPOT_API_KEY ausente no ambiente.\n')
        print('GATE_ERRO:HUBSPOT_API_KEY ausente no ambiente')
        sys.exit(1)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    cutoff_iso = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')
    msg = f'[fila] janela {WINDOW_HOURS}h inteira desde {cutoff_iso}; dedup decide, não último envio'
    log(msg)
    sys.stderr.write(msg + '\n')

    payload = {
        # OR entre contato novo e contato antigo que reenviou formulário.
        # PANFLIGHT (25/06) expôs o bug: createdate era 13/06, mas
        # recent_conversion_date era da madrugada; com filtro só por createdate
        # o alerta/diagnóstico não entrava na fila.
        'filterGroups': [
            {'filters': [{'propertyName': 'createdate', 'operator': 'GTE', 'value': cutoff_iso}]},
            {'filters': [{'propertyName': 'recent_conversion_date', 'operator': 'GTE', 'value': cutoff_iso}]},
        ],
        'properties': PROPERTIES,
        'sorts': [{'propertyName': 'createdate', 'direction': 'ASCENDING'}],
        'limit': 100,
    }
    req = urllib.request.Request(
        f'{BASE_URL}/crm/v3/objects/contacts/search',
        data=json.dumps(payload).encode(),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
        except Exception:
            body = ''
        msg = f'HTTP {e.code} {body[:300]}'
        log(f'[gate] HUBSPOT SEARCH ERROR: {msg}')
        print(f'GATE_ERRO:{msg}')
        sys.exit(1)
    except Exception as e:
        log(f'[gate] HUBSPOT SEARCH ERROR: {e}')
        print(f'GATE_ERRO:{e}')
        sys.exit(1)


MANUAL_MQL_SOURCE_TYPES = {'CRM_UI', 'MOBILE_IOS', 'MOBILE_ANDROID'}


def is_manual_mql_history_item(item):
    """True só quando o HubSpot mostra MQL alterado manualmente por usuário/app.

    MQL vindo de AUTOMATION_PLATFORM, INTEGRATION/Intercom ou formulário não é
    override humano do Rafael/time; nesses casos o crivo Não-MQL continua valendo.
    """
    if not isinstance(item, dict):
        return False
    if str(item.get('value') or '').strip().lower() != 'marketingqualifiedlead':
        return False
    source_type = str(item.get('sourceType') or '').strip().upper()
    if source_type in MANUAL_MQL_SOURCE_TYPES:
        return True
    # Fallback conservador para formatos HubSpot que trazem userId sem sourceType
    # explícito. Sem userId, não tratar como manual.
    return not source_type and bool(item.get('updatedByUserId'))


def latest_manual_mql_lifecycle_timestamp_from_history(history):
    """Último timestamp em que lifecyclestage virou MQL manualmente no HubSpot/app."""
    latest = None
    for item in history or []:
        if not is_manual_mql_history_item(item):
            continue
        ts = parse_hs_datetime(item.get('timestamp'))
        if ts and (latest is None or ts > latest):
            latest = ts
    return latest


def fetch_lifecycle_history(contact_id, token):
    """Busca histórico de lifecyclestage para diferenciar MQL manual real de update qualquer."""
    if not contact_id:
        return []
    url = f'{BASE_URL}/crm/v3/objects/contacts/{contact_id}?propertiesWithHistory=lifecyclestage'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'}, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        return (((data.get('propertiesWithHistory') or {}).get('lifecyclestage')) or [])
    except Exception as e:
        log(f'[gate] erro buscando histórico lifecyclestage contato {contact_id}: {e}')
        return []


def is_manual_mql_trigger(contact, props, processed_at, token, now=None):
    """True quando a mudança para MQL ocorreu depois do último processamento.

    Não basta `lifecyclestage=MQL + lastmodifieddate recente`: qualquer update
    posterior (ex.: owner/task) também muda lastmodifieddate. O sinal seguro é o
    histórico da própria propriedade `lifecyclestage` ter virado MQL dentro da
    janela recente E depois do processed_at.

    Rafael 28/06: "não fica lendo nada antigo; só lead novo". Portanto, se o
    contato nunca foi processado localmente mas a virada para MQL é antiga/herdada,
    não é trigger manual: precisa nova conversão real ou lifecycle virando MQL agora.
    """
    lifecycle = (props.get('lifecyclestage') or '').strip().lower()
    if lifecycle != 'marketingqualifiedlead':
        return False
    history = fetch_lifecycle_history(contact.get('id'), token)
    mql_at = latest_manual_mql_lifecycle_timestamp_from_history(history)
    if not mql_at:
        return False
    now = now or datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(hours=WINDOW_HOURS)
    if mql_at < recent_cutoff:
        return False
    return processed_at is None or mql_at > processed_at


def write_output(leads, duplicates=None):
    payload = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'count': len(leads),
        'cutoff_window_h': WINDOW_HOURS,
        'leads': leads,
        'duplicates': duplicates or [],
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main():
    # --- dedup primário (FAIL-CLOSED) ---
    processed, ok = load_processed_emails()
    if not ok:
        fail_closed('não foi possível ler processed_emails.txt')

    sent_phones = load_sent_phones()

    # --- HubSpot ---
    token = os.environ.get('HUBSPOT_API_KEY', '')
    search = hubspot_search()
    contacts = search.get('results', []) if isinstance(search, dict) else []
    total_hubspot = len(contacts)
    window_cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)

    candidates = []
    dedup_count = 0  # quantos foram barrados pelo dedup/regras

    for contact in contacts:
        props = contact.get('properties', {}) or {}

        email = (props.get('email') or '').strip().lower()
        if not email:
            dedup_count += 1
            continue

        lifecycle = (props.get('lifecyclestage') or '').strip().lower()
        processed_at = processed.get(email)
        # Rafael 29/06: NÃO usar lastmodifieddate como gatilho de "gol de mão".
        # Esse campo muda por owner, task, nota, automação e qualquer toque no CRM;
        # ontem ele cavou backlog/falso positivo. MQL manual/F5 só entra quando
        # Rafael avisar explicitamente ou por uma fila/override auditável separado.
        manual_mql_trigger = False

        # Contatos criados manualmente pela UI do CRM são tratativa interna;
        # exceção: Marketing marcou/atualizou lifecyclestage=MQL depois do último
        # processamento, então precisa investigar e poder disparar diagnóstico.
        source = (props.get('hs_object_source') or '').strip().upper()
        source_label = (props.get('hs_object_source_label') or '').strip().upper()
        if (source == 'CRM_UI' or source_label in {'CRM_UI', 'CRM UI'}) and not manual_mql_trigger:
            dedup_count += 1
            continue

        # Rafael 28/06: atuar principalmente em forms/forms/forms.
        # Exceção manual/F5 NÃO vem de lastmodifieddate; precisa override explícito.
        if not is_forms_channel_lead(props) and not manual_mql_trigger:
            dedup_count += 1
            continue

        # Rejeitar customers (clientes ativos NÃO são prospecção nova).
        if lifecycle == 'customer':
            dedup_count += 1
            continue

        # Contatos internos/testes não entram na fila comercial.
        recent_event = (props.get('recent_conversion_event_name') or '').strip()
        if email.endswith('@zydon.com.br') or any(tok in norm_text(recent_event) for tok in ('interno', 'admin', 'homolog')):
            dedup_count += 1
            continue

        # Dedup primário estrito, exceto reenvio real de formulário depois do último processamento.
        processed_at = processed.get(email)
        recent_at = parse_hs_datetime(props.get('recent_conversion_date'))
        created_at = parse_hs_datetime(props.get('createdate'))
        # Rafael 28/06: "não fica lendo nada antigo não, só vê e lê lead novo".
        # Como `hubspot_search` também busca lastmodifieddate para detectar MQL manual,
        # contatos antigos podem entrar no payload bruto. Filtrar aqui: se não foi
        # criado na janela, não teve conversão/formulário recente e não é MQL manual
        # recente confirmado pelo histórico de lifecyclestage, NÃO entra no gate.
        is_created_recent = bool(created_at and created_at >= window_cutoff)
        is_conversion_recent = bool(recent_at and recent_at >= window_cutoff)
        if not (is_created_recent or is_conversion_recent or manual_mql_trigger):
            dedup_count += 1
            continue
        # Só é reentrada quando a conversão é posterior à criação do contato.
        # Em contato novo, HubSpot também preenche recent_conversion_date ~= createdate;
        # isso NÃO deve furar dedup antigo.
        is_form_reentry = bool(
            recent_at
            and created_at
            and (recent_at - created_at).total_seconds() > 300
            and (processed_at is None or recent_at > processed_at)
            and is_form_reentry_event(props)
        )
        is_reentry = is_form_reentry or manual_mql_trigger
        if email in processed and not is_reentry:
            dedup_count += 1
            continue

        # Telefone: priorizar hs_searchable_calculated_phone_number (COMPLETO);
        # phone/hs_whatsapp_phone_number vêm MASCARADOS (PII).
        raw_phone = (props.get('hs_searchable_calculated_phone_number')
                     or props.get('hs_whatsapp_phone_number')
                     or props.get('phone') or '')
        if '*' in raw_phone:
            raw_phone = props.get('hs_searchable_calculated_phone_number') or raw_phone
        phone_digits = only_digits(raw_phone)

        # Telefone inválido/fixo NÃO pode sumir: se o agente qualificar como MQL,
        # avisamos o grupo e não tentamos disparar diagnóstico ao lead.
        phone_valid = True
        phone_invalid_reason = ''
        if not phone_digits or '*' in (raw_phone or ''):
            phone_valid = False
            phone_invalid_reason = 'telefone ausente/mascarado'
        elif is_landline(phone_digits):
            phone_valid = False
            phone_invalid_reason = 'telefone fixo ou inválido para WhatsApp'

        # Dedup secundário estrito quando já há diagnóstico MQL em andamento/final
        # para o telefone. Reenvio REAL de formulário ainda pode reentrar; MQL
        # manual recente não pode repetir se um diagnóstico manual anterior já
        # gravou status auditável no ledger.
        if phone_valid and phone_digits and phone_digits in sent_phones and not is_form_reentry:
            dedup_count += 1
            continue

        lead = {
            'id': contact.get('id'),
            'email': email,
            'firstname': props.get('firstname') or '',
            'lastname': props.get('lastname') or '',
            'company': props.get('company') or '',
            'phone': raw_phone,
            'phone_valid': phone_valid,
            'phone_invalid_reason': phone_invalid_reason,
            'createdate': props.get('createdate') or '',
            'gate_trigger': 'manual_hubspot_mql' if manual_mql_trigger else ('form_reentry' if is_form_reentry else 'new_form'),
            'hs_lastmodifieddate': props.get('lastmodifieddate') or props.get('hs_lastmodifieddate') or '',
            'properties': props,
        }
        candidates.append(lead)

    # Dedup INTRA-BATCH: entre os próprios candidatos desta rodada.
    # Colapsa grupos de duplicatas num único primário (maior score de completude)
    # e registra os secundários em `duplicates`.
    primaries, duplicates = detect_intra_batch_duplicates(candidates)

    # Já vem ordenado ASC do HubSpot para leads novos; para reenvio de formulário
    # em contato antigo, FIFO deve usar recent_conversion_date quando existir.
    primaries.sort(key=lambda l: (
        (l.get('hs_lastmodifieddate') if l.get('gate_trigger') == 'manual_hubspot_mql' else '')
        or (l.get('properties') or {}).get('recent_conversion_date')
        or l.get('createdate')
        or ''
    ))
    qualified = primaries[:MAX_LEADS]

    write_output(qualified, duplicates)
    log(
        f'[gate] total_hubspot={total_hubspot} dedup={dedup_count} '
        f'duplicatas_intra_batch={len(duplicates)} qualificados={len(qualified)}'
    )

    if not qualified:
        print('NENHUM_LEAD_NOVO')
    else:
        print(f'GATE_OK:{len(qualified)} leads qualificados -> {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
