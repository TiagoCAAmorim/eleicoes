# Previsão do 1º turno (etapa 6)

No 1º turno a pergunta muda. Não basta saber quem tem mais votos: é preciso saber **se alguém passa de 50% dos
válidos** (e leva no 1º turno) e, se não, **quem vai ao 2º turno**. Com vários candidatos, o mesmo modelo serve
também para **senador** (maioria simples, uma ou duas vagas) e para o **1º turno de prefeito**. Código:

- `eleicoes/modelos/primeiro_turno.py` (o modelo);
- `eleicoes/dados/historico.py` (`primeiro_turno`: a base por município com a eleição de referência);
- `scripts/primeiro_turno.py` (os rejogos);
- `scripts/tse_secoes_prefeito_t1.py` e o workflow `secoes_prefeito_t1` (prefeito por seção).

Saídas em `resultados/primeiro-turno/<cargo>/`.

## O modelo

O modelo do 2º turno leva os votos do 1º turno de cada município para o 2º por uma matriz de transferência. No 1º
turno não há turno anterior na mesma eleição. A matriz passa a partir de uma **eleição de referência**: o 1º turno
presidencial de quatro anos antes (para presidente, governador e senador).

| | Linhas (referência, por município) | Colunas (agora) |
|---|---|---|
| Categorias | os 3 partidos mais votados na referência, demais candidatos, branco/nulo, abstenção | os candidatos nomeados, demais candidatos, branco/nulo, abstenção |
| Exemplo 2022 | PSL, PT e PDT de 2018 | Lula, Bolsonaro, Tebet |

Cada linha da matriz diz para onde foram, em média, os eleitores daquela categoria. A geografia da referência
carrega o padrão de cada candidato para os municípios que ainda não chegaram. Onde o PT foi forte em 2018, Lula
tende a ser forte em 2022, mesmo antes de chegar um voto dali. A matriz é estimada nos municípios já apurados, com a
mesma hierarquia do 2º turno (Brasil, região, UF, UF × porte).

São chamados de **candidatos nomeados** os que têm pelo menos 5% dos válidos (no mínimo 3, no máximo 5). Os outros
entram somados em "demais". Ao vivo, a escolha vem das pesquisas.

### Antes da apuração: a pesquisa

A matriz de partida divide cada linha como a pesquisa da véspera divide os votos. Ela dá um bônus para o candidato
do mesmo partido de uma linha, para branco/nulo → branco/nulo e para abstenção → abstenção. Cada célula pode se
afastar da partida, mas o **total nacional de cada candidato fica preso à pesquisa**, com desvio de 4,5 pontos.
Esse é o erro das pesquisas Datafolha da véspera do 1º turno presidencial (próxima seção).

**O peso da pesquisa cai à medida que os votos chegam.** O desvio vale 4,5 × (1 + % apurado), então com 10% apurado
já é 11 vezes maior. Sem isso, as células ainda sem dados (o Nordeste no começo da noite) se ajustavam para manter
o total da pesquisa.

### A incerteza

A incerteza segue o modelo do 2º turno, com quatro mudanças:

- **Os choques valem no logaritmo da votação de cada candidato** no que falta apurar: nacional (1,5%), por UF (3%),
  por UF no começo (5% × fração da UF ainda não apurada) e da evidência parcial (4%).
- **Os grupos sem dados erram juntos.** Os desvios de cada grupo em relação ao Brasil têm correlação de 0,25 no
  sorteio. Antes de abrir as urnas a correlação é zero: a incerteza do total vem só da pesquisa.
- **A hierarquia é mais solta** (tau 0,7 contra 0,15 no 2º turno). Os candidatos do 1º turno mudam mais de região
  para região do que a troca entre dois candidatos de um turno para o outro.
- **A média dos sorteios fica na previsão central.** O sorteio em escala logit puxava as frações para perto da
  uniforme e tirava ~3 pontos do líder antes da apuração. Agora os sorteios são reescalados, unidade a unidade,
  para que a média seja a previsão com os parâmetros médios.

Numa UF só (governador, senador) não há choque nacional separado. Um **grupo grande ainda sem votos** (em geral a
capital) ganha um desvio extra de 0,2 × a fração do grupo não apurada. O caso que motivou: no AM em 2018, o interior
chegou antes de Manaus, e Wilson Lima, forte na capital, aparecia com 12% até 30% apurado (teve 34%).

### O que sai

Para cada candidato nomeado, o modelo dá:

- a votação (% dos válidos), com intervalos de 50% e 90%;
- a chance de ser o 1º colocado;
- a chance de ficar entre os 2 primeiros (de ir ao 2º turno);
- a chance de vencer no 1º turno (passar de 50%). No senador, a chance de ficar entre os eleitos (1 ou 2 vagas,
  maioria simples).

