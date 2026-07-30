# CLAUDE.md

Orientação para o Claude Code trabalhando neste repositório.

## Vault Obsidian
- **Vault:** /home/sebagonella/work/cloud/1_insync-gdrive-sebastiao.gonella/02_SYNC-ALIVE/01_COFRES/02_NOTEBOOKS/02_OBSIDIAN/0_sebagonella2
- **Nota do projeto:** 20_PROJETOS/PROFISSIONAL/14_concursos/_PROJETO.md
- **Sessoes:** 20_PROJETOS/PROFISSIONAL/14_concursos/SESSOES/
- **Decisoes:** 20_PROJETOS/PROFISSIONAL/14_concursos/DECISOES/
- **Pesquisas:** 20_PROJETOS/PROFISSIONAL/14_concursos/PESQUISAS/
- **Tarefas:** 20_PROJETOS/PROFISSIONAL/14_concursos/TAREFAS/

## O que é este projeto

Coleção de **skills do Claude Code** que automatizam a preparação para concursos públicos brasileiros, gerando conteúdo estruturado direto num **vault Obsidian**.

O fluxo tem três etapas encadeadas:

1. **`concurso-prep`** (Etapa 1) — a partir de um edital (PDF/DOCX/MD), monta a estrutura completa de estudos: cronograma, mapas por matéria, análise da banca, histórico do órgão, materiais (leis baixadas em MD+PDF), sinergias entre concursos. Suporta concurso *previsto* (sem edital ainda) e *reconciliação/retificação* quando o edital sai ou muda.
2. **`concurso-aprofunda`** (Etapa 2) — consome a saída da Etapa 1 + um livro de referência denso. Localiza cada assunto no livro, gera um `.md` por assunto (resumo próprio + ponteiros de página + citações curtas), flashcards nativos e o pacote para gerar podcast/mapa mental/vídeo/report no NotebookLM.
3. **`concurso-publica`** (Etapa 3) — transforma a pasta de um concurso em **site estático** que espelha a organização do vault (`{concurso}/{comum|cargo}/`) e publica **todo** o conteúdo abaixo do concurso: edital, cronograma, mapas de matéria, materiais e leis, histórico, sinergia, discursiva, títulos e o aprofundamento, com mídias embutidas, quiz de flashcards e uma página por assunto para o pacote NotebookLM. Cada matéria abre em duas visões — **Plano** (o mapa do edital) e **Estudo** (os assuntos aprofundados). Decisões travadas: gerador próprio em Python (sem Node), por concurso, uso local/rede doméstica, **site só leitura** (progresso lido do vault na geração; o vault é a única fonte de verdade), link NotebookLM apenas se `notebooklm_url:` preenchida (sem iframe do Google).

O repositório é versionado no GitHub e instalado localmente no Claude Code do usuário.

## Estrutura

```
skills/
├── concurso-prep/          # Etapa 1 — edital → estrutura de estudos
│   ├── SKILL.md            # orquestrador (fluxo de 10 etapas)
│   ├── agents/             # 5 subagents especializados
│   ├── assets/templates/   # templates .md.tpl
│   ├── scripts/            # utilitários Python
│   └── examples/
├── concurso-aprofunda/     # Etapa 2 — livro → assuntos aprofundados
│   ├── SKILL.md
│   ├── assets/templates/
│   ├── scripts/
│   └── examples/
└── concurso-publica/       # Etapa 3 — concurso → site estático
    ├── SKILL.md
    ├── assets/             # site.css, site.js (sem CDN: o site roda offline)
    ├── scripts/            # site_collector.py, site_builder.py, md2html.py
    └── examples/           # site-model-exemplo.json (o contrato entre A e B)

scripts/install.sh          # instalador único (instala/atualiza todas as skills)
scripts/test-all.sh         # roda as suítes de todas as skills
deploy/                     # Docker + rsync para servir o site num servidor doméstico
├── docker-compose.yml      # nginx:alpine, bind mount, ${CONCURSOS_PORTA:-8099}, 0.5 CPU / 128 MB
├── nginx.conf              # serve na raiz em concursos.casa:8099
├── deploy.sh               # gera o site do vault e sincroniza via SSH
└── README.md               # instalação, troca de porta e troubleshooting
docs/
├── ARQUITETURA.md          # decisões de projeto e o porquê + diagrama do fluxo
├── SETUP-VAULT.md          # preparar o vault Obsidian
├── fluxo-concurso.mmd      # fonte Mermaid do diagrama
└── fluxo-concurso.png      # o mesmo diagrama em imagem (referenciado no README)
```

