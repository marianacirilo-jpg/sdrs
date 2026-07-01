# Rotacionamento 5 Chips: Sumiço Início de Funil

**Goal:** disparar 103 mensagens de encerramento para leads em `Primeiro Contato` sem atividade há mais de 3 semanas, usando rotação entre 5 comunicadores, registrando envio e movendo negócios para perdido com motivo `sumiço, início de funil` apenas após envio confirmado.

**Contexto confirmado por Rafael:**
- Total alvo: 103 negócios.
- Campanha: `SUMIÇO INICIO DE FUNIL`.
- Stage origem: `Primeiro Contato`.
- Critério de inatividade: mais de 3 semanas sem atividade.
- Ação comercial: mandar WhatsApp e mover para perdido.
- Motivo: `sumiço, início de funil`.
- Chips comunicadores: Mariana, Lucas, Rafael, João Pedro e Gustavo.
- Porta João Pedro: `4609`.
- Porta Gustavo: `4610`.
- WhatsApps de retorno dos SDRs:
  - Breno: `5534984472414` / exibição `34 98447-2414`.
  - Sarah: `5534984095632` / exibição `34 98409-5632`.
  - Lucas Batista: `5534984295409` / exibição `34 98429-5409`.

---

## 1. Mapa de chips comunicadores

Usar os comunicadores apenas como remetentes. O CTA aponta sempre para o SDR dono do negócio.

| Comunicador | Porta | Observação |
|---|---:|---|
| Mariana | `4600` | Institucional quente |
| Lucas | `4606` | Institucional quente |
| Rafael | `4607` | Institucional quente, validar `/me` antes |
| João Pedro | `4609` | Confirmado por Rafael; precisa conectar/validar `/me` antes de uso |
| Gustavo | `4610` | Confirmado conectado como Gustavo Faria |

Antes de disparar, validar:

```bash
for p in 4600 4606 4607 4609 4610; do
  echo "=== $p ==="
  curl -s --max-time 5 http://127.0.0.1:$p/status
  echo
  curl -s --max-time 5 http://127.0.0.1:$p/me
  echo
 done
```

Critério para chip entrar na rotação:
- `/me` retorna `id`, `name` e `phone`.
- Não está `phone:null`.
- Não está pedindo QR.
- Envio teste retorna `success:true`.

Se João Pedro ainda não estiver conectado, rotação começa com 4 chips e ele entra no próximo lote após validar.

---

## 2. Distribuição dos 103 envios

### Distribuição ideal com 5 chips

103 leads dividido por 5 comunicadores:

| Comunicador | Quantidade alvo |
|---|---:|
| Mariana 4600 | 21 |
| Lucas 4606 | 21 |
| Rafael 4607 | 21 |
| João Pedro 4609 | 20 |
| Gustavo 4610 | 20 |
| **Total** | **103** |

### Distribuição se João Pedro ainda não estiver ativo

Começar com 4 chips sem ultrapassar volume agressivo:

| Comunicador | Quantidade inicial sugerida |
|---|---:|
| Mariana 4600 | 26 |
| Lucas 4606 | 26 |
| Rafael 4607 | 26 |
| Gustavo 4610 | 25 |
| **Total** | **103** |

Mas recomendado: se João Pedro vai entrar agora, aguardar a conexão dele e usar a distribuição de 5 chips.

---

## 3. Ordem de rotação

Usar round-robin simples para espalhar os envios:

1. Mariana 4600
2. Lucas 4606
3. Rafael 4607
4. João Pedro 4609
5. Gustavo 4610
6. Mariana 4600
7. Lucas 4606
8. Rafael 4607
9. João Pedro 4609
10. Gustavo 4610

E assim por diante até completar 103.

### Por que round-robin

- Evita concentrar volume em um chip.
- Reduz risco de bloqueio/instabilidade.
- Facilita auditoria.
- Se um chip cair, ele sai da fila e os demais continuam.

### Regra de falha

Se uma porta falhar:
1. Parar a porta da rotação.
2. Conferir `/me`, `/status` e histórico antes de repetir.
3. Não reenviar automaticamente para evitar duplicidade.
4. Marcar o lead como `erro_envio` e revisar no final.
5. Só mover para perdido quando o envio tiver `success:true` ou evidência clara de entrega no histórico.

---

## 4. Lotes de execução

### Lote 0: validação

Enviar 5 mensagens de homologação, uma por chip, preferencialmente para Rafael ou para leads selecionados que Rafael autorizar.

Objetivo:
- validar chip;
- validar texto;
- validar logs;
- validar movimentação para perdido em um caso controlado.

### Lote 1: 25 leads

- 5 por chip.
- Pausar após o lote.
- Checar falhas e respostas.

### Lote 2: 25 leads

- 5 por chip.
- Pausar e checar.

### Lote 3: 25 leads

- 5 por chip.
- Pausar e checar.

### Lote 4: 28 leads restantes

