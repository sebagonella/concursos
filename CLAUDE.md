# CLAUDE.md

Orientação para o Claude Code trabalhando neste repositório.

## Vault Obsidian
- **Vault:** /home/sebagonella/work/cloud/1_insync-gdrive-sebastiao.gonella/02_SYNC-ALIVE/01_COFRES/02_NOTEBOOKS/02_OBSIDIAN/0_sebagonella2
- **Nota do projeto:** 20_PROJETOS/PROFISSIONAL/14_concursos/_PROJETO.md
- **Sessoes:** 20_PROJETOS/PROFISSIONAL/14_concursos/SESSOES/
- **Decisoes:** 20_PROJETOS/PROFISSIONAL/14_concursos/DECISOES/
- **Pesquisas:** 20_PROJETOS/PROFISSIONAL/14_concursos/PESQUISAS/
- **Tarefas:** 20_PROJETOS/PROFISSIONAL/14_concursos/TAREFAS/

## O que é este projeto

Coleção de **skills do Claude Code** que automatizam a preparação para concursos públicos brasileiros, gerando conteúdo estruturado direto num **vault Obsidian**.

O fluxo tem três etapas encadeadas, mais uma camada opcional:

1. **`concurso-prep`** (Etapa 1) — a partir de um edital (PDF/DOCX/MD), monta a estrutura completa de estudos: cronograma, mapas por matéria, análise da banca, histórico do órgão, materiais (leis baixadas em MD+PDF), sinergias entre concursos. Suporta concurso *previsto* (sem edital ainda) e *reconciliação/retificação* quando o edital sai ou muda.
2. **`concurso-aprofunda`** (Etapa 2) — consome a saída da Etapa 1 + um livro de referência denso. Localiza cada assunto no livro, gera um `.md` por assunto (resumo próprio + ponteiros de página + citações curtas), flashcards nativos e o pacote para gerar podcast/mapa mental/vídeo/report no NotebookLM.
3. **`concurso-publica`** (Etapa 3) — transforma a pasta de um concurso em **site estático** que espelha a organização do vault (`{concurso}/{comum|cargo}/`) e publica **todo** o conteúdo abaixo do concurso: edital, cronograma, mapas de matéria, materiais e leis, histórico, sinergia, discursiva, títulos e o aprofundamento, com mídias embutidas, quiz de flashcards e uma página por assunto para o pacote NotebookLM. Cada matéria abre em duas visões — **Plano** (o mapa do edital) e **Estudo** (os assuntos aprofundados). Decisões travadas: gerador próprio em Python (sem Node), por concurso, uso local/rede doméstica, **site só leitura** (progresso lido do vault na geração; o vault é a única fonte de verdade), link NotebookLM apenas se `notebooklm_url:` preenchida (sem iframe do Google).
4. **`concurso-notebooklm`** (camada opcional sobre a Etapa 2) — **executa** os pacotes que a `concurso-aprofunda` preparou: cria o notebook, sobe as fontes, gera as mídias e salva os arquivos com o nome que a `concurso-publica` detecta. Roda **sob demanda**, por assunto ou por matéria. A biblioteca usada (`notebooklm-py`) **não é oficial** e quebra sem aviso, então a automação é sempre **opcional** e o modo manual segue completo.

O repositório é versionado no GitHub e instalado localmente no Claude Code do usuário.

## Estrutura

