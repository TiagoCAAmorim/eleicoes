# Eleições em dados

**Site: [tiagocaamorim.github.io/eleicoes](https://tiagocaamorim.github.io/eleicoes/)** · painel de 2026:
[modelo do dia da eleição](https://tiagocaamorim.github.io/eleicoes/2026/presidente/) e
[modelo revisado](https://tiagocaamorim.github.io/eleicoes/2026/presidente/revisado/)

Previsões da apuração em tempo real e análises de eleições brasileiras com dados abertos do TSE.
Código, dados processados e o site ficam juntos neste repositório; o site é publicado pelo GitHub Pages.

Começou como a previsão do 2º turno presidencial de 2026 (antes em `TiagoCAAmorim/misc`, pasta
`eleicao-presidencial/`; o histórico de commits veio junto).

## Estrutura

```
eleicoes/                 pacote Python
  caminhos.py             pastas do repositório (use sempre estas constantes)
  tse/aovivo.py           coleta do site de divulgação do TSE durante a apuração
  dados/geo.py            regiões, porte dos municípios
  modelos/transferencia.py  modelo de transferência de votos 1º → 2º turno
  modelos/previsao.py     roda o modelo sobre um retrato da apuração e resume por grupo
  modelos/primeiro_turno.py  modelo do 1º turno (vários candidatos; presidente, governador, senador, prefeito)
  site/                   imagens (painel, mapa), exportação de CSV e página do painel
  site/templates/         HTML do painel, do detalhe por município e dos indicadores
scripts/                  linha de comando
  apuracao.py             coleta + previsão + painel (uma rodada ou em loop)
  backtest.py             simula a apuração de 2022 e mede erro e cobertura (--variante para testar variantes)
  primeiro_turno.py       rejogos do 1º turno (--cargo presidente|governador|senador|prefeito)
  estresse.py             teste de estresse: muitas apurações sintéticas (--calibrar mede o viés de ordem de 2026)
  aliancas.py             alianças contrafactuais de deputados: validar, efeito, busca, exportar, simular
  rejogar_2026.py         rejoga a apuração real de 2026 com variantes do modelo
  rejogar_paginas_2026.py refaz as saídas da noite de 2026 com outro modelo (versão "revisado" do site)
  paineis_simulados.py    apurações simuladas dos 2º turnos presidenciais de 2006 a 2022 (painéis do site)
  extrair_retratos_2026.py  extrai do histórico git os retratos da apuração de 2026
  gerar_site.py           gera o site completo em _site/
  prep_2022.py, priori_2022.py, baixar_ibge.py, importancia.py, verificar.py, probe_tse.py
config/eleicoes.json      eleições publicadas no site (uma entrada por eleição e cargo)
dados/                    entradas: comum/ (municípios, malhas), ibge/, priori/, <ano>/<cargo>/
resultados/               saídas versionadas: 2026-presidente/ (inclui 49 retratos no histórico git), backtest/, importancia/,
                          simulacoes/ (apurações simuladas de 2006 a 2022)
site/                     páginas fixas do site (início, modelos, análises, testes por cargo) e estilo comum
docs/                     metodologia, roteiro e histórico da apuração de 2026
tests/                    testes rápidos (pytest)
.github/workflows/        site (Pages), testes, apuração ao vivo
```

## Como rodar

```bash
git clone https://github.com/TiagoCAAmorim/eleicoes.git && cd eleicoes
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/gerar_site.py          # site em _site/ (abra _site/index.html ou: python -m http.server -d _site)
python scripts/backtest.py --ordens 2022 --rodadas 1   # teste com 2022 (~2 min)
python scripts/exemplo_metodo.py      # exemplo fictício e gráficos de docs/metodo-detalhado.md (~30 s)
pytest -q                             # testes rápidos
```

Apuração ao vivo (próxima: eleições municipais de 2028; o código atual é o de presidente 2026):

```bash
python scripts/apuracao.py --loop 600 --git-push
python scripts/apuracao.py --demo-2022 30 --saida resultados/teste2022 --site resultados/teste2022/site   # ensaio com 2022
```

O ambiente de nuvem do Claude não acessa o TSE; downloads do TSE rodam no GitHub Actions ou localmente.

## Site

O workflow `site.yml` gera `_site/` com `scripts/gerar_site.py` e publica no GitHub Pages a cada push no `main`
que mude o site, os resultados, a configuração ou o código do site. Para ativar (uma vez): Settings → Pages →
Source: **GitHub Actions**.

Para incluir uma eleição no site: coloque as saídas em `resultados/<id>/` e acrescente uma entrada em
`config/eleicoes.json`.

## Documentação

- [docs/metodo-detalhado.md](docs/metodo-detalhado.md): o modelo revisado passo a passo, com equações e um exemplo fictício ao longo da apuração
- [docs/metodologia.md](docs/metodologia.md): o modelo do 2º turno e o backtest de 2022
- [docs/rejogo-2026.md](docs/rejogo-2026.md): variantes do modelo na apuração real de 2026 e em 2022
- [docs/paineis-simulados.md](docs/paineis-simulados.md): apurações simuladas de 2006 a 2022 (painéis do site)
- [docs/revisao-t2.md](docs/revisao-t2.md): revisão da incerteza do modelo do 2º turno (sem curva de transição)
- [docs/estresse.md](docs/estresse.md): teste de estresse com apurações sintéticas (gerador calibrado em 2026, repetido com 2010, 2014 e 2018)
- [docs/calibracao-priori.md](docs/calibracao-priori.md): priori calibrada com os 2º turnos de 2006 a 2026 e as pesquisas da véspera
- [docs/covariaveis.md](docs/covariaveis.md): covariáveis municipais (deputados, prefeitos, reeleição) testadas e não adotadas
- [docs/governador.md](docs/governador.md): 2º turno de governador com o modelo de transferência (2006–2022)
- [docs/prefeito.md](docs/prefeito.md): 2º turno de prefeito com o modelo por seção (2008–2024)
- [docs/base-historica.md](docs/base-historica.md): base de votos por município do TSE, 2006–2024 (`dados/historico/`)
- [docs/roteiro.md](docs/roteiro.md): etapas da revisão do modelo e da expansão para outros cargos
- [docs/historico/](docs/historico/): protocolo dos agentes usados durante a apuração de 2026

## Licença

Código sob [MIT](LICENSE); textos, gráficos e resultados sob CC BY 4.0 (cite Tiago Amorim). As previsões são estimativas estatísticas, sem garantia; a fonte oficial é o TSE. Detalhes em [LICENSE](LICENSE) e na página `licenca.html` do site. O aviso do rodapé de todas as páginas vem de `eleicoes/site/licenca.py` e `site/_rodape.html`.
