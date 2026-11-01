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
passam a dominar a estimativa (atualização bayesiana). Ao vivo em 2026 havia ainda uma curva de transição que
segurava a previsão perto da priori até 25% apurado; a revisão da etapa 3 tirou a curva
([revisao-t2.md](revisao-t2.md)).

A incerteza é obtida por simulação de Monte Carlo (1000 cenários) que combina:
- incerteza dos parâmetros (aproximação de Laplace) e variação entre municípios;
- choque comum por UF (2% da margem do eleitorado restante), mais um extra de até 4% que diminui conforme a UF
  é apurada;
- choque nacional de 1%: o que falta apurar pode diferir todo no mesmo sentido;
- viés da evidência parcial (1,5%): as seções que chegam primeiro em cada município podem não representar as
  que faltam, no mesmo sentido no país todo. Vale cheio no que falta dos municípios já começados e, nos não
  começados, proporcional a quão parcial é o que já foi apurado.

A escala foi calibrada no rejogo de 2026 e no backtest de 2022 em quatro ordens de apuração. A chance de vitória é a fração dos cenários em que o candidato
passa de 50% dos votos válidos.

Os resultados saem por Brasil, região, UF e porte da cidade (capitais, grandes
> 200 mil eleitores, médias 50–200 mil, pequenas < 50 mil, exterior).

## Backtest com 2022

`python scripts/backtest.py` usa o 1º turno de 2022 por município e simula a apuração do 2º
turno seção a seção em quatro ordens: aleatória, parecida com 2022 (Sul/Sudeste antes,
Nordeste e capitais depois), "zonas" (como a de 2022, mas em cada município as zonas mais pró-Bolsonaro apuram
antes, um viés que o 1º turno por município não enxerga) e adversa (seções quase em ordem de voto em Bolsonaro,
um pior caso irreal que nenhum modelo com dados por município consegue corrigir). Os dados
por seção vêm dos dados abertos do TSE (`scripts/prep_2022.py`, já processados em
`dados/2022/presidente/`). Resultados em `resultados/backtest/`.

