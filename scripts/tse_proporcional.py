"""Votos dos cargos proporcionais (deputado federal, estadual, distrital e vereador) por candidato e por partido, na
circunscrição inteira (UF para deputados, município para vereador), para refazer a distribuição das cadeiras pelo
quociente eleitoral e simular alianças (etapa 7 do roteiro).

Roda no GitHub Actions (workflow `proporcional`), porque o ambiente de desenvolvimento não acessa o TSE. Grava, em
dados/historico/<ano>/:

  proporcional_candidatos.csv.gz  um candidato por linha: cargo, uf, ue (UF ou código TSE do município), sq, número,
                                  nome, partido, coligação (sq e composição), federação, votos nominais (brutos e
                                  válidos), destinação dos votos, situação da candidatura e situação final (eleito
                                  por QP, por média, suplente...)
  proporcional_partidos.csv.gz    um partido por circunscrição: votos nominais válidos, de legenda (incluindo os
                                  nominais convertidos em legenda) e a coligação ou federação em que estava
  proporcional.json               colunas lidas e totais por cargo, para conferência

    python scripts/tse_proporcional.py 2022 2018
"""
import argparse
import json
import os

import pandas as pd

import tse_historico as th

ANOS = th.ANOS
PROP = {"6", "7", "8", "13"}
th.SINONIMOS.update({
    "sq_coligacao": ["SQ_COLIGACAO"], "sg_federacao": ["SG_FEDERACAO"], "destinacao": ["NM_TIPO_DESTINACAO_VOTOS"],
    "sit_cand": ["DS_SITUACAO_CANDIDATURA"], "detalhe_cand": ["DS_DETALHE_SITUACAO_CAND"],
    "v_brutos": ["QT_VOTOS_NOMINAIS"], "v_validos": ["QT_VOTOS_NOMINAIS_VALIDOS"],
    "leg_validos": ["QT_VOTOS_LEGENDA_VALIDOS"], "leg_brutos": ["QT_VOTOS_LEGENDA"],
    "leg_total": ["QT_TOTAL_VOTOS_LEG_VALIDOS"],
    "convertidos": ["QT_VOTOS_NOM_CONVR_LEG_VALIDOS", "QT_VOTOS_NOMINAIS_CONVR_LEG"],
    "anul_subjud": ["QT_VOTOS_NOMINAIS_ANUL_SUBJUD"], "transito": ["ST_VOTO_EM_TRANSITO"],
})
GRUPO = ["sq_coligacao", "coligacao", "composicao", "federacao", "sg_federacao", "composicao_federacao"]


def _limpa(d):
    for c in d.columns:
        if d[c].dtype == object or str(d[c].dtype).startswith("str"):
            d[c] = d[c].str.strip()
    return d


def candidatos(ano, brutos, log):
    url = f"{th.CDN}/votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip"
    campos = ["turno", "tipo", "tipo_nome", "uf", "ue", "zona", "mun", "transito", "cargo", "sq", "numero", "nome", "partido",
              "nr_partido", "sit_cand", "detalhe_cand", "destinacao", "situacao", "v_brutos", "v_validos"] + GRUPO
    d = th.ler_zip(th.baixar(url, brutos), campos, lambda x: th.ordinaria(x[x["cargo"].str.strip().isin(PROP)]), log)
    d = _limpa(d.drop(columns=["tipo", "tipo_nome"], errors="ignore"))
    d = th._int(d, ["v_brutos", "v_validos"])
    # em 2010 o SG_UE dos deputados vem com o código do município; a circunscrição deles é a UF
    est = d["cargo"].isin(["6", "7", "8"])
    d.loc[est, "ue"] = d.loc[est, "uf"]
    info = [c for c in ["cargo", "uf", "ue", "sq", "numero", "nome", "partido", "nr_partido", "sit_cand",
                        "detalhe_cand", "destinacao", "situacao"] + GRUPO if c in d]
    soma = [c for c in ["v_brutos", "v_validos"] if c in d]
    # SQ_CANDIDATO se repete entre cargos e circunscrições nos arquivos antigos (até 2010): a chave inclui os dois
    chave = ["cargo", "ue", "sq", "numero"]
    out = d.groupby(chave, as_index=False)[soma].sum().merge(
        d.drop_duplicates(chave)[[c for c in info if c not in chave] + chave], on=chave)
    if "v_validos" not in out:
        out["v_validos"] = pd.NA      # até 2014 o arquivo só tem os votos nominais brutos
    return out


