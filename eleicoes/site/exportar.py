"""Tabelas para download (CSV): dados por município usados no modelo e coeficientes por grupo."""
import numpy as np
import pandas as pd

from ..modelos import transferencia as modelo


def _rotulos(nomes):
    a, b = [n.split()[0] for n in nomes]
    return [f"{a}->{b}", f"{b}->{a}", "votantes->abstencao", f"outros->{a}", f"outros->{b}", "outros->branco_nulo",
            "outros->abstencao", f"abstencao->{a}", f"abstencao->{b}"]


def coeficientes(aj, nomes):
    """Uma linha por grupo da hierarquia: transferências estimadas (%), com intervalo de 90% (aproximação de Laplace)."""
    rot = _rotulos(nomes)
    rng = np.random.default_rng(123)
    linhas = []
    for (nivel, nome), (mu, cov) in aj.grupos.items():
        th = rng.multivariate_normal(mu, cov, size=400, check_valid="ignore")
        p = 100 * modelo.parametros_legiveis(th)
        m = 100 * modelo.parametros_legiveis(np.asarray(mu)[None])[0]
        linha = {"nivel": nivel, "grupo": nome}
        for i, r in enumerate(rot):
            linha[f"{r} (%)"] = round(float(m[i]), 3)
            linha[f"{r} p05"] = round(float(np.percentile(p[:, i], 5)), 3)
            linha[f"{r} p95"] = round(float(np.percentile(p[:, i], 95)), 3)
        linhas.append(linha)
    return pd.DataFrame(linhas)


def municipios(df, aj, final, nomes):
    """Entradas do modelo por município (1º turno, 2º turno apurado), o grupo-folha cujos coeficientes
    foram usados e o resultado previsto (média e intervalo de 90% das simulações, sem os cenários)."""
    a, b = [n.split()[0] for n in nomes]
    rot = _rotulos(nomes)
    mu = np.array([aj.grupos[k][0] for k in aj.folhas])
    leg = 100 * modelo.parametros_legiveis(mu)[aj.folha]
    va, vb = final[:, :, 0], final[:, :, 1]
    pa = 100 * va / np.maximum(va + vb, 1)
    out = pd.DataFrame({
        "uf": df["uf"].values, "cod_tse": df["mun"].values, "municipio": df["nome"].values,
        "regiao": df["regiao"].values, "porte": df["porte"].values,
        "grupo_coeficientes": [aj.folhas[i][1] for i in aj.folha],
        "eleitores_t1": df["E1"].values, f"{a}_t1": df["A1"].values, f"{b}_t1": df["B1"].values,
        "outros_t1": df["O1"].values, "branco_nulo_t1": df["W1"].values,
        "eleitores_t2": df["E2"].values, "eleitores_apurados_t2": df["Ea"].values,
        f"{a}_apurado_t2": df["A2"].values, f"{b}_apurado_t2": df["B2"].values,
        "branco_nulo_apurado_t2": df["W2"].values, "comparecimento_apurado_t2": df["C2"].values,
        f"{a}_previsto": va.mean(0).round(), f"{b}_previsto": vb.mean(0).round(),
        "branco_nulo_previsto": final[:, :, 2].mean(0).round(), "abstencao_prevista": final[:, :, 3].mean(0).round(),
        f"{a}_pct_validos_previsto": pa.mean(0).round(3),
        f"{a}_pct_p05": np.percentile(pa, 5, axis=0).round(3), f"{a}_pct_p95": np.percentile(pa, 95, axis=0).round(3),
    })
    for i, r in enumerate(rot):
        out[f"coef {r} (%)"] = leg[:, i].round(3)
    return out


def resumo_grupos(res):
    """Resultados principais por grupo (o que a página mostra)."""
    a, b = [n.split()[0] for n in res["nomes"]]
    linhas = []
    for nivel, grupos in res["grupos"].items():
        for nome, g in grupos.items():
            linhas.append({
                "nivel": nivel, "grupo": "Exterior" if nome == "zz" else (nome.upper() if nivel == "UF" else nome),
                "eleitores": round(g.get("eleitores", np.nan)), "pct_eleitorado": round(g.get("pct_eleitorado", np.nan), 3),
                "pct_apurado": round(g["pct_apurado"], 3), f"{a}_apurado_pct": round(g["parcial"], 3),
                f"{a}_previsto_pct": round(g["A_media"], 3), f"{a}_p05": round(g["A_p05"], 3), f"{a}_p95": round(g["A_p95"], 3),
                f"chance_{a}": round(g["prob_A"], 4), f"chance_{b}": round(1 - g["prob_A"], 4),
                "comparecimento_previsto_pct": round(g["comparecimento"], 3),
                "branco_nulo_previsto_pct": round(g["brancos_nulos"], 3),
            })
    return pd.DataFrame(linhas)
