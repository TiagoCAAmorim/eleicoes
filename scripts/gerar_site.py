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
# contato do autor na página inicial (perfil no LinkedIn)
CONTATO_LINKEDIN = "https://www.linkedin.com/in/tiago-amorim-eng/"
# botão "Me pague um café" no topo das páginas fixas: copia esta chave Pix
CHAVE_PIX = "bcd8d244-8aeb-4003-99ca-d8ba4f5f5952"
PAGINAS = ["index.html", "modelos.html", "analises.html"]


def _ler(nome):
    with open(os.path.join(SITE, nome), encoding="utf-8") as f:
        return f.read()


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


def figuras_modelos(pasta_img):
    """Copia os gráficos da página Modelos (gerados por scripts/graficos_modelos.py) para o site."""
    origem = os.path.join(RESULTADOS, "modelos")
    if not os.path.isdir(origem):
        print("aviso: resultados/modelos/ não existe; rode python scripts/graficos_modelos.py")
        return
    os.makedirs(pasta_img, exist_ok=True)
    for nome in sorted(os.listdir(origem)):
        if nome.endswith(".png"):
            shutil.copy(os.path.join(origem, nome), os.path.join(pasta_img, nome))


def contato():
    u = html.escape(CONTATO_LINKEDIN)
    return f'Contato: <a href="{u}" rel="me noopener" target="_blank">meu perfil no LinkedIn</a>.'


def pagina(nome, extras, gerado_em):
    corpo = _ler(nome)
    m = re.match(r"<!-- página: (\w+) \| titulo: (.*?) \| descricao: (.*?) -->\n", corpo)
    chave, titulo, descricao = m.groups()
    corpo = corpo[m.end():]
    for k, v in extras.items():
        corpo = corpo.replace("{{" + k + "}}", v)
    subs = {"titulo": titulo, "descricao": descricao, "raiz": "./",
            "gerado_em": gerado_em, "chave_pix": CHAVE_PIX}
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
              "contato": contato()}
    for nome in PAGINAS:
        with open(os.path.join(saida, nome), "w", encoding="utf-8") as f:
            f.write(pagina(nome, extras, gerado_em))
    figuras_modelos(os.path.join(saida, "img", "modelos"))
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
