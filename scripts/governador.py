"""2º turno de governador com o modelo de transferência (etapa 5 do roteiro).

Os 2º turnos de governador de 2006 a 2022 (56 fora o DF, que tem um município só) servem de base:

1. Ajusta a matriz de cada 2º turno com a apuração completa (A = o mais votado no 1º turno entre os dois do 2º).
2. Priori de cada eleição: média (logit) das matrizes de todos os 2º turnos de governador de anos anteriores, de
   qualquer UF. Ao contrário do presidente, os candidatos mudam de UF para UF, então só a média geral faz sentido.
3. Antes da apuração e durante um rejogo por município (mesma ordem sintética de scripts/calibrar_priori.py), mede
   erro, largura e cobertura do intervalo de 90% para algumas variantes de incerteza.

    python scripts/governador.py --rodadas 2
Saídas em resultados/governador/.
"""
import argparse
import dataclasses
import json
import os

import numpy as np
import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import RESULTADOS
from eleicoes.dados import historico as hist
from eleicoes.modelos import transferencia as modelo
from calibrar_priori import COLS, ordem_municipios, retrato, vazio
from rejogar_2026 import crps

OUT = os.path.join(RESULTADOS, "governador")
ANOS = [2006, 2010, 2014, 2018, 2022]
PONTOS = [0, 1, 3, 5, 10, 20, 30, 50, 70, 90]
BASE_CFG = {"tau": 0.15, "choque_nacional": 0.0}   # numa UF só, o choque "por UF" já é o comum a toda a eleição
VARIANTES = {
    "sem_priori": {},                                              # ponto de partida genérico, desvio 1,5
    "media": {"sd_priori_informativa": 0.7},
    "media_outros_1": {"sd_priori_informativa": 0.7, "sd_outros": 1.0},
    "media_outros_1_uf6": {"sd_priori_informativa": 0.7, "sd_outros": 1.0, "choque_uf_inicio": 0.06},
    # com o choque comum do que falta apurar (1%, como no presidente)
    "media_outros_1_uf6_nac": {"sd_priori_informativa": 0.7, "sd_outros": 1.0, "choque_uf_inicio": 0.06,
                               "choque_nacional": 0.01},
    # viés da evidência parcial maior (3%): numa UF só, o viés das primeiras seções não se dilui entre UFs
    "media_outros_1_uf6_p3": {"sd_priori_informativa": 0.7, "sd_outros": 1.0, "choque_uf_inicio": 0.06,
                              "choque_parcial": 0.03},
    "media_p3": {"sd_priori_informativa": 0.7, "choque_parcial": 0.03},
}


def pa(x):
    return 100 * x["A2"].sum() / max(x["A2"].sum() + x["B2"].sum(), 1)


def ajustar_completo(base):
    df, X, Y = modelo.preparar(base[COLS])
    aj = modelo.ajustar(df, X, Y, modelo.Config(**BASE_CFG))
    return aj.grupos[("brasil", "Brasil")][0]


def config(variante, matrizes, ano):
    anteriores = [th for (a, _), th in matrizes.items() if a < ano]
    mud = {**BASE_CFG, **VARIANTES[variante]}
    if variante == "sem_priori" or not anteriores:
        return modelo.Config(**mud)
    media = np.mean(anteriores, axis=0)
    return modelo.Config(priori={"brasil|Brasil": [float(x) for x in media]}, **mud)


