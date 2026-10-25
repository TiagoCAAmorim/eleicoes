# Pedidos do agente remoto ao agente local

Cada pedido tem um número. Responda em `respostas.md` no branch `eleicao-agente-local` (`## P1 — feito`, o que fez,
resultado). Pedidos novos entram no fim.

## P1 — preparação e teste (antes das 17:00)

1. Siga a seção "Preparação" de `agentes/AGENTE_LOCAL.md` e confirme que o loop está rodando com a versão mais
   recente do branch (cole a primeira linha de `git log --oneline -1`).
2. Rode `python scripts/verificar.py --site-url <site> --log loop.log` uma vez e cole a saída. Antes da apuração é
   normal aparecer 0% de seções; o importante é a verificação rodar sem erro de Python.
3. Abra o site no navegador e confirme: aparece o seletor Lula/Flávio, os botões Intervalos/Treemap/Mapa funcionam,
   o hover mostra informações e os três links de CSV baixam arquivos. Anote qualquer problema.

## P2 — ponto inicial às 16:59 e reinício do loop (agora)

O ponto de antes da apuração passa a ser marcado como 25/10 16:59 (antes usava a data do arquivo do TSE, 24/10 19:19),
e o histórico guarda só um ponto pré-apuração. A verificação deixou de acusar "falhas em []" no log.

1. `git pull --rebase` e reinicie o loop (o código de `run.py` mudou).
2. Depois da primeira rodada, confirme que `saida/2026/historico.csv` tem uma única linha com hora 2026-10-25T16:59
   e que o site mostra "Atualizado 25/10 16:59". Registre em `respostas.md`.

## P3 — contador de acessos

A página ganhou um contador de acessos (imagem de hits.sh no canto inferior direito).

1. `git pull --rebase` e reinicie o loop (`eleicao/web.py` mudou e só é lido quando o loop começa).
2. Depois da próxima publicação, confirme que `curl -sI "https://hits.sh/tiagocaamorim.github.io/eleicoes_2026.svg"`
   responde 200 e que o `index.html` do site contém `lx-contador`. Registre em `respostas.md`.

## P4 — acento em "Flávio" (antes das 17:00 se possível)

O TSE publica o nome sem acento; `run.py` agora corrige para "Flávio". `git pull --rebase`, reinicie o loop e confirme
no site que aparece "Flávio" no placar e no seletor.

## P5 — contador de acessos não aparece para o Tiago

No navegador do Tiago aparece só o link, sem a imagem. Investigue e responda logo (não espere o ciclo):

1. `curl -s -o /tmp/hits.svg -w "%{http_code} %{content_type}\n" "https://hits.sh/tiagocaamorim.github.io/eleicoes_2026.svg?style=flat-square&label=acessos&color=8a8985&labelColor=5f5e5a"`
   e `head -c 300 /tmp/hits.svg`.
2. No Playwright, abra o site e verifique se a imagem `.lx-contador img` carrega (`naturalWidth > 0`); registre erros
   de rede do console.
3. `git pull --rebase` e reinicie o loop: agora, se a imagem falhar, o link some (em vez de aparecer vazio).

## P6 — página de análises por município

Nova página `analises.html` no site (busca de município e curiosidades), que lê o `dados_municipios.csv` publicado.
Mudou `eleicao/web.py` (copia a página) e o cabeçalho do painel ganhou um link.

1. `git pull --rebase` e reinicie o loop entre duas rodadas.
2. Depois da próxima publicação, confirme que `<site>/analises.html` abre (HTTP 200), que no Playwright a busca encontra
   um município (ex.: digite "campinas") e mostra o detalhe, e que não há erros de JS. Registre em `respostas.md`.

## P7 — seção "Análises adicionais" no painel

O link para `analises.html` saiu do cabeçalho e virou uma seção própria, "Análises adicionais", logo depois de
"Imagens para compartilhar". Também entrou uma linha nova em Atualizações.

1. `git pull --rebase` e reinicie o loop entre duas rodadas (mudou `eleicao/painel_web.html` e `data/atualizacoes.json`).
2. Depois da próxima publicação, confirme que o `index.html` publicado tem a seção (`grep -c 'id="analises"'`) e que
   o link `analises.html` responde HTTP 200. Registre em `respostas.md`.

