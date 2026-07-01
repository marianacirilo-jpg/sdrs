# Cadência de follow-up — régua FIXA (Rafael 30/06/2026)

Processo rígido e conhecido. Não improvisar, não criar variação, não reativar
nada sem ordem explícita.

## Fonte de verdade

Os 4 textos vivem **somente** em:

```
controle/followup_textos_aprovados_rafael_20260630.json
```

O arquivo tem `texts` (follow1..follow4) e `sha256` por texto. O script verifica
o hash antes de usar; se o texto não bater com o hash declarado, o envio é
bloqueado (manifesto adulterado/quebrado).

## Variáveis permitidas (as ÚNICAS)

O código substitui apenas:

- `nome`
- `empresa`
- `portal_segmento`
- `portal_url`
- `portal_buyer_context`

`portal_*` só são usadas no Follow 1 (portal real estudado da carteira).
Qualquer outro placeholder no manifesto é tratado como adulteração e bloqueia.

## Geração de texto: caminho único

- `scripts/cadencia_primeiro_contato.py`
- Único gerador: `extract_message_variation` → `_render_approved_template`.
- `_render_approved_template` lê o manifesto, valida integridade e substitui só as
  variáveis permitidas. Não anexa parágrafo, não muda ordem, não injeta CTA, não
  muda o texto conforme o remetente.

Caminhos antigos que podiam gerar texto alternativo/ponte foram **removidos**
(`consultant_addendum`, `remove_sdr_bridge_mentions`,
`apply_diagnostic_sdr_context_bridge`, `prior_diagnostic_sent_by_owner_sdr` e as
listas `APPROVED_FOLLOWUP_REQUIRED` / `APPROVED_FOLLOWUP_BANNED`).

## Gate fail-closed antes de enviar

`approved_followup_template_gate(text, attempt, lead)` roda imediatamente antes de
cada envio e BLOQUEIA quando:

1. tentativa fora de 1–4;
2. manifesto ausente / JSON quebrado / sha256 divergente;
3. texto renderizado vazio;
4. Follow 3 com estrofe duplicada;
5. texto difere, em qualquer caractere, do manifesto após substituir as variáveis.

Só passa o texto que é exatamente o render do manifesto.

## Estado operacional

- Envio automático está **pausado** (`zydon-sdr-followup-unificado-5min`). Não reativar sem ordem explícita do Rafael.
- Envio real (`--send`) agora exige `--require-research`; sem pesquisa/estudo prévio o script bloqueia antes de consultar/enviar.
- Mesmo em execução manual, `--send` bloqueia fora da janela: seg-qui 06:00–19:59 BRT; sexta 06:00–17:59 BRT; fim de semana bloqueado.
- JSON/dry-run também carrega `gate_ok`, `gate_reason` e `text` no `cadence_preview`, para a revisão ver o mesmo gate do envio.
- Não enviar WhatsApp, não tocar HubSpot real além de dry-run/teste local.

## Validação

```
python3 -m unittest tests.test_cadencia_message_tone tests.test_cadencia_stage_guard tests.test_mql_sdr_followup -v
python3 -m py_compile scripts/cadencia_primeiro_contato.py
```
