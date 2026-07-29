# concurso-prep

Skill para Claude Code que gera estrutura completa de preparação para concurso público a partir de um edital, replicando o workflow de análise manual: cronograma adaptativo, mapas detalhados por matéria, materiais de referência baixados, histórico do órgão e identificação de provas com sinergia.

---

## 🎯 O que faz

A partir de um arquivo de edital (PDF/DOCX/MD) e do cargo pretendido, a skill:

1. **Faz parse estruturado** do edital — datas, vagas, conteúdo programático completo
2. **Analisa o perfil da banca** organizadora
3. **Gera cronograma adaptativo** baseado no tempo até a prova (4 fases se >6 meses, modo emergência se <1 mês)
4. **Cria um mapa detalhado por matéria** com subtópicos, prioridades, pegadinhas e checklists
5. **Coleta materiais de referência** — livros, canais YouTube, plataformas de questões
6. **Baixa PDFs de leis** citadas no edital (Planalto, SINJ-DF, etc.)
7. **Pesquisa o histórico do órgão** — bancas anteriores, vagas para o cargo, baixa editais antigos
8. **Identifica concursos com sinergia** — mesma banca + matérias em comum
9. **Trata prova discursiva** quando aplicável — formato, critérios, temas prováveis
10. **Valida tudo** ao final — links, placeholders, PDFs, datas

Tudo persistido em **Markdown no vault Obsidian**, sob `30_AREAS/CARREIRA/CONCURSOS/{ORGAO}_{ANO}/`.

---

## 📦 Instalação

### Pré-requisitos
- Claude Code instalado
- Python 3.10+
- `poppler-utils` (para `pdftotext`):
  ```bash
  # Ubuntu/Debian
  sudo apt install poppler-utils
  # macOS
  brew install poppler
  ```
- Dependências Python (todas opcionais, ver `requirements.txt`):
  ```bash
  pip install -r requirements.txt
  ```
  - `reportlab` — gera as leis em PDF (sem ele, só o Markdown é gerado)
  - `weasyprint` — PDF com melhor fidelidade (opcional; cai no reportlab se faltar)
  - `python-docx` — processa editais em `.docx`
  - `pyyaml` — apenas para ler `.meta.yml` legado (novos usam `.meta.json`)

### Instalar a skill

```bash
# Skill global (todos os projetos)
cp -r concurso-prep ~/.claude/skills/

# OU skill local (só este projeto)
cp -r concurso-prep .claude/skills/
```

### Instalar os subagents

```bash
# Subagents globais
mkdir -p ~/.claude/agents/
cp concurso-prep/agents/*.md ~/.claude/agents/

# OU subagents locais
mkdir -p .claude/agents/
cp concurso-prep/agents/*.md .claude/agents/
```

### Verificar instalação

No Claude Code:
```
/skills
```
Deve listar `concurso-prep` entre as disponíveis.

---

## 🚀 Uso

Dentro do Claude Code, no diretório raiz do seu vault Obsidian:

```
Use a skill concurso-prep para preparar o concurso a partir 
do edital em "99_INBOX/OUTROS/edital-sedes-2026.pdf" para o cargo 
"EDAS Administração"
```

### Parâmetros

| Parâmetro | Obrigatório | Default | Descrição |
|---|---|---|---|
| `edital` | sim | — | Caminho do PDF/DOCX/MD do edital (no modo previsto, é o edital anterior usado como proxy) |
| `cargo` | sim | — | Cargo pretendido. Multi-cargo: separar por vírgula |
| `modo` | não | `oficial` | `oficial` (com datas) ou `previsto` (sem edital ainda, cronograma relativo) |
| `reconciliar` | não | false | Atualiza o que já existe quando o edital sai (previsto→oficial) ou é retificado (oficial→retificado). Exige `--edital` com o edital novo |
| `ano-esperado` | não | ano+1 | (modo previsto) ano estimado para o nome da pasta `{ORGAO}_{ANO}_PREVISTO` |
| `formatos-lei` | não | `md,pdf` | Formatos das leis baixadas: `md`, `pdf` ou ambos |
| `vault-root` | não | auto-detect | Raiz do vault Obsidian |
| `horas-dia` | não | 4 | Horas de estudo por dia |
| `force-overwrite` | não | false | Substituir pasta destino |
| `no-download` | não | false | Pular downloads |

### Exemplo multi-cargo

```
Skill concurso-prep com edital em "99_INBOX/edital-sedes.pdf" e 
cargos "EDAS:Administração,TDAS:Administrativo"
```

Isso gera uma única pasta `SEDES_2026/` com:
- `_COMUM/` — edital, materiais, histórico (compartilhados)
- `EDAS-Administracao/` — cronograma e mapas específicos
- `TDAS-Administrativo/` — cronograma e mapas específicos

---

## 📁 Estrutura gerada

