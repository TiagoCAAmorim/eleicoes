"""Importância dos indicadores do IBGE para o voto por município (página indicadores.html).

Gradient Boosting (LightGBM) com validação cruzada espacial: cada rodada deixa um estado inteiro de fora.
Importância por SHAP (TreeSHAP do próprio LightGBM), por permutação de grupos de indicadores e por retirada
de grupos (treina de novo sem o grupo). Também calcula a correlação de Spearman de cada indicador.

    pip install lightgbm scikit-learn   # só para este script; o loop não precisa
    python scripts/importancia.py

Saídas em resultados/importancia/: importancia.json (resultados) e indicadores_mun.json (valores por município,
para o gráfico de dispersão). web.gerar_site copia os dois e a página para o site.
"""
import argparse
import json
import os
import re
import sys
import warnings
from datetime import datetime, timezone

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=Warning, module="lightgbm")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAVES = {"cdi", "cod_tse", "uf", "mun", "nome", "municipio", "cod_ibge"}

# rótulo e grupo de cada indicador da base dados/ibge (colunas novas caem nas regras por padrão do nome)
INDICADORES = {
    "pop_2022": ("População (2022)", "Demografia"), "area_km2": ("Área (km²)", "Demografia"),
    "densidade": ("Densidade (hab./km²)", "Demografia"), "pct_rural": ("% rural", "Demografia"),
    "indice_envelhecimento": ("Índice de envelhecimento", "Demografia"), "idade_mediana": ("Idade mediana", "Demografia"),
    "razao_sexo": ("Razão de sexo (homens por 100 mulheres)", "Demografia"),
    "filhos_por_mulher_12mais": ("Filhos por mulher (12+)", "Demografia"),
    "pct_branca": ("% branca", "Cor ou raça"), "pct_preta": ("% preta", "Cor ou raça"), "pct_parda": ("% parda", "Cor ou raça"),
    "pct_amarela": ("% amarela", "Cor ou raça"), "pct_indigena": ("% indígena", "Cor ou raça"),
    "pct_preta_parda": ("% preta + parda", "Cor ou raça"),
    "escolarizacao_6_14": ("Escolarização 6–14 anos (%)", "Educação"), "analfabetismo_15mais": ("Analfabetismo 15+ (%)", "Educação"),
    "anos_estudo_11mais": ("Anos médios de estudo (11+)", "Educação"),
    "rendimento_medio": ("Rendimento médio do trabalho (R$)", "Renda"), "rendimento_mediano": ("Rendimento mediano do trabalho (R$)", "Renda"),
    "pib_per_capita_2023": ("PIB per capita (2023)", "Renda"),
    "nivel_ocupacao_10mais": ("Nível de ocupação 10+ (%)", "Economia"), "pib_mil_reais_2023": ("PIB total (2023)", "Economia"),
    "pct_vab_agro_2021": ("% agropecuária no PIB (2021)", "Economia"), "pct_vab_industria_2021": ("% indústria no PIB (2021)", "Economia"),
    "pct_vab_servicos_2021": ("% serviços no PIB (2021)", "Economia"),
    "pct_vab_adm_publica_2021": ("% administração pública no PIB (2021)", "Economia"),
    "pct_catolica": ("% católica", "Religião"), "pct_evangelica": ("% evangélica", "Religião"), "pct_espirita": ("% espírita", "Religião"),
    "pct_umbanda_candomble": ("% umbanda e candomblé", "Religião"), "pct_sem_religiao": ("% sem religião", "Religião"),
}
GRUPOS = [
    ("Educação", r"escolar|analfab|estudo|instru|alfabet"),
    ("Renda", r"per_capita|rend|renda|salari|pobre|gini"),
    ("Cor ou raça", r"branc|pret|pard|amarel|indigen|negr"),
    ("Religião", r"catol|evangel|espirit|umband|candom|relig"),
    ("Economia", r"agro|industr|servic|adm|ocupa|empreg|setor|vab|pib"),
    ("Demografia", r"pop|area|densid|rural|urban|idade|envelhec|filhos|fecund|sexo"),
]

PARAMS = dict(objective="regression", learning_rate=0.03, num_leaves=31, min_child_samples=30,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, n_jobs=4)
MAX_ARVORES = 3000


def grupo_de(col):
    if col in INDICADORES:
        return INDICADORES[col][1]
    c = col.lower()
    for nome, rx in GRUPOS:
        if re.search(rx, c):
            return nome
    return "Outros"


