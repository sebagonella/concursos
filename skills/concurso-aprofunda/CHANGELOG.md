# Changelog — concurso-aprofunda

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

## [0.12.0] - 2026-08-06

### Corrigido
- **`flashcards_gen.py` apagava o baralho anterior em silêncio.** O `write_text` era
  incondicional: rodar a mesma `--out-dir`/`--nome-base` de novo trocava os cartões
  antigos pelos novos, sem backup, sem aviso e sem flag. O dano é pior que o do `.md`
  justamente por ser invisível — o plugin **Spaced Repetition ancora o histórico de
  revisão no TEXTO DA FRENTE do cartão**, então reescrever a frente zera semanas de
  revisão *sem apagar arquivo nenhum*. Até aqui a regra "flashcards se acrescentam,
  nunca se regeneram" existia só como prosa dirigida ao agente no `SKILL.md`.
  Agora o baralho existente é **pulado** e reportado em `ja_existiam` (no JSON, não
  só no stderr — quem consome o script lê o JSON); regerar exige `--forcar`, que faz
  backup `.md.bak`/`.csv.bak` antes. É a mesma proteção que o `build_subject_md.py`
  ganhou na 0.6.0 para o resumo escrito à mão, e que faltava aqui pelo mesmo motivo.

### Testes
- `test_flashcards_nao_regeneram_baralho_existente` e
  `test_flashcards_forcar_regenera_com_backup`. Ambos falham contra a 0.11.0 — o
  primeiro com "o baralho anterior foi sobrescrito".

## [0.11.0] - 2026-08-06

### Corrigido
- **A heurística de leis do notebook casava número de página com número de lei.**
  `_corpo_tem_numero` fazia substring crua, então "Cap. 3 — Ortografia 105–142" e
  "(p. 105)" no assunto **ortografia-oficial** casavam com
  `lei-complementar-105-2001-sigilo-bancario` — e `art. 109` puxaria a Resolução
  CNAS 109. Página é número, artigo é número, inciso é número; **norma é número
  com nome**. Agora o número exige fronteira de dígito e um marcador de norma
  (Lei/Decreto/Resolução/LC…) em até 40 caracteres antes. Achado no dry-run da
  migração, **antes** de gravar em 177 arquivos.

### Adicionado
- **Apelido consagrado casa a norma.** `produtos-bancarios` cita "CDC" seis vezes
  e não escreve "8.078" nenhuma — a heurística por número deixava o CDC fora do
  notebook do assunto que mais depende dele. `_APELIDOS_DE_NORMA` é lista
  **explícita**, não derivação: medindo o vault, "token final do stem" pegava CDC
  e LGPD mas também SEGURANCA e HISTORICO, e qualquer regra que aceitasse BACEN
  fazia toda menção ao Banco Central arrastar duas circulares (7 assuntos),
  enquanto SUAS — o sistema — arrastava a NOB (21). Referência a "CDC" **é**
  referência à Lei 8.078; referência a "BACEN" **não é** referência à Circular
  3.978. Rendeu 21 leis devidas em 18 aprofundamentos.
- **`migrar_fontes_notebook.py`** — declara `fontes_notebook:` nos aprofundamentos
  do vault. `--dry-run` por padrão, backup `.md.bak` (nunca `.bak.md`, que
  ordenaria antes do `.md` e viraria o arquivo principal), e falha alto quando a
  varredura não acha nada. `--completar` reexamina o que já está declarado e
  **acrescenta sem nunca remover** — é o modo de usar depois de melhorar a
  heurística, e é idempotente.

## [0.10.0] - 2026-08-05

### Adicionado

- **`conferir_fontes(fm, aprof_id)`** — espelho de `conferir_localizacoes` para o par
  (id × campo `fontes:`). O campo podia divergir do id sem que nada percebesse, e era dele que
  o site tirava a contagem exibida.
