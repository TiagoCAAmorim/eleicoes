"""Painéis das apurações simuladas do 2º turno presidencial de 2006 a 2022 (etapa 8 do roteiro).

O TSE não guarda retratos parciais das apurações antigas, só o resultado final por seção. Para mostrar o que o
modelo diria ao longo da noite, cada eleição é apurada de novo numa ordem sintética e plausível: a do gerador do
teste de estresse (eleicoes/modelos/estresse.py) com o atraso regional de 2026 (Sul e Sudeste antes, Nordeste,
Norte e capitais depois, zonas em blocos), sem viés entre cidades e com as primeiras seções de cada cidade um pouco
mais para o candidato do PT que a própria cidade, como em 2026 (gama = 0,05). Os votos de cada seção são os reais.

O modelo é o adotado (calibrado_cauteloso, o mesmo do painel revisado de 2026): priori = média das matrizes dos
2º turnos anteriores (2006 não tem anterior na base: usa a média de 2010–2022) e linha Outros ajustada às
pesquisas da véspera (dados/pesquisas/presidente_t2.csv). O horário é simulado: segue a marcha do % apurado da
noite de 2026.

Saídas em resultados/simulacoes/<ano>-presidente/: as mesmas do painel ao vivo para o último momento (imagens,
CSVs, web/*.json) e web/momentos.json, com a previsão de cada momento para o seletor da página.

    python scripts/paineis_simulados.py                 # 2006, 2010, 2014, 2018 e 2022 (~15 min)
    python scripts/paineis_simulados.py --anos 2022
"""
import argparse
import dataclasses
import datetime as dt
import json
import os
import shutil
import time

import numpy as np
import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import DADOS, resultados
from eleicoes.dados import historico as hist
from eleicoes.modelos import estresse as es
from eleicoes.modelos import priori as priori_cal
from eleicoes.modelos import transferencia as modelo
from eleicoes.modelos.previsao import NIVEIS, prever
from eleicoes.site import exportar, painel
from apuracao import gerar_saidas
import backtest

FUSO = dt.timezone(dt.timedelta(hours=-3))
PONTOS = [0, 0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 95, 99, 100]
GAMA = 0.05          # viés das primeiras seções de cada cidade (medido em 2026), em direção ao candidato do PT
SEMENTE = 2026
# calibrado_cauteloso (scripts/rejogar_2026.py), o modelo do painel revisado de 2026
MUDANCAS = {"tau": 0.15, "choque_uf_inicio": 0.04, "choque_uf_inicio_antes": 0.02, "sd_outros": 0.3}
ELEICOES = {
    2006: {"data": dt.date(2006, 10, 29), "nomes": ["Lula", "Geraldo Alckmin"]},
    2010: {"data": dt.date(2010, 10, 31), "nomes": ["Dilma Rousseff", "José Serra"]},
    2014: {"data": dt.date(2014, 10, 26), "nomes": ["Dilma Rousseff", "Aécio Neves"]},
    2018: {"data": dt.date(2018, 10, 28), "nomes": ["Fernando Haddad", "Jair Bolsonaro"]},
    2022: {"data": dt.date(2022, 10, 30), "nomes": ["Lula", "Jair Bolsonaro"]},
}
COLS = ["uf", "mun", "nome", "capital", "E1", "A1", "B1", "O1", "W1", "E2", "Ea", "A2", "B2", "W2", "C2"]
PESQUISAS = pd.read_csv(os.path.join(DADOS, "pesquisas", "presidente_t2.csv"))


