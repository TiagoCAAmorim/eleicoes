# Roteiro

Planejamento acordado em 01/11/2026, depois da apuração do 2º turno de 2026.

| Etapa | O quê | Situação |
|---|---|---|
| 0 | Repositório dedicado, pacote reorganizado, site com página inicial, modelos, análises e eleições | Em andamento |
| 0b | Painel: diagrama de Sankey das transferências de votos previstas (Brasil e regiões) | Feito |
| 1 | Banco de testes: rejogar a apuração real de 2026 (46 retratos) e 2022; métricas por % apurado (erro, cobertura 50/90%, CRPS, momento da "chamada"). Resultados em [rejogo-2026.md](rejogo-2026.md) | Feito |
| 2 | Base histórica do TSE 2006–2024 (presidente, governador, senador, prefeito, deputados), baixada pelo Actions | Feito ([base-historica.md](base-historica.md)) |
| 3 | Revisão do modelo do 2º turno: matriz mais flexível, covariáveis (deputados, reeleição, coligações), priori calibrada, incerteza honesta | Incerteza e curva feitas ([revisao-t2.md](revisao-t2.md)); priori calibrada com 2006–2026 e pesquisas ([calibracao-priori.md](calibracao-priori.md)); matriz v2 testada e não adotada: ganha pouco nos rejogos e perde no estresse ([matriz-v2.md](matriz-v2.md)); covariáveis (deputados, prefeitos, reeleição) testadas e não adotadas: explicam menos de 4% do erro por município ([covariaveis.md](covariaveis.md)) |
| 4 | Teste de estresse com várias marchas de apuração; critério: intervalo de 90% cobre ~90% em toda faixa de % apurado | Gerador de apurações sintéticas calibrado em 2026 e repetido com 2010, 2014 e 2018: o modelo adotado cobre 88–96% ([estresse.md](estresse.md)); no fim da apuração cobre 98% com 70% apurado e 85% com 90% (48 rodadas) |
| 5 | Outros cargos majoritários: governador, senador, prefeito | 2º turno de governador com o mesmo modelo, testado em 56 eleições de 2006–2022 ([governador.md](governador.md)); pesquisas da véspera de 2010, 2018 e 2022 cortam o erro de antes da apuração de 6 para 3 pontos. 2º turno de prefeito com o modelo por seção, testado em 216 eleições de 2012–2024 ([prefeito.md](prefeito.md)): cobre 93–100% com choque comum de 6% no que falta apurar. Faltam as pesquisas de governador de 2014 e as de prefeito; senador vai para a etapa 6 |
| 6 | Previsão do 1º turno: chance de vencer no 1º turno e de ir ao 2º | |
| 7 | Alianças contrafactuais (o efeito do quociente em si ficou de fora) | Deputados 2006–2026: motor que reproduz os eleitos oficiais, efeito das coligações e federações reais, busca de pares e simulador no site ([aliancas.md](aliancas.md)). Base de vereadores 2008–2024 pronta, sem simulador |
| 8 | Painéis que simulam a apuração de eleições passadas (2006–2022), mostrando como a previsão do modelo evolui ao longo da noite. Cada página deve deixar claro que é uma **simulação**: o TSE não guarda retratos parciais dessas apurações, então a ordem de chegada dos votos é sintética | |

Decisões: intervalo de 90%; base a partir de 2006; meta é acertar a faixa ao longo da apuração, não chamar o
resultado o mais cedo possível; pesquisas registradas a partir de reportagens e relatórios dos institutos.

## Diagnóstico preliminar de 2026

- Antes da apuração: Lula 48,4% (90%: 45,9–51,1); final 51,8%. Fora do intervalo até ~5% apurado e de novo aos 62%.
- A curva de transição (completa em 25%) atrasou a convergência: com 21% apurado, só os dados davam 51,4% e 99%.
- Regressão por município: ΔLula = 0,32·Outros + 0,60·Δcomparecimento + 3,5 pt; ΔFlávio = 0,57·Outros + 0,45·Δcomparecimento − 1,8 pt.
  "Outros" se dividiu como a pesquisa (32% Lula), mas o modelo estimou 62% porque a matriz não deixava brancos e
  nulos irem para um candidato nem falta diferente entre eleitores de A e B.