```
skills/
├── concurso-prep/          # Etapa 1 — edital → estrutura de estudos
│   ├── SKILL.md            # orquestrador (fluxo de 10 etapas)
│   ├── agents/             # 5 subagents especializados
│   ├── assets/templates/   # templates .md.tpl
│   ├── scripts/            # utilitários Python
│   └── examples/
├── concurso-aprofunda/     # Etapa 2 — livro → assuntos aprofundados
│   ├── SKILL.md
│   ├── assets/templates/
│   ├── scripts/
│   └── examples/
├── concurso-publica/       # Etapa 3 — concurso → site estático
│   ├── SKILL.md
│   ├── assets/             # site.css, site.js (sem CDN: o site roda offline)
│   ├── scripts/            # site_collector.py, site_builder.py, md2html.py
│   └── examples/           # site-model-exemplo.json (contrato coletor→builder)
└── concurso-notebooklm/    # camada opcional — executa os pacotes no NotebookLM
    ├── SKILL.md
    └── scripts/            # pacote.py (contrato) e plano.py (o que gerar)

scripts/install.sh          # instalador único (instala/atualiza todas as skills)
scripts/test-all.sh         # roda as suítes de todas as skills + as de shell
scripts/tests/              # suítes dos scripts de shell (os que mexem no ambiente)
├── test_install.sh         # instalação/desinstalação, incluindo os subagents
└── test_deploy.sh          # deploy com ssh/rsync/docker stubados, sem tocar a rede
deploy/                     # Docker + rsync para servir o site num servidor doméstico
├── docker-compose.yml      # nginx:alpine, bind mount, ${CONCURSOS_PORTA:-8099}, 0.5 CPU / 128 MB
├── nginx.conf              # serve na raiz em concursos.casa:8099
├── deploy.sh               # reconstrói o build do vault e sincroniza via SSH
└── README.md               # instalação, troca de porta e troubleshooting
docs/
├── ARQUITETURA.md          # decisões de projeto e o porquê + diagrama do fluxo
├── SETUP-VAULT.md          # preparar o vault Obsidian
├── fluxo-concurso.mmd      # fonte Mermaid do diagrama (o README renderiza o bloco)
└── fluxo-concurso.png      # export do .mmd, para onde o Mermaid não renderiza;
                            # regerar junto ao editar o .mmd (comando no cabeçalho dele)
```

