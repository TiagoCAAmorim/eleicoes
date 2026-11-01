"""Pastas do repositório. Todo código lê e grava a partir daqui, nunca de caminhos relativos ao módulo."""
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(RAIZ, "dados")
COMUM = os.path.join(DADOS, "comum")
PRIORI = os.path.join(DADOS, "priori")
RESULTADOS = os.path.join(RAIZ, "resultados")
TEMPLATES = os.path.join(RAIZ, "eleicoes", "site", "templates")
SITE = os.path.join(RAIZ, "site")


def dados(ano, cargo, *partes):
    """dados/<ano>/<cargo>/..."""
    return os.path.join(DADOS, str(ano), cargo, *partes)


def resultados(nome, *partes):
    """resultados/<nome>/... (ex.: resultados('2026-presidente'))"""
    return os.path.join(RESULTADOS, nome, *partes)
