"""Leitura da base histórica do TSE (dados/historico/<ano>/, gerada por scripts/tse_historico.py)."""
import os

import pandas as pd

from ..caminhos import COMUM, DADOS
from .geo import REGIAO

HIST = os.path.join(DADOS, "historico")
ANOS_PRESIDENTE = [2006, 2010, 2014, 2018, 2022]


def _ler(ano, nome):
    df = pd.read_csv(os.path.join(HIST, str(ano), nome), dtype={"mun": str, "numero": str, "turno": int, "cargo": int})
    df["mun"] = df["mun"].str.zfill(5)   # o código vem com e sem zeros à esquerda conforme o arquivo
    return df


def segundo_turno_presidente(ano, partido_a="PT"):
    """Base no formato do modelo de transferência, com o 2º turno completo.

    A = candidato do `partido_a` no 2º turno (o PT esteve em todos de 2006 a 2022), B = o outro. Colunas: uf, mun,
    nome, capital, E1, A1, B1, O1, W1 (1º turno) e E2, Ea, A2, B2, W2, C2 (2º turno inteiro apurado)."""
    v = _ler(ano, "votos_mun.csv.gz")
    v = v[v["cargo"] == 1]
    c = _ler(ano, "comparecimento_mun.csv.gz")
    c = c[c["cargo"] == 1]
    t2 = v[v["turno"] == 2]
    tot = t2.groupby(["numero", "partido"])["votos"].sum().sort_values(ascending=False)
    if len(tot) != 2:
        raise ValueError(f"{ano}: 2º turno com {len(tot)} candidatos")
    num_a = next((n for n, p in tot.index if p == partido_a), None)
    if num_a is None:
        raise ValueError(f"{ano}: {partido_a} não está no 2º turno")
    num_b = next(n for n, _ in tot.index if n != num_a)

    def votos(turno, num):
        x = v[(v["turno"] == turno) & (v["numero"] == num)]
        return x.groupby("mun")["votos"].sum()

    t1v = v[v["turno"] == 1].groupby("mun")["votos"].sum()
    c1 = c[c["turno"] == 1].set_index("mun")
    c2 = c[c["turno"] == 2].set_index("mun")
    base = c1[["uf", "mun_nome"]].rename(columns={"mun_nome": "nome"}).copy()
    base["uf"] = base["uf"].str.lower()
    base["E1"] = c1["aptos"]
    base["A1"] = votos(1, num_a).reindex(base.index).fillna(0)
    base["B1"] = votos(1, num_b).reindex(base.index).fillna(0)
    base["O1"] = (t1v.reindex(base.index).fillna(0) - base["A1"] - base["B1"]).clip(lower=0)
    base["W1"] = c1["brancos"] + c1["nulos"]
    base["E2"] = c2["aptos"].reindex(base.index)
    base["A2"] = votos(2, num_a).reindex(base.index).fillna(0)
    base["B2"] = votos(2, num_b).reindex(base.index).fillna(0)
    base["W2"] = (c2["brancos"] + c2["nulos"]).reindex(base.index)
    base["C2"] = c2["comparecimento"].reindex(base.index)
    # "vt" (voto em trânsito, 2010: 27 linhas, 53 mil votos) não tem município de origem: fica de fora
    base = base[base["uf"].isin(REGIAO)].dropna(subset=["E2"]).reset_index()
    mun = pd.read_csv(os.path.join(COMUM, "municipios.csv"), dtype={"mun": str})
    cap = set(mun.loc[mun["capital"], "mun"])
    base["capital"] = base["mun"].isin(cap)
    base["Ea"] = base["E2"]
    for col in ["E1", "A1", "B1", "O1", "W1", "E2", "Ea", "A2", "B2", "W2", "C2"]:
        base[col] = base[col].astype(float)
    nomes = t2.drop_duplicates("numero").set_index("numero")["nome"]
    return base, {"A": nomes[num_a], "B": nomes[num_b]}


