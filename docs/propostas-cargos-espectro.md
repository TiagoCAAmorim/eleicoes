# Propostas: estado dos cargos eletivos, espectro dos partidos e painel do Legislativo

Documento de propostas, escrito em 03/11/2026 a pedido do Tiago, **antes de implementar qualquer coisa**. Cada parte
termina com as decisões em aberto. Nada aqui foi construído ainda.

Três blocos, em ordem de dependência:

1. **Estado atual dos cargos eletivos**: quantos cargos cada partido ocupa, de governador a vereador, e onde.
2. **Espectro dos partidos a partir das alianças**: um grafo em que partidos que se aliam mais ficam mais perto, e
   como transformar isso em coordenadas e em cores para os mapas do bloco 1.
3. **Painel do Legislativo** (ideia futura): votações da Câmara e do Senado, votos por parlamentar, análise por
   espectro, painéis por parlamentar com suplentes; depois, as assembleias estaduais.

---

## 1. Estado atual dos cargos eletivos

### O que mostrar

| Visão | Conteúdo |
|---|---|
| Distribuição por partido | Para cada cargo (governador, senador, deputado federal, deputado estadual/distrital, prefeito, vereador): número de cadeiras e % por partido, e também por federação. Para Câmara, Senado e assembleias, gráfico de hemiciclo com os partidos ordenados pelo eixo 1 do espectro (bloco 2); para prefeitos e vereadores, barras ordenadas da mesma forma |
| Peso pela população | Prefeitos e governadores contados de dois jeitos: número de cargos e população governada (eleitorado ou população do IBGE). Um partido com 800 prefeituras pequenas e outro com 30 capitais contam histórias diferentes |
| Distribuição geográfica | Mapa por UF (governador, senadores, bancada federal e estadual) e por município (prefeito, câmara de vereadores), com agregação por região, região intermediária e imediata do IBGE |
| Indicadores | Número efetivo de partidos (Laakso-Taagepera) por cargo e UF; concentração; alinhamento entre níveis (prefeito do mesmo partido ou aliança do governador; governador alinhado ao presidente); variação contra o ciclo anterior (2020→2024, 2022→2026) |

### "Atual" quer dizer o quê

Há duas fotos possíveis, e proponho mostrar as duas lado a lado:

- **Como saiu das urnas**: partido do eleito na data da eleição (TSE). É fácil, completo e reprodutível.
- **Como está hoje**: partido atual, depois de trocas de partido (janela partidária), cassações, renúncias,
  eleições suplementares e suplentes em exercício. Só existe de forma organizada para Câmara e Senado (APIs do
  bloco 3). Para assembleias, prefeitos e vereadores, a fonte seria a base de filiados do TSE, que é grande e
  exige casar candidato com filiado pelo título de eleitor; fica como fase posterior.

Em novembro de 2026 os ciclos estão desencontrados: prefeitos e vereadores são os de 2024; governadores,
deputados e 2/3 do Senado acabaram de ser eleitos em 2026 e tomam posse em 2027 (Senado: 54 cadeiras de 2026 +
27 de 2022). A página deve dizer a qual eleição cada número se refere.

### Fontes e o que já temos

| Dado | Situação |
|---|---|
| Prefeitos eleitos 2008–2024 (partido e coligação) | Já na base: `dados/historico/<ano>/candidatos.csv.gz` |
| Governadores e senadores 2006–2022 | Já na base, mesmo arquivo |
| Deputados federais, estaduais e vereadores 2006–2024, com situação final (eleito por QP, por média, suplente) | Branch da etapa 7 (`scripts/tse_proporcional.py`, `proporcional_candidatos.csv.gz`); reaproveitar quando entrar na `main` |
| **Eleição de 2026** (governador, senador, deputados) | Falta: rodar os mesmos workflows (`historico`, `proporcional`) com `anos=2026` assim que o TSE publicar os arquivos consolidados |
| Eleições suplementares | Hoje descartadas (`CD_TIPO_ELEICAO` 1); para a foto "hoje" dos prefeitos, incluir a última eleição de cada município |
| Malhas | Já temos `dados/comum/municipios_br.geojson.gz` e `estados_br.geojson` |
| População | `dados/ibge/ibge_municipios.csv` |

