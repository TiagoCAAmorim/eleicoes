"""Rejogos do modelo do 1º turno (etapa 6 do roteiro, docs/primeiro-turno.md).

Para cada eleição (presidente, governador, senador por UF), monta a base por município com a eleição de referência
(1º turno presidencial de 4 anos antes), simula a apuração com a ordem sintética de scripts/calibrar_priori.py
(com viés nas primeiras seções de cada cidade, agora em vários candidatos) e mede, por % apurado:

- erro, cobertura 50/90% e CRPS da votação (% dos válidos) de cada candidato nomeado;
- Brier e "chamadas erradas" (mais de 99% para o que não aconteceu) de: vencer no 1º turno, ir ao 2º turno
  (ficar entre os 2 primeiros) e ser o 1º colocado.

Antes da apuração o modelo parte de uma pesquisa. Sem a pesquisa real da véspera registrada, usa uma "pesquisa
sintética": o resultado verdadeiro de cada candidato mais um erro sorteado com o desvio típico das pesquisas
(--erro-pesquisa, em pontos). A previsão de antes da apuração mede só se a faixa é honesta para esse erro.

    python scripts/primeiro_turno.py --cargo presidente --rodadas 3
    python scripts/primeiro_turno.py --cargo governador --rodadas 2
Saídas em resultados/primeiro-turno/<cargo>/.
"""
import argparse
import dataclasses
import json
import os
import time

import numpy as np
import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import DADOS, RESULTADOS
from eleicoes.dados import historico as hist
from eleicoes.modelos import primeiro_turno as m1
from calibrar_priori import ordem_municipios
from rejogar_2026 import crps

OUT = os.path.join(RESULTADOS, "primeiro-turno")
PONTOS = [0, 1, 3, 5, 10, 20, 30, 50, 70, 90]
ANOS = {"presidente": [2010, 2014, 2018, 2022, 2026], "governador": [2010, 2014, 2018, 2022],
        "senador": [2010, 2014, 2018, 2022], "prefeito": [2008, 2012, 2016, 2020, 2024]}
ERRO_PESQUISA = {"presidente": 2.0, "governador": 3.0, "senador": 3.0, "prefeito": 3.0}
# prefeito: a unidade é a seção, sem eleição de referência; grupos = zonas eleitorais; as seções chegam inteiras e
# em blocos de zona, então o que falta pode estar todo de um lado da cidade (choque comum de 8% no log, como os 6% na
# margem do 2º turno de prefeito)
PREFEITO = {"niveis": ["zona"], "choque_nacional": 0.0, "choque_parcial": 0.0, "choque_uf": 0.08}
C = {"sd_celula": 0.5, "tau": 0.15}
VARIANTES = {
    "base": {},
    "e1": {**C},
    "e1_r5": {**C, "rho_grupos": 0.5},
    "e02_r5": {**C, "rho_grupos": 0.5, "escala_pesquisa": 0.2},
    "e1_r5_t3": {**C, "rho_grupos": 0.5, "tau": 0.3},
    "t3_p4": {**C, "rho_grupos": 0.5, "tau": 0.3, "choque_parcial": 0.04},
    "t3_p6": {**C, "rho_grupos": 0.5, "tau": 0.3, "choque_parcial": 0.06},
    "t3_p4_i10": {**C, "rho_grupos": 0.5, "tau": 0.3, "choque_parcial": 0.04, "choque_uf_inicio": 0.10},
    "t5_p4": {**C, "rho_grupos": 0.5, "tau": 0.5, "choque_parcial": 0.04},
    "t5_p4_r0": {**C, "rho_grupos": 0.0, "tau": 0.5, "choque_parcial": 0.04, "sd_pesquisa": 4.5},
    "t5_p4_r25": {**C, "rho_grupos": 0.25, "tau": 0.5, "choque_parcial": 0.04, "sd_pesquisa": 4.5},
    "t7_p4": {**C, "rho_grupos": 0.5, "tau": 0.7, "choque_parcial": 0.04, "sd_pesquisa": 4.5},
    "t5_p6_s45": {**C, "rho_grupos": 0.5, "tau": 0.5, "choque_parcial": 0.06, "sd_pesquisa": 4.5},
    # adotada (padrão de eleicoes/modelos/primeiro_turno.Config, igual a t5_p4_r25)
    "adotada": {},
    "adotada_p8": {"choque_parcial": 0.08},
    "g2": {"choque_grupo_inicio": 0.2},
    "pg2": {"choque_grupo_inicio": 0.2},
    "pg2_c4": {"choque_grupo_inicio": 0.2, "choque_uf": 0.04},
    "g4": {"choque_grupo_inicio": 0.4},
    "g4_p8": {"choque_grupo_inicio": 0.4, "choque_parcial": 0.08},
    "g6_p8": {"choque_grupo_inicio": 0.6, "choque_parcial": 0.08},
    # numa UF só não há choque nacional separado do da UF; um grupo grande ainda sem votos (a capital) pode votar bem
    # diferente do interior já apurado (AM 2018: Wilson Lima): desvio extra de 0,2 por grupo não apurado (g2)
    "uf_unica": {"choque_nacional": 0.0, "choque_grupo_inicio": 0.2},
}


