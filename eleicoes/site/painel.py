"""Painel estático: imagens PNG (para WhatsApp) e página HTML autocontida."""
import base64
import html
import json
import io
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

COR_A = "#e34948"   # vermelho (Lula / PT)
COR_B = "#2a78d6"   # azul (Flávio Bolsonaro / PL)
TINTA = "#0b0b0b"
TINTA2 = "#52514e"
GRADE = "#e4e3df"
FUNDO = "#fcfcfb"

AVISO_CURTO = ("Projeto pessoal, sem filiação partidária. Estimativa estatística, não é resultado oficial; "
               "o autor não se responsabiliza por erros ou imprecisões.")
AVISO = ("Este é um projeto pessoal de estudo, sem filiação a partido, candidato, instituição de pesquisa ou ao TSE. "
         "Os números são estimativas estatísticas feitas a partir dos resultados parciais divulgados pelo TSE e podem "
         "estar errados. Não é resultado oficial: o resultado oficial é o divulgado pelo TSE. O autor não se "
         "responsabiliza por erros, imprecisões ou decisões tomadas com base nestas informações.")

plt.rcParams.update({
    "font.family": "DejaVu Sans", "axes.edgecolor": GRADE, "axes.labelcolor": TINTA2, "xtick.color": TINTA2,
    "ytick.color": TINTA2, "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": FUNDO,
    "axes.facecolor": FUNDO, "savefig.facecolor": FUNDO,
})


# nomes curtos que não são a primeira palavra (eleições de 2006 a 2022, painéis simulados)
APELIDOS = {"Geraldo Alckmin": "Alckmin", "José Serra": "Serra", "Fernando Haddad": "Haddad",
            "Jair Bolsonaro": "Bolsonaro"}


def curto(nome):
    """Nome curto para tabelas e gráficos ("Flávio Bolsonaro" -> "Flávio"); títulos usam o nome completo."""
    return APELIDOS.get(nome, nome.split()[0] if nome else nome)


def _pct_ap(x):
    return "<0,1%" if 0 < x < 0.05 else _pct(x, 1)


def _pct(x, casas=1):
    return f"{x:.{casas}f}%".replace(".", ",")


def _linha_tempo(ax, hist, nomes):
    h = hist.copy()
    h["t"] = pd.to_datetime(h["hora"], utc=True).dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
    a, b = curto(nomes[0]), curto(nomes[1])
    ax.fill_between(h["t"], h["A_p05"], h["A_p95"], color=COR_A, alpha=0.18, lw=0)
    ax.fill_between(h["t"], 100 - h["A_p95"], 100 - h["A_p05"], color=COR_B, alpha=0.18, lw=0)
    ax.plot(h["t"], h["A_media"], color=COR_A, lw=2, marker="o", ms=4, label=f"{a} (previsão)")
    ax.plot(h["t"], 100 - h["A_media"], color=COR_B, lw=2, marker="o", ms=4, label=f"{b} (previsão)")
    ax.plot(h["t"], h["parcial_A"], color=COR_A, lw=1, ls=":", label=f"{a} (apurado)")
    ax.plot(h["t"], 100 - h["parcial_A"], color=COR_B, lw=1, ls=":", label=f"{b} (apurado)")
    ax.axhline(50, color=TINTA2, lw=0.8, ls="--")
    ax.grid(axis="y", color=GRADE, lw=0.6)
    ax.set_ylabel("% dos votos válidos")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    lo = min(h["A_p05"].min(), 100 - h["A_p95"].max(), h["parcial_A"].min(), 100 - h["parcial_A"].max())
    hi = 100 - lo
    ax.set_ylim(max(0, min(lo, 45) - 1), min(100, max(hi, 55) + 1))
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    if h["t"].nunique() == 1:
        t0 = h["t"].iloc[0]
        ax.set_xlim(t0 - pd.Timedelta(minutes=30), t0 + pd.Timedelta(minutes=30))
    if len(h) > 1:
        for _, r in h.iloc[[-1]].iterrows():
            ax.annotate(_pct(r["A_media"]), (r["t"], r["A_media"]), xytext=(4, 0), textcoords="offset points",
                        color=TINTA, fontsize=9, va="center")
            ax.annotate(_pct(100 - r["A_media"]), (r["t"], 100 - r["A_media"]), xytext=(4, 0),
                        textcoords="offset points", color=TINTA, fontsize=9, va="center")


