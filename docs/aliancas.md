# Alianças contrafactuais (deputados)

Etapa 7 do [roteiro](roteiro.md). Pergunta: quanto as coligações (até 2018) e federações (2022) mudaram as
bancadas de deputado federal e estadual, e que alianças teriam rendido mais a um grupo de partidos. Por decisão de
03/11/2026, a etapa não analisa o efeito das regras do quociente eleitoral em si, só as alianças.

Página: [Alianças que não aconteceram](https://tiagocaamorim.github.io/eleicoes/aliancas.html), com um simulador
em que se junta qualquer grupo de partidos numa lista e se vê quem entraria e quem sairia.

**Hipótese de todas as simulações:** cada eleitor vota como votou; só muda quem está na mesma lista. Uma aliança real
mudaria candidaturas e campanhas, então os números são o efeito aritmético da aliança.

## Dados

`scripts/tse_proporcional.py` (workflow **proporcional**, no Actions) grava em `dados/historico/<ano>/`:

| Arquivo | Conteúdo |
|---|---|
| `proporcional_candidatos.csv.gz` | um candidato por linha: votos nominais (brutos e válidos), partido, coligação, federação, situação final (eleito por QP, por média, suplente) |
| `proporcional_partidos.csv.gz` | votos de cada partido por circunscrição: nominais válidos, legenda (incluindo nominais convertidos em legenda) e a coligação ou federação |
| `proporcional.json` | colunas lidas e totais, para conferência |

Deputados (2006–2022) e vereadores (2008–2024). Cuidados com os arquivos do TSE:
- Até 2010 o `SQ_CANDIDATO` se repete entre cargos e UFs; a chave do candidato é cargo + circunscrição + sq + número.
- Em 2010 o `SG_UE` dos deputados traz o código do município; a circunscrição deles é a UF.
- Algumas cidades têm a mesma coligação registrada duas vezes (sq diferentes, mesmos partidos em outra ordem). A
  coligação é identificada pela lista de partidos em ordem alfabética.
- Desde 2016 há votos nominais anulados ou convertidos em legenda; usamos os campos `_VALIDOS` e o total de legenda.

## Cálculo

`eleicoes/modelos/proporcional.py` distribui as cadeiras (Código Eleitoral, arts. 106–111) com a regra de cada ano:

| Ano | Listas | Sobras disputadas por | Mínimo do candidato | Quando ninguém cumpre as exigências |
|---|---|---|---|---|
| 2006–2014 | partidos e coligações | quem atingiu o QE | — | — |
| 2016 | partidos e coligações | quem atingiu o QE | 10% do QE | maiores médias entre os mesmos |
| 2018 | partidos e coligações | todos | 10% | maiores médias |
| 2020 | partidos | todos | 10% | maiores médias |
| 2022, 2024 | partidos e federações | quem tem 80% do QE | 10% (QP), 20% (sobras) | maiores médias entre todos (STF) |

Em 2022 o TSE deixou na 3ª fase das sobras só quem tinha 80% do QE; o STF abriu a todos e a retotalização trocou 7
deputados federais (AP, DF, RO, TO). Os dados abertos já trazem os eleitos depois dela, e o motor usa a regra do STF
(a leitura original fica em `REGRAS["2022_tse"]`).

Empates de votos entre candidatos são decididos pelo mais velho na lei; aqui, pela ordem do sq (a data de nascimento
não está nos arquivos de votação). Isso explica quase todas as diferenças de vereador.

### Conferência com os eleitos oficiais

| Eleição | Eleitos iguais |
|---|---|
| Deputado federal 2006 | 512 de 513 (ES: duas coligações separadas por 73 votos na última vaga) |
| Deputado estadual 2006 | 1032 de 1035 |
| Deputados federais e estaduais 2010, 2014, 2018, 2022 | 100% |
| Vereadores 2008–2024 | 99,7% a 99,9% (empates de votos e cidades com eleição revista) |

`python scripts/aliancas.py validar` refaz a tabela (`resultados/aliancas/validacao.csv`).

## Resultados

`python scripts/aliancas.py efeito busca` (cerca de 4 min) grava em `resultados/aliancas/`:

- `efeito_aliancas.csv`: para cada coligação ou federação real de cada UF, as cadeiras de cada membro com a aliança e
  com só ela desfeita (os outros mantêm as suas); linhas `fora=True` são partidos de fora que perderam ou ganharam.
- `efeito_partidos.csv`: cadeiras de cada partido no país com as alianças reais e com todos sozinhos.
- `busca_pares.csv`: todos os pares de partidos com 1% ou mais dos votos, unidos em todas as UFs.

Principais achados (deputado federal):
- **As coligações transferiam cadeiras dos grandes para os médios e pequenos.** Com todos sozinhos, o PT teria 104
  cadeiras em 2014 (teve 69) e 112 em 2010 (teve 86); o PMDB 108 em 2010 (teve 78). Somando as UFs de 2006 a 2018,
  quem mais ganhou com as próprias coligações foram PP (+44), PC do B (+35), PR (+34), PTB (+33), DEM (+31) e
  PDT (+30).
- **Dentro da coligação também havia perdedores:** 91 casos de 2006 a 2018 em que um partido teria mais cadeiras
  sozinho, como o PSB no Ceará em 2006 (2 com a coligação PMDB/PP/PSB/PT, 5 sozinho).
- **As federações de 2022 ajudaram todos os membros:** PC do B +5 e PV +5 na federação com o PT (o PT +1),
  Cidadania +3 e PSDB +2, PSOL +2 e Rede +1.
- **Parcerias que não aconteceram em 2022:** PP + Republicanos teriam 17 cadeiras a mais juntos (104 em vez de 87);
  MDB + PT, 14; PSB + Republicanos, 14; PSB + PSD, 13.

## Simulador

A página faz a mesma conta no navegador (`site/aliancas.js`), a partir de um JSON por eleição gerado por
`python scripts/aliancas.py exportar` (chamado por `gerar_site.py`; cerca de 3 MB no total). O teste
`tests/test_proporcional.py::test_pagina_reproduz_o_motor` confere, com o node, que o JavaScript e o Python elegem os
mesmos candidatos em 12 cenários. O cenário fica na URL (`#e=8&b=real&g=PT,PSOL,PSB,PDT`), para compartilhar.

Pela linha de comando:

```bash
python scripts/aliancas.py simular --ano 2022 --cargo 6 --grupo PT,PSOL,PSB,PDT
python scripts/aliancas.py simular --ano 2018 --cargo 6 --base partido          # todos sozinhos
python scripts/aliancas.py simular --ano 2018 --cargo 7 --grupo PSL,NOVO --uf SP
```

Vereadores: os dados estão na base e o motor os reproduz, mas o simulador cobre só deputados por enquanto.
