---
name: concurso-aprofunda
version: 0.4.0
description: Use quando o usuário já tem uma preparação de concurso montada no vault (pela skill concurso-prep) e quer APROFUNDAR uma matéria a partir de um material denso — tipicamente um livro de referência (PDF/EPUB) que está no vault. A skill localiza no livro cada assunto já mapeado daquela matéria (via sumário ou busca por densidade de termos), gera um arquivo .md por assunto no vault com resumo completo próprio + ponteiros de página + trechos-âncora curtos citados (Modelo 2, sem copiar a obra), e produz flashcards nativos (Obsidian + Anki). Prepara também o insumo para a Etapa NotebookLM (podcast, mapa mental), tratada separadamente. Suporta DOIS NÍVEIS de profundidade (padrao = resumo de revisão; detalhado = tratamento exaustivo com exemplos resolvidos e questões comentadas) e VÁRIOS APROFUNDAMENTOS por assunto (fontes diferentes convivem lado a lado). Triggers - "aprofundar português com o livro X", "pegar os assuntos do livro", "mapear o livro de referência", "gerar flashcards do assunto", "extrair assuntos do material para o vault", "aprofundar mais/mais detalhado esse assunto", "aprofundar com outro livro/outra fonte", "versão detalhada do assunto".
---

# concurso-aprofunda

Segunda etapa do fluxo de preparação. Consome a saída da `concurso-prep` (os assuntos já mapeados em `03-MAPAS-MATERIAS/`) e um **material denso** (livro de referência) para produzir estudo aprofundado por assunto.

## Pré-condições

1. Já existe uma pasta de concurso gerada pela `concurso-prep` (ex.: `SEDES_2026/`).
2. Existe um livro de referência da matéria no vault (PDF com texto, PDF escaneado, ou EPUB).
3. A matéria tem assuntos mapeados (lista de tópicos no mapa da matéria).

## Aprofundamentos: fontes e níveis (0.4.0)

Um assunto pode ter **vários aprofundamentos**. Cada um vive na sua própria pasta,
direto sob a pasta do assunto:

```
30_AREAS/CARREIRA/CONCURSOS/{ORGAO}_{ANO}[_PREVISTO]/{_COMUM|CARGO}/
└── 03-APROFUNDAMENTO/{slug-materia}/assuntos/{slug-assunto}/
    └── {nivel}--{fonte1}[+{fonte2}]/
        ├── {slug-assunto}--{nivel}--{fonte1}[+...]--{CONCURSO}.md
        ├── flashcards-{slug-assunto}--{nivel}--{fonte1}[+...]--{CONCURSO}.md / .csv
        ├── cards.json
        └── _fonte-notebooklm.md
```

**Princípio: cada componente existe porque diferencia alguma coisa.**

| Componente | Onde | Diferencia |
|---|---|---|
| `{nivel}` | pasta e arquivo | profundidade (`padrao` \| `detalhado`) |
| `{fonteN}` | pasta e arquivo | origem (autor do livro ou identificador da norma) |
| `{CONCURSO}` | **só no arquivo** | contexto — o mesmo livro serve a vários concursos |

O que **não** entra, por não diferenciar nada: contador de fontes (`2f` é derivável
contando os `+`) e índice posicional (`f1-`, `f2-` — a ordem já está na sequência).

Duas decisões que valem registrar:

- **O concurso vai só no nome do arquivo, e no fim.** A pasta já vive dentro do
  concurso, então o path resolve; mas o Obsidian resolve wikilink pelo **nome do
  arquivo**, e dois concursos com o mesmo livro gerariam homônimos. Vai no fim
  porque o discriminador que se procura é o assunto — concurso é desempate.
- **A fonte aparece mesmo quando há só uma.** Omiti-la obrigaria a **renomear** o
  aprofundamento existente quando surgisse uma segunda fonte, e renomear quebra
  wikilink e progresso do usuário.

Exemplos reais:

| Situação | Pasta |
|---|---|
| Livro único | `padrao--pestana` · `detalhado--pestana` |
| Duas fontes | `detalhado--pestana+abreu` |
| Norma única | `padrao--lei-8742` |
| Três normas | `padrao--leidf-7008+dec-42872+port-42` |