def imagem_principal(res, hist, caminho):
    """PNG 1080x1350 para compartilhar."""
    a, b = res["nomes"]
    br = res["grupos"]["Brasil"]["Brasil"]
    fig = plt.figure(figsize=(9, 11.25), dpi=120)
    fig.text(0.05, 0.965, "2º turno presidencial · previsão da apuração", fontsize=17, weight="bold", color=TINTA)
    fig.text(0.05, 0.94, f"Atualizado {res['hora_txt']} · {_pct(res['pct_secoes'], 2)} das seções apuradas "
                         f"(TSE)", fontsize=10.5, color=TINTA2)
    for i, (nome, cor, m, lo, hi, p, parc) in enumerate([
        (a, COR_A, br["A_media"], br["A_p05"], br["A_p95"], br["prob_A"], res["parcial_A"]),
        (b, COR_B, 100 - br["A_media"], 100 - br["A_p95"], 100 - br["A_p05"], 1 - br["prob_A"],
         100 - res["parcial_A"]),
    ]):
        x = 0.05 + 0.47 * i
        fig.patches.append(plt.Rectangle((x, 0.80), 0.43, 0.12, transform=fig.transFigure, color=cor, alpha=0.08,
                                         lw=0))
        fig.patches.append(plt.Rectangle((x, 0.80), 0.008, 0.12, transform=fig.transFigure, color=cor, lw=0))
        fig.text(x + 0.025, 0.895, nome, fontsize=13, weight="bold", color=TINTA)
        fig.text(x + 0.025, 0.845, _pct(m), fontsize=30, weight="bold", color=TINTA)
        fig.text(x + 0.24, 0.868, f"chance de vencer\n{_pct(100 * p, 0)}", fontsize=11, color=TINTA, va="center")
        parc_txt = _pct(parc) if res["pct_secoes"] > 0 else "—"
        fig.text(x + 0.025, 0.815, f"intervalo 90%: {_pct(lo)} a {_pct(hi)} · apurado: {parc_txt}", fontsize=8.5,
                 color=TINTA2)
    ax = fig.add_axes([0.09, 0.45, 0.86, 0.31])
    ax.set_title("Linha do tempo da previsão (faixa = intervalo de 90%)", fontsize=11, loc="left", color=TINTA)
    _linha_tempo(ax, hist, (a, b))
    # tabela por região e porte
    linhas = []
    for nivel in ["Região", "Porte"]:
        for nome, g in res["grupos"][nivel].items():
            if not (nivel == "Porte" and nome == "Exterior"):  # mesma linha da região Exterior
                linhas.append((nome, g))
    y = 0.39
    fig.text(0.05, y, f"Previsão por região e porte da cidade (% válidos de {curto(a)})", fontsize=11, color=TINTA,
             weight="bold")
    y -= 0.03
    fig.text(0.05, y, "", fontsize=9)
    cab = ["", "apurado", f"{curto(a)} previsto", "intervalo 90%", f"chance {curto(a)}"]
    xs = [0.05, 0.40, 0.53, 0.68, 0.86]
    for xx, c in zip(xs, cab):
        fig.text(xx, y, c, fontsize=8.5, color=TINTA2)
    for nome, g in linhas:
        y -= 0.024
        vals = [nome, _pct_ap(g["pct_apurado"]), _pct(g["A_media"]), f"{_pct(g['A_p05'])} – {_pct(g['A_p95'])}",
                _pct(100 * g["prob_A"], 0)]
        for xx, v in zip(xs, vals):
            fig.text(xx, y, v, fontsize=9, color=TINTA)
    fig.text(0.05, 0.026, "Modelo: transferência de votos do 1º para o 2º turno estimada nos municípios já apurados "
                          "(UF/porte → UF → região → Brasil). Dados: TSE.", fontsize=7, color=TINTA2)
    fig.text(0.05, 0.010, AVISO_CURTO, fontsize=7, color=TINTA2)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    fig.savefig(caminho)
    plt.close(fig)


def _intervalos(ax, itens, rotulo):
    """Ponto = previsão, barra = intervalo de 90%, | = apurado, um grupo por linha."""
    ys = range(len(itens))
    for y, (nome, g) in zip(ys, itens):
        cor = COR_A if g["A_media"] >= 50 else COR_B
        ax.plot([g["A_p05"], g["A_p95"]], [y, y], color=cor, lw=3, alpha=0.35, solid_capstyle="round")
        ax.plot(g["A_media"], y, "o", color=cor, ms=8)
        ax.plot(g["parcial"], y, "|", color=TINTA2, ms=10)
        ax.annotate(f"{_pct(g['A_media'])}  ({_pct_ap(g['pct_apurado'])} apurado)", (max(g["A_p95"], g["parcial"] if g["parcial"] == g["parcial"] else 0, 50) + 1, y),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=8, color=TINTA2)
    ax.set_yticks(list(ys), [rotulo(n) for n, _ in itens])
    ax.set_ylim(-0.7, len(itens) - 0.3)
    ax.axvline(50, color=TINTA2, lw=0.8, ls="--")
    ax.grid(axis="x", color=GRADE, lw=0.6)
    ax.set_xlim(0, 100)


