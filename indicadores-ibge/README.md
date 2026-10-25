# Indicadores municipais do IBGE

Base com uma linha por município (5.570 + código TSE 5.571º, mais 186 linhas do exterior `uf=zz` sem dados),
para cruzar com a votação e estimar a importância de cada indicador (ex.: Gradient Boosting).

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `ibge_municipios.csv` | A base (UTF-8, vírgula, ponto decimal). Chaves: `cdi` (IBGE, 7 dígitos) e `cod_tse` (texto, 5 dígitos) |
| `dicionario.md` | Cada coluna, a tabela SIDRA de origem e as ressalvas |
| `fontes.json` | Fonte legível por máquina: API, tabelas, variáveis, períodos, data do download |
| `baixar_ibge.py` | Regenera a base: `python3 indicadores-ibge/baixar_ibge.py` (`--sem-cache` força novo download) |
| `cache/` | Respostas brutas da API (ignorado pelo git) |

## Fonte

IBGE, Censo Demográfico 2022 e PIB dos Municípios, via API SIDRA (`apisidra.ibge.gov.br`). Baixado em 2026-10-25.
A página https://www.ibge.gov.br/cidades-e-estados/ não foi usada diretamente (bloqueia acesso automatizado).
O vínculo TSE <-> IBGE usa `../data/municipios.csv`.

## Ressalvas importantes

- **Desocupação não existe** no Censo 2022 por município; `nivel_ocupacao_10mais` (ocupados / pessoas de 10+) é só um substituto.
- **`filhos_por_mulher_12mais` não é a taxa de fecundidade total**, e **mortalidade infantil** não está na base (não existe por município no IBGE; viria do DATASUS/SIM+SINASC).
- PIB per capita = PIB 2023 / população do Censo 2022 (não há estimativa de população de 2023). Participação setorial é de 2021.
- Valores "-" da SIDRA foram tratados como zero; ".." / "..." / "X" viram vazio.
- Boa Esperança do Norte (MT) foi criado após o Censo e fica sem dados; Cachoeira Dourada (GO) tem participações setoriais fora de 0–100 no dado original.
- Os indicadores são muito correlacionados entre si (escolaridade, renda, cor, rural); use SHAP/permutação e validação cruzada por UF.