def _base_segundo_turno(v, c, num_a, num_b):
    """Monta a base do modelo (municípios) a partir dos votos (v) e do comparecimento (c) de um cargo."""
    t1v = v[v["turno"] == 1].groupby("mun")["votos"].sum()

    def votos(turno, num):
        x = v[(v["turno"] == turno) & (v["numero"] == num)]
        return x.groupby("mun")["votos"].sum()

    c1 = c[c["turno"] == 1].set_index("mun")
    c2 = c[c["turno"] == 2].set_index("mun")
    base = c1[["uf", "mun_nome"]].rename(columns={"mun_nome": "nome"}).copy()
    base["uf"] = base["uf"].str.lower()
    base["E1"] = c1["aptos"]
    base["A1"] = votos(1, num_a).reindex(base.index).fillna(0)
    base["B1"] = votos(1, num_b).reindex(base.index).fillna(0)
    base["O1"] = (t1v.reindex(base.index).fillna(0) - base["A1"] - base["B1"]).clip(lower=0)
    base["W1"] = c1["brancos"] + c1["nulos"]
    base["E2"] = c2["aptos"].reindex(base.index)
    base["A2"] = votos(2, num_a).reindex(base.index).fillna(0)
    base["B2"] = votos(2, num_b).reindex(base.index).fillna(0)
    base["W2"] = (c2["brancos"] + c2["nulos"]).reindex(base.index)
    base["C2"] = c2["comparecimento"].reindex(base.index)
    base = base[base["uf"].isin(REGIAO)].dropna(subset=["E2"]).reset_index()
    mun = pd.read_csv(os.path.join(COMUM, "municipios.csv"), dtype={"mun": str})
    base["capital"] = base["mun"].isin(set(mun.loc[mun["capital"], "mun"]))
    base["Ea"] = base["E2"]
    for col in ["E1", "A1", "B1", "O1", "W1", "E2", "Ea", "A2", "B2", "W2", "C2"]:
        base[col] = base[col].astype(float)
    return base


def segundos_turnos(ano, cargo=3):
    """UFs com 2º turno do cargo no ano (3 = governador)."""
    v = _ler(ano, "votos_mun.csv.gz")
    return sorted(v.loc[(v["cargo"] == cargo) & (v["turno"] == 2), "uf"].str.lower().unique())


def segundo_turno_governador(ano, uf):
    """Base do 2º turno de governador de uma UF, no mesmo formato de `segundo_turno_presidente`.

    A = quem teve mais votos no 1º turno entre os dois do 2º turno (o "líder"), B = o outro. Devolve também nomes e
    partidos."""
    v = _ler(ano, "votos_mun.csv.gz")
    v = v[(v["cargo"] == 3) & (v["uf"].str.lower() == uf)]
    c = _ler(ano, "comparecimento_mun.csv.gz")
    c = c[(c["cargo"] == 3) & (c["uf"].str.lower() == uf)]
    dois = v[v["turno"] == 2]["numero"].unique()
    if len(dois) != 2:
        raise ValueError(f"{ano} {uf}: 2º turno com {len(dois)} candidatos")
    t1 = v[(v["turno"] == 1) & v["numero"].isin(dois)].groupby("numero")["votos"].sum().sort_values(ascending=False)
    num_a, num_b = t1.index[0], t1.index[1]
    base = _base_segundo_turno(v, c, num_a, num_b)
    info = v[v["turno"] == 2].drop_duplicates("numero").set_index("numero")
    return base, {"A": info.loc[num_a, "nome"], "B": info.loc[num_b, "nome"],
                  "partido_A": info.loc[num_a, "partido"], "partido_B": info.loc[num_b, "partido"]}


CARGOS = {"presidente": 1, "governador": 3, "senador": 5, "prefeito": 11}


def _votos_cargo(ano, cargo, uf=None, turno=1):
    v = _ler(ano, "votos_mun.csv.gz")
    v = v[(v["cargo"] == cargo) & (v["turno"] == turno) & (v["tipo_voto"] == "candidato")]
    c = _ler(ano, "comparecimento_mun.csv.gz")
    c = c[(c["cargo"] == cargo) & (c["turno"] == turno)]
    if uf is not None:
        v, c = v[v["uf"].str.lower() == uf], c[c["uf"].str.lower() == uf]
    return v, c


