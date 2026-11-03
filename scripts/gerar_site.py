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
from urllib.parse import quote

import _raiz  # noqa: F401
from eleicoes.caminhos import RAIZ, RESULTADOS, SITE, resultados
from eleicoes.site import web

FUSO = dt.timezone(dt.timedelta(hours=-3))
# contato do autor na página inicial (perfil no LinkedIn)
CONTATO_LINKEDIN = "https://www.linkedin.com/in/tiago-amorim-eng/"
# botão "Me pague um café" no topo das páginas fixas: copia esta chave Pix
CHAVE_PIX = "bcd8d244-8aeb-4003-99ca-d8ba4f5f5952"
PAGINAS = ["index.html", "modelos.html", "analises.html", "aliancas.html"]


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


ANOS_ALIANCAS = [2006, 2010, 2014, 2018, 2022, 2026]


def _link_sim(ano, cargo, grupos, uf=None):
    """Âncora da página de alianças que abre o simulador com o cenário (índice = ordem de aliancas/dados/indice.json)."""
    i = 2 * ANOS_ALIANCAS.index(int(ano)) + (0 if cargo == "deputado federal" else 1)
    g = ";".join(",".join(x) for x in grupos)
    return f'#e={i}&b=real' + (f"&uf={uf}" if uf else "") + "&g=" + quote(g)


