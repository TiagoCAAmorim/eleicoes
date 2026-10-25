# data/ibge_municipios.csv

Gerado por `scripts/baixar_ibge.py` (API SIDRA do IBGE). Uma linha por município; chave `cdi` (IBGE, 7 dígitos)
ou `cod_tse` (via `data/municipios.csv`). As 186 linhas `uf=zz` (exterior) e Boa Esperança do Norte (MT, criado
depois do Censo 2022) ficam sem indicadores.

| Coluna | Tabela SIDRA | Observação |
|---|---|---|
| pop_2022, area_km2, densidade | 4714 | Censo 2022 |
| pct_branca/preta/parda/amarela/indigena, pct_preta_parda | 9605 | autodeclaração, % da população residente |
| pct_rural | 9923 | % da população residente |
| indice_envelhecimento, idade_mediana, razao_sexo | 9515 | |
| escolarizacao_6_14 | 10139 | taxa de escolarização, 6 a 14 anos |
| analfabetismo_15mais | 10135 | % |
| anos_estudo_11mais | 10062 | média de anos de estudo |
| rendimento_medio, rendimento_mediano | 10280 | R$ mensais, ocupados de 14+ com rendimento do trabalho |
| nivel_ocupacao_10mais | 10268 | ocupados / pessoas de 10+; **substitui a desocupação**, que o Censo 2022 não publica por município |
| pct_catolica/evangelica/espirita/umbanda_candomble/sem_religiao | 10198 | % das pessoas de 15+ |
| filhos_por_mulher_12mais | 10078 | filhos tidos nascidos vivos / mulheres de 12+; **não é a taxa de fecundidade total** |
| pib_mil_reais_2023, pib_per_capita_2023 | 5938 | per capita = PIB 2023 / população do Censo 2022 |
| pct_vab_agro/industria/servicos/adm_publica_2021 | 5938 | % do valor adicionado bruto; 2021 é o último ano publicado. Cachoeira Dourada (GO) tem valores fora de 0–100 no dado original |

Fora do IBGE/SIDRA por município: mortalidade infantil e taxa de fecundidade total (DATASUS), desocupação.
