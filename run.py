"""Coleta a apuração do TSE, roda a previsão e gera o painel.

    python run.py                 # uma rodada
    python run.py --loop 600      # a cada 10 minutos
    python run.py --demo-2022 15  # painel de teste com 2022 simulado em 15% apurado
"""
import argparse
import datetime as dt
import json
import os
import time

import numpy as np
import pandas as pd

from eleicao import painel, tse
from eleicao.previsao import prever

AQUI = os.path.dirname(os.path.abspath(__file__))
FUSO = dt.timezone(dt.timedelta(hours=-3))  # Brasília


def _munis():
    caminho = os.path.join(AQUI, "data/municipios.csv")
    if os.path.exists(caminho):
        return pd.read_csv(caminho, dtype={"mun": str, "cdi": str})
    m = tse.municipios()
    tse.salvar(m, caminho)
    return m


def base_t1(munis, args):
    caminho = os.path.join(AQUI, "data/2026/mun_t1.csv.gz")
    if os.path.exists(caminho):
        return pd.read_csv(caminho, dtype={"mun": str})
    print("baixando 1º turno por município (só na primeira vez)...", flush=True)
    t1 = None
    for tentativa in range(6):
        t1 = tse.baixar_municipios(args.t1, munis, cache=t1, ciclo=args.ciclo, workers=6)
        falta = len(munis) - len(t1)
        print(f"1º turno: {len(t1)} municípios, faltam {falta}", flush=True)
        if falta == 0:
            break
        # força novo download só do que faltou: o cache marca os já baixados como prontos
        t1 = t1.assign(ts=t1["ts"].clip(lower=1), st=t1["ts"].clip(lower=1))
        time.sleep(30)
    if len(munis) - len(t1) > 0.005 * len(munis):
        raise RuntimeError("1º turno incompleto; tente de novo")
    tse.salvar(t1, caminho)
    return t1


def montar(munis, t1, t2):
    df = munis.merge(t1, on=["uf", "mun"], how="inner").merge(t2, on=["uf", "mun"], how="left",
                                                               suffixes=("_1", "_2"))
    for c in ["E_2", "Ea_2", "A_2", "B_2", "brancos_2", "nulos_2", "C_2", "ts_2", "st_2"]:
        df[c] = df[c].fillna(0)
    out = pd.DataFrame({
        "uf": df["uf"], "mun": df["mun"], "nome": df["nome"], "capital": df["capital"].astype(bool),
        "E1": df["E_1"], "A1": df["A_1"], "B1": df["B_1"], "O1": df["O_1"], "W1": df["brancos_1"] + df["nulos_1"],
        "E2": np.where(df["E_2"] > 0, df["E_2"], df["E_1"]), "Ea": df["Ea_2"], "A2": df["A_2"], "B2": df["B_2"],
        "W2": df["brancos_2"] + df["nulos_2"], "C2": df["C_2"],
    })
    return out


def _hora_tse(br):
    try:
        return dt.datetime.strptime(f"{br['dg']} {br['hg']}", "%d/%m/%Y %H:%M:%S").replace(tzinfo=FUSO)
    except (KeyError, ValueError):
        return dt.datetime.now(FUSO)


