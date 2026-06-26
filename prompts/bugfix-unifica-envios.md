# BUGFIX: unificar controle de envios entre os 2 crons (honrar mesmo arquivo)

## Contexto
Projeto Zydon em `/root/.hermes/zydon-prospeccao`. Existem 2 crons que enviam WhatsApp e DEVEM compartilhar o MESMO controle de duplicidade, mas hoje estão desalinhados:

1. **Cron autônomo** (`motor/gate.py` + `motor/ciclo.py`) → lê/escreve `controle/wpp_envios.json`. Estrutura: `{"envios": [ {"date":..., "to": "jid", "slug":..., "nome":..., ...}, ... ]}`. Este é o arquivo REAL (60 envios, atualizado).
2. **Cron recorrente** (`/root/.hermes/zydon-prospeccao/disparo_dinamico.py`) → lê/escreve `/root/.hermes/zydon-prospeccao/wpp_envios.json` (RAIZ). Esse arquivo **NÃO EXISTE**. A função `load_envios()` faz `except: return {}` → retorna vazio → acha que ninguém foi enviado → **pode DUPLICAR envios**.

## Objetivo
Fazer o `disparo_dinamico.py` usar EXATAMENTE o mesmo arquivo dos outros dois: `controle/wpp_envios.json`, com a estrutura compatível. Assim os 3 motores (gate, ciclo, disparo_dinamico) compartilham uma única fonte de verdade e é impossível duplicar.

## Arquivo a editar
`/root/.hermes/zydon-prospeccao/disparo_dinamico.py`

## Especificação

### 1) Trocar o caminho do arquivo
Linha 38: 
```python
WPP_ENVIOS = '/root/.hermes/zydon-prospeccao/wpp_envios.json'
```
→
```python
WPP_ENVIOS = '/root/.hermes/zydon-prospeccao/controle/wpp_envios.json'
```

### 2) Adaptar `load_envios()` para a estrutura real
O arquivo real é `{"envios": [ {"to": "5511...@c.us", "slug":..., "date":...}, ... ]}` (LISTA dentro da chave "envios"). Hoje a função assume um dict.

Reescrever `load_envios()` para:
- Ler o arquivo.
- Se for `{"envios": [...]}` → retornar a lista interna.
- Se for uma lista direta → retornar a lista.
- Se for um dict de dicts (formato antigo legacy) → converter para lista de valores.
- Se não existir → retornar `[]` (lista vazia, NUNCA dict vazio).
- Sempre retornar uma **LISTA** de registros de envio.

### 3) Adaptar `save_envios()` para preservar a estrutura real
Hoje faz `json.dump(envios, ...)` assumindo dict. Reescrever para:
- Receber uma lista de registros.
- Escrever no formato real: `{"envios": [ ... ]}` com `ensure_ascii=False, indent=2`.
- IMPORTANTE: ao ADICIONAR um novo envio, fazer READ-MODIFY-WRITE — ler a lista atual, APPEND o novo registro, escrever de volta. NUNCA sobrescrever a lista inteira (senão apaga histórico dos outros crons).

### 4) Adaptar TODOS os usos de `load_envios()` no script
O script hoje usa `envios.values()` (assume dict). Buscar todas as ocorrências de `.values()` em envios e adaptar para iterar a lista. Especificamente verificar:
- A linha com `sum(1 for v in envios.values())` → adaptar para `len(envios)` ou filtrar por SDR.
- A linha de "já enviado" check → comparar o `to` (jid) ou `slug` do lead atual contra os registros da lista (buscar por `r.get('to')` ou `r.get('slug')` ou email igual ao jid do lead).
- Garantir que a comparação de "já enviado" usa o JID (`55...@c.us`) pois é a chave estável entre os dois formatos.

### 5) Adaptar onde ADICIONA um novo envio
Hoje provavelmente faz `envios[chave] = {...}`. Mudar para `envios.append({"date":..., "to": jid, "slug":..., "nome":..., "sdr":..., "text_status":"ok"})` e depois `save_envios(envios)` com read-modify-write.

### 6) NÃO QUEBRAR o cron autônomo
O `controle/wpp_envios.json` já tem 60 registros no formato `{"envios": [...]}`. O disparo_dinamico.py deve conseguir LER esses 60 registros e usá-los como dedup. Depois de rodar, os novos envios do recorrente devem aparecer mesclados na mesma lista.

## Restrições
- Editar SOMENTE `disparo_dinamico.py`. NÃO tocar em gate.py, ciclo.py, nem em nenhum outro arquivo.
- NÃO alterar a lógica de negócio (consulta HubSpot, qualificação SDR, delay de 30s, limit). Só alinhar o controle de envios.
- Manter os campos que já são registrados (date, to, slug, nome, sdr, text_status).
- Preservar os 60 registros existentes — o read-modify-write garante isso.

## Verificação final
Ao terminar, imprimir:
1. O caminho novo de WPP_ENVIOS.
2. Rodar mentalmente: `load_envios()` lendo o arquivo real e mostrar quantos registros carrega (esperado: ~60).
3. Mostrar que a busca de "já enviado" funciona: pegar um jid que SABEMOS que está no arquivo (ex: `553496698718@s.whatsapp.net` ou qualquer um dos 60) e confirmar que retorna True.
4. `python3 -c "import ast; ast.parse(open('/root/.hermes/zydon-prospeccao/disparo_dinamico.py').read()); print('SINTAXE OK')"`
5. Confirmação de SINTAXE OK.