def rotulos(pasta, cols):
    """Descrição de cada coluna lida do dicionario.md (tabela markdown ou lista), se existir."""
    out = {}
    arq = os.path.join(pasta, "dicionario.md")
    if os.path.exists(arq):
        for lin in open(arq, encoding="utf-8"):
            cel = [x.strip().strip("`* ") for x in lin.strip().strip("|").split("|")] if lin.lstrip().startswith("|") else None
            if cel is None:
                m = re.match(r"\s*[-*]\s*`?([\w]+)`?\s*[:—–-]\s*(.+)", lin)
                cel = [m.group(1), m.group(2)] if m else None
            if cel and len(cel) >= 2 and cel[0] in cols and cel[1] and not set(cel[1]) <= set("-: "):
                out.setdefault(cel[0], cel[1])
    return {c: INDICADORES[c][0] if c in INDICADORES else out.get(c, c.replace("_", " ")) for c in cols}


def ler_votos(arq):
    d = pd.read_csv(arq, sep=";", decimal=",", dtype={"cod_tse": str}, encoding="utf-8-sig")
    cand = [c[:-3] for c in d.columns if c.endswith("_t1") and c not in ("eleitores_t1", "outros_t1", "branco_nulo_t1")][:2]
    a, b = cand
    d = d[d["uf"] != "zz"].copy()
    d["alvo_t1"] = 100 * d[f"{a}_t1"] / (d[f"{a}_t1"] + d[f"{b}_t1"])
    fr = d["eleitores_apurados_t2"] / d["eleitores_t2"].where(d["eleitores_t2"] > 0)
    v2 = d[f"{a}_apurado_t2"] + d[f"{b}_apurado_t2"]
    ok = (fr >= 0.999) & (v2 > 0)
    d["alvo_t2"] = np.where(ok, 100 * d[f"{a}_apurado_t2"] / v2.where(v2 > 0), np.nan)
    d["alvo_mud"] = d["alvo_t2"] - d["alvo_t1"]
    return d, a, b


def treinar(X, y, n_arv=None, Xv=None, yv=None):
    m = lgb.LGBMRegressor(n_estimators=n_arv or MAX_ARVORES, **PARAMS)
    if n_arv is None:
        m.fit(X, y, eval_set=[(Xv, yv)], callbacks=[lgb.early_stopping(100, verbose=False)])
    else:
        m.fit(X, y)
    return m


def r2(y, p, w=None):
    w = np.ones_like(y) if w is None else w
    return float(1 - np.sum(w * (y - p) ** 2) / np.sum(w * (y - np.average(y, weights=w)) ** 2))


def mae(y, p, w=None):
    return float(np.average(np.abs(y - p), weights=w))