**Sucessão de partidos.** Para comparar ciclos é preciso uma tabela de sucessão mantida à mão
(`config/partidos.json`): fusões e mudanças de nome (PMDB→MDB, PR→PL, PRB→Republicanos, PPS→Cidadania, PSL+DEM→União,
PTB+Patriota→PRD, PTC→Agir, PMN→Mobiliza, incorporações pelo Podemos e pelo Solidariedade etc.) e federações
(com data de início). Essa tabela é usada também no bloco 2 e no 3, então vale fazê-la uma vez, bem documentada.

### Esforço

Baixo a médio. Os dados estão quase todos na base; o trabalho é a tabela de partidos, a de 2026 e as páginas.
Estimo uma thread para os dados e indicadores e outra para as páginas e mapas.

### Decisões em aberto

1. Mostrar as duas fotos ("urnas" e "hoje") ou só a das urnas no começo? *Recomendo só "urnas" primeiro, e "hoje"
   para Câmara e Senado quando o bloco 3 existir.*
2. Peso dos mapas de prefeito: por município (cada um conta 1) ou por eleitorado? *Recomendo ter os dois, com
   seletor.*

---

## 2. Espectro dos partidos a partir das alianças

### A ideia

Montar um grafo com um nó por partido (já passado pela tabela de sucessão) e arestas com peso igual à "força de
aliança" entre dois partidos, e então tirar desse grafo coordenadas contínuas (o "espectro") que servem para
ordenar gráficos e colorir mapas.

### Base de alianças (reaproveitando, sem duplicar)

| Fonte | Anos | Volume | Onde está |
|---|---|---|---|
| Coligações para presidente, governador, senador | 2006–2022 (+2026) | ~250 chapas por eleição geral | `candidatos.csv.gz` (colunas `coligacao`, `composicao`) |
| Coligações para prefeito | 2008–2024 | ~15–19 mil chapas por eleição | `candidatos.csv.gz` |
| Coligações proporcionais (deputados, vereadores) | 2006–2018 (proibidas a partir de 2020) | milhares | `proporcional_partidos.csv.gz` da etapa 7 |
| Federações | 2022–2026 | poucas, mas fortes (valem 4 anos e em todo o país) | idem, colunas de federação |

Um parser único para a coluna `composicao` (que inclui textos como
`Federação BRASIL DA ESPERANÇA - FE BRASIL (13-PT / 65-PC do B / 43-PV)`) deve ficar em `eleicoes/` e ser usado
tanto aqui quanto pela etapa 7, para as duas threads não terem parsers diferentes.

### Como pesar as arestas

Coligação brasileira é notoriamente pouco ideológica, sobretudo no município. Por isso o peso precisa de alguns
cuidados, que viram parâmetros:

- **Recência**: peso que decai com a idade da eleição (meia-vida de 4 a 8 anos), para o espectro refletir o
  presente e não 2006.
- **Nível**: um peso por tipo de cargo. Chapa presidencial e de governador diz mais sobre afinidade do que uma
  coligação de vereador em cidade pequena. Proposta inicial: presidente 4, governador/senador 2, prefeito 1,
  proporcional 0,5, federação 6 (é um casamento de 4 anos).
- **Normalização por tamanho**: partidos grandes e do "centrão" se aliam com todos. Usar uma medida de
  associação (p. ex. *association strength* `w_ij / (d_i·d_j)` ou PMI) em vez da contagem bruta, senão o
  centro do grafo vira simplesmente "quem tem mais candidatos".
- **Oposição (opcional)**: dois partidos que lançaram candidatos adversários na mesma disputa, especialmente em 2º
  turno, ganham uma aresta negativa. Isso dá um grafo com sinal e ajuda a separar os polos; é um passo a mais,
  então proponho testá-lo como variante.
- **Partidos nanicos**: com poucas alianças, ficam com posição instável. Mostrar com intervalo (bootstrap das
  eleições) ou agrupar em "outros".

### Métodos para tirar coordenadas do grafo