- **`nome_legivel(slug)` / `fontes_legiveis(id)`** — a projeção `id → texto`, determinística.
  O sentido importa: derivar id ← texto é ambíguo em obra de dois autores
  ("Kotler-e-Keller" deriva `keller`, e o id diz `kotler`).
- **`separar_fontes(texto)`** — quebra o campo respeitando vírgula **dentro de parênteses**.
  `"Resolução CMN nº 4.893/2021 (redação vigente, atualizada em 2025)"` é UMA fonte; quebrar
  por vírgula crua é o mesmo defeito que inflava o selo do site, e reproduzi-lo aqui trocaria
  um contador errado por outro.
- **`fontes_notebook:`** no frontmatter declara as leis que sobem ao notebook. Quando existe,
  manda; sem ele, a heurística sugere. Adivinhação silenciosa pôs leis não declaradas em ~75
  aprofundamentos do vault.

### Corrigido

- **A heurística de leis errava nos dois sentidos.** Falso negativo: o corpo escreve
  `8.742` e o nome do arquivo tem `8742` — a comparação era de substring crua, e o ponto do
  milhar quebrava o casamento. Falso positivo: `pnas-2004-texto-integral.pdf` tem **2004** como
  primeiro número, então qualquer corpo que citasse o ano arrastava a PNAS inteira. Agora os
  anos são descartados e os dígitos do corpo, normalizados.
- **A mesma norma subia duas vezes** (`.md` e `.pdf` do mesmo arquivo). Medido: **9 pacotes**
  do vault, um deles com 9 fontes que eram a nota + 4 leis × 2 containers. Agora é um container
  por norma, e o `.md` vence — texto puro, menor, melhor ingestão.
- **`validar_assuntos.py` passa a chamar as duas conferências.** `conferir_localizacoes`
  existia desde a 0.4 e **nenhum script a invocava**; ligada, achou 13 aprofundamentos
  multi-fonte com ponteiro só da primeira fonte. Ela só é cobrada de quem se declara de
  **livro**: norma e material próprio não têm página, e cobrar de todos daria 42 falsos
  positivos nos 177 aprofundamentos.

### Notas

- **O `fontes:` não é sobrescrito pelo derivado.** O texto informado vence quando é consistente
  com o id; só na ausência é que se deriva. Medido: 53 dos 55 slugs do vault têm um único nome,
  e esse nome carrega precisão que o slug não tem — `lei-8742` deriva "Lei 8.742", mas o texto
  diz "Lei nº 8.742/1993". Trocar 53 nomes bons para consertar 2 divergentes seria piorar.
- O `aprofundamento_id.py` é fonte de verdade com cópia sincronizada em `concurso-publica`;
  a cópia foi atualizada na mesma PR, e a skill irmã recebeu bump de patch por isso.

## [0.9.0] - 2026-08-03

### Adicionado
- **`validar_assuntos.py` — as seções do template deixam de ser opcionais.** A etapa 5
  substitui os marcadores do arcabouço, mas nada verificava se a escrita preservava a
  estrutura. **25 assuntos do vault** (normas jurídicas, mais dois de português) foram
  escritos com títulos próprios — `🧩 Estrutura da norma`, `📌 Artigos-chave`,
  `⚠️ Pegadinhas Quadrix`, `🔗 Relacionados`, que **não existem em template nenhum** — e
  no caminho perderam a `## 📝 Para estudar depois`, onde vivem 100% das tarefas de
  estudo. **Cinco matérias inteiras apareciam no site sem tarefa nenhuma**, sem erro em
  lugar nenhum. O validador falha alto listando os incompletos; `--corrigir` acrescenta
  a seção com backup `.md.bak`.
- Etapa **5c** no fluxo do `SKILL.md`, e a regra escrita: preencher é substituir
  marcador, nunca reescrever o arquivo com estrutura própria.

