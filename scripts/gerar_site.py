"""Gera o site do projeto (GitHub Pages) em _site/.

    python scripts/gerar_site.py               # gera em _site/
    python scripts/gerar_site.py --saida pasta

Páginas fixas em site/ (início, modelos, análises) recebem cabeçalho e rodapé comuns; cada eleição listada em
config/eleicoes.json ganha sua pasta (ex.: _site/2026/presidente/) gerada a partir de resultados/<id>.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import shutil

import _raiz  # noqa: F401
from eleicoes.caminhos import RAIZ, RESULTADOS, SITE, resultados
from eleicoes.site import web

FUSO = dt.timezone(dt.timedelta(hours=-3))
PAGINAS = ["index.html", "modelos.html", "analises.html"]
NOMES_ORDEM = {"2022": "Parecida com a real (Sul e Sudeste antes)", "aleatoria": "Aleatória por seção",
               "zonas": "Parecida com a real, com zonas pró-Bolsonaro antes em cada município",
               "adversa": "Adversa (seções pró-Bolsonaro primeiro)"}


def _ler(nome):
    with open(os.path.join(SITE, nome), encoding="utf-8") as f:
        return f.read()


def _num(x, casas=1):
    return f"{x:.{casas}f}".replace(".", ",")


def cartao_eleicao(e):
    e_ = {k: html.escape(str(v)) for k, v in e.items() if isinstance(v, (str, int))}
    itens = "\n".join(
        f'      <li><a href="{html.escape(e["caminho"] + p["href"])}"><strong>{html.escape(p["nome"])}</strong>'
        f'<span>{html.escape(p["desc"])}</span></a></li>' for p in e["paginas"])
    return f"""  <section class="cartao">
    <div class="rotulo">{e_["ano"]} · {e_["cargo"]} · {e_["turno"]}</div>
    <h3>{e_["titulo"]}</h3>
    <p class="meta">{e_["situacao"]} · {e_["data"]}</p>
    <p>{e_["resumo"]}</p>
    <ul>
{itens}
    </ul>
  </section>"""


def tabela_backtest(pasta_img):
    """Tabela com o resumo do backtest de 2022 (resultados/backtest) e o gráfico, se existirem."""
    arq = os.path.join(RESULTADOS, "backtest", "resumo.json")
    if not os.path.exists(arq):
        return "<p class=\"meta\">Resultados do teste ainda não gerados (python scripts/backtest.py).</p>"
    with open(arq) as f:
        resumo = json.load(f)
    linhas = "\n".join(
        f'    <tr><td>{html.escape(NOMES_ORDEM.get(r["ordem"], r["ordem"]))}</td>'
        f'<td class="num">{_num(r["erro_medio_abs"], 2)} pt</td><td class="num">{_num(100 * r["cobertura90"], 0)}%</td></tr>'
        for r in resumo)
    out = f"""<div class="tabela-rolagem">
<table>
  <thead><tr><th>Ordem de apuração</th><th class="num">Erro médio</th><th class="num">Cobertura do intervalo de 90%</th></tr></thead>
  <tbody>
{linhas}
  </tbody>
</table>
</div>
<p class="meta">Erro médio absoluto da previsão de Lula (pontos percentuais dos votos válidos) e fração dos momentos da
apuração (de 0,5% a 99%) em que o intervalo de 90% continha o resultado final.</p>"""
    png = os.path.join(RESULTADOS, "backtest", "backtest_2022.png")
    if os.path.exists(png):
        os.makedirs(pasta_img, exist_ok=True)
        shutil.copy(png, os.path.join(pasta_img, "backtest_2022.png"))
        out += """
<figure>
  <img src="img/backtest_2022.png" alt="Previsão e intervalo de 90% ao longo da apuração simulada de 2022, comparados com o resultado final" loading="lazy">
  <figcaption>Previsão ao longo da apuração simulada de 2022 em cada ordem de apuração.</figcaption>
</figure>"""
    return out


def pagina(nome, extras, gerado_em):
    corpo = _ler(nome)
    m = re.match(r"<!-- página: (\w+) \| titulo: (.*?) \| descricao: (.*?) -->\n", corpo)
    chave, titulo, descricao = m.groups()
    corpo = corpo[m.end():]
    for k, v in extras.items():
        corpo = corpo.replace("{{" + k + "}}", v)
    subs = {"titulo": titulo, "descricao": descricao, "raiz": "./",
            "gerado_em": gerado_em}
    for p in ["inicio", "modelos", "analises"]:
        subs[f"atual_{p}"] = ' aria-current="page"' if p == chave else ""
    doc = _ler("_cabecalho.html") + corpo + _ler("_rodape.html")
    for k, v in subs.items():
        doc = doc.replace("{{" + k + "}}", v)
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=os.path.join(RAIZ, "_site"))
    a = ap.parse_args()
    saida = a.saida
    if os.path.exists(saida):
        shutil.rmtree(saida)
    os.makedirs(saida)
    with open(os.path.join(RAIZ, "config", "eleicoes.json"), encoding="utf-8") as f:
        eleicoes = json.load(f)
    gerado_em = dt.datetime.now(FUSO).strftime("%d/%m/%Y")
    extras = {"eleicoes": "\n".join(cartao_eleicao(e) for e in eleicoes),
              "backtest": tabela_backtest(os.path.join(saida, "img"))}
    for nome in PAGINAS:
        with open(os.path.join(saida, nome), "w", encoding="utf-8") as f:
            f.write(pagina(nome, extras, gerado_em))
    shutil.copy(os.path.join(SITE, "estilo.css"), os.path.join(saida, "estilo.css"))
    for e in eleicoes:
        # uma eleição pode ter versões (ex.: modelo do dia e modelo revisado), cada uma numa subpasta
        versoes = e.get("versoes") or [{"sub": "", "resultados": e["resultados"]}]
        for v in versoes:
            caminho = e["caminho"] + v["sub"]
            destino = os.path.join(saida, caminho)
            inicio = "../" * caminho.strip("/").count("/") + "../"
            raiz_eleicao = "../" * v["sub"].strip("/").count("/") + ("../" if v["sub"] else "./")
            web.gerar_site(resultados(v["resultados"]), destino, titulo=e["titulo"],
                           arquivo={"inicio": inicio, "rotulo": f'{e["ano"]} · {e["cargo"]} · {e["turno"]}',
                                    "versoes": web.nav_versoes(e.get("versoes"), v, raiz_eleicao)})
    open(os.path.join(saida, ".nojekyll"), "w").close()
    print(f"site gerado em {saida}: {len(PAGINAS)} páginas + {len(eleicoes)} eleição(ões)")


if __name__ == "__main__":
    main()
