# Calibração da priori com 2006–2026 (etapa 3)

Antes da apuração, o modelo do 2º turno só tem a **priori**: uma matriz de transferência de votos do 1º para o
2º turno, mais a incerteza dela. Em 2026 a previsão de antes da apuração errou 3,4 pontos (48,4% contra 51,8%).
Esta etapa usa a base histórica do TSE ([base-historica.md](base-historica.md)) para medir quanto a priori erra e
calibrar a faixa. Códigos: `scripts/calibrar_priori.py` (as comparações) e `eleicoes/modelos/priori.py` (a priori
calibrada). As saídas ficam em `resultados/calibracao-priori/`.

Em todas as eleições, A é o candidato do PT, que esteve em todos os 2º turnos desde 2006: Lula, Dilma, Dilma, Haddad,
Lula e Lula.

## As matrizes de cada eleição

Para cada 2º turno, o modelo foi ajustado com a apuração completa. As matrizes estão em
`dados/priori/presidente_<ano>.json`. A linha que mais muda é a dos eleitores dos **outros candidatos**:

| Ano | 2º turno | A nos válidos | Outros (% do eleitorado) | Outros → A | Outros → B |
|---|---|---|---|---|---|
| 2006 | Lula × Alckmin | 60,8 | 7 | 87% | 12% |
| 2010 | Dilma × Serra | 56,1 | 15 | 42% | 56% |
| 2014 | Dilma × Aécio | 51,6 | 18 | 40% | 60% |
| 2018 | Haddad × Bolsonaro | 44,9 | 18 | 58% | 31% |
| 2022 | Lula × Bolsonaro | 50,9 | 6 | 22% | 77% |
| 2026 | Lula × Flávio | 51,8 | 15 | 63% | 37% |

Isso faz sentido: os "outros" de cada eleição são candidatos diferentes. Em 2010 e 2014 o maior deles foi Marina,
em 2018 Ciro, e em 2022 Ciro e Simone Tebet. Usar a linha Outros da eleição anterior é, na prática, um chute.

A estimativa com a apuração completa é ecológica: o modelo só vê totais por município. Alguns parâmetros
encostam nos limites (troca A↔B perto de zero, abstenção de 2026 indo 8% para A). Isso não atrapalha a previsão,
mas cada número isolado não deve ser lido como a migração real de eleitores.

## Quanto a previsão de antes da apuração erra

Para cada eleição de 2010 a 2026, rodei o modelo **sem nenhum voto apurado**, com prioris montadas de jeitos
diferentes, e comparei com o resultado. Em pontos de A nos votos válidos:

| Ano | Real | Matriz da eleição anterior | Média das anteriores, Outros pela pesquisa (**calibrada**) |
|---|---|---|---|
| 2010 | 56,1 | 66,7 (59,9 – 72,0) | 55,8 (52,2 – 59,7) |
| 2014 | 51,6 | 52,1 (44,1 – 60,7) | 52,5 (48,2 – 56,7) |
| 2018 | 44,9 | 40,5 (32,5 – 49,0) | 45,3 (40,9 – 49,3) |
| 2022 | 50,9 | 53,0 (49,2 – 56,6) | 51,9 (49,6 – 54,3) |
| 2026 | 51,8 | 47,2 (43,8 – 50,7) | 49,0 (46,6 – 51,2) |
| **Erro médio (absoluto)** | | **4,4** | **1,1** |
| **Largura média do intervalo de 90%** | | **11,9** | **6,7** |
| **Cobertura nas UFs** | | 87% | 96% |

Entre parênteses está o intervalo de 90%. A coluna "matriz da eleição anterior" é o modelo revisado como está hoje,
mas sem pesquisa. Em 2026 ao vivo, a linha Outros veio do cruzamento da Quaest (voto no 2º turno por voto no 1º),
e a previsão foi 48,4%.

### O que muda na priori calibrada

1. **Média das eleições anteriores**, e não só a última. A média é feita grupo a grupo (Brasil, região, UF, UF ×
   porte), na escala logit. Ela suaviza as estimativas que encostam nos limites.
2. **Linha Outros pela pesquisa.** A linha Outros é ajustada para que a previsão de antes da apuração bata com a
   última pesquisa em votos válidos (Datafolha e Ibope da véspera, média dos dois quando há os dois). As pesquisas
   estão em `dados/pesquisas/presidente_t2.csv`, com o link da reportagem de cada uma. O ajuste desloca Outros → A
   e Outros → B em sentidos opostos, a partir da linha da priori, até a previsão nacional ser a da pesquisa.
