# Roteiro

Planejamento acordado em 01/11/2026, depois da apuração do 2º turno de 2026.

| Etapa | O quê | Situação |
|---|---|---|
| 0 | Repositório dedicado, pacote reorganizado, site com página inicial, modelos, análises e eleições | Em andamento |
| 0b | Painel: diagrama de Sankey das transferências de votos previstas (Brasil e regiões) | Feito |
| 1 | Banco de testes: rejogar a apuração real de 2026 (46 retratos) e 2022; métricas por % apurado (erro, cobertura 50/90%, CRPS, momento da "chamada"). Resultados em [rejogo-2026.md](rejogo-2026.md) | Feito |
| 2 | Base histórica do TSE 2006–2024 (presidente, governador, senador, prefeito, deputados), baixada pelo Actions | Feito ([base-historica.md](base-historica.md)) |
| 3 | Revisão do modelo do 2º turno: matriz mais flexível, covariáveis (deputados, reeleição, coligações), priori calibrada, incerteza honesta | Incerteza e curva feitas ([revisao-t2.md](revisao-t2.md)); priori calibrada com 2006–2026 e pesquisas ([calibracao-priori.md](calibracao-priori.md)); matriz v2 ganha por pouco e vira o padrão ([matriz-v2.md](matriz-v2.md)), falta o estresse dela; faltam covariáveis |
| 4 | Teste de estresse com várias marchas de apuração; critério: intervalo de 90% cobre ~90% em toda faixa de % apurado | Gerador de apurações sintéticas calibrado em 2026 ([estresse.md](estresse.md)); falta repetir com 2006–2018 |
| 5 | Outros cargos majoritários: governador, senador, prefeito | |
| 6 | Previsão do 1º turno: chance de vencer no 1º turno e de ir ao 2º | |
| 7 | Quociente eleitoral e alianças contrafactuais | |

Decisões: intervalo de 90%; base a partir de 2006; meta é acertar a faixa ao longo da apuração, não chamar o
resultado o mais cedo possível; pesquisas registradas a partir de reportagens e relatórios dos institutos.

## Diagnóstico preliminar de 2026

- Antes da apuração: Lula 48,4% (90%: 45,9–51,1); final 51,8%. Fora do intervalo até ~5% apurado e de novo aos 62%.
- A curva de transição (completa em 25%) atrasou a convergência: com 21% apurado, só os dados davam 51,4% e 99%.
- Regressão por município: ΔLula = 0,32·Outros + 0,60·Δcomparecimento + 3,5 pt; ΔFlávio = 0,57·Outros + 0,45·Δcomparecimento − 1,8 pt.
  "Outros" se dividiu como a pesquisa (32% Lula), mas o modelo estimou 62% porque a matriz não deixava brancos e
  nulos irem para um candidato nem falta diferente entre eleitores de A e B.
