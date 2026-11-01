"""Mapa estático por município (PNG): votos apurados e previstos, em tamanho original e escalado pelos votos."""
import gzip
import textwrap
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import EllipseCollection, PolyCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from .painel import AVISO_CURTO, FUNDO, TINTA  # noqa: E402

from ..caminhos import COMUM as DATA  # noqa: E402
NEUTRO, VERMELHO, AZUL, SEM_DADO = "#f2f0eb", "#b51f1f", "#1c5fae", "#d9d7d2"
# azul (B) -> neutro (empate) -> vermelho (A), de 25% a 75% dos válidos para A
CMAP = LinearSegmentedColormap.from_list("div", [AZUL, NEUTRO, VERMELHO])
_GEO = None


def _geo():
    """Polígonos projetados (equiretangular com correção de latitude), um item por município."""
    global _GEO
    if _GEO is None:
        with gzip.open(os.path.join(DATA, "municipios_br.geojson.gz"), "rt") as f:
            fc = json.load(f)
        k = np.cos(np.radians(15))
        cdi, aneis, dono = [], [], []
        for i, ft in enumerate(fc["features"]):
            g = ft["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            cdi.append(ft["properties"]["cdi"])
            for p in polys:
                a = np.asarray(p[0], dtype=float)
                aneis.append(np.column_stack([a[:, 0] * k, a[:, 1]]))
                dono.append(i)
        dono = np.asarray(dono)
        area = np.zeros(len(cdi))
        cx, cy = np.zeros(len(cdi)), np.zeros(len(cdi))
        for a, d in zip(aneis, dono):
            x, y = a[:, 0], a[:, 1]
            ar = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
            area[d] += ar
            cx[d] += ar * x.mean()
            cy[d] += ar * y.mean()
        cx, cy = cx / np.maximum(area, 1e-12), cy / np.maximum(area, 1e-12)
        _GEO = {"cdi": cdi, "aneis": aneis, "dono": dono, "area": area, "cx": cx, "cy": cy}
    return _GEO


def tabela(df, final):
    """Votos apurados e previstos (média das simulações) por município."""
    return pd.DataFrame({
        "uf": df["uf"].values, "mun": df["mun"].values,
        "A_apur": df["A2"].values, "B_apur": df["B2"].values,
        "A_prev": final[:, :, 0].mean(0), "B_prev": final[:, :, 1].mean(0),
    })


def _cor(pa):
    return CMAP(np.clip((pa - 25) / 50, 0, 1))


def _painel(ax, geo, val, tot, titulo, k, ext):
    """val: % de A por município (nan = sem dados); tot: votos válidos.
    k = None desenha os polígonos; k > 0 desenha círculos com área = k * votos (mesma escala nos dois mapas)."""
    cores = np.where(np.isfinite(val)[:, None], _cor(np.nan_to_num(val, nan=50)), matplotlib.colors.to_rgba(SEM_DADO))
    if k is None:
        ax.add_collection(PolyCollection([a for a in geo["aneis"]], facecolors=cores[geo["dono"]],
                                         edgecolors=(1, 1, 1, 0.25), linewidths=0.08))
        dens_ext = np.nansum(tot) / geo["area"].sum()
    else:
        # contorno do país, para referência
        ax.add_collection(PolyCollection(geo["aneis"], facecolors="#efeeea", edgecolors="none"))
        r = np.sqrt(k * tot / np.pi)
        ordem = np.argsort(-r)
        ordem = ordem[r[ordem] > 0]
        ax.add_collection(EllipseCollection(2 * r[ordem], 2 * r[ordem], 0, units="xy", offsets=np.column_stack(
            [geo["cx"][ordem], geo["cy"][ordem]]), offset_transform=ax.transData, facecolors=cores[ordem],
            edgecolors=(1, 1, 1, 0.6), linewidths=0.2))
        dens_ext = 1 / k
    # exterior: círculo no Atlântico, com a área que teria na mesma escala
    if ext is not None and ext[1] > 0:
        r = np.sqrt(ext[1] / dens_ext / np.pi)
        x0, y0 = -33.5 * np.cos(np.radians(15)), -27.0
        cor = _cor(ext[0]) if np.isfinite(ext[0]) else SEM_DADO
        ax.add_patch(plt.Circle((x0, y0), max(r, 0.15), facecolor=cor, edgecolor="#888", linewidth=0.5))
        ax.text(x0, y0 - max(r, 0.15) - 0.6, "Exterior", ha="center", va="top", fontsize=8, color="#555")
    ax.set_xlim(-74.5 * np.cos(np.radians(15)), -31 * np.cos(np.radians(15)))
    ax.set_ylim(-34.5, 6)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(titulo, fontsize=12, color=TINTA, loc="left")


def imagem(res, mun, munis, caminho):
    """Gera 4 mapas: apurado/previsto x polígonos/círculos proporcionais aos votos válidos."""
    geo = _geo()
    m = mun.merge(munis[["uf", "mun", "cdi"]], on=["uf", "mun"], how="left")
    ext = m[m["uf"] == "zz"]
    m = m.dropna(subset=["cdi"]).groupby("cdi")[["A_apur", "B_apur", "A_prev", "B_prev"]].sum()
    m = m.reindex(geo["cdi"])
    va, vp = (m["A_apur"] + m["B_apur"]).values, (m["A_prev"] + m["B_prev"]).values
    pa = np.where(va > 0, 100 * m["A_apur"].values / np.where(va > 0, va, 1), np.nan)
    pp = np.where(vp > 0, 100 * m["A_prev"].values / np.where(vp > 0, vp, 1), np.nan)
    ea, eb = ext[["A_apur", "B_apur"]].sum(), ext[["A_prev", "B_prev"]].sum()
    ext_a = (100 * ea["A_apur"] / ea.sum() if ea.sum() else np.nan, ea.sum())
    ext_p = (100 * eb["A_prev"] / eb.sum() if eb.sum() else np.nan, eb.sum())
    a, b = res["nomes"]
    fig, axs = plt.subplots(2, 2, figsize=(14, 15), facecolor=FUNDO)
    for ax in axs.flat:
        ax.set_facecolor(FUNDO)
    # círculos: a soma das áreas dos votos previstos ocupa ~35% da área do país (mesma escala nos dois)
    k = 0.35 * geo["area"].sum() / max(np.nansum(vp) + ext_p[1], 1)
    _painel(axs[0, 0], geo, pa, np.nan_to_num(va), "Apurado", None, ext_a)
    _painel(axs[0, 1], geo, pp, np.nan_to_num(vp), "Previsto no final", None, ext_p)
    _painel(axs[1, 0], geo, pa, np.nan_to_num(va), "Apurado · círculos proporcionais aos votos já apurados", k, ext_a)
    _painel(axs[1, 1], geo, pp, np.nan_to_num(vp), "Previsto · círculos proporcionais aos votos previstos", k, ext_p)
    fig.suptitle(f"Votos válidos por município · {res.get('hora_txt', '')} · {res.get('pct_secoes', 0):.1f}% das seções apuradas",
                 x=0.03, y=0.985, ha="left", fontsize=16, color=TINTA)
    cax = fig.add_axes([0.35, 0.045, 0.3, 0.012])
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap=CMAP, norm=plt.Normalize(25, 75)), cax=cax, orientation="horizontal")
    cb.set_ticks([25, 50, 75])
    cb.set_ticklabels([f"{b} 75%", "empate", f"{a} 75%"])
    cb.outline.set_visible(False)
    nota = ("Cinza: município sem votos apurados. Embaixo, um círculo por município com área proporcional aos votos "
            "válidos, na mesma escala nos dois mapas. Áreas em branco no mapa de cima são rios e lagos. " + AVISO_CURTO)
    fig.text(0.03, 0.008, textwrap.fill(nota, 190), fontsize=8, color="#555")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.955, bottom=0.07, wspace=0.02, hspace=0.06)
    fig.savefig(caminho, dpi=110, facecolor=FUNDO)
    plt.close(fig)