def base_2026():
    """1º turno de 2026: só Lula, Flávio e os demais somados (dados/2026/presidente/mun_t1.csv.gz); referência = 1º
    turno de 2022."""
    t = pd.read_csv(os.path.join(DADOS, "2026", "presidente", "mun_t1.csv.gz"), dtype={"mun": str})
    b = t.rename(columns={"A": "d0", "B": "d1", "O": "d2"})
    b["d3"] = t["brancos"] + t["nulos"]
    b = b[["uf", "mun", "E", "d0", "d1", "d2", "d3", "C"]].set_index("mun")
    v, c = hist._votos_cargo(2022, 1)
    rt = v.groupby("partido")["votos"].sum().sort_values(ascending=False)
    partidos = list(rt.index[:3])
    rp = v.pivot_table(index="mun", columns="partido", values="votos", aggfunc="sum", fill_value=0)
    c = c.set_index("mun")
    for i, p in enumerate(partidos):
        b[f"r{i}"] = rp[p].reindex(b.index)
    b["r3"] = rp.sum(axis=1).reindex(b.index) - b[["r0", "r1", "r2"]].sum(1)
    b["r4"] = (c["brancos"] + c["nulos"]).reindex(b.index)
    b["rE"] = c["aptos"].reindex(b.index)
    b = b.dropna().reset_index()
    cols = [x for x in b if x not in ("uf", "mun")]
    b[cols] = b[cols].astype(float)
    mun = pd.read_csv(os.path.join(hist.COMUM, "municipios.csv"), dtype={"mun": str})
    b["capital"] = b["mun"].isin(set(mun.loc[mun["capital"], "mun"]))
    b["Ea"] = b["E"]
    val = b[["d0", "d1", "d2"]].sum()
    pct = 100 * val / val.sum()
    info = {"ano": 2026, "cargo": "presidente", "uf": None, "votos_por_eleitor": 1, "partidos_ref": partidos,
            "candidatos": [{"numero": "13", "nome": "LULA", "partido": "PT", "validos": float(pct["d0"])},
                           {"numero": "22", "nome": "FLÁVIO BOLSONARO", "partido": "PL", "validos": float(pct["d1"])}],
            "demais_validos": float(pct["d2"])}
    return b, info


def pesquisa_real(cargo, ano, info):
    """% dos válidos de cada candidato nomeado na pesquisa da véspera (dados/pesquisas/<cargo>_t1.csv), se houver."""
    arq = os.path.join(DADOS, "pesquisas", f"{cargo}_t1.csv")
    if not os.path.exists(arq):
        return None
    t = pd.read_csv(arq, dtype={"numero": str})
    t = t[t["ano"] == ano].groupby("numero")["validos"].mean()
    if not all(c["numero"] in t.index for c in info["candidatos"]):
        return None
    return np.array([t[c["numero"]] for c in info["candidatos"]], float)


def eleicoes(cargo):
    out = []
    for ano in ANOS[cargo]:
        if cargo == "presidente":
            out.append((ano, None))
        elif cargo == "prefeito":
            out += [(ano, m) for m in sorted(bases_prefeito(ano))]
        else:
            v, _ = hist._votos_cargo(ano, hist.CARGOS[cargo])
            out += [(ano, u) for u in sorted(v["uf"].str.lower().unique()) if u not in ("df", "zz")]
    return out


