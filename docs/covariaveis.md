# Covariáveis municipais (etapa 3)

O roteiro previa testar se informações de cada município que o modelo não usa ajudariam a prever o 2º turno:
votação para deputado, prefeitos e reeleição. Código: `scripts/covariaveis.py`; saídas em
`resultados/covariaveis/`.

## O teste

O modelo prevê cada município pela matriz de transferência do seu grupo (UF × porte) aplicada ao 1º turno do
município. Uma covariável só ajuda se explicar o que sobra, ou seja, o quanto cada município se afasta da matriz
do seu grupo.

Para cada 2º turno de 2006 a 2022:

1. Ajustei o modelo com a apuração completa (priori daquele ano, `tau` 0,15).
2. Calculei o resíduo de cada município: a fração de A nos válidos real menos a prevista pela matriz do grupo, em
   logit.
3. Fiz a regressão do resíduo nas covariáveis, dentro de cada grupo e ponderada pelo eleitorado.

Covariáveis testadas:

- **dep_A, dep_B**: fração dos votos válidos para deputado federal no 1º turno que foram para o partido de A (PT)
  e para o de B (PSDB até 2014, PSL em 2018, PL em 2022);
- **pref_A, pref_B**: prefeito eleito dois anos antes pelo partido de A ou de B (não há 2004 na base, então 2006
  fica sem);
- **comp_dif**: comparecimento do 2º turno menos o do 1º. Só serve de referência, porque só é conhecido depois que
  o município apura.

## Resultado

Fração do resíduo explicada (R²):

| Ano | Deputados | Prefeitos | Deputados + prefeitos | Comparecimento (referência) | Desvio do resíduo (logit) |
|---|---|---|---|---|---|
| 2006 | 0,9% | | | 1,1% | 0,095 |
| 2010 | 0,5% | 0,6% | 0,9% | 0,3% | 0,080 |
| 2014 | 0,2% | 1,7% | 1,7% | 1,1% | 0,103 |
| 2018 | 1,3% | 0,1% | 1,4% | 0,1% | 0,065 |
| 2022 | 3,3% | 0,2% | 3,5% | 2,5% | 0,030 |

Coeficientes (logit por unidade da covariável):

| | 2006 | 2010 | 2014 | 2018 | 2022 |
|---|---|---|---|---|---|
| dep_A | −0,08 | +0,03 | +0,02 | +0,06 | +0,03 |
| dep_B | +0,06 | +0,05 | +0,03 | −0,14 | −0,06 |
| pref_A | | −0,01 | −0,04 | −0,01 | 0,00 |
| pref_B | | +0,01 | 0,00 | +0,04 | +0,01 |

## Conclusão: não entram no modelo

- **Explicam muito pouco.** No melhor caso (2022), deputados e prefeitos juntos explicam 3,5% do resíduo, e o
  desvio do resíduo não muda na terceira casa decimal.
- **Os sinais trocam de ano para ano.** dep_B é positivo até 2014 e negativo em 2018 e 2022, então não haveria
  como fixar o coeficiente antes da eleição.
- **Os efeitos são pequenos.** Um município com 10 pontos a mais de PT para deputado se afasta da matriz em
  0,003 logit, menos de 0,1 ponto.

A razão é que o 1º turno de cada município já carrega quase tudo que essas variáveis trazem. A votação de A e B no
1º turno é, ela mesma, a melhor medida da força de cada lado no município.

**Reeleição.** A reeleição do presidente (Lula 2006, Dilma 2014) vale para o país todo. Ela não distingue um
município de outro, então só poderia entrar na priori nacional. Desde a etapa 3 a priori nacional vem da pesquisa
da véspera ([calibracao-priori.md](calibracao-priori.md)), que já reflete esse efeito.

Reproduzir: `python scripts/covariaveis.py` (cerca de 5 minutos).
