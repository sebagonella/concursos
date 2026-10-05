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

O fluxo tem três etapas encadeadas, mais uma camada opcional:

1. **`concurso-prep`** (Etapa 1) — a partir de um edital (PDF/DOCX/MD), monta a estrutura completa de estudos: cronograma, mapas por matéria, análise da banca, histórico do órgão, materiais (leis baixadas em MD+PDF), sinergias entre concursos. Suporta concurso *previsto* (sem edital ainda) e *reconciliação/retificação* quando o edital sai ou muda.
2. **`concurso-aprofunda`** (Etapa 2) — consome a saída da Etapa 1 + um livro de referência denso. Localiza cada assunto no livro, gera um `.md` por assunto (resumo próprio + ponteiros de página + citações curtas), flashcards nativos e o pacote para gerar podcast/mapa mental/vídeo/report no NotebookLM.
3. **`concurso-publica`** (Etapa 3) — transforma a pasta de um concurso em **site estático** que espelha a organização do vault (`{concurso}/{comum|cargo}/`) e publica **todo** o conteúdo abaixo do concurso: edital, cronograma, mapas de matéria, materiais e leis, histórico, sinergia, discursiva, títulos e o aprofundamento, com mídias embutidas, quiz de flashcards e uma página por assunto para o pacote NotebookLM. Cada matéria abre em duas visões — **Plano** (o mapa do edital) e **Estudo** (os assuntos aprofundados). Decisões travadas: gerador próprio em Python (sem Node), por concurso, uso local/rede doméstica, **site só leitura** (progresso lido do vault na geração; o vault é a única fonte de verdade), link NotebookLM apenas se `notebooklm_url:` preenchida (sem iframe do Google).
4. **`concurso-notebooklm`** (camada opcional sobre a Etapa 2) — **executa** os pacotes que a `concurso-aprofunda` preparou: cria o notebook, sobe as fontes, gera as mídias e salva os arquivos com o nome que a `concurso-publica` detecta. Roda **sob demanda**, por assunto ou por matéria. A biblioteca usada (`notebooklm-py`) **não é oficial** e quebra sem aviso, então a automação é sempre **opcional** e o modo manual segue completo.
5. **`concurso-afere`** (Etapa 5) — a única que **olha para trás**: com a prova real (caderno + gabarito oficial), mede quantas questões o material aprofundado responde, por nível `padrao`/`detalhado`, e aponta o que corrigir. Afere **uma matéria, várias (`--materia`) ou todas as de um cargo (`--cargo`)**; na **Quadrix**, que divide a prova por área, afere **uma área por vez**, com o vínculo questão → matéria julgado pelo agente. O script prepara o determinístico e **o agente julga** — nota inventada por script não vale nada.

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
├── concurso-publica/       # Etapa 3 — concurso → site estático
│   ├── SKILL.md
│   ├── assets/             # site.css, site.js (sem CDN: o site roda offline)
│   ├── scripts/            # site_collector.py, site_builder.py, md2html.py
│   └── examples/           # site-model-exemplo.json (contrato coletor→builder)
├── concurso-notebooklm/    # camada opcional — executa os pacotes no NotebookLM
    ├── SKILL.md
    └── scripts/            # pacote.py (contrato) e plano.py (o que gerar)
└── concurso-afere/        # Etapa 5 — prova real → nota do material
    ├── SKILL.md
    ├── assets/templates/  # afericao-materia.md.tpl
    └── scripts/           # prova_id, gabarito, casar_materias, build/validar_afericao