### Notas de projeto
- As tarefas acrescentadas saem só do que o arquivo já declara: a leitura vem do
  `fontes:` do frontmatter e o link dos flashcards vem do arquivo que existe ao lado.
  `[[flashcards-{slug}]]` genérico nasceria morto — o nome real carrega o identificador
  do aprofundamento.
- O backup é `.md.bak`, **não** `.bak.md`: quem acha o arquivo principal pega o primeiro
  `*.md` em ordem, e `…SEDES_2026.bak.md` ordena **antes** de `…SEDES_2026.md` — o
  backup viraria o aprofundamento.
- Varrer e não achar nada **falha alto** (saída 2), como manda a regra que nasceu do
  `fix_notebooklm_packs` achando 0 dos 158 pacotes e saindo com sucesso.

## [0.8.0] - 2026-08-02

### Adicionado
- **`ampliar_aprofundamento.py` — acrescentar fonte a um aprofundamento já escrito.**
  A identidade de um aprofundamento *é* o conjunto de fontes e o id *é* o path, então
  acrescentar uma fonte é necessariamente renomear (`padrao--pestana` ->
  `padrao--pestana+rosenthal`). Não havia como fazer isso: a única saída era gerar do
  zero e perder o texto já escrito. Dois modos, que só diferem em mover vs. copiar —
  **`ampliar`** (o id antigo deixa de existir; o texto vira a semente da mescla) e
  **`derivar`** (os dois convivem; a cópia nasce semeada). Dry-run é o padrão.
- **Etapa 5b (MESCLAR)** no fluxo: os quatro baldes em que a fonte nova cai
  (confirma / completa / corrige / diverge), com a divergência indo para
  `{DIVERGENCIAS}` em vez de o agente escolher lado no corpo. E a regra dos
  flashcards: **acrescentar, nunca regenerar** — o plugin Spaced Repetition ancora o
  histórico de revisão no texto da frente do cartão, então reescrever a frente zera o
  histórico do usuário mesmo sem apagar arquivo nenhum.
- **Localização por fonte**: `localizacao_2:`, `localizacao_3:`, ... para as fontes
  2..N. `--mapa` vira repetível, um por fonte, na mesma ordem de `--fontes`. Assunto
  não localizado numa das fontes é gravado como "não localizado" em vez de sumir —
  omitir não deixaria saber se a fonte não cobre o assunto ou se ninguém procurou.
- **`renomear_aprof.py`**: a máquina de renomeação (quais arquivos viajam, como o
  wikilink é reescrito nas duas granularidades) extraída do `migrar_aprofundamentos.py`
  e compartilhada com o ampliador. Teste trava por **identidade de objeto**, para
  ninguém "consertar" copiando de volta.
- `notebooklm_pack.gerar_para_pasta()`, extraída do laço de `main()`: regenerar o
  pacote de uma pasta não pode espalhar `.bak.md` pelos irmãos.
- **`--mapa` também no ampliador**, repetível, um por fonte nova. É o caminho correto no
  **modo em lote**: o ponteiro de página é POR ASSUNTO, e o `--localizacao` aplica o mesmo
  valor a todos os alvos — numa matéria de 11 assuntos gravaria a página certa de um e
  errada de dez. Descoberto rodando contra o vault real, não em revisão de código. Passar
  os dois juntos é erro de uso: teriam de concordar e não há como saber qual vale.

### Corrigido
- **`_notebooklm-estado.json` ficava para trás** no layout legado-plano: caía no
  `continue` de "arquivo alheio". Ele guarda o `notebook_id`, e perdê-lo obriga a
  recriar o notebook do zero.
- **O migrador rebaixava um aprofundamento combinado a fonte única**, porque
  `fontes_do_assunto` só olhava `localizacao_livro`.
- **O pacote do NotebookLM listava o recorte de uma fonte só.** Num combinado isso
  faz o usuário subir metade do material; agora é um item `(Referência)` por fonte.

