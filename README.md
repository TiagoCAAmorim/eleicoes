# Previsão da apuração presidencial (2º turno 2026)

Acompanha a apuração do 2º turno no site de divulgação do TSE e prevê o resultado
final a partir do resultado do 1º turno em cada município. Roda a cada 10 minutos e
gera um painel estático (imagens PNG para o WhatsApp e uma página HTML).

## Saídas

Ficam em `saida/2026/` (atualizadas no branch do projeto a cada rodada):

| Arquivo | Conteúdo |
|---|---|
| `painel.png` | Resumo para compartilhar: % previsto, intervalo de 90%, chance de vitória, linha do tempo e tabela por região e porte |
| `estados.png` | Previsão por estado com intervalo |
| `index.html` | Página única com tudo, inclusive as transferências estimadas |
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

A incerteza é obtida por simulação de Monte Carlo (1000 cenários) que combina:
incerteza dos parâmetros (aproximação de Laplace), choque comum por UF e variação
entre municípios. A chance de vitória é a fração dos cenários em que o candidato
passa de 50% dos votos válidos.

Os resultados saem por Brasil, região, UF e porte da cidade (capitais, grandes
> 200 mil eleitores, médias 50–200 mil, pequenas < 50 mil, exterior).

## Backtest com 2022

`python backtest.py` usa o 1º turno de 2022 por município e simula a apuração do 2º
turno seção a seção em três ordens: aleatória, parecida com 2022 (Sul/Sudeste antes,
Nordeste e capitais depois) e adversa (seções mais pró-Bolsonaro primeiro). Os dados
por seção vêm dos dados abertos do TSE (`scripts/prep_2022.py`, já processados em
`data/2022/`). Resultados em `saida/backtest/`.

## Como rodar

```bash
pip install -r requirements.txt
python run.py               # uma rodada
python run.py --loop 600    # a cada 10 minutos, no seu computador
python run.py --demo-2022 35  # painel de teste com 2022 simulado até 35% apurado
```

No GitHub Actions o workflow `.github/workflows/eleicao-apuracao.yml` roda o loop e
salva o painel no branch do projeto.

## Fontes

- Divulgação de resultados: `https://resultados.tse.jus.br/oficial/ele2026/{6257,6258}/dados/<uf>/<uf><município>-c0001-e00<eleição>-u.json`
  (6257 = 1º turno, 6258 = 2º turno, cargo 0001 = presidente)
- Dados abertos de 2022: `https://cdn.tse.jus.br/estatistica/sead/odsele/` (`votacao_secao`, `detalhe_votacao_secao`)
