"""Modelo do 1º turno: previsão da votação de cada candidato durante a apuração (etapa 6, docs/primeiro-turno.md).

No 2º turno, a matriz de transferência leva os votos do 1º turno de cada município para o 2º. No 1º turno não há
turno anterior na mesma eleição, então a matriz parte de uma **eleição de referência** (em geral o 1º turno
presidencial de quatro anos antes) e leva as frações do eleitorado de cada categoria da referência para os destinos
de agora:

    referência (linhas r):  partidos mais votados na referência, demais candidatos, branco/nulo, abstenção
    destinos (colunas d):   candidatos de agora, demais candidatos (O), branco/nulo (W), abstenção (N)

    y_u = x_u @ M,   M[r] = softmax([theta[r], 0])   (logits contra a abstenção)

A geografia da referência (onde o PT foi forte, onde houve mais abstenção) carrega o padrão de cada candidato para os
municípios que ainda não chegaram. A matriz é estimada nas unidades já apuradas, de forma hierárquica (Brasil ->
região -> UF -> UF x porte), como no 2º turno.

Prefeito: a unidade é a seção, e a referência é o 2º turno presidencial de dois anos antes na mesma seção. Sem
referência, x_u = [1] e a matriz vira um vetor de frações por grupo (zona eleitoral).

A priori:
- ponto de partida: as frações de cada destino na pesquisa da véspera (ou numa "pesquisa" informada), com um bônus
  para quem é do mesmo partido de uma linha da referência, para branco/nulo -> branco/nulo e abstenção -> abstenção;
  as colunas são deslocadas até a previsão nacional de antes da apuração bater com a pesquisa;
- cada célula pode se afastar `sd_celula` (escala logit), mas o total nacional de cada candidato só `sd_pesquisa`
  pontos: a geografia é livre, o total nacional fica preso ao erro típico da pesquisa até os votos chegarem.

Incerteza (Monte Carlo): covariância de Laplace no nível Brasil (comum a todo o país) mais o desvio de cada grupo,
ruído de cada unidade, choques comuns (nacional, por UF, da evidência parcial e por UF no começo) no logaritmo da
votação de cada candidato no que falta apurar, como no modelo do 2º turno.
"""
from dataclasses import dataclass, field

import numpy as np

from ..dados.geo import REGIAO, porte


@dataclass
class Config:
    sd_celula: float = 0.5            # desvio da priori de cada célula da matriz (logit)
    sd_pesquisa: float = 4.5          # desvio do total nacional de cada candidato (pontos dos válidos): erro das
                                      # pesquisas Datafolha da véspera do 1º turno presidencial 2010–2026
    # a pesquisa perde peso conforme a apuração avança: desvio = sd_pesquisa * (1 + % apurado / escala_pesquisa).
    # Sem isso, as células ainda sem dados (ex.: o Nordeste no começo) se ajustam para manter o total da pesquisa.
    escala_pesquisa: float = 1.0
    bonus_partido: float = 1.5        # logit extra para o candidato do mesmo partido de uma linha da referência
    bonus_branco: float = 1.5         # branco/nulo -> branco/nulo
    bonus_abstencao: float = 2.0      # abstenção -> abstenção
    tau: float = 0.7                  # quanto cada nível da hierarquia pode se afastar do de cima
    s0_inicial: float = 0.02          # ruído entre unidades (fração do eleitorado)
    s_parcial: float = 0.08           # desvio extra de uma unidade parcialmente apurada
    k_parcial: float = 0.30           # peso do resultado parcial da própria unidade: f/(f+k)
    # choques no log da votação de cada candidato (e dos demais) no que falta apurar; um choque de 0,03 em dois
    # candidatos de ~50% equivale a ~2% de desvio na margem entre eles
    choque_uf: float = 0.03
    choque_nacional: float = 0.015
    choque_parcial: float = 0.04
    choque_uf_inicio: float = 0.05
    choque_uf_inicio_antes: float = None
    choque_grupo_inicio: float = 0.0  # desvio extra por grupo folha (ex.: a capital) x fração do grupo ainda não
                                      # apurada: um grupo grande sem nenhum dado pode votar bem diferente do resto
    rho_grupos: float = 0.25         # correlação entre os desvios dos grupos no sorteio (grupos sem dados erram juntos)
    n_sims: int = 1000
    seed: int = 42
    niveis: list = field(default_factory=lambda: ["regiao", "uf", "uf_porte"])
    votos_por_eleitor: int = 1        # senador com duas vagas: 2


