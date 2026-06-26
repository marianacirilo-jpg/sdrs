# BUGFIX: cutoff deve avançar pelo último envio, não por janela relativa

## Contexto
Projeto de prospecção Zydon em `/root/zydon-prospeccao`. Dois motores Python buscam leads no HubSpot e estão usando **janela de tempo relativa** (agora − 24h / agora − 1 dia) para decidir quais leads processar. Isso é um BUG: a cada execução o sistema reavalia tudo das últimas 24h e só não repete por causa da dedup de email. Se um lead enviado cai dentro da janela E o email não casa (ou foi recriado), ele volta a ser candidato. Já aconteceu de reprocessar lead enviado no dia anterior.

## A correção exigida
O cutoff NUNCA deve ser uma janela relativa (agora − X). Deve ser o **timestamp do último envio bem-sucedido** registrado em `controle/wpp_envios.json`. Assim o sistema só olha pra FRENTE (leads criados DEPOIS do último envio) e é impossível reprocessar.

## Arquivos a editar
1. `/root/zydon-prospeccao/motor/gate.py` — função de busca de contatos (linha ~345): `cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)`.
2. `/root/zydon-prospeccao/motor/ciclo.py` — função `hubspot_search_contacts(days=1)` (linha ~71): `since = datetime.now(timezone.utc) - timedelta(days=days)`.

## Especificação exata

### 1) Nova função utilitária `get_last_envio_timestamp()` (adicionar em ambos os arquivos, ou num helper compartilhado)
- Lê `controle/wpp_envios.json` (estrutura: `{"envios": [ {date, to, slug, ...}, ... ]}`).
- ATENÇÃO: o campo `date` está em FORMATOS MISTOS:
  - `"2026-06-23 00:35"` (YYYY-MM-DD HH:MM, horário BRT/UTC-3)
  - `"2026-06-22T17:53:38Z"` (ISO 8601 UTC, com Z)
  - Possivelmente `"2026-06-21 21:44"` também.
- Implementar parse robusto: tenta ISO com Z primeiro (trata como UTC); se não casar, tenta `%Y-%m-%d %H:%M` (trata como America/Sao_Paulo, converte pra UTC). Falha graciosa: se não conseguir parsear um registro, ignora-o (não quebra).
- Retorna o MAX timestamp em UTC (ISO `YYYY-MM-DDTHH:MM:SSZ`). Se o arquivo estiver vazio/inexistente, retorna `None`.

### 2) gate.py — substituir a janela relativa
Na função de busca de contatos:
- Calcular `last_ts = get_last_envio_timestamp()`.
- Se `last_ts` existir: `cutoff_iso = last_ts`.
- Se não existir (primeira execução / arquivo vazio): fallback para a janela atual (agora − WINDOW_HOURS) — NÃO quebrar.
- Trocar o operador `GTE` (maior ou igual) por `GT` (estritamente maior) no filtro de `createdate`, para nunca reprocessar o próprio último lead.
- Manter a dedup por email (`processed_emails.txt`) como rede de segurança secundária — NÃO remover.
- Atualizar o docstring da função para refletir a nova lógica (não mais "últimas 48h" e sim "após o último envio").

### 3) ciclo.py — mesmo ajuste em `hubspot_search_contacts`
- Mesma lógica: usar `get_last_envio_timestamp()` como cutoff; fallback janela relativa se vazio; operador `GT`; manter dedup.

### 4) Log
- Adicionar um `print`/log mostrando o cutoff usado: `f'[cutoff] último envio: {last_ts} (GT createdate)'` ou `f'[cutoff] sem envios anteriores, fallback janela {WINDOW_HOURS}h: {cutoff_iso}'`.

## Restrições
- NÃO alterar nada além da lógica de cutoff/busca. Não mexer em envio de WhatsApp, geração de PDF, HubSpot owner, lifecyclestage, etc.
- NÃO remover a dedup por email existente — ela continua como segunda barreira.
- Manter compatibilidade: se `wpp_envios.json` não existir ou estiver vazio, o sistema deve rodar (fallback janela relativa).
- Usar apenas stdlib (datetime, json, zoneinfo). Não adicionar dependências.
- Testar com `python3 -c "import ast; ast.parse(open('motor/gate.py').read()); ast.parse(open('motor/ciclo.py').read()); print('SINTAXE OK')"` ao final.

## Verificação final
Ao terminar, imprimir:
- O cutoff calculado atualmente rodando `get_last_envio_timestamp()` (esperado: ~2026-06-23T03:35:00Z, correspondente a 00:35 BRT do último lote).
- Confirmar que o operador foi trocado para GT em ambos os arquivos.
- Confirmação de sintaxe OK nos dois arquivos.
