"""Backtest com a eleição de 2022 (Lula x Bolsonaro).

Usa o 1º turno de 2022 por município como base e simula a apuração do 2º turno
seção a seção, em diferentes ordens de apuração. Em cada ponto da apuração roda
o modelo e compara a previsão com o resultado final real.

    python scripts/backtest.py                 # todas as ordens, gera resultados/backtest/
    python scripts/backtest.py --ordens 2022 --rodadas 1
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import COMUM, RESULTADOS, dados
from eleicoes.dados.geo import REGIAO
from eleicoes.modelos import transferencia as modelo
PONTOS = [0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99]


def carregar():
    t1 = pd.read_csv(dados(2022, "presidente", "mun_t1.csv.gz"), dtype={"mun": str})
    sec = pd.read_csv(dados(2022, "presidente", "secoes_t2.csv.gz"), dtype={"mun": str})
    # versão antiga do arquivo somava aptos/comparecimento em dobro (CSV _BR + CSVs por UF)
    if (sec["comp"] == 2 * sec[["v13", "v22", "brancos", "nulos"]].sum(axis=1)).mean() > 0.99:
        sec[["aptos", "comp"]] //= 2
        t1[["aptos", "comp"]] //= 2
    mun = pd.read_csv(os.path.join(COMUM, "municipios.csv"), dtype={"mun": str, "cdi": str})
    t1 = t1.merge(mun[["uf", "mun", "capital"]], on=["uf", "mun"], how="left")
    t1["capital"] = t1["capital"].fillna(False).astype(bool)
    base = pd.DataFrame({
        "uf": t1["uf"], "mun": t1["mun"], "nome": t1["nome"], "capital": t1["capital"],
        "E1": t1["aptos"], "A1": t1["v13"], "B1": t1["v22"], "O1": t1["outros"], "W1": t1["brancos"] + t1["nulos"],
    })
    return base, sec


def ordem(sec, base, tipo, rng):
    """Instante (0-1) em que cada seção é apurada."""
    n = len(sec)
    if tipo == "aleatoria":
        return rng.random(n)
    reg = sec["uf"].map(REGIAO)
    cap = sec["mun"].map(base.set_index("mun")["capital"]).fillna(False).values
    if tipo == "2022":
        # Sul/Sudeste/Centro-Oeste e interior apuram antes; Nordeste, Norte, capitais e exterior depois
        atraso = reg.map({"Sul": 0.0, "Centro-Oeste": 0.05, "Sudeste": 0.12, "Norte": 0.25, "Nordeste": 0.3,
                          "Exterior": 0.7}).values
        zona = sec.groupby(["uf", "zona"]).ngroup().values
        efeito_zona = rng.normal(0, 0.12, zona.max() + 1)[zona]
        return atraso + 0.15 * cap + efeito_zona + rng.normal(0, 0.15, n)
    if tipo == "adversa":
        # ordem correlacionada com o voto: seções mais pró-B apuram antes (pior caso)
        pb = sec["v22"] / (sec["v13"] + sec["v22"]).clip(lower=1)
        return -pb.values + rng.normal(0, 0.25, n)
    raise ValueError(tipo)


def snapshot(base, sec, apurada):
    s = sec.assign(ap=apurada)
    tot = s.groupby(["uf", "mun"], as_index=False)["aptos"].sum().rename(columns={"aptos": "E2"})
    a = s[s["ap"]].groupby(["uf", "mun"], as_index=False)[["aptos", "comp", "v13", "v22", "brancos", "nulos"]].sum()
    df = base.merge(tot, on=["uf", "mun"], how="left").merge(a, on=["uf", "mun"], how="left").fillna(0)
    df["Ea"] = df["aptos"]
    df["A2"], df["B2"], df["W2"], df["C2"] = df["v13"], df["v22"], df["brancos"] + df["nulos"], df["comp"]
    return df


def rodar(cfg, ordens, rodadas, pontos=PONTOS, verbose=True):
    base, sec = carregar()
    final_a = 100 * sec["v13"].sum() / (sec["v13"].sum() + sec["v22"].sum())
    linhas = []
    for tipo in ordens:
        for rd in range(rodadas):
            rng = np.random.default_rng(1000 + rd)
            t = ordem(sec, base, tipo, rng)
            limites = np.percentile(t, pontos)
            for p, lim in zip(pontos, limites):
                ap = t <= lim
                df = snapshot(base, sec, ap)
                t0 = time.time()
                df, X, Y = modelo.preparar(df)
                aj = modelo.ajustar(df, X, Y, cfg)
                sims = modelo.simular(df, X, Y, aj, cfg)
                r = modelo.resumo_grupo(sims.sum(1))
                parcial = 100 * df["A2"].sum() / max(df["A2"].sum() + df["B2"].sum(), 1)
                linhas.append({"ordem": tipo, "rodada": rd, "pct_secoes": p, "parcial_A": parcial, **r,
                               "real_A": final_a, "erro": r["A_media"] - final_a,
                               "cobre90": r["A_p05"] <= final_a <= r["A_p95"], "segundos": time.time() - t0})
                if verbose:
                    print(f"{tipo:9s} r{rd} {p:5.1f}%  parcial {parcial:5.2f}  prev {r['A_media']:5.2f} "
                          f"[{r['A_p05']:5.2f}, {r['A_p95']:5.2f}]  P(A)={r['prob_A']:.2f}  real {final_a:.2f}"
                          f"  ({time.time() - t0:.1f}s)", flush=True)
    return pd.DataFrame(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ordens", nargs="+", default=["aleatoria", "2022", "adversa"])
    ap.add_argument("--rodadas", type=int, default=2)
    ap.add_argument("--saida", default=os.path.join(RESULTADOS, "backtest"))
    a = ap.parse_args()
    cfg = modelo.Config()
    res = rodar(cfg, a.ordens, a.rodadas)
    os.makedirs(a.saida, exist_ok=True)
    res.to_csv(os.path.join(a.saida, "backtest_2022.csv"), index=False)
    resumo = res.groupby("ordem").agg(erro_medio_abs=("erro", lambda e: e.abs().mean()), cobertura90=("cobre90", "mean"))
    print(resumo)
    from eleicoes.site.painel import grafico_backtest
    grafico_backtest(res, os.path.join(a.saida, "backtest_2022.png"))
    with open(os.path.join(a.saida, "resumo.json"), "w") as f:
        json.dump(resumo.reset_index().to_dict("records"), f, indent=1)


if __name__ == "__main__":
    main()
