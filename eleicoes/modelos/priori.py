"""Priori calibrada com os 2º turnos presidenciais de 2006 a 2022 (docs/calibracao-priori.md).

- Matriz de partida: média (escala logit), grupo a grupo, das matrizes estimadas com a apuração completa de cada
  eleição anterior (dados/priori/presidente_<ano>.json, geradas por scripts/calibrar_priori.py). A matriz de uma
  eleição só erra muito mais que a média, porque a linha Outros muda com os candidatos.
- Linha Outros: ajustada para que a previsão antes da apuração bata com a última pesquisa (votos válidos).
- Incerteza: desvio 0,3 na linha Outros (o erro das pesquisas), hierarquia mais apertada (tau 0,15) e choque inicial
  por UF de 2%, calibrados para que o intervalo de 90% antes da apuração cubra ~90% em Brasil e UFs.
"""
import json
import os

import numpy as np

from ..caminhos import PRIORI
from . import transferencia as modelo

ANOS_BASE = [2006, 2010, 2014, 2018, 2022]
CALIBRACAO = {"tau": 0.15, "choque_uf_inicio": 0.02, "sd_outros": 0.3}
COLS = ["uf", "mun", "nome", "capital", "E1", "A1", "B1", "O1", "W1", "E2", "Ea", "A2", "B2", "W2", "C2"]


def carregar(ano, cargo="presidente"):
    with open(os.path.join(PRIORI, f"{cargo}_{ano}.json")) as f:
        return json.load(f)


def media(prioris):
    """Média (escala logit) de várias prioris, grupo a grupo (só os grupos presentes em todas)."""
    chaves = set.intersection(*(set(p) for p in prioris))
    return {k: [float(x) for x in np.mean([p[k] for p in prioris], axis=0)] for k in sorted(chaves)}


def outros_pela_pesquisa(base, pri, alvo):
    """Linha Outros (logits de oA, oB, oW contra oN) que faz a previsão de antes da apuração bater com `alvo`
    (% de A nos votos válidos). Parte da linha Outros da priori e desloca Outros→A e Outros→B em sentidos opostos."""
    s = base[COLS].copy()
    s[["Ea", "A2", "B2", "W2", "C2"]] = 0.0
    df, X, Y = modelo.preparar(s)
    aj = modelo.ajustar(df, X, Y, modelo.Config(priori=pri))
    th = np.array([aj.grupos[k][0] for k in aj.folhas])[aj.folha]
    w = df["E2"].values[:, None]

    def prev(d):
        t = th.copy()
        t[:, 3] += d
        t[:, 4] -= d
        y = np.einsum("uk,ukd->ud", X, modelo.matriz(t)) * w
        return 100 * y[:, 0].sum() / (y[:, 0] + y[:, 1]).sum()

    lo, hi = -6.0, 6.0
    for _ in range(60):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if prev(m) < alvo else (lo, m)
    t0 = np.array(aj.grupos[("brasil", "Brasil")][0])
    return (float(t0[3] + m), float(t0[4] - m), float(t0[5]))


def config_calibrada(base, pesquisa_a, anos=None, **mudancas):
    """Config do modelo com a priori calibrada. `base`: municípios (1º turno e eleitorado do 2º);
    `pesquisa_a`: % de A nos válidos na última pesquisa; `anos`: eleições usadas na média (padrão 2006–2022)."""
    pri = media([carregar(a) for a in (anos or ANOS_BASE)])
    th = outros_pela_pesquisa(base, pri, pesquisa_a)
    return modelo.Config(priori=pri, theta_outros=th, **{**CALIBRACAO, **mudancas})