def carregar(ano):
    """(base do 1º turno por município, seções do 2º turno com v13 = A e v22 = B)."""
    if ano == 2022:
        return backtest.carregar()
    b, _ = hist.segundo_turno_presidente(ano)
    base = b[["uf", "mun", "nome", "capital", "E1", "A1", "B1", "O1", "W1"]].copy()
    sec = pd.read_csv(os.path.join(hist.HIST, str(ano), "secoes_presidente_t2.csv.gz"), dtype={"mun": str})
    sec = sec.rename(columns={"A": "v13", "B": "v22"})
    sec["mun"] = sec["mun"].str.zfill(5)
    sec = sec[sec["mun"].isin(set(base["mun"]))].reset_index(drop=True)
    # como no teste de estresse: de 2006 a 2014 ~10% das seções vêm sem aptos e comparecimento
    sem = sec["aptos"] <= 0
    if sem.any():
        sec.loc[sem, "comp"] = sec.loc[sem, ["v13", "v22", "brancos", "nulos"]].sum(axis=1)
        ok = sec[~sem].groupby("mun")[["comp", "aptos"]].sum()
        taxa = (ok["comp"] / ok["aptos"].clip(lower=1)).reindex(sec.loc[sem, "mun"]).fillna(0.8).clip(0.3, 1).values
        sec.loc[sem, "aptos"] = np.round(sec.loc[sem, "comp"].values / taxa).astype(int)
    return base, sec


def configuracao(ano, completo):
    """Config do modelo adotado para `ano` (só com informação de antes da eleição, salvo 2006; ver o cabeçalho)."""
    anteriores = [a for a in hist.ANOS_PRESIDENTE if a < ano] or [a for a in hist.ANOS_PRESIDENTE if a > ano]
    pri = priori_cal.media([priori_cal.carregar(a) for a in anteriores])
    alvo = PESQUISAS.loc[PESQUISAS["ano"] == ano, "a_validos"].mean()
    th = priori_cal.outros_pela_pesquisa(completo, pri, alvo)
    cfg = dataclasses.replace(modelo.Config(priori=pri, theta_outros=th), **MUDANCAS)
    return cfg, anteriores, alvo


def relogio():
    """% apurado -> minutos depois das 17h, pela marcha da noite de 2026 (historico do painel do dia)."""
    h = pd.read_csv(os.path.join(resultados("2026-presidente"), "historico.csv"))
    t = pd.to_datetime(h["hora"])
    minutos = ((t - t.dt.normalize()).dt.total_seconds() / 60 - 17 * 60).values
    pct = np.maximum.accumulate(h["pct_secoes"].values)
    return lambda p: float(np.interp(p, pct, minutos)) if p > 0 else -1.0


def simular(ano, pasta):
    info = ELEICOES[ano]
    nomes = info["nomes"]
    base, sec = carregar(ano)
    completo = backtest.snapshot(base, sec, np.ones(len(sec), bool))[COLS]
    cfg, anteriores, alvo = configuracao(ano, completo)
    tudo, _, _ = modelo.preparar(completo.copy())
    real = {}
    for rotulo, col in NIVEIS:
        g = tudo.groupby(col)[["A2", "B2"]].sum()
        real[rotulo] = (100 * g["A2"] / (g["A2"] + g["B2"])).to_dict()
    real_a = real["Brasil"]["Brasil"]
    ger = es.GeradorApuracao(base, sec, cfg.priori)
    t = ger.ordem(np.random.default_rng(SEMENTE + ano), beta=0.0, gama=GAMA)
    minutos = relogio()
    inicio = dt.datetime.combine(info["data"], dt.time(17, 0), tzinfo=FUSO)
    if os.path.exists(pasta):
        shutil.rmtree(pasta)
    os.makedirs(pasta)
    linhas, momentos = [], []
    for i, p in enumerate(PONTOS):
        t0 = time.time()
        ap = t <= np.percentile(t, p) if p > 0 else np.zeros(len(t), bool)
        df = backtest.snapshot(base, sec, ap)[COLS]
        res = prever(df, nomes, cfg)
        for rotulo, grupos in res["grupos"].items():
            for nome, g in grupos.items():
                g["real"] = float(real[rotulo].get(nome, float("nan")))
        res["real_A"] = real_a
        hora = (inicio + dt.timedelta(minutes=minutos(p))).replace(microsecond=0)
        res.update(hora=hora.isoformat(), hora_txt=hora.strftime("%d/%m/%Y %H:%M"), proxima_txt="",
                   pct_secoes=float(100 * ap.mean()))
        br = res["grupos"]["Brasil"]["Brasil"]
        br["pct_apurado"] = res["pct_secoes"]
        linha = {"hora": res["hora"], "pct_secoes": res["pct_secoes"], "parcial_A": res["parcial_A"],
                 **{k: br[k] for k in ["A_media", "A_p05", "A_p95", "A_p025", "A_p975", "prob_A"]}}
        web = painel.linhas_web(res, pd.DataFrame([linha]))
        mun = res["_csv"]["dados_municipios"]
        momentos.append({"pct": round(res["pct_secoes"], 3), "hora_txt": res["hora_txt"],
                         "previsao": web["previsao"], "transferencias": web["transferencias"],
                         "fluxos": exportar.fluxos(mun, *map(painel.curto, nomes))})
        print(f"{ano} {p:5.1f}%  {br['A_media']:.2f} [{br['A_p05']:.2f}, {br['A_p95']:.2f}] P={br['prob_A']:.3f}"
              f"  (real {real_a:.2f}, {time.time() - t0:.0f}s)", flush=True)
        if i < len(PONTOS) - 1:
            linhas.append(linha)
            continue
        pd.DataFrame(linhas).to_csv(os.path.join(pasta, "historico.csv"), index=False)
        gerar_saidas(res, pasta)
        os.remove(os.path.join(pasta, "index.html"))   # página estática do loop ao vivo; o site usa web/
    with open(os.path.join(pasta, "web", "momentos.json"), "w") as f:
        json.dump(momentos, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(pasta, "simulacao.json"), "w") as f:
        json.dump({"ano": ano, "nomes": nomes, "real_A": real_a, "pesquisa_A": alvo, "prioris": anteriores,
                   "gama": GAMA, "semente": SEMENTE + ano, "pontos": PONTOS, "modelo": MUDANCAS}, f,
                  ensure_ascii=False, indent=1)