def bases_prefeito(ano, k_max=5, min_validos=5.0, k_min=3):
    """Cidades com mais de 200 mil eleitores: base por seção (dados/historico/<ano>/prefeito_t1_*.csv.gz)."""
    pasta = os.path.join(DADOS, "historico", str(ano))
    if not os.path.exists(os.path.join(pasta, "prefeito_t1_secoes.csv.gz")):
        return {}
    sec = pd.read_csv(os.path.join(pasta, "prefeito_t1_secoes.csv.gz"), dtype={"mun": str})
    vot = pd.read_csv(os.path.join(pasta, "prefeito_t1_votos.csv.gz"), dtype={"mun": str, "numero": str})
    meta = json.load(open(os.path.join(pasta, "prefeito_t1_secoes.json"), encoding="utf-8"))["cidades"]
    # branco/nulo e abstenção de partida: os da cidade na eleição de prefeito anterior (2008: médias típicas)
    ant = {}
    if ano - 4 in ANOS["prefeito"]:
        _, c4 = hist._votos_cargo(ano - 4, 11)
        c4 = c4.set_index("mun")
        ant = {m: ((r["brancos"] + r["nulos"]) / r["aptos"], r["abstencoes"] / r["aptos"]) for m, r in c4.iterrows()}
    out = {}
    for mun, g in sec.groupby("mun"):
        g = g[g["E"] > 0]
        v = vot[vot["mun"] == mun]
        tot = v.groupby("numero")["votos"].sum().sort_values(ascending=False)
        if len(g) < 30 or len(tot) < 2:
            continue
        pct = 100 * tot / tot.sum()
        k = int(min(k_max, max(k_min, (pct >= min_validos).sum()), len(tot)))
        nomeados = list(tot.index[:k])
        pv = v.pivot_table(index=["zona", "secao"], columns="numero", values="votos", aggfunc="sum", fill_value=0)
        g = g.set_index(["zona", "secao"])
        b = pd.DataFrame({"uf": g["uf"].str.lower(), "E": g["E"].astype(float)}, index=g.index)
        for i, n in enumerate(nomeados):
            b[f"d{i}"] = pv[n].reindex(b.index).fillna(0).astype(float)
        b[f"d{k}"] = (pv.sum(axis=1).reindex(b.index).fillna(0) - b[[f"d{i}" for i in range(k)]].sum(axis=1)).clip(lower=0)
        b[f"d{k + 1}"] = g["W"].astype(float)
        b["C"] = np.maximum(g["C"].astype(float), b[[f"d{i}" for i in range(k + 2)]].sum(axis=1))
        b["E"] = np.maximum(b["E"], b["C"])
        b = b.reset_index()
        b["mun"] = b["zona"].astype(str) + "-" + b["secao"].astype(str)
        b["zona"] = b["zona"].astype(str)
        b["nome"], b["capital"], b["Ea"] = mun, False, b["E"]
        nm = meta.get(mun.lstrip("0"), {}).get("candidatos", {})
        info = {"ano": ano, "cargo": "prefeito", "uf": b["uf"].iloc[0], "mun": mun, "votos_por_eleitor": 1,
                "partidos_ref": [], "w_n": ant.get(mun, (0.07, 0.2)),
                "candidatos": [{"numero": n, "nome": nm.get(n, {}).get("nome", n), "partido": "", "validos": float(pct[n])}
                               for n in nomeados], "demais_validos": float(pct.iloc[k:].sum())}
        out[mun] = (b, info)
    return out


def ordem_secoes(base, D, rng, vies_sd=0.3):
    """Instante de chegada de cada seção: início da zona + posição na zona, deslocado por um viés sorteado na direção
    de uma combinação aleatória dos candidatos (seções mais favoráveis a uns chegam antes)."""
    zonas, zi = np.unique(base["zona"].values, return_inverse=True)
    t = 0.6 * rng.uniform(size=len(zonas))[zi] + 0.4 * rng.uniform(size=len(base))
    cand = base[[f"d{i}" for i in range(D - 2)]].values
    sh = cand / np.maximum(cand.sum(1, keepdims=True), 1)
    sc = sh @ rng.normal(0, 1, D - 2)
    z = (sc - sc.mean()) / max(sc.std(), 1e-6)
    return t - rng.normal(0, vies_sd) * z


