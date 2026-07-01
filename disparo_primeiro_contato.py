#!/usr/bin/env python3
"""
disparo_primeiro_contato.py — Dispara primeiro contato via WhatsApp
para leads sem atividade, por SDR.

Uso: python3 disparo_primeiro_contato.py <sdr_name> [--limit N]
  sdr_name: breno | sarah | lucas
  --limit N: máximo de envios nesta execução (default: 5)

Cada SDR dispara pela sua bridge:
  breno  -> porta 4602
  sarah  -> porta 4601
  lucas  -> porta 4603

O script pula leads já enviados (wpp_envios.json) e marca tarefa no HubSpot
a cada envio, evitando loop de contatos.
"""
import sys
import json
import time
import urllib.request
import os
from scripts.whatsapp_safe_send import safe_send_text

# ─── Config ───
BRIDGES = {
    'breno': {'port': 4602, 'owner_id': '86265630', 'owner_name': 'Breno'},
    'sarah': {'port': 4601, 'owner_id': '88063842', 'owner_name': 'Sarah'},
    'lucas': {'port': 4603, 'owner_id': '85778446', 'owner_name': 'Lucas Batista'},
}

def _load_hubspot_token():
    token = os.environ.get('HUBSPOT_API_KEY') or os.environ.get('HUBSPOT_PRIVATE_APP_TOKEN')
    if token:
        return token.strip()
    try:
        with open('/root/.hermes/credentials/hubspot.env', 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('HUBSPOT_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"\'')
    except FileNotFoundError:
        pass
    raise RuntimeError('HUBSPOT_API_KEY não configurado')

PAT = _load_hubspot_token()
HUBSPOT_HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

LEADS_FILE = '/tmp/sdr_primeiro_contato_enriquecido.json'
# Ledger compartilhado que o Channel observa em /api/conversations.
# Não gravar no root do projeto: esse caminho não é observado pela tela.
WPP_ENVIOS = '/root/.hermes/zydon-prospeccao/controle/wpp_envios.json'
DELAY_SEGUNDOS = 30  # delay entre envios para evitar flag de spam


def load_envios():
    try:
        with open(WPP_ENVIOS, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_envios(envios):
    with open(WPP_ENVIOS, 'w') as f:
        json.dump(envios, f, ensure_ascii=False, indent=2)


def montar_msg_breno(lead):
    return ("Aqui é o Breno, da Zydon. Vi que você preencheu nosso formulário "
            "para conhecer melhor a nossa plataforma de digitalização de vendas. Correto?")


def montar_msg_sarah(lead):
    return ("Oie, aqui é a Sarah da Zydon, e-commerce b2b. Como você está? "
            "Recebi o seu cadastro e quero nos apresentar melhor. Você já vende on-line?")


def montar_msg_lucas(lead):
    nome = lead['contact'].split()[0].capitalize()
    empresa = lead['dealname'].strip()
    erp = lead.get('erp', '').strip()
    erp_txt = erp if erp and erp.lower() not in ('outro', '???', '') else "sistema de gestão atual"
    return (
        f"Olá {nome}! Tudo bem?\n"
        f"Lucas Batista aqui da Zydon.\n\n"
        f"Você solicitou um contato para fazer o *Diagnóstico Comercial B2B* da {empresa}.\n\n"
        f"Notei aqui que vocês rodam a operação no {erp_txt}. "
        f"Gostaria de confirmar algumas informações para te direcionar para o meu "
        f"melhor consultor e executar o diagnóstico com você."
    )


MSG_BUILDERS = {
    'breno': montar_msg_breno,
    'sarah': montar_msg_sarah,
    'lucas': montar_msg_lucas,
}


def send_whatsapp(port, jid, text):
    """Envia mensagem via bridge Baileys. Retorna (ok, response)."""
    return safe_send_text(port, jid, text, uid='disparo_primeiro_contato', timeout=30)


def get_contact_id(deal_id):
    """Busca o contact ID associado a um deal."""
    url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}/associations/contacts"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {PAT}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            results = data.get('results', [])
            return results[0]['id'] if results else None
    except:
        return None


def create_hubspot_task(deal_id, contact_id, owner_id, owner_name, lead_name, tel):
    """Cria tarefa no HubSpot associada ao contato E ao negócio."""
    url = "https://api.hubapi.com/crm/v3/objects/tasks"
    body = {
        "properties": {
            "hs_task_subject": f"Primeiro contato WhatsApp - {lead_name} ({tel})",
            "hs_task_body": f"Disparo de primeiro contato via WhatsApp ({tel}) — {owner_name}.",
            "hs_task_status": "COMPLETED",
            "hs_task_priority": "MEDIUM",
            "hubspot_owner_id": owner_id,
        },
        "associations": [
            {"to": {"id": int(contact_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}]},
            {"to": {"id": int(deal_id)}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 216}]},
        ]
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=HUBSPOT_HEADERS, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            r = json.loads(resp.read().decode())
            return r.get('id')
    except Exception as e:
        print(f"    ⚠️  Erro ao criar tarefa: {e}")
        return None


