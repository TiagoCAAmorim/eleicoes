# Matriz v2 de transferência de votos (etapa 3)

Na matriz original, quem votou em branco ou nulo no 1º turno só podia repetir o voto ou faltar, e a chance de faltar
no 2º turno era a mesma para quem tinha votado em A e em B. A regressão por município de 2026
([roteiro.md](roteiro.md)) mostrou que o comparecimento pesou mais que os "outros" na mudança de cada candidato, e
a matriz não tinha por onde mostrar isso. A **matriz v2** acrescenta três parâmetros:

| Origem (1º turno) | A | B | Branco/nulo | Abstenção |
|---|---|---|---|---|
| A | 1 − pAB − pR | pAB | 0 | pR |
| B | pBA | 1 − pBA − **pRB** | 0 | **pRB** |
| Outros | oA | oB | oW | oN |
| Branco/nulo | **wA** | **wB** | 1 − pR − wA − wB | pR |
| Abstenção | nA | nB | 0 | 1 − nA − nB |

Os novos são **wA** e **wB** (branco/nulo do 1º turno que vota em A ou B, até 25% cada) e **pRB** (falta dos
eleitores de B, separada da dos eleitores de A, pR). O código é `Config(matriz_v2=True)` em
`eleicoes/modelos/transferencia.py`; a priori calibrada v2 sai de `priori.config_calibrada(base, pesquisa, v2=True)`.

## Priori própria

A flag já existia, mas os três parâmetros novos começavam de um chute genérico (3% de branco/nulo para cada lado,
falta de B igual à de A). Agora cada eleição tem também a sua matriz v2, estimada com a apuração completa
(`dados/priori/presidente_<ano>_v2.json`, gerada por `scripts/calibrar_priori.py`), e a priori calibrada v2 é a
média delas, como na v1. No nível Brasil:

| Ano | Ajuste por município, v1 → v2 (s0, % do eleitorado) | Branco/nulo → A | Branco/nulo → B | Falta A / falta B | Outros → A (v1 → v2) | Abstenção → A (v1 → v2) |
|---|---|---|---|---|---|---|
| 2006 | 3,30 → 2,77 | 25% | 4% | 2,9% / 3,0% | 87% → 78% | 4,1% → 0,1% |
| 2010 | 2,90 → 2,14 | 25% | 21% | 5,3% / 0,1% | 42% → 39% | 0,2% → 0,0% |
| 2014 | 2,76 → 2,20 | 25% | 19% | 3,6% / 0,0% | 40% → 37% | 0 → 0 |
| 2018 | 2,76 → 2,69 | 7% | 20% | 1,8% / 0,0% | 58% → 58% | 0 → 0 |
| 2022 | 1,38 → 1,31 | 23% | 0% | 1,2% / 0,0% | 22% → 10% | 0,5% → 2,2% |
| 2026 | 1,78 → 1,56 | 25% | 5% | 0,0% / 0,1% | 63% → 59% | 8,4% → 7,1% |

(Os números completos estão em `resultados/calibracao-priori/transferencias.json`.)

- A v2 **ajusta melhor os municípios em todos os anos** (o ruído s0 cai de 3% a 26%).
- Mas a leitura dos parâmetros continua ecológica. Branco/nulo → A encosta no limite de 25% em quatro das seis
  eleições: os municípios com muito voto nulo no 1º turno (Nordeste, interior) são os mesmos onde A cresce no 2º, e o
  modelo usa o canal novo para isso. Não dá para ler como "um quarto dos nulos votou em Lula".
- **Em 2026 a v2 não resolve a leitura das transferências.** Outros → Lula cai só de 63% para 59% (a pesquisa dizia
  32%), e a abstenção do 1º turno continua mandando 7% para Lula. A falta separada de B fica perto de zero em todos os
  anos; quem absorve a diferença é a falta dos eleitores de A, que já existia.

## Antes da apuração (2010–2026)

Previsão sem nenhum voto apurado, priori média das eleições anteriores e linha Outros pela pesquisa da véspera
(`resultados/calibracao-priori/antes_da_apuracao*.csv`):