3. **Incerteza recalibrada:**
   - **linha Outros com desvio 0,3** (escala logit), que representa o erro das pesquisas;
   - **hierarquia mais apertada** (`tau` de 0,5 para 0,15): cada UF e porte de cidade se desvia do grupo de cima
     quase como na média histórica;
   - **choque inicial por UF de 2%** (era 4%).

   Com esses valores, o erro dividido pela meia-largura do intervalo ("z") tem desvio próximo de 1: 0,96 no Brasil
   e 0,79 nas UFs. Ou seja, a faixa tem o tamanho dos erros que de fato aconteceram.

### O limite: o erro das pesquisas

Com a linha Outros certa (como se a pesquisa acertasse em cheio), o erro no Brasil cai para cerca de 1 ponto, e
o que sobra vem de abstenção e brancos/nulos. Com a pesquisa real, o erro da previsão é praticamente o erro da
pesquisa:

| Ano | Datafolha (A nos válidos) | Real | Erro da pesquisa |
|---|---|---|---|
| 2010 | 55 | 56,1 | −1,1 |
| 2014 | 52 | 51,6 | +0,4 |
| 2018 | 45 | 44,9 | +0,1 |
| 2022 | 52 | 50,9 | +1,1 |
| 2026 | 49 | 51,8 | −2,8 |

Em 2026 o Datafolha da véspera deu Flávio 51% × Lula 49%. Com a priori calibrada, a previsão de antes da apuração
seria 49,0% (46,6 – 51,2): melhor que os 48,4% ao vivo, mas ainda fora do intervalo. É 1 erro em 5 eleições,
compatível com um intervalo de 90%. Uma faixa que cobrisse 2026 com folga teria que ser bem mais larga em todos os
outros anos.

## Efeito durante a apuração

A hierarquia mais apertada e o choque inicial menor também valem durante a apuração. Por isso testei se a faixa
continua honesta com votos chegando.

**Noite real de 2026** (rejogo dos retratos, um a cada dois; `resultados/calibracao-priori/rejogo_2026_resumo.csv`):

| | Revisado | Calibrado | Calibrado cauteloso |
|---|---|---|---|
| Antes de abrir | 48,4 (44,9 – 51,8) | 49,0 (46,6 – 51,2) | 49,0 (46,6 – 51,2) |
| Com 1,6% apurado | | 53,0 (50,8 – 55,1), 99% | 53,0 (50,4 – 55,5), 97% |
| CRPS Brasil, média da noite (menor é melhor) | 0,34 | 0,30 | 0,31 |
| Largura média do intervalo de 90% no Brasil | 2,7 pontos | 2,1 pontos | 2,5 pontos |
| Cobertura 90% no Brasil | 100% | 96% (só erra antes de abrir) | 96% (só erra antes de abrir) |
| Cobertura 90% / 50% nas UFs | 96% / 80% | 95% / 73% | 97% / 78% |
| Chance > 99% a partir de | 56% apurado | 41% apurado | 48% apurado |

O intervalo de 50% das UFs, que cobria 80% (largo demais, ver [revisao-t2.md](revisao-t2.md)), chega mais perto
dos 50% que deveria. O ponto fraco é o comecinho: com 1,6% apurado, a previsão foi a 53,0% (50,8 – 55,1), com 99%
de chance para Lula. Acertou o vencedor, mas com folga de só 1 ponto para o resultado. A variante **cautelosa** volta o choque inicial
por UF para 4% assim que a apuração começa (fica 2% só antes de abrir, quando a faixa já vem da pesquisa). Com
1,6% apurado, ela dá 97% de chance e intervalo até 50,4, e só passa de 99% com 48% apurado.

**2010 a 2018 por município** (2 apurações sintéticas por ano, ordem parecida com a real e viés sorteado nas
primeiras seções; `rejogo_municipios.csv`; a linha Outros aqui é a verdadeira, para isolar o efeito da hierarquia):

| % apurado | Largura 90%, tau 0,5 | Largura 90%, tau 0,15 | Cobertura Brasil (ambos) | Cobertura UFs, tau 0,15 |
|---|---|---|---|---|
| até 5% | 7,6 | 5,2 | 100% | 99% |
| 5 a 15% | 5,7 | 4,0 | 100% | 99% |
| 15 a 30% | 4,0 | 3,0 | 100% | 98% |
| 30 a 60% | 2,3 | 1,8 | 100% | 99% |
| acima de 60% | 0,7 | 0,6 | 100% | 99% |

O erro médio é o mesmo nas duas versões: a hierarquia mais apertada só estreita a faixa. Com 100% de cobertura,
a faixa ainda tem folga. Uma ressalva: aqui cada município apura proporcionalmente, então este teste é mais fácil
que a realidade (dentro das cidades, a ordem das seções importa; ver [estresse.md](estresse.md)).

