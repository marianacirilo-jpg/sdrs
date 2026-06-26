#!/usr/bin/env python3
import json, os, re, subprocess, sys, time, urllib.request, urllib.error, urllib.parse, pathlib
BASE='http://127.0.0.1:8791'
PROJECT=pathlib.Path('/root/.hermes/zydon-prospeccao')
HEAD={'Cf-Access-Authenticated-User-Email':'rafael@zydon.com.br'}
BAD={'Cf-Access-Authenticated-User-Email':'teste@gmail.com'}
BAD_ZYDON_COM={'Cf-Access-Authenticated-User-Email':'rafael@zydon.com'}
results=[]

def ok(name, cond, detail=''):
    results.append((name, bool(cond), detail))

def http(path, headers=None, method='GET', data=None, timeout=15):
    req=urllib.request.Request(BASE+path, headers=headers or {}, method=method, data=data)
    return urllib.request.urlopen(req, timeout=timeout)

# segurança
try:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener=urllib.request.build_opener(NoRedirect)
    try:
        r=opener.open(urllib.request.Request(BASE+'/'), timeout=15)
        body=r.read().decode(errors='ignore')
        ok('root_requires_login', 'Zydon Channel' in body and 'Inbox comercial' not in body, str(r.status))
    except urllib.error.HTTPError as e:
        ok('root_requires_login', e.code in (301,302) and (e.headers.get('Location') or '').startswith('/login'), str(e.code)+' '+str(e.headers.get('Location')))
except Exception as e: ok('root_requires_login', False, repr(e))
try:
    http('/api/conversations'); ok('api_no_auth_403', False, 'unexpected ok')
except urllib.error.HTTPError as e: ok('api_no_auth_403', e.code==403, str(e.code))
try:
    http('/api/conversations', BAD); ok('bad_domain_403', False, 'unexpected ok')
except urllib.error.HTTPError as e: ok('bad_domain_403', e.code==403, str(e.code))
try:
    http('/api/conversations', BAD_ZYDON_COM); ok('zydon_com_blocked_403', False, 'unexpected ok')
except urllib.error.HTTPError as e: ok('zydon_com_blocked_403', e.code==403, str(e.code))
try:
    r=http('/api/conversations', HEAD, timeout=25); data=json.loads(r.read()); ok('cf_access_ok', data.get('user',{}).get('id')=='rafael')
except Exception as e: ok('cf_access_ok', False, repr(e)); data={'conversations':[]}
# token antigo bloqueado
try:
    users=json.load(open(PROJECT/'controle/channel_users.json')); tok=users['rafael']['token']
    http('/api/conversations?u=rafael&t='+urllib.parse.quote(tok)); ok('legacy_token_blocked', False, 'unexpected ok')
except urllib.error.HTTPError as e: ok('legacy_token_blocked', e.code==403, str(e.code))
except Exception as e: ok('legacy_token_blocked', False, repr(e))
# túneis
try:
    out=subprocess.run(['pgrep','-af','cloudflared tunnel --url http://127.0.0.1:879|localtunnel --port 8790|lt --port 8790'],capture_output=True,text=True)
    real=[l for l in out.stdout.splitlines() if 'pgrep -af' not in l and ('cloudflared tunnel --url http://127.0.0.1:879' in l or 'localtunnel --port 8790' in l or 'lt --port 8790' in l)]
    ok('public_tunnels_paused', not real, '\n'.join(real[:3]))
except Exception as e: ok('public_tunnels_paused', False, repr(e))
# inbox
convs=data.get('conversations',[])
ok('conversations_nonempty', len(convs)>0, str(len(convs)))
raw=[]; internal=[]; forbidden=[]
internal_digits={'553484255965','553484477245','553484325076','553484295409','553484428888','553496698718'}
for c in convs:
    title=(c.get('title') or '')+' '+(c.get('subtitle') or '')
    if '@lid' in title or '@s.whatsapp.net' in title or '@g.us' in title: raw.append(c.get('id'))
    chat=c.get('chat') or ''
    if chat.endswith('@g.us') or chat=='status@broadcast' or chat.endswith('@broadcast'): forbidden.append(chat)
    digs=''.join(ch for ch in chat if ch.isdigit())
    if any(digs.startswith(n) for n in internal_digits): internal.append(chat)
