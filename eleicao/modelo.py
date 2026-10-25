"""Modelo probabilístico de transferência de votos do 1º para o 2º turno.

Cada unidade (município) tem, no 1º turno, a fração do eleitorado que votou em
A, em B (os dois candidatos do 2º turno), em Outros candidatos, Branco/nulo (W)
ou se absteve (N). No 2º turno os destinos são A, B, W e N. A matriz de
transferência M (origem -> destino) é:

    A: [1-pAB-pR, pAB,      0,     pR ]    pAB: troca de A para B
    B: [pBA,      1-pBA-pR, 0,     pR ]    pR : eleitores do 1º turno que faltam
    O: [oA,       oB,       oW,    oN ]    soma 1 (oN = Outros que se abstêm)
    W: [0,        0,        1-pR,  pR ]
    N: [nA,       nB,       0, 1-nA-nB]    nA, nB: abstenção que passa a votar

y_2 = x_1 @ M, com x_1 = [A, B, O, W, N] / eleitorado.

Os 8 parâmetros são estimados por mínimos quadrados ponderados nas unidades já
apuradas, de forma hierárquica (Brasil -> região -> UF -> UF x porte): cada
nível é puxado para o valor do nível de cima (priori normal), então grupos com
poucas unidades apuradas herdam a estimativa da vizinhança mais próxima com
dados. A incerteza vem da aproximação de Laplace (covariância dos parâmetros),
de choques por UF e do ruído de cada município, simulados por Monte Carlo.
"""
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import least_squares

from .geo import REGIAO, porte

NPAR = 8
PAR_NOMES = ["A→B", "B→A", "Abstenção (votantes T1)", "Outros→A", "Outros→B", "Outros→Branco/nulo",
             "Outros→Abstenção", "Abstenção T1→A", "Abstenção T1→B"]


def _sig(z):
    return 1.0 / (1.0 + np.exp(-z))


def _logit(p):
    return np.log(p / (1 - p))


def matriz(theta):
    """theta (..., 8) -> M (..., 5, 4)."""
    theta = np.asarray(theta, dtype=float)
    pab = 0.3 * _sig(theta[..., 0])
    pba = 0.3 * _sig(theta[..., 1])
    pr = 0.5 * _sig(theta[..., 2])
    lo = np.stack([theta[..., 3], theta[..., 4], theta[..., 5], np.zeros_like(theta[..., 0])], -1)
    lo = lo - lo.max(-1, keepdims=True)
    o = np.exp(lo)
    o = o / o.sum(-1, keepdims=True)
    na = 0.3 * _sig(theta[..., 6])
    nb = 0.3 * _sig(theta[..., 7])
    z = np.zeros_like(pab)
    M = np.stack([
        np.stack([1 - pab - pr, pab, z, pr], -1),
        np.stack([pba, 1 - pba - pr, z, pr], -1),
        o,
        np.stack([z, z, 1 - pr, pr], -1),
        np.stack([na, nb, z, 1 - na - nb], -1),
    ], -2)
    return M


def parametros_legiveis(theta):
    """Converte theta (..., 8) nas probabilidades de transferência (..., 9)."""
    M = matriz(theta)
    return np.stack([M[..., 0, 1], M[..., 1, 0], M[..., 0, 3], M[..., 2, 0], M[..., 2, 1], M[..., 2, 2],
                     M[..., 2, 3], M[..., 4, 0], M[..., 4, 1]], -1)


# priori no nível Brasil: pouca troca entre A e B, ~5% dos votantes faltam,
# Outros divididos entre A e B, pequena volta de quem se absteve.
THETA0 = np.array([_logit(0.02 / 0.3), _logit(0.02 / 0.3), _logit(0.05 / 0.5),
                   np.log(0.35 / 0.15), np.log(0.35 / 0.15), 0.0, _logit(0.03 / 0.3), _logit(0.03 / 0.3)])


