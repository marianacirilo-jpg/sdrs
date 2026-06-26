# TAREFA: Lead Airtudo (airtudo) — REPROCESSAR como MQL (confiar no form)

Voce esta no projeto /root/zydon-prospeccao. Use o motor oficial em motor/. Helper: motor/render_one.py.

## CONTEXTO IMPORTANTE — CONFIAR NO FORM
O lead preencheu no formulario: "Vendemos para outras empresas" (B2B), tem loja virtual (Sim), e o cliente compraria sozinho. **Isso SIGNIFICA que e B2B** — confie na declaracao do lead. A pesquisa web (que achou varejo de armas) e COMPLEMENTO, nao sobrescreve a declaracao B2B do lead. Gere o PDF como MQL B2B.

## PASSO 1 — Ler dados HubSpot
Leia /root/zydon-prospeccao/pesquisas/airtudo_hubspot.json.

## PASSO 2 — Pesquisar (WEB SEARCH) — complementar
Pesquise "Airtudo" (airtudo.com.br, Salvador/BA). Descubra o que vendem e o modelo B2B (vendem insumos/equipamentos p/ outras empresas). Salve em pesquisas/airtudo.md. Use o B2B como verdade.

## PASSO 3 — Montar dict
slug="airtudo", theme="dark", empresa="Airtudo", contato="Vagner", cargo_area="Insumos e equipamentos B2B / Impressao 3D", local="Salvador, BA", telefone="", site="airtudo.com.br", sobre=(B2B da pesquisa), sobre_fonte=(fonte), vende_para="Empresas (B2B)", como_vende="Representante externo + WhatsApp", loja_virtual="Sim", vendedores="2 a 5", time_total="1 a 10 pessoas", faturamento="Ate R$250 mil por ano", compra_sozinho="Sim se site intuitivo", encontramos=[3 itens ESPECIFICOS B2B da pesquisa], conta=(frase especifica), pot_low="R$50 mil"/pot_high="R$200 mil"/deixa_mes="R$4 mil a R$16 mil"/pot_base="14% sobre R$250k", significa=(frase), pushpull="puxa (tem e-commerce)", food=false.

### REGRA ERP (Outro -> sob projeto)
erp="Outro", erp_integ="Integracao sob projeto", erp_golive="30 a 60 dias", erp_dev="Sim (projeto)", erp_line="A Zydon avalia a integracao com Outro sob projeto tecnico. Prazo medio: 30 a 60 dias para go-live. ERPs nativos Zydon: Sankhya, Omie, Olist e Bling."

## PASSO 4 — Gerar PDF
Salve dict em motor/airtudo_lead.json. Rode: python3 motor/render_one.py airtudo motor/airtudo_lead.json. Confirme pdfs/Potencial-Digitalizacao-airtudo.pdf.

## PASSO 5 — Mensagem WhatsApp (HOJE E SEGUNDA-FEIRA DE MANHA -> "jaja")
Oi, Vagner, tudo bem? Aqui e a Mariana, da Zydon.

A partir do que voce respondeu no nosso diagnostico, preparei um material sobre o potencial de digitalizacao B2B da Airtudo. Te mando em PDF aqui.

Em resumo, da pra [INSIGHT ESPECIFICO B2B da pesquisa]. Um consultor nosso JAJA entra em contato com voce para fazer um diagnostico mais completo da Airtudo e te mostrar isso na pratica. Pode ser?

Salve em pesquisas/airtudo_msg.txt

## REGRAS INVIOLAVEIS
1. Insight ESPECIFICO da empresa, nunca generico.
2. Sem ERP/go-live/jargao na mensagem.
3. Rodape PDF: 30 a 60 dias (sob projeto).
4. "jaja entra em contato" (hoje e dia util, manha).
5. Sem travessao/emoji/icone.

## SAIDA: MQL SIM, resumo pesquisa, dict, texto msg, confirmacao PDF.