ok('no_raw_jid_visible', not raw, str(raw[:5]))
ok('no_group_broadcast', not forbidden, str(forbidden[:5]))
ok('no_internal_chip_chats', not internal, str(internal[:5]))
# refined responder
hot=[]
def actionable(c):
    li=float(c.get('lastIncomingTime') or 0); lo=float(c.get('lastOutgoingTime') or 0); lt=float(c.get('lastTime') or 0)
    if not li or li < lo: return False
    if abs(li-lt)>2 and not ((c.get('last') or {}).get('fromMe') is False): return False
    if (c.get('localStatus') or 'open')=='resolved' and li <= float(c.get('localUpdatedAt') or 0): return False
    m=c.get('lastIncoming') or c.get('last') or {}; txt=str(m.get('text') or '').strip(); media=any(m.get(k) for k in ['mediaUrl','mediaName','mediaPath','mimetype'])
    return bool(txt or media)
hot=[c for c in convs if actionable(c)]
ok('responder_refined_count_sane', 0 <= len(hot) <= len(convs), str(len(hot)))
# CH-042: roteamento inteligente por chip saudável/permitido
routing_missing=[c.get('id') for c in convs[:80] if not all(k in c for k in ['sendPort','sendPortLabel','sendRoutingReason','sendRoutingChanged','sendRoutingHealth'])]
ok('routing_fields_present', not routing_missing, str(routing_missing[:5]))
allowed_ports=set()
try:
    for p in data.get('user',{}).get('ports',[]): allowed_ports.add(int(p.get('port')))
except Exception: pass
bad_send_ports=[(c.get('id'),c.get('sendPort')) for c in convs if c.get('sendPort') is not None and int(c.get('sendPort')) not in allowed_ports]
ok('routing_send_port_allowed', not bad_send_ports, str(bad_send_ports[:5]))
changed_routes=[c for c in convs if c.get('sendRoutingChanged')]
ok('routing_reason_when_changed', all(c.get('sendRoutingReason') for c in changed_routes), str(len(changed_routes)))
# CH-057: /queue do SDR inclui conversas de chips compartilhados quando o lead/deal é dele.
try:
    sdata=json.loads(http('/api/conversations', {'Cf-Access-Authenticated-User-Email':'sarah@zydon.com.br'}, timeout=25).read())
    sconvs=sdata.get('conversations',[])
    sallowed={int(p.get('port')) for p in sdata.get('user',{}).get('ports',[])}
    sshared=[c for c in sconvs if c.get('sharedFromPort')]
    ok('shared_queue_sarah_has_shared', len(sshared)>0, str(len(sshared)))
    ok('shared_queue_send_port_allowed', all((c.get('readOnlyInstitutional') and c.get('sendPort') is None) or int(c.get('sendPort') or 0) in sallowed for c in sshared), str([(c.get('id'),c.get('sendPort'),c.get('readOnlyInstitutional')) for c in sshared[:5]]))
    if sshared:
        sid=sshared[0]['id']
        smsg=json.loads(http('/api/messages?conv='+urllib.parse.quote(sid), {'Cf-Access-Authenticated-User-Email':'sarah@zydon.com.br'}, timeout=20).read())
        ok('shared_queue_messages_allowed_owner', len(smsg.get('messages') or [])>0, sid)
        try:
            http('/api/messages?conv='+urllib.parse.quote(sid), {'Cf-Access-Authenticated-User-Email':'breno@zydon.com.br'}, timeout=10)
            ok('shared_queue_messages_forbidden_other_sdr', False, 'unexpected ok')
        except urllib.error.HTTPError as e:
            ok('shared_queue_messages_forbidden_other_sdr', e.code==403, str(e.code))
except Exception as e:
    ok('shared_queue_sarah_has_shared', False, repr(e)); ok('shared_queue_send_port_allowed', False, repr(e)); ok('shared_queue_messages_allowed_owner', False, repr(e)); ok('shared_queue_messages_forbidden_other_sdr', False, repr(e))