def gerar_saidas(res, saida):
    hist_path = os.path.join(saida, "historico.csv")
    br = res["grupos"]["Brasil"]["Brasil"]
    linha = {"hora": res["hora"], "pct_secoes": res["pct_secoes"], "parcial_A": res["parcial_A"],
             **{k: br[k] for k in ["A_media", "A_p05", "A_p95", "A_p025", "A_p975", "prob_A"]}}
    hist = pd.read_csv(hist_path) if os.path.exists(hist_path) else pd.DataFrame()
    if len(hist) and hist["hora"].iloc[-1] == linha["hora"]:
        hist = hist.iloc[:-1]
    hist = pd.concat([hist, pd.DataFrame([linha])], ignore_index=True)
    os.makedirs(saida, exist_ok=True)
    hist.to_csv(hist_path, index=False)
    p1, p2 = os.path.join(saida, "painel.png"), os.path.join(saida, "estados.png")
    painel.imagem_principal(res, hist, p1)
    painel.imagem_estados(res, p2)
    painel.pagina_html(res, p1, p2, os.path.join(saida, "index.html"))
    with open(os.path.join(saida, "resultado.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    painel.dados_web(res, hist, os.path.join(saida, "web"))


def rodada(args):
    t0 = time.time()
    munis = _munis()
    t1 = base_t1(munis, args)
    estado = os.path.join(args.saida, "estado_t2.csv.gz")
    cache = pd.read_csv(estado, dtype={"mun": str}) if os.path.exists(estado) else None
    br = tse.resumo_brasil(args.t2, args.ciclo)
    # UFs sem seções novas desde a última rodada não precisam ser baixadas de novo
    ufs_path = os.path.join(args.saida, "estado_ufs.json")
    ufs_antes = json.load(open(ufs_path)) if os.path.exists(ufs_path) and cache is not None else {}
    ufs_agora = tse.resumo_ufs(sorted(munis["uf"].unique()), args.t2, args.ciclo)
    pular = [uf for uf, st in ufs_agora.items() if ufs_antes.get(uf) == st]
    t2 = tse.baixar_municipios(args.t2, munis, cache=cache, ciclo=args.ciclo, pular_ufs=pular,
                               prazo=time.time() + args.prazo)
    falhas = t2.attrs.get("ufs_falha", [])
    tse.salvar(t2, estado)
    t2.attrs["ufs_falha"] = falhas
    completos = (set(t2["uf"]) if len(t2) else set()) - set(t2.attrs.get("ufs_falha", []))
    with open(ufs_path, "w") as f:
        json.dump({uf: st for uf, st in ufs_agora.items() if uf in completos}, f)
    df = montar(munis, t1, t2)
    nomes = [br["nomes"].get("13", "Lula").title(), br["nomes"].get("22", "Flávio Bolsonaro").title()]
    res = prever(df, nomes)
    hora = _hora_tse(br)
    res["hora"] = hora.isoformat()
    res["hora_txt"] = hora.strftime("%d/%m %H:%M")
    res["pct_secoes"] = 100 * br["st"] / max(br["ts"], 1)
    gerar_saidas(res, args.saida)
    b = res["grupos"]["Brasil"]["Brasil"]
    print(f"{res['hora_txt']} {res['pct_secoes']:.2f}% seções | {nomes[0]} {b['A_media']:.2f}% "
          f"[{b['A_p05']:.2f}, {b['A_p95']:.2f}] P={b['prob_A']:.3f} | {time.time() - t0:.0f}s", flush=True)


def demo_2022(args):
    import backtest
    base, sec = backtest.carregar()
    rng = np.random.default_rng(0)
    hist = []
    t = backtest.ordem(sec, base, "2022", rng)
    inicio = dt.datetime(2022, 10, 30, 17, 0, tzinfo=FUSO)
    pts = [p for p in [1, 5, 10, 20, 35, 50, 65, 80, 95] if p <= args.demo_2022] or [args.demo_2022]
    for i, p in enumerate(pts):
        ap = t <= np.percentile(t, p)
        df = backtest.snapshot(base, sec, ap)
        df = df[["uf", "mun", "nome", "capital", "E1", "A1", "B1", "O1", "W1", "E2", "Ea", "A2", "B2", "W2", "C2"]]
        res = prever(df, ["Lula", "Bolsonaro"])
        hora = inicio + dt.timedelta(minutes=10 * (i + 1))
        res.update(hora=hora.isoformat(), hora_txt=hora.strftime("%d/%m/%Y %H:%M") + " (simulação 2022)",
                   pct_secoes=100 * ap.mean())
        gerar_saidas(res, args.saida)
        hist.append(res)
        print(p, res["grupos"]["Brasil"]["Brasil"]["A_media"], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="segundos entre rodadas (0 = uma rodada)")
    ap.add_argument("--saida", default=os.path.join(AQUI, "saida/2026"))
    ap.add_argument("--ciclo", default=tse.CICLO)
    ap.add_argument("--t1", default=tse.ELEICAO_T1)
    ap.add_argument("--t2", default=tse.ELEICAO_T2)
    ap.add_argument("--prazo", type=float, default=420, help="segundos máximos para baixar os municípios")
    ap.add_argument("--demo-2022", type=float, default=0)
    args = ap.parse_args()
    if args.demo_2022:
        demo_2022(args)
        return
    while True:
        try:
            rodada(args)
        except Exception as ex:  # noqa: BLE001
            print("erro na rodada:", repr(ex), flush=True)
            if not args.loop:
                raise
        if not args.loop:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
