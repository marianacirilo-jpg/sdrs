#!/usr/bin/env bash
set -euo pipefail
cd /root/.hermes/zydon-prospeccao
python3 -m py_compile scripts/roteiro_panel.py tests/test_roteiro_panel.py
python3 - <<'PY'
from pathlib import Path
s=Path('scripts/roteiro_panel.py').read_text()
start=s.index('<script>')+len('<script>')
end=s.index('</script>', start)
js=s[start:end]
Path('/tmp/roteiro_frontend.js').write_text(js)
print('roteiro_frontend_js_bytes', len(js))
PY
node --check /tmp/roteiro_frontend.js
python3 -m unittest tests/test_roteiro_panel.py -v
python3 - <<'PY'
import importlib.util
spec=importlib.util.spec_from_file_location('rp','scripts/roteiro_panel.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.google_configured(), 'Google OAuth não configurado'
assert '1269308723' in mod.ROTEIRO_STAGES and '1269710168' in mod.ROTEIRO_STAGES and '990617426' in mod.ROTEIRO_STAGES and '1269308724' in mod.ROTEIRO_STAGES and '984052834' in mod.ROTEIRO_STAGES
assert '984052835' not in mod.ROTEIRO_STAGES
assert mod.ROTEIRO_EXECUTIVE_OWNER_LABELS=={'86020066':'João Vitor','89412201':'Samara','82229596':'Edimilson','89459433':'Ítalo'}
assert mod.INTRODUCTION_STAGE_ID=='1269308723'
assert [p['id'] for p in mod.dynamic_phases({}, mod.INTRODUCTION_STAGE_ID)][0]=='challenger_aquecimento'
assert len(mod.challenger_intro_context().get('challenges') or [])==5
assert mod.load_best_practices(), 'best practices vazio'
# backlog Lucas: modo apresentação + preparação/reunião/pós-reunião na UI
src=__import__('pathlib').Path('scripts/roteiro_panel.py').read_text()
for tok in ['Modo apresentação','Sair do modo apresentação','Preparação','Reunião','Pós-reunião','prepView','postView','stageView','togglePresent']:
    assert tok in src, f'UI sem {tok!r}'
# backlog Lucas: postMeetingTemplate no start presentation
tpl=mod.post_meeting_template(); keys={f['key'] for f in tpl['fields']}
assert {'diagnostico_confirmado','telas_demonstradas','valor_percebido','objecoes_riscos','proximo_passo','quem_participa'} <= keys, 'postMeetingTemplate incompleto'
# backlog Lucas: web research sem website gera buscas/dicas
wr=mod.fetch_internet_context({'name':'Empresa Teste'})
assert wr.get('webSearchQueries') and wr.get('webResearchHints'), 'web research sem queries/hints'
# backlog Lucas: owner labels via HubSpot owners (mock)
assert mod.owner_label('70000001',{'70000001':'Fulano HubSpot'})=='Fulano HubSpot', 'owner_label não usa HubSpot owners'
print('Roteiro release gate OK')
PY
