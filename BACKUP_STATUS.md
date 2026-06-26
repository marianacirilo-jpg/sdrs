# BACKUP_STATUS — Zydon Prospecção

Atualizado em: 2026-06-24T16:58:52.634575+00:00

## Estado verificado

- Projeto persistente: `/root/.hermes/zydon-prospeccao`
- Backup Google Drive: `gdrive:prospeccao_zydon`
- Cron ativo: `zydon-drive-sync` a cada 5 min
- Script operacional: `/root/.hermes/scripts/sync_drive.sh`
- Cópia versionada no projeto/Drive: `scripts/sync_drive.sh`
- Guard fail-closed: mínimo 100 arquivos; source atual validado com 880 arquivos
- `rclone sync` usa `--backup-dir gdrive:prospeccao_zydon-backups/backup-YYYY-MM-DD`
- Logs vivos (`logs/**`) são excluídos para não quebrar hash durante escrita contínua

## Última verificação manual desta sessão

- `sync_drive.sh` executou com exit 0
- `rclone check` encontrou 0 diferenças e 880 arquivos iguais
- `BACKUP_FAILED.flag` ausente

## Observação sobre credenciais

Credenciais reais ficam em `/root/.hermes/credentials/` por segurança. Este diretório é persistente no ambiente Hermes, mas não é copiado para o Drive do projeto em texto puro. Hoje `google_oauth.env` ainda não tem segredo real do Google; só contém redirect/base URL.
