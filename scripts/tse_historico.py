"""Base histórica do TSE (2006–2024): votos por município de todos os cargos, comparecimento e candidatos.

Roda no GitHub Actions (workflow `historico`), porque o ambiente de desenvolvimento não acessa o TSE.
Baixa os arquivos de dados abertos (cdn.tse.jus.br/estatistica/sead/odsele) e grava, em dados/historico/<ano>/:

  votos_mun.csv.gz       votos por município, cargo, turno e votável. Cargos majoritários (presidente, governador,
                         senador, prefeito): uma linha por candidato (numero = número do candidato). Proporcionais
                         (deputados, vereador): uma linha por partido (nominais + legenda), numero = número do partido.
  comparecimento_mun.csv.gz  aptos, comparecimento, abstenções, brancos, nulos e válidos por município, cargo e turno
  candidatos.csv.gz      candidatos dos cargos majoritários: partido, coligação e sua composição, se tentava a
                         reeleição, situação no turno
  colunas.json           colunas encontradas em cada arquivo do TSE (o formato mudou ao longo dos anos)
  resumo.json            totais por cargo e turno, para conferir com o resultado oficial

Só eleições ordinárias (sem suplementares). Município pelo código do TSE (CD_MUNICIPIO), estável entre anos.

    python scripts/tse_historico.py 2022 2018          # anos
    python scripts/tse_historico.py --todos             # 2006 a 2024
"""
import argparse
import io
import json
import os
import urllib.request
import zipfile

import pandas as pd

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
ANOS = list(range(2006, 2025, 2))
CARGOS = {"1": "presidente", "3": "governador", "5": "senador", "6": "deputado_federal", "7": "deputado_estadual",
          "8": "deputado_distrital", "11": "prefeito", "13": "vereador"}
MAJORITARIOS = {"1", "3", "5", "11"}

# nomes possíveis de cada coluna (o TSE mudou alguns nomes entre anos)
SINONIMOS = {
    "turno": ["NR_TURNO"], "uf": ["SG_UF"], "ue": ["SG_UE"], "mun": ["CD_MUNICIPIO"], "mun_nome": ["NM_MUNICIPIO"],
    "zona": ["NR_ZONA"], "cargo": ["CD_CARGO"], "tipo": ["CD_TIPO_ELEICAO", "NM_TIPO_ELEICAO"],
    "numero": ["NR_CANDIDATO", "NR_VOTAVEL"], "nome": ["NM_URNA_CANDIDATO", "NM_VOTAVEL"],
    "partido": ["SG_PARTIDO"], "nr_partido": ["NR_PARTIDO"], "sq": ["SQ_CANDIDATO"],
    "votos": ["QT_VOTOS_NOMINAIS_VALIDOS", "QT_VOTOS_NOMINAIS", "QT_VOTOS"],
    "votos_nominais": ["QT_VOTOS_NOMINAIS_VALIDOS", "QT_VOTOS_NOMINAIS"],
    "votos_legenda": ["QT_VOTOS_LEGENDA_VALIDOS", "QT_VOTOS_LEGENDA"],
    "aptos": ["QT_APTOS"], "comparecimento": ["QT_COMPARECIMENTO"], "abstencoes": ["QT_ABSTENCOES"],
    "brancos": ["QT_VOTOS_BRANCOS"], "nulos": ["QT_VOTOS_NULOS", "QT_TOTAL_VOTOS_NULOS"],
    "situacao": ["DS_SIT_TOT_TURNO"], "coligacao": ["NM_COLIGACAO", "NM_FEDERACAO"],
    "composicao": ["DS_COMPOSICAO_COLIGACAO", "DS_COMPOSICAO_FEDERACAO"], "reeleicao": ["ST_REELEICAO"],
}


