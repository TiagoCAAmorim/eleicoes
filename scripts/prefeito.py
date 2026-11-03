"""2º turno de prefeito com o modelo de transferência por seção (etapa 5 do roteiro).

Numa cidade não há municípios para comparar: a unidade passa a ser a seção eleitoral, e o 1º turno de cada seção
vai para o 2º pela matriz da cidade. Base: dados/historico/<ano>/prefeito_secoes.csv.gz (scripts/tse_secoes_prefeito.py),
2008–2024, cidades com 2º turno.

1. Ajusta a matriz de cada cidade com a apuração completa (A = o mais votado no 1º turno entre os dois do 2º).
2. Priori de cada eleição: média (logit) das matrizes de todas as cidades de anos anteriores. 2008 fica fora.
3. Rejogo: as seções chegam por zona (cada zona começa num instante sorteado) e, dentro da zona, em ordem sorteada;
   um viés sorteado por rejogo faz as seções mais favoráveis a A (ou a B) chegarem antes. Como as seções chegam
   inteiras, o viés das primeiras seções aparece pela ordem, e não dentro da unidade como no presidente.

    python scripts/prefeito.py --rodadas 2
Saídas em resultados/prefeito/.
"""
import argparse
import json
import os

import numpy as np
import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import DADOS, RESULTADOS
from eleicoes.modelos import transferencia as modelo
from rejogar_2026 import crps

OUT = os.path.join(RESULTADOS, "prefeito")
ANOS = [2008, 2012, 2016, 2020, 2024]
PONTOS = [0, 1, 3, 5, 10, 20, 30, 50, 70, 90]
COLS = ["uf", "mun", "nome", "capital", "zona", "E1", "A1", "B1", "O1", "W1", "E2", "Ea", "A2", "B2", "W2", "C2"]
BASE_CFG = {"tau": 0.15, "choque_nacional": 0.0, "niveis": [], "n_sims": 400}
VARIANTES = {
    "sem_priori": {},
    "media": {"sd_priori_informativa": 0.7},
    "media_p3": {"sd_priori_informativa": 0.7, "choque_parcial": 0.03},
    "media_zona": {"sd_priori_informativa": 0.7, "niveis": ["zona"]},
    "media_uf6": {"sd_priori_informativa": 0.7, "choque_uf_inicio": 0.06},
    "media_uf8": {"sd_priori_informativa": 0.7, "choque_uf_inicio": 0.08},
    "media_uf12": {"sd_priori_informativa": 0.7, "choque_uf_inicio": 0.12},
    # choque comum do que falta apurar que não encolhe com o % apurado: as seções que ficam por último podem ser
    # todas de um mesmo lado da cidade (zonas inteiras chegam juntas)
    "media_c4": {"sd_priori_informativa": 0.7, "choque_uf": 0.04},
    "media_c6": {"sd_priori_informativa": 0.7, "choque_uf": 0.06},
    "media_c8": {"sd_priori_informativa": 0.7, "choque_uf": 0.08},
    "media_c6_uf8": {"sd_priori_informativa": 0.7, "choque_uf": 0.06, "choque_uf_inicio": 0.08},
}


def carregar(ano):
    caminho = os.path.join(DADOS, "historico", str(ano), "prefeito_secoes.csv.gz")
    if not os.path.exists(caminho):
        return {}
    s = pd.read_csv(caminho, dtype={"mun": str})
    info = json.load(open(caminho.replace(".csv.gz", ".json"), encoding="utf-8"))["cidades"]
    bases = {}
    for mun, g in s.groupby("mun"):
        g = g[(g["E1"] > 0) & (g["E2"] > 0)]          # sem aptos no detalhe ou seção só de um turno
        if len(g) < 30 or g["A2"].sum() + g["B2"].sum() == 0:
            continue
        b = pd.DataFrame({
            "uf": g["uf"].str.lower(), "mun": g["zona"].astype(str) + "-" + g["secao"].astype(str), "nome": mun,
            "capital": 0, "zona": g["zona"].astype(str),
            "E1": g["E1"], "A1": g["A1"], "B1": g["B1"], "O1": g["O1"], "W1": g["W1"],
            "E2": g["E2"], "Ea": g["E2"], "A2": g["A2"], "B2": g["B2"], "W2": g["W2"], "C2": g["C2"]})
        b[["E1", "E2", "Ea"]] = np.maximum(b[["E1", "E2", "Ea"]].values,
                                          np.column_stack([b[["A1", "B1", "O1", "W1"]].sum(1),
                                                           b[["A2", "B2", "W2"]].sum(1),
                                                           b[["A2", "B2", "W2"]].sum(1)]))
        b["C2"] = np.maximum(b["C2"], b[["A2", "B2", "W2"]].sum(1))
        bases[mun.lstrip("0")] = (b.reset_index(drop=True), info.get(mun.lstrip("0"), info.get(mun, {})))
    return bases


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
    return modelo.Config(priori={"brasil|Brasil": [float(x) for x in np.mean(anteriores, axis=0)]}, **mud)