scripts/install.sh          # instalador único (instala/atualiza todas as skills)
scripts/test-all.sh         # roda as suítes de todas as skills + as de shell
scripts/tests/              # suítes dos scripts de shell (os que mexem no ambiente)
├── test_install.sh         # instalação/desinstalação, incluindo os subagents
└── test_deploy.sh          # deploy com ssh/rsync/docker stubados, sem tocar a rede
deploy/                     # Docker + rsync para servir o site num servidor doméstico
├── docker-compose.yml      # nginx:alpine, bind mount, ${CONCURSOS_PORTA:-8099}, 0.5 CPU / 128 MB
├── nginx.conf              # serve na raiz em concursos.casa:8099
├── deploy.sh               # reconstrói o build do vault e sincroniza via SSH
└── README.md               # instalação, troca de porta e troubleshooting
docs/
├── ARQUITETURA.md          # decisões de projeto e o porquê + diagrama do fluxo
├── SETUP-VAULT.md          # preparar o vault Obsidian
├── fluxo-concurso.mmd      # fonte Mermaid do diagrama (o README renderiza o bloco)
└── fluxo-concurso.png      # export do .mmd, para onde o Mermaid não renderiza;
                            # regerar junto ao editar o .mmd (comando no cabeçalho dele)
```

> O índice navegável de toda a documentação está no [`README.md`](README.md#documentação).
> O contrato de dados entre as etapas — quem escreve cada campo e quem o lê — está em
> [`docs/CONTRATO-DE-DADOS.md`](docs/CONTRATO-DE-DADOS.md); o ciclo de contribuição, em
> [`CONTRIBUTING.md`](CONTRIBUTING.md).

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
./deploy/deploy.sh --concurso-dir <...> --so-este       # nao reconstruir os outros
```

> Após instalar/atualizar, **reinicie a sessão do Claude Code** — ele carrega as skills no início da sessão e pode manter a versão anterior em cache.

## Convenções invioláveis

Estas regras vieram de bugs reais. Quebrá-las volta a quebrar coisas, e o **número
medido** que acompanha cada uma é o que impede a regressão: sem ele a regra vira
opinião, e opinião se "melhora" de volta ao defeito.

As **transversais** estão aqui na íntegra. As que valem para **uma skill só** moram
no `CONVENCOES.md` dela — carregado junto com a skill, quando é relevante, em vez de
em todo turno de toda sessão. O índice abaixo diz onde cada uma está; o título é o
mesmo nos dois lugares, então dá para saltar direto.

### Valem em todo o repositório

- **Slugs em UPPERCASE** para pastas de concurso e cargo: `SEDES_2026`, `EDAS-ADMINISTRACAO`, `_COMUM`. O validador checa isso.

- **Metadata em `.meta.json`** (não YAML). Deve conter o **conteúdo programático integral** (`materias[].topicos`) — o motor de diff depende disso — e o `edital_hash` (SHA-256) para detectar edital alterado.

- **Nunca sobrescrever versão anterior** numa reconciliação. Gera-se `V1-PREVISTO` → `V2-OFICIAL` → `V3-RETIFICADO`, lado a lado, preservando o progresso do usuário.

- **Direitos autorais (Modelo 2)**: a Etapa 2 **não** extrai o texto integral de livros protegidos. Do livro entram apenas localização (páginas) e **trechos curtos citados**. O resumo é sempre original, escrito do zero. Não relaxar isso.

- **Nunca fingir precisão**: localização de assunto com baixa confiança ou não encontrada vira **pendência explícita** para conferência humana. Não inventar página.

- **Fixture tem de espelhar a saída real da skill anterior**: dois defeitos ficaram verdes por anos porque o fixture inventava o que o gerador não produz — assuntos sob `03-MAPAS-MATERIAS` (a `concurso-aprofunda` usa `03-APROFUNDAMENTO`) e uma chave `notebooklm_url` que o template nunca escrevia. Fixture divergente é teste que se autoconfirma.

- **Preservar trabalho do usuário**: re-execuções não apagam resumos, flashcards ou progresso. Scripts que sobrescrevem artefatos do usuário devem fazer backup — e **num lugar só**: quem faz é `notebooklm_pack.py`, que copia para `.bak.md` apenas quando o conteúdo mudou. O wrapper `fix_notebooklm_packs.py` duplicava esse backup incondicionalmente e o resultado era sobrescrito logo depois. **A regra não pega por analogia**: a proteção existia no `build_subject_md.py` desde a 0.6.0 e mesmo assim uma auditoria achou quatro escritas destrutivas em quatro skills — flashcards regerados por cima (pior de todos: o Spaced Repetition ancora o histórico no **texto da frente**, então zerar semanas de revisão não apaga arquivo nenhum e não deixa rastro), aferição já julgada sobrescrita, `--cobertura` escrevendo sem `--aplicar` e ainda truncando o que houvesse abaixo do marcador, e o gêmeo perdedor da consolidação indo para o `unlink()` com até 10% de conteúdo exclusivo. O padrão é sempre o mesmo — **pula o existente, reporta no JSON (não só no stderr), e `--forcar` faz `.md.bak`** —, e quem escreve script novo copia esse padrão, não improvisa outro.

