# 2º turno de prefeito (etapa 5, parte 2)

Numa cidade não há municípios para comparar entre si. Por isso, no 2º turno de prefeito, **a unidade do modelo
passa a ser a seção eleitoral**: a matriz de transferência leva os votos do 1º turno de cada seção para o 2º, como
no presidente e no governador leva os de cada município. Código:

- `scripts/tse_secoes_prefeito.py` e o workflow `secoes_prefeito` (Actions) baixam a base;
- `scripts/prefeito.py` faz o ajuste e os rejogos;
- `eleicoes/modelos/priori.py` traz `config_prefeito`.

Saídas em `resultados/prefeito/`.

## A base

Houve 246 segundos turnos de prefeito de 2008 a 2024: 30 em 2008, 50 em 2012, 57 em 2016, 58 em 2020 e 51 em
2024. Para cada cidade, `dados/historico/<ano>/prefeito_secoes.csv.gz` traz por seção:

- aptos, comparecimento e brancos + nulos nos dois turnos;
- votos de A e B nos dois turnos e dos demais candidatos no 1º.

Como no governador, **A é o mais votado no 1º turno** entre os dois que foram ao 2º. Ele venceu 73% dos 2º turnos
de 2012–2024. Todas as seções têm o detalhe de aptos e comparecimento, e os totais conferem com o oficial (São
Paulo 2024: Nunes 59,35%). As cidades vão de 700 seções a 26 mil (São Paulo).

## As matrizes

Cada cidade foi ajustada com a apuração completa. Em pontos percentuais:

| | A→B | B→A | Outros→A | Outros→B | Abstenção do 1º turno → A | → B |
|---|---|---|---|---|---|---|
| Média das 246 cidades | 3 | 4 | 46 | 48 | 9 | 7 |
| 10% menores | 0 | 0 | 21 | 22 | 0 | 0 |
| 10% maiores | 10 | 13 | 71 | 74 | 22 | 19 |

O quadro é parecido com o do governador: pouca troca entre A e B, e a linha Outros varia muito de cidade para
cidade.

## A priori

A priori de cada eleição é a média das matrizes de todas as cidades dos anos anteriores. 2008 fica de fora da
avaliação, porque não tem anos anteriores. Sobram 216 eleições (2012–2024).

Testei também um nível de zona eleitoral entre a cidade e as seções. Não melhorou (CRPS um pouco pior em 2012), então a matriz é
uma só para a cidade inteira.

## Como os rejogos simulam a apuração

**Não há retratos parciais de apurações de prefeito.** Os rejogos usam uma ordem de chegada sintética, e o
resultado depende dela.

- Ao contrário de um município no presidente, uma seção chega inteira.
- As zonas eleitorais começam a mandar seções em instantes sorteados, então bairros inteiros chegam juntos.
- Um viés sorteado em cada rejogo faz as seções mais favoráveis a A (ou a B) chegarem antes.

Usei dois tamanhos de viés:

- **moderado** (`--vies 0.1`);
- **forte** (`--vies 0.3`): as seções chegam quase em ordem do voto de A, o que é pessimista.

Foram dois rejogos por eleição, ou seja, 432 por ponto da apuração.

## Resultado

Com a configuração do governador (`media`), a faixa fica estreita demais na segunda metade da apuração: com 90%
apurado, cobre só 70% com viés moderado e 36% com viés forte.

O motivo é o mesmo do governador, só que mais forte. O modelo trata o erro de cada seção que falta como
independente, e a soma de milhares de seções fica quase sem incerteza. Mas as seções que faltam podem estar todas
do mesmo lado da cidade. A correção é um **choque comum na margem do que falta apurar** que não encolhe com o %
apurado (`choque_uf`; numa cidade só, a "UF" é a cidade).

Cobertura do intervalo de 90% (meta 90%) e largura em pontos:

| % apurado | `media`, moderado | `media`, forte | choque 4%, moderado | choque 4%, forte | **choque 6%, moderado** | **choque 6%, forte** | Largura, choque 6% |
|---|---|---|---|---|---|---|---|
| 0 | 90% | 90% | 93% | 93% | 96% | 96% | 32,6 |
| 1 | 88% | 76% | 96% | 89% | 99% | 96% | 24,7 |
| 5 | 95% | 82% | 99% | 93% | 100% | 98% | 23,1 |
| 10 | 97% | 85% | 100% | 95% | 100% | 99% | 21,4 |
| 30 | 98% | 86% | 100% | 98% | 100% | 100% | 15,2 |
| 50 | 96% | 81% | 100% | 97% | 100% | 100% | 9,8 |
| 70 | 90% | 66% | 99% | 92% | 100% | 99% | 5,3 |
| 90 | 70% | 36% | 92% | 76% | 100% | 93% | 1,6 |

**Adotei o choque de 6%** (`media_c6`, em `priori.PREFEITO`). É a única variante que cobre pelo menos 93% em toda a
apuração com o viés forte. O preço é uma faixa larga: com o viés moderado, o intervalo de 50% cobre 70% a 93%
(meta 50%). Com o choque de 4%, a faixa é cerca de 25% mais estreita, mas cai para 76% no fim da apuração com o
viés forte.

O erro médio de antes da apuração (5,6 pontos) e a faixa de 33 pontos refletem só a priori genérica, sem pesquisa.
Por ano, a cobertura com o choque de 6% e viés forte fica entre 90% e 100% em todos os pontos.

Houve uma chamada errada em 432 rejogos (mais de 99% para quem perdeu), com 1% apurado e viés forte.

## Limites e próximos passos

- **O tamanho do viés de ordem é uma suposição.** Com um retrato parcial real de uma apuração de prefeito (ex.: 2028,
  guardado durante a noite), dá para medir o viés e escolher entre 4% e 6%.
- **Pesquisas da véspera** devem cortar o erro de antes da apuração, como no governador (de 6 para 3 pontos). Ficam
  para depois.
- **Senador e 1º turno de prefeito** não têm 2º turno. O modelo de transferência precisa do 1º turno como ponto de
  partida, então esses casos vão para a etapa 6 (previsão do 1º turno).

## Como usar

```python
from eleicoes.modelos import priori
cfg = priori.config_prefeito(2028)    # média dos 2º turnos de prefeito de 2008–2024, choque comum de 6%
```

A base precisa ser por seção, no formato de `scripts/prefeito.py` (`carregar`).

```bash
python scripts/prefeito.py --rodadas 2 --variantes media media_c4 media_c6 --vies 0.3 --saida v0.3   # ~1 hora
```
