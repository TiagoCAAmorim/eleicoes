"""Exemplo numérico fictício do modelo revisado do 2º turno (docs/metodo-detalhado.md).

Cria um país inventado com 9 UFs e 500 municípios, uma matriz de transferência "verdadeira" e uma apuração com os
vieses que vimos em 2026 (Nordeste e capitais mais tarde, primeiras seções de cada cidade mais para A). Roda o modelo
revisado (`transferencia.Config` padrão + priori que erra a linha Outros, como em 2026) em vários momentos da
apuração e gera os gráficos em docs/img/metodo/ e a tabela resultados/exemplo-metodo/linha_do_tempo.csv.

    python scripts/exemplo_metodo.py
"""
import os

import _raiz  # noqa: F401
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from eleicoes.modelos import transferencia as modelo  # noqa: E402

RAIZ = _raiz.RAIZ
IMG = os.path.join(RAIZ, "docs", "img", "metodo")
OUT = os.path.join(RAIZ, "resultados", "exemplo-metodo")
PONTOS = [0, 1, 2, 3, 5, 7, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99]
COR_A, COR_B, CINZA = "#c0392b", "#2c5aa0", "#7f8c8d"


def logit(p):
    return np.log(p / (1 - p))


def theta_de(pab, pba, pr, oA, oB, oW, oN, nA, nB):
    """Probabilidades legíveis -> theta do modelo (inverso de transferencia.matriz)."""
    return np.array([logit(pab / 0.3), logit(pba / 0.3), logit(pr / 0.5), np.log(oA / oN), np.log(oB / oN),
                     np.log(oW / oN), logit(nA / 0.3), logit(nB / 0.3)])


# matriz verdadeira (desconhecida pelo modelo) e a priori que vem da "eleição anterior": a priori acerta quase tudo,
# mas acha que os eleitores de Outros vão mais para B do que de fato vão (o erro de 2026)
VERDADE = theta_de(0.01, 0.01, 0.06, 0.36, 0.38, 0.11, 0.15, 0.04, 0.04)
PRIORI = theta_de(0.01, 0.01, 0.06, 0.28, 0.46, 0.11, 0.15, 0.04, 0.04)


def pais(rng):
    inclinacao = {"rs": -0.2, "sc": -0.6, "pr": -0.4, "sp": -0.25, "rj": -0.1, "mg": 0.0, "ba": 0.6, "pe": 0.5,
                  "ce": 0.55}                                     # logit da preferência por A no 1º turno
    n = {"rs": 60, "sc": 40, "pr": 50, "sp": 90, "rj": 40, "mg": 80, "ba": 60, "pe": 40, "ce": 40}
    ufs = list(n)
    linhas = []
    for uf in ufs:
        E = np.exp(rng.normal(np.log(12_000), 1.0, n[uf])).round()
        E[0] = {"sp": 1_800_000, "rj": 1_200_000}.get(uf, 600_000)                       # capital
        for i, e in enumerate(E):
            lean = inclinacao[uf] + rng.normal(0, 0.35) + (0.25 if i == 0 else 0)
            abst = np.clip(rng.normal(0.20, 0.03), 0.1, 0.35)
            wn = np.clip(rng.normal(0.04, 0.01), 0.01, 0.08)
            outros = np.clip(rng.normal(0.14, 0.03), 0.05, 0.25)
            ab = 1 - abst - wn - outros
            a = ab / (1 + np.exp(-lean))
            linhas.append({"uf": uf, "mun": f"{uf}{i:03d}", "capital": i == 0, "E1": e, "A1": e * a,
                           "B1": e * (ab - a), "O1": e * outros, "W1": e * wn})
    df = pd.DataFrame(linhas)
    df[["A1", "B1", "O1", "W1"]] = df[["A1", "B1", "O1", "W1"]].round()
    df["E2"] = df["E1"]
    # resultado verdadeiro do 2º turno: matriz verdadeira + desvio próprio de cada município
    X = np.column_stack([df["A1"], df["B1"], df["O1"], df["W1"],
                         df["E1"] - df[["A1", "B1", "O1", "W1"]].sum(axis=1)]) / df["E1"].values[:, None]
    Y = X @ modelo.matriz(VERDADE)
    d = rng.normal(0, 0.015, len(df))
    Y[:, 0] += d
    Y[:, 1] -= d
    Y = np.clip(Y, 0, None)
    Y /= Y.sum(axis=1, keepdims=True)
    df[["A2f", "B2f", "W2f", "N2f"]] = Y * df["E2"].values[:, None]
    return df