# CH-058: perfis supervisores veem tudo; SDRs continuam restritos.
try:
    sup_expected={'mariana@zydon.com.br','lucas.resende@zydon.com.br','rafael@zydon.com.br'}
    for email in sup_expected:
        sd=json.loads(http('/api/conversations', {'Cf-Access-Authenticated-User-Email':email}, timeout=30).read())
        ok('supervisor_view_all_'+email.split('@')[0], sd.get('user',{}).get('view_all') and len(sd.get('user',{}).get('ports',[]))==6, str(sd.get('user',{})))
    bd=json.loads(http('/api/conversations', {'Cf-Access-Authenticated-User-Email':'breno@zydon.com.br'}, timeout=25).read())
    ok('regular_sdr_not_view_all_breno', not bd.get('user',{}).get('view_all') and len(bd.get('user',{}).get('ports',[]))==1, str(bd.get('user',{})))
except Exception as e:
    ok('supervisor_view_all_mariana', False, repr(e)); ok('supervisor_view_all_lucas.resende', False, repr(e)); ok('supervisor_view_all_rafael', False, repr(e)); ok('regular_sdr_not_view_all_breno', False, repr(e))
# CH-050: resumo automático heurístico
ai_missing=[c.get('id') for c in convs[:120] if not isinstance(c.get('aiSummary'), dict) or not c['aiSummary'].get('summary') or not c['aiSummary'].get('nextAction')]
ok('ai_summary_present', not ai_missing, str(ai_missing[:5]))
bad_temp=[(c.get('id'),(c.get('aiSummary') or {}).get('temperature')) for c in convs[:120] if (c.get('aiSummary') or {}).get('temperature') not in ('quente','morno','frio')]
ok('ai_summary_temperature_valid', not bad_temp, str(bad_temp[:5]))
# CH-052: áudio/transcrição/fila pesquisável
bad_audio_fields=[c.get('id') for c in convs[:120] if 'audioPending' not in c or 'audioTranscriptText' not in c]
ok('audio_fields_present', not bad_audio_fields, str(bad_audio_fields[:5]))
audio_convs=[c for c in convs if int(c.get('audioPending') or 0)>0 or c.get('audioTranscriptText')]
ok('audio_queue_sane', len(audio_convs) <= len(convs), str(len(audio_convs)))
try:
    sd=json.loads(http('/api/conversations', {'Cf-Access-Authenticated-User-Email':'sarah@zydon.com.br'}, timeout=25).read())
    sarah_audio=next((c for c in sd.get('conversations',[]) if str(c.get('port'))=='4601' and ('99875-6405' in (c.get('title') or '') or c.get('id')=='4601::5524998756405@s.whatsapp.net')), None)
    ok('sarah_audio_conversation_visible', bool(sarah_audio), str((sarah_audio or {}).get('id')))
    if sarah_audio:
        t0=time.time(); md=json.loads(http('/api/messages?conv='+urllib.parse.quote(sarah_audio['id']), {'Cf-Access-Authenticated-User-Email':'sarah@zydon.com.br'}, timeout=8).read()); elapsed=time.time()-t0
        am=[m for m in md.get('messages',[]) if (m.get('mediaType') or '').lower()=='audio' or str(m.get('mimetype') or '').startswith('audio/')]
        ok('sarah_audio_messages_return_media', bool(am) and any(m.get('mediaUrl') for m in am), str(am[:1]))
        prev=[m for m in md.get('messages',[]) if m.get('fromMe') and 'Bom dia, Geraldo. Sarah aqui da Zydon' in str(m.get('text') or '')]
        ok('sarah_audio_includes_previous_outgoing', bool(prev) and md.get('messages',[]).index(prev[0]) < md.get('messages',[]).index(am[0]), str([m.get('text') for m in md.get('messages',[])[:3]]))
        ok('audio_messages_not_blocking_on_transcribe', elapsed < 5, f'{elapsed:.2f}s')
except Exception as e:
    ok('sarah_audio_conversation_visible', False, repr(e)); ok('sarah_audio_messages_return_media', False, repr(e)); ok('sarah_audio_includes_previous_outgoing', False, repr(e)); ok('audio_messages_not_blocking_on_transcribe', False, repr(e))