def retrato_secoes(base, D, chegada, p):
    s = base.copy()
    o = np.argsort(chegada)
    acum = 100 * np.cumsum(base["E"].values[o]) / base["E"].sum()
    fora = o[np.searchsorted(acum, p) + 1:]
    s.loc[fora, ["Ea", "C"] + [f"d{i}" for i in range(D - 1)]] = 0
    return s


_CACHE = {}


def carregar(cargo, ano, uf):
    if cargo == "prefeito":
        if ano not in _CACHE:
            _CACHE.clear()
            _CACHE[ano] = bases_prefeito(ano)
        return _CACHE[ano][uf]
    if cargo == "presidente" and ano == 2026:
        return base_2026()
    return hist.primeiro_turno(ano, cargo, uf)


def mesmo_partido(info):
    K = len(info["candidatos"])
    pr = info["partidos_ref"]
    R, D = len(pr) + 3, K + 3
    mesmo = np.zeros((R, D), bool)
    for i, p in enumerate(pr):
        for j, c in enumerate(info["candidatos"]):
            mesmo[i, j] = c["partido"] == p
    mesmo[R - 2, D - 2] = True
    mesmo[R - 1, D - 1] = True
    return mesmo


def alvo_pesquisa(X, peso, pesquisa, demais, w_n=None):
    """Frações do eleitorado em cada destino: branco/nulo e abstenção como na referência (ou `w_n`); os válidos
    divididos como na pesquisa (% dos válidos de cada candidato nomeado; o resto vai para os demais)."""
    xbar = (X * peso[:, None]).sum(0) / peso.sum()
    w, n = w_n if w_n is not None else (xbar[-2], xbar[-1])
    val = 1 - w - n
    p = np.append(np.asarray(pesquisa, float), max(demais, 0.5))
    p = p / p.sum()
    return np.append(p * val, [w, n])


def retrato(base, D, inicio, duracao, vies, t):
    """Parte apurada de cada município no instante t. As primeiras seções têm a votação de cada candidato
    multiplicada por exp(vies_k * (1 - f)) (viés que some quando o município termina)."""
    f = np.clip((t - inicio) / duracao, 0, 1)
    s = base.copy()
    s["Ea"] = np.round(f * base["E"])
    fr = s["Ea"].values / base["E"].clip(lower=1).values
    cand = base[[f"d{i}" for i in range(D - 2)]].values
    val = cand.sum(1, keepdims=True)
    adj = cand * np.exp(vies[None, :] * (1 - fr)[:, None])
    adj = adj / np.maximum(adj.sum(1, keepdims=True), 1) * val
    ap = np.minimum(np.round(adj * fr[:, None]), cand)
    for i in range(D - 2):
        s[f"d{i}"] = ap[:, i]
    s[f"d{D - 2}"] = np.round(base[f"d{D - 2}"] * fr)
    s["C"] = np.round(base["C"] * fr)
    return s


def vazio(base, D):
    s = base.copy()
    s[["Ea", "C"] + [f"d{i}" for i in range(D - 1)]] = 0.0
    return s


def prever(s, info, pesquisa, cfg):
    K = len(info["candidatos"])
    R = len(info["partidos_ref"]) + 3 if info["partidos_ref"] else 1
    D = K + 3
    df, X, Y = m1.preparar(s, R, D, cfg)
    peso = df["E"].values.astype(float)
    alvo = alvo_pesquisa(X, peso, pesquisa, 100 - sum(pesquisa), info.get("w_n"))
    mesmo = mesmo_partido(info) if R > 1 else np.zeros((1, D), bool)
    th0, xbar = m1.priori(X, peso, alvo, mesmo, cfg)
    aj = m1.ajustar(df, X, Y, th0, xbar, alvo, cfg)
    final = m1.simular(df, X, Y, aj, cfg)
    return m1.resumo(final, [c["nome"] for c in info["candidatos"]], vagas=info.get("vagas", 1),
                     maioria=info.get("maioria", True))