def matriz(theta):
    """theta (..., R, D-1) -> M (..., R, D), linhas somam 1."""
    z = np.concatenate([theta, np.zeros(theta.shape[:-1] + (1,))], -1)
    z = z - z.max(-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(-1, keepdims=True)


def preparar(df, n_ref, n_dest, cfg: Config):
    """df: colunas uf, mun, capital, E (eleitorado), r0..r{n_ref-2} (votos da referência por categoria, sem a
    abstenção), rE (eleitorado da referência), Ea (eleitorado apurado), d0..d{n_dest-2} (votos apurados por destino,
    sem a abstenção), C (comparecimento apurado). Sem referência, n_ref = 1 e não há colunas r."""
    df = df.copy()
    df["regiao"] = df["uf"].map(REGIAO)
    df["porte"] = porte(df["uf"].values, df["E"].values, df["capital"].values)
    df["uf_porte"] = df["uf"] + "|" + df["porte"]
    df["brasil"] = "Brasil"
    if n_ref == 1:
        X = np.ones((len(df), 1))
    else:
        R = df[[f"r{i}" for i in range(n_ref - 1)]].values.astype(float)
        rE = df["rE"].values.astype(float)
        N = np.clip(rE - R.sum(1), 0, None)
        X = np.column_stack([R, N]) / np.maximum(rE, 1)[:, None]
    Ea = df["Ea"].clip(lower=0).values.astype(float)
    k = cfg.votos_por_eleitor
    V = df[[f"d{i}" for i in range(n_dest - 1)]].values.astype(float) / k
    N2 = np.clip(Ea - df["C"].values, 0, None)
    with np.errstate(invalid="ignore", divide="ignore"):
        Y = np.column_stack([V, N2]) / Ea[:, None]
    Y[Ea <= 0] = np.nan
    df["f"] = np.where(df["E"] > 0, Ea / df["E"].clip(lower=1), 1.0)
    return df, X, Y


def priori(X, peso, alvo, mesmo, cfg: Config, iters=60):
    """Matriz de partida theta0 (R, D-1). alvo: frações do eleitorado em cada destino (D) no país; mesmo: (R, D)
    booleano, célula "do mesmo partido" (ou branco -> branco, abstenção -> abstenção) com o bônus."""
    R, D = mesmo.shape
    bonus = np.where(mesmo, 1.0, 0.0)
    if R > 1:
        bonus[:-1] *= cfg.bonus_partido
        bonus[-2, -2] = cfg.bonus_branco * mesmo[-2, -2]
        bonus[-1, -1] = cfg.bonus_abstencao * mesmo[-1, -1]
    xbar = (X * peso[:, None]).sum(0) / peso.sum()
    off = np.log(np.clip(alvo, 1e-6, None))
    for _ in range(iters):
        z = off[None, :] + bonus
        th = z[:, :-1] - z[:, -1:]
        prev = xbar @ matriz(th)
        off = off + np.log(np.clip(alvo, 1e-6, None) / prev)
    return th, xbar


def _jac_pred(X, M):
    """d pred_ud / d theta_rj -> (U, D, R, D-1)."""
    R, D = M.shape
    eye = np.eye(D)[:, :D - 1]
    A = M[:, :, None] * (eye[None] - M[:, None, :D - 1])     # (R, D, J)
    return X[:, None, :, None] * A.transpose(1, 0, 2)[None]  # (U, D, R, J)


def _ajustar(X, Y, w, th0, sd, xbar=None, alvo=None, sd_nac=None, iters=30):
    """Mínimos quadrados com priori; média e covariância de Laplace de theta (achatado). Com `xbar`, `alvo` e `sd_nac`,
    soma a priori do total nacional: xbar @ M(theta) ~ alvo (frações do eleitorado), com desvio `sd_nac` por destino."""
    R, J = th0.shape
    sd = np.broadcast_to(np.asarray(sd, float), (R, J)).ravel()
    nac = xbar is not None and sd_nac is not None

    def res(t):
        t = t.reshape(R, J)
        out = [(t - th0).ravel() / sd]
        if nac:
            out.append((xbar @ matriz(t) - alvo)[:J] / sd_nac)
        if len(X):
            out.insert(0, ((Y - X @ matriz(t)) * w).ravel())
        return np.concatenate(out)

    def jac(t):
        t = t.reshape(R, J)
        partes = []
        if len(X):
            partes.append((-w[:, :, None, None] * _jac_pred(X, matriz(t))).reshape(-1, R * J))
        partes.append(np.diag(1 / sd))
        if nac:
            Jn = _jac_pred(xbar[None], matriz(t))[0, :J].reshape(J, R * J)
            partes.append(Jn / sd_nac[:, None])
        return np.vstack(partes)

    if len(X) == 0 and not nac:
        return th0.ravel().copy(), np.diag(sd ** 2)
    # Gauss-Newton com amortecimento (Levenberg-Marquardt simples): o jacobiano é analítico e o problema é pequeno
    t = th0.ravel().copy()
    r = res(t)
    custo = r @ r
    lam = 1e-3
    for _ in range(iters):
        Jm = jac(t)
        A = Jm.T @ Jm
        g = Jm.T @ r
        while True:
            try:
                passo = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -g)
            except np.linalg.LinAlgError:
                passo = -g * 1e-3
            t2 = t + passo
            r2 = res(t2)
            c2 = r2 @ r2
            if c2 <= custo or lam > 1e6:
                break
            lam *= 10
        melhora = custo - c2
        if c2 <= custo:
            t, r, custo = t2, r2, c2
            lam = max(lam / 10, 1e-7)
        if melhora < 1e-6 * max(custo, 1e-12) or np.abs(passo).max() < 1e-5:
            break
    Jm = jac(t)
    try:
        cov = np.linalg.inv(Jm.T @ Jm)
    except np.linalg.LinAlgError:
        cov = np.diag(sd ** 2)
    return t, cov


