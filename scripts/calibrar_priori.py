"""Calibração da priori com os 2º turnos presidenciais de 2006 a 2022 (base histórica do TSE).

1. Estima a matriz de transferência de cada eleição com a apuração completa (a priori que a eleição seguinte usaria)
   e salva em dados/priori/presidente_<ano>.json (2022 já existe, feita da base por seção, e não é sobrescrita).
2. Previsão antes da apuração: para cada eleição de 2010 a 2022, roda o modelo revisado sem nenhum voto apurado, com
   a priori da eleição anterior, e compara com o resultado (Brasil e UFs). Variantes do desvio da priori.
3. Rejogo: simula a apuração de cada ano por município (ordem parecida com a real, com viés sorteado nas primeiras
   seções de cada cidade) e mede erro e cobertura por % apurado.

    python scripts/calibrar_priori.py                  # 1 e 2
    python scripts/calibrar_priori.py --rejogo 3       # também o rejogo, 3 rodadas por ano
Saídas em resultados/calibracao-priori/.
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import DADOS, PRIORI, RESULTADOS
from eleicoes.dados import historico as hist
from eleicoes.dados.geo import REGIAO
from eleicoes.modelos import priori, transferencia as modelo

OUT = os.path.join(RESULTADOS, "calibracao-priori")
PONTOS = [1, 2, 3, 5, 7.5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 95]
COLS = ["uf", "mun", "nome", "capital", "E1", "A1", "B1", "O1", "W1", "E2", "Ea", "A2", "B2", "W2", "C2"]


def priori_do_ano(ano, base):
    caminho = os.path.join(PRIORI, f"presidente_{ano}.json")
    df, X, Y = modelo.preparar(base[COLS])
    aj = modelo.ajustar(df, X, Y, modelo.Config())
    pri = {f"{n}|{g}": [round(float(v), 4) for v in mu] for (n, g), (mu, _) in aj.grupos.items()}
    if not os.path.exists(caminho):
        with open(caminho, "w") as f:
            json.dump(pri, f, indent=0)
    br = modelo.parametros_legiveis(aj.grupos[("brasil", "Brasil")][0]) * 100
    return pri, dict(zip(modelo.PAR_NOMES, np.round(br, 1)))


def vazio(base):
    s = base.copy()
    s[["Ea", "A2", "B2", "W2", "C2"]] = 0.0
    return s


def prever(s, cfg):
    df, X, Y = modelo.preparar(s[COLS])
    aj = modelo.ajustar(df, X, Y, cfg)
    sims = modelo.simular(df, X, Y, aj, cfg)
    return df, sims


def pa(x):
    return 100 * x["A2"].sum() / max(x["A2"].sum() + x["B2"].sum(), 1)


def avaliar(df, sims, real_br, real_uf):
    r = modelo.resumo_grupo(sims.sum(1))
    linhas = [{"nivel": "Brasil", "grupo": "Brasil", **r, "real": real_br}]
    for u, x in modelo.agregar(df, sims, "uf").items():
        linhas.append({"nivel": "UF", "grupo": u, **modelo.resumo_grupo(x), "real": real_uf[u]})
    t = pd.DataFrame(linhas)
    t["erro"] = t["A_media"] - t["real"]
    t["cobre90"] = (t["A_p05"] <= t["real"]) & (t["real"] <= t["A_p95"])
    t["largura90"] = t["A_p95"] - t["A_p05"]
    t["z"] = t["erro"] / ((t["A_p95"] - t["A_p05"]) / (2 * 1.645))
    return t


# cada variante: de onde vem a priori ("anterior" = eleição anterior, "media" = média de todas as anteriores), de onde
# vem a linha Outros ("oraculo" = a verdadeira daquela eleição, como se as pesquisas acertassem) e mudanças na Config
VARIANTES = {
    "revisado": ("anterior", None, {}),
    "priori_sd_0.35": ("anterior", None, {"sd_priori_informativa": 0.35}),
    "priori_sd_1.5": ("anterior", None, {"sd_priori_informativa": 1.5}),
    "nacional_3": ("anterior", None, {"choque_nacional": 0.03}),
    "media": ("media", None, {}),
    "oraculo_outros": ("anterior", "oraculo", {}),
    "media_oraculo": ("media", "oraculo", {}),
    "media_oraculo_sd_0.35": ("media", "oraculo", {"sd_priori_informativa": 0.35}),
    "mp_t015_ufi_002_o01": ("media", "pesquisa", {"sd_outros": 0.1, "tau": 0.15, "choque_uf_inicio": 0.02}),
    "mp_t015_ufi_002_o02": ("media", "pesquisa", {"sd_outros": 0.2, "tau": 0.15, "choque_uf_inicio": 0.02}),
    "mp_t015_ufi_002_o03": ("media", "pesquisa", {"sd_outros": 0.3, "tau": 0.15, "choque_uf_inicio": 0.02}),
    "mp_revisado": ("media", "pesquisa", {}),
    "mo_outros_0.1": ("media", "oraculo", {"sd_outros": 0.1}),
    "mo_outros_0.1_tau_0.25": ("media", "oraculo", {"sd_outros": 0.1, "tau": 0.25}),
    "mo_outros_0.1_tau_0.15": ("media", "oraculo", {"sd_outros": 0.1, "tau": 0.15}),
    "mo_o01_t015_ufi_002": ("media", "oraculo", {"sd_outros": 0.1, "tau": 0.15, "choque_uf_inicio": 0.02}),
    "mo_o01_t015_ufi_0": ("media", "oraculo", {"sd_outros": 0.1, "tau": 0.15, "choque_uf_inicio": 0.0}),
    "mo_outros_0.1_tau_0.1": ("media", "oraculo", {"sd_outros": 0.1, "tau": 0.1}),
    "mo_outros_0.1_tau_0.15_sd_0.35": ("media", "oraculo", {"sd_outros": 0.1, "tau": 0.15, "sd_priori_informativa": 0.35}),
    "mo_outros_0.1_sem_choques": ("media", "oraculo", {"sd_outros": 0.1, "choque_uf": 0, "choque_uf_inicio": 0,
                                                       "choque_nacional": 0}),
    "mo_outros_0.1_uf_inicio_0.02": ("media", "oraculo", {"sd_outros": 0.1, "choque_uf_inicio": 0.02}),
}


ANOS = hist.ANOS_PRESIDENTE + [2026]


def base_2026():
    """2026 vem dos retratos da apuração (o último é o resultado final), não da base histórica."""
    import rejogar_2026
    base, ret = rejogar_2026.carregar()
    ultimo = ret.sort_values("pct_secoes")["hora"].iloc[-1]
    return rejogar_2026.retrato(base, ret, ultimo), {"A": "LULA", "B": "FLÁVIO BOLSONARO"}


PESQUISAS = pd.read_csv(os.path.join(DADOS, "pesquisas", "presidente_t2.csv"))


def config(variante, ano, pris, base=None):
    fonte, outros, mud = VARIANTES[variante]
    anteriores = [a for a in hist.ANOS_PRESIDENTE if a < ano]   # 2026 não entra na média (só é alvo)
    pri = pris[ano - 4] if fonte == "anterior" else priori.media([pris[x] for x in anteriores])
    if outros == "oraculo":
        mud = {**mud, "theta_outros": tuple(np.array(pris[ano]["brasil|Brasil"])[3:6])}
    elif outros == "pesquisa":
        alvo = PESQUISAS.loc[PESQUISAS["ano"] == ano, "a_validos"].mean()
        mud = {**mud, "theta_outros": priori.outros_pela_pesquisa(base, pri, alvo)}
    return modelo.Config(priori=pri, **mud)


def ordem_municipios(base, rng, vies_sd=0.03):
    atraso = base["uf"].map(REGIAO).map({"Sul": 0.0, "Centro-Oeste": 0.05, "Sudeste": 0.12, "Norte": 0.25,
                                         "Nordeste": 0.3, "Exterior": 0.7}).fillna(0.3).values
    inicio = np.clip(0.3 * (atraso + 0.15 * base["capital"].values) + rng.normal(0, 0.12, len(base)), 0, None)
    duracao = 0.1 + 0.15 * np.log10(base["E2"].clip(lower=10).values) / 6 + rng.exponential(0.05, len(base))
    return inicio, duracao, rng.normal(0, vies_sd)


def retrato(base, inicio, duracao, vies, t):
    """Parte apurada de cada município no instante t; as primeiras seções vêm `vies` (margem) mais para A."""
    f = np.clip((t - inicio) / duracao, 0, 1)
    s = base.copy()
    s["Ea"] = np.round(f * base["E2"])
    fr = s["Ea"] / base["E2"].clip(lower=1)
    val = base["A2"] + base["B2"]
    desl = np.clip(vies / 2 * (1 - fr) * val, -base["B2"], base["A2"])
    s["A2"] = np.round((base["A2"] + desl) * fr)
    s["B2"] = np.round((base["B2"] - desl) * fr)
    s["W2"] = np.round(base["W2"] * fr)
    s["C2"] = np.round(base["C2"] * fr)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rejogo", type=int, default=0, help="rodadas do rejogo por ano (0 = não roda)")
    ap.add_argument("--variantes", default=",".join(VARIANTES))
    ap.add_argument("--variante-rejogo", default="media_oraculo")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    bases, pris, resumo = {}, {}, {}
    for ano in ANOS:
        base, nomes = base_2026() if ano == 2026 else hist.segundo_turno_presidente(ano)
        bases[ano] = base
        pris[ano], br = priori_do_ano(ano, base)
        resumo[ano] = {"A": nomes["A"], "B": nomes["B"], "A_validos": round(pa(base), 2), "transferencias": br}
        print(ano, nomes, round(pa(base), 2), br, flush=True)
    with open(os.path.join(OUT, "transferencias.json"), "w", encoding="utf-8") as f:
        json.dump(resumo, f, ensure_ascii=False, indent=1)

    # 2. antes da apuração
    linhas = []
    variantes = [v for v in a.variantes.split(",") if v]
    for ano in ANOS[1:]:
        base = bases[ano]
        real_br = pa(base)
        real_uf = {u: pa(g) for u, g in base.groupby("uf")}
        for nome in variantes:
            cfg = config(nome, ano, pris, base)
            df, sims = prever(vazio(base), cfg)
            t = avaliar(df, sims, real_br, real_uf).assign(ano=ano, variante=nome)
            linhas.append(t)
            b = t.iloc[0]
            print(f"{ano} {nome:15s} prev {b.A_media:5.2f} [{b.A_p05:5.2f}, {b.A_p95:5.2f}] real {real_br:5.2f}  "
                  f"erro {b.erro:+5.2f}  z {b.z:+5.2f}  UFs: |erro| {t.erro[1:].abs().mean():4.2f} "
                  f"cob90 {100 * t.cobre90[1:].mean():3.0f}%", flush=True)
    if linhas:
        pre = pd.concat(linhas, ignore_index=True)
        arq = "antes_da_apuracao.csv"
        if os.path.exists(os.path.join(OUT, arq)):   # acumula variantes rodadas em chamadas separadas
            ant = pd.read_csv(os.path.join(OUT, arq))
            pre = pd.concat([ant[~ant["variante"].isin(variantes)], pre], ignore_index=True)
        pre.to_csv(os.path.join(OUT, arq), index=False, float_format="%.4f")
        tab = pre.groupby(["variante", "nivel"]).agg(
            erro_medio=("erro", "mean"), erro_abs=("erro", lambda x: x.abs().mean()), cobertura90=("cobre90", "mean"),
            largura90=("largura90", "mean"), z_rms=("z", lambda x: float(np.sqrt((x ** 2).mean()))))
        print(tab.round(3).to_string())
        tab.to_csv(os.path.join(OUT, "antes_da_apuracao_resumo.csv"), float_format="%.4f")

    # 3. rejogo por município
    if a.rejogo:
        linhas = []
        for ano in ANOS[1:]:
            base = bases[ano]
            real_br = pa(base)
            real_uf = {u: pa(g) for u, g in base.groupby("uf")}
            for rd in range(a.rejogo):
                rng = np.random.default_rng(100 * ano + rd)
                inicio, duracao, vies = ordem_municipios(base, rng)
                ts = np.linspace(0, 2, 2001)
                pct = np.array([100 * (np.clip((t - inicio) / duracao, 0, 1) * base["E2"]).sum() / base["E2"].sum()
                                for t in ts])
                for p in PONTOS:
                    s = retrato(base, inicio, duracao, vies, ts[np.searchsorted(pct, p)])
                    t0 = time.time()
                    df, sims = prever(s, config(a.variante_rejogo, ano, pris, base))
                    t = avaliar(df, sims, real_br, real_uf).assign(ano=ano, rodada=rd, vies=vies, pct=p,
                                                                   parcial=pa(s))
                    linhas.append(t)
                    b = t.iloc[0]
                    print(f"{ano} r{rd} {p:4.1f}%  parcial {pa(s):5.2f}  prev {b.A_media:5.2f} "
                          f"[{b.A_p05:5.2f}, {b.A_p95:5.2f}] real {real_br:5.2f}  P(A) {b.prob_A:.2f}  "
                          f"UF cob90 {100 * t.cobre90[1:].mean():3.0f}%  ({time.time() - t0:.0f}s)", flush=True)
        rej = pd.concat(linhas, ignore_index=True)
        rej.to_csv(os.path.join(OUT, f"rejogo_{a.variante_rejogo}.csv"), index=False, float_format="%.4f")
        r = rej.groupby(["nivel", "pct"]).agg(erro_abs=("erro", lambda x: x.abs().mean()), cobertura90=("cobre90", "mean"),
                                              largura90=("largura90", "mean"))
        print(r.round(3).to_string())


if __name__ == "__main__":
    main()