def baixar(url, pasta):
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, url.rsplit("/", 1)[1])
    if not os.path.exists(caminho):
        print("baixando", url, flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        tmp = caminho + ".parcial"
        with urllib.request.urlopen(req, timeout=900) as r, open(tmp, "wb") as f:
            while bloco := r.read(1 << 20):
                f.write(bloco)
        os.replace(tmp, caminho)
    return caminho


def _mapa(colunas, campos):
    """{campo: coluna do arquivo} para os campos pedidos que existem."""
    out = {}
    for c in campos:
        for nome in SINONIMOS[c]:
            if nome in colunas:
                out[c] = nome
                break
    return out


def ler_zip(caminho, campos, filtro=None, log=None):
    """Lê os CSVs do zip (só o _BR quando existir, para não somar em dobro) com as colunas pedidas, renomeadas
    para os nomes de `campos`. `filtro(df)` é aplicado a cada bloco."""
    partes = []
    with zipfile.ZipFile(caminho) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith((".csv", ".txt"))]
        # _BRASIL tem tudo; sem ele, lê todos (UFs e _BR) e as linhas repetidas saem no drop_duplicates abaixo
        brasil = [n for n in nomes if n.upper().rsplit(".", 1)[0].endswith("_BRASIL")]
        nomes = brasil or nomes
        if log is not None:
            log[os.path.basename(caminho)] = {"lidos": nomes, "todos": z.namelist()}
        for n in nomes:
            with z.open(n) as fh:
                cab = fh.readline().decode("latin1").strip().replace('"', "").split(";")
            mapa = _mapa(cab, campos)
            if log is not None:
                log[os.path.basename(caminho)]["colunas"] = cab
            if not mapa:
                continue
            inv = {v: k for k, v in mapa.items()}
            with z.open(n) as fh:
                for bloco in pd.read_csv(io.TextIOWrapper(fh, encoding="latin1"), sep=";", dtype=str,
                                         usecols=list(mapa.values()), chunksize=500_000):
                    bloco = bloco.rename(columns=inv)
                    if filtro is not None:
                        bloco = filtro(bloco)
                    if len(bloco):
                        partes.append(bloco)
    if not partes:
        return pd.DataFrame(columns=list(campos))
    # linhas são únicas por zona: uma repetida veio de dois arquivos com o mesmo recorte
    return pd.concat(partes, ignore_index=True).drop_duplicates()


def ordinaria(df):
    """Só eleição ordinária (CD_TIPO_ELEICAO 2, ou o nome contém "Ordin")."""
    if "tipo" not in df:
        return df
    t = df["tipo"].astype(str)
    return df[(t == "2") | t.str.contains("Ordin", case=False, na=False)]


def _int(df, cols):
    for c in cols:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64")
    return df


CHAVE = ["turno", "cargo", "uf", "mun", "mun_nome"]


def votos_majoritarios(ano, pasta, log):
    url = f"{CDN}/votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip"
    df = ler_zip(baixar(url, pasta), ["turno", "tipo", "uf", "ue", "mun", "mun_nome", "zona", "cargo", "numero", "nome",
                                       "partido", "votos"],
                 lambda d: ordinaria(d[d["cargo"].isin(MAJORITARIOS)]), log)
    df = _int(df, ["votos"])
    out = df.groupby(CHAVE + ["numero", "nome", "partido"], as_index=False, dropna=False)["votos"].sum()
    return out.assign(tipo_voto="candidato")


def votos_proporcionais(ano, pasta, log):
    url = f"{CDN}/votacao_partido_munzona/votacao_partido_munzona_{ano}.zip"
    df = ler_zip(baixar(url, pasta), ["turno", "tipo", "uf", "mun", "mun_nome", "zona", "cargo", "nr_partido", "partido",
                                       "votos_nominais", "votos_legenda"],
                 lambda d: ordinaria(d[d["cargo"].isin(set(CARGOS) - MAJORITARIOS)]), log)
    df = _int(df, ["votos_nominais", "votos_legenda"])
    df["votos"] = df.get("votos_nominais", 0) + df.get("votos_legenda", 0)
    out = df.groupby(CHAVE + ["nr_partido", "partido"], as_index=False, dropna=False)[
        ["votos", "votos_nominais", "votos_legenda"]].sum()
    return out.rename(columns={"nr_partido": "numero"}).assign(nome=lambda d: d["partido"], tipo_voto="partido")


