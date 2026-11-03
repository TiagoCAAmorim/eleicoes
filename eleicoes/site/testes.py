"""Dados das páginas de testes do site (governador, prefeito, teste de estresse).

Não roda nenhum modelo: lê os rejogos já gravados em resultados/ (scripts/governador.py, prefeito.py,
primeiro_turno.py e estresse.py) e monta, para cada página,

- um JSON com a previsão de cada eleição (ou apuração sintética) a cada % apurado, que testes.js desenha;
- as tabelas HTML de cobertura por % apurado e o índice das eleições.

Cada eleição entra com a configuração adotada em docs/governador.md, prefeito.md, primeiro-turno.md e estresse.md.
"""
import html
import json
import os

import pandas as pd

from ..caminhos import COMUM, DADOS, RESULTADOS

# configuração adotada de cada teste (ver docs/)
GOV_T2_SEM_PESQUISA = "media_p3"
GOV_T2_COM_PESQUISA = "pesquisa_o3_p3_antes2"
PREF_T2 = "media_c6"
PREF_T2_VIES = {"forte": "v0.3", "moderado": "v0.1"}
PCTS = [0, 1, 3, 5, 10, 20, 30, 50, 70, 90]
COLS_BANDA = ["media", "p05", "p25", "p75", "p95"]


def _r(x, n=1):
    return None if pd.isna(x) else round(float(x), n)


def _num(x, n=1):
    return f"{x:.{n}f}".replace(".", ",")


def _pct(x):
    return f"{100 * x:.0f}%"


def _titulo_nome(s):
    """Nomes do TSE vêm em maiúsculas; deixa só a inicial de cada palavra maiúscula (DE, DA, DO em minúsculas)."""
    if not isinstance(s, str):
        return ""
    minusc = {"DE", "DA", "DO", "DAS", "DOS", "E", "D'"}
    return " ".join(p.lower() if p in minusc and i else p.capitalize() for i, p in enumerate(s.split()))


def _municipios():
    m = pd.read_csv(os.path.join(COMUM, "municipios.csv"), dtype={"mun": str})
    return {r.mun: _titulo_nome(r.nome) for r in m.itertuples()}


def _series(g, cols, chave_rodada="rodada"):
    """{rodada: {pct: linha}} completando o ponto 0 (gravado só numa rodada, igual para todas)."""
    por_rodada = {}
    zero = g[g["pct"] == 0]
    for rod, x in g[g["pct"] > 0].groupby(chave_rodada):
        por_rodada[rod] = pd.concat([zero, x]).drop_duplicates("pct").set_index("pct").reindex(PCTS)[cols]
    if not por_rodada and len(zero):
        por_rodada[zero[chave_rodada].iloc[0]] = zero.set_index("pct").reindex(PCTS)[cols]
    return por_rodada


def _banda(linha):
    return [_r(linha[c]) for c in COLS_BANDA]


def _tabela(cab, linhas, num=(), classe=""):
    esc = html.escape
    th = "".join(f'<th class="num">{esc(c)}</th>' if i in num else f"<th>{esc(c)}</th>" for i, c in enumerate(cab))
    tr = "\n".join("<tr>" + "".join(f'<td class="num">{v}</td>' if i in num else f"<td>{v}</td>"
                                     for i, v in enumerate(l)) + "</tr>" for l in linhas)
    cl = f' class="{classe}"' if classe else ""
    return f'<div class="tabela-rolagem"><table{cl}><thead><tr>{th}</tr></thead><tbody>\n{tr}\n</tbody></table></div>'


def _resumo_pct(d, pct_col="pct", erradas=None):
    """Tabela de cobertura por % apurado (linhas já filtradas na configuração adotada)."""
    linhas = []
    for p, x in d.groupby(pct_col):
        l = [f"{_num(p, 0)}%", _pct(x["cobre90"].mean()), _pct(x["cobre50"].mean()), _num(x["largura90"].mean()),
             _num(x["erro"].abs().mean() if "erro" in x else x["erro_abs"].mean())]
        if erradas is not None:
            l.append(str(int(x[erradas].sum())))
        linhas.append(l)
    cab = ["% apurado", "Cobertura 90%", "Cobertura 50%", "Largura 90% (pontos)", "Erro médio (pontos)"]
    if erradas is not None:
        cab.append("Chamadas erradas")
    return _tabela(cab, linhas, range(1, len(cab)))