Distribuir:
- Mariana: +6
- Lucas: +6
- Rafael: +6
- João Pedro: +5
- Gustavo: +5

Total final aproximado:
- Mariana 21
- Lucas 21
- Rafael 21
- João Pedro 20
- Gustavo 20

---

## 5. Regra de SDR de retorno

O remetente pode ser qualquer comunicador, mas o CTA deve apontar para o SDR correto do negócio.

| Owner/SDR do deal | Nome no texto | WhatsApp no texto |
|---|---|---|
| Breno | Breno | `34 98447-2414` |
| Sarah/Sara | Sarah | `34 98409-5632` |
| Lucas Batista / Lucas Alcântara Batista | Lucas Batista | `34 98429-5409` |

Nunca escrever apenas `Lucas` no CTA. Usar `Lucas Batista` para evitar confusão.

---

## 6. Critério para citar ERP

Citar ERP somente se:
- existir propriedade confiável no HubSpot ou formulário;
- ERP for claro;
- mensagem não prometer algo indevido.

### ERPs nativos

Pode citar integração direta se o ERP for:
- Bling
- Omie
- Olist/Tiny
- Sankhya

Exemplo:
`integrada ao Omie`

### TOTVS e outros

Não prometer nativo. Preferir mensagem sem ERP ou com frase neutra:
`conectada ao processo comercial de vocês`

### Sem ERP

Não citar ERP.

---

## 7. Banco de mensagens para rotação

Usar rotação de templates para não mandar tudo igual. Cada mensagem deve preencher:
- `[Nome]`
- `[SDR]`
- `[WhatsApp SDR]`
- `[ERP]`, somente quando aplicável

### Mensagem 1: objetiva, sem ERP

Olá [Nome], tudo bem?

Você estava falando com o [SDR], mas imagino que a correria aí na empresa tenha atrapalhado a agenda de vocês.

Como acabaram se desencontrando, vamos pausar as tentativas por aqui para não ficar lotando seu WhatsApp.

Se ainda fizer sentido digitalizar as vendas B2B e deixar seus clientes pedindo com mais autonomia, chama o [SDR] no [WhatsApp SDR].

Abraço e sucesso!

### Mensagem 2: com ERP nativo confirmado

Olá [Nome], tudo bem?

Você estava falando com o [SDR], mas imagino que a rotina aí tenha enrolado a agenda e travado a nossa evolução.

Vamos pausar as tentativas por aqui para não ficar insistindo no seu WhatsApp.

Se o plano ainda é digitalizar as vendas B2B e criar uma operação 24h integrada ao [ERP], chama o [SDR] no [WhatsApp SDR].

Abraço e sucesso!

### Mensagem 3: curta

Oi [Nome], tudo bem?

Passando só para encerrar por aqui com cuidado.

Você e o [SDR] acabaram se desencontrando, então vamos pausar os contatos para não ficar insistindo.

Se ainda fizer sentido conversar sobre vendas B2B, portal para clientes e pedidos com mais autonomia, chama o [SDR] no [WhatsApp SDR].

Sucesso aí!

### Mensagem 4: consultiva

Olá [Nome], tudo certo?

Como não conseguimos evoluir a conversa com o [SDR], vou considerar que esse tema ficou sem prioridade agora.

Para não ficar enchendo seu WhatsApp, vamos pausar as tentativas por aqui.

Se em algum momento vocês quiserem retomar o plano de vender mais no B2B sem depender tanto de pedido manual, chama o [SDR] no [WhatsApp SDR].

Um abraço!

### Mensagem 5: com ERP sem exagero

Olá [Nome], tudo bem?

Você estava falando com o [SDR] sobre a Zydon, mas parece que a agenda de vocês acabou correndo.

Vamos pausar o contato por aqui para não incomodar.

Se ainda fizer sentido estruturar um canal B2B para seus clientes comprarem com mais autonomia e conectado ao [ERP], chama o [SDR] no [WhatsApp SDR].

Abraço e sucesso!

### Mensagem 6: muito direta

Oi [Nome], tudo bem?

Como não conseguimos seguir a conversa com o [SDR], vamos pausar as tentativas por aqui.

Se quiser retomar o projeto de vendas B2B mais pra frente, chama o [SDR] no [WhatsApp SDR].

Abraço!

### Mensagem 7: fechamento leve

Fala [Nome], tudo bem?

Como a conversa com o [SDR] não avançou nas últimas semanas, vou pausar por aqui para não ficar insistindo.

Se a prioridade de digitalizar as vendas B2B voltar para a mesa, chama o [SDR] no [WhatsApp SDR] que ele retoma com você.

Sucesso por aí!

### Mensagem 8: retomada futura

Olá [Nome], tudo bem?

A gente tentou evoluir a conversa por aqui, mas imagino que a agenda tenha ficado corrida.

Vou pausar as tentativas para não lotar seu WhatsApp.

