# Base histórica do TSE (2006–2024)

Etapa 2 do [roteiro](roteiro.md). Votos por município de todos os cargos de 2006 a 2024, para calibrar a priori, as
covariáveis e o teste de estresse do modelo, e depois para os modelos de outros cargos.

## Como é gerada

`scripts/tse_historico.py` baixa os dados abertos do TSE (`cdn.tse.jus.br/estatistica/sead/odsele`). Como o
ambiente de desenvolvimento não acessa o TSE, ele roda no GitHub Actions, no workflow **historico**. Para usar o
workflow, dispare à mão, escolhendo os anos (vazio = todos), ou faça um push num branch `claude/**` que mude o script.
Cada ano roda em paralelo e salva `dados/historico/<ano>/` no próprio branch.

```bash
python scripts/tse_historico.py 2022 2018     # localmente, se tiver acesso ao TSE
```

Arquivos do TSE usados:

| Arquivo | Para quê |
|---|---|
| `votacao_candidato_munzona` | votos por candidato (presidente, governador, senador, prefeito) |
| `votacao_partido_munzona` | votos por partido (deputados e vereador), nominais e de legenda |
| `detalhe_votacao_munzona` | aptos, comparecimento, abstenções, brancos, nulos e válidos |
| `consulta_cand` (+ `consulta_cand_complementar` a partir de 2014) | partido, coligação, federação, reeleição, situação |

De cada zip é lido só o arquivo `_BRASIL`, que tem o país inteiro. Os arquivos por UF e o `_BR` repetiriam os mesmos
votos. Ficam só as eleições ordinárias, sem as suplementares. O município é identificado pelo código do TSE, que é
estável entre os anos.

## O que sai em `dados/historico/<ano>/`

| Arquivo | Conteúdo |
|---|---|
| `votos_mun.csv.gz` | turno, cargo, UF, município, votável (candidato nos majoritários, partido nos proporcionais) e votos |
| `comparecimento_mun.csv.gz` | aptos, comparecimento, abstenções, brancos, nulos, nominais, legenda e válidos por município, cargo e turno |
| `candidatos.csv.gz` | candidatos majoritários: partido, coligação, federação, reeleição, situação no turno |
| `colunas.json` | arquivos lidos de cada zip e colunas encontradas (o formato do TSE mudou ao longo dos anos) |
| `resumo.json` | totais do país por cargo e turno, para conferência |

Cuidados:
- **Senador em 2010 e 2018**: eram 2 vagas e cada eleitor votava duas vezes, então os válidos somam cerca do dobro do
  comparecimento.
- **Exterior**: só vota para presidente, por isso o presidente tem de 77 (2006) a 181 (2010 e 2022) "municípios" a mais que os
  outros cargos.
- O 2º turno de governador e prefeito só existe onde houve.

## Conferência

O 2º turno presidencial bate com o resultado oficial em todos os anos (% dos válidos do vencedor):

| Ano | Vencedor | Base | Oficial |
|---|---|---|---|
| 2006 | Lula | 60,83 | 60,83 |
| 2010 | Dilma | 56,05 | 56,05 |
| 2014 | Dilma | 51,64 | 51,64 |
| 2018 | Bolsonaro | 55,13 | 55,13 |
| 2022 | Lula | 50,90 | 50,90 |

Outras conferências: governador de SP 2022, 2º turno, Tarcísio 55,27%; prefeito de SP 2024, 2º turno, Nunes
59,35%. O eleitorado dos anos municipais vai de 128,8 milhões (2008) a 155,9 milhões (2024).
