# Setup do vault e do fluxo de trabalho

## Estrutura esperada no vault

As skills escrevem em `30_AREAS/CARREIRA/CONCURSOS/` (padrão PARA/Johnny-Decimal):

```
30_AREAS/CARREIRA/CONCURSOS/
├── .logs/
│   └── {ORGAO}_{ANO}/          # pendências e downloads falhos por concurso
├── SEDES_2026/
│   ├── .meta.json              # metadata + conteúdo programático integral
│   ├── 00-INDICE.md
│   ├── _COMUM/                 # compartilhado entre cargos
│   │   ├── 01-EDITAL/
│   │   ├── 04-MATERIAIS/leis-baixadas/   # .md + .pdf
│   │   ├── 05-HISTORICO-CONCURSO/
│   │   └── 06-SINERGIA/
│   └── EDAS-ADMINISTRACAO/     # um por cargo
│       ├── 02-CRONOGRAMA/
│       └── 03-MAPAS-MATERIAS/
│           └── lingua-portuguesa/
│               ├── 00-INDICE-*.md
│               ├── mapa-localizacao.json
│               └── assuntos/
│                   └── crase/
│                       ├── crase.md
│                       ├── flashcards-crase.md   (Obsidian)
│                       ├── flashcards-crase.csv  (Anki)
│                       ├── _fonte-notebooklm.md
│                       └── (podcast/mapa/vídeo/report salvos aqui)
└── BB_2027_PREVISTO/           # concurso sem edital ainda
```

Onde colocar os insumos (sugestão):
- Editais: `99_INBOX/` ou uma pasta de entrada de sua preferência
- Livros de referência: `40_RECURSOS/livros/`

## Plugins do Obsidian recomendados

- **Spaced Repetition** — para revisar os flashcards gerados (tag `#flashcards`, formato `pergunta / ?? / resposta`).

## Fluxo típico

1. **Edital novo** → rodar `concurso-prep` → estrutura completa criada.
2. **Aprofundar uma matéria** → rodar `concurso-aprofunda` com o livro → assuntos + flashcards + pacotes NotebookLM.
3. **Gerar os derivados** → seguir o `_fonte-notebooklm.md` de cada assunto (manual, no NotebookLM).
4. **Edital retificado / saiu o oficial** → rodar `concurso-prep --reconciliar` → nova versão lado a lado, com diff e progresso migrado.
5. **Publicar o site** → rodar `concurso-publica` (ou `./deploy/deploy.sh --concurso-dir <...>`) → site estático com as mídias embutidas, servido no servidor doméstico.

O site é **derivado e regenerável**: ele nunca escreve no vault. Republique quantas vezes quiser.

## Manutenção

Depois de atualizar o repositório:

```bash
git pull
bash scripts/install.sh     # reinstala as skills
# reinicie a sessão do Claude Code
```

Reinstalar **não toca no vault** — apenas substitui as skills em `~/.claude/skills/`. O material gerado (resumos, flashcards, progresso) é preservado.

Para atualizar apenas os pacotes NotebookLM de um concurso já aprofundado (após mudanças no template), sem regenerar resumos:

```bash
python ~/.claude/skills/concurso-aprofunda/scripts/fix_notebooklm_packs.py \
  --assuntos-dir "<...>/03-MAPAS-MATERIAS/<materia>/assuntos" \
  --concurso "BB_2027_PREVISTO" --materia "Língua Portuguesa" --dry-run
```

## Publicação (opcional)

Ver [`deploy/README.md`](../deploy/README.md) para servir o site num container Docker no servidor doméstico, com o snippet do proxy reverso e o dimensionamento de recursos.

## Versionar o vault?

Este repositório guarda **as skills**, não o conteúdo gerado. O vault costuma ter material protegido por direitos autorais (livros) e dados pessoais de estudo — mantenha-o fora deste repo. O `.gitignore` já bloqueia `vault/` e `out/` por precaução.
