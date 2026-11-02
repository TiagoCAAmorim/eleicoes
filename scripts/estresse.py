"""Teste de estresse: roda o modelo em muitas apurações sintéticas (eleicoes/modelos/estresse.py).

Cada rodada sorteia um resultado do 2º turno de 2022 (margem de cada cidade em torno da previsão) e uma ordem de
apuração enviesada para cidades previstas para um dos lados. Em cada ponto da apuração roda cada variante do
modelo e compara com o resultado sintético. Saídas em resultados/estresse/:
  previsoes.csv  uma linha por (rodada, variante, % apurado)
  resumo.csv     cobertura do intervalo de 90% e 50%, erro, largura e CRPS por variante e faixa
  estresse.png   cobertura de 90% por % apurado, uma linha por variante

    python scripts/estresse.py --rodadas 30
    python scripts/estresse.py --rodadas 10 --variantes revisado sem_choques --beta 0.2
"""
import argparse
import dataclasses
import json
import os
from multiprocessing import Pool

import numpy as np
import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import PRIORI, RESULTADOS
from eleicoes.modelos import estresse as es
from eleicoes.modelos import transferencia as modelo
from backtest import carregar, snapshot
from rejogar_2026 import AO_VIVO, crps

PONTOS = [0, 1, 3, 5, 10, 20, 30, 50, 70, 90]
VARIANTES = {
    "ao_vivo": AO_VIVO,
    "sem_choques": {**AO_VIVO, "transicao_centro": None},
    "so_nacional": {**AO_VIVO, "transicao_centro": None, "choque_nacional": 0.01},
    "parcial_leve": {"choque_parcial": 0.0075, "choque_uf_inicio": 0.02},
    "revisado": {},
    "calibrado": {"tau": 0.15, "choque_uf_inicio": 0.02, "sd_outros": 0.3},   # hierarquia e choques de 2006–2022
    # o mesmo, mas com o choque inicial por UF de 4% depois que a apuração começa (2% só antes de abrir)
    "calibrado_cauteloso": {"tau": 0.15, "choque_uf_inicio": 0.04, "choque_uf_inicio_antes": 0.02, "sd_outros": 0.3},
    # matriz v2 (docs/matriz-v2.md), com a priori v2 de 2022 (dados/priori/presidente_2022_v2.json)
    "calibrado_v2": {"tau": 0.15, "choque_uf_inicio": 0.02, "sd_outros": 0.3, "matriz_v2": True},
    "calibrado_cauteloso_v2": {"tau": 0.15, "choque_uf_inicio": 0.04, "choque_uf_inicio_antes": 0.02, "sd_outros": 0.3,
                               "matriz_v2": True},
}
G = None


def _init(par_json):
    global G, PRI, PRI_V2
    base, sec = carregar()
    PRI = json.load(open(os.path.join(PRIORI, "presidente_2022.json")))
    PRI_V2 = json.load(open(os.path.join(PRIORI, "presidente_2022_v2.json")))
    G = es.GeradorApuracao(base, sec, PRI)


def uma_rodada(args):
    rd, variantes, par = args
    rng = np.random.default_rng(5000 + rd)
    s, t, beta, gama = G.rodada(rng, par)
    final = 100 * s["v13"].sum() / (s["v13"].sum() + s["v22"].sum())
    linhas = []
    for p in PONTOS:
        ap = t <= np.percentile(t, p) if p > 0 else np.zeros(len(t), bool)
        df = snapshot(G.base, s, ap)
        parcial = 100 * df["A2"].sum() / max(df["A2"].sum() + df["B2"].sum(), 1)
        d, X, Y = modelo.preparar(df)
        for v in variantes:
            pri = PRI_V2 if VARIANTES[v].get("matriz_v2") else PRI
            cfg = dataclasses.replace(modelo.Config(priori=pri), **VARIANTES[v])
            aj = modelo.ajustar(d, X, Y, cfg)
            sims = modelo.simular(d, X, Y, aj, cfg).sum(1)
            pa = 100 * sims[:, 0] / np.maximum(sims[:, 0] + sims[:, 1], 1)
            q = np.percentile(pa, [5, 25, 75, 95])
            linhas.append({"rodada": rd, "beta": beta, "gama": gama, "variante": v, "pct_secoes": p, "parcial_A": parcial,
                           "media": pa.mean(), "p05": q[0], "p25": q[1], "p75": q[2], "p95": q[3],
                           "prob_A": float((pa > 50).mean()), "final": final, "crps": crps(pa, final)})
    print(f"rodada {rd}: beta {beta:+.2f}, gama {gama:+.2f}, final {final:.2f}", flush=True)
    return linhas


