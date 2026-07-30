# Changelog — concurso-aprofunda

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

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
