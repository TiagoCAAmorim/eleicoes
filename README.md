# Previsão da apuração presidencial (2º turno 2026)

Acompanha a apuração do 2º turno no site de divulgação do TSE e prevê o resultado
final a partir do resultado do 1º turno em cada município. Roda a cada 10 minutos e
gera um painel estático (imagens PNG para o WhatsApp e uma página HTML).

## Saídas

Ficam em `saida/2026/` (atualizadas no branch do projeto a cada rodada):

| Arquivo | Conteúdo |
|---|---|
| `painel.png` | Resumo para compartilhar: % previsto, intervalo de 90%, chance de vitória, linha do tempo e tabela por região e porte |
| `estados.png` | Previsão por região, porte e estado com intervalo |
| `mapa_municipios.png` | Mapa por município: apurado e previsto, em polígonos e em círculos proporcionais aos votos |
| `index.html` | Página única com tudo, inclusive as transferências estimadas |
| `analises.html` (no site) | Detalhe por município (busca) e curiosidades; lê `dados_municipios.csv` publicado a cada rodada |
| `indicadores.html` (no site) | Indicadores do IBGE (`data/ibge/`) e o voto: Gradient Boosting validado por estado, SHAP, permutação e Spearman. Gerado à parte por `scripts/importancia.py` em `saida/importancia/` |
| `historico.csv` | Uma linha por rodada (base da linha do tempo) |
| `resultado.json` | Todos os números da última rodada |

## Modelo

Para cada município, o 1º turno é descrito pela fração do eleitorado que votou em A
(Lula), B (Flávio Bolsonaro), Outros (soma dos demais candidatos), branco/nulo ou que
se absteve. O 2º turno é previsto por uma matriz de transferência:

| Origem (1º turno) | → A | → B | → branco/nulo | → abstenção |
|---|---|---|---|---|
| A | 1 − troca − falta | troca A→B | 0 | falta |
| B | troca B→A | 1 − troca − falta | 0 | falta |
| Outros | oA | oB | oW | oN (soma = 100%) |
| Branco/nulo | 0 | 0 | 1 − falta | falta |
| Abstenção | nA | nB | 0 | 1 − nA − nB |

Os 8 parâmetros (troca A→B, troca B→A, falta, oA, oB, oW, nA, nB) são estimados por
mínimos quadrados ponderados nos municípios já apurados, em uma hierarquia
Brasil → região → UF → UF × porte da cidade. Cada nível é puxado para o nível de cima,
então um grupo com poucos municípios apurados usa a informação dos vizinhos mais
próximos que já têm dados. Municípios parcialmente apurados combinam o próprio
resultado parcial com a previsão do modelo para as seções que faltam.

Ponto de partida (priori): as transferências estimadas na apuração completa de 2022 (`data/priori_2022.json`,
gerado por `scripts/priori_2022.py`), por Brasil, região, UF e porte. A linha "Outros" usa as pesquisas de 2º
turno de 2026 (Quaest, 17–20/out: eleitores de Cury, Caiado, Renan Santos e demais, ponderados pelos votos de
cada um), porque os candidatos de fora do 2º turno são outros. Conforme as seções são apuradas, os dados de 2026
passam a dominar a estimativa de forma gradual (atualização bayesiana).

A incerteza é obtida por simulação de Monte Carlo (1000 cenários) que combina:
incerteza dos parâmetros (aproximação de Laplace), choque comum por UF e variação
entre municípios, com a escala calibrada no backtest de 2022 (cobertura de ~90% nos estados). A chance de vitória é a fração dos cenários em que o candidato
passa de 50% dos votos válidos.

Os resultados saem por Brasil, região, UF e porte da cidade (capitais, grandes
> 200 mil eleitores, médias 50–200 mil, pequenas < 50 mil, exterior).

## Backtest com 2022

`python backtest.py` usa o 1º turno de 2022 por município e simula a apuração do 2º
turno seção a seção em três ordens: aleatória, parecida com 2022 (Sul/Sudeste antes,
Nordeste e capitais depois) e adversa (seções mais pró-Bolsonaro primeiro). Os dados
por seção vêm dos dados abertos do TSE (`scripts/prep_2022.py`, já processados em
`data/2022/`). Resultados em `saida/backtest/`.

## Como rodar no seu computador

```bash
git clone -b claude/project-thread-0md8n6 https://github.com/TiagoCAAmorim/misc.git
cd misc/eleicao-presidencial
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py                                    # uma rodada (teste)
python run.py --loop 600 --publicar ../../eleicao-2026 --git-push
```

- `--loop 600`: roda a cada 10 minutos até você interromper (Ctrl+C). Uma rodada leva ~2 min (baixa os
  5.757 municípios do TSE, pulando os já 100% apurados e os estados sem novidade).
- `--publicar <pasta>`: gera o site interativo (index.html + painel.png + estados.png) dentro do clone do
  repositório público do GitHub Pages e faz `git push`. O site fica em `https://<usuario>.github.io/<repo>/`.
- `--git-push`: também salva as saídas (`saida/2026`) neste branch.
- As imagens para o WhatsApp ficam em `saida/2026/painel.png` e `saida/2026/estados.png`.

### Site no GitHub Pages (uma vez)

1. Crie um repositório **público** vazio (ex.: `eleicao-2026`) e clone-o ao lado do `misc`.
2. Em Settings → Pages: "Deploy from a branch", branch `main`, pasta `/ (root)`.
3. Rode com `--publicar ../../eleicao-2026` (caminho relativo à pasta `eleicao-presidencial`).

### Registro de atualizações

`data/atualizacoes.json` alimenta a seção "Atualizações" da página. Ao corrigir algo durante a apuração,
acrescente uma linha `{"quando": "dd/mm/aaaa hh:mm", "texto": "..."}`; a próxima rodada publica.

### Teste com 2022

```bash
python run.py --demo-2022 100 --saida saida/teste2022 --site saida/teste2022/site
```

Simula a apuração de 2022 (ordem parecida com a real) e gera o site em cada momento, com o resultado real
de cada grupo para comparação. `--demo-ordem aleatoria|adversa` muda a ordem de apuração.

### Alternativa: GitHub Actions

Editar `eleicao-presidencial/ligar.txt` neste branch liga um loop de ~5h40 no Actions
(`.github/workflows/eleicao-apuracao.yml`). Não use junto com o loop local.

## Fontes

- Malhas: estados simplificados em `data/estados_br.geojson`; municípios (IBGE, via tbrugz/geodata-br)
  simplificados em `data/municipios_br.geojson.gz`. Sete municípios criados depois da malha ficam sem polígono.

- Divulgação de resultados: `https://resultados.tse.jus.br/oficial/ele2026/{6257,6258}/dados/<uf>/<uf><município>-c0001-e00<eleição>-u.json`
  (6257 = 1º turno, 6258 = 2º turno, cargo 0001 = presidente)
- Dados abertos de 2022: `https://cdn.tse.jus.br/estatistica/sead/odsele/` (`votacao_secao`, `detalhe_votacao_secao`)
