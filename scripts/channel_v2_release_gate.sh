#!/usr/bin/env bash
set -euo pipefail
cd /root/.hermes/zydon-prospeccao

python3 -m py_compile scripts/channel_panel_v2.py tests/channel_v2_smoke_gate.py
python3 - <<'PY'
from pathlib import Path
s=Path('scripts/channel_panel_v2.py').read_text()
js=s[s.index('<script>')+8:s.index('</script></body></html>')]
Path('/tmp/channel_v2_frontend.js').write_text(js)
print('frontend_js_bytes', len(js))
PY
node --check /tmp/channel_v2_frontend.js
python3 -m unittest discover -s tests -v
python3 tests/channel_v2_smoke_gate.py

echo 'Channel V2 release gate OK'
