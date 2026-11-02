"""Covariáveis municipais: explicam o que a matriz de transferência não explica? (etapa 3 do roteiro)

Para cada 2º turno presidencial de 2006 a 2022, ajusta o modelo com a apuração completa e mede o resíduo de cada
município: fração de A nos válidos real menos a prevista pela matriz do grupo (UF x porte), em logit. Depois
regride o resíduo, dentro de cada grupo (efeito fixo de UF x porte), em covariáveis que o modelo não usa:

  dep_A, dep_B   fração dos votos válidos para deputado federal (1º turno) do partido de A e do de B
  pref_A, pref_B prefeito eleito dois anos antes pelo partido de A / de B (0 ou 1)
  comp_dif       comparecimento do 2º turno menos o do 1º turno (fração do eleitorado; só para diagnóstico,
                 porque só se conhece depois que o município apura)

Se as covariáveis explicam uma boa parte do resíduo, vale colocá-las no modelo; se não, a matriz por grupo já
captura o que elas trazem. Saídas em resultados/covariaveis/.

    python scripts/covariaveis.py
"""
import json
import os

import numpy as np
import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import RESULTADOS
from eleicoes.dados import historico as hist
from eleicoes.modelos import priori as priori_cal
from eleicoes.modelos import transferencia as modelo

PARTIDO_B = {2006: "PSDB", 2010: "PSDB", 2014: "PSDB", 2018: "PSL", 2022: "PL"}
SAIDA = os.path.join(RESULTADOS, "covariaveis")


def _logit(p):
    p = np.clip(p, 1e-3, 1 - 1e-3)
    return np.log(p / (1 - p))


def deputados(ano):
    v = hist._ler(ano, "votos_mun.csv.gz")
    v = v[(v["cargo"] == 6) & (v["turno"] == 1)]
    tot = v.groupby("mun")["votos"].sum()
    out = pd.DataFrame(index=tot.index)
    for nome, p in [("dep_A", "PT"), ("dep_B", PARTIDO_B[ano])]:
        out[nome] = (v[v["partido"] == p].groupby("mun")["votos"].sum().reindex(tot.index).fillna(0) / tot.clip(lower=1))
    return out


def prefeitos(ano):
    """Partido do prefeito eleito na eleição municipal de ano - 2 (turno decisivo de cada município)."""
    try:
        v = hist._ler(ano - 2, "votos_mun.csv.gz")
    except FileNotFoundError:
        return None
    v = v[v["cargo"] == 11]
    v = v[v["turno"] == v.groupby("mun")["turno"].transform("max")]
    venc = v.sort_values("votos").groupby("mun").tail(1).set_index("mun")["partido"]
    return venc


def residuos(ano):
    base, nomes = hist.segundo_turno_presidente(ano)
    df, X, Y = modelo.preparar(base)
    cfg = modelo.Config(priori=priori_cal.carregar(ano), tau=0.15)
    aj = modelo.ajustar(df, X, Y, cfg)
    th = np.array([aj.grupos[k][0] for k in aj.folhas])[aj.folha]
    pred = np.einsum("uk,ukd->ud", X, modelo.matriz(th))
    pa = pred[:, 0] / np.maximum(pred[:, 0] + pred[:, 1], 1e-9)
    real = base["A2"] / (base["A2"] + base["B2"]).clip(lower=1)
    out = pd.DataFrame({"uf": base["uf"], "mun": base["mun"], "grupo": df["uf_porte"], "E2": base["E2"],
                        "residuo": _logit(real.values) - _logit(pa)})
    # comparecimento do 1º turno = votos (A1+B1+O1+W1) / eleitorado
    out["comp_dif"] = base["C2"] / base["E2"].clip(lower=1) - base[["A1", "B1", "O1", "W1"]].sum(axis=1) / base["E1"].clip(lower=1)
    return out[base["uf"] != "zz"].set_index("mun")


def regressao(d, cols):
    """Mínimos quadrados ponderados pelo eleitorado, com efeito fixo do grupo (desvios da média do grupo)."""
    w = d["E2"].values
    Z = d[["residuo"] + cols].copy()
    medias = Z.mul(w, axis=0).groupby(d["grupo"]).transform("sum").div(
        pd.Series(w, index=d.index).groupby(d["grupo"]).transform("sum"), axis=0)
    Z = Z - medias
    y, Xc = Z["residuo"].values, Z[cols].values
    sw = np.sqrt(w)
    coef, *_ = np.linalg.lstsq(Xc * sw[:, None], y * sw, rcond=None)
    res = y - Xc @ coef
    r2 = 1 - (w * res ** 2).sum() / (w * y ** 2).sum()
    # desvio do resíduo (logit) antes e depois, ponderado pelo eleitorado
    sd0 = np.sqrt((w * y ** 2).sum() / w.sum())
    sd1 = np.sqrt((w * res ** 2).sum() / w.sum())
    return dict(zip(cols, coef)), r2, sd0, sd1


def main():
    os.makedirs(SAIDA, exist_ok=True)
    linhas, coefs = [], []
    for ano in hist.ANOS_PRESIDENTE:
        d = residuos(ano).join(deputados(ano), how="left")
        pref = prefeitos(ano)
        modelos = {"deputados": ["dep_A", "dep_B"], "comparecimento": ["comp_dif"]}
        if pref is not None:
            d["pref_A"] = (pref.reindex(d.index) == "PT").astype(float)
            d["pref_B"] = (pref.reindex(d.index) == PARTIDO_B[ano]).astype(float)
            modelos["prefeitos"] = ["pref_A", "pref_B"]
            modelos["deputados+prefeitos"] = ["dep_A", "dep_B", "pref_A", "pref_B"]
        d = d.dropna(subset=["dep_A", "dep_B"])
        for nome, cols in modelos.items():
            c, r2, sd0, sd1 = regressao(d, cols)
            linhas.append({"ano": ano, "modelo": nome, "r2": r2, "sd_residuo": sd0, "sd_depois": sd1, "municipios": len(d)})
            coefs += [{"ano": ano, "modelo": nome, "covariavel": k, "coef": v} for k, v in c.items()]
        print(ano, {m: round(l["r2"], 3) for m, l in zip(modelos, linhas[-len(modelos):])}, flush=True)
    res = pd.DataFrame(linhas)
    cf = pd.DataFrame(coefs)
    res.round(4).to_csv(os.path.join(SAIDA, "r2.csv"), index=False)
    cf.round(4).to_csv(os.path.join(SAIDA, "coeficientes.csv"), index=False)
    pd.set_option("display.width", 200)
    print(res.round(3).to_string(index=False))
    print(cf.pivot_table(index=["modelo", "covariavel"], columns="ano", values="coef").round(2).to_string())


if __name__ == "__main__":
    main()
