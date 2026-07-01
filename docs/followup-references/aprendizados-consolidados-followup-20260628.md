# Aprendizados consolidados de follow-up SDR — Rafael — 2026-06-28

Escopo deste aprendizado: régua de follow-up / primeiro contato SDR da Zydon. Não misturar com gate de diagnóstico/MQL manual em outro cron.

## Escopo operacional

- Trabalhar apenas nas etapas HubSpot:
  - `984052829` — Lead Sem Contato
  - `1214320997` — Primeiro Contato
- Lead Sem Contato recebe Follow 1 pelo SDR dono e depois move para Primeiro Contato.
- Primeiro Contato segue Follow 2, Follow 3 e Follow 4 conforme histórico.
- Exatamente 1 follow por dia útil por lead.
- Não pular etapas.
- Não repetir texto.
- Antes de enviar, ler ledger e histórico WhatsApp/Channel.
- Se respondeu, parar automação e mover para Retorno Contato.
- Se volume passar limite seguro, avisar Rafael antes de forçar.

## Ordem correta do texto

Regra final aprovada por Rafael:

1. Saudação e identificação do remetente.
2. Se for comunicador, informar o SDR responsável.
3. Primeiro mandar o link/URL da loja exemplo, no formato validado.
4. Explicar a experiência em uma frase curta.
5. Só depois enriquecer com campos HubSpot, principalmente ERP e se vende em loja online.
6. Fechar com pergunta simples.

Formato validado do link:

```text
Separei um portal real para visualizar a experiência:

https://stoky.com.br/
```

O link deve ficar limpo e em linha própria para gerar preview no WhatsApp.

## Link/portal real

- Se o lead nunca recebeu nenhum link/portal real, o próximo follow deve mandar link o quanto antes.
- Isso vale mesmo se o lead estiver indo para Follow 2, Follow 3 ou Follow 4.
- Se o segmento for claro, escolher portal por segmento.
- Se o segmento for incerto, usar fallback:
  1. https://voolt3datacado.com.br/
  2. https://stoky.com.br/
  3. https://portal.ceasamais.com.br/

## Campos HubSpot que devem enriquecer os follows

Usar campos confiáveis do HubSpot, principalmente a partir do Follow 2:

- ERP
- Se vende em loja online
- Canal atual de pedido
- Dor declarada
- Segmento
- Número de vendedores, quando confiável
- Faturamento/faixa, quando confiável

Regra de segurança:

- Se o campo estiver claro, pode usar.
- Se o campo estiver incerto, perguntar em vez de afirmar.
- Não inventar informação.
- Não dizer que o lead tem Olist, loja virtual ou ERP específico se isso não veio claramente do HubSpot/histórico.

## Vocabulário aprovado

Usar:

- login e senha
- cadastro aprovado
- liberação de acesso
- tabela comercial
- tabela de preço, quando fizer sentido
- condição comercial
- carteira do vendedor
- ERP
- cliente ou revenda, conforme contexto

Evitar:

- falar só “tabela”
- emoji
- travessão
- reticências
- frases formais com cara de IA: portanto, dessa forma, nesse sentido, ademais
- textão
- afirmação sem fonte

## Comunicadores

- Comunicadores ficam principalmente para o grosso de Primeiro Contato.
- Lead Sem Contato, como regra, é SDR dono.
- No máximo 1 comunicador por lead, além do SDR dono.
- Não misturar dois comunicadores diferentes no mesmo lead.
- Quando comunicador enviar, colocar o SDR responsável assim:

```text
O Lucas Batista está como responsável pelo seu atendimento. WhatsApp: +55 34 8429-5409.
```

Variações:

```text
A Sarah está como responsável pelo seu atendimento. WhatsApp: +55 34 8429-1640.
O Breno está como responsável pelo seu atendimento. WhatsApp: +55 34 8432-5076.
```

## Exemplos aprovados

### ERP claro no HubSpot

```text
William, aqui é o Lucas da Zydon.

Separei um portal real para visualizar a experiência:

https://stoky.com.br/

O cliente entra com login, vê catálogo, tabela comercial e condição dele, e faz o pedido direto.

Vi que vocês usam Omie e queria entender se hoje o pedido B2B já cai integrado por algum canal online ou se ainda depende do vendedor/WhatsApp.

Isso conversa com o que vocês estão buscando para a Integramix?
```

### Já vende em loja online

```text
William, aqui é o Lucas da Zydon.

Separei um portal real para visualizar a experiência:

https://stoky.com.br/

O cliente entra com login, vê catálogo, tabela comercial e condição dele, e faz o pedido direto.

Vi que vocês já têm loja online. A dúvida é se ela resolve o B2B de verdade: login por cliente, cadastro aprovado, tabela comercial por CNPJ e carteira do vendedor.

É essa parte que vocês querem estruturar melhor?
```

### Ainda não vende em loja online

```text
William, aqui é o Lucas da Zydon.

Separei um portal real para visualizar a experiência:

https://stoky.com.br/

Como vocês ainda não vendem por loja online, a ideia seria começar pelo B2B certo: cliente com login, catálogo, tabela comercial e condição própria.

Isso ainda faz sentido para a Integramix?
```

## Criativo Papel Rasgar / Comparativo

Quando a origem indicar Papel Rasgar ou Comparativo, o lead já vem comparando plataforma. Ele não precisa ser educado sobre o problema; precisa entender por que Zydon é diferente de e-commerce B2C adaptado.

Linha aprovada:

```text
Quando a empresa compara Zydon com Tray, Shopify ou Nuvemshop, normalmente a dúvida não é o site em si. É cadastro aprovado, login por cliente, tabela comercial e carteira do vendedor.

Essa é a dor que vocês estão tentando resolver?
```

Ainda assim, se houver portal exemplo, o link vem primeiro.

## Regra final resumida

Link exemplo primeiro. Contexto HubSpot depois. Texto curto, humano, sem inventar. Ler histórico antes. Não repetir. Se tiver risco, dúvida operacional ou capacidade insuficiente, marcar Rafael: <@551035817129148419>.
