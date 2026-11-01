"""Rejoga a apuração real do 2º turno de 2026 (retratos gravados a cada rodada) com variantes do modelo.

Para cada retrato e cada variante, roda o modelo e compara a previsão do Brasil e de cada UF com o resultado
final. Saídas em resultados/rejogo-2026/:
  previsoes.csv  uma linha por (variante, retrato, grupo): média, intervalos de 50% e 90%, chance, CRPS, final
  resumo.csv     métricas por variante e faixa de % apurado
  rejogo.png     previsão e intervalo de 90% do Brasil ao longo da noite, uma variante por painel

    python scripts/rejogar_2026.py                       # todas as variantes
    python scripts/rejogar_2026.py --variantes atual sem_curva --passo 2
"""
import argparse
import dataclasses
import json
import os
import time

import numpy as np
import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import COMUM, RESULTADOS, dados
from eleicoes.modelos import transferencia as modelo

TOL = 0.1  # pontos: erros menores que isso não contam como falha de cobertura (revisões do TSE, arredondamento)
FAIXAS = [(-0.01, 0.01, "antes de abrir"), (0.01, 5, "até 5%"), (5, 15, "5 a 15%"), (15, 30, "15 a 30%"),
          (30, 60, "30 a 60%"), (60, 99.5, "60 a 99,5%")]

# cada variante = mudanças sobre a configuração usada ao vivo (config_2026)
VARIANTES = {
    "atual": {},
    "sem_curva": {"transicao_centro": None},
    "sem_curva_choque": {"transicao_centro": None, "choque_nacional": 0.02},
    "sem_curva_choque_v2": {"transicao_centro": None, "choque_nacional": 0.02, "matriz_v2": True},
    "sem_curva_choque_v2_priori": {"transicao_centro": None, "choque_nacional": 0.02, "matriz_v2": True,
                                   "sd_priori_informativa": 1.0},
}
DESCRICAO = {
    "atual": "Modelo usado ao vivo (curva de transição até 25%)",
    "sem_curva": "Sem a curva de transição",
    "sem_curva_choque": "Sem curva + choque nacional (2% do eleitorado restante na margem)",
    "sem_curva_choque_v2": "Sem curva + choque nacional + matriz v2 (branco/nulo → candidatos, falta separada)",
    "sem_curva_choque_v2_priori": "Igual à anterior, com priori mais larga (desvio 1,0 em vez de 0,7)",
}


def carregar():
    """1º turno por município + retratos do 2º turno -> (base, retratos)."""
    t1 = pd.read_csv(dados(2026, "presidente", "mun_t1.csv.gz"), dtype={"mun": str})
    mun = pd.read_csv(os.path.join(COMUM, "municipios.csv"), dtype={"mun": str, "cdi": str})
    base = mun.merge(t1, on=["uf", "mun"], how="inner")
    base = pd.DataFrame({"uf": base["uf"], "mun": base["mun"], "nome": base["nome"],
                         "capital": base["capital"].astype(bool), "E1": base["E"], "A1": base["A"],
                         "B1": base["B"], "O1": base["O"], "W1": base["brancos"] + base["nulos"]})
    ret = pd.read_csv(dados(2026, "presidente", "retratos_t2.csv.gz"), dtype={"cod_tse": str})
    ret = ret.rename(columns={"cod_tse": "mun", "eleitores_t2": "E2", "eleitores_apurados_t2": "Ea",
                              "A_apurado_t2": "A2", "B_apurado_t2": "B2", "branco_nulo_apurado_t2": "W2",
                              "comparecimento_apurado_t2": "C2"})
    return base, ret


def retrato(base, ret, hora):
    r = ret[ret["hora"] == hora].drop(columns=["hora", "pct_secoes"])
    df = base.merge(r, on=["uf", "mun"], how="left")
    for c in ["Ea", "A2", "B2", "W2", "C2"]:
        df[c] = df[c].fillna(0)
    df["E2"] = df["E2"].where(df["E2"] > 0, df["E1"]).fillna(df["E1"])
    return df


