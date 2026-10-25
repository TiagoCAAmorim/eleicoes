"""Site estático e interativo (para GitHub Pages ou similar).

Usa o mesmo corpo do painel interativo (painel_web.html) com uma pequena camada
que imita a API `dash` e os dados embutidos na página, então funciona sem
servidor e sem login.
"""
import json
import os
import shutil
import subprocess

AQUI = os.path.dirname(os.path.abspath(__file__))

CABECALHO = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="Previsão estatística da apuração do 2º turno presidencial de 2026 a partir dos resultados parciais do TSE. Projeto pessoal, sem filiação partidária.">
<meta property="og:title" content="{titulo}">
<meta property="og:description" content="{og}">
<meta property="og:image" content="painel.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Source+Sans+3:wght@400;500;600&display=swap">
<style>
:root {{
  --font-anthropic-sans: "Source Sans 3", system-ui, sans-serif;
  --font-anthropic-serif: "Source Serif 4", Georgia, serif;
  --color-fg: #1b1a18; --color-fg-muted: #5f5c55; --color-bg: #fbfaf7; --color-panel: #ffffff;
  --color-border-line: #e4e1da; --color-ok: #2e7d32; --color-warn: #b26a00; --color-bad: #c62828;
  --cds-text-secondary: #5f5c55; --cds-surface-popover: #ffffff; --cds-border: #d9d5cc;
  --cds-shadow-popover: 0 4px 16px rgba(0,0,0,.12);
  --cds-chart-grid: #ebe8e1; --cds-chart-axis: #8f8b82; --cds-chart-reference: #8f8b82;
  --cds-radius: 10px; --cds-gap-xs: 4px; --cds-gap-sm: 8px; --cds-gap-md: 16px; --cds-gap-lg: 28px;
  --cds-pad-xs: 4px; --cds-pad-sm: 8px; --cds-pad-lg: 20px;
  --cds-font-size-caption: 13px; --cds-font-size-body: 15px; --cds-font-size-heading: 17px; --cds-font-size-title: 30px;
  --cds-font-weight-medium: 600; --cds-dur-slow: .3s;
}}
@media (prefers-color-scheme: dark) {{ :root {{
  --color-fg: #efede8; --color-fg-muted: #b3afa6; --color-bg: #191816; --color-panel: #22211e;
  --color-border-line: #36342f; --cds-text-secondary: #b3afa6; --cds-surface-popover: #2a2925; --cds-border: #45423c;
  --cds-chart-grid: #312f2b; --cds-chart-axis: #8a867d; --cds-chart-reference: #8a867d; color-scheme: dark;
}} }}
body {{ background: var(--color-bg); color: var(--color-fg); font-family: var(--font-anthropic-sans); margin: 0;
  padding: 24px max(16px, env(safe-area-inset-right, 0px)) 40px max(16px, env(safe-area-inset-left, 0px)); }}