| Método | Como funciona | Prós | Contras |
|---|---|---|---|
| **Laplacian eigenmap** (embedding espectral, Laplaciano normalizado) | Autovetores do Laplaciano: o 1º não trivial (vetor de Fiedler) é a maior "divisão" do grafo | Determinístico, rápido, eixos ordenados por importância, tem interpretação clara (o eixo 1 é o corte que menos rompe alianças) | Sensível a nós muito conectados (por isso o Laplaciano normalizado); sinal do eixo é arbitrário (fixamos com uma âncora, p. ex. PT negativo); nós com pouca ligação vão para as pontas |
| **Análise de correspondência** da matriz partido × chapa | Trata cada chapa como uma "coluna" e acha os eixos que mais explicam quem aparece junto | Natural para dados de incidência; dá a % de inércia explicada por eixo (diz quantos eixos valem a pena); muito usada em ciência política | Os mesmos problemas com partidos raros; menos intuitiva de explicar que o grafo |
| **MDS clássico** sobre distâncias (1 − afinidade) | Coloca os partidos num plano preservando as distâncias | Simples, dá variância explicada | Depende de como se define a distância; na prática fica próximo da análise de correspondência |
| **t-SNE** | Otimiza vizinhanças locais | Bom para ver agrupamentos em dados grandes | Com ~30 partidos é inadequado: eixos sem significado, distâncias globais não confiáveis, resultado muda a cada execução e com a perplexidade. Ruim para cor, porque a mesma cor não significaria a mesma coisa entre versões |
| **UMAP** | Grafo de vizinhos + otimização | Preserva melhor a estrutura global que o t-SNE | Mesmos problemas para 30 pontos; dependência extra (`umap-learn`); estocástico |
| **Layout por forças** (Fruchterman-Reingold, ForceAtlas2) | Simulação física do grafo | Ótimo para **desenhar** o grafo na página | Coordenadas sem significado, não serve como "feature" |
| **Detecção de comunidades** (Louvain/Leiden) | Divide em blocos | Gera blocos discretos fáceis de nomear ("campo da esquerda", "centrão"...) | Discreto; muda de bloco com pequenas variações dos pesos |

**Recomendação:** Laplacian eigenmap como método principal, com a análise de correspondência como checagem (os
dois devem concordar no eixo 1; se não concordarem, a escolha dos pesos está mal feita). Layout por forças só para
desenhar o grafo. t-SNE e UMAP não, pelo tamanho do problema. Comunidades como camada opcional de rótulos.

**Validação externa.** O espectro de alianças mede "proximidade de coalizão", que não é o mesmo que ideologia.
Proponho comparar o eixo 1 com duas réguas independentes: (a) as escalas de especialistas usadas na ciência
política brasileira (survey de Bolognesi, Ribeiro e Codato; Brazilian Legislative Surveys de Power e Zucco), só
como referência citada; e (b) o espectro tirado das **votações nominais** da Câmara (bloco 3), que é a melhor régua
de comportamento. Se o bloco 3 for feito, o painel pode mostrar os dois espectros lado a lado, o que já é uma
análise interessante por si só.

**Evolução no tempo.** Calcular o espectro por janela (p. ex. ciclo 2006–2010, ..., 2022–2026) e alinhar os eixos
entre janelas (rotação de Procrustes) permite mostrar partidos "andando" no espectro.

### Do espectro para a cor dos mapas

| Opção | Como | Prós | Contras |
|---|---|---|---|
| **A. RGB = 3 eixos** (a sua ideia original) | R, G, B recebem os eixos 1, 2 e 3 normalizados | Usa 3 dimensões; fácil de implementar | RGB não é perceptualmente uniforme (a mesma distância no espectro vira diferenças de cor muito desiguais); cores ficam "sujas" e difíceis de ler; legenda praticamente impossível; ruim para daltônicos |
| **B. Mapa de cor 2D perceptual** | Eixos 1 e 2 viram as coordenadas a e b do espaço OKLab, com luminosidade fixa; partidos próximos ganham cores parecidas | Distância no espectro ≈ diferença de cor percebida; legenda é um disco de cores com os partidos posicionados nele; dá para orientar o eixo 1 para vermelho↔azul, a convenção brasileira | Só 2 dimensões; precisa calibrar a orientação para ficar intuitivo |
| **C. Escala divergente no eixo 1** | Uma cor de cada lado, intensidade pela distância do centro | A mais legível de todas; funciona para daltônicos escolhendo a paleta certa | Perde o eixo 2 (que costuma separar, por exemplo, governismo de oposição) |
| **D. Cores de blocos** (comunidades) | Uma cor por bloco | Legenda simples | Discreto; esconde nuances |
| **E. Cores oficiais dos partidos** | A cor de cada partido | Familiar | Não tem relação com o espectro; muitos partidos com cores iguais |

