# Metodologia: previsão da apuração do 2º turno

Modelo usado ao vivo em 25/10/2026 (`eleicoes/modelos/transferencia.py`). Limitações conhecidas e a revisão planejada estão em [roteiro.md](roteiro.md).


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

Ponto de partida (priori): as transferências estimadas na apuração completa de 2022 (`dados/priori/presidente_2022.json`,
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

`python scripts/backtest.py` usa o 1º turno de 2022 por município e simula a apuração do 2º
turno seção a seção em três ordens: aleatória, parecida com 2022 (Sul/Sudeste antes,
Nordeste e capitais depois) e adversa (seções mais pró-Bolsonaro primeiro). Os dados
por seção vêm dos dados abertos do TSE (`scripts/prep_2022.py`, já processados em
`dados/2022/presidente/`). Resultados em `resultados/backtest/`.