def crps(amostras, y):
    """CRPS de uma amostra (menor é melhor): E|X - y| - E|X - X'| / 2."""
    x = np.sort(amostras)
    n = len(x)
    return float(np.abs(x - y).mean() - (2 * np.arange(1, n + 1) - n - 1) @ x / n ** 2)


def rodar_uma(df, cfg):
    d, X, Y = modelo.preparar(df)
    aj = modelo.ajustar(d, X, Y, cfg)
    final = modelo.simular(d, X, Y, aj, cfg)
    out = {"Brasil": final.sum(1)}
    for uf, idx in d.groupby("uf").indices.items():
        out[uf.upper()] = final[:, idx].sum(1)
    return {g: 100 * s[:, 0] / np.maximum(s[:, 0] + s[:, 1], 1) for g, s in out.items()}


def faixa(p):
    for lo, hi, nome in FAIXAS:
        if lo < p <= hi or (p == 0 and lo < 0):
            return nome
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variantes", nargs="+", default=list(VARIANTES))
    ap.add_argument("--passo", type=int, default=1, help="usa um a cada N retratos")
    ap.add_argument("--saida", default=os.path.join(RESULTADOS, "rejogo-2026"))
    ap.add_argument("--so-resumo", action="store_true", help="refaz resumo e gráfico a partir de previsoes.csv")
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)
    if a.so_resumo:
        res = pd.read_csv(os.path.join(a.saida, "previsoes.csv"))
        variantes = list(dict.fromkeys(res["variante"]))
        finalizar(res, variantes, a.saida)
        return
    base, ret = carregar()
    horas = sorted(ret["hora"].unique())
    pct = ret.groupby("hora")["pct_secoes"].first()
    # resultado final: o último retrato (99,86% das seções) completado pelo modelo usado ao vivo
    ult = retrato(base, ret, horas[-1])
    real = {g: float(v.mean()) for g, v in rodar_uma(ult, modelo.config_2026()).items()}
    usar = horas[:-1][::a.passo]
    linhas = []
    for nome in a.variantes:
        cfg = dataclasses.replace(modelo.config_2026(), **VARIANTES[nome])
        for h in usar:
            t0 = time.time()
            sims = rodar_uma(retrato(base, ret, h), cfg)
            for g, v in sims.items():
                y = real[g]
                q = np.percentile(v, [5, 25, 50, 75, 95])
                linhas.append({"variante": nome, "hora": h, "pct_secoes": float(pct[h]), "grupo": g,
                               "media": float(v.mean()), "p05": q[0], "p25": q[1], "p75": q[3], "p95": q[4],
                               "prob_A": float((v > 50).mean()), "final": y, "crps": crps(v, y)})
            b = [r for r in linhas if r["grupo"] == "Brasil"][-1]
            print(f"{nome:28s} {pct[h]:6.2f}%  {b['media']:6.2f} [{b['p05']:6.2f}, {b['p95']:6.2f}] "
                  f"P={b['prob_A']:.2f} final {real['Brasil']:.2f} ({time.time() - t0:.1f}s)", flush=True)
    res = pd.DataFrame(linhas)
    res["erro"] = res["media"] - res["final"]
    res["largura90"] = res["p95"] - res["p05"]
    res["faixa"] = res["pct_secoes"].map(faixa)
    res.round(4).to_csv(os.path.join(a.saida, "previsoes.csv"), index=False)
    finalizar(res, a.variantes, a.saida)


def finalizar(res, variantes, saida):
    # cobertura com tolerância: o intervalo "cobre" se o final está nele ou a menos de TOL pontos dele
    res["cobre90"] = (res["p05"] - TOL <= res["final"]) & (res["final"] <= res["p95"] + TOL)
    res["cobre50"] = (res["p25"] - TOL <= res["final"]) & (res["final"] <= res["p75"] + TOL)
    resumo = resumir(res)
    resumo.round(4).to_csv(os.path.join(saida, "resumo.csv"), index=False)
    with open(os.path.join(saida, "variantes.json"), "w", encoding="utf-8") as f:
        json.dump({k: {"mudancas": VARIANTES[k], "descricao": DESCRICAO[k]} for k in variantes}, f,
                  ensure_ascii=False, indent=1)
    grafico(res, variantes, os.path.join(saida, "rejogo.png"))
    pd.set_option("display.width", 200)
    print(resumo.round(3).to_string(index=False))


