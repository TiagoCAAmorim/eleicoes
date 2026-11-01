"""Roda o modelo sobre um retrato da apuração e monta os resumos por grupo."""
import numpy as np

from ..dados.geo import PORTES
from ..site import exportar, mapa_mun
from . import transferencia as modelo

NIVEIS = [("Brasil", "brasil"), ("Região", "regiao"), ("Porte", "porte"), ("UF", "uf")]
ORDEM_REGIAO = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul", "Exterior"]


def _transferencias(aj, cfg, nomes):
    a, b = nomes
    rot = [f"{a}→{b}", f"{b}→{a}", "Votantes→abstenção", f"Outros→{a}", f"Outros→{b}", "Outros→branco/nulo",
           "Outros→abstenção", f"Abstenção→{a}", f"Abstenção→{b}"]
    rng = np.random.default_rng(cfg.seed + 1)
    out = {}
    chaves = [("brasil", "Brasil")] + [("regiao", r) for r in ORDEM_REGIAO]
    for nivel, nome in chaves:
        if (nivel, nome) not in aj.grupos:
            continue
        mu, cov = aj.grupos[(nivel, nome)]
        th = rng.multivariate_normal(mu, cov, size=1000, check_valid="ignore")
        p = 100 * modelo.parametros_legiveis(th)
        out[nome] = {r: (float(p[:, i].mean()), float(np.percentile(p[:, i], 5)), float(np.percentile(p[:, i], 95)))
                     for i, r in enumerate(rot)}
    return out


def prever(df, nomes, cfg=None):
    cfg = cfg or modelo.config_2026()
    df, X, Y = modelo.preparar(df)
    aj = modelo.ajustar(df, X, Y, cfg)
    final = modelo.simular(df, X, Y, aj, cfg)
    grupos = {}
    for rotulo, col in NIVEIS:
        g = {}
        sims = modelo.agregar(df, final, col)
        ordem = {"regiao": ORDEM_REGIAO, "porte": PORTES}.get(col, sorted(sims))
        for nome in ordem:
            if nome not in sims:
                continue
            sel = df[col] == nome
            r = modelo.resumo_grupo(sims[nome])
            ea, e2 = df.loc[sel, "Ea"].sum(), df.loc[sel, "E2"].sum()
            va, vb = df.loc[sel, "A2"].sum(), df.loc[sel, "B2"].sum()
            # % de seções totalizadas, como o TSE mostra (sem as colunas de seções, % do eleitorado apurado)
            if "ts" in df and df.loc[sel, "ts"].sum() > 0:
                r["pct_apurado"] = float(100 * df.loc[sel, "st"].sum() / df.loc[sel, "ts"].sum())
            else:
                r["pct_apurado"] = float(100 * ea / max(e2, 1))
            r["parcial"] = float(100 * va / max(va + vb, 1)) if va + vb > 0 else float("nan")
            r["eleitores"] = float(e2)
            r["pct_eleitorado"] = float(100 * e2 / max(df["E2"].sum(), 1))
            r["votos_A_apurado"], r["votos_B_apurado"] = float(va), float(vb)
            r["votos_A_previsto"] = float(sims[nome][:, 0].mean())
            r["votos_B_previsto"] = float(sims[nome][:, 1].mean())
            g[nome] = r
        grupos[rotulo] = g
    va, vb = df["A2"].sum(), df["B2"].sum()
    return {
        "nomes": list(nomes),
        "grupos": grupos,
        "parcial_A": float(100 * va / max(va + vb, 1)) if va + vb else 50.0,
        "transferencias": _transferencias(aj, cfg, [n.split()[0] for n in nomes]),  # nomes curtos nas tabelas
        "s0": aj.s0,
        "_municipios": mapa_mun.tabela(df, final),  # não vai para o JSON
        "_csv": {"dados_municipios": exportar.municipios(df, aj, final, nomes),
                 "coeficientes_grupos": exportar.coeficientes(aj, nomes)},  # idem
    }