### Notas
- O ampliador **avisa da nota antiga que continua dentro do notebook já criado**:
  `garantir_fontes()` sobe fonte pelo nome e **só adiciona**, nunca remove, então
  gerar mídia depois de ampliar produziria podcast sobre material contraditório. Vira
  pendência nomeada e `notebooklm_fonte_obsoleta` no pacote — herdado por prefixo,
  sobrevive a toda regeração futura.
- Os slugs derivados passam a ser **sempre ecoados**, não só quando suspeitos: um nome
  de arquivo corrompido produz slug plausível e errado que `slug_suspeito()` não acusa,
  e o erro só apareceria depois de a pasta existir.
- Com **uma fonte só a saída é byte a byte idêntica** à da 0.7.2 — verificado gerando
  com o código anterior e comparando, nos dois níveis.
- Testes: 68 -> 99.

## [0.7.2] - 2026-07-31

### Corrigido
- **O `SKILL.md` e o `README` descreviam o mundo anterior à `concurso-notebooklm`.**
  Diziam, em três lugares, que a automação do NotebookLM "não existe no repo hoje" e
  que a geração da mídia é manual por decisão de projeto — enquanto a skill irmã já
  estava no repo, na 0.2.x, verificada ponta a ponta. O manual continua sendo o caminho
  garantido; o que mudou é que agora há alternativa, e omiti-la escondia trabalho feito.
- **A Etapa 7 ainda dizia que `herdar_campos()` preserva "os dois únicos campos"**
  `notebooklm_url` e `notebooklm_status`. A 0.7.1 justamente trocou isso por herança
  por prefixo `notebooklm_*` — o texto descrevia o bug que a versão anterior corrigiu.

## [0.7.1] - 2026-07-31

### Corrigido
- **Regerar o pacote apagava tudo que a automação escrevesse nele.** `herdar_campos()` herdava exatamente duas chaves — `notebooklm_url` e `notebooklm_status`. Qualquer campo novo (o id do notebook, a data da criação, o que a integração precisa para não recriar o que já existe) ia para o `.bak.md` na regeração seguinte, **em silêncio** — o mesmo defeito que a função foi criada para evitar com a URL, repetido um nível acima. A herança passa a ser por **prefixo** `notebooklm_*`: campo novo sobrevive sem ninguém lembrar de estender a função. Campo presente mas vazio continua não sendo herdado, para não fossilizar `notebooklm_id: ""`.

### Adicionado
- Bloco `{NOTEBOOKLM_EXTRA}` no template, onde os campos herdados sem lugar fixo são reemitidos, e limpeza de linha vazia no frontmatter — o placeholder fica vazio no caso comum e deixaria uma linha solta no meio do YAML.

## [0.7.0] - 2026-07-31

### Corrigido
- **O prompt mandava o NotebookLM usar uma fonte que podia não estar lá.** No nível `detalhado`, o prompt de áudio injetava `Baseie-se nas fontes: {fontes}` com o nome do arquivo do livro — mas a própria seção "Fontes para subir" marca o recorte do livro como *(Referência)* **opcional**, e o padrão é subir só a nota curada do vault. Prompt e instrução se contradiziam. Eram **20 dos 158 pacotes** do vault. Agora **os quatro prompts** ancoram na nota, por `clausula_fonte()`, e o único nome citado é o do `.md` que a seção 1 manda subir como fonte principal.
- **O migrador de pacotes não enxergava um único pacote do vault.** `fix_notebooklm_packs.py` procurava o assunto em `{assunto}/{assunto}.md` — o layout plano legado — enquanto todos os 158 pacotes vivem em `{assunto}/{nivel}--{fonte}/`. Ele imprimia "Nenhum assunto encontrado" e **saía com sucesso**: migração que não migra e não reclama. O teste passava porque o fixture usava o layout que o gerador não emite mais. Agora o inventário vem de `pastas_de_aprofundamento()`/`arquivo_principal()` do próprio gerador — a regra de layout deixa de existir em dois lugares — e não achar nada **falha alto**.
- **Backup duplicado no migrador.** Ele copiava o pacote para `.bak.md` incondicionalmente, inclusive quando nada mudaria, e o backup condicional do `notebooklm_pack.py` o sobrescrevia em seguida. Removido: o backup é do gerador, que só copia quando o conteúdo mudou.

