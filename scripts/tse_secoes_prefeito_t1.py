"""1º turno de prefeito por seção nas cidades com mais de 200 mil eleitores (as que podem ter 2º turno), 2008–2024,
para a previsão do 1º turno (etapa 6 do roteiro).

Ao contrário de prefeito_secoes.csv.gz (só cidades que tiveram 2º turno, com os demais candidatos somados em "O"),
aqui ficam todas as cidades grandes e todos os candidatos, inclusive as decididas no 1º turno.

Roda no GitHub Actions (workflow `secoes_prefeito_t1`), porque o ambiente de desenvolvimento não acessa o TSE.
Grava, em dados/historico/<ano>/:

  prefeito_t1_secoes.csv.gz       uma linha por seção: uf, mun, zona, secao, E (aptos), C (comparecimento),
                                  W (brancos + nulos)
  prefeito_t1_votos.csv.gz        uma linha por seção e candidato: mun, zona, secao, numero, votos
  prefeito_t1_secoes.json         candidatos de cada cidade e totais, para conferência

    python scripts/tse_secoes_prefeito_t1.py 2024 2020
"""
import argparse
import json
import os

import pandas as pd

import tse_historico as th
from tse_secoes import _remover
from tse_secoes_prefeito import CHAVE, _num, detalhe

ANOS = [2008, 2012, 2016, 2020, 2024]
th.SINONIMOS.setdefault("secao", ["NR_SECAO"])
MIN_APTOS = 200_000


def cidades(ano, saida):
    c = pd.read_csv(os.path.join(saida, str(ano), "comparecimento_mun.csv.gz"), dtype={"mun": str})
    c = c[(c["cargo"] == 11) & (c["turno"] == 1) & (c["aptos"] > MIN_APTOS)]
    c["mun"] = c["mun"].str.lstrip("0")
    return set(c["mun"]), sorted(c["uf"].str.upper().unique())


def ler_uf(ano, uf, muns, brutos, log):
    def filtro(d):
        d = d[(d["cargo"].str.strip() == "11") & (d["turno"].str.strip() == "1")
              & d["mun"].str.strip().str.lstrip("0").isin(muns)]
        return th.ordinaria(d)
    z = th.baixar(f"{th.CDN}/votacao_secao/votacao_secao_{ano}_{uf}.zip", brutos)
    d = th.ler_zip(z, ["turno", "tipo", "tipo_nome", "mun", "zona", "secao", "cargo", "numero", "votos"], filtro, log)
    _remover(z)
    d = d.drop(columns=["tipo", "tipo_nome", "cargo", "turno"], errors="ignore")
    d["mun"] = d["mun"].str.strip().str.lstrip("0")
    d["numero"] = d["numero"].str.strip()
    return _num(d, ["zona", "secao", "votos"])


def processar(ano, saida, brutos):
    log = {}
    muns, ufs = cidades(ano, saida)
    print(ano, len(muns), "cidades com mais de 200 mil eleitores em", ufs, flush=True)
    partes = []
    for uf in ufs:
        d = ler_uf(ano, uf, muns, brutos, log)
        print(ano, uf, len(d), "linhas", flush=True)
        partes.append(d)
    v = pd.concat(partes, ignore_index=True)
    v = v[~v["numero"].isin(["95", "96", "97"])]
    v = v.groupby(CHAVE + ["numero"], as_index=False)["votos"].sum()
    det = detalhe(ano, ufs, muns, brutos, log)
    det = det[det["turno"] == 1].drop(columns="turno")
    det["W"] = det["brancos"] + det["nulos"]
    det = det.rename(columns={"aptos": "E", "comparecimento": "C"})
    secoes = v[CHAVE].drop_duplicates().merge(det[CHAVE + ["E", "C", "W"]], on=CHAVE, how="left")
    sem = int(secoes["E"].isna().sum())
    secoes[["E", "C", "W"]] = secoes[["E", "C", "W"]].fillna(-1).astype("int64")   # -1 = sem detalhe
    vm = pd.read_csv(os.path.join(saida, str(ano), "votos_mun.csv.gz"), dtype={"mun": str, "numero": str})
    vm = vm[(vm["cargo"] == 11) & (vm["turno"] == 1)]
    vm["mun"] = vm["mun"].str.lstrip("0")
    uf_de = vm.drop_duplicates("mun").set_index("mun")["uf"].str.lower()
    secoes.insert(0, "uf", secoes["mun"].map(uf_de))
    info = {}
    for mun, g in v.groupby("mun"):
        tot = g.groupby("numero")["votos"].sum().sort_values(ascending=False)
        ofic = vm[vm["mun"] == mun].groupby("numero")["votos"].sum()
        nomes = vm[vm["mun"] == mun].drop_duplicates("numero").set_index("numero")["nome"]
        val = tot.sum()
        info[mun] = {"uf": uf_de.get(mun), "secoes": int((secoes["mun"] == mun).sum()),
                     "candidatos": {n: {"nome": nomes.get(n, ""), "votos": int(x), "validos": round(100 * x / val, 2),
                                        "oficial_mun": int(ofic.get(n, 0))} for n, x in tot.items()}}
    pasta = os.path.join(saida, str(ano))
    for d in (v, secoes):
        d["mun"] = d["mun"].str.zfill(5)
    secoes.sort_values(CHAVE).to_csv(os.path.join(pasta, "prefeito_t1_secoes.csv.gz"), index=False)
    v.sort_values(CHAVE + ["numero"]).to_csv(os.path.join(pasta, "prefeito_t1_votos.csv.gz"), index=False)
    for k in [k for k in log if k.endswith(".zip")]:
        log[k].pop("todos", None)
    with open(os.path.join(pasta, "prefeito_t1_secoes.json"), "w", encoding="utf-8") as f:
        json.dump({"cidades": info, "secoes_sem_detalhe": sem, "arquivos": log}, f, ensure_ascii=False, indent=1)
    print(ano, len(info), "cidades,", len(secoes), "seções,", "sem detalhe:", sem, flush=True)


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
