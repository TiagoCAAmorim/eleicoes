"""Regiões e porte das cidades."""
import numpy as np

REGIAO = {
    "ac": "Norte", "am": "Norte", "ap": "Norte", "pa": "Norte", "ro": "Norte", "rr": "Norte", "to": "Norte",
    "al": "Nordeste", "ba": "Nordeste", "ce": "Nordeste", "ma": "Nordeste", "pb": "Nordeste", "pe": "Nordeste",
    "pi": "Nordeste", "rn": "Nordeste", "se": "Nordeste",
    "df": "Centro-Oeste", "go": "Centro-Oeste", "ms": "Centro-Oeste", "mt": "Centro-Oeste",
    "es": "Sudeste", "mg": "Sudeste", "rj": "Sudeste", "sp": "Sudeste",
    "pr": "Sul", "rs": "Sul", "sc": "Sul",
    "zz": "Exterior",
}

PORTES = ["Capitais", "Grandes (>200 mil eleitores)", "Médias (50-200 mil)", "Pequenas (<50 mil)", "Exterior"]


def porte(uf, eleitorado, capital):
    uf = np.asarray(uf)
    e = np.asarray(eleitorado)
    cap = np.asarray(capital).astype(bool)
    out = np.where(e > 200_000, PORTES[1], np.where(e > 50_000, PORTES[2], PORTES[3])).astype(object)
    out[cap] = PORTES[0]
    out[uf == "zz"] = PORTES[4]
    return out