@dataclass
class Config:
    sd_priori_brasil: float = 1.5     # desvio da priori (escala logit) no nível Brasil
    tau: float = 0.5                  # quanto cada nível pode se afastar do nível de cima
    s0_inicial: float = 0.03          # ruído entre municípios (fração do eleitorado)
    choque_uf: float = 0.02           # choque comum por UF na margem A-B das unidades restantes
    escala_cov: float = 1.0           # inflação da covariância de Laplace (dependência espacial)
    rho_nacional: float = 0.5         # correlação entre grupos no sorteio dos parâmetros
    k_parcial: float = 0.30           # peso do resultado parcial do próprio município: f/(f+k)
    n_sims: int = 1000
    seed: int = 42
    niveis: list = field(default_factory=lambda: ["regiao", "uf", "uf_porte"])
    # priori informativa (ex.: transferências estimadas em 2022): {"nivel|nome": theta}. O nível Brasil vira o
    # ponto de partida e cada grupo herda o desvio que tinha em relação ao grupo de cima naquela eleição.
    priori: dict = None
    sd_priori_informativa: float = 0.7
    theta_outros: tuple = None         # logits (oA, oB, oW) vs oN para substituir a linha "Outros" da priori


def preparar(df):
    """Adiciona colunas derivadas. df precisa de:
    uf, mun, capital, E1, A1, B1, O1, W1 (T1, município inteiro),
    E2, Ea, A2, B2, W2, C2 (T2: eleitorado total, eleitorado apurado, votos e comparecimento apurados)."""
    df = df.copy()
    df["regiao"] = df["uf"].map(REGIAO)
    df["porte"] = porte(df["uf"].values, df["E1"].values, df["capital"].values)
    df["uf_porte"] = df["uf"] + "|" + df["porte"]
    df["brasil"] = "Brasil"
    E1 = df["E1"].clip(lower=1)
    N1 = (df["E1"] - df[["A1", "B1", "O1", "W1"]].sum(1)).clip(lower=0)
    X = np.column_stack([df["A1"], df["B1"], df["O1"], df["W1"], N1]) / E1.values[:, None]
    Ea = df["Ea"].clip(lower=0).values
    N2 = np.clip(Ea - df["C2"].values, 0, None)
    with np.errstate(invalid="ignore", divide="ignore"):
        Y = np.column_stack([df["A2"], df["B2"], df["W2"], N2]) / Ea[:, None]
    Y[Ea <= 0] = np.nan
    df["f"] = np.where(df["E2"] > 0, Ea / df["E2"].clip(lower=1), 1.0)
    return df, X, Y


def _residuos(theta, X, Y, w, prior_mu, prior_sd):
    pred = X @ matriz(theta)
    r = ((Y - pred) * w).ravel()
    return np.concatenate([r, (theta - prior_mu) / prior_sd])


def _ajustar(X, Y, Ea, s0, prior_mu, prior_sd):
    """Mínimos quadrados com priori; devolve média e covariância (Laplace)."""
    if len(X) == 0:
        return prior_mu.copy(), np.diag(prior_sd ** 2)
    p = np.clip(X @ matriz(prior_mu), 1e-4, 1)
    w = 1.0 / np.sqrt(s0 ** 2 + p * (1 - p) / np.maximum(Ea, 1)[:, None])
    sol = least_squares(_residuos, prior_mu, args=(X, Y, w, prior_mu, prior_sd), method="trf")
    J = sol.jac
    try:
        cov = np.linalg.inv(J.T @ J)
    except np.linalg.LinAlgError:
        cov = np.diag(prior_sd ** 2)
    return sol.x, cov


@dataclass
class Ajuste:
    grupos: dict          # (nivel, nome) -> (mu, cov)
    s0: float
    folha: np.ndarray     # índice do grupo folha de cada unidade
    folhas: list          # lista de (nivel, nome) das folhas