def calibrar():
    """Mede na apuração real de 2026 as grandezas que calibram o gerador."""
    import rejogar_2026 as rj
    base, ret = rj.carregar()
    horas = sorted(ret["hora"].unique())
    pct = ret.groupby("hora")["pct_secoes"].first()
    ult = rj.retrato(base, ret, horas[-1])
    fin = 100 * ult["A2"] / (ult["A2"] + ult["B2"]).clip(lower=1)
    lean = (base["A1"] - base["B1"]) / (base["A1"] + base["B1"]).clip(lower=1)
    print("% apurado | razão de velocidade (cidades pró-B / pró-A) | parciais das cidades - final (pt)")
    for h in horas:
        p = pct[h]
        if not any(abs(p - x) < 1 for x in [2, 5, 10, 20, 30, 50, 70]):
            continue
        d = rj.retrato(base, ret, h)
        f = (d["Ea"] / d["E2"].clip(lower=1)).clip(0, 1).values
        v = (d["A2"] + d["B2"]).values
        razao = es.razao_velocidade(-lean.values, f, d["E2"].values.astype(float))
        sel = (f > 0) & (f < 0.95) & (v > 0)
        dif = (100 * d["A2"] / (d["A2"] + d["B2"]).clip(lower=1) - fin).values
        print(f"{p:6.1f}% | {1 / razao:5.2f} | {np.average(dif[sel], weights=v[sel]):+.2f}")


def resumir(res):
    res = res.copy()
    res["erro"] = res["media"] - res["final"]
    res["cobre90"] = (res["p05"] <= res["final"]) & (res["final"] <= res["p95"])
    res["cobre50"] = (res["p25"] <= res["final"]) & (res["final"] <= res["p75"])
    res["largura90"] = res["p95"] - res["p05"]
    res["errou_lado"] = ((res["prob_A"] >= 0.99) & (res["final"] < 50)) | ((res["prob_A"] <= 0.01) & (res["final"] > 50))
    agg = dict(cobre90=("cobre90", "mean"), cobre50=("cobre50", "mean"), erro_abs=("erro", lambda e: e.abs().mean()),
               largura90=("largura90", "mean"), crps=("crps", "mean"), chamadas_erradas=("errou_lado", "sum"),
               n=("cobre90", "size"))
    por_ponto = res.groupby(["variante", "pct_secoes"]).agg(**agg).reset_index()
    tot = res.groupby("variante").agg(**agg).reset_index().assign(pct_secoes="todos")
    return res, pd.concat([por_ponto, tot], ignore_index=True)


def grafico(res, caminho):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
    cores = ["#8f8b82", "#c0602a", "#2a6fb0", "#2b8a5a", "#7a4fa0"]
    for c, (v, g) in zip(cores, res.groupby("variante", sort=False)):
        r = g.groupby("pct_secoes").agg(c90=("cobre90", "mean"), larg=("largura90", "mean"))
        x = np.sqrt(r.index.values.astype(float))
        axs[0].plot(x, 100 * r["c90"], "o-", color=c, label=v, ms=3)
        axs[1].plot(x, r["larg"], "o-", color=c, label=v, ms=3)
    axs[0].axhline(90, color="#5f5c55", lw=1, ls=":")
    axs[0].set_ylabel("cobertura do intervalo de 90% (%)")
    axs[1].set_ylabel("largura média do intervalo (pt)")
    ticks = [0, 1, 5, 10, 20, 50, 90]
    for ax in axs:
        ax.set_xticks(np.sqrt(ticks), [f"{t}%" for t in ticks])
        ax.set_xlabel("seções apuradas")
        ax.spines[["top", "right"]].set_visible(False)
    axs[0].legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(caminho, dpi=130)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rodadas", type=int, default=30)
    ap.add_argument("--variantes", nargs="+", default=list(VARIANTES))
    ap.add_argument("--beta", type=float, default=None, help="fixa o viés de ordem entre cidades (padrão: sorteado)")
    ap.add_argument("--gama", type=float, default=None, help="fixa o viés de ordem dentro das cidades")
    ap.add_argument("--processos", type=int, default=os.cpu_count())
    ap.add_argument("--saida", default=os.path.join(RESULTADOS, "estresse"))
    ap.add_argument("--so-resumo", action="store_true")
    ap.add_argument("--calibrar", action="store_true", help="mede o viés de ordem da apuração real de 2026")
    a = ap.parse_args()
    if a.calibrar:
        calibrar()
        return
    os.makedirs(a.saida, exist_ok=True)
    if a.so_resumo:
        res = pd.read_csv(os.path.join(a.saida, "previsoes.csv"))
    else:
        par = es.ParamEstresse(beta=a.beta, gama=a.gama)
        with Pool(a.processos, initializer=_init, initargs=(None,)) as pool:
            partes = pool.map(uma_rodada, [(rd, a.variantes, par) for rd in range(a.rodadas)], chunksize=1)
        res = pd.DataFrame([lin for p in partes for lin in p])
        res.round(4).to_csv(os.path.join(a.saida, "previsoes.csv"), index=False)
    res, resumo = resumir(res)
    resumo.round(4).to_csv(os.path.join(a.saida, "resumo.csv"), index=False)
    grafico(res, os.path.join(a.saida, "estresse.png"))
    pd.set_option("display.width", 200)
    print(resumo.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
