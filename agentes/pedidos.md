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