### Adicionado
- **Guarda sistêmica contra citar a obra no prompt.** `test_prompt_nunca_manda_consultar_o_livro` gera pacotes para as combinações representativas (livro · norma · `--proprio` · `padrao` · `detalhado`), varre **todos** os blocos cercados e falha se algum casar `.pdf`, `págs.`, `páginas`, `capítulo`, a formulação antiga, ou qualquer termo que **só** o `fontes:`/`localizacao_livro:` conheça. Vale para os prompts que ainda serão escritos — é o análogo do teste que barra cor fixa fora das variáveis de tema, na `concurso-publica`.
- **Teto de tamanho do prompt** (`test_prompt_cabe_no_campo_do_estudio`): o campo "Customize" do Estúdio trunca, e o fim do prompt é onde ficam as instruções de conteúdo. Pior caso real medido: 490 caracteres.
- **O pacote declara o que a automação precisa**, em chaves planas no frontmatter: `nome_notebook`, `arquivo_podcast`, `arquivo_mapa_mental`, `arquivo_video`, `arquivo_report`. Antes esses identificadores só existiam na prosa, e extrair nome de arquivo por regex de texto corrido era exatamente o que fazia o roteiro do mapa mental e o do report chegarem **vazios** ao site.

## [0.6.1] - 2026-07-30

### Corrigido
- **Marcar um subtópico como concluído no Obsidian renomeava o assunto.** O plugin **Tasks** acrescenta `✅ 2026-07-30` ao fim da linha, e o `assuntos_do_topico.py` só limpava isso por acidente: o corte nos dois-pontos ("Tema: explicação") descartava o resto da linha. Num item **sem** `:` a data entrava no nome — `criacao-de-brasilia-…-plano-de-metas-2026-07-30` — e o slug deixava de casar com a pasta já existente no vault, fazendo um assunto **já aprofundado parecer não aprofundado** em qualquer verificação mapa↔pastas. Agora os marcadores do Tasks (`✅ ❌ ➕ 🛫 ⏳ 📅 🔁 🆔 ⛔` e as cinco prioridades `🔺 ⏫ 🔼 🔽 ⏬`) são removidos **antes** do corte nos dois-pontos, de modo que os dois formatos de item ficam limpos. Emoji fora desse conjunto pertence ao nome e é preservado — há teste que trava isso.

## [0.6.0] - 2026-07-30

### Corrigido
- **O arcabouço deixava de existir o resumo escrito à mão.** `build_subject_md.py` gravava por cima **sem perguntar**: reexecutar a matéria trocava o texto pronto por um arcabouço com os `{PLACEHOLDER}` de volta. Era o defeito mais caro possível — o `.md` é onde mora o conteúdo curado — e ficava pior justamente no modo novo, que reexecuta a mesma matéria a cada tópico. Agora assunto que já tem `.md` é **pulado** e reportado em `ja_existiam`; regerar de propósito exige `--forcar`, com backup `.md.bak`.

### Adicionado
- **Aprofundar um tópico por vez.** `scripts/assuntos_do_topico.py` lê o mapa, seleciona um tópico (por número, slug ou trecho do título) e devolve os assuntos dos seus `### Subtópicos derivados`, já com `materia_id`/`topico_id`/`topico`. A saída serve direto para `book_index.py --assuntos` (com livro) ou `build_subject_md.py --assuntos --proprio` (sem fonte). `--listar` mostra os tópicos disponíveis. Tópico inexistente **falha alto** e lista o que existe — devolver lista vazia faria parecer que o tópico não tem assunto.
- `--assuntos` passa a aceitar o mesmo JSON do `book_index.py` além de TXT; os dois scripts liam formatos diferentes para a mesma lista.

