# REGERAR PDF Reptec — sem cortar NENHUMA informação

## Contexto
O PDF atual da Reptec (`/root/.hermes/zydon-prospeccao/motor/reptec.html` e `pdfs/Reptec - Potencial de Digitalizacao B2B.pdf`) está com **informação cortada**. Vários campos aparecem como "A confirmar" quando o HubSpot TEM o dado real. Isso é inaceitável — NUNCA cortar informação que existe.

## Os dados reais do lead (do HubSpot, verificado agora)
- **Contato:** Tiago Miranda — tiago.miranda@reptec.com.br
- **Empresa:** Reptec
- **Telefone:** 34991068253 (WhatsApp)
- **Cidade:** Uberlândia, MG (do site — HubSpot veio vazio)
- **Owner:** Lucas (hubspot_owner_id 85778446) → assinatura "Aqui é o Lucas, da Zydon"
- **Lifecycle:** marketingqualifiedlead
- **criado:** 2026-06-22T23:07:22Z

### Propriedades do diagnóstico (RESPOSTAS REAIS DO LEAD no form):
- **ERP utilizado:** `Outro` (campo `qual_erp_utiliza_`)
- **Faturamento anual:** `De R$5 a R$10 milhões ao ano` (campo `qual_o_faturamento_anual_da_sua_empresa_`)
- **Pessoas na empresa:** `+151`
- **Vende em loja virtual:** `sim` (campo `vende_em_loja_virtual_`)
- **Faixa de faturamento:** vazio (usar o outro campo)
- **ERP (outros campos):** vazio → usar `qual_erp_utiliza_` = Outro

## O que está ERRADO no PDF atual (cortado)
| Campo no PDF | Valor atual (errado) | Valor CORRETO |
|--------------|---------------------|---------------|
| Loja virtual | "A confirmar" | **sim** |
| Faturamento anual | "A confirmar" | **De R$5 a R$10 milhões ao ano** |
| Vendedores internos | "A confirmar" | (vazio no form — pesquisquisar no site) |
| ERP utilizado | "Outro" | **Outro** (manter, = sob projeto Zydon) |

## Pesquisa web da Reptec (JÁ FEITA — está em `pesquisas/reptec.md`)
Ler o arquivo `pesquisas/reptec.md` que tem o insight completo: Reptec é fabricante e distribuidora de EPIs e uniformes profissionais desde 2002, sede Uberlândia MG, ~10.000 m² de galpão, +900 colaboradores, 10.000+ clientes ativos, atuação nacional (forte MG/SP/MT), exporta para África e América Latina, programa de revendedores, catálogo amplo (cabeça/olhos/ouvidos/mãos/pés/corpo/respiratório), atende construção/agro/energia.

## A REGRAS ABSOLUTAS desta regeração
1. **NUNCA deixar campo como "A confirmar" se o dado existe** — seja no HubSpot, seja na pesquisa web, seja no site da empresa. Se o form não tem, pesquisar no site e preencher.
2. **NUNCA escrever "Outro" sem contexto** — se o ERP é "Outro", no rodapé deve aparecer a regra Zydon: "Outros ERPs = integração sob projeto".
3. **Preencher TODOS os campos do "Perfil da Operação"** com dados reais:
   - QUEM ATENDE: indústria, agronegócio, construção, energia + rede de revenda (distribuidores B2B)
   - COMO VENDE HOJE: vendedores + rede de revenda (atacado B2B) + **loja virtual (sim)**
   - LOJA VIRTUAL: **sim**
   - ERP UTILIZADO: **Outro** (rodapé: sob projeto)
   - VENDEDORES INTERNOS: pesquisar no site/LinkedIn (estimativa razoável pra +900 colaboradores); se realmente não achar, colocar valor plausível baseado no porte (ex: "50+ vendedores") e marcar como estimativa, NUNCA "A confirmar"
   - TIME TOTAL: **+900 colaboradores** (pesquisa) / +151 (form) — usar o MAIOR/relevante com nota
   - FATURAMENTO ANUAL: **De R$5 a R$10 milhões ao ano**
   - COMPRA AUTÔNOMA: resposta do diagnóstico (preservar)
4. **Preservar o insight de domínio** — a análise "O Que Encontramos" deve continuar específica (catálogo EPI amplo, portal B2B pra reposição por ciclos NR, programa de revendedores).
5. **Manter o design** — usar o mesmo HTML/template existente, só corrigir o conteúdo dos cards.
6. **Assinatura dinâmica:** o HTML é neutro, mas a MENSAGEM (txt) deve assinar "Aqui é o Lucas, da Zydon" (Tiago é do Lucas).

## Arquivos a editar/criar
1. **`motor/reptec.html`** — corrigir TODOS os campos do "Perfil da Operação" + garantir rodapé ERP.
2. **Re-renderizar o PDF** em `pdfs/Reptec - Potencial de Digitalizacao B2B.pdf` (usar o mesmo método de render: chromium headless, A4, com `--print-to-pdf`). Manter o nome do arquivo.
3. **Regenerar thumbnail** `pdfs/reptec_thumb.jpg` (320px, ~12KB, qualidade 70).
4. **`pesquisas/reptec_msg.txt`** — garantir que assina "Aqui é o Lucas, da Zydon" e está em 1ª pessoa ("vou te chamar amanhã/segunda" conforme horário, nunca "consultor").

## Método de render (usar o que já existe no projeto)
- Verificar `motor/gen.py` e `motor/render.py` (ou `.venv` com playwright) pra ver como renderizam HTML→PDF. Usar o MESMO método.
- Se chromium headless: `chromium --headless --disable-gpu --print-to-pdf="pdfs/Reptec - Potencial de Digitalizacao B2B.pdf" --no-pdf-header-footer "file:///root/.hermes/zydon-prospeccao/motor/reptec.html"`
- Thumbnail: `motor/gerar_thumb.sh` ou equivalente (320px).

## Verificação final (imprimir)
1. Rodar `grep -c "A confirmar" motor/reptec.html` → deve retornar **0**.
2. Confirmar que "De R$5 a R$10 milhões" aparece no HTML.
3. Confirmar que "sim" aparece no card de loja virtual.
4. Confirmar que o PDF foi regenerado (tamanho/mtime novo).
5. Confirmar que o thumbnail foi regenerado.
6. Mostrar o `pesquisas/reptec_msg.txt` final.

## Restrições
- NÃO mexer em gate.py, ciclo.py, disparo_dinamico.py, processed_emails, wpp_envios — esses estão OK.
- NÃO reenviar WhatsApp (o Tiago já recebeu — só corrigir os artefatos pra futura reenvio se necessário).
- Usar WebSearch/WebFetch pra confirmar dados da Reptec se precisar (vendedores, faturamento público).
