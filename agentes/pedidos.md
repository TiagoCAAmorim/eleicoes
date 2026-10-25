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
