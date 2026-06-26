# Reservas de portas WhatsApp — Zydon

Atualizado: 2026-06-23

| Porta | Nome/uso | Auth dir | Status |
|---|---|---|---|
| 4600 | Mariana / fallback principal inbound | `/root/.hermes/whatsapp-extra/auth_single` | conectado como Mariana \| Zydon (`553484255965:6`) |
| 4601 | Sarah | `/root/.hermes/whatsapp-extra/auth_4601` | offline / sem processo rodando |
| 4602 | Breno | `/root/.hermes/whatsapp-extra/auth_4602` | offline / sem processo rodando |
| 4603 | Lucas | `/root/.hermes/whatsapp-extra/auth_4603` | conectado como Lucas Batista (`553484295409:13`) |
| 4604 | Sarah 2 / SDR follow-up | `/root/.hermes/whatsapp-extra/auth_4604_sarah2` | conectado; NÃO usar na rotação Mariana do SAF/MQL; validar `/status` + `/me` antes de qualquer follow-up |
| 4605 | Breno 2 / rotação Breno follow-up | `/root/.hermes/whatsapp-extra/auth_4605_breno2` | conectado como Breno Mendonça (`553484325076:26`) |
| 4606 | Lucas institucional / rotação SAF-MQL | `/root/.hermes/whatsapp-extra/auth_4606_lucas_institucional` | conectado como Lucas Resende (`553484428888:22`); usar junto com Mariana/4600 para diagnósticos e alertas do grupo |
| 4607 | Rafael institucional / rotação SAF-MQL | `/root/.hermes/whatsapp-extra/auth_4607_rafael_institucional` | conectado como Rafael Calixto (`553496698718:30`); usar junto com Mariana/4600 e Lucas/4606 para diagnósticos e alertas do grupo |

Regra SAF/MQL: diagnósticos enviados ao lead e alertas/resumos no grupo rotacionam pelos chips institucionais: Mariana/4600 + Lucas institucional/4606 + Rafael institucional/4607 (após conectar). Esses números NÃO são SDRs; mensagem deve dizer que um consultor/consultora chama logo logo. No grupo avisar claramente se é MQL ou NÃO-MQL. Ao lead: enviar diagnóstico + PDF; saudação/timing sempre por BRT (bom dia/tarde/noite; jaja/amanhã/segunda conforme horário/fim de semana).

Regra SDR/follow-up: 4604 agora é Sarah 2 e fica reservado para follow-up/SDR. Não usar 4604 como Mariana nem como fallback do SAF/MQL. Processo atual ainda usa o auth legado `auth_4604_mariana2`; em novos starts preferir o auth renomeado `auth_4604_sarah2` após migração segura.

```bash
cd /root/.hermes/whatsapp-extra
node single-extra.js --port 4604 --auth auth_4604_sarah2
```

Depois validar `/me` antes de qualquer uso.

Porta extra Breno 2: usar `4605` com auth isolado `auth_4605_breno2`.
