# Disparo Perdido: Sumiço Início de Funil

**Goal:** executar um disparo controlado para negócios em `Primeiro Contato` sem atividade há mais de 3 semanas, avisando o lead pelo WhatsApp do SDR responsável, movendo o negócio para perdido com motivo `sumiço, início de funil`.

**Escopo informado:**
- Total em Primeiro Contato: 103
- Campanha: `SUMIÇO INICIO DE FUNIL`
- Ação: WhatsApp de despedida + mover negócio para perdido
- Motivo de perda: `sumiço, início de funil`
- Chips comunicadores disponíveis/mais quentes: Mariana, Lucas, Rafael, João Pedro, Gustavo
- Regra de assinatura/retorno: mensagem deve sempre orientar o lead a chamar o SDR correto: Lucas, Sarah/Sara ou Breno, usando o WhatsApp do SDR.

---

## 1. Regras de seleção dos 103 negócios

Selecionar somente negócios que atendam todos os critérios:

1. Pipeline SDR/Channel correto.
2. Etapa atual: `Primeiro Contato`.
3. Última atividade associada ao negócio há mais de 21 dias.
4. Negócio ainda aberto, não perdido, não ganho.
5. Lead com WhatsApp válido.
6. Owner/SDR mapeado para um dos SDRs ativos: Lucas Batista, Sarah/Sara ou Breno.
7. Excluir qualquer lead que tenha atividade recente em contato, deal, chamada, task, nota ou mensagem depois do corte de 21 dias.
8. Excluir leads pausados, sem consentimento ou sem telefone válido.

Antes de disparar, gerar uma prévia com:
- deal_id
- contact_id
- nome do lead
- empresa
- etapa atual
- owner/SDR
- WhatsApp do lead
- WhatsApp de retorno do SDR
- último timestamp de atividade
- ERP, se houver fonte confiável
- comunicador escolhido para envio
- template escolhido

---

## 2. Regra de mensagem

Tom da campanha:
- despedida educada;
- curta;
- humana;
- sem parecer cobrança pesada;
- sem emoji;
- sem travessão;
- sem jargão interno;
- sem afirmar ERP se não houver ERP confiável.

A mensagem sempre deve ter:
1. Saudação com primeiro nome.
2. Contexto: tentamos falar / vocês se desencontraram / agenda correu.
3. Aviso: vamos pausar as tentativas para não lotar o WhatsApp.
4. Retorno: se ainda fizer sentido, chamar o SDR pelo número dele.
5. Fechamento simples.

Não usar `[ERP]` quando:
- ERP estiver vazio;
- ERP for desconhecido;
- ERP vier de fonte fraca;
- ERP não for Bling, Omie, Olist/Tiny ou Sankhya e a mensagem ficar forçada.

Para ERPs nativos confirmados:
- Bling
- Omie
- Olist/Tiny
- Sankhya

Pode mencionar integração direta ao ERP.

Para TOTVS/outros:
- Não prometer integração nativa.
- Se mencionar, usar algo neutro: `com a operação comercial conectada ao processo de vocês`.

---

## 3. Templates base com variação

### Template A: objetivo, sem ERP

Olá [Nome], tudo bem?

Você estava falando com o [SDR], mas imagino que a correria aí na empresa tenha atrapalhado a agenda de vocês.

Como acabaram se desencontrando, vamos pausar as tentativas por aqui para não ficar lotando seu WhatsApp.

Se ainda fizer sentido digitalizar as vendas B2B e deixar seus clientes pedindo com mais autonomia, chama o [SDR] por aqui: [WhatsApp SDR].

Abraço e sucesso!

### Template B: objetivo, com ERP nativo confirmado

Olá [Nome], tudo bem?

Você estava falando com o [SDR], mas imagino que a rotina aí tenha enrolado a agenda e travado a nossa evolução.

Vamos pausar as tentativas por aqui para não ficar insistindo no seu WhatsApp.

Se o plano ainda é digitalizar as vendas B2B e criar uma operação 24h integrada ao [ERP], chama o [SDR] por aqui: [WhatsApp SDR].

Abraço e sucesso!

### Template C: mais curto

Oi [Nome], tudo bem?

Passando só para encerrar por aqui com cuidado.

Você e o [SDR] acabaram se desencontrando, então vamos pausar os contatos para não ficar insistindo.

Se ainda fizer sentido conversar sobre vendas B2B, portal para clientes e pedidos com mais autonomia, chama o [SDR] no [WhatsApp SDR].

Sucesso aí!

### Template D: mais consultivo, sem ERP

Olá [Nome], tudo certo?

Como não conseguimos evoluir a conversa com o [SDR], vou considerar que esse tema ficou sem prioridade agora.

Para não ficar enchendo seu WhatsApp, vamos pausar as tentativas por aqui.

Se em algum momento vocês quiserem retomar o plano de vender mais no B2B sem depender tanto de pedido manual, chama o [SDR] no [WhatsApp SDR].

Um abraço!

### Template E: com ERP confirmado, mas sem promessa exagerada

Olá [Nome], tudo bem?

Você estava falando com o [SDR] sobre a Zydon, mas parece que a agenda de vocês acabou correndo.

Vamos pausar o contato por aqui para não incomodar.

Se ainda fizer sentido estruturar um canal B2B para seus clientes comprarem com mais autonomia e conectado ao [ERP], chama o [SDR] no [WhatsApp SDR].

Abraço e sucesso!

### Template F: muito direto

Oi [Nome], tudo bem?

Como não conseguimos seguir a conversa com o [SDR], vamos pausar as tentativas por aqui.

Se quiser retomar o projeto de vendas B2B mais pra frente, chama o [SDR] no [WhatsApp SDR].

