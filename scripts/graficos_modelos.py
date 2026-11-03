"""Gráficos da página "Modelos" do site, a partir dos resultados dos testes já gravados em resultados/.

    python scripts/graficos_modelos.py      # grava os PNGs em resultados/modelos/

Não roda nenhum modelo: só lê os CSVs dos testes (calibração da priori, rejogo de 2026, teste de estresse,
governador e prefeito). scripts/gerar_site.py copia os PNGs para o site.
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import _raiz  # noqa: F401,E402
from eleicoes.caminhos import RESULTADOS  # noqa: E402

SAIDA = os.path.join(RESULTADOS, "modelos")
TINTA, TINTA2, GRADE = "#1b1a18", "#5f5c55", "#e4e1da"
AZUL, LARANJA, VERDE_AGUA, AMARELO, CINZA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#9a978f"
REAL = "#1b1a18"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRADE, "axes.labelcolor": TINTA2,
    "xtick.color": TINTA2, "ytick.color": TINTA2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "figure.dpi": 100, "savefig.dpi": 150, "savefig.facecolor": "white",
})
TICKS_PCT = [0, 1, 5, 10, 20, 30, 50, 70, 90]


def _eixo_pct(ax, maximo=100):
    """Eixo de % apurado em raiz quadrada: o começo da apuração, onde tudo acontece, fica legível."""
    ax.set_xscale("function", functions=(lambda x: np.sqrt(np.clip(x, 0, None)), lambda y: y ** 2))
    ax.set_xlim(0, maximo)
    ax.set_xticks([t for t in TICKS_PCT if t <= maximo])
    ax.set_xticklabels([f"{t}%" for t in TICKS_PCT if t <= maximo])
    ax.set_xlabel("seções apuradas")


def _titulo(fig, titulo, subtitulo, selo):
    fig.text(0.012, 0.975, titulo, fontsize=13.5, weight="bold", color=TINTA, va="top")
    fig.text(0.012, 0.915, subtitulo, fontsize=9.5, color=TINTA2, va="top")
    cor = "#8a5300" if selo.startswith("Simula") else "#1f5f9e"
    fundo = "#fbf3e4" if selo.startswith("Simula") else "#e9f1f9"
    fig.text(0.988, 0.975, selo, fontsize=9, weight="bold", color=cor, va="top", ha="right",
             bbox=dict(boxstyle="round,pad=0.35", fc=fundo, ec="none"))


def _salvar(fig, nome):
    os.makedirs(SAIDA, exist_ok=True)
    fig.savefig(os.path.join(SAIDA, nome))
    plt.close(fig)
    print("gravado", os.path.join(SAIDA, nome))


def _cobertura(ax, legenda_loc="lower left"):
    ax.axhline(90, color=TINTA, lw=1, ls=(0, (4, 3)), label="meta: 90%")
    ax.set_ylabel("o intervalo de 90% contém o resultado")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.legend(loc=legenda_loc, fontsize=8.5)


# ----------------------------------------------------------------------------------------------------------------
def antes_da_apuracao():
    """Previsão sem nenhum voto apurado, 2010–2026: matriz da eleição anterior x priori calibrada."""
    d = pd.read_csv(os.path.join(RESULTADOS, "calibracao-priori", "antes_da_apuracao.csv"))
    d = d[d.nivel == "Brasil"]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.8, bottom=0.12)
    anos = sorted(d.ano.unique())
    for i, ano in enumerate(anos):
        for desl, var, cor, nome in [(-0.14, "revisado", CINZA, "Matriz da eleição anterior"),
                                     (0.14, "calibrado", AZUL, "Priori calibrada (adotada)")]:
            r = d[(d.ano == ano) & (d.variante == var)].iloc[0]
            ax.plot([i + desl] * 2, [r.A_p05, r.A_p95], color=cor, lw=5, solid_capstyle="round",
                    alpha=0.85, label=nome if i == 0 else None)
            ax.plot(i + desl, r.A_media, "o", color="white", mec=cor, mew=2, ms=7)
        real = d[d.ano == ano].real.iloc[0]
        ax.plot([i - 0.32, i + 0.32], [real, real], color=REAL, lw=2, label="Resultado" if i == 0 else None)
    ax.set_xticks(range(len(anos)))
    ax.set_xticklabels([str(a) for a in anos])
    ax.set_xlim(-0.6, len(anos) - 0.4)
    ax.axhline(50, color=TINTA2, lw=0.8)
    ax.set_ylabel("candidato do PT, % dos votos válidos")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", fontsize=8.5, ncol=3)
    _titulo(fig, "Antes de abrir as urnas: previsão e intervalo de 90%",
            "2º turno presidencial. A calibrada usa a média das eleições anteriores e a pesquisa da véspera. "
            "Erro médio: 4,4 → 1,1 ponto.", "Resultados reais")
    _salvar(fig, "antes_da_apuracao.png")


def noite_2026():
    """Noite real de 2026: previsão publicada (modelo do dia) x o mesmo rejogo com o modelo adotado."""
    vivo = pd.read_csv(os.path.join(RESULTADOS, "rejogo-2026", "previsoes.csv"))
    vivo = vivo[(vivo.grupo == "Brasil") & (vivo.variante == "atual")]
    nov = pd.read_csv(os.path.join(RESULTADOS, "matriz-v2", "rejogo-2026", "previsoes.csv"))
    nov = nov[(nov.grupo == "Brasil") & (nov.variante == "calibrado_cauteloso")]
    final = vivo.final.iloc[0]
    fig, eixos = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.78, bottom=0.14, wspace=0.08)
    for ax, d, cor, nome in [(eixos[0], vivo, CINZA, "Modelo do dia (publicado ao vivo)"),
                             (eixos[1], nov, AZUL, "Modelo adotado em novembro")]:
        d = d.sort_values("pct_secoes")
        x = d.pct_secoes.clip(upper=100)
        ax.fill_between(x, d.p05, d.p95, color=cor, alpha=0.25, lw=0, label="intervalo de 90%")
        ax.plot(x, d.media, color=cor if cor != CINZA else "#6f6c65", lw=2, label="previsão")
        ax.axhline(final, color=REAL, lw=1.2, ls=(0, (4, 3)))
        ax.text(99, final + 0.15, f"resultado {final:.1f}%".replace(".", ","), ha="right", va="bottom",
                fontsize=8.5, color=TINTA)
        ax.axhline(50, color=TINTA2, lw=0.8)
        _eixo_pct(ax)
        ax.set_title(nome, loc="left", fontsize=10.5, color=TINTA)
        ax.legend(loc="lower right", fontsize=8.5)
    eixos[0].set_ylabel("Lula, % dos votos válidos")
    eixos[0].set_ylim(45, 56)
    _titulo(fig, "A noite de 25/10/2026 rejogada",
            "Os mesmos retratos da apuração gravados durante a noite, passados pelos dois modelos.",
            "Apuração real")
    _salvar(fig, "noite_2026.png")


def presidente_historico():
    """Rejogos por município de 2010–2026: resultado real de cada município, ordem de chegada sintética."""
    d = pd.read_csv(os.path.join(RESULTADOS, "calibracao-priori", "rejogo_calibrado_calibrado_v2.csv"))
    d = d[(d.nivel == "Brasil") & (d.variante == "calibrado")]
    anos = sorted(d.ano.unique())
    fig, eixos = plt.subplots(1, len(anos), figsize=(11, 3.9), sharey=False)
    fig.subplots_adjust(left=0.06, right=0.99, top=0.74, bottom=0.17, wspace=0.32)
    for ax, ano in zip(eixos, anos):
        r = d[(d.ano == ano) & (d.rodada == 0)].sort_values("pct")
        ax.fill_between(r.pct, r.A_p05, r.A_p95, color=AZUL, alpha=0.25, lw=0)
        ax.plot(r.pct, r.A_media, color=AZUL, lw=2)
        ax.axhline(r.real.iloc[0], color=REAL, lw=1.2, ls=(0, (4, 3)))
        _eixo_pct(ax, 95)
        ax.set_xticks([0, 5, 20, 50, 90])
        ax.set_xticklabels(["0", "5", "20", "50", "90%"])
        ax.set_xlabel("")
        c = d[d.ano == ano]
        ax.set_title(f"{ano}\ncobertura {100 * c.cobre90.mean():.0f}%", fontsize=9.5, color=TINTA, loc="left")
        m = r.real.iloc[0]
        ax.set_ylim(m - 4, m + 4)
    eixos[0].set_ylabel("PT, % dos válidos")
    fig.text(0.5, 0.03, "seções apuradas", ha="center", color=TINTA2)
    _titulo(fig, "Presidente 2010–2026: rejogos com o resultado real de cada município",
            "Faixa azul: intervalo de 90%; linha tracejada: resultado. Uma das 2 apurações sorteadas por ano; "
            "a cobertura é das duas.", "Simulação da ordem")
    _salvar(fig, "presidente_historico.png")


def estresse():
    """Teste de estresse: apurações sintéticas com viés de ordem entre e dentro das cidades."""
    vivo = pd.read_csv(os.path.join(RESULTADOS, "estresse", "resumo.csv"))
    cal = pd.read_csv(os.path.join(RESULTADOS, "calibracao-priori", "estresse_resumo.csv"))
    series = [(vivo[vivo.variante == "ao_vivo"], CINZA, "2022, modelo do dia (32 rodadas)", (0, (2, 2)))]
    series.append((cal[cal.variante == "calibrado_cauteloso"], AZUL, "2022 (16 rodadas)", "-"))
    for ano, cor in [(2010, LARANJA), (2014, VERDE_AGUA), (2018, AMARELO)]:
        h = pd.read_csv(os.path.join(RESULTADOS, "estresse-historico", str(ano), "resumo.csv"))
        series.append((h[h.variante == "calibrado_cauteloso"], cor, f"{ano} (16 rodadas)", "-"))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.4))
    fig.subplots_adjust(left=0.075, right=0.985, top=0.78, bottom=0.14, wspace=0.25)
    for d, cor, nome, ls in series:
        d = d[pd.to_numeric(d.pct_secoes, errors="coerce") > 0].astype({"pct_secoes": float})
        d = d.sort_values("pct_secoes")
        a1.plot(d.pct_secoes, 100 * d.cobre90, color=cor, lw=2, ls=ls, marker="o", ms=4, label=nome)
        a2.plot(d.pct_secoes, d.largura90, color=cor, lw=2, ls=ls, marker="o", ms=4, label=nome)
    for ax in (a1, a2):
        _eixo_pct(ax)
        ax.set_xlim(0.7, 95)
    a1.set_ylim(0, 102)
    _cobertura(a1)
    a1.set_title("Cobertura do intervalo de 90%", loc="left", fontsize=10.5, color=TINTA)
    a2.set_title("Largura do intervalo de 90% (pontos)", loc="left", fontsize=10.5, color=TINTA)
    a2.set_ylabel("pontos percentuais")
    _titulo(fig, "Teste de estresse: apurações sintéticas com seções fora de ordem",
            "Cada rodada sorteia um resultado e uma ordem de chegada enviesada, entre e dentro das cidades. "
            "Linhas cheias: modelo adotado.", "Simulação")
    _salvar(fig, "estresse.png")


def governador_prefeito():
    """Governador (46 eleições, 2010–2022) e prefeito (216 eleições, 2012–2024): cobertura ao longo da apuração."""
    g = pd.read_csv(os.path.join(RESULTADOS, "governador", "resumo.csv"))
    p1 = pd.read_csv(os.path.join(RESULTADOS, "prefeito", "resumo_v0.1.csv"))
    p3 = pd.read_csv(os.path.join(RESULTADOS, "prefeito", "resumo_v0.3.csv"))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.78, bottom=0.14, wspace=0.08)
    for d, cor, nome, ls in [(g[g.variante == "media"], CINZA, "configuração do presidente", (0, (2, 2))),
                             (g[g.variante == "media_p3"], AZUL, "adotada (viés parcial 3%)", "-"),
                             (g[g.variante == "pesquisa_o3_p3_antes2"], LARANJA, "adotada + pesquisa (33 eleições)", "-")]:
        d = d[pd.to_numeric(d.pct, errors="coerce").notna()].astype({"pct": float}).sort_values("pct")
        a1.plot(d.pct, 100 * d.cobre90, color=cor, lw=2, ls=ls, marker="o", ms=4, label=nome)
    for d, cor, nome, ls in [(p3[p3.variante == "media"], CINZA, "sem choque comum, viés forte", (0, (2, 2))),
                             (p1[p1.variante == "media_c6"], VERDE_AGUA, "adotada (choque 6%), viés moderado", "-"),
                             (p3[p3.variante == "media_c6"], AZUL, "adotada (choque 6%), viés forte", "-")]:
        d = d[pd.to_numeric(d.pct, errors="coerce").notna()].astype({"pct": float}).sort_values("pct")
        a2.plot(d.pct, 100 * d.cobre90, color=cor, lw=2, ls=ls, marker="o", ms=4, label=nome)
    a1.set_title("Governador: 46 eleições, 2010–2022", loc="left", fontsize=10.5, color=TINTA)
    a2.set_title("Prefeito: 216 eleições, 2012–2024", loc="left", fontsize=10.5, color=TINTA)
    for ax in (a1, a2):
        _eixo_pct(ax)
        ax.set_ylim(30, 102)
        _cobertura(ax)
    a2.set_ylabel("")
    _titulo(fig, "2º turno de governador e prefeito: cobertura do intervalo de 90%",
            "Resultado real de cada eleição; ordem de chegada sorteada (não há retratos parciais dessas apurações).",
            "Simulação da ordem")
    _salvar(fig, "governador_prefeito.png")


def main():
    antes_da_apuracao()
    noite_2026()
    presidente_historico()
    estresse()
    governador_prefeito()


if __name__ == "__main__":
    main()
