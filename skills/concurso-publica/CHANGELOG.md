# Changelog — concurso-publica

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

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