**Teste de estresse** (16 apurações sintéticas com viés dentro das cidades, gerador de [estresse.md](estresse.md)):

Rodado com `python scripts/estresse.py --rodadas 16 --variantes revisado calibrado --saida resultados/estresse-calibrado` (e depois `--variantes calibrado_cauteloso`).
O resumo está em `resultados/calibracao-priori/estresse_resumo.csv`. A variante `calibrado` usa a hierarquia e os
choques calibrados, com a mesma priori de 2022 do `revisado`, para isolar o efeito deles na apuração.

| % apurado | Cobertura 90%: revisado / calibrado / cauteloso | Largura 90%: revisado / calibrado / cauteloso | CRPS: revisado / calibrado / cauteloso |
|---|---|---|---|
| 0 | 88% / 62% / 62% | 7,2 / 4,3 / 4,3 | 1,64 / 1,82 / 1,82 |
| 1 | 94% / 88% / 88% | 6,2 / 4,7 / 5,5 | 0,80 / 0,85 / 0,85 |
| 3 | 100% / 88% / 94% | 5,5 / 4,3 / 4,9 | 0,68 / 0,72 / 0,73 |
| 5 | 94% / 94% / 94% | 5,0 / 4,0 / 4,5 | 0,64 / 0,67 / 0,68 |
| 10 | 94% / 94% / 94% | 4,2 / 3,5 / 3,8 | 0,54 / 0,56 / 0,57 |
| 20 | 94% / 94% / 94% | 3,2 / 2,8 / 3,0 | 0,42 / 0,43 / 0,43 |
| 30 a 70 | 94% / 94% / 94% | 2,5 a 1,0 (as três) | 0,33 a 0,14 / 0,35 a 0,14 / 0,35 a 0,14 |
| 90 | 81% / 81% / 81% | 0,3 (as três) | 0,06 (as três) |

Nenhuma chamada errada em nenhuma das três. Como ler:

- **Antes de abrir (0%)**, a comparação não vale para a priori calibrada. O gerador sorteia um desvio nacional de
  ~3 pontos em torno da priori, o tamanho do erro de uma priori **sem pesquisa**. Com a linha Outros pela pesquisa,
  o erro histórico foi de 1,1 ponto (tabela acima), e é para isso que a faixa calibrada foi feita.
- **De 5% em diante**, a cobertura é a mesma, e a faixa calibrada é um pouco mais estreita.
- **De 1% a 3%**, a calibrada cobre 88% (2 falhas em 16), contra 94–100% do revisado. Com 16 rodadas, a diferença
  ainda está dentro do ruído (1 falha a mais). Mas o mesmo padrão apareceu em 2026 (99% de chance já com 1,6%), então
  este é o ponto a vigiar. A **cautelosa** recupera parte disso: 94% com 3%, com faixa entre as outras duas.
- O intervalo de 50% cobre 50–69% na calibrada, contra 62–75% no revisado: mais perto do ideal (50%).

**Escolha.** A página revisada de 2026 (`resultados/2026-presidente-revisado`) usa a variante **calibrado
cauteloso**: priori média com linha Outros pela pesquisa, `tau` 0,15, desvio 0,3 na linha Outros, choque inicial por
UF de 2% antes de abrir e 4% depois. Ela gera com `python scripts/rejogar_paginas_2026.py` (é o padrão).

## Como usar

```python
from eleicoes.modelos import priori
cfg = priori.config_calibrada(base, pesquisa_a=49.0)   # base: municípios com 1º turno e eleitorado do 2º turno
```

```bash
python scripts/calibrar_priori.py                    # matrizes de cada ano e comparação antes da apuração
python scripts/calibrar_priori.py --rejogo 2 --variante-rejogo mp_t015_ufi_002_o03   # + rejogo por município
python scripts/rejogar_2026.py --variantes revisado calibrado_hier calibrado calibrado_cauteloso
```

## Pontos em aberto

- **Pesquisas.** Por enquanto só há o resultado final da pesquisa (votos válidos). O cruzamento por voto no 1º turno,
  quando a reportagem trouxer, daria a linha Outros direto, sem depender da matriz média.
- **Só presidente.** Governador e senador (etapa 5) usam a mesma base. Lá a priori precisa de outro desenho, porque
  os partidos mudam de UF para UF.
- **Matriz v2.** Testada com 2006–2026 em [matriz-v2.md](matriz-v2.md): ganha por pouco nos rejogos, perde no teste de
  estresse e não foi adotada.
