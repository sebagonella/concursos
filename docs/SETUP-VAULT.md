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
│   │   ├── 06-SINERGIA/
│   │   ├── 03-MAPAS-COMUNS/    # mapas de matéria comuns a vários cargos
│   │   │   └── 01-lingua-portuguesa.md      # .md PLANO, um por matéria
│   │   └── 03-APROFUNDAMENTO/  # saída da Etapa 2 (pode ficar no cargo também)
│   │       └── lingua-portuguesa/
│   │           ├── 00-INDICE-LINGUA-PORTUGUESA.md
│   │           ├── 00-COBERTURA-LIVRO.md
│   │           ├── mapa-localizacao.json
│   │           └── assuntos/
│   │               └── emprego-do-acento-indicativo-de-crase/
│   │                   ├── padrao--pestana/      # {nivel}--{fonte}
│   │                   │   ├── …--padrao--pestana--SEDES_2026.md
│   │                   │   ├── flashcards-…--padrao--pestana--SEDES_2026.md  (Obsidian)
│   │                   │   ├── flashcards-…--padrao--pestana--SEDES_2026.csv (Anki)
│   │                   │   ├── _fonte-notebooklm.md
│   │                   │   └── (podcast/mapa/vídeo/report salvos aqui)
│   │                   └── detalhado--pestana/   # outra profundidade, lado a lado
│   └── EDAS-ADMINISTRACAO/     # um por cargo
│       ├── 02-CRONOGRAMA/
│       ├── 03-MAPAS-MATERIAS/  # mapas específicos do cargo (.md planos)
│       ├── 07-DISCURSIVA/
│       └── 99-Status.md
└── BB_2027_PREVISTO/           # concurso sem edital ainda
```

> **`03-MAPAS-*` e `03-APROFUNDAMENTO` são coisas diferentes.** Os mapas são o
> **plano** do edital: um `.md` plano por matéria, gerado pela Etapa 1. O
> aprofundamento é o **conteúdo** vindo do livro, gerado pela Etapa 2, com um nível de
> pasta por `{nivel}--{fonte}`. Confundir os dois já custou um bug que ficou verde por
> meses (registrado no `CLAUDE.md`), porque o fixture do teste montava assuntos sob
> `03-MAPAS-MATERIAS` — caminho que a `concurso-aprofunda` nunca emite.

Onde colocar os insumos (sugestão):
- Editais: `99_INBOX/` ou uma pasta de entrada de sua preferência
- Livros de referência: `40_RECURSOS/livros/`

## Plugins do Obsidian recomendados

- **Spaced Repetition** — para revisar os flashcards gerados (tag `#flashcards`, formato `pergunta / ?? / resposta`).

## Fluxo típico

1. **Edital novo** → rodar `concurso-prep` → estrutura completa criada.
2. **Aprofundar uma matéria** → rodar `concurso-aprofunda` com o livro → assuntos + flashcards + pacotes NotebookLM.
3. **Gerar os derivados** → abrir a página `notebooklm/` do assunto no site (ou o
   `_fonte-notebooklm.md` no vault), copiar os prompts e rodar no NotebookLM. Ao
   terminar, **colar a URL do notebook em `notebooklm_url:`** no pack: é a única
   condição para o botão "Abrir no NotebookLM" aparecer no site. A regeneração do
   pack preserva esse valor.
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
  --assuntos-dir "<...>/03-APROFUNDAMENTO/<materia>/assuntos" \
  --concurso "BB_2027_PREVISTO" --materia "Língua Portuguesa" --dry-run
```

## Publicação (opcional)

Ver [`deploy/README.md`](../deploy/README.md) para servir o site num container Docker no servidor doméstico, com o dimensionamento de recursos, a troca de porta e o troubleshooting.

## Versionar o vault?

Este repositório guarda **as skills**, não o conteúdo gerado. O vault costuma ter material protegido por direitos autorais (livros) e dados pessoais de estudo — mantenha-o fora deste repo. O `.gitignore` já bloqueia `vault/` e `out/` por precaução.
