"""2º turno presidencial por seção (2006–2018), para o teste de estresse com eleições passadas (etapa 4).

Roda no GitHub Actions (workflow `secoes`), porque o ambiente de desenvolvimento não acessa o TSE. Grava
dados/historico/<ano>/secoes_presidente_t2.csv.gz, no mesmo formato de dados/2022/presidente/secoes_t2.csv.gz:

  uf, mun, zona, secao, aptos, comp, A, B, brancos, nulos

A é o candidato do PT (número 13), como em eleicoes/dados/historico.py; B é o outro candidato do 2º turno.
Fontes: votacao_secao_<ano>_BR.zip (votos por votável; os zips por UF só têm os cargos estaduais) e detalhe_votacao_secao (aptos e comparecimento).

    python scripts/tse_secoes.py 2018 2014
"""
import argparse
import json
import os

import pandas as pd

import tse_historico as th

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
       "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO", "ZZ"]
ANOS = [2006, 2010, 2014, 2018]
th.SINONIMOS.setdefault("secao", ["NR_SECAO"])
CHAVE = ["uf", "mun", "zona", "secao"]


def _filtro(d):
    d = d[(d["cargo"].str.strip() == "1") & (d["turno"].str.strip() == "2")]
    return th.ordinaria(d)


def _remover(caminho):
    try:
        os.remove(caminho)
    except OSError:
        pass


def diagnostico(z, log):
    """Nenhuma linha passou no filtro: mostra o cabeçalho e os valores de turno, cargo e tipo e para."""
    import zipfile
    with zipfile.ZipFile(z) as zz:
        print("arquivos:", zz.namelist(), flush=True)
    d = th.ler_zip(z, ["turno", "tipo", "tipo_nome", "cargo"], None, log)
    print("colunas:", log[os.path.basename(z)].get("colunas"), flush=True)
    for c in d.columns:
        print(c, d[c].value_counts().head(8).to_dict(), flush=True)
    raise SystemExit("nenhuma linha do 2º turno presidencial")


def votos(ano, brutos, log):
    partes = []
    # os zips por UF só têm os cargos estaduais; presidente vem no zip _BR (todas as UFs e o exterior)
    for uf in ["BR"]:
        url = f"{th.CDN}/votacao_secao/votacao_secao_{ano}_{uf}.zip"
        try:
            z = th.baixar(url, brutos)
        except Exception as e:  # noqa: BLE001  (ZZ, exterior, não existe em todos os anos)
            print("sem", url, e, flush=True)
            continue
        d = th.ler_zip(z, ["turno", "tipo", "tipo_nome", "uf", "mun", "zona", "secao", "cargo", "numero", "votos"],
                       _filtro, log)
        if d.empty:
            diagnostico(z, log)
        _remover(z)                      # os zips somam vários GB; o runner tem pouco disco
        d = th._int(d.drop(columns=["tipo", "tipo_nome"], errors="ignore"), ["votos"])
        print(ano, uf, len(d), "linhas", flush=True)
        partes.append(d)
    v = pd.concat(partes, ignore_index=True)
    v["numero"] = v["numero"].str.strip()
    cand = v[~v["numero"].isin(["95", "96", "97"])].groupby("numero")["votos"].sum().sort_values(ascending=False)
    assert "13" in cand.index[:2], f"PT não está entre os dois mais votados: {cand.head()}"
    nb = [n for n in cand.index[:2] if n != "13"][0]
    log["candidatos"] = {"A": "13", "B": nb, "votos": {k: int(x) for k, x in cand.head(4).items()}}
    rotulo = {"13": "A", nb: "B", "95": "brancos", "96": "nulos", "97": "nulos"}
    v["col"] = v["numero"].map(rotulo)
    t = v.dropna(subset=["col"]).pivot_table(index=CHAVE, columns="col", values="votos", aggfunc="sum", fill_value=0)
    return t.reset_index()


def detalhe(ano, brutos, log):
    campos = ["turno", "tipo", "tipo_nome", "uf", "mun", "zona", "secao", "cargo", "aptos", "comparecimento"]
    try:
        z = th.baixar(f"{th.CDN}/detalhe_votacao_secao/detalhe_votacao_secao_{ano}.zip", brutos)
        d = th.ler_zip(z, campos, _filtro, log)
        _remover(z)
    except Exception as e:  # noqa: BLE001  (alguns anos vêm por UF)
        print("detalhe nacional indisponível, lendo por UF:", e, flush=True)
        partes = []
        for uf in UFS:
            try:
                z = th.baixar(f"{th.CDN}/detalhe_votacao_secao/detalhe_votacao_secao_{ano}_{uf}.zip", brutos)
            except Exception as e2:  # noqa: BLE001
                print("sem detalhe", ano, uf, e2, flush=True)
                continue
            partes.append(th.ler_zip(z, campos, _filtro, log))
            _remover(z)
        d = pd.concat(partes, ignore_index=True)
    d = th._int(d, ["aptos", "comparecimento"])
    return d.groupby(CHAVE, as_index=False)[["aptos", "comparecimento"]].sum().rename(columns={"comparecimento": "comp"})


def processar(ano, saida, brutos):
    log = {}
    v = votos(ano, brutos, log)
    d = detalhe(ano, brutos, log)
    s = v.merge(d, on=CHAVE, how="left")
    log["secoes_sem_detalhe"] = int(s["aptos"].isna().sum())
    for c in ["aptos", "comp"]:
        s[c] = s[c].fillna(0).astype("int64")
    for c in ["A", "B", "brancos", "nulos"]:
        if c not in s:
            s[c] = 0
    s["uf"] = s["uf"].str.strip().str.lower()
    s["mun"] = s["mun"].str.strip().str.zfill(5)
    s["zona"] = pd.to_numeric(s["zona"]).astype(int)
    s["secao"] = pd.to_numeric(s["secao"]).astype(int)
    s = s[CHAVE + ["aptos", "comp", "A", "B", "brancos", "nulos"]].sort_values(CHAVE)
    pasta = os.path.join(saida, str(ano))
    os.makedirs(pasta, exist_ok=True)
    s.to_csv(os.path.join(pasta, "secoes_presidente_t2.csv.gz"), index=False)
    tot = s[["aptos", "comp", "A", "B", "brancos", "nulos"]].sum()
    log["totais"] = {k: int(x) for k, x in tot.items()}
    log["secoes"] = len(s)
    log["pct_A_validos"] = round(100 * tot["A"] / (tot["A"] + tot["B"]), 2)
    for k in [k for k in log if k.endswith(".zip")]:      # só as colunas de um arquivo de cada tipo
        log[k].pop("todos", None)
    with open(os.path.join(pasta, "secoes_presidente_t2.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    print(ano, json.dumps({k: log[k] for k in ["candidatos", "totais", "secoes", "pct_A_validos", "secoes_sem_detalhe"]}),
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("anos", nargs="*", type=int)
    ap.add_argument("--saida", default="dados/historico")
    ap.add_argument("--brutos", default=os.path.join(os.environ.get("RUNNER_TEMP", "dados/brutos"), "tse_secoes"))
    a = ap.parse_args()
    for ano in a.anos or ANOS:
        processar(ano, a.saida, a.brutos)


if __name__ == "__main__":
    main()