def resumir(res):
    ordem = [f[2] for f in FAIXAS]
    out = []
    for (v, fx), g in res.groupby(["variante", "faixa"]):
        br, uf = g[g["grupo"] == "Brasil"], g[g["grupo"] != "Brasil"]
        out.append({"variante": v, "faixa": fx, "n_retratos": len(br),
                    "br_erro_medio": br["erro"].mean(), "br_cobre90": br["cobre90"].mean(),
                    "br_largura90": br["largura90"].mean(), "br_crps": br["crps"].mean(),
                    "uf_cobre90": uf["cobre90"].mean(), "uf_cobre50": uf["cobre50"].mean(),
                    "uf_crps": uf["crps"].mean()})
    r = pd.DataFrame(out)
    r["o"] = r["faixa"].map(ordem.index)
    tot = res.groupby("variante").apply(lambda g: pd.Series({
        "faixa": "todas", "n_retratos": int((g["grupo"] == "Brasil").sum()),
        "br_erro_medio": g.loc[g["grupo"] == "Brasil", "erro"].mean(),
        "br_cobre90": g.loc[g["grupo"] == "Brasil", "cobre90"].mean(),
        "br_largura90": g.loc[g["grupo"] == "Brasil", "largura90"].mean(),
        "br_crps": g.loc[g["grupo"] == "Brasil", "crps"].mean(),
        "uf_cobre90": g.loc[g["grupo"] != "Brasil", "cobre90"].mean(),
        "uf_cobre50": g.loc[g["grupo"] != "Brasil", "cobre50"].mean(),
        "uf_crps": g.loc[g["grupo"] != "Brasil", "crps"].mean(),
        "chama_99": chamada(g[g["grupo"] == "Brasil"])}), include_groups=False).reset_index()
    tot["o"] = 99
    return pd.concat([r, tot], ignore_index=True).sort_values(["variante", "o"]).drop(columns="o")


def chamada(br):
    """Primeiro % apurado em que a chance do vencedor real passou de 99% (e ficou)."""
    br = br.sort_values("pct_secoes")
    venc = br["final"].iloc[0] > 50
    ok = (br["prob_A"] >= 0.99) if venc else (br["prob_A"] <= 0.01)
    falha = (~ok).to_numpy()
    if falha.all():
        return float("nan")
    ult_falha = np.flatnonzero(falha)
    i = ult_falha[-1] + 1 if len(ult_falha) else 0
    return float(br["pct_secoes"].iloc[i]) if i < len(br) else float("nan")


def grafico(res, variantes, caminho):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    br = res[res["grupo"] == "Brasil"]
    fig, axs = plt.subplots(len(variantes), 1, figsize=(8, 2.3 * len(variantes)), sharex=True, sharey=True)
    axs = np.atleast_1d(axs)
    for ax, v in zip(axs, variantes):
        g = br[br["variante"] == v].sort_values("pct_secoes")
        x = np.sqrt(g["pct_secoes"])  # raiz para abrir o começo da noite
        fora = ~g["cobre90"]
        ax.vlines(x, g["p05"], g["p95"], color=np.where(fora, "#2a6fb0", "#b9b4aa"), lw=np.where(fora, 2, 1.2))
        ax.scatter(x, g["media"], s=10, color=np.where(fora, "#2a6fb0", "#8f8b82"), zorder=3)
        ax.axhline(g["final"].iloc[0], color="#5f5c55", lw=1)
        ax.axhline(50, color="#d9d5cc", lw=0.8, ls=":")
        ax.set_title(DESCRICAO.get(v, v), fontsize=9, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylabel("Lula (%)", fontsize=8)
    ticks = [0, 1, 5, 10, 25, 50, 75, 100]
    axs[-1].set_xticks(np.sqrt(ticks), [f"{t}%" for t in ticks])
    axs[-1].set_xlabel("seções apuradas (escala de raiz quadrada)")
    fig.suptitle("Rejogo da apuração de 2026: previsão e intervalo de 90% (azul = final fora do intervalo)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(caminho, dpi=130)


if __name__ == "__main__":
    main()
