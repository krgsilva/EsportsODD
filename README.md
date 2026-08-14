# Painel de Odds — LoL (local, sem rate limit)

Ferramenta local (roda no seu computador, `localhost`) que lê o histórico
de partidas de League of Legends de um arquivo CSV baixado da Oracle's
Elixir e monta comparações no estilo do gol.gg. Duas abas:

- **Confronto (2 times)**: escolhe os dois times e recebe automaticamente
  o comparativo completo, **em abas por mercado** (Win Rate, First Blood,
  First Tower, First Dragon, First Herald, First Nashor, Most Kills, Total
  Kills, Total Towers, Total Dragons, Total Nashors, Total Inhibitors, Game
  Time) — cada aba com Overall (+ lado azul/vermelho), Recent Form
  (últimos 5/10, jogo a jogo) e Past Faceoffs (confronto direto).
- **Análise de Campeonato**: escolhe o campeonato e vê a tabela com todos
  os times dele lado a lado.

⚠️ **Isso é uma ferramenta de apoio estatístico, não uma certeza.** Ela não
considera roster atual, meta/patch mais recente que o arquivo baixado, nem
lesões/trocas de jogadores. Use como mais um dado na sua análise. Aposta
envolve risco financeiro — jogue com responsabilidade.

## Por que mudou pra um arquivo local

As versões anteriores buscavam os dados ao vivo na Leaguepedia, mas o
limite de requisições deles (~1 por minuto por IP, e às vezes bloqueios
mais longos) tornava o app praticamente inutilizável na prática. A
Oracle's Elixir disponibiliza os mesmos dados (e mais: inclusive quem fez
o primeiro abate/torre/dragão/arauto/barão, jogo a jogo) num arquivo CSV
que você baixa uma vez. Com isso, o painel roda 100% local, instantâneo, e
nunca mais dá erro de rate limit.

## 1. Baixar o arquivo de dados (só isso já resolve o problema do limite)

1. Acesse https://oracleselixir.com/tools/downloads
2. Clique no link azul **"Google Drive"** no fim da página
3. Baixe o CSV do ano que quiser (ex: 2026)
4. Salve como `data/oracles_elixir.csv` (veja `data/LEIA-ME.txt`)

Pra atualizar depois (o arquivo é atualizado 1x/dia por eles), é só baixar
de novo e substituir — o painel percebe sozinho que o arquivo mudou.

## 2. Instalar

Python 3.9+ necessário. No terminal, dentro desta pasta:

```bash
pip install -r requirements.txt
```

## 3. Rodar

```bash
python app.py
```

Abra **http://localhost:5000** no navegador. Se o CSV ainda não estiver
no lugar certo, o app mostra a tela de configuração com o passo a passo —
depois de salvar o arquivo, clique em "verificar" (não precisa reiniciar).

## 4. Usar

Tudo por lista suspensa, sem digitar nada, e tudo instantâneo (nenhuma
consulta à internet acontece depois que o CSV está carregado).

### Aba "Confronto (2 times)"

1. Escolha o **ano** e o **campeonato**.
2. Escolha **Time 1** e **Time 2**.
3. Escolha quantos jogos recentes considerar.
4. Clique em **Comparar times**.

O resultado vem com um placar de confronto direto no topo, e depois **abas
por mercado**. Cada aba mostra:
- **Overall**: taxa/média geral, e por lado azul/vermelho.
- **Recent Form**: últimos 5 e 10 jogos, com a sequência jogo a jogo
  (✓/✗ ou o valor — passe o mouse pra ver data e adversário).
- **Past Faceoffs**: o mesmo recorte, só nos jogos entre os dois times
  selecionados.

Como os dados vêm da Oracle's Elixir (que registra quem fez a primeira
jogada em cada partida), **First Blood/Tower/Dragon/Herald/Nashor também
têm Recent Form e Past Faceoffs completos** — não é só uma média geral.

Dentro da aba **Total Kills**, tem também **Total Kills até 10 min** e
**até 15 min** (soma dos dois times), com o mesmo Overall/Recent
Form/Past Faceoffs.

Dentro da aba **Game Time**, tem o **"Game Time LIVE"**: assim que o
draft ao vivo fechar (os 10 campeões escolhidos), selecione os 5
campeões de cada time e o app calcula a duração estimada da partida —
usando a média histórica de duração de cada campeão especificamente com
aquele time (ou a média geral do campeão, se o time nunca jogou com ele
antes), e tira a média dos 10 picks.

### Aba "LoL — Ao Vivo"

Essa aba é diferente das outras: ela **precisa de internet**, porque busca
direto na API pública que o próprio lolesports.com usa (a mesma API por
trás do site oficial — não é scraping de terceiro, e não tem termos de
uso proibindo, diferente do vlr.gg/rib.gg).

1. Clique em **atualizar lista de jogos ao vivo**.
2. Escolha a partida na lista (se o time não bater com nenhum time do seu
   CSV local, avisa com um ⚠).
3. O app busca sozinho o minuto atual, placar de kills, diferença de ouro
   e o draft (5 campeões de cada lado), e calcula a **linha justa agora**
   — a mesma lógica da "Linha ao vivo de Kills" do Confronto, só que
   alimentada automaticamente em vez de você digitar. Atualiza sozinho a
   cada 30 segundos.