**Como colorir um lugar com vários partidos.** Para cada município ou UF, a cor seria a **média das coordenadas dos
partidos ponderada pelas cadeiras (ou votos)**, levada para a cor; e a **saturação** dada pela concentração
(índice de Herfindahl). Uma câmara de vereadores dividida entre polos fica acinzentada; uma dominada por um bloco
fica com cor forte. Para prefeito (um partido só) é a cor do partido.

**Recomendação:** B como padrão, com C como alternativa num seletor (e por ser a mais acessível). Manter A só como
experimento comparativo, se você quiser ver.

### Esforço

Médio. Grafo e embeddings são numpy/scipy (sem dependências novas, exceto `networkx` se quisermos o layout por
forças). O trabalho maior é o parser de composições, a tabela de sucessão e calibrar os pesos.

### Decisões em aberto

3. Pesos por nível e meia-vida: aceita a proposta inicial como ponto de partida, a ser ajustada olhando o
   resultado?
4. Incluir arestas negativas (adversários) já na primeira versão ou só como variante?
5. Esquema de cor padrão: B (2D perceptual) com C no seletor, como recomendo?

---

## 3. Painel do Legislativo (futuro)

### O que mostrar

- **Lista de votações** de cada casa na legislatura, com filtro por tema, data e resultado, e link para a página
  oficial da proposição.
- **Votos por parlamentar** nas votações nominais (abertas). Votações simbólicas não têm voto individual, e no
  Senado ainda há votações secretas (indicação de autoridades, embaixadores etc.); a página deve dizer isso.
- **Análise por espectro**: votos de cada votação desenhados ao longo do eixo 1 (do bloco 2 e/ou das próprias
  votações); disciplina partidária (índice de Rice); alinhamento com a orientação do governo e do partido; um
  espectro próprio da legislatura, tirado da matriz parlamentar × votação (PCA ou um modelo de ponto ideal simples,
  feito em numpy).
- **Página por parlamentar**: foto, partido, UF, contato (e-mail, telefone do gabinete, redes), votos, percentual
  de alinhamento com o partido e com o governo, posição no espectro. **Suplentes** em exercício com link para o
  titular, e o titular com link para quem o substitui.

### Fontes

| Casa | Fonte | O que dá |
|---|---|---|
| Câmara | API REST `https://dadosabertos.camara.leg.br/api/v2` (`/votacoes`, `/votacoes/{id}/votos`, `/votacoes/{id}/orientacoes`, `/proposicoes/{id}`, `/deputados`, `/deputados/{id}`) e **arquivos anuais** em `https://dadosabertos.camara.leg.br/arquivos/` (CSV/JSON de votações, votos, orientações, proposições, deputados) | Tudo do painel. Os arquivos anuais evitam milhares de chamadas: baixa-se um por ano e o incremental pela API |
| Senado | API `https://legis.senado.leg.br/dadosabertos` (lista de senadores em exercício, detalhes, mandatos com titular e suplentes, votações do plenário, matérias) | Tudo do painel; o formato é mais irregular (XML/JSON aninhado) e tem versões de endpoints convivendo, então a primeira tarefa é um levantamento com exemplos reais |
| Congresso (sessões conjuntas, vetos) | Também nos dados abertos do Senado | Votações de vetos |

Links oficiais: ficha da proposição na Câmara (`camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=<id>`) e
página da matéria no Senado (`www25.senado.leg.br/web/atividade/materias/-/materia/<código>`).