# ---------------------------------------------------------------------------------------------------------------
# 2º turno (governador e prefeito): uma série por eleição, % de A nos válidos


def _eleicao_t2(id_, rotulo, ano, g, nomes, real, extra=None):
    rod = _series(g, COLS_BANDA + ["prob_A"])
    cob = g[g["pct"] > 0]
    return {
        "id": id_, "rotulo": rotulo, "ano": int(ano), **nomes, "real": _r(real, 2), **(extra or {}),
        "rodadas": [{"pontos": [_banda(l) + [_r(l["prob_A"], 3)] for _, l in s.iterrows()]} for s in rod.values()],
        "cobre90": round(float(cob["cobre90"].mean()), 3),
        "erro0": _r(g[g["pct"] == 0]["erro"].abs().mean()),
        "errou": bool(g["errou_lado"].any()),
    }


def governador_t2():
    d = pd.read_csv(os.path.join(RESULTADOS, "governador", "previsoes.csv"))
    com = d[d["variante"] == GOV_T2_COM_PESQUISA]
    sem = d[d["variante"] == GOV_T2_SEM_PESQUISA]
    ids_com = set(zip(com["ano"], com["uf"]))
    adot = pd.concat([com, sem[[(a, u) not in ids_com for a, u in zip(sem["ano"], sem["uf"])]]])
    nomes = {}
    for ano in sorted(adot["ano"].unique()):
        v = pd.read_csv(os.path.join(DADOS, "historico", str(ano), "votos_mun.csv.gz"),
                        usecols=["turno", "cargo", "uf", "numero", "nome", "partido", "votos"])
        v = v[v["cargo"] == 3]
        for uf, x in v.groupby(v["uf"].str.lower()):
            dois = x[x["turno"] == 2]["numero"].unique()
            if len(dois) != 2:
                continue
            t1 = x[(x["turno"] == 1) & x["numero"].isin(dois)].groupby("numero")["votos"].sum().sort_values()
            info = x[x["turno"] == 2].drop_duplicates("numero").set_index("numero")
            a, b = t1.index[-1], t1.index[0]
            nomes[(ano, uf)] = {"A": _titulo_nome(info.loc[a, "nome"]), "pA": info.loc[a, "partido"],
                                "B": _titulo_nome(info.loc[b, "nome"]), "pB": info.loc[b, "partido"]}
    eleicoes = []
    for (ano, uf), g in adot.groupby(["ano", "uf"]):
        n = nomes.get((ano, uf), {"A": "A", "pA": "", "B": "B", "pB": ""})
        eleicoes.append(_eleicao_t2(f"{ano}-{uf}", f"{uf.upper()} {ano}", ano, g, n, g["real"].iloc[0],
                                    {"uf": uf.upper(), "pesquisa": bool((ano, uf) in ids_com)}))
    return eleicoes, adot


