# Revisão do modelo do 2º turno (etapa 3, parte 1: incerteza)

Esta parte trata só da incerteza e da curva de transição, que podiam ser testadas com os dados que já temos
(rejogo de 2026 e backtest de 2022). Matriz mais flexível, covariáveis (deputados, reeleição, coligações) e
priori calibrada dependem da base histórica (etapa 2).

## O que mudou

| | Ao vivo em 2026 | Revisado |
|---|---|---|
| Curva de transição (priori → dados até 25% apurado) | sim | não |
| Choque nacional na margem do que falta apurar | 0 | 1% |
| Viés da evidência parcial (`choque_parcial`) | 0 | 1,5% |
| Choque por UF | 2% | 2% + até 4% enquanto a UF tem pouco apurado |

O **viés da evidência parcial** substitui a curva. As seções que chegam primeiro em um município podem não
representar as que faltam (centro x periferia, zonas urbanas x rurais), e esse desvio tende a ir no mesmo sentido
no país todo. O modelo agora sorteia um viés comum que vale cheio no que falta dos municípios já começados e, nos
municípios ainda não começados, é proporcional a quão parcial é a evidência apurada (P = 1 − fração média
apurada dos municípios com votos, ponderada pelos votos). Em 2026, P caiu de 0,67 com 3% apurado para 0,2 com
50%.

A curva antiga segurava a *média* perto da priori; o substituto mexe só na *largura*: a previsão segue os dados
desde o começo, e a faixa é que fica larga enquanto a evidência é parcial.

Configuração em `eleicoes/modelos/transferencia.py` (`Config`). A variante `atual` de
`scripts/rejogar_2026.py` reproduz o modelo usado ao vivo.

## Resultados em 2026 (rejogo dos 45 retratos)

| | Ao vivo | Revisado |
|---|---|---|
| Erro médio Brasil | −1,02 pt | −0,13 pt |
| Cobertura 90% Brasil | 84% | 100% |
| CRPS Brasil (menor é melhor) | 0,68 | 0,33 |
| Largura média do intervalo de 90% | 2,2 pt | 2,7 pt |
| Cobertura 90% UFs (todas / até 5% apurado) | 90% / 83% | 96% / 92% |
| Chance > 99% a partir de | 26% apurado | 52% apurado |

Antes de abrir as urnas o intervalo revisado (45,0–51,8) cobre o resultado (51,78) por pouco: o centro (48,4) continua
vindo da priori de 2022 + pesquisas, que errou 3,4 pontos. Isso só melhora com a priori calibrada (etapa 2/3).

## Resultados em 2022 (backtest, 18 pontos de 0,5% a 99%)

| Ordem de apuração | Ao vivo: erro / cobertura 90% | Revisado: erro / cobertura 90% |
|---|---|---|
| Parecida com a real | 0,41 / 94% | 0,12 / 100% |
| Aleatória por seção | 0,50 / 94% | 0,06 / 100% |
| Zonas pró-Bolsonaro antes em cada município (nova) | 0,50 / 61% | 0,28 / 94% |
| Adversa (quase em ordem de voto) | 1,12 / 44% | 3,03 / 0% |

A ordem **adversa** (seções quase ordenadas pelo voto em Bolsonaro) é um pior caso irreal: com 90% apurado a
parcial ainda estava em 48,9% contra 50,9% no final. Nenhum modelo que só vê totais por município separa esse
viés de uma virada real. A curva antiga "acertava" ali por acaso (presa à priori), e era justamente isso que
atrasou 2026. Para o teste de estresse ficou a ordem **zonas**, que é o mesmo tipo de viés em intensidade
plausível; nela a cobertura sobe de 61% para 94%.

## Custo e pontos em aberto

- **Chamada mais tarde**: a chance passa de 99% com 52% apurado em 2026 (antes 26%). É o preço de não depender
  da priori. A variante `revisado_uf_menor` (choque por UF de 2%) chama com 48% e cobre 98% no Brasil, mas só 85%
  nas UFs até 5% apurado.
- **UFs largas demais no meio da noite**: o intervalo de 50% das UFs cobre 81% (deveria ser ~50%). A faixa de 90%
  está certa, mas a distribuição tem caudas grossas demais no meio. Ajuste fino na etapa 4, com mais ordens e
  anos.
- Calibração feita com uma eleição real (2026) e uma simulada (2022): os números podem mudar com 2006–2018.

Reproduzir: `python scripts/rejogar_2026.py` e `python scripts/backtest.py [--variante atual] --rodadas 1`.
Saídas em `resultados/rejogo-2026/` e `resultados/backtest/` (`variantes_2022.csv` tem a comparação de 2022).
