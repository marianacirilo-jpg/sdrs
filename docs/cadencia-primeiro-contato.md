# Cadência automática — Primeiro Contato sem resposta

Implementação: `scripts/cadencia_primeiro_contato.py`.

## O que faz

- Busca negócios no pipeline principal (`671008549`) que ainda estão em `Primeiro Contato` (`1214320997`) e pertencem a Breno, Sarah ou Lucas Batista.
- Usa `controle/wpp_envios.json` como fonte do Dia 0 (`msg_type=primeiro_contato` ou `primeiro_contato_backlog_institucional`) e das tentativas seguintes (`msg_type=primeiro_contato_cadencia`).
- Só considera elegível quando:
  - o negócio continua em Primeiro Contato;
  - não existe resposta do lead no histórico da bridge após o Dia 0;
  - não existe task comercial/manual após o Dia 0;
  - não existe ligação atendida/conversa;
  - não existe reunião associada/agendada/efetuada;
  - respeitou janela mínima: tentativa N só após D+(N-1) e pelo menos 20h desde a última tentativa.
- Envia no máximo 4 tentativas totais contando o Dia 0.
- Depois de 4 tentativas sem interação, não envia mais WhatsApp: cria tarefa de nutrição/material rico com `--mark-nurture`.

## Modos

Prévia segura, sem envio e sem task:

```bash
cd /root/.hermes/zydon-prospeccao
python3 scripts/cadencia_primeiro_contato.py --dry-run --limit 10
```

Prévia JSON para revisão:

```bash
python3 scripts/cadencia_primeiro_contato.py --dry-run --limit 20 --json > /tmp/cadencia_primeiro_contato_preview.json
```

Envio real, somente após aprovação:

```bash
python3 scripts/cadencia_primeiro_contato.py --send --limit 3 --max-per-hour 3 --sleep-seconds 300
```

Marcar nutrição/material rico após 4 tentativas sem resposta, sem enviar WhatsApp:

```bash
python3 scripts/cadencia_primeiro_contato.py --mark-nurture --limit 10
```

## Registros criados no envio real

- WhatsApp via bridge do SDR dono, escolhida pelas regras existentes de `disparo_dinamico.py`.
- Registro em `controle/wpp_envios.json` com:
  - `msg_type=primeiro_contato_cadencia`;
  - `attempt_number=2|3|4`;
  - `campaign_id=cadencia_primeiro_contato_sem_resposta`;
  - `deal_id`, `contact_id`, `sender_name`, `bridge_port`, `send_response`.
- Task COMPLETED no HubSpot associada ao contato (`typeId 204`) e negócio (`typeId 216`).
- Linha analítica em `controle/cadencia_primeiro_contato_metrics.jsonl` para medir quem recebeu tentativa, etapa, owner, tempo desde D0 e posterior evolução.

## Ativação sugerida após aprovação

Rodar primeiro por alguns dias em `--dry-run` e revisar amostras no Channel/HubSpot. Depois, agendar em horário comercial com limite baixo, por exemplo a cada hora útil:

```bash
python3 scripts/cadencia_primeiro_contato.py --send --limit 3 --max-per-hour 3 --sleep-seconds 300
```

Não ativar simultaneamente com lotes manuais grandes de SDR para evitar encavalamento de mensagens no mesmo chip.