def comparecimento(ano, pasta, log):
    url = f"{CDN}/detalhe_votacao_munzona/detalhe_votacao_munzona_{ano}.zip"
    cols = ["aptos", "comparecimento", "abstencoes", "brancos", "nulos", "votos_nominais", "votos_legenda"]
    df = ler_zip(baixar(url, pasta), ["turno", "tipo", "uf", "mun", "mun_nome", "zona", "cargo"] + cols,
                 lambda d: ordinaria(d[d["cargo"].isin(set(CARGOS))]), log)
    df = _int(df, cols)
    out = df.groupby(CHAVE, as_index=False)[[c for c in cols if c in df]].sum()
    leg = out["votos_legenda"] if "votos_legenda" in out else 0
    out["validos"] = out.get("votos_nominais", 0) + leg
    return out


def candidatos(ano, pasta, log):
    url = f"{CDN}/consulta_cand/consulta_cand_{ano}.zip"
    df = ler_zip(baixar(url, pasta), ["turno", "tipo", "uf", "ue", "cargo", "sq", "numero", "nome", "partido",
                                       "coligacao", "composicao", "reeleicao", "situacao"],
                 lambda d: ordinaria(d[d["cargo"].isin(MAJORITARIOS)]), log)
    return df.drop(columns=["tipo"], errors="ignore").drop_duplicates()


def resumo(votos, comp):
    """Totais por cargo e turno (Brasil) e os dois mais votados nos cargos nacionais."""
    out = []
    for (cargo, turno), g in comp.groupby(["cargo", "turno"]):
        r = {"cargo": CARGOS.get(cargo, cargo), "turno": int(turno), "municipios": int(g["mun"].nunique()),
             **{c: int(g[c].sum()) for c in ["aptos", "comparecimento", "brancos", "nulos", "validos"] if c in g}}
        v = votos[(votos["cargo"] == cargo) & (votos["turno"] == turno)]
        if cargo == "1" and len(v):
            tot = v.groupby(["numero", "nome"])["votos"].sum().sort_values(ascending=False)
            r["mais_votados"] = [{"numero": n, "nome": nm, "votos": int(x), "pct_validos": round(float(100 * x / tot.sum()), 2)}
                                 for (n, nm), x in tot.head(4).items()]
        out.append(r)
    return out


def processar(ano, saida, brutos):
    pasta = os.path.join(saida, str(ano))
    os.makedirs(pasta, exist_ok=True)
    log = {}
    maj = votos_majoritarios(ano, brutos, log)
    prop = votos_proporcionais(ano, brutos, log)
    votos = pd.concat([maj, prop], ignore_index=True)
    votos["cargo_nome"] = votos["cargo"].map(CARGOS)
    for c in ["votos_nominais", "votos_legenda"]:
        if c in votos:
            votos[c] = votos[c].astype("Int64")
    comp = comparecimento(ano, brutos, log)
    comp["cargo_nome"] = comp["cargo"].map(CARGOS)
    cand = candidatos(ano, brutos, log)
    cand["cargo_nome"] = cand["cargo"].map(CARGOS)
    ordem = ["turno", "cargo", "cargo_nome", "uf", "mun", "mun_nome", "tipo_voto", "numero", "nome", "partido", "votos",
             "votos_nominais", "votos_legenda"]
    votos[[c for c in ordem if c in votos]].sort_values(["cargo", "turno", "uf", "mun", "numero"]).to_csv(
        os.path.join(pasta, "votos_mun.csv.gz"), index=False)
    comp.sort_values(["cargo", "turno", "uf", "mun"]).to_csv(os.path.join(pasta, "comparecimento_mun.csv.gz"), index=False)
    cand.to_csv(os.path.join(pasta, "candidatos.csv.gz"), index=False)
    with open(os.path.join(pasta, "colunas.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    res = resumo(votos, comp)
    with open(os.path.join(pasta, "resumo.json"), "w", encoding="utf-8") as f:
        json.dump({"ano": ano, "cargos": res}, f, ensure_ascii=False, indent=1)
    for r in res:
        print(ano, r["cargo"], r["turno"], r.get("municipios"), r.get("validos"), r.get("mais_votados", "")[:2]
              if r.get("mais_votados") else "", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("anos", nargs="*", type=int)
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--saida", default="dados/historico")
    ap.add_argument("--brutos", default=os.path.join(os.environ.get("RUNNER_TEMP", "dados/brutos"), "tse"))
    a = ap.parse_args()
    anos = ANOS if a.todos or not a.anos else a.anos
    for ano in anos:
        processar(ano, a.saida, a.brutos)


if __name__ == "__main__":
    main()