## [0.5.0] - 2026-07-30

### Adicionado
- **Aprofundamento sem fonte externa**, escrito do conhecimento próprio, nos dois níveis: `{nivel}--proprio`. `--proprio` no `build_subject_md.py`, com `--assuntos` no lugar do `--mapa` (não há livro para localizar), e dois templates novos sem `localizacao_livro`, sem `⚓ Trechos-âncora` e sem o checkbox "Ler as páginas". No lugar, `## 📚 Onde conferir`, com a norma oficial verificável.
- **Regra de honestidade para material sem fonte**: sem livro para ancorar, *não inventar número de lei, artigo, súmula ou jurisprudência* — o que não for seguro vira pendência. É o análogo direto de "não inventar página", e não existia.
- **Vínculo assunto → tópico do edital** gravado no frontmatter: `materia_id`, `topico_id[]` e `topico[]`. A skill já lia o mapa para saber quais assuntos existem — ela sabia de que tópico cada um veio e simplesmente não registrava.
- `propor_vinculos.py` (extrai o material cru para a classificação por leitura) e `aplicar_vinculos.py` (grava o vínculo, dry-run por padrão, com backup e recusa de tópico inexistente).

### Corrigido
- **"Sem fonte" deixa de ser indistinguível de erro.** `id_aprofundamento([], nivel)` caía em `padrao--fonte`, que `slug_suspeito()` marca como derivação ruim — então um material deliberadamente sem fonte se disfarçaria de configuração errada, e vice-versa. O token `proprio` é reservado e declarado; a lista vazia continua significando "a derivação falhou".
- Tag da matéria some da lista YAML quando não há matéria, em vez de deixar um item vazio (`[a, , b]`).

## [0.4.1] - 2026-07-30

### Corrigido
- **O pacote NotebookLM passa a emitir `notebooklm_url:`.** A `concurso-publica` só mostra o botão "Abrir no NotebookLM" quando essa chave está preenchida, mas o template **nunca a escrevia** — 0 dos 92 pacotes do vault a têm, e o botão era inalcançável em 100% dos casos. Não havia como o usuário preencher um campo que não existia. O teste que cobria isso escrevia a chave à mão no fixture, num pack de duas linhas que não se parece com o template real.
- **`herdar_campos()` preserva o que o usuário digitou na regeneração.** A chave sozinha apagaria dado: o gerador reescreve o pacote sempre que o conteúdo muda, e acrescentar um campo faz TODO pacote existente contar como mudado — a URL colada à mão iria para o `.bak.md` e o botão desapareceria do site sem erro nenhum. `notebooklm_url` e `notebooklm_status` são os dois únicos campos que o gerador não sabe reconstruir; fontes, prompts, roteiro e perguntas ele reconstrói.

> Os pacotes já no vault seguem sem a chave até serem regerados. `fix_notebooklm_packs.py` faz isso com backup, mas é escrita no vault e fica a critério do dono.

## [0.4.0] - 2026-07-29

### Modificado (BREAKING — identificador de aprofundamento)
- **Identificador enxugado e globalmente único.** De `{nivel}--{N}f--f1-{fonte}` para `{nivel}--{fonte1}[+{fonte2}]` na pasta, e `{assunto}--{nivel}--{fontes}--{CONCURSO}` no arquivo.

  ```
  antes:  padrao--3f--f1-leidf-7008--f2-dec-42872--f3-port-42/
          crase--detalhado--1f--f1-pestana.md
  agora:  padrao--leidf-7008+dec-42872+port-42/
          crase--detalhado--pestana--SEDES_2026.md
  ```

  Removidos por **não diferenciarem nada**: o contador de fontes (`2f`, derivável contando os `+`) e o índice posicional (`f1-`, `f2-`, já implícito na ordem). Acrescentado o **concurso no nome do arquivo**, que resolve colisão real: 18 arquivos já eram homônimos entre `SEDES_2026` e `BB_2027_PREVISTO`, porque usam o mesmo livro para os mesmos assuntos — e o Obsidian resolve wikilink por nome de arquivo.