def apuracao(df, rng):
    """Instante de início e duração da apuração de cada município (Sul/Sudeste antes, Bahia e capitais depois)."""
    atraso = df["uf"].map({"rs": 0.0, "sc": 0.0, "pr": 0.0, "sp": 0.08, "rj": 0.1, "mg": 0.1, "ba": 0.3, "pe": 0.3,
                           "ce": 0.3}).values
    inicio = np.clip(atraso + 0.12 * df["capital"] + rng.exponential(0.12, len(df)), 0, None)
    duracao = 0.15 + 0.25 * np.log10(df["E2"].values) / 6.3 + rng.exponential(0.1, len(df))
    return inicio, duracao


VIES_INICIO = 0.03   # as primeiras seções de cada cidade vêm 3 pontos (da margem nos válidos) mais para A


def retrato(df, inicio, duracao, t):
    f = np.clip((t - inicio) / duracao, 0, 1)
    s = df.copy()
    s["Ea"] = (f * s["E2"]).round()
    fr = s["Ea"] / s["E2"]
    val = s["A2f"] + s["B2f"]
    desloc = VIES_INICIO / 2 * (1 - fr) * val          # parte apurada mais para A enquanto a cidade está no começo
    s["A2"] = ((s["A2f"] + desloc) * fr).round()
    s["B2"] = ((s["B2f"] - desloc) * fr).round()
    s["W2"] = (s["W2f"] * fr).round()
    s["C2"] = s["A2"] + s["B2"] + s["W2"]
    return s


def rodar(df_ap, cfg):
    d, X, Y = modelo.preparar(df_ap)
    aj = modelo.ajustar(d, X, Y, cfg)
    sims = modelo.simular(d, X, Y, aj, cfg)
    return d, aj, sims


SEM = {"choque_uf": 0.0, "choque_uf_inicio": 0.0, "choque_nacional": 0.0, "choque_parcial": 0.0}
CAMADAS = [  # componentes da incerteza ligados um a um, para medir quanto cada um alarga a faixa
    ("Parâmetros + municípios", dict(SEM)),
    ("+ choque por UF", {**SEM, "choque_uf": 0.02, "choque_uf_inicio": 0.04}),
    ("+ choque nacional", {**SEM, "choque_uf": 0.02, "choque_uf_inicio": 0.04, "choque_nacional": 0.01}),
    ("+ viés da evidência parcial", {}),
]


