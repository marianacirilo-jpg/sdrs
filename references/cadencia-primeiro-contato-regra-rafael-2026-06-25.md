# Regra Rafael — Cadência Primeiro Contato / follow-ups SDR

Data: 2026-06-25
Fonte: correção direta do Rafael no Discord.

## Regra final

A cadência automática de follow-up SDR usa a **etapa atual do negócio no HubSpot** como filtro principal.

- Só faz follow-up se o negócio **está agora** na etapa `1214320997` / **Primeiro Contato**.
- Se o negócio saiu de **Primeiro Contato**, não faz follow enquanto estiver fora da etapa.
- Se o negócio saiu de **Primeiro Contato** e depois voltou para **Primeiro Contato**, ele volta a ser elegível; a cadência pode continuar conforme as tentativas já registradas.
- Não existe bloqueio permanente apenas porque o negócio saiu da etapa em algum momento anterior.

## O que NÃO bloqueia a cadência

Enquanto o negócio continua em **Primeiro Contato**, NÃO bloquear por atividade interna do HubSpot:

- task manual;
- task comercial;
- ligação feita ou atendida;
- reunião associada, agendada ou realizada;
- qualquer outra atividade interna do HubSpot.

Essas atividades podem existir, mas não devem tirar o lead da cadência se o negócio ainda está em Primeiro Contato.

## O que bloqueia / muda a cadência

- Resposta do lead no WhatsApp depois do primeiro contato: se o negócio ainda estiver em etapa inicial (`Lead Sem Contato`, `Primeiro Contato` ou `Retorno Contato`), mover para `998099482` / **Retorno Contato** e parar a cadência enquanto estiver fora de Primeiro Contato.
- **Nunca regredir** negócio que já esteja em **Introdução** ou qualquer etapa superior (`Diagnóstico EC`, apresentações, proposta, termos, fechado/perdido) para Retorno Contato. Nesses casos, criar tarefa/alerta para o responsável e preservar a etapa atual.
- Saída da etapa **Primeiro Contato**: parar follow-ups enquanto estiver fora.
- Retorno posterior para **Primeiro Contato**: volta a ser elegível.

## Implicação técnica

O script `scripts/cadencia_primeiro_contato.py` deve:

1. Buscar apenas deals que estão atualmente no pipeline principal e na etapa `1214320997`.
2. Não chamar task/call/meeting como critério de bloqueio.
3. Usar histórico WhatsApp para detectar resposta do lead após o primeiro contato.
4. Contar tentativas pelo ledger/histórico e continuar a próxima tentativa quando elegível.

Correção aplicada em 2026-06-25: removido bloqueio por `has_interaction_after_first()` dentro de `collect_candidates()`; task/ligação/reunião não bloqueiam mais.