@dataclass
class Ajuste:
    grupos: dict        # (nivel, nome) -> (mu, cov) de theta achatado; Brasil: cov total; demais: cov do desvio
    s0: float
    folha: np.ndarray
    folhas: list
    forma: tuple


def ajustar(df, X, Y, th0, xbar, alvo, cfg: Config):
    """alvo: frações do eleitorado em cada destino no país (a pesquisa, ver `priori`)."""
    R, J = th0.shape
    val = 1 - alvo[-2] - alvo[-1]
    pct = 100 * df["Ea"].clip(lower=0).sum() / max(df["E"].sum(), 1)
    sd_nac = np.full(J, cfg.sd_pesquisa / 100 * val * (1 + pct / cfg.escala_pesquisa))
    sd_nac[-1] = 0.01                                   # branco/nulo
    ok = np.isfinite(Y).all(1) & (df["Ea"].values > 0)
    Ea = df["Ea"].values.astype(float)
    Ew = Ea * np.clip(df["f"].values, 0.05, 1)
    extra = (cfg.s_parcial ** 2 * np.clip(1 - df["f"].values, 0, 1))[:, None]

    def pesos(sel, s0, t):
        p = np.clip(X[sel] @ matriz(t.reshape(R, J)), 1e-4, 1)
        return 1.0 / np.sqrt(s0 ** 2 + extra[sel] + p * (1 - p) / np.maximum(Ew[sel], 1)[:, None])

    s0 = cfg.s0_inicial
    mu, cov = _ajustar(X[ok], Y[ok], pesos(ok, s0, th0), th0, cfg.sd_celula, xbar, alvo, sd_nac)
    if ok.sum() > 30:
        p = np.clip(X[ok] @ matriz(mu.reshape(R, J)), 1e-4, 1)
        r = Y[ok] - p
        exc = (r ** 2 - p * (1 - p) / np.maximum(Ew[ok], 1)[:, None] - extra[ok]).mean()
        s0 = float(np.sqrt(max(exc, 0.004 ** 2)))
        mu, cov = _ajustar(X[ok], Y[ok], pesos(ok, s0, mu), th0, cfg.sd_celula, xbar, alvo, sd_nac)
    grupos = {("brasil", "Brasil"): (mu, cov)}
    # pai de cada nível: o nível de cima da hierarquia regional que estiver em cfg.niveis (ou o Brasil)
    pais = {}
    for n in cfg.niveis:
        p = {"regiao": "brasil", "uf": "regiao", "uf_porte": "uf"}.get(n, "brasil")
        while p != "brasil" and p not in cfg.niveis:
            p = {"uf": "regiao", "regiao": "brasil"}[p]
        pais[n] = p
    for nivel in cfg.niveis:
        for nome, idx in df.groupby(nivel).indices.items():
            pn = df[pais[nivel]].iloc[idx[0]]
            pmu, pcov = grupos[(pais[nivel], pn)]
            pvar = np.zeros(R * J) if pais[nivel] == "brasil" else np.diag(pcov)
            psd = np.sqrt(cfg.tau ** 2 + pvar)
            sel = idx[ok[idx]]
            if len(sel) == 0:
                grupos[(nivel, nome)] = (pmu, np.diag(psd ** 2))
                continue
            m, c = _ajustar(X[sel], Y[sel], pesos(sel, s0, pmu), pmu.reshape(R, J), psd.reshape(R, J))
            # covariância do desvio em relação ao Brasil: o que sobra da incerteza do grupo além da nacional
            grupos[(nivel, nome)] = (m, c)
    ultimo = cfg.niveis[-1] if cfg.niveis else "brasil"
    folhas = sorted(df[ultimo].unique())
    pos = {n: i for i, n in enumerate(folhas)}
    return Ajuste(grupos, s0, df[ultimo].map(pos).values, [(ultimo, n) for n in folhas], (R, J))


