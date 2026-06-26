Você é o motor de geração de PDFs e mensagem WhatsApp da Zydon para o lead abaixo. Trabalhe em /root/zydon-prospeccao.

## LEAD (dados do HubSpot)
- slug: coop-caixas-sul
- empresa: Cooperativa de Agricultores e Agroindústrias Familiares de Caixas do Sul
- contato: Edson
- email: edson@caaf.coop.br
- telefone/JID: 44999443183@c.us
- ERP: Outro (SOB PROJETO — TOTVS/outros)
- SDR responsável: Mariana (assinatura abaixo)

## DECISÃO MQL (JÁ TOMADA): SIM ✅
É MQL. NÃO precisa redecidir.

## TAREFAS (faça TODAS, em ordem)

### 1. PESQUISA WEB (WebSearch/WebFetch obrigatório)
Pesquise "Cooperativa de Agricultores e Agroindústrias Familiares de Caixas do Sul" / site / segmento. Descubra:
- Catálogo/produtos reais.
- Para quem vende B2B (atacado/distribuidores/indústria).
- Porte, localização, site e Instagram ativos.
Salve em /root/zydon-prospeccao/pesquisas/coop-caixas-sul.md

### 2. GERAR PDF (use motor oficial motor/gen.py + motor/render.py)
Crie /root/zydon-prospeccao/motor/_gen_coop-caixas-sul.py que importe build_html de gen, defina o dicionário lead, escreva HTML em motor/coop-caixas-sul.html, use Playwright para renderizar PDF em /root/zydon-prospeccao/pdfs/Potencial-Digitalizacao-coop-caixas-sul.pdf (210mm x 297mm, print_background=True, margin zero, tema dark).
Use o dicionário lead no formato EXATO de motor/_gen_sustenpack.py (leia ele como referência). Preencha os campos "sobre", "vende_para", "encontramos", "conta", "pot_low", "pot_high" com base na pesquisa — insight ESPECÍFICO de domínio.

ERP "Outro" = SOB PROJETO:
- erp="Outro", erp_integ="Sob projeto", erp_golive="30 a 60 dias", erp_dev="Sim (projeto)"
- erp_line="A Zydon avalia a integração com 'Outro' sob projeto técnico. Prazo médio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."
- NÃO mencionar "go-live em 48h" nem "nativo".

### 3. MENSAGEM WHATSAPP
Escreva em /root/zydon-prospeccao/pesquisas/coop-caixas-sul_msg.txt seguindo EXATAMENTE:
```
Boa tarde, Edson, tudo bem? Aqui é a Mariana, da Zydon.
A partir do que você respondeu no nosso diagnóstico, preparei um material sobre o potencial de digitalização B2B da Cooperativa de Agricultores e Agroindústrias Familiares de Caixas do Sul. Te mando em PDF aqui.
Em resumo, dá pra [INSIGHT ESPECÍFICO da pesquisa — concreto, 1 frase]. Um consultor nosso jaja entra em contato com você para fazer um diagnóstico mais completo da Cooperativa de Agricultores e Agroindústrias Familiares de Caixas do Sul e te mostrar isso na prática. Pode ser?
```
- Assinatura OBRIGATÓRIA: "Aqui é a Mariana, da Zydon"
- PROIBIDO: ERP, go-live, integração, prazos, jargão, travessão (—), emojis.
- COM ACENTOS CORRETOS (é, ã, ç).

### 4. CONFIRMAÇÃO
Ao final imprima: caminho do PDF, texto da mensagem, confirme 3 páginas e fundo escuro. NÃO faça envio WhatsApp.