def prefeito_t2():
    muns = _municipios()
    eleicoes, adot_todas = {}, []
    cand = {}
    for vies, suf in PREF_T2_VIES.items():
        d = pd.read_csv(os.path.join(RESULTADOS, "prefeito", f"previsoes_{suf}.csv"), dtype={"mun": str})
        d = d[d["variante"] == PREF_T2].copy()
        d["mun"] = d["mun"].str.zfill(5)
        d["vies"] = vies
        adot_todas.append(d)
        for ano in sorted(d["ano"].unique()):
            if ano in cand:
                continue
            with open(os.path.join(DADOS, "historico", str(ano), "prefeito_secoes.json"), encoding="utf-8") as f:
                cid = json.load(f)["cidades"]
            c = pd.read_csv(os.path.join(DADOS, "historico", str(ano), "candidatos.csv.gz"),
                            dtype={"ue": str, "numero": str}, usecols=["cargo", "ue", "numero", "nome", "partido"])
            c = c[c["cargo"] == 11].drop_duplicates(["ue", "numero"]).set_index(["ue", "numero"])
            cand[ano] = {}
            for mun, info in cid.items():
                par = {}
                for k in "AB":
                    chave = (mun.zfill(5), str(info[k]))
                    par[k] = _titulo_nome(c.loc[chave, "nome"]) if chave in c.index else k
                    par["p" + k] = c.loc[chave, "partido"] if chave in c.index else ""
                cand[ano][mun.zfill(5)] = par
        for (ano, mun), g in d.groupby(["ano", "mun"]):
            uf = g["uf"].iloc[0].upper()
            id_ = f"{ano}-{mun}"
            e = eleicoes.setdefault(id_, {
                "id": id_, "rotulo": f"{muns.get(mun, mun)} ({uf}) {ano}", "ano": int(ano), "uf": uf,
                "cidade": muns.get(mun, mun), "secoes": int(g["secoes"].iloc[0]),
                **cand.get(ano, {}).get(mun, {"A": "A", "pA": "", "B": "B", "pB": ""}),
                "real": _r(g["real"].iloc[0], 2), "vies": {}})
            x = _eleicao_t2(id_, "", ano, g, {}, g["real"].iloc[0])
            e["vies"][vies] = {k: x[k] for k in ["rodadas", "cobre90", "erro0", "errou"]}
    lista = sorted(eleicoes.values(), key=lambda e: (e["ano"], e["cidade"]))
    return lista, pd.concat(adot_todas)


# ---------------------------------------------------------------------------------------------------------------
# 1º turno (governador, senador, prefeito): uma série por candidato nomeado

COLS_T1 = COLS_BANDA + ["prob_1o", "prob_top2", "prob_eleito"]


def _eleicao_t1(id_, rotulo, ano, g, info, extra=None):
    """g = linhas de uma eleição (todas as rodadas), info = entrada de eleicoes.json."""
    reais = {c["nome"]: c for c in info.get("candidatos", [])}
    cands = (g.drop_duplicates("candidato").sort_values("pos_real")[["candidato", "pos_real", "real"]])
    rodadas = []
    for rod, x in g[g["pct"] > 0].groupby("rodada"):
        x = pd.concat([g[g["pct"] == 0], x])
        r = {"prob2t": [], "cands": []}
        dois = x.drop_duplicates("pct").set_index("pct").reindex(PCTS)["prob_2o_turno"]
        r["prob2t"] = [_r(v, 3) for v in dois]
        for c in cands["candidato"]:
            s = x[x["candidato"] == c].drop_duplicates("pct").set_index("pct").reindex(PCTS)
            r["cands"].append([_banda(l) + [_r(l[k], 3) for k in COLS_T1[5:]] for _, l in s.iterrows()])
        rodadas.append(r)
    top3 = g[(g["pct"] > 0) & (g["pos_real"] <= 3)]
    errou = bool(g[["errado_1o", "errado_top2", "errado_eleito"]].any().any())
    return {
        "id": id_, "rotulo": rotulo, "ano": int(ano), **(extra or {}),
        "candidatos": [{"nome": _titulo_nome(c.candidato), "partido": reais.get(c.candidato, {}).get("partido", ""),
                        "pos": int(c.pos_real), "real": _r(c.real, 2)} for c in cands.itertuples()],
        "rodadas": rodadas,
        "cobre90": round(float(top3["cobre90"].mean()), 3),
        "erro0": _r(g[(g["pct"] == 0) & (g["pos_real"] <= 3)]["erro"].abs().mean()),
        "errou": errou,
    }


def _json_eleicoes(cargo):
    with open(os.path.join(RESULTADOS, "primeiro-turno", cargo, "eleicoes.json"), encoding="utf-8") as f:
        return json.load(f)