> O índice navegável de toda a documentação está no [`README.md`](README.md#documentação).

## Comandos

```bash
# Instalar/atualizar TODAS as skills (global, em ~/.claude/)
bash scripts/install.sh

# Instalar só uma
bash scripts/install.sh --only concurso-aprofunda

# Instalação local (no .claude/ do diretório atual)
bash scripts/install.sh --local

# Desinstalar
bash scripts/install.sh --uninstall

# Rodar os testes de todas as skills
bash scripts/test-all.sh

# Publicar o site no servidor doméstico (Docker + rsync)
./deploy/deploy.sh --setup                              # 1ª vez
./deploy/deploy.sh --concurso-dir <.../SEDES_2026>      # atualizações
./deploy/deploy.sh --concurso-dir <...> --dry-run       # conferir antes
./deploy/deploy.sh --concurso-dir <...> --so-este       # nao reconstruir os outros
```

> Após instalar/atualizar, **reinicie a sessão do Claude Code** — ele carrega as skills no início da sessão e pode manter a versão anterior em cache.

## Convenções invioláveis

Estas regras vieram de bugs reais. Quebrá-las volta a quebrar coisas.

- **Slugs em UPPERCASE** para pastas de concurso e cargo: `SEDES_2026`, `EDAS-ADMINISTRACAO`, `_COMUM`. O validador checa isso.
- **Path canônico do aprofundamento** — um assunto pode ter vários, cada um na sua pasta:

  ```
  30_AREAS/CARREIRA/CONCURSOS/{ORGAO}_{ANO}[_PREVISTO]/{_COMUM|CARGO}/
  └── 03-APROFUNDAMENTO/{slug-materia}/assuntos/{slug-assunto}/
      └── {padrao|detalhado}--{fonte1}[+{fonte2}]/
          └── {slug-assunto}--{padrao|detalhado}--{fonte1}[+...]--{CONCURSO}.md
  ```

  **Cada componente existe porque diferencia alguma coisa** — nível diferencia profundidade, fonte diferencia origem, concurso diferencia contexto. Não acrescente campo que não desempata: contador de fontes e índice posicional (`2f`, `f1-`) foram removidos justamente por serem deriváveis. O slug da fonte é o **sobrenome de um autor** (`pestana`, `kotler`) ou o **identificador da norma** (`lei-8742`, `lc-105`, `leidf-6938`, `res-cmn-4893`); alteração posterior da mesma norma não conta como fonte extra. A regra vive em `skills/concurso-aprofunda/scripts/aprofundamento_id.py`, **fonte de verdade**, com cópia sincronizada em `concurso-publica` barrada por teste. Não reimplemente a convenção em outro lugar.
- **A fonte fica no nome mesmo quando é única, e o concurso sempre**: omitir a fonte obrigaria a renomear o aprofundamento quando surgisse a segunda — e renomear quebra wikilink e progresso. O concurso resolve colisão real entre concursos que usam o mesmo livro.
- **Acrescentar fonte é renomear, e a renomeação quebra sete coisas**: como o id *é* o conjunto de fontes e o id *é* o path, `padrao--pestana` → `padrao--pestana+rosenthal` é a única forma. Quem faz isso é `ampliar_aprofundamento.py`, que **move primeiro e regenera o pacote depois** — invertido, `herdar_campos()` não enxerga o `notebooklm_url` e o link do notebook some em silêncio. A pior das sete é invisível: `executor.garantir_fontes` sobe fonte **pelo nome e só adiciona**, então o notebook fica com a nota antiga *e* a nova e passa a gerar mídia sobre material contraditório — vira pendência nomeada, nunca conserto automático (esta skill não importa `notebooklm-py`).
- **A ordem das fontes é significativa e nunca canonicalizada**: `a+b` e `b+a` são pastas diferentes, e ordenar alfabeticamente renomearia material que ninguém pediu (4 pastas do vault já não estão em ordem). Fonte nova entra **no fim**, o que mantém o prefixo do id estável e espelha a cronologia. Conjunto igual em outra ordem é pendência, não escolha silenciosa.
- **Localização é por fonte, em chaves numeradas**: a fonte 1 fica em `localizacao_livro` e as demais em `localizacao_2`, `localizacao_3`. Chave única com `;` não serve — os ponteiros reais contêm `;` dentro deles. E **nada é obrigado a ser parseável**: 61 dos 122 valores do vault são prosa livre, e `extrair_paginas` já falha neles; quem quiser página tenta extrair e **degrada**, nunca exige o formato.
- **Em norma, o `book_index` é triagem, não localização — e "média" ali é o teto, não um juízo.** O PDF de uma lei do Planalto não tem sumário (`toc_entradas: 0`), então o script cai na busca por densidade; e `CONF_ALTA` **só existe no caminho `toc`** (linha 219), enquanto a densidade termina em `CONF_MEDIA if melhor_d >= 0.35 else CONF_BAIXA` (linha 249). Ou seja: por densidade é **matematicamente impossível** sair "alta", com qualquer score. Ler aquele `media` como dúvida sobre a fonte é erro de interpretação — e o defeito real nem é a etiqueta, é o **ponteiro**: na Lei 11.340 a densidade devolveu `pp. 1–9` para **8 dos 10** assuntos, num documento de **9 páginas**. Ponteiro que aponta para tudo não aponta para nada. A referência real de uma norma é o **artigo**: extraia com `pdftotext`, monte o mapa artigo→página, confira, e grave `confianca: alta` com `metodo: "mapeamento por artigo"` — a nota fica auditável porque o método está ao lado dela. É barato (a lei tem 9 páginas) e é o que os 10 aprofundamentos do `_COMUM` já faziam antes de a regra existir.
- **Tópico multi-fonte é o desenho do edital, não descuido do mapa**: o literal do tópico 2 do EDAS diz "Lei Maria da Penha **e** Política Nacional de Enfrentamento" — o "e" são duas fontes, e a Política Nacional tem **zero** ocorrências nas 10 páginas da lei. O `Material recomendado` do mapa listava só a norma, e seguir o mapa ao pé da letra teria deixado 2 dos 10 assuntos sem fonte. Antes de aprofundar, **leia o literal do edital** e confira se cada parte dele tem fonte no vault; o que não tiver vira aprofundamento de identidade própria (`padrao--pdpm`, `padrao--lei-14994+lei-13104`) ou pendência nomeada — nunca conteúdo escrito sob uma fonte que não o sustenta.
- **Flashcards se acrescentam, nunca se regeneram numa mescla**: o plugin Spaced Repetition ancora o histórico de revisão no **texto da frente** do cartão. Reescrever a frente zera o histórico do usuário sem apagar arquivo nenhum — é perda de trabalho que não deixa rastro.
- **Slug derivado é sempre ecoado, não só quando suspeito**: `slug_suspeito()` tem ponto cego. Um PDF com nome corrompido deriva `indleycintra` — plausível, errado e aprovado —, e o erro só apareceria depois de a pasta existir.
- **Nome de arquivo repete o identificador do aprofundamento**: o Obsidian resolve wikilink por *nome de arquivo*, então dois `crase.md` em pastas diferentes ficam ambíguos. Todo script que gera artefato de aprofundamento (`.md`, flashcards) precisa receber o nome-base — foi exatamente daí que veio o bug do `flashcards_gen.py`.
- **Mover material no vault reescreve wikilink**: os índices de matéria (`00-INDICE-*.md`) ficam **fora** de `assuntos/` e apontam para o path completo. Migração que só move pasta deixa o vault cheio de link quebrado.
- **Metadata em `.meta.json`** (não YAML). Deve conter o **conteúdo programático integral** (`materias[].topicos`) — o motor de diff depende disso — e o `edital_hash` (SHA-256) para detectar edital alterado.
- **Nunca sobrescrever versão anterior** numa reconciliação. Gera-se `V1-PREVISTO` → `V2-OFICIAL` → `V3-RETIFICADO`, lado a lado, preservando o progresso do usuário.
- **Direitos autorais (Modelo 2)**: a Etapa 2 **não** extrai o texto integral de livros protegidos. Do livro entram apenas localização (páginas) e **trechos curtos citados**. O resumo é sempre original, escrito do zero. Não relaxar isso.
- **Flashcards do Obsidian**: no formato multi-linha, o `??` precisa ficar **sozinho na própria linha** entre pergunta e resposta. Colado na resposta, o plugin Spaced Repetition não lê o cartão.
- **Nunca fingir precisão**: localização de assunto com baixa confiança ou não encontrada vira **pendência explícita** para conferência humana. Não inventar página.
- **O site é derivado, o vault é a fonte**: a `concurso-publica` nunca escreve no vault. O progresso exibido no site vem dos checkboxes dos `.md` e é **só leitura** — não criar um segundo lugar onde o progresso vive.
- **O site espelha COMUM/cargo**: a estrutura de saída é `{concurso}/{comum|cargo}/`, como as pastas do vault. `00-INDICE.md` e `99-Status.md` são **derivados, não republicados** — a navegação do site é o índice, e os checkboxes do status entram na barra de tarefas do escopo. Mas eles continuam sendo *lidos*: é de lá que saem a ordenação das matérias e os selos de questões/prioridade.
- **Progresso é barra, em todo lugar.** A bolha do cartão-resposta deixou de medir progresso: ela sobrevive como selo de nível (meia = padrão, cheia = detalhado) e como marcador das listas de tarefa. Duas tentativas anteriores falharam pelo mesmo motivo — `min(total, max_bolhas)` fazia 8 bolhas valerem 303 tarefas, e depois barra na matéria com bolha no assunto punha o **mesmo número com duas aparências em telas vizinhas**. Escopo e matéria usam **duas barras lisas empilhadas, sempre na mesma ordem**: tarefas de estudo (verde `--confere`, o visto de concluído) em cima, tópicos do edital (azul `--tinta`, a caneta que escreveu o material) embaixo; o assunto usa uma só, a de tarefas. Trocar a ordem ou a cor num lugar só torna as caixas incomparáveis, que é exatamente o defeito.
- **Tarefas de estudo é tudo o que há para marcar** — assuntos (a **união** dos aprofundamentos, não só o principal) + os **itens do plano do mapa** + documentos de seção + `99-Status.md`, somados em `progresso_tarefas`. Cada exclusão aqui já escondeu trabalho: contando só os assuntos, os cargos apareciam sem barra tendo 21, 17 e 8 tarefas em documentos; contando só o aprofundamento principal, sumiam 181 checkboxes em 29 assuntos. **Os mapas ficaram de fora na 0.17.0 e voltaram na 0.18.0** — o argumento de que 1.998 itens nunca marcados afogariam as ~200 reais estava errado, porque "Ler as páginas" e "Resolver 30 questões" são a mesma espécie de trabalho, e a exclusão deixava **12 das 22 matérias sem barra nenhuma**. Denominador grande e verdadeiro ganha de pequeno e mudo.
- **O mapa conta para quem guarda o arquivo.** `cruzar_materias_comuns` anexa o mapa do cargo à matéria irmã do `_COMUM`, então a matéria com `mapa_em` **não** soma os itens do plano: somar dos dois lados contaria 237 em dobro só no comum do SEDES. É a mesma regra da tarefa herdada, e o resto das parcelas não se sobrepõe por construção — o `99-Status` fica fora das pastas de `SECOES`, e a seção herdada do `_COMUM` é ponteiro com `documentos: []`.
- **Matéria com aprofundamento tem aba Estudo, mesmo que o material more no comum.** `tem_estudo` olhava só `materia["assuntos"]`, e a matéria do cargo tem a lista vazia quando o mapa é dele e o material é do `_COMUM` — três matérias do SEDES ficavam só com o Plano enquanto a cobertura já afirmava 40%, 60% e 25%. Os assuntos da irmã entram em `assuntos_herdados`, **chave à parte que a agregação de progresso ignora**: copiá-los para `assuntos` faria os mesmos checkboxes contarem nos dois escopos. Matéria só-com-mapa e **sem** irmã segue sem Estudo, que é o caso legítimo de 9 matérias.
- **Documento longo no topo de uma aba esconde o que a aba existe para mostrar**: a bússola `COMO-A-BANCA-COBRA` é o primeiro bloco da visão Estudo e era publicada inteira e aberta. Medido: **2.770px** de bússola empurravam o primeiro grupo de assuntos para **3.131px** — **2,3 telas** numa janela de 1.321px —, e o relato foi "o tópico **nem existe** dentro de Estudo". Existia. O incentivo ficava invertido: **quanto melhor o documento, mais ele escondia a lista** (as duas matérias com bússola tinham 5.976 e 7.424 chars antes do primeiro assunto; as sem bússola, 64 e 101). Documento de apoio no topo de uma aba vai em `<details>` **fechado**, com título no `<summary>` — nativo, sem JS, e `@media print` reabre. E a lição de verificação: **"o HTML contém o elemento" não é "a pessoa vê o elemento"** — depois de publicar, meça **posição**, não só presença.
- **Asset publicado leva a versão do conteúdo na URL** (`site.css?v=<hash>`). O nginx manda `expires 1h`, então sem isso o navegador serve **HTML novo com CSS velho** — e o defeito é invisível, porque a página renderiza, só renderiza errado: foi assim que os rótulos das barras saíram no tipo do corpo e a cobertura saiu verde depois de já ser azul no servidor.
- **Barra ausente, vazia e desconhecida são três coisas**: some só quando o medido não existe (cobertura sem mapa nenhum); vem vazia com o trilho à vista quando existe e está em zero (`0/48`, nunca `0/0`); vem **hachurada e escrita** quando existe e não se pode saber (`vinculo_ausente`). Matéria sem vínculo **nunca** entra no denominador agregado — é o falso zero já proibido no link tópico↔assunto, agora em escala de escopo, onde uma matéria arrastaria a barra de um cargo inteiro.
- **Tarefa pertence a quem guarda o arquivo; cobertura pertence a quem tem o edital.** A barra de tarefas de uma matéria conta só os assuntos **próprios** — matéria "aprofundada no comum" não repete os checkboxes do `_COMUM` no cargo, senão o mesmo trabalho conta duas vezes e nenhum total fecha. A cobertura é o oposto: o tópico é do edital **do cargo**, então a matéria emprestada entra sim no denominador dele.
- **Nunca inferir o link mapa↔assunto por slug**: dos 203 tópicos dos 24 mapas do vault, ~18% casam. Um tópico do edital pode cobrir vários assuntos, aprofundamento por legislação é N:M, e assunto reaproveitado de outro concurso mantém o slug do edital de origem. Sem casamento exato, a página **não afirma nada** — o falso negativo ("sem aprofundamento" quando existe com outro nome) esconde trabalho feito. O link fino vem de `mapa-aliases.json`, opcional.
- **Nada escrito no tópico do mapa se perde em silêncio**: rótulo de H3 fora do template é **publicado** (com o texto do vault) **e avisado** na geração — publicar sem avisar esconde que template e vault divergiram, avisar sem publicar foi o bug que sumiu com 50 blocos (`Leis-chave`, mnemônicos 🧠). Rótulo repetido no mesmo tópico **acumula**, nunca sobrescreve: guardar as subseções num dict chave→markdown perdia 57 subtópicos em 5 tópicos. E **a lista exibida tem de contar o mesmo que o contador do rodapé** — foi a contradição (1 item listado sob `0/22 itens do plano`) que denunciou o defeito, e há teste que trava o invariante.
- **Cobertura é contagem; qualidade não se inventa**: a % de tópicos com aprofundamento sai do `topico_id` gravado, e as lacunas aparecem **por nome**. Nota sintética de qualidade foi descartada por medição — no vault os sinais que a comporiam estão saturados (placeholders em 0 arquivos, `status` `revisar` em todos, `confianca baixa` em 0 de 92), então a nota seria constante disfarçada de métrica. Mostra-se o que **existe** (cards, âncoras, nível). E matéria com assuntos sem vínculo tem cobertura **desconhecida**, nunca zero.
- **O arcabouço nunca sobrescreve conteúdo**: `build_subject_md.py` pula assunto que já tem `.md` e só regenera com `--forcar`, fazendo backup. O `.md` é onde mora o resumo escrito à mão.
- **Selo de mídia no card só para o que existe**: mostrar os 8 tipos com os ausentes em cinza são 88 ícones numa matéria de 11 assuntos. A grade completa fica na página do assunto, onde "falta gerar" é acionável.
- **Índice de nomes é para wikilink; navegação é calculada**: o índice resolve por basename e nomes repetem entre escopos (`lingua-portuguesa` no comum e em cada cargo). Link de navegação sai sempre da rota da própria página — usar o índice fazia o hub do cargo apontar para a matéria do comum e deixava a própria órfã.
- **Fixture tem de espelhar a saída real da skill anterior**: dois defeitos ficaram verdes por anos porque o fixture inventava o que o gerador não produz — assuntos sob `03-MAPAS-MATERIAS` (a `concurso-aprofunda` usa `03-APROFUNDAMENTO`) e uma chave `notebooklm_url` que o template nunca escrevia. Fixture divergente é teste que se autoconfirma.
- **Cores só via variáveis de tema**: nada de hex fixo para cor de texto no CSS, senão o tema escuro quebra (já aconteceu com `strong`). Toda variável precisa existir nos dois temas — há teste que barra isso.
- **Deploy é sincronização, e por isso reconstrói o build inteiro**: o container usa bind mount; atualizar o site é rsync, sem rebuild de imagem nem restart — isso não muda. O que mudou é que **o escopo do build tem de alcançar o do envio**: o `--concurso-dir` nomeia um concurso, mas o envio é `rsync --delete` do `out/site/` inteiro, e esse diretório acumula. Construir só o concurso pedido republicava os demais com o conteúdo da sessão em que foram gerados, **sem aviso** — aconteceu com o `BB_2027_PREVISTO` enquanto se publicava o `SEDES_2026`. Hoje o deploy reconstrói **todos** os concursos do build antes de enviar, achando a origem de cada um no campo `origem` do `.concurso.json`; manifesto antigo sem o campo cai na pasta irmã, **com o palpite ecoado**. Concurso cuja origem sumiu é republicado como está e **avisado duas vezes** (no começo e no fim, porque aviso no meio de saída longa não se lê) — o script nunca escolhe sozinho entre publicar velho e despublicar bom. `--so-este` pula a reconstrução dos outros, avisando. E **não** apague o `out/site/` para forçar um só: o envio é `--delete` do build inteiro, então um build com um concurso **remove os outros do servidor** — o diretório é espelho do que está publicado, não cache descartável. Coberto por `scripts/tests/test_deploy.sh`; detalhe em `deploy/README.md`.
- **Preservar trabalho do usuário**: re-execuções não apagam resumos, flashcards ou progresso. Scripts que sobrescrevem artefatos do usuário devem fazer backup — e **num lugar só**: quem faz é `notebooklm_pack.py`, que copia para `.bak.md` apenas quando o conteúdo mudou. O wrapper `fix_notebooklm_packs.py` duplicava esse backup incondicionalmente e o resultado era sobrescrito logo depois.
- **Regra de layout mora no gerador, nunca copiada**: `fix_notebooklm_packs.py` reimplementava a busca do `.md` do assunto e ficou preso no formato plano legado — achava **zero** dos 158 pacotes do vault e saía com sucesso. Quem varre pastas de aprofundamento usa `pastas_de_aprofundamento()`/`arquivo_principal()`, e não achar nada **falha alto**. **Isso vale também para script de análise descartável**, e não só para o que entra no pacote: uma comparação ad-hoc entre escopos pegou `sorted(glob("*.md"))[0]` e leu o **`_fonte-notebooklm.md`** em vez do assunto — `_` (95) ordena antes das minúsculas —, o que fez o relatório afirmar 17 artigos ausentes onde havia **8**, e subestimar o material já escrito. `arquivo_principal()` já filtra `flashcards-`, `_`, `00-`, `report-`, `teste-` e `tabela-`; reimplementar é repetir o bug, mesmo num script que se joga fora depois.
- **O prompt do NotebookLM aponta para a nota do vault, nunca para o livro**: subir o recorte da obra é opcional, então prompt que a nomeia manda o modelo consultar fonte que pode não estar no notebook. A cláusula sai de `clausula_fonte()`, num lugar só, e há teste que varre **todos** os blocos gerados procurando `.pdf`, página, capítulo ou termo que só o `fontes:` conheça.
- **O que a automação consome é contrato, não prosa**: `nome_notebook` e `arquivo_*` vivem no frontmatter do pacote. Extrair nome de arquivo por regex de texto corrido foi o que fez o roteiro do mapa mental e o do report chegarem vazios ao site.

## Ao evoluir uma skill

1. **Plano antes de implementar.** O dono do repo revisa planos e listas de gaps antes de qualquer código. Apresente o plano e espere aprovação.
2. **Testes**: cada skill tem `scripts/tests/test_smoke.py`, que roda standalone (sem pytest); os scripts de shell têm suíte própria em `scripts/tests/test_*.sh`, que o `test-all.sh` também roda. Toda correção de bug ganha um teste que o reproduz — e vale conferir que ele **falha** contra o código antigo, senão é só decoração.
3. **Versionamento**: SemVer em **três** lugares, que o CI confere batendo um contra o outro — frontmatter do `SKILL.md`, linha `Versão atual:` do `README.md` da skill e topo do `CHANGELOG.md`. Esquecer o README é fácil justamente porque ele não parece metadado; foi assim que a 0.14.0 quebrou o CI.
4. **Higiene de pacote** antes de fechar uma versão: sem `__pycache__`, sem arquivos órfãos, sem nomes estranhos. (Já houve incidente de pasta criada por expansão de chaves malsucedida — `mkdir -p a/{b,c}` falha em `sh`; use linhas separadas.)
5. **Degradação graciosa**: dependências são opcionais. Sem `reportlab`, gera-se o `.md` e avisa-se sobre o PDF; sem OCR, PDF-imagem vira pendência. Nunca travar o fluxo inteiro por uma dependência ausente.

## Ao criar uma skill nova

Skills novas para o mesmo propósito (ex.: publicação web, geração de simulados) entram em `skills/<nome>/` seguindo o mesmo padrão: `SKILL.md` com frontmatter (`name`, `version`, `description` com triggers), `scripts/` com utilitários e testes, `assets/templates/`, `examples/`. O `scripts/install.sh` descobre skills automaticamente — não precisa editá-lo.

Reaproveite o que já existe antes de duplicar: `textmatch.py` (normalização/similaridade), `slugify.py` (convenção de nomes), o motor de diff em `diff_editais.py`.

## Contexto do domínio

Vocabulário recorrente: **edital** (o documento que rege o concurso), **banca** (organizadora; ex.: Quadrix, Cebraspe), **retificação** (alteração oficial do edital), **cargo**, **conteúdo programático**, **discursiva**, **concurso previsto** (esperado, sem edital publicado).

O vault de destino segue PARA/Johnny-Decimal, com os concursos em `30_AREAS/CARREIRA/CONCURSOS/`.

## Escopo e limites

- O conteúdo gerado é material de estudo — **não substitui a leitura do edital oficial**. Datas e regras devem ser conferidas na fonte.
- A integração com o NotebookLM tem **dois modos, e o manual é o garantido**: não há API pública de consumidor, e a via da comunidade (`notebooklm-py`) usa endpoints não-oficiais que quebram sem aviso. A `concurso-aprofunda` prepara o pacote e o usuário sobe e clica; a `concurso-notebooklm` executa o mesmo pacote automaticamente, como **camada opcional** — nunca em substituição. Sem a biblioteca, a skill degrada e o pacote continua completo.