O slug da fonte é o **sobrenome de um autor** (livro) ou o **identificador da norma**:
`lei-8742`, `lc-105`, `leidf-6938`, `dec-7053`, `res-cmn-4893`, `res-conj-cnas-conanda-1`.
Alteração posterior da mesma norma **não** é fonte nova.

Quando o nome da fonte não permite deduzir autor/norma (obra com dois autores, arquivo
sem autor no nome), passe **`--fontes-slug`**. O script avisa quando a derivação sai
suspeita, em vez de gravar um path ruim no vault.

A convenção é implementada em `scripts/aprofundamento_id.py` — **fonte de verdade**,
com leitura retrocompatível dos formatos anteriores. A `concurso-publica` tem cópia
sincronizada; há teste que falha se divergirem.

### Níveis (`--nivel`)

| Nível | Resumo | Para quê |
|---|---|---|
| `padrao` (default) | ~350-500 palavras | revisão: regras principais, subtópicos, pegadinhas |
| `detalhado` | ~1200-2500 palavras | domínio: desenvolvimento completo, quadro de casos, exemplos resolvidos passo a passo, questões comentadas, divergências entre autores |

O nível escolhe o template (`assunto.md.tpl` ou `assunto-detalhado.md.tpl`) e vai
para o frontmatter, que a skill `concurso-publica` usa para montar o seletor no site.

### Migrar material antigo

```bash
# 1. conferir o que muda (padrão: dry-run, nada é escrito)
python scripts/migrar_aprofundamentos.py --raiz <.../CONCURSOS> --dry-run

# 2. aplicar, com overrides para as fontes que a derivação não acerta
python scripts/migrar_aprofundamentos.py --raiz <.../CONCURSOS> \
    --overrides examples/overrides-fontes.json --aplicar
```

Move (não copia) os aprofundamentos dos formatos antigos para o padrão atual,
atualiza o frontmatter (`nivel`, `aprofundamento`, `fontes`) e **reescreve os
wikilinks** dos índices de matéria, que ficam fora de `assuntos/` e apontam para
o path completo — sem isso a migração deixa o vault cheio de link quebrado.

Nunca sobrescreve pasta de destino existente e recusa migrar quando o slug da
fonte sai suspeito, reportando pendência em vez de gravar um path ruim.
É opcional para leitura: o site lê os formatos antigos também.

## Escopo desta versão (0.3.0)

Cobre os **Subsistemas A + B + flashcards nativos**. A **Etapa NotebookLM** (podcast, mapa mental) é preparada mas executada numa etapa seguinte (ver "Ponte NotebookLM").

## Parâmetros

| Parâmetro | Obrigatório | Default | Descrição |
|---|---|---|---|
| `livro` | sim | — | Caminho do livro no vault (PDF/EPUB) |
| `materia` | sim | — | Matéria a aprofundar (ex.: "Língua Portuguesa") |
| `concurso` | sim | — | Pasta do concurso (ex.: "SEDES_2026") |
| `nivel` | não | `padrao` | **`padrao`** = resumo de revisão (~350-500 palavras) · **`detalhado`** = tratamento exaustivo (~1200-2500 palavras, com desenvolvimento completo, quadro de casos, exemplos resolvidos, questões comentadas e divergências entre autores) |
| `fontes` | não | nome do livro | Nome(s) da(s) fonte(s), separados por vírgula. Define a identidade do aprofundamento junto com o nível. **Várias fontes numa mesma execução geram UM aprofundamento combinado**; execuções separadas geram aprofundamentos distintos do mesmo assunto |
| `fontes-slug` | não | derivado | Slugs das fontes, na mesma ordem de `fontes`. Sobrepõe a derivação automática (sobrenome do autor / identificador da norma). Use quando o nome da fonte não permite deduzir — obra com dois autores, arquivo sem autor no nome, documento sem número de norma |
| `ocr` | não | `auto` | `auto` (OCR só se o PDF for imagem), `forcar`, `nunca` |
| `so-encontrados` | não | false | Não gerar arcabouço para assuntos não localizados no livro |
| `flashcards` | não | true | Gerar flashcards nativos por assunto |

