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
    for pag in ["governador.html", "prefeito.html", "estresse.html"]:
        texto = (saida / pag).read_text(encoding="utf-8")
        assert "{{" not in texto and 'class="botao-cafe"' in texto and 'class="selo' in texto, pag
    for nome in ["governador", "prefeito", "estresse"]:
        d = json.loads((saida / "testes" / f"{nome}.json").read_text(encoding="utf-8"))
        assert d["pcts"][0] == 0
    gov = json.loads((saida / "testes" / "governador.json").read_text(encoding="utf-8"))
    assert len(gov["t2"]) == 46 and all(len(r["pontos"]) == len(gov["pcts"]) for e in gov["t2"] for r in e["rodadas"])


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


def test_matriz_v2_usa_priori_v2():
    """Com matriz_v2 e uma priori de 11 parâmetros, o ponto de partida dos 3 extras vem da priori; com a matriz
    original, a mesma priori é cortada nos 8 primeiros."""
    import pandas as pd
    from eleicoes.modelos import transferencia as modelo
    th = np.random.default_rng(2).normal(size=(20, modelo.NPAR + 3))
    M = modelo.matriz(th)
    assert np.allclose(M.sum(-1), 1) and (M >= 0).all()
    extra = [modelo._logit(0.2 / 0.25), modelo._logit(0.01 / 0.25), modelo._logit(0.02 / 0.5)]
    pri = {"brasil|Brasil": list(modelo.THETA0) + extra}
    n = 10
    E = np.full(n, 10_000.0)
    df = pd.DataFrame({"uf": "sp", "mun": [f"{i:05d}" for i in range(n)], "nome": "x", "capital": False, "E1": E,
                       "A1": 0.35 * E, "B1": 0.3 * E, "O1": 0.12 * E, "W1": 0.03 * E, "E2": E, "Ea": 0.0,
                       "A2": 0.0, "B2": 0.0, "W2": 0.0, "C2": 0.0})
    d, X, Y = modelo.preparar(df)
    aj = modelo.ajustar(d, X, Y, modelo.Config(priori=pri, matriz_v2=True, niveis=[]))
    mu = aj.grupos[("brasil", "Brasil")][0]
    assert len(mu) == modelo.NPAR + 3 and np.allclose(mu[modelo.NPAR:], extra)
    aj = modelo.ajustar(d, X, Y, modelo.Config(priori=pri, niveis=[]))
    assert len(aj.grupos[("brasil", "Brasil")][0]) == modelo.NPAR


def test_primeiro_turno_recupera_matriz():
    """Modelo do 1º turno: antes da apuração bate com a pesquisa; com tudo apurado, a previsão é o resultado."""
    import pandas as pd
    from eleicoes.modelos import primeiro_turno as m1
    rng = np.random.default_rng(1)
    U, R, D = 300, 3, 5                      # referência: 2 categorias + abstenção; destinos: A, B, demais, W, N
    Mv = np.array([[0.6, 0.1, 0.05, 0.05, 0.2], [0.1, 0.55, 0.05, 0.05, 0.25], [0.1, 0.1, 0.02, 0.03, 0.75]])
    xr = rng.dirichlet([3, 3, 2], U)
    E = rng.integers(2000, 50000, U).astype(float)
    y = (xr @ Mv) * E[:, None]
    df = pd.DataFrame({"uf": rng.choice(["sp", "ba", "rs"], U), "mun": [str(i) for i in range(U)], "capital": False,
                       "E": E, "rE": E, "r0": xr[:, 0] * E, "r1": xr[:, 1] * E, "Ea": E,
                       "d0": y[:, 0], "d1": y[:, 1], "d2": y[:, 2], "d3": y[:, 3], "C": y[:, :4].sum(1)})
    cfg = m1.Config(n_sims=200, niveis=["uf"])
    d, X, Y = m1.preparar(df, R, D, cfg)
    alvo = np.array([0.3, 0.3, 0.04, 0.05, 0.31])
    th0, xbar = m1.priori(X, E, alvo, np.zeros((R, D), bool), cfg)
    assert np.allclose(xbar @ m1.matriz(th0), alvo, atol=1e-4)
    aj = m1.ajustar(d, X, Y, th0, xbar, alvo, cfg)
    r = m1.resumo(m1.simular(d, X, Y, aj, cfg), ["A", "B"])
    real = 100 * y[:, 0].sum() / y[:, :3].sum()
    assert abs(r["candidatos"][0]["media"] - real) < 0.05
