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


def fluxos(mun, nome_a, nome_b):
    """Votos que a matriz de transferência leva de cada origem do 1º turno a cada destino do 2º turno, somados por
    Brasil e região. `mun` é a tabela de `municipios()` (ou o dados_municipios.csv lido de volta). Os coeficientes
    são os do grupo-folha de cada município; o 1º turno é reescalado para o eleitorado do 2º turno, como no modelo.
    Devolve linhas {grupo, origem, destino, votos}."""
    t1 = [c for c in mun.columns if c.endswith("_t1")]           # eleitores, A, B, outros, branco/nulo
    coef = [c for c in mun.columns if c.startswith("coef ")]      # na ordem de modelo.PAR_NOMES
    E1 = mun[t1[0]].clip(lower=1).to_numpy(float)
    x = mun[t1[1:5]].to_numpy(float)
    x = np.column_stack([x, np.clip(E1 - x.sum(1), 0, None)]) / E1[:, None]
    x *= mun["eleitores_t2"].to_numpy(float)[:, None]
    p = mun[coef].to_numpy(float) / 100
    ab, ba, falta, oa, ob, ow, on, na, nb = p.T
    z = np.zeros_like(ab)
    M = np.stack([                                                # (U, origem, destino A B W N)
        np.stack([1 - ab - falta, ab, z, falta], -1),
        np.stack([ba, 1 - ba - falta, z, falta], -1),
        np.stack([oa, ob, ow, on], -1),
        np.stack([z, z, 1 - falta, falta], -1),
        np.stack([na, nb, z, 1 - na - nb], -1),
    ], 1)
    F = x[:, :, None] * M                                         # (U, 5, 4) votos
    origens = [nome_a, nome_b, "Outros", "Branco/nulo", "Abstenção"]
    destinos = [nome_a, nome_b, "Branco/nulo", "Abstenção"]
    out = []
    grupos = [("Brasil", np.ones(len(mun), bool))] + [(g, (mun["regiao"] == g).to_numpy()) for g in
                                                       ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul", "Exterior"]]
    for g, sel in grupos:
        if not sel.any():
            continue
        tot = F[sel].sum(0)
        for i, o in enumerate(origens):
            for j, d in enumerate(destinos):
                if tot[i, j] >= 0.5:
                    out.append({"grupo": g, "origem": o, "destino": d, "votos": int(round(tot[i, j]))})
    return out
