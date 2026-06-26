Você é o motor de geração de PDFs e mensagem WhatsApp da Zydon para o lead abaixo. Trabalhe em /root/zydon-prospeccao.

## LEAD (dados do HubSpot)
- slug: plasthome
- empresa: Plasthome
- contato: Paulo Granussio
- email: comercial@plasthome.com.br
- telefone/JID: 5519997635591@c.us (DDD 19 = Piracicaba/SP)
- ERP: Outro (SOB PROJETO)
- faturamento: De R$1 milhão a R$5 milhões ao ano
- como vende: Venda direta
- loja virtual: Não
- pessoas: 1 a 10
- vendedores internos: 1
- lifecyclestage: marketingqualifiedlead

## DECISÃO MQL (JÁ TOMADA): SIM ✅
É MQL: indústria de plásticos (Piracicaba/SP, 29 anos, CNPJ ativo) + R$1-5M + atende revendas/comércio (atacado B2B). NÃO precisa redecidir.

## TAREFAS (faça TODAS, em ordem)

### 1. PESQUISA WEB (WebSearch/WebFetch obrigatório)
Pesquise "Plasthome" / "plasthome.com.br" / "Plasthome Piracicaba plásticos". Descubra:
- Que produtos de plástico fabrica (sacos, embalagens, filmes, tubos, utilidades?).
- Para quem vende B2B (indústrias, supermercados, distribuidores, revendas).
- Porte, localização (Piracicaba/SP), site/redes sociais.
- Cruze com os dados do formulário.

Salve em /root/zydon-prospeccao/pesquisas/plasthome.md.

### 2. GERAR PDF (motor oficial motor/gen.py + motor/render.py)
Crie /root/zydon-prospeccao/motor/_gen_plasthome.py que importe build_html, defina o dicionário lead, escreva HTML em motor/plasthome.html, use Playwright pra PDF em /root/zydon-prospeccao/pdfs/Potencial-Digitalizacao-plasthome.pdf. RODE.

### DICIONÁRIO LEAD:
```
l = {
  "slug": "plasthome",
  "theme": "dark",
  "empresa": "Plasthome",
  "contato": "Paulo Granussio",
  "cargo_area": "Indústria e comércio de plásticos",
  "local": "Piracicaba, SP",
  "telefone": "",
  "site": "",
  "sobre": "...",  # da pesquisa (29 anos, Piracicaba)
  "sobre_fonte": "...",
  "vende_para": "Indústrias, supermercados, revendas, distribuidores (atacado B2B)",
  "como_vende": "Venda direta",
  "loja_virtual": "Não",
  "vendedores": "1 interno",
  "time_total": "1 a 10 pessoas",
  "faturamento": "R$ 1 milhão a R$ 5 milhões por ano",
  "compra_sozinho": "A confirmar",
  "encontramos": [  # 3 itens específicos de indústria de plásticos
    "...", "...", "..."
  ],
  "conta": "...",  # específico: revendas recomprando sozinhas
  "pot_low": "R$ 80 mil", "pot_high": "R$ 400 mil",  # ousadia: R$1-5M
  "deixa_mes": "R$ 6 mil a R$ 33 mil",
  "pot_base": "...",
  "significa": "...",
  "erp": "Outro",
  "erp_integ": "Sob projeto",
  "erp_golive": "30 a 60 dias",
  "erp_dev": "Sim (projeto)",
  "erp_line": "A Zydon avalia a integração com 'Outro' sob projeto técnico. Prazo médio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling.",
  "pushpull": "...",
  "food": False,
}
```
⚠️ ERP "Outro" = SOB PROJETO. Rodapé: INTEGRAÇÃO "Sob projeto", GO-LIVE "30 a 60 dias", DESENVOLVIMENTO "Sim (projeto)". Sem "nativo".

### 3. MENSAGEM WHATSAPP
Escreva em /root/zydon-prospeccao/pesquisas/plasthome_msg.txt:

```
Boa noite, Paulo, tudo bem? Aqui é a Mariana, da Zydon.
A partir do que você respondeu no nosso diagnóstico, preparei um material sobre o potencial de digitalização B2B da Plasthome. Te mando em PDF aqui.
Em resumo, dá pra [INSIGHT ESPECÍFICO da pesquisa]. Um consultor nosso jaja entra em contato com você para fazer um diagnóstico mais completo da Plasthome e te mostrar isso na prática. Pode ser?
```
⚠️ Saudação = "Boa noite". CONSULTOR_TIMING = "jaja" (segunda-feira). PROIBIDO: ERP, go-live, jargão, travessão, emojis. Assinatura "Aqui é a Mariana, da Zydon". Com ACENTOS.

### 4. CONFIRMAÇÃO
Ao final imprima: caminho do PDF, texto da mensagem, confirme 3 páginas fundo escuro. NÃO faça envio WhatsApp.
