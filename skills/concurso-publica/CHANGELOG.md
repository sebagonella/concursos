# Changelog — concurso-publica

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

## [0.7.0] - 2026-07-30

### Adicionado
- **Escopos COMUM/cargo dentro do concurso.** A estrutura de saída espelha o vault: `{concurso}/{comum|cargo}/`. A capa lista os galhos, um card por escopo; a grade de matérias desceu para o hub do escopo, porque na capa o que se faz é escolher o cargo.
- **Todo o conteúdo abaixo do concurso**, por tabela declarativa `SECOES`: edital, cronograma, materiais (com as leis), histórico, sinergia, discursiva e títulos. Os `.md` viram documento; o resto vira **anexo copiado** — o nginx serve só `/srv/site`, então sem a cópia o link da lei funcionaria apenas na máquina do vault. Anexo mostra o tamanho antes do clique: há PDF de quase 10 MB.
- **Mapas de matéria na aba Plano.** Cada matéria é uma página com duas visões — Plano (o mapa do edital, com tópicos e subtópicos) e Estudo (os assuntos aprofundados). São ângulos do mesmo recorte; separá-los obrigaria a saber em qual procurar. Reusa o seletor em abas que já existia.
- **Pacote NotebookLM como página**, uma por assunto, com abas por aprofundamento e **botão de copiar** em cada prompt. É a única página do site cuja razão de existir é uma ação: o vault tem 92 pacotes prontos e um único assunto com mídia real — o gargalo não é ter o roteiro, é executá-lo.
- **Resolvedor global de wikilinks**, com três classes de alvo: página, artefato embutido (flashcards → âncora do quiz) e arquivo copiado (mídia, anexo). Contra o vault real, wikilinks mortos caíram de 96 para 22, e os 22 restantes apontam para mapas de outro cargo.
- Sumário lateral em documento com mais de 3 seções, reusando `.colunas`/`.lateral`. Há documento de 2.400 linhas; rolar 600 sem índice é o que faz voltar para o Obsidian.
- `mapa-aliases.json` **opcional** na pasta da matéria, para o link fino tópico→assunto que o slug não alcança. Ausente = sem links extras, nenhum palpite.

### Corrigido
- **O agrupamento por cargo nunca funcionou.** `cargo_de()` procurava o segmento `03-MAPAS` no caminho, mas o aprofundamento vive em `03-APROFUNDAMENTO`: a condição nunca casava e TODA matéria caía em `_GERAL`, deixando a capa sem agrupamento. A capa do BB passou de zero `<h2>` para os dois escopos. O teste existia e ficava verde porque o fixture montava os assuntos sob `03-MAPAS-MATERIAS`, caminho que a `concurso-aprofunda` não produz — fixture que inventa uma realidade que o gerador não gera é teste que se autoconfirma. Regressão em `test_escopo_vem_do_primeiro_componente_do_caminho`.
- **A varredura precisava inverter, não só ser renomeada.** `achar_materias()` partia de `rglob("assuntos")`, então a árvore era descoberta a partir da existência de aprofundamento — um escopo que só tem `01-EDITAL` (o `_COMUM` de qualquer concurso antes da Etapa 2) nunca era descoberto. `achar_escopos()` acha os galhos primeiro.
- **A mídia do assunto vinha do aprofundamento errado.** `midias` era herdada do principal, e a ordenação põe `detalhado` primeiro; o único assunto do vault com podcast, vídeo e mapa mental guarda os três em `padrao--pestana`, então o site anunciava "0 com áudio" numa matéria que os tinha. Presença passa a ser a união dos aprofundamentos. Regressão em `test_midia_do_assunto_e_uniao_dos_aprofundamentos`.
- **Matéria que só tem mapa deixa de ser descartada** — `coletar_materia()` devolvia None sem `assuntos/`, e no BB isso sumia com 7 das 8 matérias de cada cargo.
- **`md2html`, quatro lacunas:** `![alt](src)` casava a regex de link e saía como `!<a href=…>` (toda imagem quebrada); headings não tinham `id`, logo não havia âncora nem sumário; `[[alvo#seção]]` e o pipe escapado `\|` que a tabela markdown obriga — usado nos índices do BB — não eram reconhecidos, e o divisor de células partia o wikilink em duas.
- **`.wikilink-morto`** era emitido desde a primeira versão e nunca teve regra no CSS. Wikilink sem rótulo passa a exibir só o último segmento: os do SEDES usam caminho absoluto do vault, e o caminho inteiro como texto visível vazava `_COMUM` para 9 páginas.
- **Rebuild deixava lixo.** `construir()` só fazia mkdir, então pasta de layout anterior sobrevivia em `out/` e o `rsync --delete` não a removia, porque existe na origem. Limpeza escopada ao concurso, preservando irmãos e o `assets/`.
- **Navegação interna resolvia pelo índice de nomes**, que casa por basename com o primeiro registro vencendo — com `lingua-portuguesa` no comum e no cargo, o hub do cargo apontava para a matéria do comum e a própria ficava órfã. Link de navegação passa a ser explícito (`rota_irma`, `rota_anexo`); o índice fica só para wikilink. Foi o auditor de links que pegou.
- `iniciarSeletorAprof` tratava só o **primeiro** `.seletor-aprof` da página, o que impediria as abas de visão de coexistirem com as de aprofundamento.