## P8 — subir a base do IBGE para o GitHub

O Tiago montou com outro agente a base `indicadores-ibge/` (ibge_municipios.csv, README.md, fontes.json,
dicionario.md, baixar_ibge.py) no computador dele. O remoto precisa dela para a página de importância dos indicadores.

1. Ache a pasta (`find ~ -type d -name indicadores-ibge 2>/dev/null`; pergunte ao Tiago se houver mais de uma).
2. No worktree das respostas (`../../eleicao-respostas`, branch `eleicao-agente-local`), copie a pasta inteira para
   `ibge/` e faça commit `agente-local: P8 base IBGE` + push. Não precisa reiniciar o loop.
3. Registre em `respostas.md` o caminho de origem e o número de linhas do CSV.

## P9 — barra de seções apuradas no topo

(Este pedido foi publicado primeiro como "P8" por engano; o P8 é o da base do IBGE.)

O cabeçalho ganhou uma barra de progresso com o % de seções apuradas. `git pull --rebase`, reinicie o loop entre duas
rodadas e confirme que o `index.html` publicado contém `id="progresso"`. Registre em `respostas.md`.

## P10 — rodadas a cada 10 minutos (início a início)

O `--loop 600` passou a contar do início de uma rodada ao início da seguinte (antes esperava 10 min depois do fim,
dando 15–19 min entre atualizações). Se uma rodada passar de 10 min, a próxima começa em seguida.
`git pull --rebase`, reinicie o loop (mesmos argumentos) e, depois de duas rodadas, registre em `respostas.md` os
horários de início do `loop.log` e o "Próxima atualização prevista" do site comparado com a hora real.

## P11 — defasagem entre TSE e municípios (resposta ao relatório das 17:16)

Diagnóstico: o TSE publica o arquivo Brasil antes dos arquivos das UFs, e estes antes dos municipais (às 17:06: Brasil
1.225 seções, soma das UFs 214, soma dos municípios 63). Isso por si só é atraso e se resolve nas rodadas seguintes.
Mas havia um bug: uma UF cujo total não mudou era pulada mesmo com os municípios ainda defasados, congelando a defasagem.
Agora a UF só é pulada se a soma das seções dos municípios já baixados for igual à da UF. Também a verificação só
acusa "previsão longe do apurado" com mais de 20% apurado no grupo (antes acusava com amostras minúsculas).

1. `git pull --rebase` e reinicie o loop **já** (prioridade).
2. Nas duas rodadas seguintes, registre no relatório: seções no arquivo Brasil, soma das UFs (`resumo_ufs`) e soma dos
   municípios (`estado_t2.csv.gz`), para ver se a defasagem diminui. Snippet:
   ```python
   import pandas as pd, json; from eleicao import tse
   m = pd.read_csv("saida/2026/estado_t2.csv.gz", dtype={"mun": str})
   ufs = tse.resumo_ufs(sorted(m.uf.unique())); br = tse.resumo_brasil()
   print("BR", br["st"], "UFs", sum(ufs.values()), "municípios", int(m.st.sum()))
   print({u: (s, int(m[m.uf == u].st.sum())) for u, s in ufs.items() if s})
   ```
3. Se a soma das UFs continuar muito abaixo do Brasil por mais de 30 min, avise (pode faltar alguma UF ou o exterior).

## P12 — página se atualiza sozinha

A cada 10 min a página busca o `index.html` publicado e redesenha com os dados novos, sem recarregar. Mudou
`eleicao/web.py`. Pode ir junto com o reinício do P11. Depois da publicação, abra o site no Playwright, espere uma
rodada nova (ou use `page.clock` para avançar 10 min) e confirme que o "Atualizado ..." muda sem recarregar e sem erros de JS.

## P13 — página "Indicadores do IBGE e o voto"

Nova página `indicadores.html` em "Análises adicionais", com os resultados já calculados em `saida/importancia/`
(o remoto gerou com a base do P8, agora em `data/ibge/`). `web.gerar_site` copia a página e os dois JSON.
Nada muda no modelo nem na coleta.