| | Calibrado (v1) | Calibrado v2 | v2 com priori genérica |
|---|---|---|---|
| Erro médio absoluto, Brasil | 1,07 | 1,09 | 1,13 |
| Largura média do intervalo de 90%, Brasil | 6,7 | 6,4 | 7,3 |
| Cobertura 90%, Brasil | 4 de 5 | 4 de 5 | 4 de 5 |
| Erro médio absoluto, UFs | 2,48 | 2,65 | 2,61 |
| Cobertura 90%, UFs | 96% | 97% | 97% |

Empate no Brasil, como esperado: antes de abrir, o nível nacional é preso à pesquisa. Nas UFs, a v2 erra um pouco
mais (0,2 ponto). Nos dois casos, 2026 fica fora do intervalo (o erro da pesquisa, ver
[calibracao-priori.md](calibracao-priori.md)).

## Durante a apuração

**2010 a 2026 por município** (2 apurações sintéticas por ano, ordem parecida com a real e viés sorteado nas
primeiras seções, 16 pontos de 1% a 95%; `resultados/calibracao-priori/rejogo_calibrado_calibrado_v2.csv`):

| % apurado | Erro abs. Brasil v1 / v2 | CRPS Brasil v1 / v2 | Largura 90% v1 / v2 | Erro abs. UFs v1 / v2 | Cobertura 90% UFs v1 / v2 |
|---|---|---|---|---|---|
| até 5% | 0,79 / 0,77 | 0,61 / 0,60 | 4,9 / 4,9 | 1,34 / 1,31 | 99% / 100% |
| 5 a 15% | 0,65 / 0,61 | 0,50 / 0,49 | 3,8 / 3,9 | 1,06 / 1,02 | 99% / 100% |
| 15 a 30% | 0,50 / 0,46 | 0,37 / 0,36 | 2,8 / 2,8 | 0,75 / 0,73 | 99% / 99% |
| 30 a 60% | 0,26 / 0,25 | 0,20 / 0,19 | 1,7 / 1,7 | 0,45 / 0,44 | 97% / 98% |
| acima de 60% | 0,09 / 0,09 | 0,07 / 0,07 | 0,5 / 0,5 | 0,14 / 0,14 | 87% / 87% |
| **todos** | **0,45 / 0,43** | **0,348 / 0,339** | | **0,75 / 0,73** | **96% / 96%** |

Cobertura de 90% no Brasil igual nas duas (99%) e nenhuma chamada errada. A v2 tem CRPS menor em 61% dos pontos
(diferença média −0,009, erro-padrão 0,005) e em 4 dos 5 anos; a exceção é 2026 nesta simulação (0,26 → 0,27).

**Noite real de 2026** (retratos gravados, um a cada dois; `resultados/matriz-v2/rejogo-2026/`):

| | Calibrado | Calibrado v2 | Cauteloso | Cauteloso v2 |
|---|---|---|---|---|
| Com 1,6% apurado | 53,0 (50,8 – 55,1), 99% | 52,9 (50,7 – 55,1), 99% | 53,0 (50,4 – 55,5), 97% | 52,9 (50,2 – 55,5), 96% |
| CRPS Brasil até 5% | 0,64 | 0,59 | 0,65 | 0,61 |
| CRPS Brasil, noite toda | 0,298 | 0,289 | 0,314 | 0,306 |
| Cobertura 90% Brasil | 96% | 96% | 96% | 96% |
| Cobertura 90% / 50% UFs | 95% / 73% | 95% / 74% | 97% / 78% | 97% / 79% |
| CRPS UFs | 0,518 | 0,513 | 0,546 | 0,548 |
| Chance > 99% a partir de | 41% | 48% | 48% | 48% |

## Teste de estresse

16 apurações sintéticas com viés de ordem entre e dentro das cidades (gerador de [estresse.md](estresse.md)), rodadas
no PC do Tiago com `python scripts/estresse.py --rodadas 16 --variantes calibrado_cauteloso calibrado_cauteloso_v2
--saida resultados/estresse-v2` (`resultados/estresse-v2/resumo.csv`):

