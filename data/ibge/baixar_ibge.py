"""Baixa indicadores municipais do IBGE (API SIDRA) e grava indicadores-ibge/ibge_municipios.csv.

Uma linha por município, chave `cdi` (código IBGE de 7 dígitos) e `cod_tse`
(via data/municipios.csv). Todas as tabelas são do Censo 2022, exceto PIB (2023).

Uso: python indicadores-ibge/baixar_ibge.py [--sem-cache]
"""
import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

import pandas as pd

PASTA = Path(__file__).resolve().parent
CACHE = PASTA / "cache"
SAIDA = PASTA / "ibge_municipios.csv"
MUNICIPIOS = PASTA.parent / "data" / "municipios.csv"  # tabela TSE <-> IBGE (coluna cdi)
URL = "https://apisidra.ibge.gov.br/values"


def sidra(nome, tabela, variaveis, periodo, classes=None, usar_cache=True):
    """Consulta a SIDRA para todos os municípios; devolve DataFrame com `cdi`, `v` (variável),
    uma coluna por classificação (código da categoria) e `valor` numérico."""
    caminho = CACHE / f"{nome}.json"
    if usar_cache and caminho.exists():
        dados = json.loads(caminho.read_text())
    else:
        partes = [f"t/{tabela}", "n6/all", f"v/{variaveis}", f"p/{periodo}"]
        partes += [f"c{c}/{cats}" for c, cats in (classes or {}).items()]
        url = f"{URL}/" + "/".join(partes)
        for tentativa in range(4):
            try:
                req = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
                dados = json.loads(urllib.request.urlopen(req, timeout=180).read())
                break
            except Exception as e:  # rede/5xx: tenta de novo
                print(f"  {nome}: tentativa {tentativa + 1} falhou ({e})")
                time.sleep(3 * (tentativa + 1))
        else:
            raise RuntimeError(f"{nome}: falha em {url}")
        if len(dados) < 2:
            raise RuntimeError(f"{nome}: resposta vazia em {url}")
        CACHE.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(dados))
    cab, linhas = dados[0], dados[1:]
    df = pd.DataFrame(linhas)
    saida = pd.DataFrame({"cdi": df["D1C"].astype(int)})
    for k in sorted(c for c in cab if re.fullmatch(r"D\d+C", c) and c != "D1C"):
        nome_dim = cab[k[:-1] + "N"]
        saida["v" if nome_dim == "Variável" else f"c_{nome_dim}"] = df[k].astype(int)
    # "-" é zero absoluto na SIDRA; "..", "..." e "X" (não aplicável/sigilo) viram NaN
    saida["valor"] = pd.to_numeric(df["V"].replace("-", "0"), errors="coerce")
    print(f"  {nome}: {len(saida)} linhas, {saida['cdi'].nunique()} municípios")
    return saida