def ajustar(df, X, Y, cfg: Config):
    ok = np.isfinite(Y).all(1) & (df["Ea"].values > 0)
    Ea = df["Ea"].values.astype(float)
    # ponderação pela fração apurada: municípios parcialmente apurados contam menos
    Ew = Ea * np.clip(df["f"].values, 0.05, 1)
    s0 = cfg.s0_inicial
    theta0, sd0 = THETA0.copy(), np.full(NPAR, cfg.sd_priori_brasil)
    # parâmetros da priori presos em zero na eleição de referência (problema de identificação ecológica)
    # são limitados a ~1% para não travar a estimativa
    pri = {k: np.maximum(np.array(v, float), [-3.4, -3.4, -3.4, -9, -9, -9, -3.4, -3.4])
           for k, v in (cfg.priori or {}).items()}
    if "brasil|Brasil" in pri:
        theta0, sd0 = pri["brasil|Brasil"].copy(), np.full(NPAR, cfg.sd_priori_informativa)
    if cfg.theta_outros is not None:
        theta0[3:6] = cfg.theta_outros
        sd0[3:6] = cfg.sd_priori_informativa

    def desvio(nivel, nome, pai_nivel, pai_nome):
        """Desvio do grupo em relação ao de cima na eleição de referência (0 sem priori; linha Outros = 0)."""
        a, b = pri.get(f"{nivel}|{nome}"), pri.get(f"{pai_nivel}|{pai_nome}")
        if a is None or b is None:
            return np.zeros(NPAR)
        d = a - b
        d[3:6] = 0.0
        return d

    grupos = {}
    mu, cov = _ajustar(X[ok], Y[ok], Ew[ok], s0, theta0, sd0)
    if ok.sum() > 30:
        res = Y[ok] - X[ok] @ matriz(mu)
        p = np.clip(X[ok] @ matriz(mu), 1e-4, 1)
        excesso = (res ** 2 - p * (1 - p) / np.maximum(Ew[ok], 1)[:, None]).mean()
        s0 = float(np.sqrt(max(excesso, 0.005 ** 2)))
        mu, cov = _ajustar(X[ok], Y[ok], Ew[ok], s0, theta0, sd0)
    grupos[("brasil", "Brasil")] = (mu, cov * cfg.escala_cov)
    pais = {"regiao": "brasil", "uf": "regiao", "uf_porte": "uf"}
    for nivel in cfg.niveis:
        for nome, idx in df.groupby(nivel).indices.items():
            pai_nome = df[pais[nivel]].iloc[idx[0]]
            pmu, pcov = grupos[(pais[nivel], pai_nome)]
            pmu = pmu + desvio(nivel, nome, pais[nivel], pai_nome)
            psd = np.sqrt(cfg.tau ** 2 + np.diag(pcov))
            sel = idx[ok[idx]]
            m, c = _ajustar(X[sel], Y[sel], Ew[sel], s0, pmu, psd)
            grupos[(nivel, nome)] = (m, c * (cfg.escala_cov if len(sel) else 1.0))
    ultimo = cfg.niveis[-1] if cfg.niveis else "brasil"
    folhas = sorted(df[ultimo].unique())
    pos = {n: i for i, n in enumerate(folhas)}
    folha = df[ultimo].map(pos).values
    return Ajuste(grupos, s0, folha, [(ultimo, n) for n in folhas])


def _amostrar_theta(aj: Ajuste, chaves, cfg, rng):
    """Amostra theta para cada grupo em `chaves` -> (n_sims, n_grupos, 8)."""
    zn = rng.standard_normal((cfg.n_sims, NPAR))
    out = np.empty((cfg.n_sims, len(chaves), NPAR))
    for j, k in enumerate(chaves):
        mu, cov = aj.grupos[k]
        L = np.linalg.cholesky(cov + 1e-9 * np.eye(NPAR))
        z = np.sqrt(cfg.rho_nacional) * zn + np.sqrt(1 - cfg.rho_nacional) * rng.standard_normal((cfg.n_sims, NPAR))
        out[:, j] = mu + z @ L.T
    return out


