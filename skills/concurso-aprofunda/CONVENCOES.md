# Convenções invioláveis — `concurso-aprofunda`

Regras que vieram de **bugs reais** neste repositório. Cada uma traz o número que a
originou, e é o número que impede a regressão: sem ele a regra vira opinião, e
opinião se "melhora" de volta ao defeito.

Moram aqui, e não no `CLAUDE.md` da raiz, porque só valem para esta skill — e o
raiz é carregado em todo turno de toda sessão, inclusive nas que não a tocam. O
índice de todas está em [`CLAUDE.md`](../../CLAUDE.md#por-skill).

> Se uma destas regras conflitar com o código, **o código venceu** e a regra virou
> defeito de documentação. Corrija os dois na mesma PR.

---

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

- **Flashcards do Obsidian**: no formato multi-linha, o `??` precisa ficar **sozinho na própria linha** entre pergunta e resposta. Colado na resposta, o plugin Spaced Repetition não lê o cartão.

- **O arcabouço nunca sobrescreve conteúdo**: `build_subject_md.py` pula assunto que já tem `.md` e só regenera com `--forcar`, fazendo backup. O `.md` é onde mora o resumo escrito à mão.

- **Regra de layout mora no gerador, nunca copiada**: `fix_notebooklm_packs.py` reimplementava a busca do `.md` do assunto e ficou preso no formato plano legado — achava **zero** dos 158 pacotes do vault e saía com sucesso. Quem varre pastas de aprofundamento usa `pastas_de_aprofundamento()`/`arquivo_principal()`, e não achar nada **falha alto**. **Isso vale também para script de análise descartável**, e não só para o que entra no pacote: uma comparação ad-hoc entre escopos pegou `sorted(glob("*.md"))[0]` e leu o **`_fonte-notebooklm.md`** em vez do assunto — `_` (95) ordena antes das minúsculas —, o que fez o relatório afirmar 17 artigos ausentes onde havia **8**, e subestimar o material já escrito. `arquivo_principal()` já filtra `flashcards-`, `_`, `00-`, `report-`, `teste-` e `tabela-`; reimplementar é repetir o bug, mesmo num script que se joga fora depois.

- **O prompt do NotebookLM aponta para a nota do vault, nunca para o livro**: subir o recorte da obra é opcional, então prompt que a nomeia manda o modelo consultar fonte que pode não estar no notebook. A cláusula sai de `clausula_fonte()`, num lugar só, e há teste que varre **todos** os blocos gerados procurando `.pdf`, página, capítulo ou termo que só o `fontes:` conheça.
