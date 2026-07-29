# concursos-vault-skills

Skills do [Claude Code](https://claude.com/claude-code) que automatizam a preparação para **concursos públicos brasileiros**, gerando material de estudo estruturado direto num **vault Obsidian**.

## As skills

| Skill | Etapa | O que faz |
|---|---|---|
| **`concurso-prep`** | 1 | Do **edital** → estrutura completa de estudos: cronograma em 3 fases, mapas por matéria, análise da banca, histórico do órgão, leis baixadas (MD+PDF), sinergias entre concursos |
| **`concurso-aprofunda`** | 2 | Do **livro de referência** → um `.md` por assunto (resumo próprio + páginas do livro + citações curtas), flashcards (Obsidian/Anki) e o pacote para gerar podcast/mapa mental/vídeo/report no NotebookLM |
| **`concurso-publica`** | 3 | Do **vault** → site estático navegável, com uma página por assunto onde o podcast toca, o vídeo roda, o mapa e o infográfico aparecem e os flashcards viram quiz |

Cada etapa consome a saída da anterior.

### Destaques

- **Modo previsto**: começa a estudar antes do edital sair, usando o edital anterior como proxy (cronograma sem datas, tudo marcado como provisório).
- **Reconciliação e retificação**: quando o edital sai (ou é retificado), gera nova versão lado a lado (`V1-PREVISTO` → `V2-OFICIAL` → `V3-RETIFICADO`), com diff de conteúdo programático e de estrutura da prova (vagas, salário, nº de questões), preservando o progresso já feito.
- **Reaproveitamento entre concursos**: se um assunto já foi aprofundado com o mesmo livro em outro concurso, a skill detecta e reaproveita em vez de refazer.
- **Localização automática no livro**: casa cada assunto do edital com as páginas do livro (via sumário ou densidade de termos), com score de confiança — e marca como pendência o que não achou com segurança.
- **Vários aprofundamentos por assunto**: o mesmo assunto pode ter versões de fontes diferentes e em dois níveis (padrão para revisão, detalhado para domínio), selecionáveis no site.
- **Site de estudo**: tema claro/escuro, concursos agrupados por órgão, assuntos agrupados por prioridade (alta/média/base) e download de todas as mídias.

## Instalação

```bash
git clone <url-do-repo>
cd concursos-vault-skills

# instala todas as skills no Claude Code (~/.claude/)
bash scripts/install.sh

# ou apenas uma
bash scripts/install.sh --only concurso-aprofunda

# ver o que há disponível
bash scripts/install.sh --list
```

> **Reinicie a sessão do Claude Code** depois de instalar/atualizar — as skills são carregadas no início da sessão.

### Pré-requisitos

- Python 3.10+
- `poppler-utils` (`pdftotext`) — para ler editais e livros em PDF
- Opcionais: `reportlab` (leis em PDF), `tesseract-ocr` (livros escaneados), `python-docx` (editais .docx)

```bash
pip install -r skills/concurso-prep/requirements.txt
```

## Uso

Dentro do vault, no Claude Code:

```
# Etapa 1
Use a skill concurso-prep:
- edital: "99_INBOX/edital-sedes-2026.pdf"
- cargo: "EDAS Administração"

# Etapa 2
Use a skill concurso-aprofunda:
- livro: "40_RECURSOS/livros/gramatica-pestana.pdf"
- materia: "Língua Portuguesa"
- concurso: "SEDES_2026"

# Etapa 3 (site)
Use a skill concurso-publica para gerar o site do concurso SEDES_2026
```

Veja o `README.md` de cada skill para todos os parâmetros.

## Publicar o site (servidor doméstico)

O site gerado pela Etapa 3 pode ser servido num container Docker enxuto. Tudo em [`deploy/`](deploy/):

```bash
# 1ª vez: prepara o servidor e sobe o container
./deploy/deploy.sh --setup

# a cada atualização do vault: gera o site e sincroniza (rsync)
./deploy/deploy.sh --concurso-dir ~/vault/.../CONCURSOS/SEDES_2026
./deploy/deploy.sh --concurso-dir <...> --dry-run      # conferir antes
```

O container usa **bind mount**, então atualizar o site é só sincronizar arquivos — sem rebuild de imagem nem restart. Limites dimensionados para ~3 usuários simultâneos (0.5 CPU / 128 MB). Detalhes, snippet do proxy reverso e troubleshooting em [`deploy/README.md`](deploy/README.md).

## Desenvolvimento

```bash
bash scripts/test-all.sh              # testes de todas as skills
bash scripts/test-all.sh --only concurso-prep
```

Convenções e diretrizes de contribuição estão no [`CLAUDE.md`](CLAUDE.md) — vale ler antes de mexer, pois várias regras vieram de bugs reais.

## Nota sobre direitos autorais

A Etapa 2 trabalha com livros protegidos por direitos autorais e **não extrai o texto integral** deles. Cada arquivo de assunto traz um resumo **original**, a **localização** no livro (páginas) e, no máximo, **trechos curtos citados** com atribuição. O objetivo é orientar o estudo no livro, não substituí-lo.

## Licença

MIT — veja [LICENSE](LICENSE).
