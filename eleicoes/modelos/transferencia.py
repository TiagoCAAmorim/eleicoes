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

from ..dados.geo import REGIAO, porte

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
    if theta.shape[-1] > NPAR:
        # versão 2 (Config.matriz_v2): branco/nulo do 1º turno pode votar em A ou B, e a falta dos eleitores de B
        # é separada da dos eleitores de A (permite que um lado falte mais que o outro)
        wa, wb = 0.25 * _sig(theta[..., 8]), 0.25 * _sig(theta[..., 9])
        prb = 0.5 * _sig(theta[..., 10])
    else:
        wa = wb = z
        prb = pr
    M = np.stack([
        np.stack([1 - pab - pr, pab, z, pr], -1),
        np.stack([pba, 1 - pba - prb, z, prb], -1),
        o,
        np.stack([wa, wb, 1 - pr - wa - wb, pr], -1),
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
    s_parcial: float = 0.08           # desvio extra de um município parcialmente apurado: as seções que chegam
                                      # primeiro vêm agrupadas (mesma zona/bairro), não são amostra aleatória
    choque_uf: float = 0.02           # choque comum por UF na margem A-B das unidades restantes
    choque_nacional: float = 0.01     # choque comum a todo o país na margem A-B das unidades restantes (erro
                                      # sistemático: a parte que falta apurar pode diferir toda no mesmo sentido)
    # choques que dependem de quão representativo é o que já foi apurado (substitutos da curva de transição):
    # - choque_parcial: viés nacional comum na margem do que falta apurar. Nos municípios já começados vale cheio
    #   (as seções que chegam primeiro podem não representar o resto, no mesmo sentido no país todo); nos não
    #   começados vale x P = parte "parcial" da evidência (1 - f médio dos apurados, ponderado pelos votos).
    # - choque_uf_inicio: desvio extra por UF x fração da UF ainda não apurada (UFs com pouco apurado erram mais).
    choque_parcial: float = 0.015
    choque_uf_inicio: float = 0.04
    choque_uf_inicio_antes: float = None   # valor antes de abrir as urnas (None = o mesmo de choque_uf_inicio)
    matriz_v2: bool = False           # parâmetros extras: branco/nulo -> A/B e falta separada para B
    escala_cov: float = 1.0           # inflação da covariância de Laplace (dependência espacial)
    rho_nacional: float = 0.5         # correlação entre grupos no sorteio dos parâmetros
    k_parcial: float = 0.30           # peso do resultado parcial do próprio município: f/(f+k)
    # transição da priori para os parâmetros estimados conforme o % do eleitorado apurado no país: 1ª metade de
    # uma sigmoide (sobe devagar e acelera até o centro, onde passa a usar só os estimados). None = sem transição.
    # Usada ao vivo em 2026 (centro 25); desligada na revisão da etapa 3, que a trocou pelos choques acima
    # (ver docs/revisao-t2.md): a curva prendia a previsão à priori e custou ~1 ponto em 2026.
    transicao_centro: float = None
    transicao_largura: float = 8.0
    n_sims: int = 1000
    seed: int = 42
    niveis: list = field(default_factory=lambda: ["regiao", "uf", "uf_porte"])
    # priori informativa (ex.: transferências estimadas em 2022): {"nivel|nome": theta}. O nível Brasil vira o
    # ponto de partida e cada grupo herda o desvio que tinha em relação ao grupo de cima naquela eleição.
    priori: dict = None
    sd_priori_informativa: float = 0.7
    theta_outros: tuple = None         # logits (oA, oB, oW) vs oN para substituir a linha "Outros" da priori
    sd_outros: float = None            # desvio da priori na linha Outros (None = sd_priori_informativa)


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
    peso: float = 1.0     # peso dos parâmetros estimados na transição a partir da priori


def peso_transicao(pct, cfg: Config):
    """Peso (0 a 1) dos parâmetros estimados com a apuração, em função do % do eleitorado apurado no país."""
    if cfg.transicao_centro is None or pct >= cfg.transicao_centro:
        return 1.0
    sig = lambda x: 1 / (1 + np.exp(-(x - cfg.transicao_centro) / cfg.transicao_largura))  # noqa: E731
    return float(max(sig(pct) - sig(0), 0) / (0.5 - sig(0)))


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
    if cfg.sd_outros is not None:
        sd0[3:6] = cfg.sd_outros
    if cfg.matriz_v2:
        # branco/nulo -> A e -> B começam em ~3% cada; a falta de B começa igual à de A
        theta0 = np.concatenate([theta0, [_logit(0.03 / 0.25), _logit(0.03 / 0.25), theta0[2]]])
        sd0 = np.concatenate([sd0, [1.5, 1.5, 1.0]])
    npar = len(theta0)

    def desvio(nivel, nome, pai_nivel, pai_nome):
        """Desvio do grupo em relação ao de cima na eleição de referência (0 sem priori; linha Outros = 0)."""
        a, b = pri.get(f"{nivel}|{nome}"), pri.get(f"{pai_nivel}|{pai_nome}")
        if a is None or b is None:
            return np.zeros(npar)
        d = np.zeros(npar)
        d[:NPAR] = a - b
        d[3:6] = 0.0
        return d

    # variância extra das parciais: proporcional ao que falta apurar no município (zero quando completo)
    extra = (cfg.s_parcial ** 2 * np.clip(1 - df["f"].values, 0, 1))[:, None]
    sx = lambda s, sel: np.sqrt(s ** 2 + extra[sel])  # noqa: E731
    mu, cov = _ajustar(X[ok], Y[ok], Ew[ok], sx(s0, ok), theta0, sd0)
    if ok.sum() > 30:
        res = Y[ok] - X[ok] @ matriz(mu)
        p = np.clip(X[ok] @ matriz(mu), 1e-4, 1)
        excesso = (res ** 2 - p * (1 - p) / np.maximum(Ew[ok], 1)[:, None] - extra[ok]).mean()
        s0 = float(np.sqrt(max(excesso, 0.005 ** 2)))
        mu, cov = _ajustar(X[ok], Y[ok], Ew[ok], sx(s0, ok), theta0, sd0)
    pais = {"regiao": "brasil", "uf": "regiao", "uf_porte": "uf"}
    indices = {nivel: df.groupby(nivel).indices for nivel in cfg.niveis}

    def hierarquia(ok, mu, cov):
        grupos = {("brasil", "Brasil"): (mu, cov * cfg.escala_cov)}
        for nivel in cfg.niveis:
            for nome, idx in indices[nivel].items():
                pai_nome = df[pais[nivel]].iloc[idx[0]]
                pmu, pcov = grupos[(pais[nivel], pai_nome)]
                pmu = pmu + desvio(nivel, nome, pais[nivel], pai_nome)
                psd = np.sqrt(cfg.tau ** 2 + np.diag(pcov))
                sel = idx[ok[idx]]
                m, c = _ajustar(X[sel], Y[sel], Ew[sel], sx(s0, sel), pmu, psd)
                grupos[(nivel, nome)] = (m, c * (cfg.escala_cov if len(sel) else 1.0))
        return grupos

    grupos = hierarquia(ok, mu, cov)
    w = peso_transicao(100 * Ea[ok].sum() / max(df["E2"].sum(), 1), cfg)
    if w < 1:
        # mistura (por momentos) entre a previsão só com a priori e a estimada com a apuração parcial
        sem = np.zeros_like(ok)
        priori = hierarquia(sem, *_ajustar(X[sem], Y[sem], Ew[sem], sx(s0, sem), theta0, sd0))
        for k, (m1, c1) in grupos.items():
            m0, c0 = priori[k]
            d = (m1 - m0)[:, None]
            grupos[k] = (m0 + w * (m1 - m0), w * c1 + (1 - w) * c0 + w * (1 - w) * (d @ d.T))
    ultimo = cfg.niveis[-1] if cfg.niveis else "brasil"
    folhas = sorted(df[ultimo].unique())
    pos = {n: i for i, n in enumerate(folhas)}
    folha = df[ultimo].map(pos).values
    return Ajuste(grupos, s0, folha, [(ultimo, n) for n in folhas], w)


def _amostrar_theta(aj: Ajuste, chaves, cfg, rng):
    """Amostra theta para cada grupo em `chaves` -> (n_sims, n_grupos, 8)."""
    npar = len(aj.grupos[chaves[0]][0])
    zn = rng.standard_normal((cfg.n_sims, npar))
    out = np.empty((cfg.n_sims, len(chaves), npar))
    for j, k in enumerate(chaves):
        mu, cov = aj.grupos[k]
        L = np.linalg.cholesky(cov + 1e-9 * np.eye(npar))
        z = np.sqrt(cfg.rho_nacional) * zn + np.sqrt(1 - cfg.rho_nacional) * rng.standard_normal((cfg.n_sims, npar))
        out[:, j] = mu + z @ L.T
    return out


def indice_parcial(df):
    """Quão "parcial" é a evidência apurada (0 = só municípios completos ou nada apurado, perto de 1 = só começos)."""
    Ea = df["Ea"].values.astype(float)
    if Ea.sum() <= 0:
        return 0.0  # antes de abrir não há evidência parcial (a incerteza vem da priori e do choque nacional)
    return float(1 - (Ea * np.clip(df["f"].values, 0, 1)).sum() / Ea.sum())


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
    f = df["f"].values
    sd_uf = np.full(len(ufs), cfg.choque_uf)
    uf_inicio = cfg.choque_uf_inicio
    if cfg.choque_uf_inicio_antes is not None and df["Ea"].sum() <= 0:
        uf_inicio = cfg.choque_uf_inicio_antes
    if uf_inicio:
        Ea_uf = np.bincount(uf_idx, df["Ea"].values.astype(float), len(ufs))
        E_uf = np.bincount(uf_idx, df["E2"].values.astype(float), len(ufs))
        sd_uf = sd_uf + uf_inicio * np.clip(1 - Ea_uf / np.maximum(E_uf, 1), 0, 1)
    choque = rng.standard_normal((S, len(ufs)))[:, uf_idx] * sd_uf[uf_idx]
    if cfg.choque_nacional:
        choque = choque + rng.standard_normal((S, 1)) * cfg.choque_nacional
    temY = np.isfinite(Y).all(1)
    # viés da evidência parcial, comum ao país: no que falta de um município já começado, as seções restantes podem
    # diferir das apuradas (tamanho cheio, sem amortecer por rho, porque é o resultado parcial que pode estar
    # enviesado); nos municípios não começados, o viés entra pelos parâmetros estimados e escala com P
    vies = 0.0
    if cfg.choque_parcial:
        fator = np.where((f > 0) & (f < 1) & temY, 1.0, indice_parcial(df))
        vies = rng.standard_normal((S, 1)) * cfg.choque_parcial * fator[None, :]
    rho = np.where(temY, f / (f + cfg.k_parcial), 0.0)
    escala = (1 - rho)
    pred[..., 0] += (ruido[..., 0] + choque / 2) * escala
    pred[..., 1] += (ruido[..., 1] - choque / 2) * escala
    pred = np.clip(pred, 0, None)
    pred /= pred.sum(-1, keepdims=True)
    Yf = np.where(temY[:, None], Y, 0.0)
    pred = rho[None, :, None] * Yf[None] + (1 - rho)[None, :, None] * pred
    if cfg.choque_parcial:
        pred[..., 0] += vies / 2
        pred[..., 1] -= vies / 2
        pred = np.clip(pred, 0, None)
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
    from ..caminhos import PRIORI
    caminho = os.path.join(PRIORI, "presidente_2022.json")
    pri = json.load(open(caminho)) if os.path.exists(caminho) else None
    return Config(priori=pri, theta_outros=OUTROS_PESQUISA_2026 if pri else None)
