Você é o motor de geração de PDFs e mensagem WhatsApp da Zydon para o lead abaixo. Trabalhe em /root/zydon-prospeccao.

## LEAD (dados do HubSpot via gate)
- slug: dl-distribuidora
- empresa: DL Distribuidora
- contato: Daniel Pessoa
- email: dldistripecas@dl.com.br
- telefone/JID: 5581984619957@c.us (DDD 81 = Pernambuco/Recife)
- ERP: Bling (NATIVO Zydon — go-live rápido 7 a 14 dias)
- faturamento: De R$250 mil a R$500 mil ao ano
- como vende: Representante externo
- loja virtual: Não
- pessoas: 1 a 10
- lifecyclestage: lead (será promovido a mql)

## DECISÃO MQL (JÁ TOMADA PELO ORQUESTRADOR): SIM ✅
É MQL: distribuidora B2B (o nome e o email "dldistripecas" indicam distribuição de peças) + ERP Bling nativo + porte compatível. NÃO precisa redecidir.

## TAREFAS (faça TODAS, em ordem)

### 1. PESQUISA WEB (WebSearch/WebFetch obrigatório)
Pesquise publicamente sobre "DL Distribuidora" / "dl.com.br" / "DL Distribuidora peças Pernambuco" / "DL distribuidoraRecife". Descubra:
- Qual o segmento real (peças de quê? autopeças? peças industriais? peças de informática?).
- É distribuidora/atacado B2B? (confirme operação para revendas/lojistas/instaladores).
- Porte real, localização, se tem site/redes sociais.
- Cruze com os dados do formulário HubSpot.

Salve a pesquisa em /root/zydon-prospeccao/pesquisas/dl-distribuidora.md (formato igual aos outros pesquisas/*.md — seção de dados do form, pesquisa web, veredito MQL, insight, fontes).

### 2. GERAR PDF (use o motor oficial motor/gen.py + motor/render.py)
O arquivo motor/leads.py contém a lista LEADS com dicionários. O motor/gen.py tem build_html(l) e o motor/render.py renderiza cada lead de LEADS em PDF.

Crie um script Python TEMPORÁRIO em /root/zydon-prospeccao/motor/_gen_dl.py que:
- importe build_html de gen (from gen import build_html, OUT)
- defina o dicionário lead abaixo (PREENCHA os campos com base na pesquisa web — insight específico, nunca genérico)
- escreva o HTML em motor/dl-distribuidora.html
- use Playwright para renderizar o PDF em /root/zydon-prospeccao/pdfs/Potencial-Digitalizacao-dl-distribuidora.pdf
  (pg.pdf(path=..., width="210mm", height="297mm", print_background=True, margin tudo zero))
- RODE o script e confirme que o PDF foi gerado.

### DICIONÁRIO LEAD (formato EXATO — siga os campos de motor/leads.py):
```
l = {
  "slug": "dl-distribuidora",
  "theme": "dark",
  "empresa": "DL Distribuidora",
  "contato": "Daniel Pessoa",
  "cargo_area": "Distribuição de peças",  # ajuste conforme a pesquisa (autopeças/peças industriais/etc)
  "local": "Pernambuco",  # ajuste se descobrir cidade
  "telefone": "",
  "site": "",  # se descobrir
  "sobre": "...",  # 2-3 frases sobre a empresa, da pesquisa web
  "sobre_fonte": "...",  # fontes
  "vende_para": "...",  # B2B — para quem (revendas, oficinas, lojistas, instaladores)
  "como_vende": "Representante externo + pedidos por telefone/WhatsApp",
  "loja_virtual": "Não",
  "vendedores": "1 a 3 internos",  # inferir do porte 1-10 pessoas
  "time_total": "1 a 10 pessoas",
  "faturamento": "R$ 250 mil a R$ 500 mil por ano",
  "compra_sozinho": "A confirmar",
  "self_serve_resp": "",
  "dor": "",
  "encontramos": [  # 3 itens específicos do segmento de peças/distribuição
    "...",
    "...",
    "..."
  ],
  "detalhe": "",
  "conta": "...",  # a conta que quase ninguém faz — específica de distribuidora de peças
  "pot_low": "R$ 50 mil", "pot_high": "R$ 250 mil",  # ousadia: faixa R$250-500k faturamento
  "deixa_mes": "R$ 4 mil a R$ 21 mil",
  "pot_base": "...",  # base da estimativa
  "significa": "...",
  # ERP Bling = NATIVO:
  "erp": "Bling",
  "erp_integ": "Bling - nativa",
  "erp_golive": "7 a 14 dias",
  "erp_dev": "Não (nativo)",
  "erp_line": "A Zydon tem integração nativa com Sankhya, Omie, Olist e Bling — go-live mais rápido, sem projeto customizado. ERPs diferentes são suportados sob avaliação.",
  "pushpull": "...",  # distribuidora de peças: recompra recorrente = puxada
  "food": False,
}
```
⚠️ ERP Bling é NATIVO. O rodapé do PDF deve ter: INTEGRAÇÃO "Bling - nativa", GO-LIVE "7 a 14 dias", DESENVOLVIMENTO "Não (nativo)".
⚠️ NÃO mencionar "go-live em 48h" em lugar nenhum.

### 3. MENSAGEM WHATSAPP
Escreva em /root/zydon-prospeccao/pesquisas/dl-distribuidora_msg.txt a mensagem seguindo EXATAMENTE este template (preencha [INSIGHT] com 1 frase específica da pesquisa, sem ERP/go-live/jargão):

```
Boa tarde, Daniel, tudo bem? Aqui é a Mariana, da Zydon.
A partir do que você respondeu no nosso diagnóstico, preparei um material sobre o potencial de digitalização B2B da DL Distribuidora. Te mando em PDF aqui.
Em resumo, dá pra [INSIGHT ESPECÍFICO]. Um consultor nosso **jaja** entra em contato com você para fazer um diagnóstico mais completo da DL Distribuidora e te mostrar isso na prática. Pode ser?
```

⚠️ Saudação = "Boa tarde" (horário BR 13h). CONSULTOR_TIMING = "jaja" (segunda-feira, horário comercial).
⚠️ PROIBIDO na mensagem: ERP, sistema de gestão, integração, go-live, prazos, jargão técnico, travessão (—), emojis. Assinatura = "Aqui é a Mariana, da Zydon".
⚠️ Escreva a mensagem COM ACENTOS corretos (dá, prática, diagnóstico, digitalização, etc).

### 4. CONFIRMAÇÃO
Ao final, imprima:
- Caminho do PDF gerado
- Texto completo da mensagem
- Confirme que o PDF tem 3 páginas e fundo escuro.
NÃO faça envio WhatsApp (isso é com o orquestrador).