Abraço!

---

## 4. Distribuição dos envios pelos comunicadores

Usar comunicadores quentes para enviar as mensagens, mas sem confundir o retorno.

Comunicador que envia:
- Mariana
- Lucas
- Rafael
- João Pedro
- Gustavo

SDR para retorno:
- Lucas Batista
- Sarah/Sara
- Breno

Regra:
- O texto deve dizer `chama o [SDR] no [WhatsApp SDR]`.
- O número do remetente pode ser Gustavo/Mariana/etc., mas o CTA aponta para o SDR dono ou SDR responsável.

Distribuição sugerida para 103 leads:
- Dividir entre 5 comunicadores ativos, aproximadamente 20 a 21 leads por comunicador.
- Respeitar limite conservador de volume por chip no dia.
- Não disparar os 103 de uma vez. Fazer em lotes.

Lote sugerido:
1. Lote teste: 5 leads, um por comunicador.
2. Validar entrega, texto, logs e ausência de falhas.
3. Lote 1: 25 leads.
4. Pausa e checagem de respostas/falhas.
5. Lote 2: 25 leads.
6. Pausa.
7. Lote 3: 25 leads.
8. Lote final: restante.

Se algum chip falhar:
- parar somente o chip com falha;
- não repetir automaticamente para evitar duplicidade;
- conferir histórico/log antes de tentar de outro comunicador.

---

## 5. Ordem segura de execução

### Fase 0: dados que faltam do Rafael

Antes de executar, Rafael precisa passar:
1. WhatsApp do Lucas Batista para retorno.
2. WhatsApp da Sarah/Sara para retorno.
3. WhatsApp do Breno para retorno.
4. Confirmação se João Pedro está mesmo ativo para envio ou se fica fora.
5. Confirmação se quer mover para perdido imediatamente após envio ou somente após retorno de sucesso do endpoint.

Recomendação: mover para perdido somente após envio confirmado `success:true`.

### Fase 1: inventário de bridges

Validar `/me` de cada comunicador:
- Mariana
- Lucas
- Rafael
- João Pedro
- Gustavo

Registrar:
- porta
- nome retornado por `/me`
- telefone
- status
- se pode enviar hoje

### Fase 2: extração HubSpot

Buscar os 103 negócios:
- etapa Primeiro Contato;
- última atividade > 21 dias;
- owner/SDR;
- contato associado;
- telefone/WhatsApp;
- empresa;
- ERP confiável se existir.

Gerar CSV de prévia e não disparar ainda.

### Fase 3: montagem da campanha

Para cada lead:
- normalizar primeiro nome;
- mapear SDR correto;
- inserir WhatsApp do SDR;
- escolher template por rotação;
- decidir se pode citar ERP;
- escolher comunicador por distribuição;
- gerar mensagem final.

### Fase 4: lote teste

Enviar 5 mensagens:
- 1 por comunicador ativo;
- para leads reais do lote, se Rafael autorizar;
- ou para Rafael/validação, se quiser homologar texto antes.

Validar:
- `success:true`;
- `messageId` salvo;
- mensagem correta;
- sem duplicidade;
- lead certo;
- chip certo;
- SDR certo no CTA.

### Fase 5: disparo controlado

Executar lotes com pausas.

Para cada envio:
- enviar WhatsApp;
- salvar log com deal_id, contact_id, telefone, porta, remetente, texto, messageId, status;
- se sucesso, criar atividade/nota no HubSpot;
- mover deal para perdido;
- setar motivo `sumiço, início de funil`.

Se falhar:
- não mover para perdido;
- marcar como erro no CSV/log;
- revisar depois.

### Fase 6: relatório final

Reportar:
- total elegíveis;
- total enviados;
- total movidos para perdido;
- falhas por motivo;
- duplicidades evitadas;
- respostas recebidas durante execução;
- distribuição por comunicador;
- distribuição por SDR de retorno.

---

## 6. Critérios de segurança

1. Não enviar mensagem para lead sem telefone validado.
2. Não mover para perdido sem envio bem-sucedido, salvo se Rafael mandar explicitamente.
3. Não citar ERP sem fonte confiável.
4. Não chamar Lucas sem sobrenome em relatório interno: usar Lucas Batista quando houver ambiguidade.
5. Não usar chips pausados/removidos sem confirmar.
6. Não usar João Pedro se estiver removido/desativado no Channel atual, a menos que Rafael confirme que ele voltou.
7. Não gerar QR nem reiniciar bridge com envio em andamento, salvo falha clara.
8. Em erro 500/503/timeout, checar histórico antes de repetir.
9. Registrar tudo para auditoria.

---

## 7. Perguntas abertas

1. Quais são os números de WhatsApp de retorno de Lucas Batista, Sarah/Sara e Breno?
2. João Pedro está ativo mesmo para essa campanha ou fica fora?
3. Quer usar todos os 5 comunicadores ou limitar aos mais estáveis hoje?
4. O motivo de perda no HubSpot já existe exatamente como `sumiço, início de funil` ou precisa mapear para uma opção existente?
5. A etapa de perdido correta é `Negócio perdido` no mesmo pipeline?
6. Quer aprovar os 6 templates antes do lote teste?

---

## 8. Decisão recomendada

Minha recomendação operacional:

1. Você me passa os WhatsApps de Lucas Batista, Sarah/Sara e Breno.
2. Eu levanto os 103 no HubSpot e gero uma prévia sem disparar.
3. Eu te mostro amostra de 10 mensagens finais, com lead, SDR, comunicador e template.
4. Você aprova.
5. Eu mando 5 testes reais, um por comunicador.
6. Se tudo OK, executo em lotes e só movo para perdido quando o envio retornar sucesso.