def _indice_parcial(df):
    Ea = df["Ea"].values.astype(float)
    if Ea.sum() <= 0:
        return 0.0
    return float(1 - (Ea * np.clip(df["f"].values, 0, 1)).sum() / Ea.sum())


def simular(df, X, Y, aj: Ajuste, cfg: Config):
    """Votos finais simulados de cada unidade: (S, U, D), na escala de eleitores (senador: votos / 2)."""
    rng = np.random.default_rng(cfg.seed)
    R, J = aj.forma
    S, U, D = cfg.n_sims, len(df), J + 1
    mu_b, cov_b = aj.grupos[("brasil", "Brasil")]
    Lb = np.linalg.cholesky(cov_b + 1e-9 * np.eye(R * J))
    zb = rng.standard_normal((S, R * J)) @ Lb.T                     # incerteza nacional, comum a todos
    pred = np.empty((S, U, D), dtype=np.float32)
    zg = rng.standard_normal((S, R * J))                            # parte comum dos desvios dos grupos
    for g, k in enumerate(aj.folhas):
        idx = np.flatnonzero(aj.folha == g)
        mu, cov = aj.grupos[k]
        if k[0] == "brasil":
            th = mu + zb
        else:
            L = np.linalg.cholesky(cov + 1e-9 * np.eye(R * J))
            # o grupo herda o sorteio nacional e soma o próprio desvio (média do grupo - nacional)
            # antes de abrir, a incerteza do total vem da pesquisa: os desvios dos grupos (a geografia) não se somam
            rho = cfg.rho_grupos if df["Ea"].sum() > 0 else 0.0
            z = np.sqrt(rho) * zg + np.sqrt(1 - rho) * rng.standard_normal((S, R * J))
            th = mu + zb + z @ L.T
        M = matriz(th.reshape(S, R, J))
        sim = np.einsum("ur,srd->sud", X[idx], M)
        # o sorteio em escala logit puxa as frações para perto da uniforme (desigualdade de Jensen): reescala para
        # que a média dos sorteios de cada unidade seja a previsão com os parâmetros médios, sem mudar a dispersão
        det = X[idx] @ matriz(mu.reshape(R, J))
        sim = sim * (det / np.maximum(sim.mean(0), 1e-9))[None]
        pred[:, idx] = sim / np.maximum(sim.sum(-1, keepdims=True), 1e-9)
    temY = np.isfinite(Y).all(1)
    f = df["f"].values
    rho = np.where(temY, f / (f + cfg.k_parcial), 0.0)
    pred += (rng.standard_normal((S, U, D), dtype=np.float32) * aj.s0 * (1 - rho)[None, :, None])
    pred = np.clip(pred, 0, None)
    pred /= np.maximum(pred.sum(-1, keepdims=True), 1e-9)
    Yf = np.where(temY[:, None], Y, 0.0)
    pred = rho[None, :, None] * Yf[None] + (1 - rho)[None, :, None] * pred
    # choques no log da votação dos candidatos (destinos 0..D-3) no que falta apurar
    nc = D - 2
    ufs, uf_idx = np.unique(df["uf"].values, return_inverse=True)
    sd_uf = np.full(len(ufs), cfg.choque_uf)
    ini = cfg.choque_uf_inicio
    if cfg.choque_uf_inicio_antes is not None and df["Ea"].sum() <= 0:
        ini = cfg.choque_uf_inicio_antes
    if ini:
        Ea_uf = np.bincount(uf_idx, df["Ea"].values.astype(float), len(ufs))
        E_uf = np.bincount(uf_idx, df["E"].values.astype(float), len(ufs))
        sd_uf = sd_uf + ini * np.clip(1 - Ea_uf / np.maximum(E_uf, 1), 0, 1)
    z = (rng.standard_normal((S, len(ufs), nc)) * sd_uf[None, :, None])[:, uf_idx]      # (S, U, nc)
    if cfg.choque_nacional:
        z = z + rng.standard_normal((S, 1, nc)) * cfg.choque_nacional
    if cfg.choque_grupo_inicio:
        G = len(aj.folhas)
        Ea_g = np.bincount(aj.folha, df["Ea"].values.astype(float), G)
        E_g = np.bincount(aj.folha, df["E"].values.astype(float), G)
        sd_g = cfg.choque_grupo_inicio * np.clip(1 - Ea_g / np.maximum(E_g, 1), 0, 1)
        z = z + (rng.standard_normal((S, G, nc)) * sd_g[None, :, None])[:, aj.folha]
    if cfg.choque_parcial:
        fator = np.where((f > 0) & (f < 1) & temY, 1.0, _indice_parcial(df))
        z = z + rng.standard_normal((S, 1, nc)) * cfg.choque_parcial * fator[None, :, None]
    cand = pred[..., :nc]
    tot = cand.sum(-1, keepdims=True)
    cand = cand * np.exp(z).astype(np.float32)
    pred[..., :nc] = cand * tot / np.maximum(cand.sum(-1, keepdims=True), 1e-9)
    k = cfg.votos_por_eleitor
    obs = np.column_stack([df[[f"d{i}" for i in range(D - 1)]].values / k,
                           np.clip(df["Ea"].values - df["C"].values, 0, None)]).astype(float)
    Erest = np.clip(df["E"].values - df["Ea"].values, 0, None).astype(float)
    return obs[None] + Erest[None, :, None] * pred