```
{vault}/30_AREAS/CARREIRA/CONCURSOS/{ORGAO}_{ANO}/
├── 00-INDICE.md
├── .meta.json
├── _COMUM/
│   ├── 01-EDITAL/
│   │   ├── edital-original.pdf
│   │   ├── edital-resumo.md
│   │   ├── cronograma-oficial.md
│   │   └── analise-banca.md
│   ├── 04-MATERIAIS/
│   │   ├── livros-recomendados.md
│   │   ├── canais-youtube.md
│   │   ├── plataformas-questoes.md
│   │   └── leis-baixadas/*.md + *.pdf
│   ├── 05-HISTORICO-CONCURSO/
│   │   ├── concursos-anteriores.md
│   │   ├── editais-anteriores/*.pdf
│   │   └── provas-anteriores/*.pdf
│   └── 06-SINERGIA/
│       ├── concursos-similares.md
│       └── provas-baixadas/*.pdf
└── {CARGO-SLUG-UPPER}/    # ex: EDAS-ADMINISTRACAO
    ├── 02-CRONOGRAMA/
    │   ├── cronograma-macro.md
    │   ├── cronograma-semanal.md
    │   ├── rotina-diaria.md
    │   └── metas-quantitativas.md
    ├── 03-MAPAS-MATERIAS/
    │   ├── 00-INDICE.md
    │   ├── 01-Portugues.md
    │   ├── 02-...md
    │   └── ...
    ├── 07-DISCURSIVA/      # se aplicável
    └── 99-Status.md
```

---

## 📐 Convenção de nomeação

**Todas as pastas são geradas em UPPERCASE.** Nomes de cargo viram slug sem acento/espaço e em maiúsculas:

| Cargo informado | Pasta gerada |
|---|---|
| `EDAS Administração` | `EDAS-ADMINISTRACAO` |
| `TDAS Administrativo` | `TDAS-ADMINISTRATIVO` |
| `Técnico Judiciário - Área Administrativa` | `TECNICO-JUDICIARIO-AREA-ADMINISTRATIVA` |

Pasta do concurso: `{ORGAO}_{ANO}` em uppercase (ex: `SEDES_2026`). O nome "bonito" (com acento) aparece só no título interno dos arquivos `.md`.

Helper: `scripts/slugify.py "EDAS Administração"` → `EDAS-ADMINISTRACAO`

---

## 🔀 Modos de operação

A skill tem dois modos, via `--modo`:

### `oficial` (default)
Edital vigente, com cronograma e datas reais. Comportamento completo.

### `previsto`
Para **concursos esperados mas ainda sem edital publicado**. Você fornece o **edital anterior** como proxy de conteúdo:

```
concurso-prep --modo previsto --edital "99_INBOX/OUTROS/edital-2022.pdf" --cargo "Analista Administrativo"
```

- Gera tudo (mapas, materiais, histórico, sinergias) **sem datas**
- Cronograma é **relativo** (Semana 1, 2... no seu ritmo)
- Pasta recebe sufixo `_PREVISTO` (ex: `TJDFT_2026_PREVISTO`)
- Todo arquivo leva banner `⚠️ CONTEÚDO PROVISÓRIO`

### Reconciliação — quando o edital oficial sai

```
concurso-prep --reconciliar --edital "99_INBOX/OUTROS/edital-oficial.pdf" --cargo "Analista Administrativo" --modo oficial
```

- Preserva a versão prevista intacta, renomeando para `_V1-PREVISTO` (seu progresso fica salvo)
- Gera `_V2-OFICIAL` nova, com datas reais
- Produz `00-DIFF-PREVISTO-VS-OFICIAL.md` mostrando 🟢 mantidos / 🔴 removidos / 🆕 novos / 🔀 alterados
- Migra automaticamente o progresso dos tópicos que continuam valendo

---

## ⚙️ Como funciona internamente

A skill orquestra **5 subagents especializados** que rodam em paralelo quando possível:

| Subagent | Função |
|---|---|
| `edital-parser` | Extrai estrutura do edital → JSON |
| `materia-mapper` | Gera mapa detalhado de UMA matéria (rodam em paralelo) |
| `material-collector` | Busca/baixa materiais de referência |
| `historico-researcher` | Pesquisa histórico do órgão + baixa editais antigos |
| `sinergia-finder` | Identifica concursos com matérias em comum |

### Fluxo das 10 etapas

```
1. Bootstrap (validação + logs)
2. Parse do edital → edital-parser
3. Análise da banca → web search
4. Cronograma macro (adaptativo)
5. Mapas por matéria → materia-mapper (paralelo)
6. Coleta de materiais → material-collector
7. Histórico do órgão → historico-researcher
8. Sinergias → sinergia-finder
9. Discursiva (condicional)
10. Índices + validação + finalização
```

### Cronograma adaptativo

