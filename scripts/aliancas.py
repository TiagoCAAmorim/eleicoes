"""Alianças contrafactuais nas eleições de deputados (etapa 7 do roteiro).

    python scripts/aliancas.py validar                 # o motor reproduz os eleitos reais?
    python scripts/aliancas.py efeito                  # quem ganhou e quem perdeu com cada coligação/federação real
    python scripts/aliancas.py busca                   # alianças de dois partidos que teriam dado mais cadeiras
    python scripts/aliancas.py exportar                # dados da página interativa (_site/aliancas/)
    python scripts/aliancas.py simular --ano 2022 --cargo 6 --grupo PT,PSOL,PSB,PDT [--grupo PL,PP] [--base partido]

Hipótese de todas as simulações: cada eleitor vota igual, só muda quem está na mesma lista. Na prática uma aliança
muda candidaturas e campanhas, então os números dizem o efeito *aritmético* da aliança, não o efeito total.
"""
import argparse
import json
import os

import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import resultados
from eleicoes.modelos import proporcional as pr

ANOS = [2006, 2010, 2014, 2018, 2022, 2026]
CARGOS = {6: "deputado federal", 7: "deputado estadual"}
SAIDA = resultados("aliancas")


def _salvar(df, nome):
    os.makedirs(SAIDA, exist_ok=True)
    df.to_csv(os.path.join(SAIDA, nome), index=False)


def validar(anos):
    linhas = []
    for ano in anos:
        for cargo in CARGOS:
            p, c, v = pr.carregar(ano, cargo)
            e = pr.simular(p, c, v, pr.regra_do_ano(ano))
            real = set(zip(c.loc[c["eleito"], "ue"], c.loc[c["eleito"], "sq"]))
            sim = set(zip(e["ue"], e["sq"]))
            dif = (e.groupby("partido").size().sub(c[c["eleito"]].groupby("partido").size(), fill_value=0))
            linhas.append({"ano": ano, "cargo": CARGOS[cargo], "vagas": len(real),
                           "eleitos_iguais": len(real & sim), "pct": round(100 * len(real & sim) / len(real), 2),
                           "cadeiras_partido_trocadas": int(dif.abs().sum() / 2),
                           "ufs_com_diferenca": ",".join(sorted({u for u, _ in real ^ sim}))})
            print(linhas[-1], flush=True)
    df = pd.DataFrame(linhas)
    _salvar(df, "validacao.csv")
    return df


def efeito(anos):
    """Para cada aliança real (coligação até 2018, federação em 2022) em cada UF: cadeiras dos membros com a
    aliança e com ela desfeita (os outros partidos mantêm as suas)."""
    por_alianca, por_partido = [], []
    for ano in anos:
        regra = pr.regra_do_ano(ano)
        for cargo in CARGOS:
            p, c, v = pr.carregar(ano, cargo)
            base = pr.agremiacoes(p, regra)
            real = pr.simular(p, c, v, regra)
            sozinhos = pr.simular(p, c, v, regra, "partido")
            # todos sozinhos ao mesmo tempo, por partido no país
            t = pd.DataFrame({"real": real.groupby("partido").size(), "sozinhos": sozinhos.groupby("partido").size()})
            t = t.fillna(0).astype(int).assign(ano=ano, cargo=CARGOS[cargo], ganho=lambda d: d["real"] - d["sozinhos"])
            por_partido.append(t.reset_index(names="partido"))
            for (ue, agrem), g in base.groupby(["ue", "agrem"]):
                membros = sorted(g["partido"])
                if len(membros) < 2:
                    continue
                pu, cu = p[p["ue"] == ue], c[c["ue"] == ue]
                desfeita = pr.simular(pu, cu, v, regra, pr.com_grupos(regra, [(m,) for m in membros]))
                ru = real[real["ue"] == ue]
                antes = ru.groupby("partido").size()
                depois = desfeita.groupby("partido").size()
                for m in membros:
                    a, d = int(antes.get(m, 0)), int(depois.get(m, 0))
                    por_alianca.append({"ano": ano, "cargo": CARGOS[cargo], "uf": ue, "alianca": agrem,
                                        "partido": m, "votos": int(g.loc[g["partido"] == m, "votos"].sum()),
                                        "cadeiras_com": a, "cadeiras_sem": d, "ganho": a - d})
                fora = antes.sub(depois, fill_value=0).drop(membros, errors="ignore")
                for m, x in fora[fora != 0].items():
                    por_alianca.append({"ano": ano, "cargo": CARGOS[cargo], "uf": ue, "alianca": agrem,
                                        "partido": m, "votos": None, "cadeiras_com": int(antes.get(m, 0)),
                                        "cadeiras_sem": int(depois.get(m, 0)), "ganho": int(x), "fora": True})
            print(ano, CARGOS[cargo], "alianças:", base.groupby(["ue", "agrem"]).ngroups, flush=True)
    a = pd.DataFrame(por_alianca)
    a["fora"] = a.get("fora", False)
    a["fora"] = a["fora"].fillna(False).astype(bool)
    _salvar(a, "efeito_aliancas.csv")
    pp = pd.concat(por_partido, ignore_index=True)
    _salvar(pp, "efeito_partidos.csv")
    return a, pp