def main():
    # Parse argumentos
    args = sys.argv[1:]
    if not args or args[0].lower() not in BRIDGES:
        print("Uso: python3 disparo_primeiro_contato.py <breno|sarah|lucas> [--limit N]")
        sys.exit(1)

    sdr_key = args[0].lower()
    LIMIT = 5  # default: máx 5 envios por execução
    if '--limit' in args:
        idx = args.index('--limit')
        if idx + 1 < len(args):
            LIMIT = int(args[idx + 1])

    bridge = BRIDGES[sdr_key]
    port = bridge['port']
    owner_id = bridge['owner_id']
    owner_name = bridge['owner_name']
    msg_builder = MSG_BUILDERS[sdr_key]

    print(f"\n{'='*60}")
    print(f"  DISPARO — {owner_name.upper()} (porta {port}, limite {LIMIT})")
    print(f"{'='*60}")

    # 1. Verificar se a bridge está conectada
    try:
        url = f"http://localhost:{port}/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = json.loads(resp.read().decode())
        if not status.get('connected'):
            print(f"❌ Bridge {port} NÃO conectada! Abortando.")
            sys.exit(1)
        print(f"✅ Bridge conectada.")
    except Exception as e:
        print(f"❌ Erro ao verificar bridge: {e}")
        sys.exit(1)

    # 2. Carregar leads deste SDR
    with open(LEADS_FILE, 'r') as f:
        all_leads = json.load(f)

    leads = [l for l in all_leads if l['owner_name'].lower() == sdr_key]
    print(f"📱 {len(leads)} leads para disparar.\n")

    # 3. Carregar envios já feitos (para não repetir)
    envios = load_envios()

    enviados = 0
    falhas = 0
    pulados = 0

    for i, lead in enumerate(leads, 1):
        # Parar se atingiu o limite de envios desta execução
        if enviados >= LIMIT:
            print(f"\n  🛑 Limite de {LIMIT} envios atingido. Restantes: {len(leads) - i + 1}")
            break

        tel = lead['tel']
        jid = lead['jid']
        nome = lead['contact']
        empresa = lead['dealname']

        # Skip se já enviado
        if tel in envios:
            pulados += 1
            continue

        msg = msg_builder(lead)
        print(f"  [{i}/{len(leads)}] 📤 Enviando para {nome} | {empresa} | {lead['tel_fmt']}")

        # Enviar WhatsApp
        ok, resp = send_whatsapp(port, jid, msg)
        if ok:
            print(f"         ✅ Enviado!")
            enviados += 1

            # Registrar envio
            envios[tel] = {
                'nome': nome,
                'empresa': empresa,
                'sdr': owner_name,
                'data': time.strftime('%Y-%m-%d %H:%M:%S'),
                'msg_type': 'primeiro_contato',
            }
            save_envios(envios)

            # Criar tarefa no HubSpot
            contact_id = get_contact_id(lead['deal_id'])
            if contact_id:
                task_id = create_hubspot_task(
                    lead['deal_id'], contact_id, owner_id, owner_name, nome, lead['tel_fmt']
                )
                if task_id:
                    print(f"         📋 Tarefa HubSpot criada: {task_id}")

        else:
            print(f"         ❌ Falha: {resp}")
            falhas += 1

        # Delay entre envios
        if i < len(leads):
            time.sleep(DELAY_SEGUNDOS)

    print(f"\n{'='*60}")
    print(f"  RESUMO — {owner_name.upper()}")
    print(f"  Enviados neste lote: {enviados}")
    print(f"  Pulados (já enviados): {pulados}")
    print(f"  Falhas: {falhas}")
    restantes = sum(1 for l in leads if l['tel'] not in envios)
    print(f"  Restantes para próximos horários: {restantes}")
    if restantes == 0:
        print(f"  ✅ TODOS OS LEADS DO {owner_name.upper()} FORAM CONTATADOS!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