def primeiro_turno_uf(cargo):
    d = pd.read_csv(os.path.join(RESULTADOS, "primeiro-turno", cargo, "previsoes.csv"))
    info = _json_eleicoes(cargo)
    out = []
    for (ano, uf), g in d.groupby(["ano", "uf"]):
        if cargo == "presidente":  # uma eleição por ano, no Brasil inteiro (eleicoes.json usa a chave "<ano>|None")
            e = _eleicao_t1(str(ano), f"Presidente {ano}", ano, g, info.get(f"{ano}|None", {}), {"uf": "BR"})
        else:
            e = _eleicao_t1(f"{ano}-{uf}", f"{uf.upper()} {ano}", ano, g, info.get(f"{ano}|{uf}", {}),
                            {"uf": uf.upper()})
        e["vagas"] = 2 if cargo == "senador" and ano in (2010, 2018) else 1
        out.append(e)
    return out, d


def prefeito_t1():
    d = pd.read_csv(os.path.join(RESULTADOS, "primeiro-turno", "prefeito", "previsoes.csv"), dtype={"uf": str})
    d["mun"] = d["uf"].str.zfill(5)
    d["vies_nome"] = d["vies"].str.split(" ").str[0]
    info = _json_eleicoes("prefeito")
    muns = _municipios()
    out = {}
    for (ano, mun), g in d.groupby(["ano", "mun"]):
        i = info.get(f"{ano}|{mun}", {})
        uf = str(i.get("uf", "")).upper()
        id_ = f"{ano}-{mun}"
        e = out.setdefault(id_, {"id": id_, "rotulo": f"{muns.get(mun, mun)} ({uf}) {ano}", "ano": int(ano),
                                 "uf": uf, "cidade": muns.get(mun, mun), "vies": {}})
        for vies, x in g.groupby("vies_nome"):
            # cada viés tem uma rodada só: o ponto 0 (sem votos) é o mesmo
            x = x.assign(rodada=0)
            r = _eleicao_t1(id_, "", ano, x, i)
            e["candidatos"] = r["candidatos"]
            e["vies"][vies] = {k: r[k] for k in ["rodadas", "cobre90", "erro0", "errou"]}
    return sorted(out.values(), key=lambda e: e["cidade"]), d


def _resumo_t1(d):
    x = d[d["pos_real"] <= 3].copy()
    x["erradas"] = x[["errado_1o", "errado_top2", "errado_eleito"]].any(axis=1)
    # chamadas erradas contadas por eleição e momento, não por candidato
    linhas = []
    for p, y in x.groupby("pct"):
        chaves = [c for c in ["ano", "uf", "rodada", "vies"] if c in y]
        err = y.groupby(chaves)["erradas"].any().sum()
        linhas.append([f"{_num(p, 0)}%", _pct(y["cobre90"].mean()), _pct(y["cobre50"].mean()),
                       _num(y["largura90"].mean()), _num(y["erro"].abs().mean()), str(int(err))])
    return _tabela(["% apurado", "Cobertura 90%", "Cobertura 50%", "Largura 90% (pontos)", "Erro médio (pontos)",
                    "Chamadas erradas"], linhas, range(1, 6))


# ---------------------------------------------------------------------------------------------------------------
# índice das eleições (tabela clicável)

def _indice(eleicoes, colunas, sufixo_vies=None):
    linhas = []
    for e in eleicoes:
        x = e["vies"][sufixo_vies] if sufixo_vies else e
        if x is None:
            continue
        link = f'<a href="#{html.escape(e["id"])}" data-eleicao="{html.escape(e["id"])}">{html.escape(e["rotulo"])}</a>'
        linhas.append([link] + [f(e) for _, f in colunas] + [
            _num(x["erro0"]) if x["erro0"] is not None else "–", _pct(x["cobre90"]),
            '<span class="neg">sim</span>' if x["errou"] else "não"])
    cab = ["Eleição"] + [c for c, _ in colunas] + ["Erro antes de abrir", "Cobertura 90%", "Chamada errada"]
    n = len(colunas)
    return _tabela(cab, linhas, range(n + 1, n + 3), classe="indice")


def _venc_t2(e):
    venc, perd = (e["A"], e["B"]) if e["real"] >= 50 else (e["B"], e["A"])
    return f'{html.escape(venc)} {_num(max(e["real"], 100 - e["real"]))}% x {html.escape(perd)}'