⚠️ Essa API não é documentada oficialmente pela Riot — funciona porque é a
mesma que o site deles usa, mas pode mudar de formato sem aviso. Se parar
de funcionar do nada, é isso que provavelmente aconteceu (não é bug do
app).

### Aba "Análise de Campeonato"

Escolhe ano + campeonato e a tabela carrega na hora com todos os times:
jogos, vitória %, duração, First Blood/Tower/Dragon/Herald/Nashor %, ouro,
kills, mortes, torres, dragões, barões, e % de jogos acima de várias
linhas comuns pra cada mercado.

## Sobre a fonte de dados

Os dados vêm da [Oracle's Elixir](https://oracleselixir.com), mantida pela
comunidade, cobrindo LCK, LPL, LEC, LCS/LTA, CBLoL e a maioria das ligas
oficiais de LoL. O arquivo é atualizado uma vez por dia — então um jogo de
hoje só aparece no painel depois que você baixar a versão mais nova do
CSV.

**Valorant:** a Oracle's Elixir é específica de League of Legends. Pra
Valorant seria necessário outra fonte de dados. Posso adaptar o painel
depois, se quiser.

## Aba Valorant (VCT)

Uma terceira aba compara 2 times de Valorant, lendo o dataset "Valorant
Champion Tour Data" do Kaggle (por ryanluong1) — igual à Oracle's Elixir,
mas pro Valorant: baixado uma vez, sem internet, sem scraping.

**Por que não é ao vivo do vlr.gg:** cheguei a pesquisar isso, mas os
Termos de Uso do vlr.gg proíbem explicitamente bots/scrapers automatizados
— então essa aba usa o dataset do Kaggle, que é público e feito pra isso.

### Como ativar

1. Acesse https://www.kaggle.com/datasets/ryanluong1/valorant-champion-tour-2021-2023-data
   (conta gratuita no Kaggle necessária)
2. Baixe o dataset completo (.zip) e extraia
3. Copie as pastas dos anos que quiser (ex: `vct_2026`) para dentro de
   `data/valorant/` — veja `data/valorant/LEIA-ME.txt`
4. Na aba Valorant do app, clique em "JÁ COLOQUEI OS ARQUIVOS — VERIFICAR"

### O que tem nessa aba

- **Win Rate**: taxa de vitória por mapa (nos jogos analisados, últimos 5,
  últimos 10) de cada time, e confronto direto completo entre os dois
  (histórico inteiro, igual fizemos no LoL).
- **Mapas**: escolhe um mapa específico (Haven, Bind, Pearl...) e vê,
  pra cada time: vitórias/derrotas nesse mapa, e a tabela dos 5 jogadores
  com agente mais jogado, rating, ACS, médias de kills/mortes/assistências,
  ADR e HS% naquele mapa.

Cada ano do dataset é uma pasta grande (dezenas a centenas de MB) — só
coloque os anos que for realmente analisar.

### Stats ao vivo (dentro da aba Valorant)

Como o dataset do Kaggle não é atualizado na mesma hora que os jogos
acontecem, tem uma seção extra na aba Valorant — "Stats ao vivo" — que lê
um arquivo que **você mesmo mantém atualizado** (ex: copiando uma tabela
de estatísticas do vlr.gg periodicamente e salvando como .csv).

Coloque o arquivo em `data/valorant_live/` — veja o
`data/valorant_live/LEIA-ME.txt` pra saber o formato exato. Toda vez que
você substituir o arquivo por uma versão mais nova, o app já reflete os
dados novos sozinho, sem precisar reiniciar.

**Limitações desse formato:** a coluna de agentes vem só com as
porcentagens de pick (ex: "56% 33% 11%"), sem os nomes dos agentes — isso
se perde ao copiar a tabela do site original (lá são ícones, não texto).

## Estrutura do projeto

```
esports-odds-analyzer/
├── app.py                # backend Flask: LoL + rotas de Valorant
├── valorant_data.py       # backend: dataset VCT do Kaggle
├── valorant_live_data.py  # backend: CSV "ao vivo" que você atualiza
├── requirements.txt
├── data/
│   ├── LEIA-ME.txt          # como baixar os dados de LoL
│   ├── oracles_elixir.csv   # você adiciona esse arquivo (LoL)
│   ├── valorant/
│   │   ├── LEIA-ME.txt      # como baixar os dados de Valorant (Kaggle)
│   │   └── vct_2026/        # você adiciona essas pastas (Valorant)
│   └── valorant_live/
│       ├── LEIA-ME.txt      # formato do CSV "ao vivo"
│       └── *.csv            # você adiciona e atualiza esse(s) arquivo(s)
├── static/
│   ├── index.html      # interface
│   ├── style.css
│   └── script.js
└── README.md
```

## Se algo der errado

- **Tela de "configuração necessária"**: o arquivo `data/oracles_elixir.csv`
  (LoL) ou as pastas em `data/valorant/` (Valorant) ainda não foram
  encontrados — siga os passos na própria tela.
- **"Nenhum campeonato/time encontrado"**: o ano/campeonato escolhido pode
  não estar no arquivo que você baixou (baixe o ano certo, ou confira se o
  arquivo salvou certo).
- Quer mais mercados, mudar as linhas padrão, juntar vários anos, ou
  guardar seu histórico de apostas? É só pedir — dá pra estender o
  `app.py` facilmente, e agora sem se preocupar com limite de requisições.
