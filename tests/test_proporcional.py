import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eleicoes.modelos import proporcional as pr  # noqa: E402


def _cands(listas):
    return pd.DataFrame([{"sq": f"{a}{i}", "agrem": a, "votos": v} for a, vs in listas.items()
                         for i, v in enumerate(vs)])


def test_quociente_eleitoral_arredonda_meio_para_baixo():
    assert pr.quociente_eleitoral(1050, 10) == 105
    assert pr.quociente_eleitoral(1055, 10) == 105    # fração 0,5 é desprezada
    assert pr.quociente_eleitoral(1056, 10) == 106


def test_dhondt_so_quem_atinge_qe_ate_2014():
    # 10 vagas, 1000 votos, QE 100: A 480 (QP 4), B 350 (QP 3), C 95 (não atinge), D 75
    votos = {"A": 480, "B": 350, "C": 95, "D": 75}
    c = _cands({k: [v // 5] * 6 for k, v in votos.items()})
    el, fases, qe = pr.distribuir(votos, c, 10, pr.REGRAS["2006"])
    assert qe == 100
    n = pd.Series([e[0] for e in el]).value_counts()
    # sobras: A 480/5=96, B 350/4=87.5 → A; A 480/6=80, B 87.5 → B; B 350/5=70, A 80 → A
    assert n["A"] == 6 and n["B"] == 4 and "C" not in n


def test_sobras_para_todos_em_2018():
    votos = {"A": 480, "B": 350, "C": 95, "D": 75}
    c = _cands({k: [v // 5] * 6 for k, v in votos.items()})
    el, _, _ = pr.distribuir(votos, c, 10, pr.REGRAS["2018"])
    n = pd.Series([e[0] for e in el]).value_counts()
    # C 95/1 = 95 entra na disputa e leva uma cadeira das sobras
    assert n.get("C", 0) == 1


def test_minimo_individual_e_80_por_cento_em_2022():
    # QE 100; C tem 85 (≥80%) mas nenhum candidato com 20 votos; D tem 70 (<80%)
    votos = {"A": 480, "B": 365, "C": 85, "D": 70}
    c = _cands({"A": [200, 150, 60, 40, 15, 15], "B": [150, 100, 50, 30, 20, 15], "C": [19, 19, 19, 19, 9],
                "D": [70]})
    el, fases, _ = pr.distribuir(votos, c, 10, pr.REGRAS["2022"])
    n = pd.Series([e[0] for e in el]).value_counts()
    assert "C" not in n and "D" not in n
    # A: QP 4 com 10% (10 votos) → 4; B: QP 3 → 3; sobras com candidato ≥ 20
    assert len(el) == 10 and n["A"] + n["B"] == 10


def test_art111_ninguem_atinge_qe():
    votos = {"A": 30, "B": 30, "C": 40}
    c = _cands({"A": [30], "B": [20, 10], "C": [25, 15]})
    el, fases, _ = pr.distribuir(votos, c, 2, pr.REGRAS["2006"])
    assert el == ["A0", "C0"] and set(fases) == {"art111"}


def test_gallagher_zero_quando_proporcional():
    assert pr.gallagher({"a": 60, "b": 40}, {"a": 6, "b": 4}) < 1e-9