auto_missing=[c.get('id') for c in convs if not isinstance(c.get('automation'), dict)]
ok('automation_summary_present', not auto_missing, str(auto_missing[:5]))
auto_with_events=sum(1 for c in convs if (c.get('automation') or {}).get('lastAutomationAt'))
ok('automation_events_detected', auto_with_events>0, str(auto_with_events))
# hubspot read on first found
hs_found=False
for c in convs[:80]:
    try:
        r=http('/api/hubspot?conv='+urllib.parse.quote(c['id']), HEAD, timeout=20); h=json.loads(r.read())
        if h.get('found') and h.get('contact'):
            hs_found=True; break
    except Exception: pass
ok('hubspot_read_found_sample', hs_found)
# endpoints protected
# chips health / scale
try:
    chips=json.loads(http('/api/chips', HEAD, timeout=20).read()).get('chips',[])
    ok('chips_health_present', bool(chips) and all(('healthScore' in c and 'loadPct' in c and 'responseRate' in c) for c in chips), str(len(chips)))
    ok('chips_limit_30', bool(chips) and all(c.get('suggestedLimit')==30 for c in chips), str([c.get('suggestedLimit') for c in chips[:8]]))
except Exception as e:
    ok('chips_health_present', False, repr(e))
    ok('chips_limit_30', False, repr(e))
# endpoints protected
for path,name in [('/api/state','state_no_auth_403'),('/api/hubspot/action','hubspot_action_no_auth_403')]:
    try:
        http(path, {'Content-Type':'application/json'}, 'POST', b'{}'); ok(name, False, 'unexpected ok')
    except urllib.error.HTTPError as e: ok(name, e.code==403, str(e.code))
# admin users/chips: só admin, sem vazar token
try:
    http('/api/admin/users'); ok('admin_users_no_auth_403', False, 'unexpected ok')
except urllib.error.HTTPError as e: ok('admin_users_no_auth_403', e.code==403, str(e.code))
try:
    http('/api/admin/users', {'Cf-Access-Authenticated-User-Email':'sarah@zydon.com.br'}); ok('admin_users_nonadmin_403', False, 'unexpected ok')
except urllib.error.HTTPError as e: ok('admin_users_nonadmin_403', e.code==403, str(e.code))
try:
    r=http('/api/admin/users', HEAD); adm=json.loads(r.read()); raw=json.dumps(adm)
    ok('admin_users_admin_ok', adm.get('ok') and len(adm.get('ports',[]))>=1 and len(adm.get('users',[]))>=1)
    ok('admin_users_no_token_leak', 'token' not in raw)
except Exception as e:
    ok('admin_users_admin_ok', False, repr(e)); ok('admin_users_no_token_leak', False, repr(e))
# invariants/static
s=(PROJECT/'scripts/channel_panel_v2.py').read_text()
for term in ['sendInFlight','_dedupe_send','/api/send-file','quickTemplates','data-theme','/api/hubspot/action','/api/state','suggestedReplyForActive','✨ Sugerir resposta','Preenche o texto, não envia','/api/transcribe','audioPending','Áudios pendentes','summary_note','followup','sharedFromPort','SHARED_DEAL_VISIBILITY_PORTS','conversation_id_allowed','sharedBadge','view_all','user_can_view_all','effective_ports','transcribePendingAudioForActive','Carregando mensagens…','Não transcrever de forma síncrona','preserveScroll','wasNearBottom',"document.activeElement.id==='composer'",'archived','Arquivadas','archiveConv','matchesSearch','phoneVariants','[data-theme="dark"] .bulkbar','pipeCallFilter','pipeWhatsFilter','pipeFiltersBlock','hasCall','hasWhatsApp','com ligação','sem WhatsApp']:
    ok('invariant_'+term, term in s)
# JS syntax
start=s.index('<script>')+len('<script>'); end=s.index('</script>', start)
js=pathlib.Path('/tmp/channel_v2_check.js'); js.write_text(s[start:end])
r=subprocess.run(['node','--check',str(js)],capture_output=True,text=True)
ok('javascript_syntax', r.returncode==0, r.stderr[:300])
# heartbeat script
r=subprocess.run(['python3','/root/.hermes/scripts/zydon_channel_v2_security_heartbeat.py'],capture_output=True,text=True)
ok('security_heartbeat', r.returncode==0, r.stdout+r.stderr)

print(json.dumps({'ok':all(x[1] for x in results),'results':[{'name':n,'ok':c,'detail':d} for n,c,d in results]},ensure_ascii=False,indent=2))
sys.exit(0 if all(x[1] for x in results) else 1)
