"""Gerador estatístico de apurações para o teste de estresse do modelo do 2º turno.

Em vez de uma ordem de apuração fixa (e às vezes irreal), sorteia muitas eleições e muitas ordens plausíveis:

1. **Resultado de cada cidade**: parte da margem mais provável (a previsão da priori para aquela cidade) e soma,
   na escala logit da fração de A nos votos válidos, um desvio nacional, um por UF e um da própria cidade. O desvio
   da cidade é sorteado dos desvios reais de 2022 (cidades do mesmo porte), então a distribuição tem as caudas que
   a realidade teve. Dentro da cidade, cada seção mantém o desvio real que teve em relação à sua cidade em 2022.
   Comparecimento e brancos/nulos de cada seção ficam como foram em 2022; só a divisão dos votos válidos muda.

2. **Ordem de apuração**: a base é a ordem parecida com a real (Sul/Sudeste antes, Nordeste, Norte e capitais
   depois, zonas apurando em blocos). Sobre ela entra um viés na direção das cidades que a previsão dá para um dos
   lados: a velocidade de apuração de cada cidade é multiplicada por exp(beta * z), com z a inclinação prevista
   da cidade padronizada. beta > 0 apura antes as cidades previstas para A; beta < 0, as previstas para B.
   Dentro de cada cidade, as seções mais para um lado que a própria cidade podem apurar antes (gama), como as
   primeiras seções das cidades em 2026, que vieram ~1 a 2,5 pontos mais para Lula. As intensidades são sorteadas
   com escalas calibradas no que se mediu na apuração real de 2026 (`scripts/estresse.py --calibrar`).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..dados.geo import REGIAO, porte
from . import transferencia as modelo


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _sig(z):
    return 1 / (1 + np.exp(-z))


# escala do atraso regional/capitais calibrada para que, com beta = 0, as cidades previstas para B apurem ~1,3x
# mais rápido que as previstas para A até 20% apurado, como na apuração real de 2026
FORCA_REGIAO = 0.3


@dataclass
class ParamEstresse:
    """Escalas do sorteio. Medido em 2026 (priori ao vivo x resultado): desvio nacional +0,15 logit; desvios por
    região, região x porte e UF de só 0,01 a 0,02; primeiras seções de cada cidade ~1 a 2,5 pontos mais para Lula
    que a cidade inteira até 5% apurado (some depois de ~10%)."""
    sd_nacional: float = 0.12     # logit; 0,12 ~ 3 pontos na fração de A perto de 50%
    sd_regiao: float = 0.02
    sd_uf: float = 0.03
    escala_cidade: float = 1.0    # multiplica os desvios reais das cidades
    sd_beta: float = 0.10         # viés de ordem entre cidades; beta = ±0,1 muda a razão de 1,3 para 0,8 ou 2,3
    sd_gama: float = 0.05         # viés de ordem dentro das cidades; 0,05 ~ 1,5 ponto nas parciais até 5%
    beta: float = None            # fixa beta em vez de sortear
    gama: float = None            # fixa gama em vez de sortear


class GeradorApuracao:
    """Prepara a base de 2022 (1º turno por município + 2º turno por seção) e sorteia eleições e ordens."""

    def __init__(self, base, sec, priori):
        self.base = base.reset_index(drop=True)
        self.sec = sec.reset_index(drop=True)
        mun = self.base.set_index("mun")
        # previsão mais provável de cada cidade: matriz da priori no grupo UF x porte (ou UF, região, Brasil)
        reg = self.base["uf"].map(REGIAO)
        prt = porte(self.base["uf"].values, self.base["E1"].values, self.base["capital"].values)
        E1 = self.base["E1"].clip(lower=1).values
        N1 = np.clip(E1 - self.base[["A1", "B1", "O1", "W1"]].sum(axis=1).values, 0, None)
        X = np.column_stack([self.base["A1"], self.base["B1"], self.base["O1"], self.base["W1"], N1]) / E1[:, None]
        chaves = [[f"uf_porte|{u}|{p}", f"uf|{u}", f"regiao|{r}", "brasil|Brasil"]
                  for u, p, r in zip(self.base["uf"], prt, reg)]
        theta = np.array([next(np.array(priori[k]) for k in ks if k in priori) for ks in chaves])
        Y = np.einsum("uk,ukd->ud", X, modelo.matriz(theta))
        self.prev_a = Y[:, 0] / np.maximum(Y[:, 0] + Y[:, 1], 1e-9)       # fração de A prevista (válidos)
        # resultado real de 2022 por cidade e por seção
        s = self.sec
        val_s = (s["v13"] + s["v22"]).values.astype(float)
        cid = s.groupby("mun")[["v13", "v22"]].sum()
        real_c = (cid["v13"] / (cid["v13"] + cid["v22"]).clip(lower=1)).reindex(self.base["mun"]).values
        self.desvio_cidade = _logit(real_c) - _logit(self.prev_a)
        self.porte = prt
        pos = pd.Series(np.arange(len(self.base)), index=self.base["mun"])
        self.cidade_da_secao = pos.reindex(s["mun"]).values
        sec_a = s["v13"].values / np.maximum(val_s, 1)
        self.desvio_secao = np.where(val_s > 0, _logit(sec_a) - _logit(real_c[self.cidade_da_secao]), 0.0)
        self.validos = val_s
        self.z_secao = self.desvio_secao / max(self.desvio_secao.std(), 1e-9)
        z = _logit(self.prev_a)
        w = self.base["E1"].values.astype(float)
        m = np.average(z, weights=w)
        self.z_cidade = (z - m) / np.sqrt(np.average((z - m) ** 2, weights=w))
        self.uf_idx = pd.factorize(self.base["uf"])[0]
        self.regiao_sec = s["uf"].map(REGIAO).values
        self.capital_sec = self.base["capital"].values[self.cidade_da_secao]
        self.zona = s.groupby(["uf", "zona"]).ngroup().values

    def eleicao(self, rng, par: ParamEstresse):
        """Sorteia um resultado do 2º turno. Devolve DataFrame de seções com v13/v22 sintéticos."""
        nu = self.uf_idx.max() + 1
        desv = np.empty(len(self.base))
        for p in np.unique(self.porte):                     # desvio da cidade sorteado entre cidades do mesmo porte
            idx = np.flatnonzero(self.porte == p)
            ok = idx[np.isfinite(self.desvio_cidade[idx])]
            desv[idx] = rng.choice(self.desvio_cidade[ok], len(idx)) if len(ok) else 0.0
        reg_idx = pd.factorize(self.base["uf"].map(REGIAO))[0]
        lc = (_logit(self.prev_a) + rng.normal(0, par.sd_nacional) + rng.normal(0, par.sd_regiao, reg_idx.max() + 1)[reg_idx]
              + rng.normal(0, par.sd_uf, nu)[self.uf_idx] + par.escala_cidade * desv)
        ls = lc[self.cidade_da_secao] + self.desvio_secao
        pa = _sig(ls)
        v13 = np.round(self.validos * pa)
        s = self.sec.copy()
        s["v13"], s["v22"] = v13.astype(int), (self.validos - v13).astype(int)
        return s

    def ordem(self, rng, beta, gama=0.0, forca_regiao=FORCA_REGIAO):
        """Instante (0-1, só a ordem importa) de apuração de cada seção, com viés beta nas cidades."""
        atraso = pd.Series(self.regiao_sec).map({"Sul": 0.0, "Centro-Oeste": 0.05, "Sudeste": 0.12, "Norte": 0.25,
                                                  "Nordeste": 0.3, "Exterior": 0.7}).fillna(0.3).values
        efeito_zona = rng.normal(0, 0.12, self.zona.max() + 1)[self.zona]
        t = forca_regiao * (atraso + 0.15 * self.capital_sec) + efeito_zona + rng.normal(0, 0.15, len(self.sec))
        # viés: cidades com previsão mais para A (beta > 0) ou B (beta < 0) apuram mais rápido
        t = t - beta * self.z_cidade[self.cidade_da_secao] * 0.3
        # viés dentro da cidade: seções mais para A que a própria cidade (gama > 0) apuram antes
        t = t - gama * self.z_secao * 0.3
        return t

    def rodada(self, rng, par: ParamEstresse):
        beta = par.beta if par.beta is not None else rng.normal(0, par.sd_beta)
        gama = par.gama if par.gama is not None else rng.normal(0, par.sd_gama)
        s = self.eleicao(rng, par)
        return s, self.ordem(rng, beta, gama), beta, gama


def razao_velocidade(z, f, w):
    """Quanto as cidades previstas para B apuram mais rápido que as previstas para A (razão das frações)."""
    pb = (f * w * (z < 0)).sum() / max((w * (z < 0)).sum(), 1)
    pa = (f * w * (z >= 0)).sum() / max((w * (z >= 0)).sum(), 1)
    return pb / max(pa, 1e-9)
