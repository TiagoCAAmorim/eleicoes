import json
import os
import subprocess
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from eleicoes.modelos import transferencia as modelo  # noqa: E402


def test_matriz_soma_um():
    th = np.random.default_rng(0).normal(size=(50, modelo.NPAR))
    M = modelo.matriz(th)
    assert np.allclose(M.sum(-1), 1)
    assert (M >= 0).all()


def test_config_2026_le_priori():
    cfg = modelo.config_2026()
    assert cfg.priori and "brasil|Brasil" in cfg.priori


def test_gera_site(tmp_path):
    saida = tmp_path / "site"
    subprocess.run([sys.executable, os.path.join(RAIZ, "scripts", "gerar_site.py"), "--saida", str(saida)], check=True)
    for pag in ["index.html", "modelos.html", "analises.html", "estilo.css", "2026/presidente/index.html",
                "2026/presidente/analises.html", "2026/presidente/indicadores.html"]:
        assert (saida / pag).exists(), pag
    inicio = (saida / "index.html").read_text(encoding="utf-8")
    assert "{{" not in inicio and "2026/presidente/" in inicio
    painel = (saida / "2026/presidente/index.html").read_text(encoding="utf-8")
    assert 'class="lx-nav"' in painel and "lx-refresh" not in painel
    assert '"fluxos"' in painel and 'id="chart-sankey"' in painel


def test_catalogo_aponta_para_resultados():
    with open(os.path.join(RAIZ, "config", "eleicoes.json"), encoding="utf-8") as f:
        for e in json.load(f):
            assert os.path.isdir(os.path.join(RAIZ, "resultados", e["resultados"], "web")), e["id"]


def test_fluxos_conservam_votos():
    import pandas as pd
    from eleicoes.site.exportar import fluxos
    mun = pd.read_csv(os.path.join(RAIZ, "resultados/2026-presidente/dados_municipios.csv"), sep=";", decimal=",",
                      encoding="utf-8-sig")
    f = pd.DataFrame(fluxos(mun, "Lula", "Flávio"))
    br = f[f.grupo == "Brasil"]
    # cada origem distribui todo o seu eleitorado (reescalado para o 2º turno) entre os destinos
    assert abs(br.votos.sum() - mun.eleitores_t2.sum()) / mun.eleitores_t2.sum() < 1e-4
    assert set(br.destino) <= {"Lula", "Flávio", "Branco/nulo", "Abstenção"}
    regioes = f[f.grupo != "Brasil"].groupby(["origem", "destino"]).votos.sum()
    assert (abs(regioes - br.set_index(["origem", "destino"]).votos) <= 10).all()


def test_gerador_estresse_conserva_validos():
    """A eleição sintética só redistribui os votos válidos de cada seção entre A e B."""
    import pandas as pd
    from eleicoes.modelos import estresse as es
    base = pd.DataFrame({"uf": ["sp", "sp"], "mun": ["1", "2"], "nome": ["a", "b"], "capital": [False, False],
                         "E1": [1000, 2000], "A1": [400, 900], "B1": [400, 700], "O1": [100, 200], "W1": [50, 100]})
    sec = pd.DataFrame({"uf": ["sp"] * 4, "mun": ["1", "1", "2", "2"], "zona": [1, 1, 2, 2], "secao": [1, 2, 1, 2],
                        "aptos": [500, 500, 1000, 1000], "comp": [400, 400, 800, 800], "v13": [200, 180, 400, 420],
                        "v22": [180, 200, 350, 330], "brancos": [10, 10, 25, 25], "nulos": [10, 10, 25, 25],
                        "outros": [0, 0, 0, 0]})
    pri = {"brasil|Brasil": list(np.zeros(8))}
    g = es.GeradorApuracao(base, sec, pri)
    s, t, beta, gama = g.rodada(np.random.default_rng(0), es.ParamEstresse())
    assert ((s["v13"] + s["v22"]) == (sec["v13"] + sec["v22"])).all()
    assert len(t) == len(sec) and np.isfinite(t).all()


def test_priori_linha_outros_bate_com_a_pesquisa():
    """A linha Outros ajustada faz a previsão de antes da apuração bater com a pesquisa."""
    import pandas as pd
    from eleicoes.modelos import priori, transferencia as modelo
    rng = np.random.default_rng(1)
    n = 60
    E = rng.integers(5_000, 50_000, n).astype(float)
    base = pd.DataFrame({"uf": rng.choice(["sp", "ba", "rs"], n), "mun": [f"{i:05d}" for i in range(n)],
                         "nome": "x", "capital": False, "E1": E, "A1": 0.35 * E, "B1": 0.3 * E, "O1": 0.12 * E,
                         "W1": 0.03 * E, "E2": E, "Ea": 0.0, "A2": 0.0, "B2": 0.0, "W2": 0.0, "C2": 0.0})
    pri = priori.media([{"brasil|Brasil": list(modelo.THETA0)}, {"brasil|Brasil": list(modelo.THETA0 + 0.2)}])
    assert np.allclose(pri["brasil|Brasil"], modelo.THETA0 + 0.1)
    th = priori.outros_pela_pesquisa(base, pri, 52.0)
    t = np.array(pri["brasil|Brasil"])
    t[3:6] = th
    y = (base[["A1", "B1", "O1", "W1"]].sum() / E.sum()).tolist()
    x = np.array(y + [1 - sum(y)]) @ modelo.matriz(t)
    assert abs(100 * x[0] / (x[0] + x[1]) - 52.0) < 0.05