def colunas(df, mapa, filtro=None, coluna="v"):
    """Pivota `df` para uma linha por município, renomeando `coluna` segundo `mapa`."""
    if filtro is not None:
        df = df[filtro(df)]
    p = df.pivot_table(index="cdi", columns=coluna, values="valor", aggfunc="first")
    return p[list(mapa)].rename(columns=mapa)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-cache", action="store_true")
    usar_cache = not ap.parse_args().sem_cache
    S = lambda *a, **k: sidra(*a, usar_cache=usar_cache, **k)

    print("Baixando...")
    # População, área, densidade
    t = S("pop", 4714, "93,6318,614", 2022)
    base = colunas(t, {93: "pop_2022", 6318: "area_km2", 614: "densidade"})

    # Cor ou raça (percentual sobre o total)
    t = S("cor", 9605, 93, 2022, {86: "95251,2776,2777,2778,2779,2780"})
    cor = t.pivot_table(index="cdi", columns="c_Cor ou raça", values="valor", aggfunc="first")
    cor = cor.rename(columns={95251: "tot", 2776: "branca", 2777: "preta", 2778: "amarela",
                              2779: "parda", 2780: "indigena"})
    pct = pd.DataFrame({f"pct_{c}": 100 * cor[c] / cor["tot"]
                        for c in ["branca", "preta", "parda", "amarela", "indigena"]})
    pct["pct_preta_parda"] = pct["pct_preta"] + pct["pct_parda"]

    # Situação do domicílio -> % rural
    t = S("rural", 9923, 93, 2022, {1: "6795,2"})
    r = t.pivot_table(index="cdi", columns="c_Situação do domicílio", values="valor", aggfunc="first")
    rural = pd.DataFrame({"pct_rural": 100 * r[2] / r[6795]})

    # Idade mediana, envelhecimento, razão de sexo
    t = S("idade", 9515, "10612,10613,8845", 2022)
    idade = colunas(t, {10612: "indice_envelhecimento", 10613: "idade_mediana", 8845: "razao_sexo"})

    # Escolarização 6 a 14 anos
    t = S("escol", 10139, 12805, 2022, {2: 6794, 58: 31615, 839: 46583})
    escol = colunas(t, {12805: "escolarizacao_6_14"})

    # Analfabetismo 15+
    t = S("analf", 10135, 10267, 2022, {2: 6794, 58: 95253, 86: 95251, 839: 46583})
    analf = colunas(t, {10267: "analfabetismo_15mais"})

    # Anos médios de estudo (11+)
    t = S("estudo", 10062, 13285, 2022, {2: 6794, 58: 95253, 86: 95251})
    estudo = colunas(t, {13285: "anos_estudo_11mais"})

    # Rendimento do trabalho (ocupados 14+)
    t = S("renda", 10280, "13536,13537", 2022, {2: 6794, 11913: 96165})
    renda = colunas(t, {13536: "rendimento_medio", 13537: "rendimento_mediano"})

    # Nível de ocupação (substituto da desocupação, que o Censo 2022 não publica por município)
    t = S("ocup", 10268, "140,696", 2022, {2: 6794, 86: 95251, 58: 95253})
    o = t.pivot_table(index="cdi", columns="v", values="valor", aggfunc="first")
    ocup = pd.DataFrame({"nivel_ocupacao_10mais": 100 * o[696] / o[140]})

    # Religião (15+)
    t = S("religiao", 10198, 950, 2022, {133: "95278,95263,95277,2826,2827,2836", 58: 95253, 59: 93024})
    r = t.pivot_table(index="cdi", columns="c_Religião", values="valor", aggfunc="first")
    rel = pd.DataFrame({
        "pct_catolica": 100 * r[95263] / r[95278],
        "pct_evangelica": 100 * r[95277] / r[95278],
        "pct_espirita": 100 * r[2826] / r[95278],
        "pct_umbanda_candomble": 100 * r[2827] / r[95278],
        "pct_sem_religiao": 100 * r[2836] / r[95278],
    })

    # Filhos tidos nascidos vivos por mulher de 12+ (não é a taxa de fecundidade total)
    t = S("filhos", 10078, "13315,13316", 2022)
    if t.groupby(["cdi", "v"]).size().max() != 1:
        raise RuntimeError("filhos: mais de uma linha por município/variável; confira as classificações")
    f = t.pivot_table(index="cdi", columns="v", values="valor", aggfunc="first")
    filhos = pd.DataFrame({"filhos_por_mulher_12mais": f[13316] / f[13315]})

    # PIB 2023 (per capita sobre a população do Censo 2022: não há estimativa de 2023); estrutura produtiva de 2021,
    # pois o valor adicionado por setor só está publicado até 2021
    t = S("pib", 5938, 37, 2023)
    p = colunas(t, {37: "pib_mil_reais_2023"})
    p["pop_2022"] = base["pop_2022"]
    t = S("vab", 5938, "498,513,517,6575,525", 2021)
    v = colunas(t, {498: "vab", 513: "vab_agro", 517: "vab_industria", 6575: "vab_servicos",
                    525: "vab_adm_publica"})
    pib = pd.DataFrame({
        "pib_mil_reais_2023": p["pib_mil_reais_2023"],
        "pib_per_capita_2023": 1000 * p["pib_mil_reais_2023"] / p["pop_2022"],
        "pct_vab_agro_2021": 100 * v["vab_agro"] / v["vab"],
        "pct_vab_industria_2021": 100 * v["vab_industria"] / v["vab"],
        "pct_vab_servicos_2021": 100 * v["vab_servicos"] / v["vab"],
        "pct_vab_adm_publica_2021": 100 * v["vab_adm_publica"] / v["vab"],
    })

    df = base.join([pct, rural, idade, escol, analf, estudo, renda, ocup, rel, filhos, pib], how="outer")
    df = df.reset_index()

    mun = pd.read_csv(MUNICIPIOS, dtype={"mun": str})
    mun = mun[["uf", "mun", "nome", "cdi"]].rename(columns={"mun": "cod_tse", "nome": "municipio"})
    df = mun.merge(df, on="cdi", how="outer", indicator=True)
    sem_tse = df[df["_merge"] == "right_only"]
    sem_ibge = df[df["_merge"] == "left_only"]
    print(f"IBGE sem código TSE: {len(sem_tse)}; TSE sem dado IBGE: {len(sem_ibge)}")
    if len(sem_ibge):
        print(sem_ibge[["uf", "cod_tse", "municipio", "cdi"]].head(10).to_string(index=False))
    df = df.drop(columns="_merge").sort_values(["uf", "cod_tse"], na_position="last")
    df.to_csv(SAIDA, index=False, float_format="%.4f")
    print(f"Gravado {SAIDA}: {len(df)} linhas, {df.shape[1]} colunas")
    print("Faltantes por coluna:")
    print(df.isna().sum()[lambda s: s > 0].to_string())


if __name__ == "__main__":
    main()
