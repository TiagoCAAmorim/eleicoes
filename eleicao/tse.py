"""Leitura dos resultados de divulgação do TSE (resultados.tse.jus.br)."""
import json
import os
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

BASE = "https://resultados.tse.jus.br/oficial"
CICLO = "ele2026"
ELEICAO_T1 = "6257"
ELEICAO_T2 = "6258"
CARGO = "0001"  # presidente


UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def _get(url, tentativas=6):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as ex:
            if ex.code == 404 or i == tentativas - 1:
                raise
            espera = ex.headers.get("Retry-After") if ex.code in (429, 503) else None
            try:
                espera = float(espera)
            except (TypeError, ValueError):
                espera = 3 * 2 ** i
            time.sleep(min(espera, 60) * (0.75 + 0.5 * random.random()))
        except Exception:  # noqa: BLE001
            if i == tentativas - 1:
                raise
            time.sleep(2 * 2 ** i * (0.75 + 0.5 * random.random()))


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


def baixar_municipios(ele, munis, cache=None, workers=8, ciclo=CICLO, cand_a="13", cand_b="22",
                      pular_ufs=(), prazo=None):
    """Baixa o arquivo de cada município. Municípios já 100% apurados no `cache`
    (DataFrame do ciclo anterior), ou de UFs em `pular_ufs` (sem novidade desde a
    última rodada), não são baixados de novo. Depois do `prazo` (time.time())
    usa o cache para o que faltar."""
    prontos = {}
    if cache is not None and len(cache):
        c = cache[((cache["ts"] > 0) & (cache["st"] >= cache["ts"])) | cache["uf"].isin(list(pular_ufs))]
        prontos = {(r.uf, r.mun): r._asdict() for r in c.itertuples(index=False)}
    falhas = set()

    def um(row):
        uf, mun = row
        if (uf, mun) in prontos:
            return prontos[(uf, mun)]
        if prazo is not None and time.time() > prazo:
            falhas.add(uf)
            if cache is not None:
                antigo = cache[(cache["uf"] == uf) & (cache["mun"] == mun)]
                if len(antigo):
                    return antigo.iloc[0].to_dict()
            return None
        try:
            r = parse_abr(_get(url_abr(ele, uf, mun, ciclo)), cand_a, cand_b)
        except Exception as ex:  # noqa: BLE001
            falhas.add(uf)
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
    df.attrs["ufs_falha"] = sorted(falhas)
    print(f"{len(pares) - len(prontos)} arquivos consultados, falhas em {sorted(falhas)}", flush=True)
    return df


def resumo_brasil(ele=ELEICAO_T2, ciclo=CICLO, cand_a="13", cand_b="22"):
    return parse_abr(_get(url_abr(ele, "br", "", ciclo)), cand_a, cand_b)


def resumo_ufs(ufs, ele=ELEICAO_T2, ciclo=CICLO):
    """Seções totalizadas por UF (para pular UFs sem novidade)."""
    out = {}
    for uf in ufs:
        try:
            r = parse_abr(_get(url_abr(ele, uf, "", ciclo)))
            out[uf] = r["st"]
        except Exception as ex:  # noqa: BLE001
            print("falhou UF", uf, ex)
    return out


def salvar(df, caminho):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    df.to_csv(caminho, index=False)