| Tempo até a prova | Fases | Distribuição |
|---|---|---|
| > 180 dias | Fundação → Aprofundamento → Reta Final → Preparação Final | 35/35/20/10% |
| 90-180 dias | Fundação → Aprofundamento → Reta Final | 40/40/20% |
| 30-90 dias | Revisão Acelerada → Simulados Intensivos | 60/40% |
| < 30 dias | Modo Emergência | 100% |

---

## 🔄 Re-execução

Se a pasta destino já existe, a skill pergunta:

1. **Substituir tudo** (`--force-overwrite`)
2. **Atualizar** preservando arquivos modificados por você (detectados por hash em `.meta.json`)
3. **Abortar**

Arquivos sempre preservados:
- `99-Status.md` (seu progresso)
- Qualquer `.md` cujo hash mudou desde a última geração

---

## 📊 Logs

Localização: `{vault}/30_AREAS/CARREIRA/CONCURSOS/.logs/`

Arquivos:
- `execucao-{TIMESTAMP}.log` — eventos de execução com duração
- `pendencias.md` — itens que precisam ação manual
- `downloads-falhos.md` — URLs que falharam (tentar manualmente)
- `validacao-{TIMESTAMP}.json` — saída da validação final

---

## 🧪 Validação automática

Ao final, a skill roda `scripts/validate_output.py` que checa:

- [x] Estrutura de pastas existe
- [x] Nenhum placeholder `{XXX}` deixado nos `.md`
- [x] Wikilinks `[[...]]` apontam para arquivos existentes
- [x] Soma de questões por matéria bate com total da prova
- [x] Cronograma termina antes da prova
- [x] PDFs baixados têm header `%PDF-` válido
- [x] Tags Obsidian consistentes

Problemas vão para `pendencias.md`.

---

## 🛠️ Customização

### Templates

Cada arquivo gerado parte de um template em `assets/templates/*.md.tpl`. Para customizar:

1. Edite o `.md.tpl` desejado
2. Mantenha os placeholders `{NOME_VARIAVEL}` que a skill preenche
3. Re-execute (a skill detecta o template novo automaticamente)

### Adicionar novo subagent

1. Crie `.claude/agents/seu-agent.md` com frontmatter (`name`, `description`, `tools`)
2. Adicione referência na seção apropriada do `SKILL.md`

---

## 📋 Limitações conhecidas

- **Não baixa livros** (questão de copyright) — só lista título/autor/ISBN
- **Não reproduz conteúdo** de provas anteriores — só baixa o PDF quando disponível publicamente
- **Editais muito atípicos** (sem cronograma claro, sem conteúdo programático separado) podem precisar de ajustes manuais
- **Bancas pequenas/desconhecidas** caem em perfil genérico

---

## 🐛 Troubleshooting

### "Edital não encontrado"
Verifique o caminho. Se relativo, é relativo ao diretório atual no Claude Code (geralmente raiz do vault).

### "Vault não detectado"
Passe `vault-root` explicitamente. A skill procura pasta `.obsidian/` subindo a árvore.

### "Subagent timeout"
A skill faz 2 retries automaticamente. Em caso de falha persistente, o conteúdo daquela etapa fica em `pendencias.md`.

### PDF de lei não baixou
Algumas leis estaduais não estão em portais padronizados. Veja `downloads-falhos.md` para tentar manualmente.

---

## 📚 Estrutura do projeto

```
concurso-prep/
├── SKILL.md                    # orquestrador principal (10 etapas + reconciliação)
├── README.md                   # este arquivo
├── install.sh                  # instalador (global/local/uninstall)
├── agents/
│   ├── edital-parser.md
│   ├── materia-mapper.md
│   ├── material-collector.md
│   ├── historico-researcher.md
│   └── sinergia-finder.md
├── assets/
│   ├── config.yml              # defaults (inclui modos previsto/reconciliação)
│   └── templates/              # 13 templates .md.tpl
├── scripts/
│   ├── extract_edital.py       # PDF/DOCX/MD → texto
│   ├── fetch_pdf.py            # download robusto
│   ├── slugify.py              # nomes de pasta UPPERCASE
│   ├── diff_editais.py         # diff de conteúdo programático (reconciliação)
│   ├── validate_output.py      # validação final
│   └── log_helper.py           # logging
└── examples/
    ├── sedes-2026-mock/        # caso modo oficial
    └── previsto-reconciliacao/ # caso modo previsto + reconciliação
```

---

## 📜 Changelog

Histórico de versões em [CHANGELOG.md](CHANGELOG.md). Versão atual: **1.3.1** (correções no validador: soma por cargo, wikilinks com pipe escapado, metadata em YAML legado; `diff_editais.py` aceita a pasta do concurso).

---

## 📝 Licença

Uso pessoal. Não reproduzir conteúdo de obras protegidas (livros, provas) — a skill respeita isso por design.
