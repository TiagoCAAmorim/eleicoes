# Rejogo da apuração de 2026 (etapa 1)

> A etapa 3 usou este banco de testes para revisar a incerteza do modelo: ver [revisao-t2.md](revisao-t2.md).
> As variantes abaixo continuam reproduzíveis (`atual` = modelo usado ao vivo).

A noite de 25/10/2026 foi rejogada com 5 variantes do modelo, usando os 46 retratos publicados durante a
apuração (`dados/2026/presidente/retratos_t2.csv.gz`, extraídos do histórico git por
`scripts/extrair_retratos_2026.py`). Para não ajustar o modelo só a 2026, as mesmas variantes rodaram no
backtest de 2022 com a ordem parecida com a real e com a ordem adversa (seções mais pró-Bolsonaro primeiro).

Reproduzir: `python scripts/rejogar_2026.py` (~20 min) e
`python scripts/backtest.py --variante <nome> --ordens 2022 adversa --rodadas 1`.
Saídas: `resultados/rejogo-2026/` e `resultados/backtest/variantes_2022.csv`.

O modelo atual, rejogado, reproduz os números publicados na noite (ex.: 7,67% apurado: 49,44% [46,84; 51,96]).

## Variantes

| Variante | Mudança |
|---|---|
| atual | Modelo usado ao vivo (curva de transição até 25%) |
| sem_curva | Sem a curva de transição |
| sem_curva_choque | Sem curva + choque nacional de 2% na margem do eleitorado que falta apurar |
| sem_curva_choque_v2 | + matriz v2: branco/nulo do 1º turno pode ir para A ou B; falta separada para eleitores de B |
| sem_curva_choque_v2_priori | + priori mais larga (desvio 1,0 em vez de 0,7) |

## Resultados em 2026 (Brasil, todas as rodadas)

| Variante | Erro médio (pt) | Cobertura 90% Brasil | Largura média 90% (pt) | CRPS | Cobertura 90% UFs | Chance > 99% a partir de |
|---|---|---|---|---|---|---|
| atual | −1,02 | 84% | 2,16 | 0,68 | 90% | 26% apurado |
| sem_curva | −0,11 | 98% | 1,45 | 0,30 | 85% | 26% |
| sem_curva_choque | −0,12 | 100% | 2,32 | 0,31 | 90% | 41% |
| sem_curva_choque_v2 | −0,09 | 100% | 2,42 | 0,30 | 88% | 41% |
| sem_curva_choque_v2_priori | −0,08 | 100% | 2,45 | 0,29 | 88% | 41% |

Cobertura com tolerância de 0,1 ponto: perto do fim os intervalos das UFs têm centésimos de ponto e
revisões do TSE contariam como falha. CRPS mede a distribuição inteira (menor é melhor).

Detalhe por faixa de % apurado em `resultados/rejogo-2026/resumo.csv`; gráfico em `rejogo.png`.

## Resultados em 2022 (backtest, 1 rodada por ordem)

| Variante | Ordem real: erro / cobertura 90% | Ordem adversa: erro / cobertura 90% |
|---|---|---|
| atual | 0,41 pt / 94% | 1,12 pt / 44% |
| sem_curva | 0,12 / 94% | 3,07 / 0% |
| sem_curva_choque | 0,15 / 100% | 3,10 / 0% |
| sem_curva_choque_v2 | 0,13 / 100% | 3,10 / 0% |

## Conclusões

1. **A curva de transição custou caro em 2026**: tirar a curva corta o erro médio de −1,0 para −0,1 ponto e o
   CRPS pela metade. Mas a curva é o que protege contra uma ordem de apuração enviesada: na ordem adversa de 2022,
   sem ela a cobertura cai de 44% para 0%. **Ela não deve sair sem um substituto.** Proposta para a etapa 3:
   no lugar de uma curva fixa pelo % apurado, um peso que depende de quão representativo é o que já foi apurado
   (quantas UFs e portes têm dados e quanto o apurado difere da priori em cada grupo).
2. **O choque nacional resolve a cobertura antes da apuração e no Brasil** (84% → 100%), ao custo de intervalos
   ~60% mais largos e de chamar o resultado só com 41% apurado (contra 26%). 2% parece demais; testar 1%.
   Não ajuda na ordem adversa, porque o viés vem dos parâmetros, não do ruído.
3. **A matriz v2 não resolve a leitura das transferências.** Com os dados finais, Outros→Lula cai só de 62%
   para 59%, e branco/nulo→Lula vai ao teto (25%); a falta dos eleitores de Flávio continua perto de zero. Os
   dados por município não separam esses fluxos: a solução passa por prioris de pesquisas e de eleições passadas
   (etapas 2 e 3). Efeito no total é pequeno (CRPS igual).
4. **A priori mais larga só muda o começo** e quase nada.
5. **UFs no começo da noite**: cobertura de 73% a 83% até 5% apurado em todas as variantes. O choque por UF
   (2%) está pequeno para o início.

Próximo passo (etapa 3): substituto da curva + choque nacional calibrado (1% a 2%) + choque por UF maior no
início, testados de novo nos dois anos e nas ordens da etapa 4.