- **O que a automação consome é contrato, não prosa**: `nome_notebook` e `arquivo_*` vivem no frontmatter do pacote. Extrair nome de arquivo por regex de texto corrido foi o que fez o roteiro do mapa mental e o do report chegarem vazios ao site.

### Por skill

**`concurso-aprofunda`** — [skills/concurso-aprofunda/CONVENCOES.md](skills/concurso-aprofunda/CONVENCOES.md)

- Path canônico do aprofundamento
- A fonte fica no nome mesmo quando é única, e o concurso sempre
- Acrescentar fonte é renomear, e a renomeação quebra sete coisas
- A ordem das fontes é significativa e nunca canonicalizada
- Localização é por fonte, em chaves numeradas
- Em norma, o `book_index` é triagem, não localização — e "média" ali é o teto, não um juízo
- Tópico multi-fonte é o desenho do edital, não descuido do mapa
- Flashcards se acrescentam, nunca se regeneram numa mescla
- Slug derivado é sempre ecoado, não só quando suspeito
- Nome de arquivo repete o identificador do aprofundamento
- Mover material no vault reescreve wikilink
- Flashcards do Obsidian
- O arcabouço nunca sobrescreve conteúdo
- Regra de layout mora no gerador, nunca copiada
- O prompt do NotebookLM aponta para a nota do vault, nunca para o livro

**`concurso-publica`** — [skills/concurso-publica/CONVENCOES.md](skills/concurso-publica/CONVENCOES.md)

- O site é derivado, o vault é a fonte
- O site espelha COMUM/cargo
- Progresso é barra, em todo lugar
- Tarefas de estudo é tudo o que há para marcar
- O mapa conta para quem guarda o arquivo
- Matéria com aprofundamento tem aba Estudo, mesmo que o material more no comum
- Documento longo no topo de uma aba esconde o que a aba existe para mostrar
- Asset publicado leva a versão do conteúdo na URL
- Barra ausente, vazia e desconhecida são três coisas
- Tarefa pertence a quem guarda o arquivo; cobertura pertence a quem tem o edital
- Nunca inferir o link mapa↔assunto por slug
- Nada escrito no tópico do mapa se perde em silêncio
- Cobertura é contagem; qualidade não se inventa
- Selo de mídia no card só para o que existe
- Índice de nomes é para wikilink; navegação é calculada
- Cores só via variáveis de tema

**`concurso-afere`** — [skills/concurso-afere/CONVENCOES.md](skills/concurso-afere/CONVENCOES.md)

- Aferir prova é casar VERSÃO e CARGO, ou falhar alto
- Na aferição, `SEM MATERIAL` nunca vira nota baixa
- A conclusão não excede a amostra
- Cobertura de tópico é tautológica quando o vault veio do mesmo edital da prova
- O `detalhado` não é superconjunto do `padrao`
- Na Quadrix, tipo não é prova
- Anulada sai do denominador e entra na amostra

