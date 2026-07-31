# concurso-aprofunda

Segunda etapa do fluxo de preparação para concursos. Consome a saída da skill **concurso-prep** (assuntos já mapeados no vault) + um **livro de referência** denso e produz estudo aprofundado por assunto.

## O que faz

1. **Localiza no livro** cada assunto já mapeado da matéria — por sumário (TOC) ou, na falta dele, por densidade de termos. Saída: página exata + score de confiança.
2. **Gera um `.md` por assunto** no vault, no **Modelo 2**: resumo completo próprio + ponteiros de página + trechos-âncora curtos citados. Não copia a obra.
3. **Flashcards nativos** por assunto (Obsidian + Anki), sem depender do NotebookLM.
4. **Prepara a ponte NotebookLM** (podcast/mapa mental) para a etapa seguinte.

## Níveis e múltiplos aprofundamentos

Um assunto pode ter **vários aprofundamentos**, cada um na sua pasta, identificados
por `{nivel}--{fonte1}[+{fonte2}]`:

```
assuntos/emprego-do-acento-indicativo-de-crase/
├── padrao--pestana/
│   ├── emprego-do-acento-indicativo-de-crase--padrao--pestana--SEDES_2026.md
│   ├── flashcards-…--padrao--pestana--SEDES_2026.md   (Obsidian)
│   ├── flashcards-…--padrao--pestana--SEDES_2026.csv  (Anki)
│   └── _fonte-notebooklm.md
└── detalhado--pestana/
```

O slug da fonte é o sobrenome de um autor (`pestana`) ou o identificador da norma
(`lei-8742`, `res-cmn-4893`). O identificador carrega **só o que diferencia**: nível,
fonte e — no nome do arquivo — o concurso. O concurso está ali por motivo empírico:
18 arquivos colidiam entre `SEDES_2026` e `BB_2027_PREVISTO`, que usam o mesmo livro
para os mesmos assuntos, e o Obsidian resolve wikilink por nome de arquivo.

A convenção é implementada uma única vez, em `scripts/aprofundamento_id.py`, que é a
**fonte de verdade**. Detalhe completo no `SKILL.md`.


| Nível | Tamanho | Seções extras |
|---|---|---|
| `padrao` (default) | ~350-500 palavras | — |
| `detalhado` | ~1200-2500 palavras | visão geral, desenvolvimento completo, quadro de casos, exemplos resolvidos passo a passo, questões comentadas, divergências entre autores |

```
# revisão com um livro
Use a skill concurso-aprofunda: livro X, materia "Língua Portuguesa",
concurso SEDES_2026, nivel padrao

# depois, versão detalhada com OUTRA fonte (convivem lado a lado)
Use a skill concurso-aprofunda: livro Y, materia "Língua Portuguesa",
concurso SEDES_2026, nivel detalhado
```

Várias fontes numa mesma execução geram **um** aprofundamento combinado. O site
(`concurso-publica`) mostra as versões em abas na página do assunto.

## Pré-requisitos

- Python 3.10+
- `poppler-utils` (pdftotext/pdftoppm) para PDFs
- Opcional: `tesseract-ocr` + `tesseract-ocr-por` (só para PDFs escaneados)
- Uma preparação existente da `concurso-prep` no vault

## Uso (no Claude Code, dentro do vault)

```
Use a skill concurso-aprofunda:
- livro: "40_RECURSOS/livros/portugues-fernando-pestana.pdf"
- materia: "Língua Portuguesa"
- concurso: "SEDES_2026"
```

A skill localiza os assuntos no livro, gera os `.md` por assunto (que o Claude preenche com resumo completo e citações curtas) e os flashcards.

## Scripts (uso isolado)

```bash
# Localizar assuntos no livro
python scripts/book_index.py --livro livro.pdf --assuntos assuntos.json --out mapa.json

# Gerar arcabouço .md por assunto — SEMPRE com --fontes e --nivel: sem eles o
# script cai no caminho legado e a identidade do aprofundamento não se forma
python scripts/build_subject_md.py --mapa mapa.json --out-dir assuntos/ \
  --concurso SEDES_2026 --fontes "A Gramática para Concursos (Pestana)" --nivel padrao

# Flashcards — a --out-dir é a pasta do APROFUNDAMENTO, não a do assunto, e o
# nome-base precisa casar com o do .md, senão o wikilink do Obsidian não resolve
python scripts/flashcards_gen.py --cards cards.json \
  --out-dir assuntos/crase/padrao--pestana/ \
  --aprofundamento padrao--pestana --concurso SEDES_2026

# Cobertura do livro vs. edital · pacote NotebookLM · reaproveitamento entre concursos
python scripts/book_coverage.py --help
python scripts/notebooklm_pack.py --help
python scripts/reuse_finder.py --help

# Migrar aprofundamentos de uma convenção de pasta anterior
python scripts/migrar_aprofundamentos.py --help
```

Todos os scripts têm `--help`. O `aprofundamento_id.py` não é executável: é o módulo
com a convenção de nomes, importado pelos outros.

## Direitos autorais (Modelo 2)

O `.md` de cada assunto traz um resumo **original** (escrito do zero), a **localização** no livro (páginas) e, no máximo, **trechos curtos** citados com atribuição de página. A skill **não** extrai o texto integral do livro nem espalha cópias da obra pelo vault. Quando for preciso o texto completo, o caminho é apontar o NotebookLM diretamente para o PDF original.

## Confiança e honestidade

A localização vem com score. Assuntos não encontrados ou de baixa confiança viram **pendências explícitas** para conferência manual — a skill nunca inventa uma página.

## O que ainda não existe

- **Automação do NotebookLM.** A camada manual está pronta e é a garantida: a skill
  gera o pacote com as fontes e os prompts, e a `concurso-publica` publica isso como
  página com botão de copiar. A automação (via `notebooklm-py`, que usa endpoints
  internos não-documentados do Google) entraria como camada **opcional** por cima,
  nunca substituindo o modo manual.

O histórico de versões vive no [CHANGELOG.md](CHANGELOG.md) — antes havia um roadmap
aqui que repetia e contradizia o changelog.

Versão atual: **0.7.1** (todo prompt do NotebookLM ancora na **nota do vault**, nunca
no livro — que é fonte opcional no notebook; o pacote declara o nome do notebook e o
de cada arquivo de saída como contrato; e o migrador de pacotes voltou a enxergar o
layout atual, que ele não via desde a 0.5.0).
