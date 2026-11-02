# 2º turno de governador (etapa 5, parte 1)

O primeiro cargo além de presidente é o 2º turno de governador. Ele usa o mesmo modelo de transferência: a matriz leva
os votos do 1º turno de cada município para o 2º. Código:

- `eleicoes/dados/historico.py` (`segundo_turno_governador`);
- `scripts/governador.py`;
- `eleicoes/modelos/priori.py` (`config_governador`).

Saídas em `resultados/governador/`.

## A base

Houve 59 segundos turnos de governador de 2006 a 2022. Ficam 56, porque o DF tem um município só e o modelo
precisa de vários. Como os candidatos mudam de UF para UF, **A é o mais votado no 1º turno** entre os dois que
foram ao 2º, e B é o outro. O líder do 1º turno venceu 71% dessas eleições. Os totais conferem com o oficial
(SP 2022: Tarcísio 55,27%).

## As matrizes

Cada 2º turno foi ajustado com a apuração completa (`dados/priori/governador.json`). Em pontos percentuais:

| | A→B | B→A | Outros→A | Outros→B | Abstenção do 1º turno → A | → B |
|---|---|---|---|---|---|---|
| Média das 56 eleições | 5 | 5 | 40 | 54 | 9 | 8 |
| 10% menores | 0 | 0 | 7 | 22 | 1 | 0 |
| 10% maiores | 16 | 14 | 71 | 87 | 24 | 17 |

A linha Outros varia muito mais que no presidente. Os outros candidatos de cada UF são diferentes, e as alianças de
2º turno também.

## A priori e as variantes

A priori de cada eleição é a média das matrizes de todos os 2º turnos de governador dos anos anteriores, de
qualquer UF. 2006 fica de fora da avaliação, porque não tem anos anteriores. Numa UF só não existe o choque nacional
do presidente: o choque "por UF" já é comum à eleição inteira.

| Variante | O que muda |
|---|---|
| `sem_priori` | ponto de partida genérico do modelo, desvio 1,5 |
| `media` | priori média, desvio 0,7, choques do presidente revisado |
| `media_outros_1_uf6` | linha Outros com desvio 1,0, choque inicial por UF de 6% |
| `media_p3` (**adotada**) | `media` com o viés da evidência parcial em 3% (o presidente usa 1,5%) |

## Antes da apuração

Sem pesquisa, a previsão erra em média **5,5 pontos**, com um intervalo de 90% de **22 pontos**. Ele cobre 91% das
46 eleições, então a faixa é honesta, mas larga demais para ser útil. O erro vem quase todo da linha Outros. No
presidente, a pesquisa da véspera derrubou o erro de 4,4 para 1,1 ponto ([calibracao-priori.md](calibracao-priori.md)).
Por isso registrei as pesquisas de governador da véspera (ver a seção seguinte).

## Com a pesquisa da véspera

`dados/pesquisas/governador_t2.csv` traz a última pesquisa antes do 2º turno de 33 eleições: 2010 (Ibope), 2018
(Ibope) e 2022 (Ipec, ou Atlas quando não houve Ipec), cada uma com o link da reportagem. Para 2014 não achei uma
fonte com as pesquisas da véspera; fica para completar. Em RN 2018, a última pesquisa achada é de 17/10.

**As pesquisas de governador erram mais que as de presidente:** 3,2 pontos em média (desvio 3,9), contra ~1 ponto
no presidente. O maior erro foi SC 2018: o Ibope deu 59% a Comandante Moisés, que teve 71%.

Como no presidente, a linha Outros da priori é ajustada para que a previsão de antes da apuração bata com a
pesquisa (`priori.outros_pela_pesquisa`). Nas 33 eleições com pesquisa:

| Antes da apuração | Sem pesquisa (`media_p3`) | Com pesquisa (adotada) |
|---|---|---|
| Erro médio | 6,0 | 3,2 |
| Largura do intervalo de 90% | 23,1 | 14,8 |
| Cobertura 90% / 50% | 88% / 45% | 97% / 48% |
| CRPS | 4,25 | 2,20 |

A variante adotada (`pesquisa_o3_p3_antes2`) usa desvio 0,3 na linha Outros e choque por UF de 2% antes de abrir
(4% depois). Apertar também os outros parâmetros da matriz (desvio 0,3 em vez de 0,7) estreitava a faixa, mas
piorava a apuração: cobertura de 85% com 30% apurado e uma chamada errada (SE 2022).

**Durante a apuração a pesquisa não ajuda.** Nas mesmas 33 eleições, o CRPS com pesquisa fica 3% a 5% acima do sem
pesquisa entre 1% e 30% apurado (1,66 contra 1,59 com 10%), e a cobertura é parecida (89% a 98% contra 91% a 98%).
Quando os votos chegam, a linha Outros passa a ser estimada pelos dados, e a pesquisa deixa de pesar. A diferença
está dentro do ruído de 66 rejogos. Por isso fica uma configuração só: com pesquisa quando houver, sem pesquisa
quando não houver.

## Durante a apuração

Rejogo por município, 2 apurações sintéticas por eleição, com a ordem e o viés das primeiras seções de
`scripts/calibrar_priori.py`. Cobertura do intervalo de 90% (meta 90%):

| % apurado | `media` | `media_p3` (adotada) | Largura 90%, `media_p3` | Cobertura 50%, `media_p3` |
|---|---|---|---|---|
| 0 | 91% | 91% | 22,2 | 43% |
| 1 | 98% | 99% | 16,8 | 77% |
| 5 | 97% | 97% | 13,8 | 76% |
| 10 | 97% | 97% | 11,4 | 72% |
| 20 | 96% | 96% | 8,4 | 61% |
| 30 | 92% | 93% | 6,4 | 57% |
| 50 | 86% | 97% | 3,8 | 60% |
| 70 | 79% | 97% | 2,1 | 57% |
| 90 | 79% | 98% | 0,7 | 59% |

- **Com a configuração do presidente** (`media`), a faixa fica estreita demais da metade da apuração em diante:
  cobre só 79% com 70% apurado. As falhas se espalham por UFs e anos.
- **O motivo:** no presidente, o viés das primeiras seções de cada cidade se dilui entre 27 UFs; numa UF só, ele
  vale para a eleição inteira. Dobrar o choque da evidência parcial (1,5% → 3%) leva a cobertura para 93–99% em
  toda a apuração, com o mesmo erro e o CRPS quase igual (1,08 contra 1,06).
- **No começo a faixa é larga** (17 pontos com 1% apurado; o intervalo de 50% cobre ~77%). Isso também deve
  melhorar com a pesquisa.
- Nenhuma chamada errada (mais de 99% de chance para quem perdeu) na variante adotada.

Ressalva: o viés das primeiras seções no rejogo (desvio de 3% na margem) foi medido na noite de 2026 do presidente.
Não há retratos parciais de apurações de governador para conferir esse tamanho.

## Como usar

```python
from eleicoes.dados import historico as hist
from eleicoes.modelos import priori
base, nomes = hist.segundo_turno_governador(2022, "sp")
cfg = priori.config_governador(2026)                        # sem pesquisa: média dos 2º turnos de 2006–2022
cfg = priori.config_governador(2026, base, pesquisa_a=52)   # com a pesquisa da véspera (% de A nos válidos)
```

```bash
python scripts/governador.py --rodadas 2 --variantes media media_p3     # ~10 minutos por variante
```