### Modificado
- **`construir()` virou dois passos:** `montar_rotas()` decide onde cada página mora, e só depois vem a renderização. É pré-requisito do resolvedor global — para virar `href`, um wikilink precisa da URL de páginas ainda não geradas.
- **Prefixo sai da rota**, não da contagem manual: `pagina()` recebe a rota da própria página e as trilhas usam `relativo()`. Os literais `"../"`, `"../../"` e `"../../../"` espalhados pelos templates faziam cada nível de pasta novo custar um acerto à mão em cada template.
- **Card de assunto redesenhado:** selo só para mídia que EXISTE (a grade dos 8 tipos com ausentes fica na página do assunto, onde "falta gerar" é acionável); fim da redundância entre "1 fonte", "Padrão + Detalhado" e "2 versões" — com uma fonte, a contagem repetia o nível.
- **O progresso do mapa é contado separado do aprofundamento.** Os 24 mapas do vault somam 2.220 checkboxes, nenhum marcado; misturá-los com os ~200 do aprofundamento apagaria a única barra que significa algo.
- **`✍️ Meu resumo` não é publicado** — vazio em 16 dos 24 mapas e, nos outros 8, exercício de preenchimento com tabela de células vazias. Faz sentido no Obsidian, onde se escreve; nenhum na web.
- Seção com um documento só e sem anexo **é** o documento: índice que lista um item é página inútil e gerava caminho redundante (`titulos/titulos/`).
- **O link tópico→assunto só sai com casamento exato.** Dos 203 tópicos dos 24 mapas, ~18% casam por slug: um tópico do SEDES explode em 7 assuntos, nas matérias de "lei como fonte" o assunto É uma norma (N:M), e 9 assuntos de Português foram reaproveitados do BB. Sem casamento a página **não afirma nada** — o falso negativo (tópico lido como "sem aprofundamento" quando existe com outro nome) esconderia trabalho feito.
- `.grupo` extraído dos três cabeçalhos duplicados (órgão, escopo, prioridade) — menos CSS do que antes. Nenhuma variável de cor nova.
- Removidos o parâmetro morto `origem_dir` de `pagina_assunto` e o atalho `status` do assunto.
- **`prioridades_do_guia()` mantida, com pendência registrada.** Ela procura arquivos `00-GUIA-*` que **não existem em nenhum dos dois concursos** (a prioridade real vem do frontmatter, em 20 arquivos), mas há teste que a exercita de propósito — apagar a função exigiria apagar o teste. O certo é reapontá-la para o mapa de matéria, que é onde a "ordem sugerida" de fato vive; fica para uma próxima versão.
- `cargos[]` segue no modelo como **alias** de `escopos[]`, porque `--modelo site-model.json` é contrato público documentado.

### Testes
- 73 (eram 42), com regressão para cada defeito acima.
- **Auditor de links reforçado.** A regex usava `([^"#?]+)`, o que fazia **não casar nada** quando a URL tinha `#` — link com âncora passava sem verificação, e uma classe inteira de link ficaria fora de cobertura justamente quando as âncoras passaram a existir. Agora confere que o `id` existe no destino, exige `index.html` em link de diretório e acusa página órfã, com contra-prova própria.
- Fixture reescrito para espelhar o vault: `{ESCOPO}/03-APROFUNDAMENTO/{materia}/` e as pastas numeradas, com teste barrando que alguém o enxugue.
- A forma do modelo e o caminho de saída passam por helpers (`_escopos`, `_materias`, `_dir_materia`, `_dir_assunto`), para mudança de estrutura não virar patch de 30 asserções.