def prever(s, cfg):
    df, X, Y = modelo.preparar(s[COLS])
    aj = modelo.ajustar(df, X, Y, cfg)
    sims = modelo.simular(df, X, Y, aj, cfg).sum(1)
    p = 100 * sims[:, 0] / np.maximum(sims[:, 0] + sims[:, 1], 1)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rodadas", type=int, default=2, help="rejogos por eleição (0 = só antes da apuração)")
    ap.add_argument("--variantes", nargs="+", default=list(VARIANTES))
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    bases, nomes, matrizes = {}, {}, {}
    for ano in ANOS:
        for uf in hist.segundos_turnos(ano, 3):
            if uf == "df":
                continue
            b, n = hist.segundo_turno_governador(ano, uf)
            bases[(ano, uf)], nomes[(ano, uf)] = b, n
            matrizes[(ano, uf)] = ajustar_completo(b)
            leg = modelo.parametros_legiveis(matrizes[(ano, uf)]) * 100
            print(ano, uf, n["A"], "x", n["B"], f"{pa(b):.1f}", np.round(leg, 0).tolist(), flush=True)
    with open(os.path.join(OUT, "matrizes.json"), "w", encoding="utf-8") as f:
        json.dump({f"{a}|{u}": {**nomes[(a, u)], "A_validos": round(pa(bases[(a, u)]), 2),
                                "theta": [round(float(x), 4) for x in th],
                                "legivel": dict(zip(modelo.PAR_NOMES, np.round(modelo.parametros_legiveis(th) * 100, 1).tolist()))}
                   for (a, u), th in matrizes.items()}, f, ensure_ascii=False, indent=1)

    linhas = []
    for (ano, uf), base in bases.items():
        if ano == ANOS[0]:
            continue
        real = pa(base)
        cfgs = {v: config(v, matrizes, ano) for v in a.variantes}
        ordens = [None] + [ordem_municipios(base, np.random.default_rng(1000 * ano + rd + 31 * ord(uf[0]) + ord(uf[1])))
                           for rd in range(a.rodadas)]
        for rd, ordem in enumerate(ordens):
            pontos = [0] if ordem is None else PONTOS[1:]
            if ordem is not None:
                inicio, duracao, vies = ordem
                ts = np.linspace(0, 2, 2001)
                pct = np.array([100 * (np.clip((t - inicio) / duracao, 0, 1) * base["E2"]).sum() / base["E2"].sum()
                                for t in ts])
            for p in pontos:
                s = vazio(base) if p == 0 else retrato(base, inicio, duracao, vies, ts[min(np.searchsorted(pct, p), len(ts) - 1)])
                for v in a.variantes:
                    x = prever(s, cfgs[v])
                    q = np.percentile(x, [5, 25, 75, 95])
                    linhas.append({"ano": ano, "uf": uf, "rodada": rd, "pct": p, "variante": v, "media": x.mean(),
                                   "p05": q[0], "p25": q[1], "p75": q[2], "p95": q[3], "prob_A": (x > 50).mean(),
                                   "real": real, "crps": crps(x, real)})
        b = [l for l in linhas if l["ano"] == ano and l["uf"] == uf and l["pct"] == 0]
        print(ano, uf, f"real {real:.1f}", " | ".join(f"{l['variante']} {l['media']:.1f} [{l['p05']:.1f}, {l['p95']:.1f}]"
                                                       for l in b), flush=True)
    res = pd.DataFrame(linhas)
    res["erro"] = res["media"] - res["real"]
    res["cobre90"] = (res["p05"] <= res["real"]) & (res["real"] <= res["p95"])
    res["cobre50"] = (res["p25"] <= res["real"]) & (res["real"] <= res["p75"])
    res["largura90"] = res["p95"] - res["p05"]
    res["errou_lado"] = ((res["prob_A"] >= 0.99) & (res["real"] < 50)) | ((res["prob_A"] <= 0.01) & (res["real"] > 50))
    res.round(4).to_csv(os.path.join(OUT, "previsoes.csv"), index=False)
    agg = dict(erro_abs=("erro", lambda e: e.abs().mean()), cobre90=("cobre90", "mean"), cobre50=("cobre50", "mean"),
               largura90=("largura90", "mean"), crps=("crps", "mean"), chamadas_erradas=("errou_lado", "sum"),
               n=("erro", "size"))
    resumo = res.groupby(["variante", "pct"]).agg(**agg).reset_index()
    resumo.round(4).to_csv(os.path.join(OUT, "resumo.csv"), index=False)
    pd.set_option("display.width", 200)
    print(resumo.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