| % apurado | Cobertura 90% v1 / v2 | Cobertura 50% v1 / v2 | Erro abs. v1 / v2 | Largura 90% v1 / v2 | CRPS v1 / v2 |
|---|---|---|---|---|---|
| 0 | 62% / 56% | 25% / 25% | 2,32 / 2,52 | 4,3 / 4,3 | 1,82 / 2,01 |
| 1 | 88% / 88% | 56% / 50% | 1,15 / 1,41 | 5,5 / 5,7 | 0,85 / 0,99 |
| 3 | 94% / 94% | 56% / 56% | 1,00 / 1,18 | 4,9 / 5,2 | 0,73 / 0,82 |
| 5 | 94% / 94% | 56% / 56% | 0,94 / 1,06 | 4,5 / 4,8 | 0,68 / 0,75 |
| 10 | 94% / 94% | 62% / 50% | 0,80 / 0,87 | 3,8 / 4,1 | 0,57 / 0,61 |
| 20 | 94% / 94% | 69% / 62% | 0,60 / 0,63 | 3,0 / 3,2 | 0,43 / 0,45 |
| 30 a 90 | 81–94% (iguais) | 50–69% / 50–62% | iguais | iguais | iguais |
| **todos** | **89% / 88%** | **58% / 53%** | **0,79 / 0,87** | **3,1 / 3,3** | **0,585 / 0,640** |

Aqui a v2 **perde**: erra mais e tem faixa mais larga até ~20% apurado, com a mesma cobertura; de 30% em diante as
duas empatam. Nenhuma chamada errada em nenhuma. A diferença vem do começo da apuração, quando o que pesa é a
priori e as poucas cidades apuradas: com seções enviesadas dentro das cidades, os três parâmetros a mais dão ao
modelo mais liberdade para "explicar" o viés com transferências, e ele erra mais na extrapolação. (O gerador sorteia
as eleições de 2022 em torno da previsão da priori v1 mais os desvios reais das cidades; isso pode favorecer um
pouco a v1 em 0%, mas não explica a diferença de 1% a 20%.)

## Conclusão

A v2 ajusta melhor os municípios e ganha por pouco nas apurações sem viés dentro das cidades (CRPS ~3% menor), mas
perde mais do que isso no teste de estresse (CRPS ~9% maior, erro maior até 20% apurado). Como a meta é a faixa
honesta nas apurações difíceis, **a página revisada de 2026 continua com a v1 (calibrado cauteloso)**. A v2 fica
disponível (`matriz_v2=True`, `priori.config_calibrada(..., v2=True)`, variantes `*_v2` nos scripts), e as
exportações, as tabelas e o Sankey já sabem mostrar os três parâmetros novos se ela for usada.

O que a v2 também **não** resolve: ler as transferências de 2026 como a pesquisa (Outros → Lula ~32%). Com dados só
por município, o modelo atribui ao canal mais conveniente o crescimento de Lula onde houve mais nulo e mais
abstenção. Para separar isso faltam covariáveis (próximo item da etapa 3) ou o cruzamento das pesquisas por voto no
1º turno. Uma variação que talvez valha testar depois: só a falta separada para A e B, sem branco/nulo → candidatos,
com priori mais apertada nos parâmetros novos (`sd_v2`).

## Como rodar

```bash
python scripts/calibrar_priori.py --variantes calibrado,calibrado_v2,calibrado_v2_generico   # antes da apuração (~3 min)
python scripts/calibrar_priori.py --variantes "" --rejogo 2 --variante-rejogo calibrado,calibrado_v2   # ~40 min
python scripts/rejogar_2026.py --variantes calibrado calibrado_v2 calibrado_cauteloso calibrado_cauteloso_v2 \
    --passo 2 --saida resultados/matriz-v2/rejogo-2026                                         # ~10 min
# teste de estresse (~1h30 com 16 rodadas; rodado no PC):
python scripts/estresse.py --rodadas 16 --variantes calibrado_cauteloso calibrado_cauteloso_v2 --saida resultados/estresse-v2
```
