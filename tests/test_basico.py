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