**deploy** — [deploy/README.md](deploy/README.md#por-que-o-deploy-reconstrói-todos-os-concursos-e-não-só-o-que-você-pediu)

- Deploy é sincronização, e por isso reconstrói o build inteiro

## Ao evoluir uma skill

1. **Plano antes de implementar.** O dono do repo revisa planos e listas de gaps antes de qualquer código. Apresente o plano e espere aprovação.
2. **Testes**: cada skill tem `scripts/tests/test_smoke.py`, que roda standalone (sem pytest); os scripts de shell têm suíte própria em `scripts/tests/test_*.sh`, que o `test-all.sh` também roda. Toda correção de bug ganha um teste que o reproduz — e vale conferir que ele **falha** contra o código antigo, senão é só decoração.
3. **Versionamento**: SemVer em **três** lugares, que o CI confere batendo um contra o outro — frontmatter do `SKILL.md`, linha `Versão atual:` do `README.md` da skill e topo do `CHANGELOG.md`. Esquecer o README é fácil justamente porque ele não parece metadado; foi assim que a 0.14.0 quebrou o CI.
4. **Higiene de pacote** antes de fechar uma versão: sem `__pycache__`, sem arquivos órfãos, sem nomes estranhos. (Já houve incidente de pasta criada por expansão de chaves malsucedida — `mkdir -p a/{b,c}` falha em `sh`; use linhas separadas.) Outra da mesma família, e essa apagava: **`printf '%s\n' "${vazio[@]}"` imprime UMA LINHA EM BRANCO**, porque o formato é aplicado uma vez mesmo sem argumento. No `install.sh` isso fazia o `mapfile` devolver um array de comprimento 1 com o elemento `""`, o guarda de `-eq 0` nunca disparava, e o `rm -rf "$CLAUDE_DIR/skills/$s"` virava `rm -rf "$CLAUDE_DIR/skills/"` — o diretório inteiro, com as skills de outros projetos junto. Array vazio em bash se testa com `((${#arr[@]}))` antes de imprimir, e todo laço que compõe path destrutivo defende com `[[ -n "$s" ]] || continue`.
5. **Degradação graciosa**: dependências são opcionais. Sem `reportlab`, gera-se o `.md` e avisa-se sobre o PDF; sem OCR, PDF-imagem vira pendência. Nunca travar o fluxo inteiro por uma dependência ausente.
6. **O CI confere mais do que versão.** Além das suítes, ele barra: skill nova ausente do README/CLAUDE/ARQUITETURA; regra num `CONVENCOES.md` que o índice daqui não lista; link ou **âncora** apontando para o que não existe; o bloco ```mermaid do README divergindo do `.mmd`; o nome da pasta de histórico sem o sufixo `-CONCURSO`; a linha `Versão atual` virando changelog; `__pycache__` commitado; `bash -n` nos shells. A tabela completa está em [CONTRIBUTING.md](CONTRIBUTING.md#o-que-o-ci-confere) — quem edita o README e quebra o mermaid não tem como adivinhar por que reprovou.

## Ao criar uma skill nova

Skills novas para o mesmo propósito (ex.: publicação web, geração de simulados) entram em `skills/<nome>/` seguindo o mesmo padrão: `SKILL.md` com frontmatter (`name`, `version`, `description` com triggers), `scripts/` com utilitários e testes, `assets/templates/`, `examples/`. O `scripts/install.sh` descobre skills automaticamente — não precisa editá-lo.

Reaproveite o que já existe antes de duplicar: `textmatch.py` (normalização/similaridade), `slugify.py` (convenção de nomes), o motor de diff em `diff_editais.py`.

## Contexto do domínio

Vocabulário recorrente: **edital** (o documento que rege o concurso), **banca** (organizadora; ex.: Quadrix, Cebraspe), **retificação** (alteração oficial do edital), **cargo**, **conteúdo programático**, **discursiva**, **concurso previsto** (esperado, sem edital publicado).

O vault de destino segue PARA/Johnny-Decimal, com os concursos em `30_AREAS/CARREIRA/CONCURSOS/`.

## Escopo e limites

- O conteúdo gerado é material de estudo — **não substitui a leitura do edital oficial**. Datas e regras devem ser conferidas na fonte.
- A integração com o NotebookLM tem **dois modos, e o manual é o garantido**: não há API pública de consumidor, e a via da comunidade (`notebooklm-py`) usa endpoints não-oficiais que quebram sem aviso. A `concurso-aprofunda` prepara o pacote e o usuário sobe e clica; a `concurso-notebooklm` executa o mesmo pacote automaticamente, como **camada opcional** — nunca em substituição. Sem a biblioteca, a skill degrada e o pacote continua completo.