def resumir():
    """resultados/simulacoes/resumo.csv: erro e intervalo em alguns momentos, cobertura e momento da "chamada"."""
    linhas = []
    for ano in ELEICOES:
        pasta = resultados(os.path.join("simulacoes", f"{ano}-presidente"))
        arq = os.path.join(pasta, "web", "momentos.json")
        if not os.path.exists(arq):
            continue
        real = json.load(open(os.path.join(pasta, "simulacao.json")))["real_A"]
        h = pd.DataFrame([{**next(r for r in m["previsao"] if r["nivel"] == "Brasil"), "pct": m["pct"]}
                          for m in json.load(open(arq))])
        # tolerância de 0,01 ponto: no fim o intervalo tem largura ~0 e os JSONs têm 3 casas; 100% apurado não conta
        h = h[h["pct"] < 99.95]
        cobre = (h["A_p05"] - 0.01 <= real) & (real <= h["A_p95"] + 0.01)
        certo = (h["prob_A"] >= 0.99) if real > 50 else (h["prob_A"] <= 0.01)
        errado = (h["prob_A"] <= 0.01) if real > 50 else (h["prob_A"] >= 0.99)
        # chamada: primeiro momento a partir do qual a chance fica acima de 99% para o vencedor até o fim
        cham = next((h["pct"].iloc[i] for i in range(len(h)) if certo.iloc[i:].all()), None)
        lin = {"ano": ano, "real_A": real, "cobertura90": cobre.mean(), "chamadas_erradas": int(errado.sum()),
               "chamada_pct": cham}
        for p in [0, 1, 5, 10, 25, 50]:
            r = h.iloc[(h["pct"] - p).abs().argmin()]
            lin[f"prev_{p}"], lin[f"p05_{p}"], lin[f"p95_{p}"] = r["A_media"], r["A_p05"], r["A_p95"]
        linhas.append(lin)
    res = pd.DataFrame(linhas)
    res.round(3).to_csv(resultados(os.path.join("simulacoes", "resumo.csv")), index=False)
    print(res.round(2).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anos", type=int, nargs="+", default=list(ELEICOES))
    ap.add_argument("--so-resumo", action="store_true")
    a = ap.parse_args()
    if not a.so_resumo:
        for ano in a.anos:
            simular(ano, resultados(os.path.join("simulacoes", f"{ano}-presidente")))
    resumir()


if __name__ == "__main__":
    main()
