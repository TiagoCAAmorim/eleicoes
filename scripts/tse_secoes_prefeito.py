"""1º e 2º turno de prefeito por seção, nas cidades que tiveram 2º turno (2008–2024), para o modelo de transferência
aplicado dentro de uma cidade (etapa 5 do roteiro).

Roda no GitHub Actions (workflow `secoes`), porque o ambiente de desenvolvimento não acessa o TSE. As cidades com
2º turno vêm de dados/historico/<ano>/votos_mun.csv.gz. Grava, em dados/historico/<ano>/:

  prefeito_secoes.csv.gz  uma linha por seção: uf, mun, zona, secao, E1, C1, A1, B1, O1, W1, E2, C2, A2, B2, W2
                          (E = aptos, C = comparecimento, W = brancos + nulos; A = o mais votado no 1º turno entre os
                          dois do 2º, B = o outro, O = os demais candidatos)
  prefeito_secoes.json    candidatos de cada cidade e totais, para conferência

Fontes: votacao_secao_<ano>_<UF>.zip (votos por votável) e detalhe_votacao_secao (aptos, comparecimento, brancos e
nulos por cargo).

    python scripts/tse_secoes_prefeito.py 2024 2020
"""
import argparse
import json
import os

import pandas as pd

import tse_historico as th
from tse_secoes import _remover

ANOS = [2008, 2012, 2016, 2020, 2024]
th.SINONIMOS.setdefault("secao", ["NR_SECAO"])
CHAVE = ["mun", "zona", "secao"]


def cidades(ano, saida):
    v = pd.read_csv(os.path.join(saida, str(ano), "votos_mun.csv.gz"), dtype={"mun": str, "numero": str})
    v = v[v["cargo"] == 11]
    v["mun"] = v["mun"].str.lstrip("0")
    mun2 = set(v.loc[v["turno"] == 2, "mun"])
    return v[v["mun"].isin(mun2)], sorted(v.loc[v["mun"].isin(mun2), "uf"].str.upper().unique())


def _num(d, cols):
    for c in cols:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0).astype("int64")
    return d


def ler_uf(ano, uf, muns, brutos, log):
    def filtro(d):
        d = d[(d["cargo"].str.strip() == "11") & d["mun"].str.strip().str.lstrip("0").isin(muns)]
        return th.ordinaria(d)
    z = th.baixar(f"{th.CDN}/votacao_secao/votacao_secao_{ano}_{uf}.zip", brutos)
    d = th.ler_zip(z, ["turno", "tipo", "tipo_nome", "mun", "zona", "secao", "cargo", "numero", "votos"], filtro, log)
    _remover(z)
    d = d.drop(columns=["tipo", "tipo_nome", "cargo"], errors="ignore")
    d["mun"] = d["mun"].str.strip().str.lstrip("0")
    d["numero"] = d["numero"].str.strip()
    return _num(d, ["turno", "zona", "secao", "votos"])


def detalhe(ano, ufs, muns, brutos, log):
    campos = ["turno", "tipo", "tipo_nome", "mun", "zona", "secao", "cargo", "aptos", "comparecimento", "brancos",
              "nulos"]

    def filtro(d):
        d = d[(d["cargo"].str.strip() == "11") & d["mun"].str.strip().str.lstrip("0").isin(muns)]
        return th.ordinaria(d)
    try:
        z = th.baixar(f"{th.CDN}/detalhe_votacao_secao/detalhe_votacao_secao_{ano}.zip", brutos)
        d = th.ler_zip(z, campos, filtro, log)
        _remover(z)
    except Exception as e:  # noqa: BLE001
        print("detalhe nacional indisponível, lendo por UF:", e, flush=True)
        partes = []
        for uf in ufs:
            z = th.baixar(f"{th.CDN}/detalhe_votacao_secao/detalhe_votacao_secao_{ano}_{uf}.zip", brutos)
            partes.append(th.ler_zip(z, campos, filtro, log))
            _remover(z)
        d = pd.concat(partes, ignore_index=True)
    d = d.drop(columns=["tipo", "tipo_nome", "cargo"], errors="ignore")
    d["mun"] = d["mun"].str.strip().str.lstrip("0")
    d = _num(d, ["turno", "zona", "secao", "aptos", "comparecimento", "brancos", "nulos"])
    return d.groupby(["turno"] + CHAVE, as_index=False)[["aptos", "comparecimento", "brancos", "nulos"]].sum()


