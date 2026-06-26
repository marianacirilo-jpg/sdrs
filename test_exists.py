#!/usr/bin/env python3
import subprocess, json
# Testar o endpoint /exists diretamente
urls = [
    "http://localhost:4500/exists?jid=5531985550860@s.whatsapp.net",
    "http://localhost:4500/exists?jid=5511982028007@s.whatsapp.net",
]
for u in urls:
    rr = subprocess.run(["curl","-s",u], capture_output=True, text=True, timeout=15)
    print(u)
    print("  ->", rr.stdout[:300])
    print()
