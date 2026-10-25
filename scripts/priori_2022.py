"""Estima as transferências 1º→2º turno de 2022 (apuração completa) em todos os níveis e
salva em data/priori_2022.json, para servir de ponto de partida em 2026."""
import json
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import backtest  # noqa: E402
from eleicao import modelo  # noqa: E402

base, sec = backtest.carregar()
cols = ["uf", "mun", "nome", "capital", "E1", "A1", "B1", "O1", "W1", "E2", "Ea", "A2", "B2", "W2", "C2"]
df, X, Y = modelo.preparar(backtest.snapshot(base, sec, np.ones(len(sec), bool))[cols])
aj = modelo.ajustar(df, X, Y, modelo.Config())
out = {f"{n}|{g}": [round(float(v), 4) for v in mu] for (n, g), (mu, _) in aj.grupos.items()}
with open(os.path.join(AQUI, "data/priori_2022.json"), "w") as f:
    json.dump(out, f, indent=0)
br = modelo.parametros_legiveis(aj.grupos[("brasil", "Brasil")][0]) * 100
print("Brasil 2022:", dict(zip(modelo.PAR_NOMES, np.round(br, 1))))