## [0.6.0] - 2026-07-29

### Modificado (deploy)
- **O site passa a responder em `concursos.casa:8088`, na raiz** — não mais em `beelink.casa/concursos`. O `nginx.conf` serve `/`, o compose publica a porta 8088 e o `deploy.sh` usa o novo host. Não é mais preciso proxy reverso na frente.
- O caminho antigo `/concursos/<algo>` **redireciona para `/<algo>`** (rewrite, não return fixo), preservando deep links já salvos.
- `absolute_redirect off` + `port_in_redirect off`: sem isso o nginx montava o `Location` com a porta **interna** (`localhost/` em vez de `concursos.casa:8088/`) e todo redirect caía na porta errada. Verificado com container real.
- Variáveis do `deploy.sh` renomeadas de `BEELINK_*` para `CONCURSOS_*` (as antigas seguem aceitas como fallback), e a porta virou `CONCURSOS_PORTA`.
- Removida a redeclaração de `m4a` no bloco `types` — o `mime.types` do nginx já a cobre, e a duplicata gerava warning na inicialização.

> O gerador **não** precisou mudar: o site sempre usou links relativos, então funciona igual na raiz ou em subpath.

### Modificado
- Acompanha o identificador enxugado da `concurso-aprofunda` 0.4.0 (`{nivel}--{fonte}`, sem contador nem índice posicional; concurso no nome do arquivo). Os formatos anteriores continuam sendo lidos.

## [0.5.0] - 2026-07-29

### Adicionado
- Leitura do **novo padrão de pastas de aprofundamento** (`{assunto}/{nivel}--{N}f--f1-{fonte}/`), definido na `concurso-aprofunda` 0.3.0. Os layouts anteriores (`aprofundamentos/{id}/` e o legado plano) continuam sendo lidos — o site nunca deve quebrar por material que o usuário não migrou.
- `scripts/aprofundamento_id.py` — cópia sincronizada da convenção; teste de smoke falha se divergir da fonte em `concurso-aprofunda`.
- O coletor passa a derivar nível e fontes **do nome da pasta**, que é mais confiável que o frontmatter (material antigo pode não ter `nivel:`). Novos campos por aprofundamento: `rotulo`, `n_fontes_id`, `fontes_id`.

## [0.4.2] - 2026-07-28

### Corrigido
- Parser de frontmatter lia comentários inline do YAML junto com o valor, fazendo o nível `padrao` ser tratado como distinto e suprimindo o selo "Padrão + Detalhado".

## [0.4.1] - 2026-07-28

### Adicionado
- Selos nos cards de assunto indicando **quantas fontes** e **quais níveis** (Padrão / Detalhado / ambos), usando a bolha do cartão-resposta: meia = padrão, cheia = detalhado.

## [0.4.0] - 2026-07-28

### Adicionado
- Concursos agrupados por **órgão** no índice raiz.
- Suporte a **vários aprofundamentos por assunto**, com seletor em abas; mídias de cada aprofundamento isoladas em `media/<id>/`.

### Modificado
- Lê tanto a estrutura nova (`aprofundamentos/`) quanto o formato legado.

## [0.3.0] - 2026-07-28

### Adicionado
- **Tema claro/escuro** com preferência do sistema, memória da escolha e script anti-flash.
- **Índice raiz multi-concurso** com manifesto `.concurso.json` por concurso (deploy incremental não remove os demais).
- Assuntos agrupados por **prioridade** (alta/média/base).
- Seção **"Como a banca cobra"** antes da lista de assuntos.
- **Download** de todas as mídias e suporte aos 8 tipos do Estúdio do NotebookLM (áudio, vídeo, slides, mapa mental, infográfico, relatório, teste, tabela de dados).

### Corrigido
- Cores de texto fixas em hex quebravam o tema escuro (`strong` ficava quase invisível). Todas migradas para variáveis de tema, com teste de regressão.

## [0.2.0] - 2026-07-28

### Adicionado
- Subsistema B (`site_builder.py`) + `md2html.py`: geração das páginas (capa, matéria, assunto) com mídias embutidas.
- Quiz de flashcards interativo na página do assunto.

### Corrigido
- Prefixos relativos dos assets tinham um nível a mais — CSS e JS não carregavam nas páginas internas.

## [0.1.0] - 2026-07-28

### Adicionado
- Subsistema A (`site_collector.py`): varre a pasta do concurso e monta o `site-model.json`.