## Fluxo (8 etapas)

```
1. Ler os assuntos mapeados da matéria
   - Fonte: {concurso}/{CARGO}/03-MAPAS-MATERIAS/{materia}/ (ou o índice da matéria)
   - Montar assuntos.json = {materia, assuntos:[...]}

2. Localizar cada assunto no livro   [Subsistema A]
   - scripts/book_index.py --livro <livro> --assuntos assuntos.json --out mapa-localizacao.json
   - Detecta tipo (PDF-texto/escaneado/EPUB); usa sumário (TOC) ou densidade de termos
   - Saída: para cada assunto {paginas, confianca, metodo}

2b. Verificar REAPROVEITAMENTO entre concursos   [antes de gerar/preencher]
   - scripts/reuse_finder.py --vault-concursos <CONCURSOS/> --livro <livro> \
       --assuntos assuntos.json --concurso-atual <concurso>
   - Percorre os concursos já salvos no vault e verifica se cada assunto JÁ foi
     aprofundado com O MESMO LIVRO (mesmo assunto + mesmo livro = mesmo trabalho).
   - Para os assuntos "reaproveitaveis": copiar o .md (e flashcards) já preenchido
     do concurso de origem, validando as páginas (se divergirem muito, é outra
     edição — avisar e revalidar). Registrar no novo .md a origem do reaproveitamento.
   - Só os assuntos "sem_fonte" precisam ser preenchidos do zero.
   - Regra: só reaproveita material EFETIVAMENTE preenchido (status != nao-iniciado
     e sem placeholders pendentes). Nunca reaproveita arcabouço vazio.

3. Revisar pendências de localização
   - Assuntos "nao_encontrado" ou de confiança baixa vão para pendências
   - Apresentar ao usuário os que precisam de conferência manual (NÃO fingir precisão)

3b. Relatório de cobertura do livro   [opcional, recomendado]
   - scripts/book_coverage.py --mapa mapa-localizacao.json --out 00-COBERTURA-LIVRO.md
   - Lista as faixas de páginas do livro FORA do edital (o que dá para pular) e
     a % de cobertura. Útil para economizar tempo de estudo.

3c. Classificar os assuntos por PRIORIDADE (alta | media | base)
   - O Claude classifica cada assunto pelo peso na prova e pela dificuldade típica,
     considerando o perfil da banca. Grava em prioridades.json e passa ao builder:
     scripts/build_subject_md.py ... --prioridades prioridades.json
   - A prioridade vai para o frontmatter de cada assunto e é usada pela skill
     concurso-publica para agrupar os assuntos no site.

3d. Gerar "Como a {BANCA} cobra {MATÉRIA}"  [bússola da matéria]
   - Template: assets/templates/como-banca-cobra.md.tpl
   - Salvar como COMO-A-BANCA-COBRA-{MATERIA}.md na pasta da matéria.
   - O Claude preenche: estilo da banca nesta matéria, o que mais cai, formato das
     questões, armadilhas recorrentes e como isso muda o estudo. Use a análise de
     banca da concurso-prep (_COMUM/) como insumo, especializando-a PARA ESTA MATÉRIA.
   - Este documento é exibido no site (concurso-publica) antes da lista de assuntos.

4. Gerar o arcabouço .md por assunto   [Subsistema B]
   - scripts/build_subject_md.py --mapa mapa-localizacao.json --out-dir <assuntos/> \
       --concurso <concurso> --fontes "<nome da fonte>" --nivel <padrao|detalhado> \
       [--prioridades prioridades.json]
   - SEMPRE passe --fontes e --nivel: eles definem a identidade do aprofundamento
     ({nivel}--{fonte}) e permitem que o mesmo assunto tenha várias versões.
   - Se o usuário não disser o nível, pergunte OU use `padrao` e avise que existe
     o `detalhado`. Se ele pedir "mais completo/aprofundado/detalhado", use `detalhado`.
   - Cria assuntos/{assunto}/{nivel}--{fonte}/{assunto}--{nivel}--{fonte}--{CONCURSO}.md
   - Se o nome da fonte não deixa deduzir autor/norma, passe --fontes-slug
     (ex.: --fontes-slug "kotler"); o script avisa quando o slug sai suspeito.

5. PREENCHER o conteúdo de cada assunto  [tarefa do AGENTE — Modelo 2]
   O conjunto de seções DEPENDE DO NÍVEL escolhido na etapa 4.

   NÍVEL `padrao` (template assunto.md.tpl) — resumo de revisão:
   - RESUMO_COMPLETO: resumo próprio e completo do assunto (redigido do zero,
     didático, cobrindo o que o concurso exige). NÃO copiar o texto do livro.
   - RELEVANCIA_CONCURSO: por que cai na prova, peso, ligação com a banca
   - SUBTOPICOS: desmembramento do assunto
   - CITACOES: 1–3 trechos CURTOS do livro (definição-chave, uma regra), entre
     aspas, com a página. Trechos curtos apenas — nunca parágrafos inteiros.
   - PEGADINHAS: erros clássicos e pontos de atenção da banca
   - RELACIONADOS / NORMA: conexões com outros assuntos e legislação
   NÍVEL `detalhado` (template assunto-detalhado.md.tpl) — além das seções acima:
   - VISAO_GERAL: mapa do assunto em poucas linhas, situando as partes
   - DESENVOLVIMENTO: tratamento completo, cada regra COM SUA JUSTIFICATIVA
     (não só o enunciado); é a seção mais longa do documento
   - QUADRO_CASOS: tabela de casos (obrigatório/proibido/facultativo, quando
     aplicável) ou quadro comparativo equivalente para o assunto
   - EXEMPLOS_RESOLVIDOS: 3 a 5 exemplos trabalhados PASSO A PASSO, mostrando o
     raciocínio, não só a resposta
   - QUESTOES_COMENTADAS: questões no estilo da banca, com o comentário de por que
     cada alternativa está certa ou errada
   - DIVERGENCIAS: onde os autores/gramáticos discordam e o que a banca costuma
     adotar (deixar vazio se não houver divergência relevante)

   > Regra de direitos autorais: o resumo é original; do livro entram só
   > localização (páginas) e trechos curtos citados. Não reproduzir a obra.
   > Isso vale IGUALMENTE no nível detalhado — mais profundidade significa mais
   > análise própria, NUNCA mais transcrição da obra.

6. Gerar flashcards nativos por assunto  [se flashcards=true]
   - O Claude produz cards.json (front/back/tag) a partir do conteúdo redigido
   - scripts/flashcards_gen.py --cards cards.json --out-dir <pasta-do-aprofundamento>
   - IMPORTANTE: a --out-dir é a pasta do APROFUNDAMENTO
     (assuntos/{assunto}/{nivel}--{fonte}/), não a do assunto.
   - Passe --aprofundamento <id> (ou --nome-base): sem isso os arquivos saem com
     o nome legado e o wikilink do .md não resolve.
     Cada aprofundamento tem seus próprios flashcards, derivados da sua fonte.
   - No nível `detalhado`, gere mais cartões (cobrindo casos especiais e exceções)
   - Saída: flashcards-{slug}.md (Obsidian) + .csv (Anki)

7. Preparar a ponte NotebookLM  [Subsistema C — só o pacote, execução na próxima etapa]
   - scripts/notebooklm_pack.py --assuntos-dir <assuntos/> --concurso <c> --materia <m> [--leis-dir <...>]
   - Gera um pacote POR APROFUNDAMENTO: fontes diferentes merecem notebooks
     diferentes no NotebookLM (o material de origem não é o mesmo).
   - Gera _fonte-notebooklm.md por assunto: nome do notebook, fontes a subir,
     prompt de áudio pronto, roteiro de cliques (podcast/mapa mental/vídeo) e checklist.
   - UM notebook POR ASSUNTO (decisão de design: foco e qualidade; casa com reaproveitamento).

8. Validar e resumir
   - Conferir que nenhum {PLACEHOLDER} sobrou nos .md preenchidos
   - Apresentar: assuntos localizados/gerados, pendências de conferência,
     flashcards gerados, e o que fica pronto para a Etapa NotebookLM
```

