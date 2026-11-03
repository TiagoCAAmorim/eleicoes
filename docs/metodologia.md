# Metodologia: previsão da apuração do 2º turno

Resumo do modelo em uso desde novembro de 2026 (`eleicoes/modelos/transferencia.py` com a configuração
`calibrado_cauteloso` de `eleicoes/modelos/priori.py`). O site tem a versão para o público, com os gráficos dos testes
(página Modelos, gerada de `site/modelos.html`; gráficos por `scripts/graficos_modelos.py`). Equações e um exemplo
numérico: [metodo-detalhado.md](metodo-detalhado.md). Histórico das decisões: [roteiro.md](roteiro.md).

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

Ponto de partida (priori, [calibracao-priori.md](calibracao-priori.md)): a média, grupo a grupo e em escala logit,
das matrizes de todas as eleições anteriores (2006–2022, cada uma estimada com a apuração completa,
`dados/priori/presidente_<ano>.json`). A linha "Outros" é ajustada para que a previsão de antes da apuração bata com a
pesquisa da véspera (`dados/pesquisas/presidente_t2.csv`), com desvio 0,3 em logit; a hierarquia usa `tau` 0,15.
Conforme as seções são apuradas, os dados passam a dominar. Ao vivo em 2026 a priori era só a matriz de 2022 e havia
uma curva de transição que segurava a previsão perto da priori até 25% apurado; a curva saiu na revisão
([revisao-t2.md](revisao-t2.md)).

A incerteza é obtida por simulação de Monte Carlo (1000 cenários) que combina:
- incerteza dos parâmetros (aproximação de Laplace) e variação entre municípios;
- choque comum por UF (2% da margem do eleitorado restante), mais um extra de 2% antes de abrir as urnas e de até
  4% depois, que diminui conforme a UF é apurada;
- choque nacional de 1%: o que falta apurar pode diferir todo no mesmo sentido;
- viés da evidência parcial (1,5%): as seções que chegam primeiro em cada município podem não representar as
  que faltam, no mesmo sentido no país todo. Vale cheio no que falta dos municípios já começados e, nos não
  começados, proporcional a quão parcial é o que já foi apurado.

As escalas foram calibradas no rejogo de 2026, nos rejogos por município de 2010–2026 e no teste de estresse com
2010, 2014, 2018 e 2022 ([estresse.md](estresse.md)). A chance de vitória é a fração dos cenários em que o candidato
passa de 50% dos votos válidos.

Testados e não adotados: matriz v2 ([matriz-v2.md](matriz-v2.md)) e covariáveis municipais
([covariaveis.md](covariaveis.md)). Outros cargos: governador ([governador.md](governador.md), mesmo modelo com viés
da evidência parcial de 3%) e prefeito ([prefeito.md](prefeito.md), seção como unidade e choque comum de 6%).

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