> O índice navegável de toda a documentação está no [`README.md`](README.md#documentação).

## Comandos

```bash
# Instalar/atualizar TODAS as skills (global, em ~/.claude/)
bash scripts/install.sh

# Instalar só uma
bash scripts/install.sh --only concurso-aprofunda

# Instalação local (no .claude/ do diretório atual)
bash scripts/install.sh --local

# Desinstalar
bash scripts/install.sh --uninstall

# Rodar os testes de todas as skills
bash scripts/test-all.sh

# Publicar o site no servidor doméstico (Docker + rsync)
./deploy/deploy.sh --setup                              # 1ª vez
./deploy/deploy.sh --concurso-dir <.../SEDES_2026>      # atualizações
./deploy/deploy.sh --concurso-dir <...> --dry-run       # conferir antes
```

> Após instalar/atualizar, **reinicie a sessão do Claude Code** — ele carrega as skills no início da sessão e pode manter a versão anterior em cache.

## Convenções invioláveis

Estas regras vieram de bugs reais. Quebrá-las volta a quebrar coisas.

- **Slugs em UPPERCASE** para pastas de concurso e cargo: `SEDES_2026`, `EDAS-ADMINISTRACAO`, `_COMUM`. O validador checa isso.
- **Path canônico do aprofundamento** — um assunto pode ter vários, cada um na sua pasta:

  ```
  30_AREAS/CARREIRA/CONCURSOS/{ORGAO}_{ANO}[_PREVISTO]/{_COMUM|CARGO}/
  └── 03-APROFUNDAMENTO/{slug-materia}/assuntos/{slug-assunto}/
      └── {padrao|detalhado}--{fonte1}[+{fonte2}]/
          └── {slug-assunto}--{padrao|detalhado}--{fonte1}[+...]--{CONCURSO}.md
  ```

  **Cada componente existe porque diferencia alguma coisa** — nível diferencia profundidade, fonte diferencia origem, concurso diferencia contexto. Não acrescente campo que não desempata: contador de fontes e índice posicional (`2f`, `f1-`) foram removidos justamente por serem deriváveis. O slug da fonte é o **sobrenome de um autor** (`pestana`, `kotler`) ou o **identificador da norma** (`lei-8742`, `lc-105`, `leidf-6938`, `res-cmn-4893`); alteração posterior da mesma norma não conta como fonte extra. A regra vive em `skills/concurso-aprofunda/scripts/aprofundamento_id.py`, **fonte de verdade**, com cópia sincronizada em `concurso-publica` barrada por teste. Não reimplemente a convenção em outro lugar.
- **A fonte fica no nome mesmo quando é única, e o concurso sempre**: omitir a fonte obrigaria a renomear o aprofundamento quando surgisse a segunda — e renomear quebra wikilink e progresso. O concurso resolve colisão real entre concursos que usam o mesmo livro.
- **Nome de arquivo repete o identificador do aprofundamento**: o Obsidian resolve wikilink por *nome de arquivo*, então dois `crase.md` em pastas diferentes ficam ambíguos. Todo script que gera artefato de aprofundamento (`.md`, flashcards) precisa receber o nome-base — foi exatamente daí que veio o bug do `flashcards_gen.py`.
- **Mover material no vault reescreve wikilink**: os índices de matéria (`00-INDICE-*.md`) ficam **fora** de `assuntos/` e apontam para o path completo. Migração que só move pasta deixa o vault cheio de link quebrado.
- **Metadata em `.meta.json`** (não YAML). Deve conter o **conteúdo programático integral** (`materias[].topicos`) — o motor de diff depende disso — e o `edital_hash` (SHA-256) para detectar edital alterado.
- **Nunca sobrescrever versão anterior** numa reconciliação. Gera-se `V1-PREVISTO` → `V2-OFICIAL` → `V3-RETIFICADO`, lado a lado, preservando o progresso do usuário.
- **Direitos autorais (Modelo 2)**: a Etapa 2 **não** extrai o texto integral de livros protegidos. Do livro entram apenas localização (páginas) e **trechos curtos citados**. O resumo é sempre original, escrito do zero. Não relaxar isso.
- **Flashcards do Obsidian**: no formato multi-linha, o `??` precisa ficar **sozinho na própria linha** entre pergunta e resposta. Colado na resposta, o plugin Spaced Repetition não lê o cartão.
- **Nunca fingir precisão**: localização de assunto com baixa confiança ou não encontrada vira **pendência explícita** para conferência humana. Não inventar página.
- **O site é derivado, o vault é a fonte**: a `concurso-publica` nunca escreve no vault. O progresso exibido no site vem dos checkboxes dos `.md` e é **só leitura** — não criar um segundo lugar onde o progresso vive.
- **O site espelha COMUM/cargo**: a estrutura de saída é `{concurso}/{comum|cargo}/`, como as pastas do vault. `00-INDICE.md` e `99-Status.md` são **derivados, não republicados** — a navegação do site é o índice, e o progresso do status vira a barra do hub do escopo. Mas eles continuam sendo *lidos*: é de lá que saem a ordenação das matérias e os selos de questões/prioridade.
- **Nunca inferir o link mapa↔assunto por slug**: dos 203 tópicos dos 24 mapas do vault, ~18% casam. Um tópico do edital pode cobrir vários assuntos, aprofundamento por legislação é N:M, e assunto reaproveitado de outro concurso mantém o slug do edital de origem. Sem casamento exato, a página **não afirma nada** — o falso negativo ("sem aprofundamento" quando existe com outro nome) esconde trabalho feito. O link fino vem de `mapa-aliases.json`, opcional.
- **Nada escrito no tópico do mapa se perde em silêncio**: rótulo de H3 fora do template é **publicado** (com o texto do vault) **e avisado** na geração — publicar sem avisar esconde que template e vault divergiram, avisar sem publicar foi o bug que sumiu com 50 blocos (`Leis-chave`, mnemônicos 🧠). Rótulo repetido no mesmo tópico **acumula**, nunca sobrescreve: guardar as subseções num dict chave→markdown perdia 57 subtópicos em 5 tópicos. E **a lista exibida tem de contar o mesmo que o contador do rodapé** — foi a contradição (1 item listado sob `0/22 itens do plano`) que denunciou o defeito, e há teste que trava o invariante.
- **Cobertura é contagem; qualidade não se inventa**: a % de tópicos com aprofundamento sai do `topico_id` gravado, e as lacunas aparecem **por nome**. Nota sintética de qualidade foi descartada por medição — no vault os sinais que a comporiam estão saturados (placeholders em 0 arquivos, `status` `revisar` em todos, `confianca baixa` em 0 de 92), então a nota seria constante disfarçada de métrica. Mostra-se o que **existe** (cards, âncoras, nível). E matéria com assuntos sem vínculo tem cobertura **desconhecida**, nunca zero.
- **O arcabouço nunca sobrescreve conteúdo**: `build_subject_md.py` pula assunto que já tem `.md` e só regenera com `--forcar`, fazendo backup. O `.md` é onde mora o resumo escrito à mão.
- **Selo de mídia no card só para o que existe**: mostrar os 8 tipos com os ausentes em cinza são 88 ícones numa matéria de 11 assuntos. A grade completa fica na página do assunto, onde "falta gerar" é acionável.
- **Índice de nomes é para wikilink; navegação é calculada**: o índice resolve por basename e nomes repetem entre escopos (`lingua-portuguesa` no comum e em cada cargo). Link de navegação sai sempre da rota da própria página — usar o índice fazia o hub do cargo apontar para a matéria do comum e deixava a própria órfã.
- **Fixture tem de espelhar a saída real da skill anterior**: dois defeitos ficaram verdes por anos porque o fixture inventava o que o gerador não produz — assuntos sob `03-MAPAS-MATERIAS` (a `concurso-aprofunda` usa `03-APROFUNDAMENTO`) e uma chave `notebooklm_url` que o template nunca escrevia. Fixture divergente é teste que se autoconfirma.
- **Cores só via variáveis de tema**: nada de hex fixo para cor de texto no CSS, senão o tema escuro quebra (já aconteceu com `strong`). Toda variável precisa existir nos dois temas — há teste que barra isso.
- **Deploy é sincronização**: o container usa bind mount; atualizar o site é rsync, sem rebuild nem restart. Não introduzir passos de build no deploy.
- **Preservar trabalho do usuário**: re-execuções não apagam resumos, flashcards ou progresso. Scripts que sobrescrevem artefatos do usuário devem fazer backup (ver `fix_notebooklm_packs.py`).

## Ao evoluir uma skill

1. **Plano antes de implementar.** O dono do repo revisa planos e listas de gaps antes de qualquer código. Apresente o plano e espere aprovação.
2. **Testes**: cada skill tem `scripts/tests/test_smoke.py`, que roda standalone (sem pytest). Toda correção de bug ganha um teste que o reproduz.
3. **Versionamento**: SemVer no frontmatter do `SKILL.md` + entrada no `CHANGELOG.md` da skill.
4. **Higiene de pacote** antes de fechar uma versão: sem `__pycache__`, sem arquivos órfãos, sem nomes estranhos. (Já houve incidente de pasta criada por expansão de chaves malsucedida — `mkdir -p a/{b,c}` falha em `sh`; use linhas separadas.)
5. **Degradação graciosa**: dependências são opcionais. Sem `reportlab`, gera-se o `.md` e avisa-se sobre o PDF; sem OCR, PDF-imagem vira pendência. Nunca travar o fluxo inteiro por uma dependência ausente.

## Ao criar uma skill nova

Skills novas para o mesmo propósito (ex.: publicação web, geração de simulados) entram em `skills/<nome>/` seguindo o mesmo padrão: `SKILL.md` com frontmatter (`name`, `version`, `description` com triggers), `scripts/` com utilitários e testes, `assets/templates/`, `examples/`. O `scripts/install.sh` descobre skills automaticamente — não precisa editá-lo.

Reaproveite o que já existe antes de duplicar: `textmatch.py` (normalização/similaridade), `slugify.py` (convenção de nomes), o motor de diff em `diff_editais.py`.

## Contexto do domínio

Vocabulário recorrente: **edital** (o documento que rege o concurso), **banca** (organizadora; ex.: Quadrix, Cebraspe), **retificação** (alteração oficial do edital), **cargo**, **conteúdo programático**, **discursiva**, **concurso previsto** (esperado, sem edital publicado).

O vault de destino segue PARA/Johnny-Decimal, com os concursos em `30_AREAS/CARREIRA/CONCURSOS/`.

## Escopo e limites

- O conteúdo gerado é material de estudo — **não substitui a leitura do edital oficial**. Datas e regras devem ser conferidas na fonte.
- A integração com o NotebookLM é **manual** por decisão de projeto: não há API pública de consumidor, e a via da comunidade (`notebooklm-py`) usa endpoints não-oficiais e pode quebrar. A skill prepara o pacote; o usuário sobe e clica. Se um dia a automação entrar, será **camada opcional** sobre o modo manual, nunca substituindo-o.