**Suplentes.** No Senado é direto: cada senador tem dois suplentes, e os mandatos indicam quem está em exercício
no lugar de quem. Na Câmara a API diz que o deputado é suplente em exercício, mas não aponta o titular; ele sai
cruzando quem está afastado (licença, secretaria, ministério) com a ordem de suplência do TSE na mesma
federação/coligação e UF (dados da etapa 7). É um casamento heurístico que vou validar à mão no começo.

### Viabilidade

- **Rede**: este ambiente de desenvolvimento não acessa as APIs da Câmara e do Senado (testei em 03/11; o proxy
  bloqueia, como acontece com o TSE). Como na base do TSE, a coleta roda no **GitHub Actions**, com um workflow
  diário que baixa o incremental e grava JSON por votação e por parlamentar para o site estático.
- **Volume**: uma legislatura da Câmara tem da ordem de mil a dois mil votações nominais × 513 deputados, alguns
  milhões de linhas no total, mas cada página carrega só a sua votação ou o seu parlamentar. Cabe no Pages.
- **Esforço**: médio a alto. Câmara primeiro (API mais limpa), Senado depois. Estimo três threads: coleta; páginas
  de votações; páginas por parlamentar.

### Extensão para as assembleias estaduais (adendo do Tiago)

| Parte | Viabilidade |
|---|---|
| Composição das 27 casas (eleitos, partido, suplentes) | **Alta**: vem do TSE (deputados estaduais e distritais), já coberta pelo bloco 1 |
| Contato dos deputados estaduais | **Média**: cada assembleia publica em seu site, em formatos diferentes; exige um coletor por casa |
| Votações nominais | **Baixa e desigual**: não há padrão nacional. Algumas casas têm portais de dados abertos (Minas Gerais tem um dos mais completos; Pernambuco tem API, com pacote R `alepe`; São Paulo tem portal de dados abertos), mas a maioria vota de forma simbólica ou publica votos nominais só no diário oficial em PDF |

Proposta: antes de prometer qualquer painel estadual, fazer um **levantamento das 27 assembleias** (o que cada uma
publica, formato, se há votos nominais, se a coleta passa pelo Actions) e começar pelas 2 ou 3 com dados abertos de
verdade. Para as demais, mostrar só composição e contato.

### Decisões em aberto

6. Começar o bloco 3 pela Câmara só, ou já com as duas casas?
7. Espectro do painel: o das alianças (bloco 2), o das votações, ou os dois lado a lado? *Recomendo os dois.*

---

## Ordem sugerida

| Passo | O quê | Depende de |
|---|---|---|
| 1 | Tabela de sucessão de partidos e parser único de composições | Etapa 7 (base proporcional) entrar na `main` |
| 2 | Base de 2026 (governador, senador, deputados) | Arquivos consolidados do TSE |
| 3 | Grafo de alianças, eigenmap + análise de correspondência, validação | 1 |
| 4 | Páginas de distribuição por partido e mapas de prevalência coloridos pelo espectro | 1–3 |
| 5 | Coleta da Câmara e do Senado pelo Actions | — (independente) |
| 6 | Painéis de votações e por parlamentar | 3, 5 |
| 7 | Levantamento das assembleias e painéis estaduais onde houver dados | 5–6 |

---

## Decisões do Tiago (03/11/2026)

| # | Decisão |
|---|---|
| 1 | Foto "como saiu das urnas" primeiro; "como está hoje" depois |
| 2 | Mapas de prefeito e governador com os dois pesos (por cargo e por eleitorado), com seletor |
| 3 | Pesos por nível e meia-vida propostos aceitos como ponto de partida, com revisão depois de ver o resultado |
| 4 | Arestas negativas (adversários) como variante, para medir o impacto |
| 5 | Esquemas de cor como opções no painel (seletor); padrão a definir ao ver os mapas |
| 6 | Painel do Legislativo com as duas casas (Câmara e Senado) |
| 7 | Os dois espectros (alianças e votações) lado a lado |

Assembleias estaduais e Câmara Legislativa do DF: por ora, só o levantamento de quais casas permitem o painel. O
foco inicial é o nível federal.