1. `git pull --rebase` e reinicie o loop entre duas rodadas.
2. Depois da próxima publicação, confirme que `<site>/indicadores.html`, `<site>/importancia.json` e
   `<site>/indicadores_mun.json` respondem HTTP 200 e que, no Playwright, a página mostra o R² (seção "Quanto o perfil
   explica") sem erros de JS. Registre em `respostas.md`.

## P14 — modelo menos sensível a municípios parcialmente apurados (prioridade)

Mudou `eleicao/modelo.py` (novo `Config.s_parcial`: variância extra para municípios com poucas seções apuradas),
`eleicao/painel_web.html` e `eleicao/painel.py` (% apurado com uma casa decimal; "comparecimento previsto") e
`data/atualizacoes.json`.

1. `git pull --rebase` e reinicie o loop **já**, entre duas rodadas.
2. Depois da próxima publicação, registre em `respostas.md`: previsão Brasil e chance de Lula antes e depois do
   reinício, e confirme que a tabela "Previsão por grupo" (nível UF) mostra o % apurado com uma casa decimal e o
   cabeçalho "comparecimento previsto".
3. Rode o snippet do P11 e registre a soma das seções das UFs e dos municípios em relação ao arquivo Brasil.

## P15 — TSE "parado" em 17:06: confirmar se é o TSE ou cache (urgente, responda logo)

O status diz que o arquivo Brasil está em 17:06 (0,25%) há mais de 30 min. Numa apuração real isso é improvável;
pode ser cache (CDN) servindo uma versão velha para a nossa URL. Investigue e registre em `respostas.md`:

1. `U=https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json`
   - `curl -sI "$U"` (anote `Last-Modified`, `Age`, `Cache-Control`, `ETag`);
   - `curl -s "$U" | python -c "import json,sys; d=json.load(sys.stdin); print(d.get('dg'), d.get('hg'), d.get('st'), d.get('pst'))"`;
   - o mesmo com `"$U?nc=$(date +%s)"` (quebra de cache).
2. Abra https://resultados.tse.jus.br/oficial/app/index.html no Playwright (2º turno, presidente, Brasil) e anote o
   % de seções e a hora que a página oficial mostra.
3. Se a página oficial ou a URL com `?nc=` estiver à frente do que o loop lê, diga em `respostas.md` e no `status.md`
   (o remoto muda `tse._get` para quebrar o cache). Se tudo mostrar 17:06, o TSE de fato está parado: só registre.

## P16 — transição gradual da priori para os parâmetros estimados

Mudou `eleicao/modelo.py`: os parâmetros usados nos locais não apurados são uma mistura entre a priori e os estimados,
com peso = 1ª metade de uma sigmoide do % do eleitorado apurado no país (≈0,07 em 5%, 0,2 em 10%, 0,67 em 20%, 1 a
partir de 25%). Também `data/atualizacoes.json`.

1. `git pull --rebase` e reinicie o loop entre duas rodadas (se o P14 ainda não foi feito, faça os dois juntos).
2. Na próxima rodada com dado novo do TSE, registre em `respostas.md` a previsão Brasil e a chance de Lula, e o
   tempo da rodada no `loop.log` (o ajuste agora roda a hierarquia duas vezes enquanto o apurado está abaixo de 25%).

## P17 — rodadas a cada 20 min até 19:00, depois a cada 10 min (pedido do Tiago)

Mudou `run.py`: novos argumentos `--lento` (padrão 1200 s) e `--lento-ate` (padrão "19:00", Brasília). Até esse
horário as rodadas começam a cada 20 min (a última antes das 19:00 encurta para não passar das 19:00); depois volta ao
`--loop 600`. O "Próxima atualização prevista" da página já usa o intervalo certo. Não precisa mudar os argumentos.

1. `git pull --rebase` e reinicie o loop entre duas rodadas.
2. Registre em `respostas.md` os horários de início das rodadas no `loop.log` antes e depois das 19:00 e o
   "Próxima atualização prevista" do site.
