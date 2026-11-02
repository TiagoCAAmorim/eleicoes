# Teste de estresse com apurações sintéticas (etapa 4, parte 1)

Em vez de ordens de apuração fixas (como a "adversa", que ordenava as seções pelo próprio voto), o teste agora
sorteia **muitas eleições e muitas apurações plausíveis** e mede se o intervalo de 90% contém o resultado ~90%
das vezes em cada momento da apuração. Código: `eleicoes/modelos/estresse.py` e `scripts/estresse.py`.

## Como uma apuração sintética é sorteada

Base: 2º turno de 2022 por seção (472 mil seções) e 1º turno por município.

1. **Resultado de cada cidade.** Parte da margem mais provável (previsão da priori para a cidade) e soma, na
   escala logit da fração de A nos válidos:
   - desvio nacional (desvio-padrão 0,12, ~3 pontos);
   - desvio por região (0,02) e por UF (0,03);
   - desvio da cidade, sorteado entre os desvios reais de 2022 de cidades do mesmo porte (caudas reais).
   Cada seção mantém o desvio real que teve em relação à sua cidade; comparecimento e brancos/nulos ficam como em
   2022.
2. **Ordem de apuração.** Base parecida com a real (regiões e capitais com atraso, zonas em blocos), mais dois
   vieses sorteados:
   - **entre cidades (beta)**: cidades previstas para um lado apuram mais rápido (velocidade x exp(beta·z));
   - **dentro das cidades (gama)**: as seções mais para um lado que a própria cidade apuram antes.

## Calibração com a apuração real de 2026

`python scripts/estresse.py --calibrar` mede na noite de 2026:

| % apurado | Cidades pró-Flávio / pró-Lula (velocidade) | Parciais das cidades − final da cidade |
|---|---|---|
| 1,6% | 1,09 | +0,96 pt |
| 5,7% | 1,30 | +0,53 pt |
| 10% | 1,31 | +0,17 pt |
| 29% | 1,27 | −0,30 pt |
| 70% | 1,04 | −0,19 pt |

- A base da ordem sem viés (beta = 0) reproduz a razão de ~1,3; beta é sorteado com desvio 0,10 (razão entre 0,8
  e 2,3).
- Gama é sorteado com desvio 0,05, o que dá parciais 1 a 2 pontos fora da cidade no começo, como em 2026. No
  gerador o viés some mais devagar que em 2026 (ainda ~0,5 ponto com 30%), então o teste é um pouco pessimista.
- Comparando a priori usada ao vivo com o resultado de 2026, o erro foi quase todo nacional (+0,15 logit); região,
  porte e UF somaram só 0,01 a 0,02. Por isso os desvios regionais do gerador são pequenos.

## Resultado (32 apurações sintéticas, 10 momentos cada)

![cobertura](../resultados/estresse/estresse.png)

| Variante | Cobertura 90% (meta 90%) | Cobertura 50% (meta 50%) | Largura média 90% | CRPS | Chamadas erradas (>99% no perdedor) |
|---|---|---|---|---|---|
| ao_vivo (curva até 25%) | 66% | 31% | 3,0 pt | 0,76 | 7 |
| sem_choques (sem curva) | 58% | 29% | 2,0 | 0,57 | 8 |
| so_nacional (sem curva + choque nacional 1%) | 63% | 33% | 2,3 | 0,56 | 5 |
| parcial_leve (metade dos choques novos) | 81% | 42% | 2,8 | 0,55 | 0 |
| **revisado (padrão atual)** | **95%** | **57%** | 3,7 | 0,56 | **0** |

Por intensidade do viés dentro das cidades (cobertura de 90%, momentos com votos apurados):

| abs(gama) | ao_vivo | sem_choques | revisado |
|---|---|---|---|
| até 0,03 | 84% | 91% | 100% |
| 0,03 a 0,06 (nível de 2026) | 55% | 51% | 100% |
| acima de 0,06 | 47% | 3% | 83% |

## Conclusões

1. **O que derruba o modelo é o viés dentro das cidades**, não o viés entre cidades: a ordem por cidade
   (beta) é absorvida porque o modelo já condiciona no 1º turno de cada município.
2. **O modelo revisado está calibrado** nessas apurações plausíveis: cobre 95% (meta 90%) e o intervalo de 50%
   cobre 57% (meta 50%), sem nenhuma chamada errada. Os choques da etapa 3 ficam como estão.
3. Sem os choques novos, o modelo errou o vencedor com mais de 99% de chance em 8 dos 320 momentos.
4. Antes de abrir as urnas a cobertura é 88%: o centro vem da priori, e o desvio nacional sorteado (3 pontos) é
   do tamanho do que aconteceu em 2026. Melhorar isso é trabalho da priori (etapas 2 e 3).

Reproduzir: `python scripts/estresse.py --rodadas 32` (~1 h com 4 núcleos). `--beta` e `--gama` fixam os vieses.

# Parte 2: o mesmo teste com 2010, 2014 e 2018