def simular(df, X, Y, aj: Ajuste, cfg: Config):
    """Simula o resultado final de cada unidade. Retorna dict com arrays (n_sims, n_unid) de votos A, B, W, N."""
    rng = np.random.default_rng(cfg.seed)
    th = _amostrar_theta(aj, aj.folhas, cfg, rng)               # (S, G, 8)
    M = matriz(th)                                               # (S, G, 5, 4)
    S, U = cfg.n_sims, len(df)
    pred = np.empty((S, U, 4), dtype=np.float32)
    for g in range(len(aj.folhas)):
        idx = np.flatnonzero(aj.folha == g)
        pred[:, idx] = np.einsum("uk,skd->sud", X[idx], M[:, g])
    # ruído de cada município (proporcional a s0) e choque comum por UF na margem A-B
    ruido = rng.standard_normal((S, U, 2), dtype=np.float32) * aj.s0
    ufs, uf_idx = np.unique(df["uf"].values, return_inverse=True)
    choque = rng.standard_normal((S, len(ufs)))[:, uf_idx] * cfg.choque_uf
    f = df["f"].values
    temY = np.isfinite(Y).all(1)
    rho = np.where(temY, f / (f + cfg.k_parcial), 0.0)
    escala = (1 - rho)
    pred[..., 0] += (ruido[..., 0] + choque / 2) * escala
    pred[..., 1] += (ruido[..., 1] - choque / 2) * escala
    pred = np.clip(pred, 0, None)
    pred /= pred.sum(-1, keepdims=True)
    Yf = np.where(temY[:, None], Y, 0.0)
    pred = rho[None, :, None] * Yf[None] + (1 - rho)[None, :, None] * pred
    Erest = np.clip(df["E2"].values - df["Ea"].values, 0, None).astype(float)
    obs = np.column_stack([df["A2"], df["B2"], df["W2"],
                           np.clip(df["Ea"].values - df["C2"].values, 0, None)]).astype(float)
    final = obs[None] + Erest[None, :, None] * pred              # (S, U, 4)
    return final


def agregar(df, final, por):
    """Agrega as simulações por coluna `por` -> dict nome -> (S, 4)."""
    out = {}
    for nome, idx in df.groupby(por).indices.items():
        out[nome] = final[:, idx].sum(1)
    return out


def resumo_grupo(sims4, obs4=None):
    """sims4: (S, 4) votos A, B, W, N. Devolve estatísticas em % dos votos válidos."""
    validos = sims4[:, 0] + sims4[:, 1]
    pa = 100 * sims4[:, 0] / np.maximum(validos, 1)
    comp = 100 * (sims4[:, :3].sum(1)) / np.maximum(sims4.sum(1), 1)
    d = {
        "A_media": float(pa.mean()), "A_p05": float(np.percentile(pa, 5)), "A_p95": float(np.percentile(pa, 95)),
        "A_p025": float(np.percentile(pa, 2.5)), "A_p975": float(np.percentile(pa, 97.5)),
        "prob_A": float((pa > 50).mean()), "comparecimento": float(comp.mean()),
        "brancos_nulos": float((100 * sims4[:, 2] / np.maximum(sims4[:, :3].sum(1), 1)).mean()),
    }
    return d


# Pesquisas de 2º turno de 2026 (Quaest 17-20/out, ponderada pelos votos de cada candidato no 1º turno:
# Cury, Renan Santos, Caiado, Zema e demais): Outros -> Lula ~32%, Flávio ~46%, branco/nulo/abstenção ~21%.
OUTROS_PESQUISA_2026 = (float(np.log(0.32 / 0.10)), float(np.log(0.46 / 0.10)), float(np.log(0.12 / 0.10)))


def config_2026():
    """Configuração usada ao vivo: priori de 2022 + linha Outros das pesquisas de 2026."""
    import json
    import os
    caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/priori_2022.json")
    pri = json.load(open(caminho)) if os.path.exists(caminho) else None
    return Config(priori=pri, theta_outros=OUTROS_PESQUISA_2026 if pri else None)
