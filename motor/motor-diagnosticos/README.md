# README — Base de criação dos PDFs "Potencial de Digitalização B2B"

Pacote para o time técnico **reproduzir e automatizar** a geração dos materiais. Leia o **`PLAYBOOK.md`** para as regras de negócio; este README é o quickstart técnico.

## Requisitos
- Python 3.10+
- Dependências: `pip install pandas openpyxl playwright`
- Chromium do Playwright: `python -m playwright install chromium`
  - (Em servidor Linux pode faltar libs do sistema: `python -m playwright install-deps chromium`.)

## Estrutura
```
motor/        # gerador
  gen.py            -> TEMPLATE (HTML/CSS) + build_html(): todas as regras de layout/marca/ERP/potencial
  render.py         -> percorre os leads e converte HTML -> PDF (Chromium headless, 210x297mm)
  leads.py          -> 4 leads do piloto (estrutura de referência de um lead)
  gen_batch*.py     -> dados + copy personalizada de cada lote de empresas
assets/
  logo/             -> logo oficial Zydon (branca p/ tema escuro, preta p/ tema claro)
  fonts/            -> fonte de apoio
dados/
  fila_junho.csv             -> 1 linha por lead (tema A/B, status do PDF, campos do formulário)
  wpp_envios.json            -> lista de envios de WhatsApp (texto + link wa.me)
  _Índice MQLs Junho (98).xlsx
exemplos/           -> 3 PDFs prontos (referência do resultado)
PLAYBOOK.md         -> REGRAS DE NEGÓCIO (ler primeiro)
```

## Como gerar (exemplo)
Cada `gen_batch*.py` é autocontido: define a lista `LEADS` (dicts) e renderiza via `gen.build_html` + Playwright.
```bash
cd motor
python gen_batch.py        # gera os PDFs daquele lote na pasta de saída
```
Para um lote novo: copie um `gen_batch*.py`, troque a lista `LEADS` (um dict por empresa, ver chaves em `leads.py`) e rode.

## Estrutura de um lead (dict)
Campos esperados por `build_html` (ver `leads.py`/`gen_batch*.py`):
`slug, theme ("dark"/"light"), food (bool), empresa, contato, cargo_area, local, sobre, sobre_fonte,
vende_para, como_vende, loja_virtual, erp, vendedores, time_total, faturamento, compra_sozinho,
encontramos[3], pushpull, conta, significa, pot_low, pot_high, deixa_mes, pot_base,
erp_integ, erp_golive, erp_dev, erp_line`

## Regras que NÃO podem quebrar (resumo — detalhes no PLAYBOOK)
- **TOTVS = "sob consulta"** (nunca nativo). Nativos: Bling, Olist/Tiny, Omie, Sankhya.
- **Empurra × puxa** é o eixo do diagnóstico.
- **"Deixa na mesa" = 14%** do faturamento (ano e mês), sempre como estimativa.
- Falar por **"você"** (vai pro cliente), sem "uso interno" no rodapé.
- **Tema A/B** preto/branco alternado.
- Pesquisar a empresa de verdade; **não inventar** CNPJ/datas.

## Observação sobre o disparo no WhatsApp
O texto pode ser pré-preenchido por link `wa.me`. **O anexo de PDF NÃO se automatiza pelo WhatsApp Web** (a plataforma bloqueia envio de mídia por automação). Para envio automático ponta-a-ponta use a **WhatsApp Business Cloud API** (template + documento). Ver PLAYBOOK seção 7 e 10.
