"""Aviso de licença e isenção de responsabilidade do rodapé de todas as páginas do site (um só lugar)."""

SITE = "https://tiagocaamorim.github.io/eleicoes_2026/"
LINKEDIN = "https://www.linkedin.com/in/tiago-amorim-eng/"
PAGINA = SITE + "licenca.html"

AVISO = ("© 2026 <a href=\"{linkedin}\" rel=\"me noopener\">Tiago Amorim</a>. As previsões são estimativas "
         "estatísticas, não resultados oficiais; a fonte oficial é o <a href=\"https://resultados.tse.jus.br/\">TSE</a>. "
         "Conteúdo fornecido “como está”, sem garantia de exatidão e sem responsabilidade do autor por erros ou por "
         "decisões tomadas com base nele. Pode usar os resultados, gráficos e textos citando Tiago Amorim "
         "(CC BY 4.0); o código é MIT. <a href=\"{pagina}\">Licença completa e como citar</a>.")


def aviso(pagina=PAGINA):
    return AVISO.format(linkedin=LINKEDIN, pagina=pagina)


def rodape_isolado():
    """Rodapé para páginas com estilo próprio (painéis): vale tanto no claro quanto no escuro."""
    return ('<footer style="max-width:960px;margin:32px auto 0;padding:16px 0 0;border-top:1px solid rgba(128,128,128,.35);'
            'font:13px/1.5 system-ui,sans-serif;opacity:.8">' + aviso() + "</footer>\n")