def primeiro_turno(ano, cargo, uf=None, ref=(None, "presidente"), k_max=5, min_validos=5.0, k_min=3, k_ref=3):
    """Base do 1º turno de `cargo` ("presidente", "governador", "senador", "prefeito") para o modelo do 1º turno
    (eleicoes/modelos/primeiro_turno.py), por município, com a apuração completa.

    Destinos d0..d{K-1} = candidatos nomeados (os de pelo menos `min_validos`% dos válidos, no mínimo `k_min` e no
    máximo `k_max`, em ordem de votos), dK = demais candidatos, d{K+1} = brancos + nulos; C = comparecimento.
    Referência (`ref` = (ano, cargo); ano None = 4 anos antes): r0..r{k_ref-1} = os `k_ref` partidos mais votados no
    1º turno da referência (na UF, se `uf`), r{k_ref} = demais, r{k_ref+1} = brancos + nulos, rE = eleitorado.
    Municípios sem referência (criados depois) recebem a média da UF. `ref=None`: sem referência.
    Devolve (base, info) com nomes, partidos e o resultado (% dos válidos) de cada candidato nomeado."""
    v, c = _votos_cargo(ano, CARGOS[cargo], uf)
    tot = v.groupby(["numero"])["votos"].sum().sort_values(ascending=False)
    pct = 100 * tot / tot.sum()
    k = int(min(k_max, max(k_min, (pct >= min_validos).sum()), len(tot)))
    nomeados = list(tot.index[:k])
    info_c = v.drop_duplicates("numero").set_index("numero")
    c = c.set_index("mun")
    base = c[["uf", "mun_nome"]].rename(columns={"mun_nome": "nome"}).copy()
    base["uf"] = base["uf"].str.lower()
    base["E"] = c["aptos"].astype(float)
    pv = v.pivot_table(index="mun", columns="numero", values="votos", aggfunc="sum", fill_value=0)
    for i, n in enumerate(nomeados):
        base[f"d{i}"] = pv[n].reindex(base.index).fillna(0).astype(float)
    base[f"d{k}"] = (pv.sum(1).reindex(base.index).fillna(0) - base[[f"d{i}" for i in range(k)]].sum(1)).clip(lower=0)
    base[f"d{k + 1}"] = (c["brancos"] + c["nulos"]).astype(float)
    base["C"] = c["comparecimento"].astype(float)
    partidos_ref = []
    if ref is not None:
        ano_ref = ref[0] or ano - 4
        rv, rc = _votos_cargo(ano_ref, CARGOS[ref[1]], uf)
        rt = rv.groupby("partido")["votos"].sum().sort_values(ascending=False)
        partidos_ref = list(rt.index[:k_ref])
        rp = rv.pivot_table(index="mun", columns="partido", values="votos", aggfunc="sum", fill_value=0)
        rc = rc.set_index("mun")
        r = pd.DataFrame(index=base.index)
        for i, p in enumerate(partidos_ref):
            r[f"r{i}"] = rp[p].reindex(base.index)
        r[f"r{k_ref}"] = rp.sum(1).reindex(base.index) - r[[f"r{i}" for i in range(k_ref)]].sum(1)
        r[f"r{k_ref + 1}"] = (rc["brancos"] + rc["nulos"]).reindex(base.index)
        r["rE"] = rc["aptos"].reindex(base.index)
        r.loc[r["rE"].notna()] = r.loc[r["rE"].notna()].fillna(0)
        vpe = 2 if r[[f"r{i}" for i in range(k_ref + 2)]].sum().sum() > 1.5 * rc["comparecimento"].sum() else 1
        r[[f"r{i}" for i in range(k_ref + 2)]] /= vpe
        falta = r["rE"].isna()
        if falta.any():
            fr = r.div(r["rE"], axis=0)
            fr["uf"] = base["uf"]
            media = fr[~falta].groupby("uf").mean()
            geral = fr[~falta].drop(columns="uf").mean()
            for col in [f"r{i}" for i in range(k_ref + 2)]:
                r.loc[falta, col] = base.loc[falta, "uf"].map(media[col]).fillna(geral[col]) * base.loc[falta, "E"]
            r.loc[falta, "rE"] = base.loc[falta, "E"]
        base = base.join(r.astype(float))
    base = base[base["uf"].isin(REGIAO)].reset_index()
    mun = pd.read_csv(os.path.join(COMUM, "municipios.csv"), dtype={"mun": str})
    base["capital"] = base["mun"].isin(set(mun.loc[mun["capital"], "mun"]))
    base["Ea"] = base["E"]
    vpe = 2 if tot.sum() + base[f"d{k + 1}"].sum() > 1.5 * base["C"].sum() else 1
    info = {"ano": ano, "cargo": cargo, "uf": uf, "votos_por_eleitor": vpe, "partidos_ref": partidos_ref,
            "candidatos": [{"numero": n, "nome": info_c.loc[n, "nome"], "partido": info_c.loc[n, "partido"],
                            "validos": float(pct[n])} for n in nomeados],
            "demais_validos": float(pct.iloc[k:].sum())}
    return base, info
