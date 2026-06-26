# Cadência automática — Primeiro Contato sem resposta

Data: 2026-06-24
Origem: direção Rafael — reduzir limbo de deals em **Primeiro Contato** que receberam abordagem, não responderam, e ficam poluindo o pipe enquanto SDR prioriza novos leads, respostas, Diagnóstico, Introdução e agenda/no-show.

## Problema

O marketing gera volume alto de leads. O time já consegue contatar todos os leads novos e fechar o dia, mas o gargalo aparece no **dia seguinte**: a prioridade natural vai para novos leads, quem respondeu ontem/hoje e quem já avançou no pipe (Diagnóstico SDR, Introdução/agendados/no-show). Com isso, a galera do limbo em **Primeiro Contato** fica travada: recebeu uma ou duas mensagens, não interagiu, mas também não foi perdido/nutrido. Sem resposta deles, não sobra tempo manual para reaquecer.

Distinção operacional importante:

- **Retorno Contato** = lead já respondeu/interagiu. Aí o SDR avança e segue conversando.
- **Primeiro Contato travado** = lead recebeu abordagem, não respondeu e fica há dias/semanas no limbo, poluindo o pipe.

A dor principal é essa: muitos leads, segundo contato, terceiro contato e despedida. A tela de operação do SDR precisa ajudar a fazer essas coisas, primeiro com prévia/playbooks e depois com automação segura.

## Decisão de produto

Criar uma cadência automática conservadora para leads em **Primeiro Contato sem resposta**:

- Dia 0: mensagem inicial / primeiro contato.
- Dia 1: 2º contato automático se não houve resposta/interação.
- Dia 2: 3º contato automático se ainda não houve resposta/interação.
- Dia 3/4: 4º contato automático se ainda não houve resposta/interação.
- Após 4 contatos sem resposta: remover da prioridade SDR e mandar para nutrição/marketing/material rico, em vez de manter poluindo o pipe.

## Regras duras

1. Não tocar lead que respondeu depois do último envio.
2. Não tocar lead que saiu de Primeiro Contato para Retorno/Diagnóstico/Introdução/etc.
3. Não tocar deal com ligação/reunião/tarefa comercial humana relevante após o último envio.
4. Não tocar conversa institucional privada — mesma regra de privacidade do Channel.
5. Respeitar owner/chip do SDR e limite diário/hora.
6. Mensagens precisam variar por dia e por lead; nada de blast idêntico.
7. Primeiro lançamento deve ser **dry-run + prévia**, sem envio automático.
8. Toda execução real deve registrar:
   - `msg_type`: `segundo_contato`, `terceiro_contato`, `quarto_contato`;
   - `deal_id`, `contact_id`, SDR, porta, `messageId`, texto;
   - task/atividade HubSpot concluída.
9. Depois de 4 tentativas sem resposta, criar marcação/nota para nutrição marketing em vez de nova cobrança SDR.

## Dry-run inicial

Script criado:

```bash
python3 scripts/cadencia_primeiro_contato_dryrun.py --limit 300 --sample 12
```

Saída em:

```txt
controle/cadencia_primeiro_contato_dryrun.json
```

Resultado inicial em 2026-06-24 18:41 BRT:

```txt
totalDeals analisados em Primeiro Contato: 300
aptos para 2º contato: 19
aguardando janela 24h: 14
responderam depois do envio: 3
sem primeiro contato registrado no ledger: 264
```

A categoria `sem_primeiro_contato_registrado` precisa de saneamento: pode ser deal em Primeiro Contato por automação antiga sem ledger, ou deal realmente sem abordagem SDR. Não ativar cadência real em massa antes de resolver essa lacuna.

## Direção de conteúdo da cadência

Rafael vai consolidar materiais dispersos do Drive/NotebookLM/Information numa pasta de contexto específica para Primeiro Contato. A cadência não deve ser “só queria falar com você”; cada tentativa precisa agregar valor e deixar claro **por que** vale conversar.

Estrutura desejada:

- D0: primeiro contato contextual, com motivo claro (“quero falar com você por isso”).
- D+1 / 2º contato: reforçar o motivo, conectando com uma dor/oportunidade da empresa.
- D+2 / 3º contato: trazer insight/relevância (“acho que tal coisa é relevante para vocês”).
- D+3/D+4 / 4º contato: abordagem leve, reconhecendo que talvez não seja prioridade agora; CTA simples (“me manda um OK/oi” ou link de agenda).
- Despedida/break-up: se não respondeu, encerrar com elegância (“talvez não seja o momento; ficamos de portas abertas”) e tirar o lead da prioridade SDR/nutrição, limpando o pipe.

Princípio: quem responde/levanta a mão fica em foco; quem não responde sai do limbo para melhorar a visão real do pipeline.

## Próxima implementação

1. Criar mensagens aprovadas para 2º/3º/4º contato por SDR usando o contexto consolidado pelo Rafael.
2. Criar script `cadencia_primeiro_contato_execute.py` com `--dry-run` default e `--apply` explícito.
3. Adicionar limite por SDR/chip:
   - máximo conservador por hora;
   - máximo diário por chip;
   - aborta na primeira falha de bridge.
4. Mostrar prévia no Channel/Foco SDR/Playbooks antes de ativar cron.
5. Métricas de funil:
   - perfil que responde ao 1º/2º/3º contato;
   - perfil que vira Diagnóstico/Introdução;
   - perfil que agenda e dá no-show;
   - perfil que vai para perda;
   - critérios para limar entrada ruim do funil.

## Status

Preparado como fila/kanban. Nenhum disparo real foi ativado ainda.
