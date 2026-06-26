#!/usr/bin/env bash
set -euo pipefail
cd /root/.hermes/zydon-prospeccao
python3 -m py_compile scripts/roteiro_panel.py tests/test_roteiro_panel.py
python3 - <<'PY'
from pathlib import Path
s=Path('scripts/roteiro_panel.py').read_text()
js=s[s.index('<script>')+8:s.index('</script></body></html>')]
Path('/tmp/roteiro_frontend.js').write_text(js)
print('roteiro_frontend_js_bytes', len(js))
PY
node --check /tmp/roteiro_frontend.js
python3 -m unittest tests/test_roteiro_panel.py -v
python3 - <<'PY'
import importlib.util
spec=importlib.util.spec_from_file_location('rp','scripts/roteiro_panel.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.PRESENTATION_STAGE_ID=='990617426'
assert mod.roteiro_can_view_all('rafael')
assert mod.roteiro_can_view_all('lucas_resende')
assert mod.google_configured(), 'Google OAuth não configurado'
print('Roteiro release gate OK')
PY