def tabelas_aliancas():
    """Tabelas da página de alianças, a partir de resultados/aliancas (python scripts/aliancas.py efeito busca validar)."""
    pasta = os.path.join(RESULTADOS, "aliancas")
    vazio = '<p class="meta">Ainda não gerado (python scripts/aliancas.py {0}).</p>'
    out = {"aliancas_efeito": vazio.format("efeito"), "aliancas_busca": vazio.format("busca"),
           "aliancas_validacao": vazio.format("validar")}
    try:
        import pandas as pd
    except ImportError:
        return out
    esc = html.escape

    def tabela(cab, linhas, num=()):
        th = "".join(f'<th class="num">{esc(c)}</th>' if i in num else f"<th>{esc(c)}</th>" for i, c in enumerate(cab))
        tr = "\n".join("<tr>" + "".join(f'<td class="num">{v}</td>' if i in num else f"<td>{v}</td>"
                                         for i, v in enumerate(l)) + "</tr>" for l in linhas)
        return f'<div class="tabela-rolagem"><table><thead><tr>{th}</tr></thead><tbody>\n{tr}\n</tbody></table></div>'

    def sinal(n):
        n = int(n)
        return f'<span class="pos">+{n}</span>' if n > 0 else (f'<span class="neg">{n}</span>' if n < 0 else "0")

    arq = os.path.join(pasta, "efeito_aliancas.csv")
    if os.path.exists(arq):
        e = pd.read_csv(arq)
        e = e[~e["fora"].astype(bool)]
        partes = []
        for cargo in ["deputado federal", "deputado estadual"]:
            x = e[e["cargo"] == cargo]
            m = x.groupby(["partido", "ano"])["ganho"].sum().unstack("ano").reindex(columns=ANOS_ALIANCAS).fillna(0)
            m["Total"] = m.sum(axis=1)
            m = m[m["Total"] != 0].sort_values("Total", ascending=False)
            linhas = [[esc(pp)] + [sinal(v) if a != "Total" else f"<strong>{sinal(v)}</strong>" for a, v in r.items()]
                      for pp, r in m.head(15).iterrows()]
            t1 = tabela(["Partido"] + [str(a) for a in ANOS_ALIANCAS] + ["Total"], linhas, range(1, len(ANOS_ALIANCAS) + 2))
            # membros que perderam cadeiras dentro da própria aliança
            perdas = x[x["ganho"] < 0].sort_values(["ganho", "ano"]).head(12)
            lp = []
            for r in perdas.itertuples():
                membros = sorted(e[(e["ano"] == r.ano) & (e["cargo"] == cargo) & (e["uf"] == r.uf) &
                                   (e["alianca"] == r.alianca)]["partido"])
                link = _link_sim(r.ano, cargo, [(mm,) for mm in membros], r.uf)
                lp.append([str(r.ano), r.uf, esc(r.partido), esc(" / ".join(membros)), str(r.cadeiras_com),
                           str(r.cadeiras_sem), sinal(r.ganho), f'<a href="{link}">simular</a>'])
            t2 = tabela(["Ano", "UF", "Partido", "Aliança", "Com", "Sem", "Efeito", ""], lp, (4, 5, 6))
            nome = "federais" if cargo == "deputado federal" else "estaduais"
            partes.append(f"""<h3>Deputados {nome}: saldo de cada partido</h3>
<p class="meta">Soma, em todas as UFs, das cadeiras que cada partido ganhou (+) ou perdeu (−) por estar na sua
coligação ou federação, contra a mesma eleição com só aquela aliança desfeita. Os 15 maiores saldos.</p>
{t1}
<details><summary>Quem perdeu cadeira dentro da própria aliança (deputados {nome})</summary>
<p class="meta">Partidos que teriam mais cadeiras sozinhos: os votos deles ajudaram a eleger candidatos dos parceiros.</p>
{t2}
</details>""")
        out["aliancas_efeito"] = "\n".join(partes)

    arq = os.path.join(pasta, "busca_pares.csv")
    if os.path.exists(arq):
        b = pd.read_csv(arq)
        partes = []
        for cargo in ["deputado federal", "deputado estadual"]:
            linhas = []
            for ano in ANOS_ALIANCAS:
                g = b[(b["ano"] == ano) & (b["cargo"] == cargo) & (b["ganho"] > 0)]
                for r in g.sort_values(["ganho", "juntos_a"], ascending=False).head(5).itertuples():
                    link = _link_sim(ano, cargo, [(r.a, r.b)])
                    linhas.append([str(ano), f"{esc(r.a)} + {esc(r.b)}", str(r.real_a + r.real_b),
                                   str(r.juntos_a + r.juntos_b), sinal(r.ganho),
                                   f"{esc(r.a)} {sinal(r.juntos_a - r.real_a)}, {esc(r.b)} {sinal(r.juntos_b - r.real_b)}",
                                   f'<a href="{link}">simular</a>'])
            t = tabela(["Ano", "Par", "Real", "Juntos", "Ganho", "Por partido", ""], linhas, (2, 3, 4))
            nome = "federais" if cargo == "deputado federal" else "estaduais"
            partes.append(f"<h3>Deputados {nome}: os 5 melhores pares de cada eleição</h3>\n{t}")
        out["aliancas_busca"] = "\n".join(partes)

    arq = os.path.join(pasta, "validacao.csv")
    if os.path.exists(arq):
        v = pd.read_csv(arq)
        linhas = [[str(r.ano), esc(r.cargo), str(r.vagas), str(r.eleitos_iguais), f"{r.pct:.1f}%".replace(".", ",")]
                  for r in v.itertuples()]
        out["aliancas_validacao"] = tabela(["Ano", "Cargo", "Vagas", "Eleitos iguais", "Acerto"], linhas, (2, 3, 4))
    return out


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
              "contato": contato(), **tabelas_aliancas()}
    for nome in PAGINAS:
        with open(os.path.join(saida, nome), "w", encoding="utf-8") as f:
            f.write(pagina(nome, extras, gerado_em))
    figuras_modelos(os.path.join(saida, "img", "modelos"))
    shutil.copy(os.path.join(SITE, "estilo.css"), os.path.join(saida, "estilo.css"))
    shutil.copy(os.path.join(SITE, "aliancas.js"), os.path.join(saida, "aliancas.js"))
    # dados do simulador de alianças (um JSON por eleição de deputados)
    import aliancas
    aliancas.exportar(ANOS_ALIANCAS, os.path.join(saida, "aliancas", "dados"))
    web.copiar_icones(saida)
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