O gerador agora aceita outras eleições (`--ano`). Para cada uma:

- **Seções:** o 2º turno presidencial por seção, baixado do TSE pelo workflow **secoes** (`scripts/tse_secoes.py`,
  arquivo `dados/historico/<ano>/secoes_presidente_t2.csv.gz`). Os totais batem com o resultado oficial. De 2006 a
  2014, cerca de 10% das seções não casam com o arquivo de comparecimento do TSE; nelas, o comparecimento é a soma
  dos votos e os aptos seguem a taxa da cidade.
- **Priori:** `calibrado_cauteloso` usa a priori calibrada daquele ano, só com o que se sabia na véspera: a média
  das matrizes das eleições anteriores e a linha Outros pela pesquisa ([calibracao-priori.md](calibracao-priori.md)).
  `revisado` usa a matriz da eleição anterior, como o modelo fazia antes da calibração.
- **Eleições sintéticas:** centradas na previsão da priori calibrada, com os mesmos desvios e vieses de ordem da
  parte 1. Os desvios das cidades vêm do próprio ano. 2006 fica de fora porque não há eleição anterior na base
  para montar a priori.

Resultado com 16 apurações sintéticas por ano (`resultados/estresse-historico/<ano>/`):

| % apurado | 2010: cobertura 90%, revisado / calibrado | 2014 | 2018 | Largura 90% (média dos 3 anos), revisado / calibrado |
|---|---|---|---|---|
| 0 | 0% / 81% | 100% / 94% | 94% / 94% | 15,1 / 8,1 |
| 1 | 100% / 94% | 94% / 94% | 100% / 100% | 8,1 / 6,5 |
| 3 | 100% / 94% | 94% / 94% | 100% / 100% | 6,9 / 5,8 |
| 5 | 100% / 94% | 94% / 94% | 100% / 100% | 6,3 / 5,3 |
| 10 | 100% / 94% | 94% / 88% | 100% / 100% | 5,1 / 4,5 |
| 20 | 94% / 94% | 88% / 88% | 94% / 100% | 3,8 / 3,4 |
| 30 | 94% / 94% | 88% / 81% | 94% / 94% | 3,0 / 2,7 |
| 50 | 94% / 88% | 81% / 81% | 94% / 94% | 1,9 / 1,8 |
| 70 | 81% / 81% | 81% / 81% | 94% / 94% | 1,1 / 1,0 |
| 90 | 81% / 81% | 81% / 81% | 81% / 81% | 0,35 / 0,34 |

| Ano | Variante | Cobertura 90% | Cobertura 50% | Largura média 90% | CRPS | Chamadas erradas |
|---|---|---|---|---|---|---|
| 2010 | revisado | 84% | 59% | 4,9 | 1,41 | 1 |
| 2010 | **calibrado cauteloso** | **89%** | **56%** | **3,8** | **0,60** | 1 |
| 2014 | revisado | 89% | 67% | 5,3 | 0,66 | 0 |
| 2014 | **calibrado cauteloso** | **88%** | **56%** | **4,0** | **0,64** | 0 |
| 2018 | revisado | 95% | 61% | 5,4 | 0,73 | 0 |
| 2018 | **calibrado cauteloso** | **96%** | **64%** | **4,0** | **0,53** | 0 |

Conclusões:

1. **A variante adotada (calibrado cauteloso) continua calibrada em outras eleições:** cobre 88% a 96% (meta 90%) e
   o intervalo de 50% cobre 56% a 64% (meta 50%), com faixa 25% mais estreita e CRPS menor que o revisado nos três
   anos.
2. **O ganho vem quase todo de antes da apuração e do começo.** Em 2010, a matriz de 2006 deixava o revisado
   fora do alvo antes de abrir (0% de cobertura, CRPS 9,7). Com 1% apurado as duas variantes já se parecem.
3. **A única chamada errada** (nas duas variantes) foi antes de abrir, numa rodada de 2010 em que o gerador
   sorteou Dilma com 49,8%, 6 pontos abaixo da pesquisa. O gerador sorteia o desvio nacional com ~3 pontos de
   desvio-padrão, o tamanho do erro de uma priori sem pesquisa. O erro histórico das pesquisas na véspera foi
   de ~1 ponto, então esse cenário é mais extremo que o que se viu de 2010 a 2026.
4. **Ponto fraco, igual em 2022: o fim da apuração.** Com 70% a 90% apurado, a cobertura cai para ~81% em todos os
   anos e variantes. Nessa fase a faixa tem menos de 1 ponto. O que falha é o viés de ordem dentro das cidades
   (gama), que no gerador demora mais a sumir do que sumiu em 2026. Fica como ponto a investigar: um choque
   residual mínimo no fim, ou um gerador com o viés sumindo como em 2026.

Reproduzir (cerca de 10 minutos por ano com 4 núcleos):

```bash
python scripts/estresse.py --ano 2018 --rodadas 16 --variantes revisado calibrado_cauteloso --saida resultados/estresse-historico/2018
```