def busca(anos, minimo_votos=0.01):
    """Pares de partidos (com ao menos `minimo_votos` dos votos do país) que, unidos numa lista em todas as UFs,
    teriam mais cadeiras juntos do que tiveram de fato. Até 2018 a união é uma coligação (o partido sai da sua);
    em 2022, uma federação."""
    linhas = []
    for ano in anos:
        regra = pr.regra_do_ano(ano)
        for cargo in CARGOS:
            p, c, v = pr.carregar(ano, cargo)
            real = pr.simular(p, c, v, regra)
            seats = real.groupby("partido").size()
            tot = p.groupby("partido")["votos"].sum()
            grandes = sorted(tot[tot >= minimo_votos * tot.sum()].index)
            for i, a in enumerate(grandes):
                for b in grandes[i + 1:]:
                    s = pr.simular(p, c, v, regra, pr.com_grupos(regra, [(a, b)]))
                    n = s.groupby("partido").size()
                    linhas.append({"ano": ano, "cargo": CARGOS[cargo], "a": a, "b": b,
                                   "real_a": int(seats.get(a, 0)), "real_b": int(seats.get(b, 0)),
                                   "juntos_a": int(n.get(a, 0)), "juntos_b": int(n.get(b, 0))})
            print(ano, CARGOS[cargo], len(grandes), "partidos", flush=True)
    df = pd.DataFrame(linhas)
    df["ganho"] = df["juntos_a"] + df["juntos_b"] - df["real_a"] - df["real_b"]
    _salvar(df, "busca_pares.csv")
    return df


def exportar(anos, pasta):
    """Um JSON por ano e cargo para a página interativa: por UF, vagas, partidos (votos e lista real) e os
    candidatos que podem ser eleitos (no máximo `vagas` por partido, na ordem do desempate do motor)."""
    os.makedirs(pasta, exist_ok=True)
    indice = []
    for ano in anos:
        regra = pr.regra_do_ano(ano)
        for cargo in CARGOS:
            p, c, v = pr.carregar(ano, cargo)
            base = pr.agremiacoes(p, regra)
            siglas = sorted(base["partido"].unique())
            idx = {s: i for i, s in enumerate(siglas)}
            ufs = {}
            for ue, g in base.groupby("ue"):
                n = int(v.get(ue, 0))
                cu = c[(c["ue"] == ue) & (c["votos"] > 0)].sort_values(["votos", "sq"], ascending=[False, True])
                cu = cu.groupby("partido", group_keys=False).head(n)
                ufs[ue] = {"vagas": n,
                           "p": {r.partido: [int(r.votos), r.agrem] for r in g.itertuples()},
                           "c": [[r.nome, idx[r.partido], int(r.votos), int(r.eleito)] for r in cu.itertuples()
                                 if r.partido in idx]}
            dados = {"ano": ano, "cargo": cargo, "cargo_nome": CARGOS[cargo], "partidos": siglas,
                     "regra": {k: getattr(regra, k) for k in ["nome", "coligacoes", "federacoes", "barreira",
                                                              "minimo_qp", "minimo_sobras", "fase3"]},
                     "ufs": ufs}
            nome = f"{ano}_{cargo}.json"
            with open(os.path.join(pasta, nome), "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
            indice.append({"ano": ano, "cargo": cargo, "cargo_nome": CARGOS[cargo], "arquivo": nome})
            print(nome, os.path.getsize(os.path.join(pasta, nome)) // 1024, "KB", flush=True)
    with open(os.path.join(pasta, "indice.json"), "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False)


def simular(ano, cargo, grupos, base, ufs):
    regra = pr.regra_do_ano(ano)
    p, c, v = pr.carregar(ano, cargo)
    real = pr.simular(p, c, v, regra)
    cen = pr.simular(p, c, v, regra, pr.com_grupos(regra, grupos, base, ufs))
    tab = pd.DataFrame({"real": real.groupby("partido").size(), "cenario": cen.groupby("partido").size()})
    tab = tab.fillna(0).astype(int)
    tab["dif"] = tab["cenario"] - tab["real"]
    print(tab[tab["dif"] != 0].sort_values("dif").to_string())
    print()
    print(pr.comparar(real, cen, c).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=["validar", "efeito", "busca", "exportar", "simular"])
    ap.add_argument("--anos", type=int, nargs="*", default=ANOS)
    ap.add_argument("--ano", type=int, default=2022)
    ap.add_argument("--cargo", type=int, default=6)
    ap.add_argument("--grupo", action="append", default=[], help="partidos separados por vírgula")
    ap.add_argument("--base", choices=["real", "partido"], default="real")
    ap.add_argument("--uf", nargs="*")
    ap.add_argument("--pasta", default=os.path.join("_site", "aliancas", "dados"))
    a = ap.parse_args()
    if a.acao == "validar":
        validar(a.anos)
    elif a.acao == "efeito":
        efeito(a.anos)
    elif a.acao == "busca":
        busca(a.anos)
    elif a.acao == "exportar":
        exportar(a.anos, a.pasta)
    else:
        simular(a.ano, a.cargo, [tuple(x.strip() for x in g.split(",")) for g in a.grupo], a.base, a.uf)


if __name__ == "__main__":
    main()
