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
