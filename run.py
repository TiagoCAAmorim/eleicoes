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

from eleicao import exportar, mapa_mun, painel, tse
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


def _proxima(pct_secoes, loop, inicio):
    """Horário previsto da próxima atualização do painel (texto, horário de Brasília).
    As rodadas começam a cada `loop` segundos; a próxima publica ~uma duração de rodada depois de começar."""
    agora = dt.datetime.now(FUSO)
    if not loop:
        return ""
    dur = time.time() - inicio + 60  # download + modelo até aqui, + publicação
    prox = dt.datetime.fromtimestamp(inicio + max(loop, dur) + dur, FUSO)
    if pct_secoes <= 0:
        # urnas fecham às 17h (Brasília); os primeiros resultados saem em seguida
        prox = max(prox, agora.replace(hour=17, minute=15, second=0, microsecond=0))
    return f"~{prox:%H:%M}"


def gerar_saidas(res, saida):
    mun = res.pop("_municipios", None)
    csvs = res.pop("_csv", {})
    hist_path = os.path.join(saida, "historico.csv")
    br = res["grupos"]["Brasil"]["Brasil"]
    linha = {"hora": res["hora"], "pct_secoes": res["pct_secoes"], "parcial_A": res["parcial_A"],
             **{k: br[k] for k in ["A_media", "A_p05", "A_p95", "A_p025", "A_p975", "prob_A"]}}
    hist = pd.read_csv(hist_path) if os.path.exists(hist_path) else pd.DataFrame()
    if len(hist) and hist["hora"].iloc[-1] == linha["hora"]:
        hist = hist.iloc[:-1]
    if len(hist) and linha["pct_secoes"] == 0:
        hist = hist[hist["pct_secoes"] > 0]  # só um ponto de antes da apuração (o mais recente)
    hist = pd.concat([hist, pd.DataFrame([linha])], ignore_index=True)
    os.makedirs(saida, exist_ok=True)
    hist.to_csv(hist_path, index=False)
    p1, p2 = os.path.join(saida, "painel.png"), os.path.join(saida, "estados.png")
    painel.imagem_principal(res, hist, p1)
    painel.imagem_estados(res, p2)
    painel.pagina_html(res, p1, p2, os.path.join(saida, "index.html"))
    if mun is not None:
        try:
            mapa_mun.imagem(res, mun, _munis(), os.path.join(saida, "mapa_municipios.png"))
        except Exception as ex:  # noqa: BLE001
            print("mapa por município falhou:", repr(ex), flush=True)
    # dados para download (separador ";" e vírgula decimal, que o Excel em português abre direto)
    csvs["resumo_grupos"] = exportar.resumo_grupos(res)
    for nome, tab in csvs.items():
        tab.to_csv(os.path.join(saida, f"{nome}.csv"), sep=";", decimal=",", index=False, encoding="utf-8-sig")
    with open(os.path.join(saida, "resultado.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    painel.dados_web(res, hist, os.path.join(saida, "web"))


def publicar_git(args):
    """Commita e envia as saídas para o branch do projeto (para o painel na web)."""
    import subprocess
    raiz = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=AQUI, capture_output=True, text=True).stdout.strip()
    if not raiz:
        print("git: pasta não é um repositório; nada enviado")
        return
    rel = os.path.relpath(args.saida, raiz)
    cmds = [["git", "add", "-A", rel, os.path.relpath(os.path.join(AQUI, "data/2026"), raiz)],
            ["git", "commit", "-q", "-m", f"eleicao: painel {dt.datetime.now(FUSO):%H:%M} [skip ci]"],
            ["git", "pull", "-q", "--rebase", "-X", "theirs"], ["git", "push", "-q"]]
    for c in cmds:
        r = subprocess.run(c, cwd=raiz, capture_output=True, text=True)
        if r.returncode and c[1] != "commit":
            print("git falhou:", " ".join(c), r.stderr.strip()[:300])
            return


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
    nomes = [n.replace("Flavio", "Flávio") for n in nomes]  # o TSE publica o nome de urna sem acento
    res = prever(df, nomes)
    hora = _hora_tse(br)
    if br["st"] == 0:
        # antes da apuração o arquivo do TSE traz a data da carga (dia anterior): a estimativa inicial
        # vale para o fechamento das urnas
        hora = dt.datetime.now(FUSO).replace(hour=16, minute=59, second=0, microsecond=0)
    res["hora"] = hora.isoformat()
    res["hora_txt"] = hora.strftime("%d/%m %H:%M")
    res["pct_secoes"] = 100 * br["st"] / max(br["ts"], 1)
    res["proxima_txt"] = _proxima(res["pct_secoes"], args.loop, t0)
    gerar_saidas(res, args.saida)
    b = res["grupos"]["Brasil"]["Brasil"]
    print(f"{res['hora_txt']} {res['pct_secoes']:.2f}% seções | {nomes[0]} {b['A_media']:.2f}% "
          f"[{b['A_p05']:.2f}, {b['A_p95']:.2f}] P={b['prob_A']:.3f} | {time.time() - t0:.0f}s", flush=True)


def demo_2022(args):
    """Simula a apuração de 2022 (ordem parecida com a real) e gera saídas e site de teste,
    com o resultado real de cada grupo para comparação."""
    import backtest
    from eleicao import modelo, web
    from eleicao.previsao import NIVEIS
    base, sec = backtest.carregar()
    rng = np.random.default_rng(0)
    t = backtest.ordem(sec, base, args.demo_ordem, rng)
    # resultado real por grupo
    cols = ["uf", "mun", "nome", "capital", "E1", "A1", "B1", "O1", "W1", "E2", "Ea", "A2", "B2", "W2", "C2"]
    tudo, _, _ = modelo.preparar(backtest.snapshot(base, sec, np.ones(len(sec), bool))[cols])
    real = {}
    for rotulo, col in NIVEIS:
        g = tudo.groupby(col)[["A2", "B2"]].sum()
        real[rotulo] = (100 * g["A2"] / (g["A2"] + g["B2"])).to_dict()
    if os.path.exists(os.path.join(args.saida, "historico.csv")):
        os.remove(os.path.join(args.saida, "historico.csv"))
    inicio = dt.datetime(2022, 10, 30, 17, 0, tzinfo=FUSO)
    pts = [p for p in [0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99, 100]
           if p <= args.demo_2022]
    for i, p in enumerate(pts):
        ap = t <= np.percentile(t, p)
        df = backtest.snapshot(base, sec, ap)[cols]
        res = prever(df, ["Lula", "Bolsonaro"], modelo.Config())  # sem priori de 2022 (seria usar o gabarito)
        for rotulo, grupos in res["grupos"].items():
            for nome, g in grupos.items():
                g["real"] = float(real[rotulo].get(nome, float("nan")))
        res["real_A"] = real["Brasil"]["Brasil"]
        hora = inicio + dt.timedelta(minutes=10 * (i + 1))
        res.update(hora=hora.isoformat(), hora_txt=hora.strftime("%d/%m/%Y %H:%M") + " (simulação 2022)",
                   pct_secoes=100 * ap.mean(),
                   proxima_txt=f"~{hora + dt.timedelta(minutes=10):%H:%M}" if p < 100 else "")
        gerar_saidas(res, args.saida)
        print(f"{p:5.1f}% {res['grupos']['Brasil']['Brasil']['A_media']:.2f}", flush=True)
        if args.site:
            web.gerar_site(args.saida, os.path.join(args.site, f"{i:02d}_{p:g}pct"),
                           titulo="Teste: apuração simulada de 2022", artefato=args.artefato)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="segundos entre rodadas (0 = uma rodada)")
    ap.add_argument("--saida", default=os.path.join(AQUI, "saida/2026"))
    ap.add_argument("--ciclo", default=tse.CICLO)
    ap.add_argument("--t1", default=tse.ELEICAO_T1)
    ap.add_argument("--t2", default=tse.ELEICAO_T2)
    ap.add_argument("--prazo", type=float, default=420, help="segundos máximos para baixar os municípios")
    ap.add_argument("--git-push", action="store_true", help="commita e envia as saídas ao fim de cada rodada")
    ap.add_argument("--publicar", default="", help="pasta do clone do repositório do site (GitHub Pages)")
    ap.add_argument("--demo-2022", type=float, default=0, help="simula 2022 até este % apurado")
    ap.add_argument("--demo-ordem", default="2022", help="ordem da simulação: 2022, aleatoria ou adversa")
    ap.add_argument("--site", default="", help="(teste) pasta onde gerar o site a cada ponto")
    ap.add_argument("--artefato", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.demo_2022:
        demo_2022(args)
        return
    while True:
        inicio = time.time()  # o intervalo conta do início de uma rodada ao início da seguinte
        try:
            rodada(args)
            if args.git_push:
                publicar_git(args)
            if args.publicar:
                from eleicao import web
                if web.publicar(args.saida, args.publicar):
                    print("site publicado", flush=True)
        except Exception as ex:  # noqa: BLE001
            print("erro na rodada:", repr(ex), flush=True)
            if not args.loop:
                raise
        if not args.loop:
            break
        time.sleep(max(0, args.loop - (time.time() - inicio)))


if __name__ == "__main__":
    main()