No geral, o modelo também dá a chance de haver 2º turno.

## As pesquisas da véspera

`dados/pesquisas/presidente_t1.csv` traz a última Datafolha antes do 1º turno presidencial de 2010 a 2026, com o
link da reportagem. Em 2010 a reportagem dá os votos totais; os válidos foram calculados tirando brancos, nulos e
indecisos.

| Ano | 1º colocado: pesquisa → resultado | 2º colocado: pesquisa → resultado |
|---|---|---|
| 2010 | Dilma 50,5 → 46,9 | Serra 31,2 → 32,6 |
| 2014 | Dilma 44 → 41,6 | Aécio 26 → 33,5 |
| 2018 | Bolsonaro 40 → 46,0 | Haddad 25 → 29,3 |
| 2022 | Lula 50 → 48,4 | Bolsonaro 36 → 43,2 |
| 2026 | Flávio 42 → 47,0 | Lula 45 → 45,2 |

O erro médio (raiz da média dos quadrados) é de **4,6 pontos**, muito maior que o ~1 ponto das pesquisas de 2º turno.
E tem sinal: o candidato da direita foi subestimado em todos os anos desde 2014, por 5 a 7,5 pontos. Não corrigi esse
viés, porque cinco eleições é pouco para separar um padrão do acaso. O desvio de 4,5 pontos da priori vem desse erro.

## Rejogos

A ordem de chegada é a sintética de `scripts/calibrar_priori.py`: Sul primeiro, Nordeste e Norte por último, e as
cidades grandes demoram mais. Em cada rejogo, as primeiras seções de cada cidade têm a votação de cada candidato
multiplicada por um fator sorteado (desvio de 4,5% no log, ~3% na margem, como no 2º turno), que some quando a
cidade termina. **Não há retratos parciais do 1º turno** além de 2026, e o de 2026 só tem Lula, Flávio e os demais
somados.

Para governador, senador e prefeito não registrei pesquisas. A previsão de antes da apuração parte de uma **pesquisa
sintética**: o resultado verdadeiro de cada candidato mais um erro sorteado com desvio de 3 pontos. Ela só mede se a
faixa é honesta para esse erro.

Métricas: erro, cobertura dos intervalos de 50% e 90% e CRPS da votação dos **3 primeiros colocados reais**. Para
os eventos (vencer no 1º turno, ficar entre os 2 primeiros, ser o 1º), o Brier e as **chamadas erradas** (mais de
99% de chance para o que não aconteceu, ou menos de 1% para o que aconteceu).

### Presidente (2010–2026, pesquisas reais)

Cinco eleições, 3 rejogos cada, com os 3 primeiros colocados (42 previsões por ponto). Meta de cobertura: 90% e 50%.

| % apurado | Cobertura 90% | Cobertura 50% | Largura 90% (pontos) | CRPS | Erro médio |
|---|---|---|---|---|---|
| 0 | 79% | 29% | 10,3 | 2,33 | 3,3 |
| 1 | 100% | 55% | 6,9 | 0,93 | 1,3 |
| 5 | 95% | 40% | 5,6 | 0,87 | 1,2 |
| 10 | 95% | 43% | 4,9 | 0,78 | 1,1 |
| 20 | 95% | 45% | 3,9 | 0,63 | 0,9 |
| 30 | 95% | 52% | 3,1 | 0,52 | 0,8 |
| 50 | 93% | 43% | 2,0 | 0,33 | 0,5 |
| 70 | 95% | 38% | 1,2 | 0,19 | 0,3 |
| 90 | 98% | 48% | 0,4 | 0,06 | 0,1 |

- **Antes da apuração** o modelo é a pesquisa, e erra o que ela erra: a faixa de 90% não cobriu Aécio em 2014,
  Bolsonaro em 2018 e Bolsonaro em 2022.
- **Com 1% apurado**, o erro cai de 3,3 para 1,3 ponto, e a faixa cobre 93–100% até o fim.
- **Nenhuma chamada errada** em vencer no 1º turno, ir ao 2º turno ou ser o 1º colocado.

O caminho até a configuração adotada, nas mesmas eleições:

| Variante | O que muda | Cobertura 90% (1% → 90% apurado) | CRPS com 10% |
|---|---|---|---|
| inicial | hierarquia apertada (tau 0,15), choque parcial de 2%, sem correlação entre grupos | 48–57% | 1,08 |
| intermediária | tau 0,5, choque parcial de 4%, correlação 0,25 | 90–98% | 0,77 |
| **adotada** | tau 0,7 e média dos sorteios corrigida | **93–100%** | **0,78** |

