"""Distribuição das cadeiras nas eleições proporcionais (deputados e vereadores) pelo sistema do Código Eleitoral
(arts. 106 a 111), com as regras de cada ano de 2006 a 2024, e simulação de alianças contrafactuais (etapa 7).

Uma *agremiação* é quem disputa as cadeiras como uma só lista: a coligação (até 2018 para deputados, até 2016 para
vereadores), a federação (a partir de 2022) ou o partido sozinho. Os votos da agremiação são os nominais válidos de
seus candidatos mais os de legenda de seus partidos.

Passos em cada circunscrição (UF ou município), com V = votos válidos (nominais + legenda) e n = vagas:

1. Quociente eleitoral QE = V / n, arredondado (fração até meio é desprezada, art. 106).
2. Quociente partidário QP = ⌊votos da agremiação / QE⌋ (art. 107); a agremiação elege até QP candidatos, os mais
   votados, entre os que têm pelo menos `minimo_qp`·QE votos (10% desde 2016, art. 108).
3. Sobras (art. 109): cada cadeira restante vai à maior média votos / (cadeiras + 1) entre as agremiações que podem
   disputar (as que atingiram `barreira`·QE: 100% até 2016, todas em 2018–2020, 80% desde 2022) e que ainda têm
   candidato com `minimo_sobras`·QE votos (10% em 2016–2020, 20% desde 2022).
4. Se ninguém mais atende às exigências, as cadeiras que faltam vão às maiores médias sem exigência individual,
   entre as agremiações da barreira (leitura do TSE em 2022) ou entre todas (STF, ADIs 7228/7263/7325, a partir de
   2024).
5. Se nenhuma agremiação atinge o QE, elegem-se os candidatos mais votados (art. 111).
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Regra:
    nome: str
    coligacoes: bool          # as coligações proporcionais valem como uma só lista
    federacoes: bool          # as federações valem como uma só lista
    barreira: float           # fração do QE que a agremiação precisa para disputar as sobras (0 = todas)
    minimo_qp: float          # fração do QE que o candidato precisa para ocupar vaga do QP
    minimo_sobras: float      # fração do QE que o candidato precisa para ocupar vaga das sobras
    fase3: str = "barreira"   # quem disputa as cadeiras que ninguém mais pode ocupar: "barreira" ou "todos"


REGRAS = {
    # Código Eleitoral original: só quem atinge o QE disputa as sobras; sem votação mínima individual
    "2006": Regra("até 2014", True, False, 1.0, 0.0, 0.0),
    # Lei 13.165/2015: candidato precisa de 10% do QE
    "2016": Regra("2016", True, False, 1.0, 0.1, 0.1),
    # Lei 13.488/2017: todos os partidos e coligações disputam as sobras
    "2018": Regra("2018", True, False, 0.0, 0.1, 0.1, "todos"),
    # EC 97/2017: fim das coligações proporcionais
    "2020": Regra("2020", False, False, 0.0, 0.1, 0.1, "todos"),
    # Lei 14.211/2021 e federações (Lei 14.208/2021): sobras só para quem tem 80% do QE e candidato com 20%. Na 3ª
    # fase das sobras o TSE deixou só quem tinha 80% do QE; o STF (ADIs 7228/7263/7325) abriu a todos, e a
    # retotalização de 2022 trocou 7 deputados federais (AP, DF, RO, TO). Os dados do TSE já trazem os eleitos
    # depois dela, por isso 2022 usa "todos"; a leitura original é REGRAS["2022_tse"].
    "2022": Regra("2022", False, True, 0.8, 0.1, 0.2, "todos"),
    "2022_tse": Regra("2022 (leitura original do TSE)", False, True, 0.8, 0.1, 0.2, "barreira"),
    "2024": Regra("2024", False, True, 0.8, 0.1, 0.2, "todos"),
}


def regra_do_ano(ano):
    if ano <= 2014:
        return REGRAS["2006"]
    return REGRAS[str(min(ano, 2024))]


def quociente_eleitoral(validos, vagas):
    q, r = divmod(int(validos), int(vagas))
    return q + (1 if 2 * r > vagas else 0)


def distribuir(votos_agrem, candidatos, vagas, regra, desempate=None):
    """Distribui `vagas` cadeiras numa circunscrição.

    votos_agrem: {agremiação: votos válidos (nominais + legenda)}
    candidatos: DataFrame com colunas sq, agrem, votos (nominais válidos); só candidatos que podem ser eleitos
    Devolve (eleitos: lista de sq na ordem em que foram eleitos, fase de cada um, QE)."""
    V = sum(votos_agrem.values())
    if V <= 0 or vagas <= 0:
        return [], [], 0
    qe = quociente_eleitoral(V, vagas)
    cand = candidatos.sort_values(["votos", "sq"], ascending=[False, True])
    listas = {a: list(zip(g["sq"], g["votos"])) for a, g in cand.groupby("agrem", sort=False)}
    pos = {a: 0 for a in votos_agrem}        # próximo candidato de cada lista
    cad = {a: 0 for a in votos_agrem}
    eleitos, fases = [], []

    def proximo(a, minimo):
        lst = listas.get(a, [])
        i = pos[a]
        if i < len(lst) and lst[i][1] >= minimo:
            return lst[i][0]
        return None

    def eleger(a, sq, fase):
        eleitos.append(sq)
        fases.append(fase)
        pos[a] += 1
        cad[a] += 1

    if max(votos_agrem.values()) < qe:
        # art. 111: ninguém atingiu o QE
        for sq in cand["sq"].head(vagas):
            eleitos.append(sq)
            fases.append("art111")
        return eleitos, fases, qe

    for a, v in votos_agrem.items():
        for _ in range(v // qe):
            sq = proximo(a, regra.minimo_qp * qe)
            if sq is None or len(eleitos) >= vagas:
                break
            eleger(a, sq, "qp")

    disputam = [a for a, v in votos_agrem.items() if v >= regra.barreira * qe]
    fase = "media"
    while len(eleitos) < vagas:
        if fase == "media":
            aptos = [a for a in disputam if proximo(a, regra.minimo_sobras * qe) is not None]
            if not aptos:
                fase = "fase3"
                continue
            minimo = regra.minimo_sobras * qe
        else:
            grupo = disputam if regra.fase3 == "barreira" else list(votos_agrem)
            aptos = [a for a in grupo if proximo(a, 0) is not None]
            if not aptos:
                aptos = [a for a in votos_agrem if proximo(a, 0) is not None]
            if not aptos:
                break       # não há mais candidatos
            minimo = 0
        # empate total: vence o primeiro em ordem alfabética (a página interativa faz igual)
        a = max(sorted(aptos), key=lambda x: (votos_agrem[x] / (cad[x] + 1), votos_agrem[x]))
        eleger(a, proximo(a, minimo), fase)
    return eleitos, fases, qe


# ---------------------------------------------------------------------------------------------------------------
# Agremiações e simulação de uma eleição inteira

def _nulo(s):
    s = s.fillna("").astype(str).str.strip()
    return s.where(~s.str.upper().isin(["", "#NULO", "#NULO#", "#NE", "NAN"]), "")


def agremiacoes(partidos, regra, alianca=None):
    """Coluna `agrem` de cada partido em cada circunscrição.

    alianca: None (as listas reais do ano, conforme a regra), "partido" (cada partido sozinho) ou uma função
    (DataFrame de partidos) -> Series com o nome da agremiação de cada linha (por exemplo, coligações de
    governador como se valessem para deputado, ou federações hipotéticas)."""
    p = partidos.copy()
    if callable(alianca):
        p["agrem"] = alianca(p).fillna(p["partido"]).where(lambda s: s != "", p["partido"])
        return p
    p["agrem"] = p["partido"]
    if alianca == "partido":
        return p
    if regra.federacoes and "sg_federacao" in p:
        fed = _nulo(p["sg_federacao"])
        p["agrem"] = np.where(fed != "", "Fed. " + fed, p["agrem"])
    if regra.coligacoes and "sq_coligacao" in p:
        sozinho = _nulo(p["coligacao"]).str.upper().str.contains("PARTIDO ISOLADO|^$", regex=True)
        # a composição identifica a coligação: há municípios com a mesma coligação registrada duas vezes (sq
        # diferentes, mesma lista de partidos em outra ordem); a ordem dos partidos é normalizada
        comp = _nulo(p["composicao"]).map(lambda x: " / ".join(sorted(t.strip() for t in x.split("/") if t.strip())))
        col = "Col. " + comp.where(comp != "", p["sq_coligacao"].astype(str))
        p["agrem"] = np.where(sozinho, p["agrem"], col)
    return p


def simular(partidos, candidatos, vagas, regra, alianca=None):
    """Distribui as cadeiras de todas as circunscrições.

    partidos: proporcional_partidos de um cargo (cargo, ue, partido, votos, coligação/federação)
    candidatos: proporcional_candidatos do mesmo cargo, com a coluna `votos` (nominais válidos)
    vagas: {ue: número de cadeiras}
    Devolve DataFrame de eleitos: ue, sq, partido, agrem, fase, qe."""
    p = agremiacoes(partidos, regra, alianca)
    mapa = p.set_index(["ue", "partido"])["agrem"]
    c = candidatos[["ue", "sq", "partido", "votos"]].copy()
    c["agrem"] = mapa.reindex(pd.MultiIndex.from_frame(c[["ue", "partido"]])).to_numpy()
    c["agrem"] = c["agrem"].fillna(c["partido"])
    out = []
    cg = dict(tuple(c.groupby("ue")))
    for ue, g in p.groupby("ue"):
        n = int(vagas.get(ue, 0))
        if n <= 0:
            continue
        va = g.groupby("agrem")["votos"].sum().astype("int64").to_dict()
        cc = cg.get(ue, c.iloc[:0])
        eleitos, fases, qe = distribuir(va, cc[cc["votos"] > 0], n, regra)
        if eleitos:
            e = cc.set_index("sq").loc[eleitos, ["partido", "agrem"]].reset_index()
            e["fase"] = fases
            e["ue"] = ue
            e["qe"] = qe
            out.append(e)
    if not out:
        return pd.DataFrame(columns=["ue", "sq", "partido", "agrem", "fase", "qe"])
    return pd.concat(out, ignore_index=True)[["ue", "sq", "partido", "agrem", "fase", "qe"]]


def cadeiras(eleitos, por="partido"):
    return eleitos.groupby(por).size().sort_values(ascending=False)


# ---------------------------------------------------------------------------------------------------------------
# Medidas de proporcionalidade

def gallagher(votos, cadeiras_):
    """Índice de mínimos quadrados de Gallagher (em pontos percentuais): √(½ Σ (v_i − s_i)²)."""
    df = pd.DataFrame({"v": pd.Series(votos, dtype=float), "s": pd.Series(cadeiras_, dtype=float)}).fillna(0)
    v = 100 * df["v"] / df["v"].sum()
    s = 100 * df["s"] / df["s"].sum()
    return float(np.sqrt(0.5 * ((v - s) ** 2).sum()))


def sainte_lague(votos, n):
    """Cadeiras por Sainte-Laguë (divisores 1, 3, 5...), para comparação com uma regra mais proporcional."""
    v = pd.Series(votos, dtype=float)
    s = pd.Series(0, index=v.index)
    for _ in range(n):
        s[(v / (2 * s + 1)).idxmax()] += 1
    return s


__all__ = ["Regra", "REGRAS", "regra_do_ano", "quociente_eleitoral", "distribuir", "agremiacoes", "simular",
           "cadeiras", "gallagher", "sainte_lague", "replace"]


# ---------------------------------------------------------------------------------------------------------------
# Leitura da base (dados/historico/<ano>/proporcional_*.csv.gz, gerada por scripts/tse_proporcional.py)

CARGOS = {6: "deputado_federal", 7: "deputado_estadual", 8: "deputado_distrital", 13: "vereador"}
ELEITO = r"^(ELEITO|M[ÉE]DIA)"


def carregar(ano, cargo):
    """(partidos, candidatos, vagas) de um cargo. Vagas = número de eleitos em cada circunscrição."""
    import os
    from ..caminhos import DADOS
    pasta = os.path.join(DADOS, "historico", str(ano))
    c = pd.read_csv(os.path.join(pasta, "proporcional_candidatos.csv.gz"), dtype=str)
    p = pd.read_csv(os.path.join(pasta, "proporcional_partidos.csv.gz"), dtype=str)
    c, p = c[c["cargo"] == str(cargo)].copy(), p[p["cargo"] == str(cargo)].copy()
    if cargo in (6, 7, 8):
        c["ue"], p["ue"] = c["uf"], p["uf"]
    p["votos"] = pd.to_numeric(p["votos"]).fillna(0).astype("int64")
    c["votos"] = pd.to_numeric(c["v_validos"].fillna(c["v_brutos"])).fillna(0).astype("int64")
    c["eleito"] = c["situacao"].fillna("").str.strip().str.upper().str.match(ELEITO)
    vagas = c[c["eleito"]].groupby("ue").size().to_dict()
    return p.reset_index(drop=True), c.reset_index(drop=True), vagas


def com_grupos(regra, grupos=(), base="real", ufs=None):
    """Função de aliança para `simular`: parte das listas reais do ano (base="real") ou de cada partido sozinho
    (base="partido") e junta cada grupo de partidos numa lista só. Um partido de um grupo sai da coligação ou
    federação em que estava; os outros membros dela continuam juntos. Um grupo de um partido só tira o partido da
    sua aliança. `ufs`: aplica os grupos só nessas circunscrições."""
    grupos = [tuple(g) for g in grupos]

    def f(p):
        a = agremiacoes(p, regra, None if base == "real" else "partido")["agrem"].copy()
        onde = p["ue"].isin(ufs) if ufs is not None else pd.Series(True, index=p.index)
        for g in grupos:
            nome = "Aliança " + " / ".join(g) if len(g) > 1 else g[0]
            a[p["partido"].isin(g) & onde] = nome
        return a
    return f


def comparar(antes, depois, candidatos):
    """Quem entra e quem sai entre duas simulações (DataFrames de `simular`)."""
    a, d = set(zip(antes["ue"], antes["sq"])), set(zip(depois["ue"], depois["sq"]))
    info = candidatos.set_index(["ue", "sq"])[["nome", "partido", "votos"]]
    entra = info.reindex(sorted(d - a)).reset_index().assign(mudanca="entra")
    sai = info.reindex(sorted(a - d)).reset_index().assign(mudanca="sai")
    return pd.concat([entra, sai], ignore_index=True).sort_values(["mudanca", "ue", "votos"], ascending=[True, True, False])