- `parse_id()` **lê o formato anterior** e o normaliza (campo `formato`), para que vault não migrado continue legível pelo site.

### Corrigido
- **`migrar_aprofundamentos.py` podia trocar conteúdo preenchido por arcabouço vazio.** Quando a pasta de origem tinha mais de um `.md` principal (um arcabouço órfão convivendo com o material redigido), o migrador escolhia "o primeiro em ordem alfabética" — e o arcabouço vinha antes. Agora essa situação é **recusada como pendência**, pedindo consolidação manual, em vez de adivinhar. Coberto por teste de regressão.

### Adicionado
- `--concurso` no `flashcards_gen.py`, para o nome-base dos flashcards casar com o do `.md`.
- Migração automática do formato 0.3.x: o `migrar_aprofundamentos.py` reconhece as pastas antigas, **reaproveita** nível e slugs já resolvidos (em vez de rederivar do frontmatter) e reescreve os wikilinks.

## [0.3.0] - 2026-07-29

### Modificado (BREAKING — layout de pastas)
- **Nova convenção de pastas de aprofundamento.** O nível intermediário `aprofundamentos/` deixa de existir e o identificador passa de `{fonte}--{nivel}` para `{nivel}--{N}f--f1-{fonte1}[--f2-{fonte2}]`, direto sob a pasta do assunto:

  ```
  assuntos/emprego-do-acento-indicativo-de-crase/
  ├── padrao--1f--f1-pestana/
  └── detalhado--1f--f1-pestana/
  ```

  O slug da fonte é o **sobrenome de um autor** (livro) ou o **identificador da norma** (`f1-lei-8742`, `f1-res-cmn-4893`, `f1-lc-105`, `f1-leidf-6938`) — 42% do material do vault vem de lei/decreto/resolução, que não têm autor. Os nomes de arquivo repetem o identificador, porque o Obsidian resolve wikilink por nome de arquivo.
- Leitura dos formatos anteriores mantida em `notebooklm_pack.py` e `reuse_finder.py` (e no site): quem não migrar não fica sem material.

### Adicionado
- `scripts/aprofundamento_id.py` — implementação única da convenção (montar/ler/validar). A `concurso-publica` tem cópia sincronizada, com teste que falha se divergirem.
- `--fontes-slug` no `build_subject_md.py`: sobrepõe a derivação automática quando o nome da fonte não permite deduzir autor/norma (obra com dois autores, arquivo sem autor, documento sem número). O script **avisa** quando o slug derivado sai suspeito, em vez de gravar um path ruim no vault.
- `migrar_aprofundamentos.py` reescrito: varre a raiz de concursos, move o material para o padrão atual, atualiza o frontmatter (`nivel`, `aprofundamento`, `fontes`) e **reescreve os wikilinks dos índices de matéria** — que vivem fora de `assuntos/` e referenciam o path completo. Sem essa etapa a migração deixaria o vault cheio de link quebrado. Dry-run é o padrão; aceita `--overrides`.
- `examples/overrides-fontes.json` com os três casos reais que a heurística não acerta.

### Corrigido
- **`flashcards_gen.py` gerava `flashcards-{assunto}.md` sem o sufixo do aprofundamento**, enquanto o `build_subject_md.py` apontava o wikilink para `flashcards-{assunto}--{id}`. Resultado: link quebrado no Obsidian e dois arquivos homônimos quando o mesmo assunto tinha mais de um aprofundamento. Agora aceita `--aprofundamento`/`--nome-base`; sem eles mantém o nome legado. Coberto por teste de regressão.
- `notebooklm_pack.py` sobrescrevia `_fonte-notebooklm.md` sem backup. Agora só grava quando o conteúdo muda, e faz backup `.bak.md` antes — contraria a regra de preservar trabalho do usuário.