def resumo(final, nomes, vagas=1, maioria=True):
    """final: (S, U, D) ou (S, D) com destinos [candidatos..., O, W, N]. Devolve, por candidato nomeado: % dos
    válidos (média e quantis), P(1º), P(entre os 2 primeiros), P(> 50% dos válidos) e, no geral, P(haver 2º turno).
    vagas: número de eleitos (senador em ano de duas vagas: 2); maioria=False para eleição de maioria simples."""
    tot = final.sum(1) if final.ndim == 3 else final
    nc = tot.shape[1] - 3                      # candidatos nomeados (sem os demais, branco/nulo e abstenção)
    val = tot[:, :nc + 1].sum(1, keepdims=True)
    pct = 100 * tot[:, :nc] / np.maximum(val, 1)
    ordem = np.argsort(-pct, axis=1)
    rank = np.empty_like(ordem)
    rank[np.arange(len(pct))[:, None], ordem] = np.arange(nc)[None]
    q = np.percentile(pct, [5, 25, 50, 75, 95], axis=0)
    cands = []
    for i, n in enumerate(nomes):
        cands.append({"nome": n, "media": float(pct[:, i].mean()), "p05": float(q[0, i]), "p25": float(q[1, i]),
                      "p50": float(q[2, i]), "p75": float(q[3, i]), "p95": float(q[4, i]),
                      "prob_1o": float((rank[:, i] == 0).mean()), "prob_top2": float((rank[:, i] <= 1).mean()),
                      "prob_eleito_1t": float(((pct[:, i] > 50) if maioria and vagas == 1 else (rank[:, i] < vagas)).mean()),
                      "amostras": pct[:, i]})
    out = {"candidatos": cands}
    if maioria and vagas == 1:
        out["prob_2o_turno"] = float(1 - (pct.max(1) > 50).mean())
    return out