def _primeiros_t1(e):
    c = sorted(e["candidatos"], key=lambda c: c["pos"])[:2]
    return " · ".join(f'{html.escape(x["nome"])} {_num(x["real"])}%' for x in c)


# ---------------------------------------------------------------------------------------------------------------
# teste de estresse

ESTRESSE = [
    # (ano, pasta, variantes [(id, nome)]); a primeira é a que a página mostra de início
    (2010, "estresse-historico/2010", [("calibrado_cauteloso", "Modelo adotado"),
                                       ("revisado", "Matriz da eleição anterior")]),
    (2014, "estresse-historico/2014", [("calibrado_cauteloso", "Modelo adotado"),
                                       ("revisado", "Matriz da eleição anterior")]),
    (2018, "estresse-historico/2018", [("calibrado_cauteloso", "Modelo adotado"),
                                       ("revisado", "Matriz da eleição anterior")]),
    (2022, "estresse", [("revisado", "Modelo revisado (priori da eleição anterior)"),
                        ("ao_vivo", "Modelo do dia (25/10/2026)")]),
]


def estresse():
    anos = []
    tabelas = {}
    for ano, pasta, variantes in ESTRESSE:
        d = pd.read_csv(os.path.join(RESULTADOS, pasta, "previsoes.csv"))
        rodadas = []
        for rod, g in d.groupby("rodada"):
            r = {"n": int(rod) + 1, "beta": _r(g["beta"].iloc[0], 3), "gama": _r(g["gama"].iloc[0], 3),
                 "final": _r(g["final"].iloc[0], 2), "parcial": None, "var": {}}
            for v, _ in variantes:
                s = g[g["variante"] == v].drop_duplicates("pct_secoes").set_index("pct_secoes").reindex(PCTS)
                if r["parcial"] is None:
                    r["parcial"] = [None if not p else _r(s.loc[p, "parcial_A"]) for p in PCTS]
                r["var"][v] = [_banda(l) + [_r(l["prob_A"], 3)] for _, l in s.iterrows()]
            rodadas.append(r)
        anos.append({"ano": ano, "variantes": [{"id": v, "nome": n} for v, n in variantes], "rodadas": rodadas})
        tabelas[ano] = d
    return anos, tabelas


def _resumo_estresse(tabelas):
    """Cobertura de 90% por % apurado, variante adotada de cada ano (2022: modelo revisado e modelo do dia)."""
    cal = pd.read_csv(os.path.join(RESULTADOS, "calibracao-priori", "estresse_resumo.csv"))
    vivo = pd.read_csv(os.path.join(RESULTADOS, "estresse", "resumo.csv"))

    def por_pct(x, variante):
        x = x[x["variante"] == variante].copy()
        x["pct_secoes"] = pd.to_numeric(x["pct_secoes"], errors="coerce")
        return x.dropna(subset=["pct_secoes"]).astype({"pct_secoes": int}).set_index("pct_secoes")

    cal, vivo = por_pct(cal, "calibrado_cauteloso"), por_pct(vivo, "ao_vivo")
    cols = {}
    for ano in (2010, 2014, 2018):
        x = tabelas[ano]
        x = x[x["variante"] == "calibrado_cauteloso"]
        inter = (x["p05"] <= x["final"]) & (x["final"] <= x["p95"])
        cols[str(ano)] = inter.groupby(x["pct_secoes"]).mean()
    cols["2022"] = cal["cobre90"]
    cols["2022, modelo do dia"] = vivo["cobre90"]
    linhas = []
    for p in PCTS:
        linhas.append([f"{p}%"] + [_pct(c.get(p, float("nan"))) if p in c.index else "–" for c in cols.values()])
    return _tabela(["% apurado"] + list(cols), linhas, range(1, len(cols) + 1))


# ---------------------------------------------------------------------------------------------------------------

