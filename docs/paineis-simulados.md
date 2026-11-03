# Apurações simuladas de 2006 a 2022 (etapa 8)

Painéis no mesmo formato do painel da apuração real, para os 2º turnos presidenciais de 2006, 2010, 2014, 2018 e
2022, com um seletor do momento da noite: em cada momento, a página mostra o que o modelo diria com as seções
apuradas até ali (placar, chance, linha do tempo até aquele ponto, grupos, mapa, transferências e Sankey). Um botão
reproduz a noite inteira. O painel revisado de 2026 ganhou o mesmo seletor, com os 43 retratos reais da noite.

Site: `/<ano>/presidente/` (ex.: [2022](https://tiagocaamorim.github.io/eleicoes/2022/presidente/)) e a seção
"Apurações simuladas" da página inicial. Código: `scripts/paineis_simulados.py` (dados) e `eleicoes/site/web.py`
(seletor e aviso). Saídas em `resultados/simulacoes/<ano>-presidente/`.

## Por que simulada

O TSE só guarda o resultado final por seção; os parciais da noite não existem para essas eleições. Então:

- **Votos**: os reais, seção a seção (`dados/historico/<ano>/secoes_presidente_t2.csv.gz`; 2022 em `dados/2022/`).
- **Ordem de chegada**: sorteada pelo gerador do teste de estresse (`eleicoes/modelos/estresse.py`, `ordem`), com
  o atraso regional de 2026 (Sul e Sudeste antes; Nordeste, Norte e capitais depois; zonas em blocos), **sem viés
  entre cidades** (beta = 0) e com as primeiras seções de cada cidade um pouco mais para o candidato do PT que a
  cidade inteira (gama = 0,05), como se mediu em 2026. Semente fixa (2026 + ano).
- **Horário**: segue a marcha do % apurado da noite de 2026 a partir das 17h; é só para o eixo de horário.
- **Modelo**: o adotado (calibrado_cauteloso, o mesmo do painel revisado de 2026). Priori = média das matrizes dos
  2º turnos anteriores, com a linha dos outros candidatos ajustada à média das pesquisas da véspera (Datafolha e
  Ibope). 2006 não tem eleição anterior na base: usa a média de 2010–2022 (informação do futuro só na matriz;
  a pesquisa é a de 2006, 61% para Lula, acrescentada a `dados/pesquisas/presidente_t2.csv`).

Cada página diz no topo que é uma simulação e mostra o resultado oficial (linha tracejada na linha do tempo,
losangos nos grupos e coluna "resultado real" na tabela).

## O que o modelo diria

21 momentos por eleição (antes, 0,5%, 1%, ..., 99%, 100%). Previsão de A (candidato do PT) nos votos válidos, com o
intervalo de 90%; cobertura = fração dos momentos antes de 100% em que o intervalo contém o resultado
(`resultados/simulacoes/resumo.csv`):

| Ano | Real | Antes | 5% | 25% | 50% | Cobertura 90% | Chance > 99% do vencedor a partir de |
|---|---|---|---|---|---|---|---|
| 2006 | 60,8 | 58,3 (56,4–60,2) | 62,9 (60,7–65,2) | 62,4 (61,0–63,7) | 61,7 (60,9–62,6) | 50% | antes da apuração |
| 2010 | 56,1 | 55,7 (52,2–59,7) | 57,2 (54,5–59,7) | 56,8 (55,3–58,3) | 56,6 (55,7–57,4) | 100% | antes da apuração |
| 2014 | 51,6 | 52,5 (48,2–56,7) | 52,5 (49,8–55,2) | 52,3 (50,9–53,9) | 52,2 (51,3–53,1) | 95% | 25% |
| 2018 | 44,9 | 45,3 (40,9–49,3) | 45,8 (43,2–48,4) | 45,4 (43,9–47,0) | 45,2 (44,3–46,1) | 100% | 3% |
| 2022 | 50,9 | 51,9 (49,5–54,3) | 51,9 (49,7–54,1) | 51,5 (50,2–52,9) | 51,3 (50,5–52,1) | 100% | 50% |

Nenhuma chamada errada (chance acima de 99% para quem perdeu) em nenhum momento.

Leitura:

- **A previsão fica ~0,5 a 2 pontos acima do resultado para o PT até o fim** em todos os anos. É o efeito do viés
  das primeiras seções de cada cidade (gama), que o modelo absorve só em parte: o resultado parcial de uma cidade
  pesa na previsão do resto dela. É o mesmo mecanismo que o teste de estresse apontou como o que mais engana
  modelos ([estresse.md](estresse.md)).
- **2006 é o caso ruim**: antes da apuração a faixa fica abaixo do resultado (a matriz de 2010–2022 não descreve
  bem o 2º turno de 2006, mesmo com a pesquisa) e, com o viés das primeiras seções, a previsão passa para cima e o
  intervalo fica acima do resultado entre 7,5% e 60% apurado. O resultado nunca esteve em dúvida, mas a faixa
  ficou estreita demais.
- Nos outros anos a faixa cobre 95–100% dos momentos. Em 2014, a eleição mais apertada, a chance passa de 99%
  com 25% apurado; em 2022, com 50%.

Isto é **uma** noite por eleição. Outra semente daria outra ordem e outra trajetória; a cobertura em muitas noites
é a do [teste de estresse](estresse.md).

## Como refazer

```bash
python scripts/paineis_simulados.py              # 2006–2022, ~15 min; grava resultados/simulacoes/
python scripts/paineis_simulados.py --so-resumo  # só a tabela acima
python scripts/rejogar_paginas_2026.py           # painel revisado de 2026, agora com web/momentos.json
python scripts/gerar_site.py                     # monta as páginas (lê resultados/simulacoes/ sozinho)
```

## Próximos passos possíveis

- Governador (2º turno, 46 eleições já rejogadas) e prefeito: o painel atual é nacional (região, porte, UF), então
  precisariam de um painel por UF/cidade com grupos por município ou zona.
- Mais de uma noite por eleição (sementes), ou um seletor de ordem (sem viés, viés para A, viés para B).
- O painel do dia de 2026 com os retratos publicados na noite (27 versões de `web/previsao.json` no histórico git).