def partidos(ano, brutos, log):
    url = f"{th.CDN}/votacao_partido_munzona/votacao_partido_munzona_{ano}.zip"
    campos = ["turno", "tipo", "tipo_nome", "uf", "ue", "zona", "mun", "transito", "cargo", "nr_partido", "partido", "v_brutos",
              "v_validos", "leg_validos", "leg_brutos", "leg_total", "convertidos", "anul_subjud"] + GRUPO
    d = th.ler_zip(th.baixar(url, brutos), campos, lambda x: th.ordinaria(x[x["cargo"].str.strip().isin(PROP)]), log)
    d = _limpa(d.drop(columns=["tipo", "tipo_nome"], errors="ignore"))
    num = [c for c in ["v_brutos", "v_validos", "leg_validos", "leg_brutos", "leg_total", "convertidos",
                       "anul_subjud"] if c in d]
    d = th._int(d, num)
    est = d["cargo"].isin(["6", "7", "8"])
    d.loc[est, "ue"] = d.loc[est, "uf"]
    chave = ["cargo", "uf", "ue", "nr_partido", "partido"]
    out = d.groupby(chave, as_index=False)[num].sum()
    out = out.merge(d.drop_duplicates(chave)[chave + [c for c in GRUPO if c in d]], on=chave)
    # nominais válidos e legenda: os nomes mudaram em 2016 e 2018
    out["nominais"] = out["v_validos"] if "v_validos" in out else out["v_brutos"]
    if "leg_total" in out:
        out["legenda"] = out["leg_total"]
    elif "leg_validos" in out:
        out["legenda"] = out["leg_validos"] + out.get("convertidos", 0)
    else:
        out["legenda"] = out["leg_brutos"]
    out["votos"] = out["nominais"] + out["legenda"]
    return out


def processar(ano, saida, brutos):
    pasta = os.path.join(saida, str(ano))
    os.makedirs(pasta, exist_ok=True)
    log = {}
    th.TIPOS.clear()
    cand = candidatos(ano, brutos, log)
    part = partidos(ano, brutos, log)
    cand["cargo_nome"] = cand["cargo"].map(th.CARGOS)
    part["cargo_nome"] = part["cargo"].map(th.CARGOS)
    cand.sort_values(["cargo", "uf", "ue", "partido", "numero"]).to_csv(
        os.path.join(pasta, "proporcional_candidatos.csv.gz"), index=False)
    part.sort_values(["cargo", "uf", "ue", "partido"]).to_csv(
        os.path.join(pasta, "proporcional_partidos.csv.gz"), index=False)
    eleito = cand["situacao"].fillna("").str.upper().str.strip().str.match(r"^(ELEITO|M[ÉE]DIA)")
    res = {"ano": ano, "tipos_de_eleicao": dict(th.TIPOS), "colunas": {k: v.get("colunas") for k, v in log.items()},
           "situacoes": cand["situacao"].value_counts().to_dict(),
           "destinacoes": cand["destinacao"].value_counts().to_dict() if "destinacao" in cand else {},
           "cargos": {}}
    for cargo, g in part.groupby("cargo"):
        c = cand[cand["cargo"] == cargo]
        res["cargos"][th.CARGOS.get(cargo, cargo)] = {
            "circunscricoes": int(g["ue"].nunique()), "votos": int(g["votos"].sum()),
            "nominais": int(g["nominais"].sum()), "legenda": int(g["legenda"].sum()),
            "candidatos": int(len(c)), "eleitos": int(eleito[c.index].sum()),
            "nominais_candidatos": int(c["v_validos"].fillna(c["v_brutos"]).sum())}
        print(ano, cargo, res["cargos"][th.CARGOS.get(cargo, cargo)], flush=True)
    with open(os.path.join(pasta, "proporcional.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("anos", nargs="*", type=int)
    ap.add_argument("--saida", default="dados/historico")
    ap.add_argument("--brutos", default=os.path.join(os.environ.get("RUNNER_TEMP", "dados/brutos"), "tse"))
    a = ap.parse_args()
    for ano in a.anos or ANOS:
        processar(ano, a.saida, a.brutos)


if __name__ == "__main__":
    main()
