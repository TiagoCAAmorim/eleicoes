"""Extrai do histórico git os retratos da apuração do 2º turno de 2026 (um por rodada publicada).

Cada commit do loop gravou saida/2026/dados_municipios.csv (depois resultados/2026-presidente/). Este script lê
todas as versões e grava só o que muda na apuração em dados/2026/presidente/retratos_t2.csv.gz:
uma linha por (rodada, município) com o 2º turno apurado. O 1º turno fica em mun_t1.csv.gz.

    python scripts/extrair_retratos_2026.py
"""
import io
import subprocess

import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import RAIZ, dados

CAMINHOS = ["saida/2026/dados_municipios.csv", "resultados/2026-presidente/dados_municipios.csv"]
HIST = ["saida/2026/historico.csv", "resultados/2026-presidente/historico.csv"]
COLS = ["eleitores_t2", "eleitores_apurados_t2", "A_apurado_t2", "B_apurado_t2", "branco_nulo_apurado_t2",
        "comparecimento_apurado_t2"]


def git(*a):
    return subprocess.run(["git", *a], cwd=RAIZ, capture_output=True, check=True).stdout


def main():
    commits = git("log", "--format=%H %cI", "--", *CAMINHOS).decode().split("\n")
    vistos, partes = set(), []
    for linha in reversed([c for c in commits if c]):
        h, quando = linha.split()
        for cam in CAMINHOS:
            try:
                bruto = git("show", f"{h}:{cam}")
                hist = pd.read_csv(io.BytesIO(git("show", f"{h}:{HIST[CAMINHOS.index(cam)]}")))
                break
            except subprocess.CalledProcessError:
                bruto = None
        if bruto is None:
            continue
        ult = hist.iloc[-1]
        hora = str(ult["hora"])
        if not hora.startswith("2026-10-25") or hora in vistos:   # descarta testes de antes da eleição e repetições
            continue
        df = pd.read_csv(io.BytesIO(bruto), sep=";", decimal=",", encoding="utf-8-sig", dtype={"cod_tse": str})
        # colunas pelo nome genérico (o nome do candidato mudou de "Flavio" para "Flávio" durante a noite)
        ap = [c for c in df.columns if c.endswith("_apurado_t2")]
        df = df.rename(columns={ap[0]: "A_apurado_t2", ap[1]: "B_apurado_t2"})
        vistos.add(hora)
        partes.append(df[["uf", "cod_tse"] + COLS].assign(hora=hora, pct_secoes=float(ult["pct_secoes"])))
        print(hora, f"{float(ult['pct_secoes']):6.2f}%", h[:7], len(df))
    out = pd.concat(partes, ignore_index=True)
    caminho = dados(2026, "presidente", "retratos_t2.csv.gz")
    out[["hora", "pct_secoes", "uf", "cod_tse"] + COLS].to_csv(caminho, index=False)
    print(f"{out.hora.nunique()} retratos gravados em {caminho}")


if __name__ == "__main__":
    main()