def imagem_estados(res, caminho):
    a, b = res["nomes"]
    grupos = res["grupos"]
    blocos = [("Região", list(grupos["Região"].items())[::-1], str),
              ("Porte da cidade", list(grupos["Porte"].items())[::-1], str),
              ("Estado", sorted(grupos["UF"].items(), key=lambda kv: kv[1]["A_media"]),
               lambda n: "Exterior" if n == "zz" else n.upper())]
    fig, axs = plt.subplots(3, 1, figsize=(9, 15), dpi=120, sharex=True,
                            gridspec_kw={"height_ratios": [len(x[1]) + 1.5 for x in blocos]})
    fig.subplots_adjust(left=0.25, right=0.95, top=0.92, bottom=0.05, hspace=0.12)
    for ax, (titulo, itens, rot) in zip(axs, blocos):
        _intervalos(ax, itens, rot)
        ax.set_title(titulo, loc="left", fontsize=11, color=TINTA, weight="bold")
    axs[-1].set_xlabel(f"% dos votos válidos para {curto(a)} (ponto = previsão, barra = intervalo 90%, | = apurado)")
    fig.text(0.05, 0.965, f"Previsão por região, porte e estado · {a} x {b}", fontsize=16, weight="bold", color=TINTA)
    fig.text(0.05, 0.945, f"Atualizado {res['hora_txt']} · {_pct(res['pct_secoes'], 2)} das seções apuradas",
             fontsize=10, color=TINTA2)
    fig.text(0.05, 0.01, AVISO_CURTO, fontsize=7, color=TINTA2)
    fig.savefig(caminho)
    plt.close(fig)


