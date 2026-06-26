# Estado Atual do Sistema — Zydon Prospecção

Data: 21 junho 2026, 22:55 BRT (01:55 UTC)

## Status Backup
- Último ciclo: exit=0 (OK)
- Token: renovado e conectado
- Cron ativo: every 5m
- Sincronização completa executada

## No Drive (prospeccao_zydon/)
- PDFs de leads (todos)
- Motor (gen.py, render.py, batches)
- Aprendizados (md files)
- backup_config/ (configs rclone)
- controle/ (leads processados)

## No Drive (zydon_sistema_completo/)
- skills/zydon-prospeccao/
- scripts/ (rclone_backup.sh, run_fluxo_zydon.sh, sync_drive.sh, zydon.sh)
- configs/ (rclone.conf)
- aprendizado/

## Token
- OAuth com refresh_token (renovação automática)
- Backup redundante em /root/.hermes/backups/rclone.conf
- Pendente: Service Account (permanente, não expira)

## Como recuperar
1. Baixar tudo de prospeccao_zydon/ e zydon_sistema_completo/
2. Restaurar em /root/zydon-prospeccao/
3. Reinstalar .venv
4. Reauth rclone se necessário
