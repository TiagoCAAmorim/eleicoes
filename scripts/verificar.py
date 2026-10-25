"""Verificações de consistência da apuração e da previsão (rodado pelo agente local entre as rodadas).

    python scripts/verificar.py --site-url https://<usuario>.github.io/<repo>/ --log loop.log --relatorio relatorio.md

Sai com código 0 se tudo estiver ok, 1 se houver alertas. O relatório em Markdown lista cada verificação.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

import pandas as pd

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
from eleicao import tse  # noqa: E402

FUSO = dt.timezone(dt.timedelta(hours=-3))


class Relatorio:
    def __init__(self):
        self.linhas, self.alertas, self.extra = [], 0, ""

    def ok(self, nome, detalhe=""):
        self.linhas.append(f"- OK · {nome}" + (f": {detalhe}" if detalhe else ""))

    def alerta(self, nome, detalhe):
        self.alertas += 1
        self.linhas.append(f"- **ALERTA** · {nome}: {detalhe}")

    def info(self, nome, detalhe):
        self.linhas.append(f"- info · {nome}: {detalhe}")


def checar_tse(rel, saida, t2, ciclo):
    """Compara os totais do TSE (arquivo Brasil e por UF) com a soma dos municípios baixados."""
    est = os.path.join(saida, "estado_t2.csv.gz")
    if not os.path.exists(est):
        rel.alerta("municípios baixados", f"{est} não existe")
        return
    m = pd.read_csv(est, dtype={"mun": str})
    m = m[m["uf"] != "br"] if "uf" in m else m
    try:
        br = tse.resumo_brasil(t2, ciclo)
    except Exception as ex:  # noqa: BLE001
        rel.alerta("TSE Brasil", f"não foi possível ler o arquivo Brasil: {ex!r}")
        return
    rel.info("TSE Brasil", f"{br['st']}/{br['ts']} seções, {br['dg']} {br['hg']}, A={br['A']:,} B={br['B']:,}")
    sa, sb = m["A"].sum(), m["B"].sum()
    for nome, tse_v, soma in [("votos Lula", br["A"], sa), ("votos Flávio", br["B"], sb)]:
        dif = (soma - tse_v) / max(tse_v, 1)
        msg = f"TSE {tse_v:,} x soma dos municípios {soma:,.0f} ({100 * dif:+.2f}%)"
        # a soma pode ficar um pouco atrás do TSE (rodada anterior); à frente ou muito atrás é problema
        (rel.ok if -0.03 <= dif <= 0.001 or tse_v == 0 else rel.alerta)(nome, msg)
    ufs = sorted(m["uf"].unique())
    piores = []
    for uf in ufs:
        try:
            r = tse.parse_abr(tse._get(tse.url_abr(t2, uf, "", ciclo)))
        except Exception as ex:  # noqa: BLE001
            piores.append(f"{uf}: erro {ex!r}")
            continue
        s = m[m["uf"] == uf][["A", "B"]].sum()
        tot = r["A"] + r["B"]
        dif = (s["A"] + s["B"] - tot) / max(tot, 1)
        if tot and not (-0.05 <= dif <= 0.001):
            piores.append(f"{uf}: TSE {tot:,} x soma {s['A'] + s['B']:,.0f} ({100 * dif:+.1f}%)")
    (rel.alerta if piores else rel.ok)("totais por UF", "; ".join(piores) if piores else f"{len(ufs)} UFs batem com o TSE")


def checar_previsao(rel, saida):
    """Coerência interna do resultado.json e do histórico."""
    with open(os.path.join(saida, "resultado.json")) as f:
        res = json.load(f)
    hora = dt.datetime.fromisoformat(res["hora"])
    idade = (dt.datetime.now(FUSO) - hora).total_seconds() / 60
    rel.info("última rodada", f"{res['hora_txt']} · {res['pct_secoes']:.2f}% das seções · há {idade:.0f} min (hora do TSE)")
    if res["pct_secoes"] > 0 and idade > 30:
        rel.alerta("atualização", f"resultado.json com {idade:.0f} min; o loop pode ter parado")
    probs = []
    for nivel, grupos in res["grupos"].items():
        for nome, g in grupos.items():
            rot = f"{nivel}/{nome}"
            if not (g["A_p05"] - 1e-6 <= g["A_media"] <= g["A_p95"] + 1e-6):
                probs.append(f"{rot}: média fora do intervalo")
            if not 0 <= g["prob_A"] <= 1:
                probs.append(f"{rot}: chance fora de [0,1]")
            for c in "AB":
                if g.get(f"votos_{c}_previsto", 0) + 1 < g.get(f"votos_{c}_apurado", 0):
                    probs.append(f"{rot}: votos previstos de {c} menores que os apurados")
            if g["pct_apurado"] >= 99.9 and g["parcial"] == g["parcial"] and abs(g["A_media"] - g["parcial"]) > 0.15:
                probs.append(f"{rot}: 100% apurado mas previsão {g['A_media']:.2f} ≠ apurado {g['parcial']:.2f}")
            # com pouco apurado a diferença pode ser grande (seções que chegam primeiro não são representativas)
            if g["pct_apurado"] > 20 and g["parcial"] == g["parcial"] and abs(g["A_media"] - g["parcial"]) > 10:
                probs.append(f"{rot}: previsão {g['A_media']:.1f} muito longe do apurado {g['parcial']:.1f}")
    br = res["grupos"]["Brasil"]["Brasil"]
    soma_uf = sum(g["eleitores"] for g in res["grupos"]["UF"].values())
    if abs(soma_uf - br["eleitores"]) > 1:
        probs.append(f"soma dos eleitores das UFs {soma_uf:,.0f} ≠ Brasil {br['eleitores']:,.0f}")
    (rel.alerta if probs else rel.ok)("coerência da previsão", "; ".join(probs[:15]) if probs else "intervalos, chances e votos coerentes")
    hist = pd.read_csv(os.path.join(saida, "historico.csv"))
    if len(hist) >= 2:
        a, b = hist.iloc[-2], hist.iloc[-1]
        if b["pct_secoes"] + 1e-9 < a["pct_secoes"]:
            rel.alerta("histórico", f"% de seções caiu de {a['pct_secoes']:.2f} para {b['pct_secoes']:.2f}")
        salto = b["A_media"] - a["A_media"]
        fora = not (a["A_p05"] - 0.3 <= b["A_media"] <= a["A_p95"] + 0.3)
        txt = f"previsão Lula {a['A_media']:.2f} → {b['A_media']:.2f} ({salto:+.2f} pt), seções {a['pct_secoes']:.1f} → {b['pct_secoes']:.1f}%"
        (rel.alerta if abs(salto) > 1.5 or (fora and a["pct_secoes"] > 5) else rel.ok)("variação entre rodadas", txt)
    return res


def comparar_tse(rel, res, t2, ciclo):
    """Compara o que a página mostra (resultado.json) com os arquivos oficiais do TSE, Brasil e cada UF:
    % de seções totalizadas e % de Lula nos votos válidos. Diferenças vêm da assincronia entre os arquivos
    das UFs e dos municípios (a página usa os municipais) ou de erro de coleta."""
    linhas, grandes = [], []
    alvos = [("Brasil", "br", res["grupos"]["Brasil"]["Brasil"])] + [
        ("Exterior" if u == "zz" else u.upper(), u, g) for u, g in res["grupos"]["UF"].items()]
    for nome, uf, g in alvos:
        try:
            r = tse.parse_abr(tse._get(tse.url_abr(t2, uf, "", ciclo)))
        except Exception as ex:  # noqa: BLE001
            linhas.append(f"| {nome} | erro {ex!r} | | | |")
            continue
        pst = 100 * r["st"] / max(r["ts"], 1)
        lula = 100 * r["A"] / (r["A"] + r["B"]) if r["A"] + r["B"] else float("nan")
        d_st, d_lula = g["pct_apurado"] - pst, g["parcial"] - lula
        linhas.append(f"| {nome} | {pst:.2f} / {g['pct_apurado']:.2f} | {lula:.2f} / {g['parcial']:.2f} | "
                      f"{d_st:+.2f} | {d_lula:+.2f} |")
        if abs(d_st) > 1 or (lula == lula and g["parcial"] == g["parcial"] and abs(d_lula) > 0.5):
            grandes.append(f"{nome} (seções {d_st:+.1f} pt, Lula {d_lula:+.1f} pt)")
    (rel.alerta if grandes else rel.ok)(
        "página x TSE", ("diferenças acima de 1 pt nas seções ou 0,5 pt em Lula: " + "; ".join(grandes))
        if grandes else "Brasil e UFs batem com os arquivos do TSE")
    rel.extra = ("\n## Página x TSE (TSE / página)\n\n| | % seções | % Lula (válidos) | dif. seções | dif. Lula |\n"
                 "|---|---|---|---|---|\n" + "\n".join(linhas) + "\n")


def checar_site(rel, url, res):
    if not url:
        return
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/index.html?nocache=" + str(int(dt.datetime.now().timestamp())),
                                    timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception as ex:  # noqa: BLE001
        rel.alerta("site", f"não abriu {url}: {ex!r}")
        return
    (rel.ok if res["hora_txt"] in html else rel.alerta)(
        "site", f"{'mostra' if res['hora_txt'] in html else 'NÃO mostra'} a rodada {res['hora_txt']} (o GitHub Pages leva 1-3 min)")


def checar_log(rel, log):
    if not log or not os.path.exists(log):
        return
    with open(log, encoding="utf-8", errors="replace") as f:
        linhas = f.read().splitlines()[-60:]
    erros = [x for x in linhas if ("erro" in x.lower() or "falh" in x.lower() or "Traceback" in x)
             and "falhas em []" not in x]
    (rel.alerta if erros else rel.ok)("log do loop", " | ".join(erros[-5:]) if erros else "sem erros nas últimas linhas")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=os.path.join(AQUI, "saida/2026"))
    ap.add_argument("--site-url", default="")
    ap.add_argument("--log", default="")
    ap.add_argument("--relatorio", default="")
    ap.add_argument("--sem-tse", action="store_true", help="não consulta o TSE (teste offline)")
    ap.add_argument("--t2", default=tse.ELEICAO_T2)
    ap.add_argument("--ciclo", default=tse.CICLO)
    args = ap.parse_args()
    rel = Relatorio()
    agora = dt.datetime.now(FUSO)
    if not args.sem_tse:
        checar_tse(rel, args.saida, args.t2, args.ciclo)
    res = checar_previsao(rel, args.saida)
    if not args.sem_tse:
        comparar_tse(rel, res, args.t2, args.ciclo)
    checar_site(rel, args.site_url, res)
    checar_log(rel, args.log)
    texto = (f"# Verificação {agora:%d/%m %H:%M} (Brasília)\n\n"
             f"Resultado: {'tudo ok' if not rel.alertas else f'{rel.alertas} alerta(s)'}\n\n" + "\n".join(rel.linhas) + "\n" + rel.extra)
    print(texto)
    if args.relatorio:
        with open(args.relatorio, "w", encoding="utf-8") as f:
            f.write(texto)
    sys.exit(1 if rel.alertas else 0)


if __name__ == "__main__":
    main()