## Estrutura gerada

```
30_AREAS/CARREIRA/CONCURSOS/{ORGAO}_{ANO}[_PREVISTO]/{_COMUM|CARGO}/03-APROFUNDAMENTO/{materia-slug}/
├── 00-INDICE-{MATERIA}.md              # índice da matéria (ganha coluna "no livro")
├── 00-COBERTURA-LIVRO.md               # o que no livro está fora do edital
├── mapa-localizacao.json               # onde cada assunto está no livro
└── assuntos/
    ├── concordancia-verbal-e-nominal/
    │   └── padrao--pestana/
    │       ├── concordancia-verbal-e-nominal--padrao--pestana--SEDES_2026.md
    │       ├── flashcards-concordancia-verbal-e-nominal--padrao--pestana--SEDES_2026.md
    │       ├── flashcards-concordancia-verbal-e-nominal--padrao--pestana--SEDES_2026.csv
    │       ├── cards.json
    │       └── _fonte-notebooklm.md    # pacote p/ a próxima etapa
    └── emprego-do-acento-indicativo-de-crase/
        ├── padrao--pestana/          # dois aprofundamentos do mesmo assunto,
        └── detalhado--pestana/       # lado a lado
```

> Matéria comum a vários cargos (ex.: Português) fica em `_COMUM/`; matéria
> específica fica na pasta do cargo.