def avaliar(r, info, chave):
    reais = np.array([c["validos"] for c in info["candidatos"]])
    rank_real = np.argsort(np.argsort(-reais))
    vagas, maioria = info.get("vagas", 1), info.get("maioria", True)
    linhas = []
    for i, c in enumerate(r["candidatos"]):
        y = reais[i]
        ev_eleito = (y > 50) if maioria and vagas == 1 else (rank_real[i] < vagas)
        linhas.append({**chave, "candidato": c["nome"], "pos_real": int(rank_real[i]) + 1, "real": y,
                       "media": c["media"], "p05": c["p05"], "p25": c["p25"], "p75": c["p75"], "p95": c["p95"],
                       "crps": crps(c["amostras"], y), "prob_1o": c["prob_1o"], "prob_top2": c["prob_top2"],
                       "prob_eleito": c["prob_eleito_1t"], "ev_1o": rank_real[i] == 0, "ev_top2": rank_real[i] <= 1,
                       "ev_eleito": bool(ev_eleito)})
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cargo", default="presidente", choices=list(ANOS))
    ap.add_argument("--rodadas", type=int, default=2)
    ap.add_argument("--variantes", nargs="+", default=["base"])
    ap.add_argument("--erro-pesquisa", type=float, default=None)
    ap.add_argument("--anos", nargs="*", type=int)
    ap.add_argument("--ufs", nargs="*")
    ap.add_argument("--pontos", nargs="*", type=float, default=PONTOS)
    ap.add_argument("--n-sims", type=int, default=1000)
    ap.add_argument("--saida", default=None)
    ap.add_argument("--vies-secoes", type=float, default=0.3, help="prefeito: viés da ordem das seções (0,1 a 0,3)")
    ap.add_argument("--pesquisa-sintetica", action="store_true", help="usa a pesquisa sintética mesmo quando há a real")
    ap.add_argument("--juntar", nargs="*", help="só junta previsoes.csv destas saídas (pastas em resultados/primeiro-turno/) "
                    "em --saida e refaz o resumo")
    a = ap.parse_args()
    out = os.path.join(OUT, a.saida or a.cargo)
    if a.juntar:
        os.makedirs(out, exist_ok=True)
        res = pd.concat([pd.read_csv(os.path.join(OUT, j, "previsoes.csv")) for j in a.juntar], ignore_index=True)
        res.to_csv(os.path.join(out, "previsoes.csv"), index=False)
        infos = {}
        for j in a.juntar:
            infos.update(json.load(open(os.path.join(OUT, j, "eleicoes.json"), encoding="utf-8")))
        with open(os.path.join(out, "eleicoes.json"), "w", encoding="utf-8") as f:
            json.dump(infos, f, ensure_ascii=False, indent=1)
        resumo = resumir(res)
        resumo.round(4).to_csv(os.path.join(out, "resumo.csv"), index=False)
        pd.set_option("display.width", 250)
        print(resumo.round(3).to_string(index=False))
        return
    os.makedirs(out, exist_ok=True)
    sd_p = a.erro_pesquisa if a.erro_pesquisa is not None else ERRO_PESQUISA[a.cargo]
    linhas, infos = [], {}
    for ano, uf in eleicoes(a.cargo):
        if (a.anos and ano not in a.anos) or (a.ufs and uf not in a.ufs):
            continue
        base, info = carregar(a.cargo, ano, uf)
        if a.cargo == "senador":
            info["vagas"], info["maioria"] = info["votos_por_eleitor"], False
        infos[f"{ano}|{uf}"] = info
        K = len(info["candidatos"])
        D = K + 3
        semente = 0 if uf is None else (int(uf) if uf.isdigit() else 31 * ord(uf[0]) + ord(uf[1]))
        rng = np.random.default_rng(7919 * ano + semente)
        reais = np.array([c["validos"] for c in info["candidatos"]])
        pesquisa = np.clip(reais + rng.normal(0, sd_p, K), 0.5, None)
        real_p = pesquisa_real(a.cargo, ano, info)
        if real_p is not None and not a.pesquisa_sintetica:
            pesquisa = real_p
        for v in a.variantes:
            cfg = m1.Config(**{**VARIANTES[v], "n_sims": a.n_sims, "votos_por_eleitor": info["votos_por_eleitor"]})
            if a.cargo == "prefeito":
                cfg = dataclasses.replace(cfg, **{k: x for k, x in PREFEITO.items() if k not in VARIANTES[v]})
            elif uf is not None:
                cfg = dataclasses.replace(cfg, **{k: x for k, x in VARIANTES["uf_unica"].items()
                                                  if k not in VARIANTES[v]})
            for rd in range(a.rodadas + 1):
                if rd == 0:
                    pts = [0] if 0 in a.pontos else []
                else:
                    pts = [p for p in a.pontos if p > 0]
                    if a.cargo == "prefeito":
                        chegada = ordem_secoes(base, D, rng, a.vies_secoes)
                    inicio, duracao, _ = ordem_municipios(base.assign(E2=base["E"]), rng)
                    vies = rng.normal(0, 0.045, K + 1)
                    ts = np.linspace(0, 2, 2001)
                    pct = np.array([100 * (np.clip((t - inicio) / duracao, 0, 1) * base["E"]).sum() / base["E"].sum()
                                    for t in ts])
                for p in pts:
                    t0 = time.time()
                    if p == 0:
                        s = vazio(base, D)
                    elif a.cargo == "prefeito":
                        s = retrato_secoes(base, D, chegada, p)
                    else:
                        s = retrato(base, D, inicio, duracao, vies, ts[min(np.searchsorted(pct, p), len(ts) - 1)])
                    r = prever(s, info, pesquisa, cfg)
                    ch = {"ano": ano, "uf": uf or "br", "variante": v, "rodada": rd, "pct": p,
                          "prob_2o_turno": r.get("prob_2o_turno", np.nan)}
                    ls = avaliar(r, info, ch)
                    linhas += ls
                    l0 = ls[0]
                    print(f"{ano} {uf or 'br'} {v} r{rd} {p:4.0f}% | " + " | ".join(
                        f"{l['candidato'][:12]} {l['media']:.1f} [{l['p05']:.1f},{l['p95']:.1f}] real {l['real']:.1f}"
                        for l in ls[:3]) + f" | P(eleito) {l0['prob_eleito']:.2f} ({time.time() - t0:.1f}s)", flush=True)
    res = pd.DataFrame(linhas)
    res["erro"] = res["media"] - res["real"]
    res["cobre90"] = (res["p05"] <= res["real"]) & (res["real"] <= res["p95"])
    res["cobre50"] = (res["p25"] <= res["real"]) & (res["real"] <= res["p75"])
    res["largura90"] = res["p95"] - res["p05"]
    for e in ["1o", "top2", "eleito"]:
        pe, ev = res[f"prob_{e}"], res[f"ev_{e}"].astype(float)
        res[f"brier_{e}"] = (pe - ev) ** 2
        res[f"errado_{e}"] = ((pe >= 0.99) & (ev == 0)) | ((pe <= 0.01) & (ev == 1))
    res.round(4).to_csv(os.path.join(out, "previsoes.csv"), index=False)
    with open(os.path.join(out, "eleicoes.json"), "w", encoding="utf-8") as f:
        json.dump(infos, f, ensure_ascii=False, indent=1)
    resumo = resumir(res)
    resumo.round(4).to_csv(os.path.join(out, "resumo.csv"), index=False)
    pd.set_option("display.width", 250)
    print(resumo.round(3).to_string(index=False))


def resumir(res):
    """Por variante e % apurado. Votação: só os dois primeiros colocados reais (os que decidem o 2º turno)."""
    top = res[res["pos_real"] <= 3]
    agg = top.groupby(["variante", "pct"]).agg(
        erro_abs=("erro", lambda e: e.abs().mean()), cobre90=("cobre90", "mean"), cobre50=("cobre50", "mean"),
        largura90=("largura90", "mean"), crps=("crps", "mean"), n=("erro", "size"))
    ev = res.groupby(["variante", "pct"]).agg(
        brier_eleito=("brier_eleito", "mean"), brier_top2=("brier_top2", "mean"), brier_1o=("brier_1o", "mean"),
        erradas_eleito=("errado_eleito", "sum"), erradas_top2=("errado_top2", "sum"),
        erradas_1o=("errado_1o", "sum"))
    return agg.join(ev).reset_index()


if __name__ == "__main__":
    main()