Com a hierarquia apertada, a matriz aprendida no Sul (que chega primeiro) era aplicada ao Nordeste quase sem ajuste.
O erro mudava de sinal conforme o ano: Dilma superestimada em 2010, Lula subestimado em 2022 e 2026. Soltar a
hierarquia e fazer os grupos sem dados errarem juntos resolveu.

**A chance de haver 2º turno** (todas as cinco eleições tiveram 2º turno), média dos rejogos:

| % apurado | 0 | 1 | 10 | 20 | 30 | 50 |
|---|---|---|---|---|---|---|
| 2010 | 51% | 61% | 70% | 86% | 94% | 100% |
| 2014 | 97% | 100% | 100% | 100% | 100% | 100% |
| 2018 | 100% | 90% | 96% | 99% | 100% | 100% |
| 2022 | 55% | 75% | 84% | 89% | 92% | 98% |
| 2026 | 90% | 71% | 81% | 89% | 95% | 100% |

Em 2022, a pesquisa dava Lula com 50% dos válidos. O modelo começou com 45% de chance de vitória no 1º turno e só
passou de 99% de chance de 2º turno com mais de metade apurada. Em 2026, Flávio aparece como 1º colocado provável
(86%) desde 1% apurado, embora a pesquisa o desse atrás.

### Governador e senador (2010–2022, pesquisa sintética)

104 eleições de governador (fora o DF, que tem um município só) e 108 de senador (fora o DF), 2 rejogos cada.
Senador: em 2010 e 2018 são duas vagas; "eleito" é ficar entre os dois primeiros.

| % apurado | Governador: cobertura 90% | 50% | Largura 90% | CRPS | Senador: cobertura 90% | 50% | Largura 90% | CRPS |
|---|---|---|---|---|---|---|---|---|
| 0 | 97% | 87% | 26,5 | 2,37 | 97% | 89% | 26,2 | 2,39 |
| 1 | 95% | 74% | 16,6 | 1,89 | 98% | 78% | 17,0 | 1,80 |
| 5 | 95% | 72% | 14,2 | 1,68 | 98% | 79% | 14,5 | 1,57 |
| 10 | 95% | 72% | 12,5 | 1,48 | 98% | 80% | 12,7 | 1,38 |
| 30 | 94% | 70% | 7,7 | 1,00 | 98% | 76% | 7,8 | 0,87 |
| 50 | 94% | 65% | 4,3 | 0,57 | 97% | 73% | 4,4 | 0,50 |
| 70 | 95% | 66% | 2,1 | 0,27 | 97% | 71% | 2,1 | 0,25 |
| 90 | 94% | 58% | 0,5 | 0,08 | 95% | 60% | 0,5 | 0,07 |

- **A faixa é honesta, mas larga.** O intervalo de 50% cobre 60–80%, quando deveria cobrir 50%. Antes da apuração, a
  faixa de 26 pontos é larga demais para uma pesquisa com erro de 3 pontos. Os choques por UF valem cheios sobre a
  UF inteira ainda não apurada. Com pesquisas reais registradas, dá para apertar.
- **O desvio extra para grupos sem votos** (0,2) levou a cobertura do governador de 88–96% para 94–96%, ao custo de
  ~6% no CRPS.
- **Uma chamada errada** em 1.244 rejogos de governador: AM 2018. Num dos rejogos, Manaus chegou por último, e
  Wilson Lima ficou com menos de 1% de chance de ser o 1º até 30% apurado (ele teve 34% e ficou em 1º). Nenhuma no
  senador.
- **Vencer no 1º turno** (59 das 104 eleições de governador): quando o modelo dá entre 80% e 95%, o candidato venceu
  em 99,6% das vezes; entre 40% e 60%, em 24%. Perto de 50% o modelo exagera a chance de vitória; nas pontas, a
  subestima.

RESULTADOS_PREFEITO

## Como usar

```python
from eleicoes.dados import historico as hist
base, info = hist.primeiro_turno(2022, "governador", "sp")       # base com a referência (presidente 2018)
```

```bash
python scripts/primeiro_turno.py --cargo presidente --rodadas 3 --variantes adotada    # ~30 min (4 núcleos: --anos)
python scripts/primeiro_turno.py --cargo governador --rodadas 2 --variantes adotada    # ~15 min
python scripts/primeiro_turno.py --cargo senador --rodadas 2 --variantes adotada
python scripts/primeiro_turno.py --cargo prefeito --rodadas 1 --variantes adotada --vies-secoes 0.3
python scripts/primeiro_turno.py --juntar pasta1 pasta2 --saida junto                   # junta rodadas separadas
```

Para usar ao vivo, a função `prever` de `scripts/primeiro_turno.py` mostra a sequência: `preparar`,
`priori` (a pesquisa), `ajustar`, `simular` e `resumo`.
