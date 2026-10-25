"""Leitura dos resultados de divulgação do TSE (resultados.tse.jus.br)."""
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

BASE = "https://resultados.tse.jus.br/oficial"
CICLO = "ele2026"
ELEICAO_T1 = "6257"
ELEICAO_T2 = "6258"
CARGO = "0001"  # presidente


def _get(url, tentativas=3):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (previsao-eleicao)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            if i == tentativas - 1:
                raise
            time.sleep(1 + 2 * i)


def url_config(ele, ciclo=CICLO):
    return f"{BASE}/{ciclo}/{ele}/config/mun-e{int(ele):06d}-cm.json"


def url_abr(ele, uf, mun="", ciclo=CICLO):
    return f"{BASE}/{ciclo}/{ele}/dados/{uf}/{uf}{mun}-c{CARGO}-e{int(ele):06d}-u.json"


def municipios(ele=ELEICAO_T2, ciclo=CICLO):
    cfg = _get(url_config(ele, ciclo))
    linhas = []
    for a in cfg["abr"]:
        for m in a["mu"]:
            linhas.append({"uf": a["cd"], "mun": m["cd"], "nome": m["nm"], "capital": m.get("c") == "s",
                           "cdi": m.get("cdi", "")})
    return pd.DataFrame(linhas)


def _num(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def parse_abr(d, cand_a="13", cand_b="22"):
    """Extrai totais de um arquivo -u.json (Brasil, UF ou município)."""
    s, e, v = d.get("s", {}), d.get("e", {}), d.get("v", {})
    out = {"ts": _num(s.get("ts")), "st": _num(s.get("st")), "E": _num(e.get("te")), "Ea": _num(e.get("est")),
           "C": _num(e.get("c")), "brancos": _num(v.get("vb")), "nulos": _num(v.get("tvn")),
           "A": 0, "B": 0, "O": 0, "dg": d.get("dg", ""), "hg": d.get("hg", ""), "nomes": {}}
    for carg in d.get("carg", []):
        for agr in carg.get("agr", []):
            for par in agr.get("par", []):
                for c in par.get("cand", []):
                    n, vap = c.get("n"), _num(c.get("vap"))
                    out["nomes"][n] = c.get("nmu") or c.get("nm")
                    if n == cand_a:
                        out["A"] += vap
                    elif n == cand_b:
                        out["B"] += vap
                    else:
                        out["O"] += vap
    return out


def baixar_municipios(ele, munis, cache=None, workers=48, ciclo=CICLO, cand_a="13", cand_b="22"):
    """Baixa o arquivo de cada município. Municípios já 100% apurados no `cache`
    (DataFrame do ciclo anterior) não são baixados de novo."""
    prontos = {}
    if cache is not None and len(cache):
        c = cache[(cache["ts"] > 0) & (cache["st"] >= cache["ts"])]
        prontos = {(r.uf, r.mun): r._asdict() for r in c.itertuples(index=False)}

    def um(row):
        uf, mun = row
        if (uf, mun) in prontos:
            return prontos[(uf, mun)]
        try:
            r = parse_abr(_get(url_abr(ele, uf, mun, ciclo)), cand_a, cand_b)
        except Exception as ex:  # noqa: BLE001
            if cache is not None:
                antigo = cache[(cache["uf"] == uf) & (cache["mun"] == mun)]
                if len(antigo):
                    return antigo.iloc[0].to_dict()
            print("falhou", uf, mun, ex)
            return None
        r.pop("nomes")
        r.update(uf=uf, mun=mun)
        return r

    pares = list(zip(munis["uf"], munis["mun"]))
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(um, pares))
    df = pd.DataFrame([r for r in res if r is not None])
    return df


def resumo_brasil(ele=ELEICAO_T2, ciclo=CICLO, cand_a="13", cand_b="22"):
    return parse_abr(_get(url_abr(ele, "br", "", ciclo)), cand_a, cand_b)


def salvar(df, caminho):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    df.to_csv(caminho, index=False)