.dash-skeleton {{ background: var(--color-border-line); border-radius: var(--cds-radius); opacity: .4; }}
.lx-baixar {{ display: flex; flex-wrap: wrap; gap: var(--cds-gap-sm); font-size: var(--cds-font-size-caption); }}
.lx-baixar a {{ color: var(--color-fg); }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>
window.__DADOS = {dados};
(function () {{
  const calcs = {{}}, cbs = [];
  window.dash = {{
    data: (id) => {{
      if (id in calcs) {{ const c = calcs[id]; return {{ status: 'ok', data: c.fn(...c.inputs.map((i) => window.__DADOS[i] || [])) }}; }}
      return window.__DADOS[id] ? {{ status: 'ok', data: window.__DADOS[id] }} : {{ status: 'missing', data: [] }};
    }},
    calc: (id, o) => {{ calcs[id] = o; }},
    loader: () => {{}},
    onData: (fn) => {{ cbs.push(fn); if (document.readyState !== 'loading') fn(); }},
    setLink: () => {{}}, params: () => ({{}}), setParams: () => {{}}, resetParams: () => {{}}, refresh: () => {{}},
    colors: ['#e34948', '#2a78d6'],
  }};
  const run = () => cbs.forEach((f) => {{ try {{ f(); }} catch (e) {{ console.error(e); }} }});
  document.addEventListener('DOMContentLoaded', run);
  let t; window.addEventListener('resize', () => {{ clearTimeout(t); t = setTimeout(run, 150); }});
  // atualização automática: a cada 2 min busca a página publicada, extrai os dados embutidos e redesenha sem
  // recarregar (mantém as abas escolhidas e não conta acesso novo); só redesenha se a rodada mudou
  const chave = (d) => JSON.stringify(((d.previsao || []).find((r) => r.nivel === 'Brasil') || {{}}).hora_txt || '');
  let ultima = Date.now();
  async function atualizar() {{
    ultima = Date.now();
    try {{
      const r = await fetch(location.pathname + '?t=' + Date.now(), {{ cache: 'no-store' }});
      if (!r.ok) return;
      const html = await r.text();
      const i = html.indexOf('window.__DADOS = '), j = html.lastIndexOf(';', html.indexOf('(function ()', i));
      if (i < 0 || j < 0) return;
      const novo = JSON.parse(html.slice(i + 'window.__DADOS = '.length, j));
      if (chave(novo) !== chave(window.__DADOS)) {{ window.__DADOS = novo; run(); return 'novo'; }}
      return 'igual';
    }} catch (e) {{ console.warn('atualização automática falhou', e); }}
    return 'erro';
  }}
  window.lxAtualizar = atualizar;
  if (location.protocol.startsWith('http')) {{
    setInterval(() => {{ if (!document.hidden) atualizar(); }}, 2 * 60 * 1000);
    document.addEventListener('visibilitychange', () => {{ if (!document.hidden && Date.now() - ultima > 2 * 60 * 1000) atualizar(); }});
  }}
}})();
</script>
</head><body><div id="dash-root">
"""

RODAPE = """
</div></body></html>
"""

# botão de atualizar no canto superior direito: busca os dados novos como a atualização automática (sem recarregar,
# então não soma acesso no contador)
ATUALIZAR = """
<button type="button" class="lx-refresh" title="Buscar dados novos" aria-label="Buscar dados novos">
<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2"
 stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 1 0-2.34 5.66"/><path d="M20 4v7h-7"/></svg></button>
<style>.lx-refresh{position:fixed;top:10px;right:10px;z-index:6;width:34px;height:34px;display:grid;place-items:center;
padding:0;border-radius:50%;border:1px solid var(--cds-border);background:var(--cds-surface-popover);color:var(--color-fg-muted);
cursor:pointer;opacity:.85;box-shadow:var(--cds-shadow-popover)}.lx-refresh:hover{opacity:1;color:var(--color-fg)}
.lx-refresh:focus-visible{outline:2px solid var(--lx-b);outline-offset:2px}
.lx-refresh.girando svg{animation:lx-gira .8s linear infinite}@keyframes lx-gira{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion: reduce){.lx-refresh.girando svg{animation:none}}@media print{.lx-refresh{display:none}}</style>
<script>(function () {
  const b = document.querySelector('.lx-refresh');
  const dica = {novo: 'Dados novos carregados', igual: 'Sem dados novos do TSE ainda', erro: 'Não foi possível buscar agora'};
  b.addEventListener('click', async () => {
    if (b.classList.contains('girando') || !window.lxAtualizar) return;
    b.classList.add('girando');
    const r = await window.lxAtualizar();
    b.classList.remove('girando');
    b.title = dica[r] || 'Buscar dados novos';
    setTimeout(() => { b.title = 'Buscar dados novos'; }, 4000);
  });
})();</script>
"""

# contador de acessos (hits.sh, sem cadastro nem cookies): imagem discreta no canto inferior direito
CONTADOR = """
<a class="lx-contador" href="https://hits.sh/" title="Contador de acessos (hits.sh)" target="_blank" rel="noopener">
<img src="https://hits.sh/tiagocaamorim.github.io/eleicoes_2026.svg?style=flat-square&amp;label=acessos&amp;color=8a8985&amp;labelColor=5f5e5a"
 alt="" height="16" onerror="this.parentNode.style.display='none'"></a>
<style>.lx-contador{position:fixed;right:8px;bottom:8px;opacity:.55;line-height:0;z-index:5}
.lx-contador:hover{opacity:1}@media print{.lx-contador{display:none}}</style>
"""


def gerar_site(saida, pasta_site, titulo="Previsão do 2º turno presidencial 2026", artefato=False):
    """Monta index.html + imagens em `pasta_site` a partir de saida/<ano>."""
    web = os.path.join(saida, "web")
    dados = {}
    for nome in ["historico", "previsao", "transferencias"]:
        with open(os.path.join(web, f"{nome}.json")) as f:
            dados[nome] = json.load(f)
    geo = os.path.join(os.path.dirname(AQUI), "data/estados_br.geojson")
    if os.path.exists(geo):
        with open(geo) as f:
            dados["geo"] = [json.load(f)]
    att = os.path.join(os.path.dirname(AQUI), "data/atualizacoes.json")
    if os.path.exists(att):
        with open(att) as f:
            dados["atualizacoes"] = json.load(f)
    br = next((r for r in dados["previsao"] if r["nivel"] == "Brasil"), None)
    og = "Previsão estatística da apuração do 2º turno a partir dos parciais do TSE."
    if br:
        n = lambda x: f"{x:.1f}".replace(".", ",")  # noqa: E731
        og = (f"{br.get('nome_A_completo', br['nome_A'])} {n(br['A_media'])}% x {br.get('nome_B_completo', br['nome_B'])} {n(100 - br['A_media'])}% com "
              f"{n(br['pct_secoes'])}% apurado ({br['hora_txt']}). Estimativa, não é resultado oficial.")
    with open(os.path.join(AQUI, "painel_web.html"), encoding="utf-8") as f:
        corpo = f.read().replace("Previsão do 2º turno presidencial 2026", titulo)
    js = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    os.makedirs(pasta_site, exist_ok=True)
    with open(os.path.join(pasta_site, "index.html"), "w", encoding="utf-8") as f:
        doc = (CABECALHO.format(dados=js, og=og.replace('"', "'"), titulo=titulo) + corpo
               + ("" if artefato else ATUALIZAR + CONTADOR) + RODAPE)  # o teste não conta acessos do site
        if artefato:  # página sem <html>/<head>/<body> próprios (a plataforma adiciona)
            for tag in ['<html lang="pt-BR"><head>', "</head><body>", "</body></html>"]:
                doc = doc.replace(tag, "")
            doc = doc.replace("body {", "body.lx-site, body {")
        f.write(doc)
    for img in ["painel.png", "estados.png", "mapa_municipios.png", "dados_municipios.csv", "coeficientes_grupos.csv",
                "resumo_grupos.csv"]:
        if os.path.exists(os.path.join(saida, img)):
            shutil.copy(os.path.join(saida, img), os.path.join(pasta_site, img))
    shutil.copy(os.path.join(AQUI, "analises.html"), os.path.join(pasta_site, "analises.html"))  # lê dados_municipios.csv
    shutil.copy(os.path.join(AQUI, "indicadores.html"), os.path.join(pasta_site, "indicadores.html"))
    imp = os.path.join(os.path.dirname(saida.rstrip("/")), "importancia")  # gerado à parte por scripts/importancia.py
    for nome in ["importancia.json", "indicadores_mun.json"]:
        if os.path.exists(os.path.join(imp, nome)):
            shutil.copy(os.path.join(imp, nome), os.path.join(pasta_site, nome))
    open(os.path.join(pasta_site, ".nojekyll"), "w").close()


def publicar(saida, clone, titulo="Previsão do 2º turno presidencial 2026"):
    """Gera o site dentro do clone do repositório público e faz commit + push."""
    gerar_site(saida, clone, titulo)
    for c in [["git", "add", "-A"], ["git", "commit", "-q", "-m", "atualiza previsão"], ["git", "push", "-q"]]:
        r = subprocess.run(c, cwd=clone, capture_output=True, text=True)
        if r.returncode and c[1] != "commit":
            print("publicação falhou:", " ".join(c), r.stderr.strip()[:300])
            return False
    return True