def _b64(caminho):
    with open(caminho, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _tabela(grupos, a):
    linhas = "".join(
        f"<tr><td>{html.escape(n)}</td><td>{_pct_ap(g['pct_apurado'])}</td><td>{_pct(g['parcial'])}</td>"
        f"<td><b>{_pct(g['A_media'])}</b></td><td>{_pct(g['A_p05'])} – {_pct(g['A_p95'])}</td>"
        f"<td>{_pct(100 * g['prob_A'], 0)}</td><td>{_pct(g['comparecimento'])}</td></tr>"
        for n, g in grupos.items())
    return (f"<table><thead><tr><th></th><th>apurado</th><th>{a} apurado</th><th>{a} previsto</th>"
            f"<th>intervalo 90%</th><th>chance {a}</th><th>comparecimento previsto</th></tr></thead><tbody>{linhas}</tbody>"
            "</table>")


def _tabela_transf(transf):
    if not transf:
        return ""
    cols = list(next(iter(transf.values())).keys())
    cab = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    linhas = "".join("<tr><td>" + html.escape(n) + "</td>" + "".join(
        f"<td>{_pct(v[0])} <small>({_pct(v[1], 0)}–{_pct(v[2], 0)})</small></td>" for v in t.values()) + "</tr>"
        for n, t in transf.items())
    return f"<table><thead><tr><th></th>{cab}</tr></thead><tbody>{linhas}</tbody></table>"


def pagina_html(res, img_principal, img_estados, caminho):
    a, b = res["nomes"]
    blocos = "".join(f"<h2>Por {html.escape(nivel.lower())}</h2>"
                     f"{_tabela(g, curto(a))}"
                     for nivel, g in res["grupos"].items() if nivel != "Brasil")
    doc = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Previsão 2º turno</title>
<style>
:root{{--bg:#fcfcfb;--fg:#0b0b0b;--fg2:#52514e;--grid:#e4e3df}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#1a1a19;--fg:#f0efec;--fg2:#c3c2b7;--grid:#3a3a37}}}}
:root[data-theme="dark"]{{--bg:#1a1a19;--fg:#f0efec;--fg2:#c3c2b7;--grid:#3a3a37}}
body{{background:var(--bg);color:var(--fg);font-family:system-ui,sans-serif;margin:0 auto;max-width:960px;padding:16px}}
img{{width:100%;height:auto;border-radius:8px}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin-bottom:12px;display:block;overflow-x:auto}}
th,td{{padding:4px 8px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}}
th:first-child,td:first-child{{text-align:left}} th{{color:var(--fg2);font-weight:500}}
small,.nota{{color:var(--fg2)}}
</style></head><body>
<h1>2º turno presidencial · previsão da apuração</h1>
<p class="nota">Atualizado {res['hora_txt']} · {_pct(res['pct_secoes'], 2)} das seções apuradas.
Página gerada automaticamente a cada 10 minutos.</p>
<p class="nota"><b>Aviso.</b> {html.escape(AVISO)}</p>
<img alt="Resumo da previsão" src="data:image/png;base64,{_b64(img_principal)}">
<h2>Brasil</h2>{_tabela(res['grupos']['Brasil'], a)}
{blocos}
<h2>Estados</h2><img alt="Previsão por estado" src="data:image/png;base64,{_b64(img_estados)}">
<h2>Transferências estimadas (1º → 2º turno)</h2>
<p class="nota">Fração dos eleitores de cada origem no 1º turno que foi para cada destino no 2º turno
(média e intervalo de 90%). "Outros" = soma dos candidatos que não foram ao 2º turno. A = {html.escape(a)},
B = {html.escape(b)}.</p>
{_tabela_transf(res.get('transferencias', {}))}
<h2>Como funciona</h2>
<p class="nota">Para cada município, o resultado do 1º turno (A, B, Outros, branco/nulo, abstenção) é
transformado no 2º turno por uma matriz de transferência. A matriz é estimada nos municípios já apurados,
começando pelos mais próximos (mesma UF e porte de cidade) e recorrendo à UF, à região e ao Brasil quando há
poucos dados. As seções ainda não apuradas de cada município seguem a matriz estimada, misturada com o
resultado parcial do próprio município. A incerteza vem de milhares de simulações, que incluem a incerteza dos
parâmetros, choques por estado e variação entre municípios.</p>
</body></html>"""
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(doc)


def grafico_backtest(res, caminho):
    ordens = list(res["ordem"].unique())
    fig, axs = plt.subplots(len(ordens), 1, figsize=(9, 3.2 * len(ordens)), dpi=110, squeeze=False)
    for ax, o in zip(axs[:, 0], ordens):
        r = res[(res["ordem"] == o) & (res["rodada"] == 0)].sort_values("pct_secoes")
        ax.fill_between(r["pct_secoes"], r["A_p05"], r["A_p95"], color=COR_A, alpha=0.2, lw=0,
                        label="intervalo 90%")
        ax.plot(r["pct_secoes"], r["A_media"], color=COR_A, lw=2, marker="o", ms=4, label="previsão")
        ax.plot(r["pct_secoes"], r["parcial_A"], color=TINTA2, lw=1, ls=":", label="apurado")
        ax.axhline(r["real_A"].iloc[0], color=TINTA, lw=1, ls="--", label="resultado final")
        ax.set_xscale("log")
        ax.set_xticks([0.5, 1, 2, 5, 10, 20, 50, 99], ["0,5", "1", "2", "5", "10", "20", "50", "99"])
        ax.set_title(f"Ordem de apuração: {o}", loc="left", fontsize=11)
        ax.set_ylabel("% válidos Lula")
        ax.grid(axis="y", color=GRADE, lw=0.6)
        ax.legend(fontsize=8, frameon=False, loc="lower right")
    axs[-1, 0].set_xlabel("% das seções apuradas")
    fig.tight_layout()
    fig.savefig(caminho)
    plt.close(fig)


def linhas_web(res, hist):
    """Linhas do painel interativo na web: {"historico", "previsao", "transferencias"}."""
    a, b = res["nomes"]
    num = lambda x: None if x is None or x != x else round(float(x), 3)  # noqa: E731
    h = [{"hora": r["hora"], **{k: num(r[k]) for k in ["pct_secoes", "parcial_A", "A_media", "A_p05", "A_p95",
                                                         "prob_A"]}} for _, r in hist.iterrows()]
    if res.get("real_A") is not None:
        for r in h:
            r["real_A"] = num(res["real_A"])
    prev = []
    for nivel, grupos in res["grupos"].items():
        for nome, g in grupos.items():
            prev.append({"nivel": nivel, "nome": ("Exterior" if nome == "zz" else nome.upper()) if nivel == "UF" else nome,
                         **{k: num(g.get(k)) for k in ["pct_apurado", "parcial", "A_media", "A_p05", "A_p95", "prob_A",
                                                       "comparecimento", "pct_eleitorado"]},
                         **{k: round(g[k]) for k in ["eleitores", "votos_A_apurado", "votos_B_apurado",
                                                      "votos_A_previsto", "votos_B_previsto"] if k in g},
                         "nome_A": curto(a), "nome_B": curto(b), "nome_A_completo": a, "nome_B_completo": b, "hora_txt": res["hora_txt"], "proxima_txt": res.get("proxima_txt", ""), "pct_secoes": num(res["pct_secoes"]),
                         **({"real": num(g["real"])} if "real" in g else {})})
    transf = [{"grupo": g, "transferencia": t, "media": num(v[0]), "p05": num(v[1]), "p95": num(v[2])}
              for g, d in res.get("transferencias", {}).items() for t, v in d.items()]
    return {"historico": h, "previsao": prev, "transferencias": transf}


def dados_web(res, hist, pasta):
    """JSONs de linhas para o painel interativo na web."""
    os.makedirs(pasta, exist_ok=True)
    for nome, linhas in linhas_web(res, hist).items():
        with open(os.path.join(pasta, f"{nome}.json"), "w") as f:
            json.dump(linhas, f, ensure_ascii=False)
