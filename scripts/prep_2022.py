"""Baixa os dados abertos de 2022 do TSE (por seção) e gera arquivos compactos para o backtest.

Roda no GitHub Actions (o ambiente de desenvolvimento não acessa o TSE).
Saídas em data/2022/:
  mun_t1.csv.gz     1º turno agregado por município (base do modelo, como ao vivo)
  secoes_t2.csv.gz  2º turno por seção (para simular a apuração parcial)
"""
import io
import os
import sys
import urllib.request
import zipfile

import pandas as pd

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
OUT = sys.argv[1] if len(sys.argv) > 1 else "data/2022"
TMP = os.environ.get("RUNNER_TEMP", "/tmp")
os.makedirs(OUT, exist_ok=True)


def download(url):
    path = os.path.join(TMP, url.rsplit("/", 1)[1])
    if not os.path.exists(path):
        print("baixando", url, flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    return path


def read_zip_csvs(path, usecols, filt):
    parts = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        print(path, names[:5], "...", len(names), flush=True)
        for n in names:
            with z.open(n) as fh:
                head = fh.readline().decode("latin1")
            print("colunas", n, head.strip()[:400], flush=True)
            with z.open(n) as fh:
                for ch in pd.read_csv(io.TextIOWrapper(fh, encoding="latin1"), sep=";", usecols=lambda c: c in usecols,
                                      dtype=str, chunksize=500_000):
                    ch = filt(ch)
                    if len(ch):
                        parts.append(ch)
    return pd.concat(parts, ignore_index=True)


KEY = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO"]

# votos por seção e votável (presidente)
vot = read_zip_csvs(
    download(f"{CDN}/votacao_secao/votacao_secao_2022_BR.zip"),
    set(KEY + ["CD_CARGO", "NR_VOTAVEL", "QT_VOTOS"]),
    lambda d: d[d["CD_CARGO"] == "1"],
)
vot["QT_VOTOS"] = vot["QT_VOTOS"].astype(int)
vot["col"] = vot["NR_VOTAVEL"].map({"13": "v13", "22": "v22", "95": "brancos", "96": "nulos"}).fillna("outros")
piv = vot.pivot_table(index=KEY, columns="col", values="QT_VOTOS", aggfunc="sum", fill_value=0).reset_index()
del vot

# comparecimento e aptos por seção
det = read_zip_csvs(
    download(f"{CDN}/detalhe_votacao_secao/detalhe_votacao_secao_2022.zip"),
    set(KEY + ["CD_CARGO", "QT_APTOS", "QT_COMPARECIMENTO"]),
    lambda d: d[d["CD_CARGO"] == "1"],
)
for c in ["QT_APTOS", "QT_COMPARECIMENTO"]:
    det[c] = det[c].astype(int)
det = det.groupby(KEY, as_index=False)[["QT_APTOS", "QT_COMPARECIMENTO"]].sum()

sec = det.merge(piv, on=KEY, how="outer")
for c in ["v13", "v22", "outros", "brancos", "nulos", "QT_APTOS", "QT_COMPARECIMENTO"]:
    if c not in sec:
        sec[c] = 0
    sec[c] = sec[c].fillna(0).astype(int)
sec = sec.rename(columns={"NR_TURNO": "turno", "SG_UF": "uf", "CD_MUNICIPIO": "mun", "NM_MUNICIPIO": "nome",
                          "NR_ZONA": "zona", "NR_SECAO": "secao", "QT_APTOS": "aptos", "QT_COMPARECIMENTO": "comp"})
sec["uf"] = sec["uf"].str.lower()
sec["mun"] = sec["mun"].str.zfill(5)
print(sec.groupby("turno")[["aptos", "comp", "v13", "v22", "outros", "brancos", "nulos"]].sum(), flush=True)

cols = ["uf", "mun", "nome", "aptos", "comp", "v13", "v22", "outros", "brancos", "nulos"]
t1 = sec[sec["turno"] == "1"].groupby(["uf", "mun", "nome"], as_index=False)[cols[3:]].sum()
t1.to_csv(os.path.join(OUT, "mun_t1.csv.gz"), index=False)
t2 = sec[sec["turno"] == "2"][["uf", "mun", "zona", "secao", "aptos", "comp", "v13", "v22", "brancos", "nulos", "outros"]]
t2.to_csv(os.path.join(OUT, "secoes_t2.csv.gz"), index=False)
print("ok", len(t1), "municipios;", len(t2), "secoes T2", flush=True)