def main():
    os.makedirs(IMG, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(7)
    df = pais(rng)
    inicio, duracao = apuracao(df, rng)
    real = 100 * df["A2f"].sum() / (df["A2f"] + df["B2f"]).sum()
    # instantes em que o país atinge cada % do eleitorado apurado
    ts = np.linspace(0, 2, 4001)
    pct_t = np.array([100 * (np.clip((t - inicio) / duracao, 0, 1) * df["E2"]).sum() / df["E2"].sum() for t in ts])
    linhas, larguras = [], []
    # priori para todos os grupos (como a de 2022 usada em 2026), aqui sem diferença entre grupos
    d0, *_ = modelo.preparar(df.assign(Ea=0, A2=0, B2=0, W2=0, C2=0))
    pri = {"brasil|Brasil": list(PRIORI)}
    for nivel in ["regiao", "uf", "uf_porte"]:
        pri.update({f"{nivel}|{g}": list(PRIORI) for g in d0[nivel].unique()})
    for p in PONTOS:
        t = ts[np.searchsorted(pct_t, p)] if p > 0 else -1
        s = retrato(df, inicio, duracao, t)
        cfg = modelo.Config(priori=pri)
        d, aj, sims = rodar(s, cfg)
        r = modelo.resumo_grupo(sims.sum(1))
        uf = modelo.agregar(d, sims, "uf")
        mu, cov = aj.grupos[("brasil", "Brasil")]
        th = mu + rng.multivariate_normal(np.zeros(len(mu)), cov, 2000)
        leg = modelo.parametros_legiveis(th)
        val_ap = s["A2"].sum() + s["B2"].sum()
        linha = {"pct": p, "parcial_A": 100 * s["A2"].sum() / val_ap if val_ap else np.nan,
                 "P": modelo.indice_parcial(d), "s0": aj.s0, **r, "real_A": real,
                 "oA": leg[:, 3].mean(), "oA_p05": np.percentile(leg[:, 3], 5), "oA_p95": np.percentile(leg[:, 3], 95),
                 "oB": leg[:, 4].mean(), "oB_p05": np.percentile(leg[:, 4], 5), "oB_p95": np.percentile(leg[:, 4], 95)}
        for u, x in uf.items():
            ru = modelo.resumo_grupo(x)
            linha[f"{u}_A"], linha[f"{u}_p05"], linha[f"{u}_p95"] = ru["A_media"], ru["A_p05"], ru["A_p95"]
            linha[f"{u}_real"] = 100 * df.loc[df.uf == u, "A2f"].sum() / df.loc[df.uf == u, ["A2f", "B2f"]].sum().sum()
            linha[f"{u}_ap"] = 100 * s.loc[s.uf == u, "Ea"].sum() / s.loc[s.uf == u, "E2"].sum()
        linhas.append(linha)
        for nome, mud in CAMADAS:
            c = modelo.Config(priori=pri, **mud)
            *_, sm = rodar(s, c)
            ru = modelo.resumo_grupo(sm.sum(1))
            larguras.append({"pct": p, "camada": nome, "largura": ru["A_p95"] - ru["A_p05"]})
        print(f"{p:3d}%  parcial {linha['parcial_A']:6.2f}  prev {r['A_media']:5.2f} [{r['A_p05']:5.2f}, {r['A_p95']:5.2f}]"
              f"  P(A)={r['prob_A']:.2f}  Outros→A {linha['oA']:.2f}  P={linha['P']:.2f}", flush=True)
    tab = pd.DataFrame(linhas)
    lar = pd.DataFrame(larguras)
    tab.to_csv(os.path.join(OUT, "linha_do_tempo.csv"), index=False, float_format="%.4f")
    lar.to_csv(os.path.join(OUT, "largura_por_componente.csv"), index=False, float_format="%.4f")
    print(f"real {real:.2f}")
    graficos(tab, lar, real, df, inicio, duracao, ts, pct_t)
    exemplo_municipio(df, inicio, duracao, ts, pct_t)


def eixo(ax):
    ax.set_xscale("symlog", linthresh=10)
    ax.set_xticks([0, 1, 3, 5, 10, 20, 50, 100])
    ax.set_xticklabels(["0", "1", "3", "5", "10", "20", "50", "100"])
    ax.set_xlim(0, 100)
    ax.set_xlabel("% do eleitorado apurado (escala comprimida acima de 10%)")
    ax.grid(alpha=0.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def graficos(tab, lar, real, df, inicio, duracao, ts, pct_t):
    x = tab["pct"]
    # 1. previsão, faixa de 90% e parcial
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    a1.fill_between(x, tab["A_p05"], tab["A_p95"], color=COR_A, alpha=0.18, label="intervalo de 90%")
    a1.plot(x, tab["A_media"], color=COR_A, lw=2, label="previsão (média)")
    a1.plot(x, tab["parcial_A"], color=CINZA, ls=":", lw=1.8, label="parcial apurada")
    a1.axhline(real, color="k", lw=1, ls="--", label=f"resultado final ({real:.1f}%)")
    a1.axhline(50, color=CINZA, lw=0.8)
    a1.set_ylabel("A, % dos votos válidos")
    a1.set_ylim(44, 56)
    a1.legend(loc="lower right", fontsize=8, frameon=False)
    a1.set_title("País fictício: previsão de A ao longo da apuração", fontsize=11, loc="left")
    eixo(a1)
    a1.set_xlabel("")
    a2.plot(x, 100 * tab["prob_A"], color=COR_A, lw=2, label="A")
    a2.plot(x, 100 * (1 - tab["prob_A"]), color=COR_B, lw=2, label="B")
    a2.set_ylabel("chance de vitória (%)")
    a2.set_ylim(0, 100)
    a2.legend(loc="center right", fontsize=8, frameon=False)
    eixo(a2)
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "1_linha_do_tempo.png"), dpi=130)
    plt.close(fig)

    # 2. largura da faixa de 90% por componente
    fig, ax = plt.subplots(figsize=(8, 4))
    cores = ["#bdc3c7", "#f5b041", "#af7ac5", COR_A]
    for (nome, _), c in zip(CAMADAS, cores):
        g = lar[lar["camada"] == nome]
        ax.plot(g["pct"], g["largura"], color=c, lw=2, marker="o", ms=3, label=nome)
    ax.set_ylabel("largura do intervalo de 90% (pontos)")
    ax.set_title("Quanto cada componente alarga a faixa", fontsize=11, loc="left")
    ax.legend(fontsize=8, frameon=False)
    eixo(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "2_largura_componentes.png"), dpi=130)
    plt.close(fig)

    # 3. estimativa da linha Outros
    fig, ax = plt.subplots(figsize=(8, 4))
    for k, c, nome in [("oA", COR_A, "Outros → A"), ("oB", COR_B, "Outros → B")]:
        ax.fill_between(x, 100 * tab[f"{k}_p05"], 100 * tab[f"{k}_p95"], color=c, alpha=0.18)
        ax.plot(x, 100 * tab[k], color=c, lw=2, label=nome + " (estimado)")
    leg = modelo.parametros_legiveis(VERDADE)
    ax.axhline(100 * leg[3], color=COR_A, ls="--", lw=1, label="verdadeiro")
    ax.axhline(100 * leg[4], color=COR_B, ls="--", lw=1)
    ax.set_ylabel("% dos eleitores de Outros")
    ax.set_title("A matriz sai da priori e vai para o valor verdadeiro", fontsize=11, loc="left")
    ax.legend(fontsize=8, frameon=False, ncol=2)
    eixo(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "3_matriz_outros.png"), dpi=130)
    plt.close(fig)

    # 4. UFs: faixa e % apurado
    fig, axs = plt.subplots(2, 2, figsize=(8, 5.5), sharex=True)
    for ax, u in zip(axs.ravel(), ["pr", "sp", "mg", "ce"]):
        ax.fill_between(x, tab[f"{u}_p05"], tab[f"{u}_p95"], color=COR_A, alpha=0.18)
        ax.plot(x, tab[f"{u}_A"], color=COR_A, lw=1.8)
        ax.axhline(tab[f"{u}_real"].iloc[0], color="k", ls="--", lw=1)
        ax.set_title(f"{u.upper()} (real {tab[f'{u}_real'].iloc[0]:.1f}%)", fontsize=10, loc="left")
        eixo(ax)
        ax.set_xlabel("")
        ax2 = ax.twinx()
        ax2.plot(x, tab[f"{u}_ap"], color=CINZA, lw=1, ls=":")
        ax2.set_ylim(0, 100)
        ax2.set_yticks([0, 50, 100])
        ax2.tick_params(labelsize=7, colors=CINZA)
    fig.suptitle("Por UF: faixa de 90% (vermelho) e % da UF apurado (pontilhado, eixo à direita)", fontsize=10)
    fig.supxlabel("% do eleitorado do país apurado", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "4_ufs.png"), dpi=130)
    plt.close(fig)

    # 5. ritmo da apuração e índice P
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(x, tab["P"], color="#8e44ad", lw=2)
    ax.set_ylabel("P")
    ax.set_ylim(0, 1.05)
    ax.set_title("Índice de evidência parcial P (0 = só municípios completos, 1 = só começos)", fontsize=11, loc="left")
    eixo(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "5_indice_parcial.png"), dpi=130)
    plt.close(fig)


def exemplo_municipio(df, inicio, duracao, ts, pct_t):
    """Conta de um município com números redondos, para o texto."""
    M = modelo.matriz(PRIORI)
    x = np.array([0.30, 0.34, 0.14, 0.04, 0.18])
    y = x @ M
    print("\nMunicípio de exemplo: x1 =", x)
    print("M (priori):\n", np.round(M, 3))
    print("y2 = x1 M =", np.round(y, 4), " A nos válidos =", round(100 * y[0] / (y[0] + y[1]), 2))
    Mv = modelo.matriz(VERDADE)
    yv = x @ Mv
    print("y2 verdadeiro =", np.round(yv, 4), " A nos válidos =", round(100 * yv[0] / (yv[0] + yv[1]), 2))


if __name__ == "__main__":
    main()