def processar(ano, saida, brutos):
    log = {}
    vm, ufs = cidades(ano, saida)
    muns = set(vm["mun"])
    print(ano, len(muns), "cidades com 2º turno em", ufs, flush=True)
    partes = []
    for uf in ufs:
        d = ler_uf(ano, uf, muns, brutos, log)
        print(ano, uf, len(d), "linhas", flush=True)
        partes.append(d.assign(uf=uf.lower()))
    v = pd.concat(partes, ignore_index=True)
    det = detalhe(ano, ufs, muns, brutos, log)
    linhas, info = [], {}
    for mun, g in v.groupby("mun"):
        cand = g[~g["numero"].isin(["95", "96", "97"])]
        dois = cand.loc[cand["turno"] == 2, "numero"].unique()
        if len(dois) != 2:
            print("pulando", mun, "2º turno com", len(dois), "candidatos", flush=True)
            continue
        t1 = cand[(cand["turno"] == 1)].groupby("numero")["votos"].sum()
        a, b = sorted(dois, key=lambda n: -t1.get(n, 0))
        x = cand.assign(col=cand["numero"].map({a: "A", b: "B"}).fillna("O"))
        p = x.pivot_table(index=["turno", "uf"] + CHAVE, columns="col", values="votos", aggfunc="sum", fill_value=0)
        p = p.reset_index()
        for c in ["A", "B", "O"]:
            if c not in p:
                p[c] = 0
        t1s = p[p["turno"] == 1].drop(columns="turno").rename(columns={"A": "A1", "B": "B1", "O": "O1"})
        t2s = p[p["turno"] == 2].drop(columns=["turno", "O"]).rename(columns={"A": "A2", "B": "B2"})
        s = t1s.merge(t2s, on=["uf"] + CHAVE, how="outer").fillna(0)
        for turno, suf in [(1, "1"), (2, "2")]:
            dd = det[(det["turno"] == turno) & (det["mun"] == mun)].drop(columns="turno")
            dd = dd.assign(**{f"W{suf}": dd["brancos"] + dd["nulos"]}).rename(
                columns={"aptos": f"E{suf}", "comparecimento": f"C{suf}"})[CHAVE + [f"E{suf}", f"C{suf}", f"W{suf}"]]
            s = s.merge(dd, on=CHAVE, how="left")
        linhas.append(s)
        nomes = g.drop_duplicates("numero").set_index("numero")
        info[mun] = {"uf": g["uf"].iloc[0], "A": a, "B": b,
                     "secoes": len(s), "secoes_sem_detalhe": int(s["E1"].isna().sum() + s["E2"].isna().sum()),
                     "A2_validos": round(100 * s["A2"].sum() / max(s["A2"].sum() + s["B2"].sum(), 1), 2)}
    s = pd.concat(linhas, ignore_index=True)
    cols = ["E1", "C1", "A1", "B1", "O1", "W1", "E2", "C2", "A2", "B2", "W2"]
    s[cols] = s[cols].fillna(0).astype("int64")
    s["mun"] = s["mun"].str.zfill(5)
    s = s[["uf"] + CHAVE + cols].sort_values(["uf"] + CHAVE)
    pasta = os.path.join(saida, str(ano))
    s.to_csv(os.path.join(pasta, "prefeito_secoes.csv.gz"), index=False)
    for k in [k for k in log if k.endswith(".zip")]:
        log[k].pop("todos", None)
    with open(os.path.join(pasta, "prefeito_secoes.json"), "w", encoding="utf-8") as f:
        json.dump({"cidades": info, "arquivos": log}, f, ensure_ascii=False, indent=1)
    print(ano, len(info), "cidades,", len(s), "seções,", "sem detalhe:",
          sum(i["secoes_sem_detalhe"] for i in info.values()), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("anos", nargs="*", type=int)
    ap.add_argument("--saida", default="dados/historico")
    ap.add_argument("--brutos", default=os.path.join(os.environ.get("RUNNER_TEMP", "dados/brutos"), "tse_prefeito"))
    a = ap.parse_args()
    for ano in a.anos or ANOS:
        processar(ano, a.saida, a.brutos)


if __name__ == "__main__":
    main()