## [0.2.1] - 2026-07-28

### Corrigido
- `notebooklm_pack.py` não enxergava a estrutura de aprofundamentos e gerava 0 pacotes. Agora gera **um pacote por aprofundamento** (fontes diferentes merecem notebooks diferentes), com prompt de áudio específico para o nível `detalhado`.
- Parser de frontmatter passava a ler comentários inline do YAML junto com o valor (`nivel: padrao   # padrao | detalhado`), quebrando a comparação de níveis. Corrigido em todos os parsers; comentários removidos dos templates.

### Modificado
- `SKILL.md`: `nivel` e `fontes` agora aparecem na **tabela de parâmetros** e no comando do fluxo — antes existiam só no script, invisíveis para quem invoca a skill. A etapa de preenchimento descreve as seções exclusivas do nível `detalhado`.

## [0.2.0] - 2026-07-28

### Adicionado
- **Múltiplos aprofundamentos por assunto**: identidade `{fonte}--{nivel}`, cada um na própria pasta `aprofundamentos/`. Várias fontes numa execução geram um aprofundamento combinado; execuções separadas geram aprofundamentos distintos.
- **Níveis de profundidade** (`--nivel`): `padrao` (~350-500 palavras, revisão) e `detalhado` (~1200-2500 palavras, com desenvolvimento completo, quadro de casos, exemplos resolvidos, questões comentadas e divergências entre autores). Template próprio: `assunto-detalhado.md.tpl`.
- **`--fontes`**: declara a(s) fonte(s) do aprofundamento, gravada(s) no frontmatter.
- **`migrar_aprofundamentos.py`**: reorganiza material do formato antigo para a estrutura de aprofundamentos (com `--dry-run`).
- **Classificação por prioridade** (alta/média/base) no frontmatter, usada pelo site para agrupar assuntos.
- **`como-banca-cobra.md.tpl`**: documento "Como a {BANCA} cobra {MATÉRIA}", exibido no site antes da lista de assuntos.
- **`fix_notebooklm_packs.py`**: atualiza os pacotes NotebookLM de um concurso existente, com backup e sem regenerar resumos.
- **`book_coverage.py`**: relatório de páginas do livro fora do edital (o que dá para pular).
- **`reuse_finder.py`**: detecta assuntos já aprofundados com o mesmo livro em outros concursos.

### Modificado
- Pacote NotebookLM: extensão corrigida para `.m4a`, prompts finos para os 4 geráveis (áudio, mapa mental, vídeo, relatório) e seção de links para os arquivos salvos.
- Flashcards Obsidian: `??` passa a ficar sozinho na linha (formato multi-linha válido do plugin Spaced Repetition). Antes o plugin não reconhecia os cartões.
- Seção "Resumo completo" renomeada para "Resumo" — o rótulo anterior era enganoso para o volume gerado.

### Nota de compatibilidade
O formato antigo (arquivo direto na pasta do assunto) continua sendo lido pela skill `concurso-publica`. A migração é opcional.

## [0.1.0] - 2026-07-15

### Adicionado
- Subsistema A (`book_index.py`): localiza assuntos no livro por sumário ou densidade de termos, com score de confiança; suporta PDF com texto, PDF escaneado (OCR) e EPUB.
- Subsistema B (`build_subject_md.py`): gera o arcabouço `.md` por assunto no Modelo 2 (resumo original + ponteiros de página + citações curtas).
- `flashcards_gen.py`: flashcards nativos em formato Obsidian e Anki.
- `notebooklm_pack.py`: pacote de embarque para gerar podcast/mapa mental no NotebookLM (camada manual).