def exportar(pasta_dados):
    """Grava os JSON das páginas em `pasta_dados` e devolve os trechos HTML ({{chave}}) das páginas."""
    os.makedirs(pasta_dados, exist_ok=True)
    out = {}

    gov2, d_gov2 = governador_t2()
    gov1, d_gov1 = primeiro_turno_uf("governador")
    sen1, d_sen1 = primeiro_turno_uf("senador")
    with open(os.path.join(pasta_dados, "governador.json"), "w", encoding="utf-8") as f:
        json.dump({"pcts": PCTS, "t2": gov2, "t1": gov1, "senador": sen1}, f, ensure_ascii=False,
                  separators=(",", ":"))
    out["gov_t2_resumo"] = _resumo_pct(d_gov2, erradas="errou_lado")
    out["gov_t2_indice"] = _indice(gov2, [("Resultado", _venc_t2),
                                          ("Pesquisa", lambda e: "sim" if e["pesquisa"] else "não")])
    out["gov_t1_resumo"] = _resumo_t1(d_gov1)
    out["gov_t1_indice"] = _indice(gov1, [("1º e 2º no 1º turno", _primeiros_t1)])
    out["sen_resumo"] = _resumo_t1(d_sen1)
    out["sen_indice"] = _indice(sen1, [("Mais votados", _primeiros_t1)])
    out["gov_t2_n"] = str(len(gov2))
    out["gov_t2_n_pesquisa"] = str(sum(e["pesquisa"] for e in gov2))
    out["gov_t1_n"] = str(len(gov1))
    out["sen_n"] = str(len(sen1))

    pres1, d_pres1 = primeiro_turno_uf("presidente")
    with open(os.path.join(pasta_dados, "presidente.json"), "w", encoding="utf-8") as f:
        json.dump({"pcts": PCTS, "t1": pres1}, f, ensure_ascii=False, separators=(",", ":"))
    out["pres_t1_resumo"] = _resumo_t1(d_pres1)
    out["pres_t1_indice"] = _indice(pres1, [("1º e 2º no 1º turno", _primeiros_t1)])
    pesq = pd.read_csv(os.path.join(DADOS, "pesquisas", "presidente_t1.csv"))
    linhas = []
    for e in pres1:
        p = pesq[pesq["ano"] == e["ano"]].sort_values("validos", ascending=False)
        reais = {c["nome"].upper(): c["real"] for c in e["candidatos"]}
        for r in p.head(2).itertuples():
            real = next((v for k, v in reais.items() if _titulo_nome(r.candidato).upper() == k), None)
            linhas.append([str(e["ano"]), html.escape(_titulo_nome(r.candidato)), _num(float(r.validos)),
                           _num(real) if real is not None else "–",
                           f'<a href="{html.escape(r.fonte)}" rel="noopener">{html.escape(r.instituto)}</a>'])
    out["pres_t1_pesquisas"] = _tabela(["Ano", "Candidato", "Pesquisa (% válidos)", "Resultado", "Fonte"],
                                       linhas, (2, 3))

    pref2, d_pref2 = prefeito_t2()
    pref1, d_pref1 = prefeito_t1()
    with open(os.path.join(pasta_dados, "prefeito.json"), "w", encoding="utf-8") as f:
        json.dump({"pcts": PCTS, "t2": pref2, "t1": pref1}, f, ensure_ascii=False, separators=(",", ":"))
    for vies in PREF_T2_VIES:
        x = d_pref2[d_pref2["vies"] == vies]
        out[f"pref_t2_resumo_{vies}"] = _resumo_pct(x, erradas="errou_lado")
        p1 = d_pref1[d_pref1["vies_nome"] == vies]
        out[f"pref_t1_resumo_{vies}"] = _resumo_t1(p1)
    out["pref_t2_indice"] = _indice(pref2, [("Resultado", _venc_t2)], sufixo_vies="moderado")
    out["pref_t1_indice"] = _indice(pref1, [("1º e 2º no 1º turno", _primeiros_t1)], sufixo_vies="moderado")
    out["pref_t2_n"] = str(len(pref2))
    out["pref_t1_n"] = str(len(pref1))

    est, tabelas = estresse()
    with open(os.path.join(pasta_dados, "estresse.json"), "w", encoding="utf-8") as f:
        json.dump({"pcts": PCTS, "anos": est}, f, ensure_ascii=False, separators=(",", ":"))
    out["estresse_resumo"] = _resumo_estresse(tabelas)
    return out
