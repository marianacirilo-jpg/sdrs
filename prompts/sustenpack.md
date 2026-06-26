Você é o motor de geração de PDFs e mensagem WhatsApp da Zydon para o lead abaixo. Trabalhe em /root/zydon-prospeccao.

## LEAD (dados do HubSpot)
- slug: sustenpack
- empresa: Sustenpack
- contato: Moises Gil
- email: moises.gil@sustenpack.com.br
- telefone/JID: 5511994045828@c.us (DDD 11 = São Paulo)
- ERP: Outro (SOB PROJETO — TOTVS/outros)
- faturamento: De R$10 milhões a R$50 milhões ao ano
- como vende: representantes e vendedores internos
- loja virtual: Sim
- pessoas: 51 a 150
- vendedores internos: 6 a 20
- lifecyclestage: marketingqualifiedlead

## DECISÃO MQL (JÁ TOMADA): SIM ✅
É MQL: indústria de embalagens sustentáveis para food service (atacado B2B) + R$10-50M + 51-150 pessoas + já vende em loja virtual + representantes. NÃO precisa redecidir.

## TAREFAS (faça TODAS, em ordem)

### 1. PESQUISA WEB (WebSearch/WebFetch obrigatório)
Pesquise "Sustenpack" / "sustenpack.com.br" / "Sustenpack embalagens sustentáveis food service". Descubra:
- Catálogo real (que tipos de embalagem: marmitas, copos, sacolas, etc).
- Para quem vende B2B (restaurantes, delivery, supermercados, distribuidores).
- Porte real, localização (SP), site e Instagram ativos.
- Cruze com os dados do formulário.

Salve em /root/zydon-prospeccao/pesquisas/sustenpack.md.

### 2. GERAR PDF (use motor oficial motor/gen.py + motor/render.py)
Crie /root/zydon-prospeccao/motor/_gen_sustenpack.py que importe build_html de gen, defina o dicionário lead, escreva HTML em motor/sustenpack.html, use Playwright para renderizar PDF em /root/zydon-prospeccao/pdfs/Potencial-Digitalizacao-sustenpack.pdf (210mm x 297mm, print_background=True, margin zero). RODE o script.

### DICIONÁRIO LEAD (formato EXATO):
```
l = {
  "slug": "sustenpack",
  "theme": "dark",
  "empresa": "Sustenpack",
  "contato": "Moises Gil",
  "cargo_area": "Fabricação de embalagens sustentáveis para food service",
  "local": "São Paulo, SP",
  "telefone": "",
  "site": "sustenpack.com.br",
  "sobre": "...",  # 2-3 frases da pesquisa
  "sobre_fonte": "...",
  "vende_para": "Restaurantes, delivery, supermercados, distribuidores (atacado B2B)",
  "como_vende": "Representantes externos + vendedores internos (6 a 20)",
  "loja_virtual": "Sim",
  "vendedores": "6 a 20 internos",
  "time_total": "51 a 150 pessoas",
  "faturamento": "R$ 10 milhões a R$ 50 milhões por ano",
  "compra_sozinho": "A confirmar",
  "encontramos": [  # 3 itens específicos de embalagens sustentáveis food service
    "...", "...", "..."
  ],
  "conta": "...",  # específico: recompra de marmitas/copos pelos restaurantes
  "pot_low": "R$ 300 mil", "pot_high": "R$ 1,2 milhão",  # ousadia: R$10-50M
  "deixa_mes": "R$ 25 mil a R$ 100 mil",
  "pot_base": "...",
  "significa": "...",
  # ERP "Outro" = SOB PROJETO:
  "erp": "Outro",
  "erp_integ": "Sob projeto",
  "erp_golive": "30 a 60 dias",
  "erp_dev": "Sim (projeto)",
  "erp_line": "A Zydon avalia a integração com 'Outro' sob projeto técnico. Prazo médio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling.",
  "pushpull": "...",  # embalagens: recompra recorrente de restaurantes = puxada
  "food": True,
}
```
⚠️ ERP "Outro" = SOB PROJETO. Rodapé: INTEGRAÇÃO "Sob projeto", GO-LIVE "30 a 60 dias", DESENVOLVIMENTO "Sim (projeto)".
⚠️ NÃO mencionar "go-live em 48h" nem "nativo".

### 3. MENSAGEM WHATSAPP
Escreva em /root/zydon-prospeccao/pesquisas/sustenpack_msg.txt seguindo EXATAMENTE este template:

```
Boa noite, Moises, tudo bem? Aqui é a Mariana, da Zydon.
A partir do que você respondeu no nosso diagnóstico, preparei um material sobre o potencial de digitalização B2B da Sustenpack. Te mando em PDF aqui.
Em resumo, dá pra [INSIGHT ESPECÍFICO da pesquisa — restaurantes/distribuidores recomprando embalagens sozinhos]. Um consultor nosso jaja entra em contato com você para fazer um diagnóstico mais completo da Sustenpack e te mostrar isso na prática. Pode ser?
```
⚠️ Saudação = "Boa noite" (horário BR noite). CONSULTOR_TIMING = "jaja" (segunda-feira, dia útil).
⚠️ PROIBIDO: ERP, go-live, integração, prazos, jargão, travessão (—), emojis. Assinatura "Aqui é a Mariana, da Zydon". Com ACENTOS corretos.

### 4. CONFIRMAÇÃO
Ao final imprima: caminho do PDF, texto da mensagem, confirme 3 páginas e fundo escuro. NÃO faça envio WhatsApp.
