"""Refaz as saídas da noite de 2026 (histórico, painel, mapas, CSVs) com outra configuração do modelo.

Roda o modelo em cada um dos 46 retratos gravados na apuração e grava em resultados/<saida>/ os mesmos arquivos
que o loop ao vivo gerava, para montar uma segunda versão da página da eleição.

    python scripts/rejogar_paginas_2026.py                         # modelo revisado (priori calibrada, cautela no
                                                                   # início) -> 2026-presidente-revisado
    python scripts/rejogar_paginas_2026.py --variante atual --saida 2026-presidente-teste   # modelo do dia
"""
import argparse
import datetime as dt
import json
import os
import shutil

import pandas as pd

import _raiz  # noqa: F401
from eleicoes.caminhos import resultados
from eleicoes.modelos.previsao import prever
from eleicoes.site import exportar, painel
from apuracao import gerar_saidas
from rejogar_2026 import VARIANTES, carregar, config_variante, retrato

NOMES = ["Lula", "Flávio Bolsonaro"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variante", default="calibrado_cauteloso", choices=list(VARIANTES))
    ap.add_argument("--saida", default="2026-presidente-revisado")
    a = ap.parse_args()
    saida = resultados(a.saida)
    if os.path.exists(saida):
        shutil.rmtree(saida)
    os.makedirs(saida)
    base, ret = carregar()
    cfg = config_variante(a.variante, base, ret)
    pct = ret.groupby("hora")["pct_secoes"].first()
    # mesmos momentos e mesmo "apurado" (linha pontilhada) da página do dia: ao vivo o parcial do Brasil vinha do
    # arquivo nacional do TSE, que sai antes dos municipais, e três retratos repetidos não entraram no histórico
    dia = pd.read_csv(os.path.join(resultados("2026-presidente"), "historico.csv")).set_index("hora")
    horas = [h for h in sorted(pct.index) if h in dia.index]
    linhas, momentos = [], []
    for i, h in enumerate(horas):
        res = prever(retrato(base, ret, h), NOMES, cfg)
        hora = dt.datetime.fromisoformat(h)
        res["hora"], res["hora_txt"] = hora.isoformat(), hora.strftime("%d/%m %H:%M")
        res["pct_secoes"] = float(pct[h])
        res["grupos"]["Brasil"]["Brasil"]["pct_apurado"] = res["pct_secoes"]
        res["parcial_A"] = float(dia.loc[h, "parcial_A"])
        res["grupos"]["Brasil"]["Brasil"]["parcial"] = res["parcial_A"]
        res["proxima_txt"] = ""
        br = res["grupos"]["Brasil"]["Brasil"]
        print(f"{res['hora_txt']} {res['pct_secoes']:6.2f}%  {br['A_media']:.2f} [{br['A_p05']:.2f}, {br['A_p95']:.2f}]"
              f" P={br['prob_A']:.3f}", flush=True)
        linha = {"hora": res["hora"], "pct_secoes": res["pct_secoes"], "parcial_A": res["parcial_A"],
                 **{k: br[k] for k in ["A_media", "A_p05", "A_p95", "A_p025", "A_p975", "prob_A"]}}
        # previsão deste momento, para o seletor da página (web/momentos.json)
        web = painel.linhas_web(res, pd.DataFrame([linha]))
        momentos.append({"pct": round(res["pct_secoes"], 3), "hora_txt": res["hora_txt"], "previsao": web["previsao"],
                         "transferencias": web["transferencias"],
                         "fluxos": exportar.fluxos(res["_csv"]["dados_municipios"], *map(painel.curto, NOMES))})
        if i < len(horas) - 1:
            linhas.append(linha)
            continue
        pd.DataFrame(linhas).to_csv(os.path.join(saida, "historico.csv"), index=False)
        gerar_saidas(res, saida)   # último retrato: painel completo + histórico
    with open(os.path.join(saida, "web", "momentos.json"), "w") as f:
        json.dump(momentos, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