def ordem_secoes(base, rng, vies_sd=0.3):
    """Instante de chegada de cada seção: início da zona + posição na zona, deslocado pelo viés (em desvios da
    fração de A na seção)."""
    zonas, zi = np.unique(base["zona"].values, return_inverse=True)
    t = 0.6 * rng.uniform(size=len(zonas))[zi] + 0.4 * rng.uniform(size=len(base))
    v = base["A2"] / (base["A2"] + base["B2"]).clip(lower=1)
    z = ((v - v.mean()) / max(v.std(), 1e-6)).values
    return t - rng.normal(0, vies_sd) * z


def retrato(base, chegada, p):
    """Seções que chegaram até o instante em que p% do eleitorado está apurado (seções inteiras)."""
    s = base.copy()
    if p <= 0:
        s[["Ea", "A2", "B2", "W2", "C2"]] = 0
        return s
    o = np.argsort(chegada)
    acum = 100 * np.cumsum(base["E2"].values[o]) / base["E2"].sum()
    fora = o[np.searchsorted(acum, p) + 1:]
    s.loc[fora, ["Ea", "A2", "B2", "W2", "C2"]] = 0
    return s


def prever(s, cfg):
    df, X, Y = modelo.preparar(s[COLS])
    aj = modelo.ajustar(df, X, Y, cfg)
    sims = modelo.simular(df, X, Y, aj, cfg).sum(1)
    return 100 * sims[:, 0] / np.maximum(sims[:, 0] + sims[:, 1], 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rodadas", type=int, default=2, help="rejogos por cidade (0 = só antes da apuração)")
    ap.add_argument("--variantes", nargs="+", default=list(VARIANTES))
    ap.add_argument("--anos", nargs="+", type=int, default=ANOS[1:])
    ap.add_argument("--saida", default="")
    ap.add_argument("--vies", type=float, default=0.3, help="desvio do viés de ordem do rejogo")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    bases, matrizes = {}, {}
    for ano in ANOS:
        for mun, (b, inf) in carregar(ano).items():
            bases[(ano, mun)] = (b, inf)
            matrizes[(ano, mun)] = ajustar_completo(b)
        print(ano, sum(1 for k in bases if k[0] == ano), "cidades", flush=True)
    with open(os.path.join(OUT, "matrizes.json"), "w", encoding="utf-8") as f:
        json.dump({f"{a_}|{m}": {"uf": bases[(a_, m)][0]["uf"].iloc[0], "secoes": len(bases[(a_, m)][0]),
                                 "A_validos": round(pa(bases[(a_, m)][0]), 2), "theta": [round(float(x), 4) for x in th],
                                 "legivel": dict(zip(modelo.PAR_NOMES,
                                                     np.round(modelo.parametros_legiveis(th) * 100, 1).tolist()))}
                   for (a_, m), th in matrizes.items()}, f, ensure_ascii=False, indent=1)

    linhas = []
    for (ano, mun), (base, _) in bases.items():
        if ano not in a.anos:
            continue
        real = pa(base)
        cfgs = {v: config(v, matrizes, ano) for v in a.variantes}
        semente = 1000 * ano + int(mun) % 997
        ordens = [None] + [ordem_secoes(base, np.random.default_rng(semente + rd), a.vies) for rd in range(a.rodadas)]
        for rd, chegada in enumerate(ordens):
            for p in ([0] if chegada is None else PONTOS[1:]):
                s = retrato(base, chegada, p)
                for v in a.variantes:
                    x = prever(s, cfgs[v])
                    q = np.percentile(x, [5, 25, 75, 95])
                    linhas.append({"ano": ano, "mun": mun, "uf": base["uf"].iloc[0], "secoes": len(base),
                                   "rodada": rd, "pct": p, "variante": v, "media": x.mean(), "p05": q[0],
                                   "p25": q[1], "p75": q[2], "p95": q[3], "prob_A": (x > 50).mean(), "real": real,
                                   "crps": crps(x, real)})
        b = [l for l in linhas if l["ano"] == ano and l["mun"] == mun and l["pct"] in (0, 10)]
        print(ano, mun, f"real {real:.1f}", " | ".join(f"{l['pct']}% {l['variante']} {l['media']:.1f} "
                                                       f"[{l['p05']:.1f}, {l['p95']:.1f}]" for l in b), flush=True)
    res = pd.DataFrame(linhas)
    res["erro"] = res["media"] - res["real"]
    res["cobre90"] = (res["p05"] <= res["real"]) & (res["real"] <= res["p95"])
    res["cobre50"] = (res["p25"] <= res["real"]) & (res["real"] <= res["p75"])
    res["largura90"] = res["p95"] - res["p05"]
    res["errou_lado"] = ((res["prob_A"] >= 0.99) & (res["real"] < 50)) | ((res["prob_A"] <= 0.01) & (res["real"] > 50))
    sufixo = f"_{a.saida}" if a.saida else ""
    res.round(4).to_csv(os.path.join(OUT, f"previsoes{sufixo}.csv"), index=False)
    agg = dict(erro_abs=("erro", lambda e: e.abs().mean()), cobre90=("cobre90", "mean"), cobre50=("cobre50", "mean"),
               largura90=("largura90", "mean"), crps=("crps", "mean"), chamadas_erradas=("errou_lado", "sum"),
               n=("erro", "size"))
    resumo = res.groupby(["variante", "pct"]).agg(**agg).reset_index()
    resumo.round(4).to_csv(os.path.join(OUT, f"resumo{sufixo}.csv"), index=False)
    pd.set_option("display.width", 200)
    print(resumo.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
