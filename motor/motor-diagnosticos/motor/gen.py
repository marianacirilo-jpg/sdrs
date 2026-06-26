# -*- coding: utf-8 -*-
import os, base64
from leads import LEADS

OUT = os.path.dirname(os.path.abspath(__file__))
HOJE = "13 jun 2026"

def b64(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

LOGO_WHITE = b64(os.path.join(OUT, "logo", "zydon_full.png"))        # tema escuro
LOGO_BLACK = b64(os.path.join(OUT, "logo", "zydon_full_black.png"))  # tema claro

def stat_cards(food):
    big = ('R$ 443 bi', 'faturamento do atacado distribuidor em 2024, <b>+9,78%</b> no ano. '
           '<b>Alimentos é a maior categoria</b> do setor, com 45,5%.') if food else \
          ('R$ 443 bi', 'movimentados pelo atacado distribuidor brasileiro em 2024, <b>+9,78%</b> no ano &mdash; '
           'todas as categorias.')
    return f'''
    <div class="statgrid">
      <div class="statcard"><div class="statnum">{big[0]}</div><p>{big[1]}</p></div>
      <div class="statcard"><div class="statnum">14%</div><p>do faturamento dos <b>distribuidores com entrega</b> já vem do e-commerce B2B. A média geral subiu de 6% para 8%.</p></div>
      <div class="statcard"><div class="statnum">+62%</div><p>foi o crescimento do canal digital B2B em 2 anos. <b>Quase 3x mais rápido</b> que o resto do setor.</p></div>
      <div class="statcard"><div class="statnum">+ da metade</div><p>das grandes compras B2B já são feitas por <b>autoatendimento</b>, sem depender de vendedor.</p></div>
    </div>'''

def page(tag, body, logo_src):
    return f'''<section class="page">
  <header class="phead"><img class="logo" src="{logo_src}" alt="zydon"><span class="tag">{tag}</span></header>
  <div class="pbody">{body}</div>
  <footer class="pfoot"><span>Material de briefing produzido pela Zydon</span><span>zydon.com.br</span></footer>
</section>'''

def build_html(l):
    food = l.get("food", l["slug"] in ("nacional-carnes", "zotto-comercial"))
    logo_src = LOGO_WHITE if l["theme"] == "dark" else LOGO_BLACK

    p1body = f'''
    <div class="hero">
      <div class="kline"></div>
      <h1>Potencial de<br><span class="hl">digitalização</span><br>da operação B2B</h1>
      <div class="breadcrumb">{l["empresa"]} &nbsp;/&nbsp; {l["cargo_area"]} &nbsp;/&nbsp; {l["local"]}</div>
      <div class="prepared">Preparado para <b>{l["contato"]}</b> &middot; a partir de dados públicos e das respostas no diagnóstico Zydon &middot; {HOJE}</div>
    </div>
    <div class="sectitle"><span class="dash"></span>SOBRE A {l["empresa"].upper()}</div>
    <div class="aboutbox"><p>{l["sobre"]}</p><p class="src">{l["sobre_fonte"]}</p></div>
    <div class="sectitle"><span class="dash"></span>PERFIL DA OPERAÇÃO</div>
    <div class="profile">
      <div class="pcard wide"><span class="plabel">QUEM A EMPRESA ATENDE</span><span class="pval">{l["vende_para"]}</span></div>
      <div class="pcard"><span class="plabel">COMO VENDE HOJE</span><span class="pval">{l["como_vende"]}</span></div>
      <div class="pcard"><span class="plabel">LOJA VIRTUAL</span><span class="pval">{l["loja_virtual"]}</span></div>
      <div class="pcard"><span class="plabel">ERP UTILIZADO</span><span class="pval">{l["erp"]}</span></div>
      <div class="pcard"><span class="plabel">VENDEDORES INTERNOS</span><span class="pval">{l["vendedores"]}</span></div>
      <div class="pcard"><span class="plabel">TIME TOTAL</span><span class="pval">{l["time_total"]}</span></div>
      <div class="pcard"><span class="plabel">FATURAMENTO ANUAL</span><span class="pval">{l["faturamento"]}</span></div>
      <div class="pcard wide"><span class="plabel">COMPRA AUTÔNOMA (RESPOSTA NO DIAGNÓSTICO)</span><span class="pval hl-soft">{l["compra_sozinho"]}</span></div>
    </div>
    <p class="src bottom">Dados informados por {l["contato"]} no diagnóstico comercial Zydon.</p>'''

    enc = "".join(f'<li><span class="bdash"></span><p>{x}</p></li>' for x in l["encontramos"])
    p2body = f'''
    <div class="sectitle"><span class="dash"></span>O QUE ENCONTRAMOS</div>
    <ul class="findings">{enc}</ul>
    <div class="callout">
      <div class="colabel">PONTO DE ATENÇÃO &middot; ESSA OPERAÇÃO EMPURRA OU PUXA PEDIDO?</div>
      <p>{l["pushpull"]}</p>
    </div>
    <div class="contabox">
      <h3>A conta que quase ninguém faz</h3>
      <p>{l["conta"]}</p>
    </div>
    <div class="sectitle"><span class="dash"></span>O MERCADO JÁ VIROU ESSE JOGO</div>
    {stat_cards(food)}
    <p class="src">Fontes: Ranking ABAD/NielsenIQ 2025 (dados de 2024) e Forrester. O crescimento do setor veio de ticket e recompra, não de mais clientes.</p>'''

    p3body = f'''
    <div class="sectitle"><span class="dash"></span>O QUE FICA NA MESA PRA {l["empresa"].upper()}</div>
    <div class="meanbox">
      <p>{l["significa"]} No patamar dos distribuidores que já digitalizaram (14% da receita), é o que deixa de entrar a cada ano sem um canal digital:</p>
      <div class="bignum"><span class="range">{l["pot_low"]}&ndash;{l["pot_high"]}</span><span class="bnsub">por ano que ficam<br>na mesa hoje</span></div>
      <div class="bnbar"><span class="bnbar-fill"></span></div>
      <div class="permes">&asymp; {l["deixa_mes"]} por mês de potencial não capturado</div>
      <p class="src">Estimativa ilustrativa: {l["pot_base"]} O número real depende da base de clientes e do mix da {l["empresa"]}.</p>
      <div class="checks">
        <div class="chk"><span class="ck">&#10003;</span><p><b>Vendedor para de tirar pedido</b> e passa a fechar negócio e cuidar de carteira.</p></div>
        <div class="chk"><span class="ck">&#10003;</span><p><b>Cliente compra 24/7</b>, com a tabela e o crédito dele, direto do celular.</p></div>
        <div class="chk"><span class="ck">&#10003;</span><p><b>Ticket e recompra sobem</b>: catálogo na mão sugere mais itens por pedido.</p></div>
        <div class="chk"><span class="ck">&#10003;</span><p><b>Time atende mais clientes</b> sem precisar contratar mais gente pro telefone.</p></div>
      </div>
    </div>
    <div class="sectitle"><span class="dash"></span>E A INTEGRAÇÃO? JÁ ESTÁ RESOLVIDA</div>
    <div class="erpbox">
      <div class="erptop">
        <div class="erpitem"><span class="erplabel">INTEGRAÇÃO</span><span class="erpval">{l["erp_integ"]}</span></div>
        <div class="erpitem"><span class="erplabel">GO-LIVE MÉDIO</span><span class="erpval hl">{l["erp_golive"]}</span></div>
        <div class="erpitem"><span class="erplabel">DESENVOLVIMENTO</span><span class="erpval">{l["erp_dev"]}</span></div>
      </div>
      <p class="erpdesc">{l["erp_line"]}</p>
      <p class="erpnote">A Zydon nasceu dentro da Sankhya e conhece o ecossistema de distribuição por dentro &mdash; as integrações foram construídas para o B2B desde o início, não adaptadas depois.</p>
    </div>'''

    pages = page("ANÁLISE DE POTENCIAL", p1body, logo_src) + page("DIAGNÓSTICO", p2body, logo_src) + page("POTENCIAL & INTEGRAÇÃO", p3body, logo_src)
    return TEMPLATE.replace("{{THEME}}", l["theme"]).replace("{{PAGES}}", pages)

TEMPLATE = r'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<style>
:root{ --lime:#CDEB00; }
*{margin:0;padding:0;box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact;}
@page{size:210mm 297mm;margin:0;}
html,body{font-family:'Poppins',sans-serif;}
body[data-theme="dark"]{ --bg:#0a0a0a; --fg:#ffffff; --muted:#9a9a9d; --card:#161616; --cardln:#262626; --hair:#222; }
body[data-theme="light"]{ --bg:#ffffff; --fg:#0b0b0b; --muted:#6b6b70; --card:#f4f4f2; --cardln:#e6e6e6; --hair:#e6e6e6; }
.page{position:relative;width:210mm;height:297mm;background:var(--bg);color:var(--fg);
  padding:15mm 15mm 11mm;display:flex;flex-direction:column;overflow:hidden;page-break-after:always;}
.page:last-child{page-break-after:auto;}
.phead{display:flex;align-items:center;justify-content:space-between;}
.logo{height:21px;width:auto;}
.tag{font-size:9px;letter-spacing:.18em;font-weight:600;color:var(--fg);border:1px solid var(--fg);border-radius:4px;padding:6px 10px;}
.pbody{flex:1;padding-top:7mm;}
.pfoot{display:flex;justify-content:space-between;font-size:8.5px;color:var(--muted);padding-top:7px;border-top:1px solid var(--hair);letter-spacing:.02em;}
.pfoot span:last-child{font-weight:600;}
.sectitle{display:flex;align-items:center;gap:9px;font-size:10px;font-weight:600;letter-spacing:.16em;color:var(--lime);margin:0 0 13px;}
.sectitle .dash{width:18px;height:2px;background:var(--lime);display:inline-block;flex:0 0 18px;}
.hl{color:var(--lime);}
b{font-weight:600;}
.src{font-size:9.5px;color:var(--muted);margin-top:10px;line-height:1.45;}
.src.bottom{margin-top:8px;}

/* PAGE 1 */
.hero{margin-bottom:9mm;}
.hero .kline{width:34px;height:4px;background:var(--lime);margin-bottom:13px;}
h1{font-size:40px;font-weight:700;line-height:1.02;letter-spacing:-.025em;}
.breadcrumb{margin-top:14px;font-size:13px;font-weight:500;}
.prepared{margin-top:7px;font-size:10.5px;color:var(--muted);}
.aboutbox{background:var(--card);border:1px solid var(--cardln);border-radius:12px;padding:18px 20px;margin-bottom:8mm;}
.aboutbox p{font-size:13.5px;line-height:1.65;}
.profile{display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px;}
.pcard{background:var(--card);border:1px solid var(--cardln);border-radius:10px;padding:14px 15px;display:flex;flex-direction:column;gap:6px;min-height:70px;justify-content:center;}
.pcard.wide{grid-column:1 / -1;}
.plabel{font-size:9px;letter-spacing:.1em;color:var(--muted);font-weight:600;}
.pval{font-size:15.5px;font-weight:600;line-height:1.3;}
.pval.hl-soft{color:var(--lime);}

/* PAGE 2 */
.findings{list-style:none;margin-bottom:7mm;}
.findings li{display:flex;gap:11px;margin-bottom:10px;align-items:flex-start;}
.findings .bdash{flex:0 0 16px;height:2px;background:var(--lime);margin-top:9px;}
.findings p{font-size:12.5px;line-height:1.6;}
.callout{border:1.5px solid var(--lime);border-radius:12px;padding:16px 20px;margin-bottom:6mm;background:rgba(205,235,0,.06);}
.colabel{font-size:9.5px;letter-spacing:.14em;font-weight:700;color:var(--lime);margin-bottom:8px;}
.callout p{font-size:13px;line-height:1.6;}
.contabox{background:var(--card);border:1px solid var(--cardln);border-radius:12px;padding:16px 20px;margin-bottom:7mm;}
.contabox h3{font-size:16.5px;font-weight:700;margin-bottom:7px;letter-spacing:-.01em;}
.contabox p{font-size:12px;line-height:1.6;}
.statgrid{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-bottom:7px;}
.statcard{background:var(--card);border:1px solid var(--cardln);border-radius:12px;padding:15px 17px;}
.statnum{font-size:30px;font-weight:700;color:var(--lime);letter-spacing:-.02em;line-height:1;margin-bottom:7px;}
.statcard p{font-size:10px;line-height:1.5;}

/* PAGE 3 */
.meanbox{background:var(--card);border:1px solid var(--cardln);border-radius:14px;padding:18px 20px;margin-bottom:6mm;}
.meanbox > p{font-size:13px;line-height:1.6;}
.bignum{display:flex;align-items:baseline;gap:15px;margin:15px 0 11px;}
.range{font-size:48px;font-weight:700;color:var(--lime);letter-spacing:-.03em;line-height:.95;}
.bnsub{font-size:11px;color:var(--muted);line-height:1.35;}
.bnbar{height:8px;border-radius:6px;background:var(--cardln);overflow:hidden;margin-bottom:8px;}
.bnbar-fill{display:block;height:100%;width:60%;background:var(--lime);border-radius:6px;}
.permes{font-size:12px;font-weight:600;margin-bottom:6px;}
.checks{display:grid;grid-template-columns:1fr 1fr;gap:12px 18px;margin-top:15px;}
.chk{display:flex;gap:10px;align-items:flex-start;}
.ck{flex:0 0 19px;height:19px;border-radius:5px;background:var(--lime);color:#000;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:1px;}
.chk p{font-size:11.5px;line-height:1.5;}
.erpbox{background:var(--card);border:1px solid var(--cardln);border-radius:14px;padding:18px 20px;}
.erptop{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;padding-bottom:14px;margin-bottom:13px;border-bottom:1px solid var(--cardln);}
.erpitem{display:flex;flex-direction:column;gap:5px;}
.erplabel{font-size:9px;letter-spacing:.1em;color:var(--muted);font-weight:600;}
.erpval{font-size:15.5px;font-weight:700;letter-spacing:-.01em;}
.erpdesc{font-size:12.5px;line-height:1.6;margin-bottom:10px;}
.erpnote{font-size:10.5px;line-height:1.55;color:var(--muted);}
</style></head>
<body data-theme="{{THEME}}">{{PAGES}}</body></html>'''

if __name__ == "__main__":
    for l in LEADS:
        html = build_html(l)
        with open(os.path.join(OUT, f"{l['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print("wrote", l["slug"])