Quando fizer sentido retomar a ideia de dar mais autonomia para seus clientes comprarem no B2B, chama o [SDR] no [WhatsApp SDR].

Abraço!

### Mensagem 9: foco em pedido manual

Oi [Nome], tudo certo?

Como não conseguimos avançar com o [SDR], vamos encerrar as tentativas por aqui.

Se mais pra frente vocês quiserem reduzir pedido manual e deixar o cliente B2B comprando com mais autonomia, chama o [SDR] no [WhatsApp SDR].

Um abraço e sucesso!

### Mensagem 10: institucional simples

Olá [Nome], tudo bem?

Como vocês acabaram se desencontrando com o [SDR], vamos pausar esse contato por enquanto.

A ideia é não ficar insistindo no seu WhatsApp sem necessidade.

Se ainda fizer sentido olhar para vendas B2B, portal do cliente e pedidos 24h, chama o [SDR] no [WhatsApp SDR].

Abraço!

---

## 8. Exemplos preenchidos

### Exemplo Breno, sem ERP

Olá Carlos, tudo bem?

Você estava falando com o Breno, mas imagino que a correria aí na empresa tenha atrapalhado a agenda de vocês.

Como acabaram se desencontrando, vamos pausar as tentativas por aqui para não ficar lotando seu WhatsApp.

Se ainda fizer sentido digitalizar as vendas B2B e deixar seus clientes pedindo com mais autonomia, chama o Breno no 34 98447-2414.

Abraço e sucesso!

### Exemplo Sarah, com Omie

Olá Fernanda, tudo bem?

Você estava falando com a Sarah, mas imagino que a rotina aí tenha enrolado a agenda e travado a nossa evolução.

Vamos pausar as tentativas por aqui para não ficar insistindo no seu WhatsApp.

Se o plano ainda é digitalizar as vendas B2B e criar uma operação 24h integrada ao Omie, chama a Sarah no 34 98409-5632.

Abraço e sucesso!

### Exemplo Lucas Batista, curto

Oi Marcelo, tudo bem?

Passando só para encerrar por aqui com cuidado.

Você e o Lucas Batista acabaram se desencontrando, então vamos pausar os contatos para não ficar insistindo.

Se ainda fizer sentido conversar sobre vendas B2B, portal para clientes e pedidos com mais autonomia, chama o Lucas Batista no 34 98429-5409.

Sucesso aí!

### Exemplo Breno, consultivo

Olá Renata, tudo certo?

Como não conseguimos evoluir a conversa com o Breno, vou considerar que esse tema ficou sem prioridade agora.

Para não ficar enchendo seu WhatsApp, vamos pausar as tentativas por aqui.

Se em algum momento vocês quiserem retomar o plano de vender mais no B2B sem depender tanto de pedido manual, chama o Breno no 34 98447-2414.

Um abraço!

### Exemplo Sarah, muito direto

Oi João, tudo bem?

Como não conseguimos seguir a conversa com a Sarah, vamos pausar as tentativas por aqui.

Se quiser retomar o projeto de vendas B2B mais pra frente, chama a Sarah no 34 98409-5632.

Abraço!

---

## 9. Registro obrigatório por envio

Para cada envio, salvar log com:
- `campaign`: `sumico_inicio_funil_2026_06_25`
- `deal_id`
- `contact_id`
- `lead_name`
- `company`
- `lead_phone`
- `owner_sdr`
- `owner_sdr_phone`
- `sender_name`
- `sender_port`
- `template_id`
- `message_text`
- `send_status`
- `message_id`
- `sent_at`
- `hubspot_moved_to_lost`: true/false
- `lost_reason`: `sumiço, início de funil`
- `error`, se houver

---

## 10. Execução recomendada agora

1. Conectar/validar João Pedro na porta `4609`.
2. Validar `/me` das portas `4600`, `4606`, `4607`, `4609`, `4610`.
3. Extrair os 103 negócios elegíveis do HubSpot.
4. Gerar CSV/JSON de prévia.
5. Mostrar amostra de 10 mensagens finais para aprovação rápida.
6. Fazer lote teste de 5 envios, um por chip.
7. Se tudo OK, disparar em lotes de 25/25/25/28.
8. Após cada envio `success:true`, criar nota/atividade no HubSpot e mover o negócio para perdido com motivo `sumiço, início de funil`.
9. Reportar total enviado, perdido, falhas e respostas.

---

## 11. Checklist antes de apertar o disparo

- [ ] João Pedro conectado na 4609.
- [ ] Gustavo conectado na 4610.
- [ ] Mariana, Lucas e Rafael validados.
- [ ] 103 negócios extraídos com critério correto.
- [ ] Telefones normalizados.
- [ ] SDR de retorno mapeado.
- [ ] Templates renderizados sem `[placeholder]` sobrando.
- [ ] ERPs citados somente quando confiáveis.
- [ ] Lote teste aprovado.
- [ ] Log preparado.
- [ ] Movimento para perdido condicionado a envio confirmado.