def analisar(df, cols, grupos, alvo, rng):
    d = df[df[alvo].notna()].reset_index(drop=True)
    X, y, w, uf = d[cols], d[alvo].values, d["eleitores_t1"].values.astype(float), d["uf"].values
    ufs = sorted(set(uf))
    oof, oof_reg, oof_ridge, oof_base = (np.full(len(d), np.nan) for _ in range(4))
    shap = np.zeros((len(d), len(cols)))
    gnomes = sorted(set(grupos.values()))
    perm = {g: [] for g in gnomes}
    perm_ind = {c: [] for c in cols}
    retirada = {g: [] for g in gnomes}
    ganho = []
    Xr = pd.concat([X, pd.get_dummies(d["regiao"], prefix="reg", dtype=float)], axis=1)
    ridge = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 12)))
    for u in ufs:
        te, tr = uf == u, uf != u
        # parada antecipada com estados de validação sorteados entre os de treino
        outros = [x for x in ufs if x != u]
        val = np.isin(uf, rng.choice(outros, size=max(3, len(outros) // 5), replace=False)) & tr
        fit = tr & ~val
        m0 = treinar(X[fit], y[fit], Xv=X[val], yv=y[val])
        n_arv = max(50, m0.best_iteration_ or MAX_ARVORES)
        m = treinar(X[tr], y[tr], n_arv)
        oof[te] = m.predict(X[te])
        contrib = m.predict(X[te], pred_contrib=True)
        shap[te] = contrib[:, :-1]
        ganho.append(m.booster_.feature_importance("gain") / max(1e-9, m.booster_.feature_importance("gain").sum()))
        base = np.mean((y[te] - oof[te]) ** 2)
        for g in gnomes:  # permutação do grupo inteiro (mesma permutação para todas as colunas do grupo)
            gc = [c for c in cols if grupos[c] == g]
            dl = []
            for _ in range(5):
                Xp = X[te].copy()  # valores sorteados do país inteiro: só no estado de teste a variação seria pequena
                Xp[gc] = X[gc].values[rng.choice(len(X), len(Xp))]
                dl.append(np.mean((y[te] - m.predict(Xp)) ** 2) - base)
            perm[g].append((float(np.mean(dl)), int(te.sum())))
            mg = treinar(X.loc[tr, [c for c in cols if c not in gc]], y[tr], n_arv)
            retirada[g].append((float(np.mean((y[te] - mg.predict(X.loc[te, [c for c in cols if c not in gc]])) ** 2) - base), int(te.sum())))
        for c in cols:
            Xp = X[te].copy()
            Xp[c] = X[c].values[rng.choice(len(X), len(Xp))]
            perm_ind[c].append((float(np.mean((y[te] - m.predict(Xp)) ** 2) - base), int(te.sum())))
        oof_reg[te] = treinar(Xr[tr], y[tr], n_arv).predict(Xr[te])
        oof_ridge[te] = ridge.fit(X[tr], y[tr]).predict(X[te])
        medias = pd.Series(y[tr]).groupby(d["regiao"].values[tr]).mean()
        oof_base[te] = d.loc[te, "regiao"].map(medias).fillna(y[tr].mean()).values
        print(f"  {alvo} {u}: {te.sum()} municípios, {n_arv} árvores, MAE {mae(y[te], oof[te]):.2f}", file=sys.stderr)

    # divisão aleatória, só para comparar
    oof_rand = np.full(len(d), np.nan)
    for tr, te in KFold(5, shuffle=True, random_state=1).split(X):
        oof_rand[te] = treinar(X.iloc[tr], y[tr], 400).predict(X.iloc[te])

    def resumo(lst):  # média ponderada pelo nº de municípios de teste + faixa entre os estados
        v = np.array([x[0] for x in lst])
        n = np.array([x[1] for x in lst])
        return {"media": float(np.average(v, weights=n)), "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90))}

    mse_oof = float(np.mean((y - oof) ** 2))
    abs_shap = np.abs(shap).mean(0)
    shap_grupo = {g: float(np.abs(shap[:, [i for i, c in enumerate(cols) if grupos[c] == g]].sum(1)).mean()) for g in gnomes}
    # posição de cada indicador (por |SHAP|) em cada estado de teste: estabilidade do ranking
    rank_uf = []
    for u in ufs:
        s = np.abs(shap[uf == u]).mean(0)
        rank_uf.append(pd.Series(s).rank(ascending=False).values)
    rank_uf = np.array(rank_uf)
    ordem = np.argsort(-abs_shap)
    dep = {}
    for i in ordem[:8]:
        c = cols[i]
        k = np.where(X[c].notna())[0]
        k = rng.choice(k, size=min(1500, len(k)), replace=False)
        dep[c] = {"x": [round(float(v), 3) for v in X[c].values[k]], "s": [round(float(v), 2) for v in shap[k, i]],
                  "uf": [str(v) for v in uf[k]]}
    res = y - oof
    por_uf = (pd.DataFrame({"uf": uf, "e": np.abs(res), "r": res, "w": w}).groupby("uf")
              .apply(lambda g: pd.Series({"mae": g.e.mean(), "vies": g.r.mean(), "n": len(g)}), include_groups=False))

    def lista(sinal):
        o = [i for i in np.argsort(-sinal * res) if w[i] >= 5000][:15]  # pequenos oscilam demais
        return [{"id": d["uf"][i] + d["cod_tse"][i], "nome": d["municipio"][i], "uf": d["uf"][i], "real": round(float(y[i]), 2),
                 "prev": round(float(oof[i]), 2), "eleitores": int(w[i])} for i in o]

    return {
        "n": int(len(d)), "n_ufs": len(ufs), "media": float(y.mean()),
        "metricas": {
            "modelo": {"r2": r2(y, oof), "mae": mae(y, oof), "r2_pond": r2(y, oof, w), "mae_pond": mae(y, oof, w)},
            "modelo_regiao": {"r2": r2(y, oof_reg), "mae": mae(y, oof_reg)},
            "ridge": {"r2": r2(y, oof_ridge), "mae": mae(y, oof_ridge)},
            "media_regiao": {"r2": r2(y, oof_base), "mae": mae(y, oof_base)},
            "aleatoria": {"r2": r2(y, oof_rand), "mae": mae(y, oof_rand)},
        },
        "mse": mse_oof,
        "grupos": [{"grupo": g, "n_ind": sum(1 for c in cols if grupos[c] == g), "shap": shap_grupo[g],
                    "perm": resumo(perm[g]), "retirada": resumo(retirada[g])} for g in gnomes],
        "indicadores": [{"col": c, "grupo": grupos[c], "shap": float(abs_shap[i]), "perm": resumo(perm_ind[c]),
                         "ganho": float(np.mean([gg[i] for gg in ganho])),
                         "rank_med": float(np.median(rank_uf[:, i])), "rank_p10": float(np.percentile(rank_uf[:, i], 10)),
                         "rank_p90": float(np.percentile(rank_uf[:, i], 90)),
                         "rho": float(spearmanr(X[c], y, nan_policy="omit").statistic)} for i, c in enumerate(cols)],
        "dependencia": dep,
        "por_uf": [{"uf": u, "mae": round(float(r.mae), 3), "vies": round(float(r.vies), 3), "n": int(r.n)} for u, r in por_uf.iterrows()],
        "residuos": {"a": lista(1), "b": lista(-1)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ibge", default=os.path.join(RAIZ, "dados/ibge/ibge_municipios.csv"))
    ap.add_argument("--votos", default=os.path.join(RAIZ, "resultados/2026-presidente/dados_municipios.csv"))
    ap.add_argument("--saida", default=os.path.join(RAIZ, "resultados/importancia"))
    ap.add_argument("--min-t2", type=int, default=1500, help="mínimo de municípios 100%% apurados para analisar o 2º turno")
    args = ap.parse_args()
    rng = np.random.default_rng(42)

    ib = pd.read_csv(args.ibge, dtype={"cdi": str, "cod_tse": str})
    ib["cod_tse"] = ib["cod_tse"].str.zfill(5)
    votos, a, b = ler_votos(args.votos)
    cols = [c for c in ib.columns if c.lower() not in CHAVES and pd.api.types.is_numeric_dtype(ib[c])]
    # participações setoriais fora de 0–100 (dado original do IBGE) viram ausentes
    for c in cols:
        if c.startswith("part_") or c.startswith("pct_"):
            ib.loc[(ib[c] < 0) | (ib[c] > 100), c] = np.nan
    ib = ib[ib[cols].notna().any(axis=1)]  # exterior e município criado depois do Censo
    df = votos.merge(ib[["cod_tse"] + cols], on="cod_tse", how="inner")  # cod_tse é único no país
    grupos = {c: grupo_de(c) for c in cols}
    pasta = os.path.dirname(os.path.abspath(args.ibge))
    rot = rotulos(pasta, cols)
    print(f"{len(df)} municípios, {len(cols)} indicadores", file=sys.stderr)

    out = {"gerado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "candidatos": [a, b],
           "rotulos": rot, "grupo_de": grupos, "alvos": {}, "params": {k: v for k, v in PARAMS.items() if k not in ("verbose", "n_jobs")}}
    fontes = os.path.join(pasta, "fontes.json")
    if os.path.exists(fontes):
        out["fontes"] = json.load(open(fontes, encoding="utf-8"))
    rho = df[cols].corr(method="spearman")
    out["corr"] = {"cols": cols, "m": [[round(float(v), 2) if pd.notna(v) else None for v in r] for r in rho.values]}
    nomes = {"alvo_t1": "1º turno", "alvo_t2": "2º turno", "alvo_mud": "Mudança do 1º para o 2º turno"}
    for alvo, nome in nomes.items():
        n = int(df[alvo].notna().sum())
        if alvo != "alvo_t1" and n < args.min_t2:
            print(f"{nome}: só {n} municípios completos, pulando", file=sys.stderr)
            continue
        out["alvos"][alvo] = {"nome": nome, **analisar(df, cols, grupos, alvo, rng)}
        out["alvos"][alvo]["parcial"] = alvo != "alvo_t1" and n < int(df["alvo_t1"].notna().sum()) * 0.98

    os.makedirs(args.saida, exist_ok=True)
    with open(os.path.join(args.saida, "importancia.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    # valores por município para o gráfico de dispersão (colunar, arredondado)
    mun = {"id": (df["uf"] + df["cod_tse"]).tolist(), "nome": df["municipio"].tolist(), "uf": df["uf"].tolist(),
           "regiao": df["regiao"].tolist(), "eleitores": df["eleitores_t1"].astype(int).tolist(),
           **{k: [None if pd.isna(v) else round(float(v), 2) for v in df[k]] for k in nomes},
           "ind": {c: [None if pd.isna(v) else float(f"{v:.4g}") for v in df[c]] for c in cols}}
    with open(os.path.join(args.saida, "indicadores_mun.json"), "w", encoding="utf-8") as f:
        json.dump(mun, f, ensure_ascii=False, separators=(",", ":"))
    for alvo, r in out["alvos"].items():
        mm = r["metricas"]
        print(f"{r['nome']}: R² por UF {mm['modelo']['r2']:.2f} (aleatória {mm['aleatoria']['r2']:.2f}, ridge {mm['ridge']['r2']:.2f}, "
              f"região {mm['media_regiao']['r2']:.2f}), MAE {mm['modelo']['mae']:.2f} p.p.", file=sys.stderr)
        for g in sorted(r["grupos"], key=lambda g: -g["shap"]):
            print(f"   {g['grupo']:12s} SHAP {g['shap']:.2f}  perm {g['perm']['media']:.1f}  retirada {g['retirada']['media']:.1f}", file=sys.stderr)


if __name__ == "__main__":
    main()