## Ponte NotebookLM (próxima etapa — arquitetura de duas camadas)

Esta versão só **prepara** o insumo. A execução (gerar podcast/mapa mental) virá numa etapa seguinte, em duas camadas:

- **Camada garantida (manual/semi-auto):** a skill gera `_fonte-notebooklm.md` por assunto — um pacote com as fontes sugeridas (o .md do assunto + leis relacionadas) e um roteiro de cliques. O usuário sobe no NotebookLM manualmente.
- **Camada opcional (automatizada):** se a lib da comunidade `notebooklm-py` estiver instalada e funcionando, um script orquestra a criação do notebook, o upload das fontes e a geração dos artefatos. Como usa endpoints não-oficiais do Google, é frágil por natureza — se falhar, cai na camada manual sem perda.

Divisão de responsabilidades por artefato:
- **Podcast (áudio) e mapa mental** → especialidade do NotebookLM.
- **Flashcards e resumo esquemático** → gerados nativamente pela própria skill (melhor controle, sem dependência frágil). Já cobertos nesta versão.

## Scripts

Em `scripts/`:
- `aprofundamento_id.py` — **convenção de nomes de aprofundamento (fonte de verdade)**: monta e lê `{nivel}--{fonte}`; a `concurso-publica` tem cópia sincronizada
- `textmatch.py` — normalização e similaridade textual (compartilhado)
- `book_index.py` — **(Subsistema A)** localiza assuntos no livro (TOC ou densidade)
- `reuse_finder.py` — reaproveitamento: acha assuntos já aprofundados com o mesmo livro em outros concursos
- `notebooklm_pack.py` — gera o pacote NotebookLM por assunto (camada manual)
- `fix_notebooklm_packs.py` — atualiza os _fonte-notebooklm.md de um concurso já existente (com backup), sem regenerar resumos/flashcards
- `book_coverage.py` — relatório de cobertura: o que no livro está fora do edital (pulável)
- `build_subject_md.py` — **(Subsistema B)** gera o arcabouço .md por assunto
- `flashcards_gen.py` — geração nativa de flashcards (Obsidian + Anki). Passe `--aprofundamento`/`--nome-base` para o nome do arquivo casar com o wikilink do `.md`
- `migrar_aprofundamentos.py` — move material antigo para o padrão de pastas atual e reescreve os wikilinks (dry-run por padrão)
- `tests/test_smoke.py` — smoke tests

## Comportamento e princípios

- **Nunca fingir localização.** Confiança baixa/não-encontrado vira pendência explícita.
- **Direitos autorais (Modelo 2).** O resumo é original; do livro entram só páginas e trechos curtos citados. A skill não extrai o texto integral da obra.
- **Degradação graciosa.** Sem OCR, PDFs-imagem viram pendência com aviso. Sem `notebooklm-py`, a ponte fica manual.
- **Preservar trabalho do usuário.** Re-execuções não sobrescrevem resumos/cards já preenchidos sem aviso.
