# INVENTORY — levantamento factual da parte web do `14_concursos` (2026-09-22)

> Levantamento em 2026-09-21/22, sobre o estado de `main` em `4e5b754`
> (`concurso-publica` 0.25.0). **Relato, não proposta.** Tudo que foi inferido e
> não confirmado no código leva ⚠️. Nada aqui é decisão.
>
> Concursos publicados são citados pela sigla da pasta (`SEDES_2026`,
> `BB_2027_PREVISTO`); pastas de cargo aparecem como `{cargo}`.

---

## 1. FRONTEIRA WEB vs NÃO-WEB

### 1.1 O que é "web"

| Componente | Arquivos | Linhas | Papel |
|---|---|---|---|
| Gerador — coletor | `skills/concurso-publica/scripts/site_collector.py` | 1.769 | varre a pasta do concurso no vault e monta o **modelo** (`site-model.json`) |
| Gerador — builder | `skills/concurso-publica/scripts/site_builder.py` | 2.374 | consome o modelo, decide rotas, renderiza HTML, copia mídia/anexos, escreve manifesto |
| Gerador — Markdown | `skills/concurso-publica/scripts/md2html.py` | 437 | conversor MD→HTML próprio (sem dependência) |
| Gerador — convenção | `skills/concurso-publica/scripts/aprofundamento_id.py` | 437 | **cópia sincronizada** do mesmo arquivo da `concurso-aprofunda` (teste barra divergência: `test_smoke.py:3416`) |
| Assets do site | `skills/concurso-publica/assets/site.css` (811) · `site.js` (316) | 1.127 | copiados para `out/site/assets/` em `site_builder.py:2256-2261` |
| Templates | **não há arquivos de template** — o HTML é f-string dentro de `site_builder.py` (esqueleto em `pagina()`, `site_builder.py:260-300`) | — | |
| Contrato/exemplo | `skills/concurso-publica/examples/site-model-exemplo.json` | — | gerado do fixture, exercitado por `test_smoke.py:1614` |
| Saída | `out/site/` (gitignored por `out*/`, `.gitignore`) | — | 389 páginas, 502 arquivos, 1,0 GB hoje (ver §5, §3.3) |
| Deploy | `deploy/docker-compose.yml` (97) · `deploy/nginx.conf` (104) · `deploy/deploy.sh` (424) · `deploy/README.md` (232) · `deploy/deploy.env` (4, gitignored) | 625 (sem README) | nginx:alpine em bind mount, rsync sobre SSH |
| Suíte | `skills/concurso-publica/scripts/tests/test_smoke.py` (3.547) + `fixture_concurso.py` (274) · `scripts/tests/test_deploy.sh` (361) | 4.182 | ver §8 |
| Doc da skill | `skills/concurso-publica/SKILL.md` (238) · `CONVENCOES.md` (46) · `README.md` · `CHANGELOG.md` | — | |

Total de **código** web (py+js+css, sem testes): **6.144 linhas**; deploy: 625; testes web: 4.182.

### 1.2 O que NÃO é web

- `skills/concurso-prep/` (4.967 linhas de código, 2.184 de teste) — edital → estrutura no vault, escreve `.meta.json`.
- `skills/concurso-aprofunda/` (4.237 / 2.266) — livro → `.md` por assunto, flashcards, `_fonte-notebooklm.md`.
- `skills/concurso-notebooklm/` (1.377 / 848) — executa os pacotes; grava mídias e `notebooklm_url` no vault.
- `skills/concurso-afere/` (1.410 / 681) — prova real → `00-AFERICAO-*.md` no vault.
- `scripts/install.sh`, `scripts/test-all.sh`, `scripts/tests/test_install.sh` (instalação das skills no Claude Code; nada de web).
- `out/backup/`, `out/REVISAO-VINCULOS.md`, `out/vinculos-*.preenchido.json` — saídas da `concurso-aprofunda` (backfill de vínculos), não do site. Coabitam `out/` por acaso.
- `site-model-SEDES_2026.json` na raiz do repo (15 KB, 2026-07-28, gitignored por `/site-model-*.json`) — coleta antiga solta; nada a lê.

### 1.3 Fluxo de dados ponta a ponta

```
vault (Obsidian)                                     [pessoa edita no Obsidian]
  ├─ .meta.json                    ← concurso-prep (agente grava; SKILL.md:408)
  ├─ {ESCOPO}/0N-*/…*.md, *.pdf     ← concurso-prep
  ├─ {ESCOPO}/03-MAPAS-*/{materia}.md ← concurso-prep
  ├─ {ESCOPO}/03-APROFUNDAMENTO/{materia}/assuntos/{assunto}/{nivel}--{fontes}/
  │     {assunto}--…--{CONCURSO}.md, flashcards-*.md/.csv, cards.json,
  │     _fonte-notebooklm.md        ← concurso-aprofunda
  │     podcast-*.m4a, video-*.mp4, mapa-mental-*.png, report-*.md …
  │                                 ← concurso-notebooklm OU a pessoa, à mão
  └─ {materia}/00-AFERICAO-*.md     ← concurso-afere
          │
          │  BUILD (na máquina do vault) — deploy.sh:313 chama:
          ▼
site_builder.py --concurso-dir <pasta>  ──►  coletar_concurso()  (site_collector.py:1664)
          │                                      = modelo em memória (ou --out site-model.json)
          ▼
montar_rotas() (site_builder.py:2109)  →  plano de páginas + índice de wikilinks
construir()   (site_builder.py:2231)   →  out/site/{concurso}/**/index.html
                                          out/site/{concurso}/…/media/<ident>/<mídia>   (cópia, :614-617)
                                          out/site/{concurso}/{escopo}/{secao}/arquivos/… (cópia, :2092)
                                          out/site/{concurso}/.concurso.json (manifesto, :2318-2331)
                                          out/site/index.html  (raiz, relida dos manifestos, :2333-2338)
                                          out/site/assets/site.css|site.js
          │
          │  DEPLOY — deploy.sh:346,397
          ▼
rsync -az --delete --chmod=D755,F644  out/site/  →  ssh {user}@{host}:{CONCURSOS_DIR}/site/
          │
          │  RUNTIME — nginx:alpine, bind mount ./site:/srv/site:ro (compose:29)
          ▼
http://{host}:8099/  →  navegador  →  site.js (quiz, abas, tema, copiar, lightbox)
```

**Momento de cada coisa:**

| Etapa | Quando roda | Onde | Lê o vault? |
|---|---|---|---|
| Coleta + build | sob demanda (`deploy.sh` ou `site_builder.py` à mão) | máquina do vault | **sim** (única leitura) |
| rsync | logo após o build, no mesmo `deploy.sh` | máquina do vault → servidor | não |
| nginx | contínuo | servidor | não — só `/srv/site` |
| `site.js` | no navegador | cliente | não |

**O site NÃO lê o vault em runtime.** Tudo é resolvido no build: progresso
(`contar_progresso`, `site_collector.py:275-279`), mídia (`detectar_midias`, `:432-466`),
flashcards (parseados para JSON e embutidos em `<script type="application/json">`,
`site_builder.py:532-563`), anexos e mídias copiados para dentro de `out/site`
(`copiar_anexos` `:2092-2106`; closure `copiar` `:614-617`). O docstring de `copiar_anexos`
é explícito: "nada que esteja fora dessa pasta é alcançável pelo navegador".

### 1.4 Se a web fosse removida, o que quebra nas skills?

- **Nada nas quatro skills** depende de `concurso-publica` em runtime: nenhuma importa
  `site_collector`/`site_builder` (`grep -rn "site_collector\|site_builder" skills/` só
  acha a própria publica, o deploy e a documentação).
- Acoplamentos **de contrato**, não de código:
  - `aprofundamento_id.py` existe em duas cópias; a fonte é a da `concurso-aprofunda`
    (`CONVENCOES.md` da aprofunda; teste `test_smoke.py:3416`). Remover a publica remove a cópia, não a fonte.
  - `concurso-notebooklm` nomeia as mídias "com o nome que a `concurso-publica` detecta"
    (`CLAUDE.md`, item 4) — o catálogo de nomes é `CATALOGO_MIDIAS`, `site_collector.py:298-307`.
    O nome continua válido sem o site; só ninguém o consome.
  - `docs/CONTRATO-DE-DADOS.md` §5 documenta o `site-model.json` como contrato público.
- **Caminho inverso (site → vault): não existe.** `SKILL.md` "Fora de escopo: Backend,
  login, sincronização site→vault". Teste `test_build_nao_escreve_no_vault`
  (`test_smoke.py:458`). O JS declara "Sem dependências, sem armazenamento" (`site.js:1-3`).
  Único estado gravado no cliente é o tema (§3.5).

---

## 2. STACK

| | Web (gerador + site + deploy) | Skills (prep, aprofunda, notebooklm, afere) |
|---|---|---|
| Linguagem | Python 3 (stdlib apenas: `argparse, json, re, hashlib, html, shutil, unicodedata, pathlib, datetime`) — usa `str \| None` (≥3.10). Local: 3.12.3; CI: 3.11 (`tests.yml:16`) | Python 3 stdlib; opcionais: `reportlab` (PDF), `pyyaml` (legado `.meta.yml`), `poppler-utils` (CI), `notebooklm-py` (não-oficial) |
| HTML/CSS/JS | **puros**. Sem framework, sem bundler, sem npm, sem CDN, sem webfont (`SKILL.md` "Tipografia por stack de sistema"). `grep` por `https?://|@import|@font-face|fetch(` em `site.js`/`site.css`: zero. JS em IIFE ES5 (`var`, `function`) | — |
| Bibliotecas embutidas | nenhuma. `requirements.txt` da skill: só `pytest>=8.0` opcional para rodar a suíte | — |
| Markdown | `md2html.py` próprio ("não pretende ser CommerMark": headings, negrito/itálico, código inline, listas aninhadas, checkboxes, blockquote, tabelas, links, wikilinks com âncora/pipe, block-ids `^id`, autolink) | — |
| Build tool | nenhum; `python3 site_builder.py --out out/site` | — |
| Servidor | `nginx:alpine` (**sem tag de versão fixa**, `docker-compose.yml:15`), 1 worker, 256 conexões, `sendfile`, gzip só em texto, `access_log off` | — |
| Container | `deploy.resources.limits`: **0.50 CPU / 128 MB** (reserva 0.05 / 32 MB) + `cpus/mem_limit` de fallback (`:44-54`); `read_only`, `cap_drop: ALL` + 4 caps, `no-new-privileges`, tmpfs em `/var/cache/nginx`, `/var/run`, `/tmp`; healthcheck `wget --spider http://127.0.0.1/healthz` a cada 30 s; log json-file 5 m × 3 | — |
| Shell | `deploy/deploy.sh` (bash, `set -euo pipefail`, shellcheck no CI) | `scripts/install.sh`, `test-all.sh` |
| Transporte | `rsync` sobre `ssh`; `scp` no `--setup` | — |
| Docker Compose | v2 (`docker compose`) | — |

**Manifests relevantes (colados):**

`docker-compose.yml` (essência, `:14-30, 42-54, 61-69, 80-97`):
```yaml
services:
  concursos:
    image: nginx:alpine
    container_name: concursos-site
    restart: unless-stopped
    ports: ["${CONCURSOS_PORTA:-8099}:80"]
    volumes:
      - ./site:/srv/site:ro
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    deploy: { resources: { limits: { cpus: "0.50", memory: 128M }, reservations: { cpus: "0.05", memory: 32M } } }
    cpus: 0.50 ; mem_limit: 128m ; mem_reservation: 32m
    healthcheck: { test: ["CMD","wget","-q","--spider","http://127.0.0.1/healthz"], interval: 30s, timeout: 3s, retries: 3 }
    security_opt: [no-new-privileges:true]
    read_only: true
    cap_drop: [ALL] ; cap_add: [CHOWN, SETGID, SETUID, NET_BIND_SERVICE]
    tmpfs: [/var/cache/nginx, /var/run, /tmp]
    logging: { driver: json-file, options: { max-size: 5m, max-file: "3" } }
```

`nginx.conf` (essência, `:11-101`):
```nginx
worker_processes 1;  events { worker_connections 256; }
http {
  include mime.types; types { text/markdown md; }
  sendfile on; tcp_nopush on; keepalive_timeout 30;
  access_log off; error_log /var/log/nginx/error.log warn;
  gzip on; gzip_types text/plain text/css application/javascript application/json text/markdown; gzip_min_length 1024;
  server {
    listen 80; server_name concursos.casa _;
    root /srv/site; index index.html;
    absolute_redirect off; port_in_redirect off;
    location = /healthz { return 200 'ok'; }
    add_header X-Content-Type-Options nosniff always; X-Frame-Options SAMEORIGIN; Referrer-Policy no-referrer;
    location = /concursos { return 301 /; }
    location ^~ /concursos/ { rewrite ^/concursos/(.*)$ /$1 permanent; }
    location ~* \.html$ { expires -1; (+ os 3 headers repetidos) }
    location / { try_files $uri $uri/ $uri/index.html =404; expires 1h; }
  }
}
```
Sem TLS (só `listen 80`), sem `auth_basic`, sem `location ~ /\.` (dotfiles são servidos — ver §6).

`deploy/deploy.env` (só nomes; valores omitidos): `CONCURSOS_HOST`, `CONCURSOS_USER`,
`CONCURSOS_DIR`, `CONCURSOS_PORTA`. Padrões no script (`deploy.sh:70-74`): host
`concursos.casa`, dir `/opt/concursos`, porta `8099`, `BUILD_DIR=out/site`. No `.env`
local o host é um **IP** e o dir **não** é o padrão; a porta é 8099.

---

## 3. MODELO DE DADOS

### 3.1 `.meta.json` (raiz da pasta do concurso)

Escrito pelo **agente** da `concurso-prep` (passo 10.4, `skills/concurso-prep/SKILL.md:408-420`),
não por script — e por isso **os dois `.meta.json` do vault têm shapes diferentes**
(reconhecido em `validate_parsed.py:5-8` e `concurso-prep/SKILL.md:140`). Tabela canônica
em `docs/CONTRATO-DE-DADOS.md` §1. O que a **web** lê é uma allowlist
(`site_collector.py:1712-1719`):

```python
("orgao", "ano", "banca", "modo", "datas_chave", "estrutura_prova",
 "vagas_ac", "vagas_total", "salario", "cargos_validados")
```

| Campo | Tipo | Escreve | Lê (web) | Onde |
|---|---|---|---|---|
| `orgao`, `orgao_sigla`, `ano`, `banca`, `modo` | str/int/str/str (`oficial`\|`previsto`) | prep | capa e manifesto | `site_builder.py:1937-1945, 2318-2331` |
| `datas_chave.prova_data` | `YYYY-MM-DD` ou objeto `null` (previsto) | prep | capa ("faltam N dias"), índice raiz, ordenação | `:1943-1950, 2030-2037, 2059` |
| `estrutura_prova.objetiva.total_questoes` | int | prep | capa ("Questões") | `:1974-1976` |
| `vagas_ac`, `vagas_total`, `salario` | raiz (concurso de cargo único) | prep | capa | `:1958-1960` |
| `cargos_validados[].{sigla, vagas_total, salario, nome_completo, codigo}` | lista de obj | prep | capa "por cargo" | `:1962-1972` |
| `materias[].{nome, materia_id, tipo, subitem_edital, topicos[], cargos_ids[]}` | conteúdo programático integral | prep | **não lida pela web** (motor de diff da prep) | — |
| `edital_hash`, `edital_pdf_sha256` | SHA-256 | prep | não | — |
| `estrutura_prova_por_cargo`, `materias_por_cargo`, `cargos_multi`, `downloads`, `estudo`, `cargo` (SEDES) / `vagas_proxy`, `remuneracao_proxy`, `edital_proxy_*`, `cargos_gerados`, `leis_citadas`, `pasta`, `versao` (BB) | variam entre os dois arquivos | prep | não | — |

Exemplo fictício, só com o que a web consome:
```json
{ "orgao": "Órgão Exemplo", "orgao_sigla": "OEX", "ano": 2026, "banca": "Banca X", "modo": "oficial",
  "datas_chave": { "prova_data": "2026-09-06" },
  "estrutura_prova": { "objetiva": { "presente": true, "total_questoes": 60 },
                       "discursiva": { "presente": true, "tipo": "dissertativa" }, "titulos": { "presente": false } },
  "cargos_validados": [ { "sigla": "CARGO-A", "vagas_total": 10, "salario": 4000.0 } ] }
```

### 3.2 `site-model.json` (coletor → builder)

Gerado por `coletar_concurso()` (`site_collector.py:1664-1740`); salvo só com `--out`.
Chaves de topo: `concurso`, `dir` (path absoluto do vault), `meta` (allowlist), `escopos[]`,
`cargos[]` (**alias** de `escopos`, `:1725`), `descartados_placeholder[]`, `resumo{n_escopos,
n_cargos, n_materias, n_assuntos, n_documentos, n_anexos}`.

**Escopo** (`coletar_escopo`, `:1361-1431`): `tipo` (`comum`|`cargo`|`geral`), `nome` (pasta),
`slug`, `secoes[]`, `materias[]`, `n_materias`, `n_assuntos`, `progresso` (só matérias),
`progresso_documentos`, `progresso_status` (do `99-Status.md`), `progresso_tarefas` (soma dos três,
`:1434-1456`), `cobertura{n_topicos, n_cobertos, pct|null, n_materias, n_com_mapa, n_sem_vinculo}`
(`:105-138`). Após `herdar_secoes_comuns` (`:1462`) o cargo ganha uma seção `materiais` ponteiro com
`documentos: []`; após `cruzar_materias_comuns` (`:1518`) a matéria ganha `aprofundamento_em` /
`mapa_em` / `assuntos_herdados`.

**Seção** (`coletar_secao`, `:1084-1128`): `ordinal`, `rotulo`, `slug`, `registro` (`estudo`|`consulta`),
`modo`, `dir`, `documentos[]{arquivo, caminho, slug, titulo, resumo, progresso, n_secoes}`,
`anexos[]{arquivo, caminho, extensao, bytes, subpasta}`, `n_documentos`, `n_anexos`, `bytes_anexos`.

**Matéria** (`coletar_materia`, `:875-961`): `nome`, `materia_id`, `slug`, `dir`, `doc_banca`,
`docs_afericao[]`, `docs_apoio[]`, `mapa_localizacao`, `aliases_mapa{}`, `assuntos[]`, `progresso`,
`n_assuntos`, `n_com_podcast`, `n_com_flashcards`, `por_prioridade{alta,media,base}`, e depois
`mapa` (ou `null`) e `cobertura{n_topicos, n_cobertos, pct, topicos_sem[], n_detalhado, n_com_midia}`
ou `{vinculo_ausente: true, n_assuntos}` (`:62-102`).

**Assunto** (`coletar_assunto`, `:773-868`): `slug`, `titulo`, `prioridade`, `paginas_livro`,
`n_aprofundamentos`, `niveis[]`, `fontes[]` (nomes legíveis), `n_fontes`, `tem_proprio`,
`aprofundamentos[]`, `materia_id`, `topico_id[]`, `topico[]`, `midias{podcast, video, slides,
mapa_mental, infografico, report, teste, tabela}` (nome de arquivo ou `null`, união dos
aprofundamentos), `flashcards{obsidian, anki, n_cards}`, `sinais{n_cards, tem_ancoras, palavras}`,
`progresso` (união), `resumo_md` (path absoluto), `notebooklm_url`.

**Aprofundamento** (`coletar_aprofundamento`, `:469-572`): `slug`, `slug_assunto`, `aprofundamento`
(id = nome da pasta), `nivel`, `n_fontes_id`, `fontes_id[]`, `fontes` (str), `fontes_notebook[]`,
`fontes_notebook_declarado`, `titulo`, `prioridade`, `materia_id`, `topico_id[]`, `topico[]`, `status`,
`paginas_livro`, `localizacoes[]{fonte, texto}`, `resumo_md`, `midias{}`, `flashcards{}`,
`notebooklm_url`, `progresso{total, feitos}`, `tem_ancoras`, `palavras`, `tem_pack_notebooklm`,
`pack_notebooklm{caminho, status, url, nome_notebook, fontes[], prompts[]{chave, icone, rotulo,
titulo_secao, prompt, roteiro[], arquivo_saida}, perguntas[], checklist[]{feito, texto}, progresso}`
(`:583-645`), `legado` (só no layout plano).

**Mapa** (`coletar_mapa`, `:1268-1332`): `arquivo`, `caminho`, `materia_id`, `titulo`, `auxiliares[]`,
`n_topicos`, `progresso`, `rotulos_extras[]`, `topicos[]{numero, titulo, slug, prioridade,
subtopicos[]{texto, feito, subgrupo, grupo}, blocos[]{chave, rotulo, sufixo, markdown, itens[],
n_itens}, progresso}`. `chave` ∈ `topicos_edital|subtopicos|material|pegadinhas|meta|extra`
(`H3_MAPA`, `:1130-1136`).

⚠️ O `examples/site-model-exemplo.json` (último commit 2026-08-03) **não contém** `fontes_notebook`,
`fontes_notebook_declarado`, `tem_proprio`, `docs_afericao`, `descartados_placeholder`,
`assuntos_herdados`, `aprofundamento_em`, `mapa_em` — todos gravados pelo coletor de 2026-08-12.
O teste `test_exemplo_do_modelo_constroi_de_verdade` só exige um subconjunto. O exemplo está
**defasado em relação ao código**, sem quebrar o teste.

**Quem lê cada campo**: só `site_builder.py`. Campos que carregam **path absoluto da máquina do
vault** (`dir`, `caminho`, `resumo_md`, `mapa.caminho`, `pack_notebooklm.caminho`) são usados pelo
builder para copiar/ler; o único que **vai para o site publicado** é `dir`, gravado como `origem` no
`.concurso.json` (`site_builder.py:2321`).

### 3.3 Estrutura de pastas que o gerador espera (e o que "detecta")

Raiz do concurso = `{vault}/30_AREAS/CARREIRA/CONCURSOS/{SIGLA}_{ANO}[_PREVISTO|_V2-OFICIAL…]`
(`concurso-prep/SKILL.md:513-560`). Dentro dela, o coletor:

1. **Escopos** = toda subpasta que não começa com `.` (`achar_escopos`, `:1576-1586`).
   `_COMUM`/`COMUM` → `tipo: comum`; qualquer outra → `cargo` (`:1418`). Matéria solta na raiz →
   escopo implícito `_GERAL` (`:1685-1702`). Ordem: comum primeiro, depois alfabético (`:1705`).
2. **Seções numeradas** por tabela literal `SECOES` (`:966-983`), casadas em UPPERCASE:

   | Pasta do vault | Seção do site | Registro | Modo |
   |---|---|---|---|
   | `01-EDITAL` | `edital` | consulta | documentos |
   | `02-CRONOGRAMA` | `cronograma` | estudo | documentos |
   | `03-MAPAS-MATERIAS` / `03-MAPAS-COMUNS` | `mapas` | estudo | mapas (aba Plano) |
   | `03-APROFUNDAMENTO` | `aprofundamento` | estudo | materias (aba Estudo) |
   | `04-MATERIAIS` | `materiais` | consulta | documentos (herdada pelo cargo, `SECOES_HERDAVEIS`, `:1459`) |
   | `05-HISTORICO-CONCURSO` | `historico` | consulta | documentos |
   | `06-SINERGIA` | `sinergia` | consulta | documentos |
   | `07-DISCURSIVA` | `discursiva` | estudo | documentos |
   | `08-TITULOS` (pasta ou `.md`) | `titulos` | estudo | documentos |

   Dentro de uma seção, **recursivamente** (`rglob`, `:1094`): `.md` → documento; qualquer outro
   arquivo → anexo com `bytes`; ignorados: dotfiles e `IGNORAR_EXT = {.bak,.tmp,.swp,.orig,.rej}` (`:964`).
3. **Não publicados**: `00-INDICE*`, `99-Status*` (`DOCS_NAO_PUBLICAVEIS`, `:985`) — o status é
   **lido** para progresso (`progresso_do_status`, `:1353`). Documento com placeholder de template
   `{MAIUSCULAS}` é descartado e listado (`PLACEHOLDER_RE`, `:989`; aviso `:1011`).
4. **Matérias aprofundadas** = qualquer pasta com `assuntos/` contendo subpastas (`achar_materias`,
   `:1592-1600`, via `rglob("assuntos")`). Nome legível do `00-INDICE*.md` (`materia:` ou `title:`),
   senão title-case do slug (`:893-901`).
5. **Assunto** = subpasta de `assuntos/`. Três layouts aceitos (`:773-786`):
   `assuntos/{a}/{nivel}--{fonte1}[+{fonte2}]/` (atual; reconhecido por `eh_pasta_aprofundamento`),
   `assuntos/{a}/aprofundamentos/{id}/` (0.2.x), `assuntos/{a}/{a}.md` (legado plano → `legado: true`).
6. **Arquivo principal** do aprofundamento: `arquivo_principal()` de `aprofundamento_id.py`; nome
   completo `{assunto}--{nivel}--{fontes}--{CONCURSO}.md`.
7. **Mídias** por presença de arquivo, `detectar_midias` (`:432-466`): tenta `{prefixo}-{slug}{ext}`,
   depois `{prefixo}-*` com extensão aceita (exclui `flashcards-*`). Catálogo `CATALOGO_MIDIAS` (`:298-307`):

   | chave | prefixos | extensões |
   |---|---|---|
   | `podcast` | `podcast`, `audio`, `resumo-audio` | `.m4a .mp3 .wav .ogg` |
   | `video` | `video`, `resumo-video` | `.mp4 .webm .mov` |
   | `slides` | `slides`, `apresentacao` | `.pdf .pptx` |
   | `mapa_mental` | `mapa-mental`, `mapa` | `.png .jpg .jpeg .svg .webp` |
   | `infografico` | `infografico`, `infografia` | imagens + `.pdf` |
   | `report` | `report`, `relatorio` | `.md .pdf .txt` |
   | `teste` | `teste`, `quiz` | `.md .pdf .txt` |
   | `tabela` | `tabela`, `tabela-dados`, `dados` | `.csv .md .tsv` |
8. **Flashcards**: `flashcards-{slug}.md` / `.csv`; senão o primeiro `flashcards-*.md|csv` (`:480-494`).
9. **Pacote NotebookLM**: `_fonte-notebooklm.md` no diretório do aprofundamento (`:583-645`);
   `notebooklm_url:` no frontmatter dele liga o botão (`_url_do_pack`, `:722`).
10. **Docs de apoio da matéria** (`.md` na pasta da matéria): `00-COBERTURA*`, `00-GUIA*`, `00-INDICE*`,
    `COMO-USAR*` (`:871-872`); "como a banca cobra" por `DOC_BANCA` (`:373-376`); aferições
    `00-AFERICAO*` ordenadas por `data:` e `rodada:` desc (`:390-423`); `mapa-aliases.json` opcional (`:927-936`).
11. **Mapa de matéria**: `.md` em `03-MAPAS-MATERIAS`/`03-MAPAS-COMUNS` (`achar_mapas`, `:1335-1350`);
    casa com a matéria por `materia_id` do frontmatter, senão por slug de arquivo (`:1395`).

Árvore real do `SEDES_2026` (2 níveis): `00-INDICE.md`, `.meta.json`, `_COMUM/{01-EDITAL,
03-APROFUNDAMENTO, 03-MAPAS-COMUNS, 04-MATERIAIS, 05-HISTORICO-CONCURSO, 06-SINERGIA}`, e três
`{cargo}/{02-CRONOGRAMA, 03-MAPAS-MATERIAS, 04-MATERIAIS, 07-DISCURSIVA, 99-Status.md}` — um deles
também com `03-APROFUNDAMENTO` e `08-TITULOS.md`.

### 3.4 Mídias

- **Tipos e onde ficam no vault**: ao lado do `.md` do aprofundamento (§3.3 item 7). Anexos de seção
  (PDF de leis, editais, provas) em `04-MATERIAIS/leis-baixadas/`, `01-EDITAL/`,
  `05-HISTORICO-CONCURSO/{editais,provas}-anteriores/`, `06-SINERGIA/provas-baixadas/`.
- **Como entram no site**: **copiadas** (`shutil.copy2`) para `out/site/{c}/{escopo}/materias/{m}/{a}/media/{ident}/`
  (`site_builder.py:614-617`) e `out/site/{c}/{escopo}/{secao}/arquivos/{subpasta}/` (`rota_anexo` `:198`, `copiar_anexos` `:2092`).
  Nunca linkadas ao vault. Referência no HTML: `<audio controls preload="none" src=…>` (`:630-632`),
  `<video controls preload="none">` (`:634-636`), `<img loading="lazy">` (`:638-640`), report `.md` é
  **convertido e inserido no corpo** (`:684-689`), PDF/slides/infográfico PDF viram botão "Abrir"
  (`:642-654`). Cada mídia ganha link `⤓ Baixar` (`:619-622`). Anexos listam o tamanho (`tamanho_legivel`, `:1698`).
- **Tamanho** (`du`, build de 2026-08-06):

  | | `sedes_2026` | `bb_2027_previsto` | assets | total |
  |---|---|---|---|---|
  | páginas (`index.html`) | 242 | 146 | — | 389 (+1 raiz) |
  | arquivos | 302 | 197 | 2 | 502 |
  | tamanho | 487 MB | 527 MB | 52 KB | **1,0 GB** |

  Por tipo: **17 `.m4a` = 874 MB** (86%); 2 `.mp4` = 69 MB; 86 `.pdf` = 52 MB; 389 `.html` = 8 MB;
  2 `.png` = 4 MB. **10 arquivos > 50 MB, todos podcasts (máx. 68,1 MB); nenhum > 100 MB.**
  Vault: `SEDES_2026` 488 MB, `BB_2027_PREVISTO` 531 MB — o site copia praticamente tudo.
- O build **recopia toda a mídia** a cada execução (`rmtree` da pasta do concurso, `:2251-2253`);
  o rsync continua incremental porque `copy2` preserva mtime (comentário `:2242-2249`).

### 3.5 Flashcards → quiz

- **Formato no vault**: plugin Obsidian *Spaced Repetition* — tag `#flashcards`, cartão multiline
  `pergunta` / `??` / `resposta` (gerado por `concurso-aprofunda/scripts/flashcards_gen.py:86-100`);
  singleline `pergunta::resposta` também aceito. Origem: `cards.json` (front/back/tag) escrito pelo
  agente da aprofunda → `flashcards_gen.py` → `.md` + `.csv` (Anki). No vault: **177 arquivos
  `flashcards-*.md`**, todos multiline; **0 com marcação `<!--SR:…-->`** (nenhuma revisão espaçada
  registrada até hoje).
- **Como vira quiz**: `parsear_flashcards()` (`site_builder.py:467-499`) → lista `[{f, v}]` →
  `bloco_quiz()` (`:532-563`) embute JSON em `<script type="application/json">` com `</` escapado →
  `iniciarQuiz()` (`site.js:9-84`) lê, mostra `frente`/`verso`, botões **Virar / Próximo /
  Embaralhar**, teclado (espaço/Enter vira, → avança), `aria-live`. **Sem correção, sem pontuação,
  sem repetição espaçada, sem persistência**: a dica na página diz "Para revisão espaçada com
  agendamento, use o baralho no Obsidian" (`:556-557`). Contagem no build atual (coleta de
  2026-09-22): 1.424 cards no SEDES, 964 no BB.
- Só o `.md` alimenta o quiz; `cards.json` e `.csv` não são lidos pela web (o `.csv` só entra no
  índice de wikilinks, `site_builder.py:2193-2197`).

### 3.6 Progresso

- **Onde é registrado**: checkboxes `- [ ]`/`- [x]` nos `.md` do vault, marcados pela pessoa no
  Obsidian. Contados por `contar_progresso` (`site_collector.py:275-279`) em três parcelas
  (`atualizar_progresso`, `:1434-1456`): matérias (assuntos = união dos aprofundamentos `:848`, +
  itens do plano do mapa quando o mapa é próprio `:150-169`), documentos de seção, `99-Status.md`.
  Cobertura (`:62-138`) é outra medida: tópicos do edital com ≥1 assunto via `topico_id` gravado.
- **Números reais** (coleta 2026-09-22): SEDES 3/1.351 tarefas (0,22 %); BB 1/1.371 (0,07 %).
  No vault inteiro: 3.820 checkboxes, 8 marcados. Há tarefa aberta no vault sobre "progresso em
  0,15 %" (nota de sessão 2026-08-16: "não é defeito", decisão pendente).
- **O site grava algo?** Só o **tema** claro/escuro em `localStorage["concursos:tema"]`
  (`site.js:107-137`; leitura inline antes da pintura em `site_builder.py:276-278`). `grep` por
  `sessionStorage|cookie|<form|<input|fetch(|XMLHttpRequest|service worker` nos assets e no builder:
  **zero**. Comentário do JS (`:262-266`): "Nada é persistido — é preferência de leitura, e o progresso
  mora no vault". Estado do `<details>` do plano e da aba ativa **não** persiste entre páginas.

---

## 4. REGRAS DE NEGÓCIO NA WEB

Legenda de "Onde vive": **C** = `site_collector.py` (Python, build) · **B** = `site_builder.py`
(Python, build) · **JS** = `assets/site.js` (navegador) · **CSS** = `assets/site.css` ·
**N** = `deploy/nginx.conf` · **D** = `deploy/deploy.sh`. "Confirmada" = lida no código nesta sessão.

| # | Regra (comportamento observável) | Onde vive | Confirmada? |
|---|---|---|---|
| **Navegação e índice** | | | |
| 1 | Índice raiz lista todos os concursos publicados, lidos dos manifestos `*/.concurso.json` de `out/site`; publicar um concurso não apaga os outros do índice | B `ler_manifestos` :2080-2089, `pagina_raiz` :2020-2077 | sim |
| 2 | Índice raiz agrupa por órgão (`orgao` do manifesto, senão prefixo do slug antes de `_`/`-`), órgãos em ordem alfabética, dentro do órgão por `prova_data` (sem data vai ao fim: `"9999"`) | B :2051-2065 | sim |
| 3 | Card de concurso mostra banca, data da prova + "faltam N dias" ou "realizada", e tag `previsto`/`retificado` derivada do **nome da pasta** | B :2027-2046 | sim |
| 4 | Capa do concurso: ficha (banca, prova, vagas, salário — raiz ou "por cargo" via `cargos_validados`, questões) + **um card por escopo**, comum com tag | B `pagina_capa` :1937-2014 | sim |
| 5 | Hub do escopo: matérias primeiro (focal), depois seções de registro `estudo`, por último `consulta` ("registro visivelmente mais quieto") | B `pagina_escopo` :1747-1827 | sim |
| 6 | Seção com **um documento e sem anexo colapsa**: a rota da seção É a do documento (sem página de índice de um item) | B `montar_rotas` :2143-2156 | sim |
| 7 | Cargo herda a seção `materiais` do `_COMUM` como ponteiro (`documentos: []`), para a bibliografia ter caminho de navegação em todo galho | C `herdar_secoes_comuns` :1459-1515; B `bloco_herdado` :1830 | sim |
| 8 | Matéria com mapa no cargo e aprofundamento no comum (ou vice-versa) é cruzada por `materia_id` (senão slug): ganha `mapa_em`/`aprofundamento_em` e cards que abrem no outro escopo; **nada é copiado** | C `cruzar_materias_comuns` :1518-1573; B `bloco_estudo_herdado` :392-417 | sim |
| 9 | Trilha (breadcrumb): concurso → escopo → seção/matéria → assunto; o primeiro nível sempre leva à capa (teste :3240) | B `pagina()` + cada `pagina_*` | sim |
| 10 | Todo link emitido é **relativo** (`relativo()`, :66-83); o site funciona na raiz ou em subpath e aberto por `file://` | B :56-83 | sim |
| 11 | Wikilinks `[[…]]` resolvem por índice global nome→rota montado antes de renderizar; 3 classes de alvo (página, artefato embutido→âncora `#flashcards`, arquivo copiado); âncora de bloco `^id` vence o nome; `00-INDICE` nunca é registrado; o primeiro registro de um nome vence | B `Rotas` :85-170, `montar_rotas` :2109-2228 | sim |
| 12 | Wikilink sem alvo vira `<span class="wikilink-morto">` estilizado, nunca link quebrado | `md2html.py` + CSS (teste :2704) | sim |
| 13 | Assets levam hash do conteúdo na URL (`site.css?v=<sha256[:8]>`) | B `versao_asset` :237-257 | sim |
| **Filtros / busca / paginação** | | | |
| 14 | **Não existe busca, filtro nem paginação** em lugar nenhum do site; `grep -i "busca\|filtro\|search\|filter\|pagina"` nos assets/builder só acha comentários | JS, B | sim (ausência) |
| 15 | Único "filtro" de exibição: botão **Expandir tudo / Recolher tudo** dos `<details>` de tópico do Plano, só quando a matéria tem > 8 tópicos | B `TOPICOS_PARA_RECOLHER = 8` :1085, :1230, :1290; JS :267-296 | sim |
| **Ordem de exibição** | | | |
| 16 | Escopos: `_COMUM` primeiro, cargos em ordem alfabética | C :1705 | sim |
| 17 | Matérias do escopo: por `slug` | C :1409 | sim |
| 18 | Seções: por `(ordinal, slug)`; documentos por nome de arquivo; anexos por `(subpasta, arquivo)` | C :1120-1121, :1411 | sim |
| 19 | Assuntos na aba Estudo, eixo "por prioridade": alta → média → base → sem classificação; prioridade vem do frontmatter, senão da seção "Ordem sugerida" do `00-GUIA*.md` por casamento de termos | B `pagina_materia` :1566-1590; C `prioridades_do_guia` :331-370 | sim |
| 20 | Eixo "na ordem do edital": assuntos agrupados por tópico via `topico_id` **gravado** (nunca inferido por slug); **só agrupa** se nº de tópicos com assunto ≤ 60 % do nº de assuntos, senão grade única com o tópico como selo; assuntos sem vínculo vão para o balde visível "Ainda sem tópico"; o seletor de eixo só aparece quando os dois eixos existem | B `agrupar_por_topico` :1457-1525, :1651 | sim |
| 21 | Aprofundamentos do assunto: `padrao` antes de `detalhado`, com id de pasta antes do legado, depois alfabético; o primeiro é o "principal" (aba que abre, dados do card) | C :814-822 | sim |
| 22 | Aferições da matéria: `data:` desc, depois `rodada:` desc, depois nome | C `achar_docs_afericao` :390-423 | sim |
| 23 | Índice de concursos: ver #2 | | |
| **Quiz** | | | |
| 24 | Sorteio: ordem inicial = ordem do arquivo; "Embaralhar" faz Fisher-Yates e volta ao índice 0 | JS :29-52 | sim |
| 25 | Correção/pontuação: **não há** — só virar, avançar (circular `% length`), embaralhar | JS :9-84 | sim (ausência) |
| 26 | Repetição espaçada: **não há**; a página remete ao Obsidian | B :556-557 | sim (ausência) |
| 27 | Um quiz por aprofundamento (cada aba tem o seu), cards do `.md` de flashcards daquele aprofundamento | B :667-672 | sim |
| 28 | JSON dos cards escapa `</` para o `<script>` não fechar no meio (teste :3271) | B :540-548 | sim |
| **Mídia** | | | |
| 29 | Mídia detectada por presença de arquivo com prefixo do catálogo (8 tipos); presença do **assunto** é a união dos aprofundamentos | C :298-307, :432-466, `uniao_midias` :734 | sim |
| 30 | Mídia ausente = seção ausente (sem placeholder na lateral) | B :628-660 | sim |
| 31 | Selo de mídia no **card** só para o que existe; na **página do assunto** aparecem todos os 8 (ausentes em cinza) | B `selos_midia(so_presentes=…)` :447-461 | sim |
| 32 | Áudio/vídeo com `preload="none"`; ao trocar de aba a mídia da aba que saiu é pausada | B :631, :635; JS :210-214 | sim |
| 33 | Mapa mental/infográfico imagem abrem em lightbox (clique; Esc fecha) | JS :85-104 | sim |
| 34 | Report `.md`/`.txt` é convertido e **anexado ao corpo** da página (não é card lateral); report PDF vira botão | B :682-694 | sim |
| 35 | Botão "Abrir no NotebookLM" só se `notebooklm_url` preenchida (sem iframe) | B :676-680; C :722-728 | sim |
| **Detecção de nomes** | | | |
| 36 | Nível e fontes do aprofundamento vêm do **nome da pasta** (`{nivel}--{f1}[+{f2}]`), não do frontmatter | C :507-514 via `aprofundamento_id.parse_id` | sim |
| 37 | Contagem de fontes por **slug do id**, não pelo campo `fontes:` (texto livre) | C `fontes_externas` :184-199 | sim |
| 38 | Arquivo principal decidido por `aprofundamento_id.arquivo_principal` (evita pegar `_fonte-notebooklm.md`) | C :461-466 | sim |
| 39 | Pastas de escopo/seção casadas por nome literal (`SECOES`, UPPERCASE); `_COMUM`/`COMUM` = comum | C :966-983, :1367-1369, :1418 | sim |
| 40 | Nome legível do concurso: `_`→espaço, `PREVISTO`→"(previsto)", `V2-OFICIAL`→"— oficial (v2)" | B `nome_legivel` :47-53 | sim |
| 41 | Slug de rota do concurso: `[^A-Za-z0-9_-]`→`-`, minúsculo; de escopo: NFKD sem acento, `_` removido | B :2237; C :1420 | sim |
| **Redirect do subpath antigo** | | | |
| 42 | `/concursos` → `301 /`; `/concursos/<x>` → `rewrite … permanent` para `/<x>`; redirects relativos (`absolute_redirect off`, `port_in_redirect off`) | N :47-48, :66-69 | sim |
| **Condições que ocultam/mostram conteúdo** | | | |
| 43 | Escopo sem seção nem matéria não entra no modelo | C :1677-1680 | sim |
| 44 | Documento com `{PLACEHOLDER}` de template é descartado, avisado no stderr e listado em `descartados_placeholder` | C :989-1019, :1049-1053 | sim |
| 45 | `00-INDICE*` e `99-Status*` nunca viram página; `## Meu resumo` do mapa é descartado | C :985, `H2_DESCARTAR` :1145 | sim |
| 46 | Barra: `total>0` sempre aparece (mesmo com 0 feitos); `total==0` some; cobertura desconhecida (`vinculo_ausente`) desenha trilho hachurado e escreve a ressalva, nunca 0 % | B `medidor` :302-344 | sim |
| 47 | Aba **Plano** só se há mapa; aba **Estudo** se há assuntos próprios **ou herdados**; sem os dois, a página vai direto ao conteúdo | B :1631-1640 | sim |
| 48 | Tópico do Plano abre expandido se a matéria tem ≤ 8 tópicos; senão recolhido | B :1230 | sim |
| 49 | "Como a banca cobra" e aferições publicadas **recolhidas** (`<details>`), antes dos assuntos; reabrem na impressão por JS | B :1590-1612, `bussola_recolhida` :1406, `afericao_recolhida` :1427; JS :297-306 | sim |
| 50 | Sumário lateral em documento só com ≥ 4 headings | B `bloco_sumario` :1879-1893 | sim |
| 51 | Link tópico→assunto no Plano só com casamento **exato** de slug ou `mapa-aliases.json`; sem casamento a página **não afirma nada** | B `assuntos_do_topico` :1040-1061 | sim |
| 52 | Card de assunto diz nº de fontes e níveis (selo bolha meia/cheia); "material próprio" anunciado por `tem_proprio` | B `selos_aprofundamento` :935-993 | sim |
| 53 | Tema claro/escuro: `localStorage` > `prefers-color-scheme`; aplicado inline antes da pintura | B :276-278; JS :107-139 | sim |
| 54 | Página do pacote NotebookLM só existe se algum aprofundamento tem `_fonte-notebooklm.md`; mostra fontes a subir, nome do notebook, 4 prompts com botão "Copiar" (clipboard API com fallback `execCommand`) | B :2210-2220, `pagina_notebooklm` :889; JS :219-266 | sim |
| **Cache** | | | |
| 55 | `*.html`: `expires -1` (`Cache-Control: no-cache`); tudo o mais (`location /`): `expires 1h`; assets versionados por hash (#13); mídia com nome único por aprofundamento | N :82-101 | sim |
| 56 | gzip só em text/css/js/json/markdown, mín. 1 KB; mídia não comprimida; `Accept-Ranges` padrão do nginx (seek de áudio) | N :34-36, :95-97 | sim |
| 57 | Healthcheck `GET /healthz` → `200 ok` | N :53-56; compose :61-67 | sim |
| **Deploy (regras que afetam o que se vê)** | | | |
| 58 | Todo deploy reconstrói **todos** os concursos do build (origem lida do `.concurso.json`); `--so-este` avisa e republica os demais como estão | D :195-258, :271-296 | sim |
| 59 | Build menor que o servidor **aborta** (despublicaria concurso); `--permitir-remocao` libera e lista | D :336-390 | sim |
| 60 | Permissões normalizadas no destino (`--chmod=D755,F644`) — arquivo 0600 no vault dava 403 | D :338-346 | sim |

---

## 5. TELAS E ROTAS DO SITE

Todas as rotas são `…/index.html` (diretório + index), decididas em `montar_rotas`
(`site_builder.py:2109-2228`). `{c}` = slug do concurso (`sedes_2026`, `bb_2027_previsto`),
`{e}` = slug do escopo (`comum` ou o cargo em minúsculas), `{s}` = seção, `{m}` = matéria,
`{a}` = assunto.

| Tipo | Rota | Por concurso | Mostra | Função |
|---|---|---|---|---|
| Índice raiz | `/index.html` | **global** (1) | cards de concurso agrupados por órgão | `pagina_raiz` :2020 |
| Capa | `/{c}/index.html` | 1 | ficha da prova + card por escopo | `pagina_capa` :1937 |
| Hub de escopo | `/{c}/{e}/index.html` | 1 por escopo | duas barras (tarefas, cobertura), cards de matéria, seções estudo/consulta | `pagina_escopo` :1747 |
| Seção | `/{c}/{e}/{s}/index.html` | 1 por seção com >1 doc ou anexos | lista de documentos + anexos com tamanho; ou o próprio documento se colapsada (#6) | `pagina_secao` :1860 |
| Documento | `/{c}/{e}/{s}/{doc}/index.html` | 1 por `.md` publicável | MD renderizado, checkboxes como tarefas, sumário lateral se ≥4 H | `pagina_documento` :1896 |
| Anexo | `/{c}/{e}/{s}/arquivos/{subpasta}/{arquivo}` | 1 por arquivo não-`.md` | arquivo bruto (PDF, txt) | `rota_anexo` :198, `copiar_anexos` :2092 |
| Matéria | `/{c}/{e}/materias/{m}/index.html` | 1 por matéria | abas **Plano** (tópicos do edital em `<details>`: literais, subtópicos com estado, material, pegadinhas, meta, extras) e **Estudo** (banca, aferições, cobertura do edital, eixos "ordem do edital"/"prioridade", cards de assunto, docs de apoio) | `pagina_materia` :1561 |
| Assunto | `/{c}/{e}/materias/{m}/{a}/index.html` | 1 por assunto | abas por aprofundamento (nível/fonte); esquerda: ficha (fontes, onde está, nível, fontes do notebook) + resumo; direita: barra de tarefas, áudio, vídeo, mapa mental, infográfico, slides, outros, quiz, botão NotebookLM | `pagina_assunto` :751 |
| Mídia | `/{c}/{e}/materias/{m}/{a}/media/{ident}/{arquivo}` | 1 por mídia | arquivo bruto | closure `copiar` :614 |
| Pacote NotebookLM | `/{c}/{e}/materias/{m}/{a}/notebooklm/index.html` | 1 por assunto com pacote | fontes a subir, nome do notebook, 4 prompts copiáveis, perguntas, checklist | `pagina_notebooklm` :889 |
| Manifesto | `/{c}/.concurso.json` | 1 | `{concurso, slug, origem, orgao, banca, prova_data, n_materias, n_assuntos, gerado_em}` | :2318-2331 |
| Assets | `/assets/site.css`, `/assets/site.js` | **global** | | :2256-2261 |
| Health | `/healthz` | global (nginx) | `ok` | `nginx.conf:53` |

**Contagem no `out/site` de hoje (build de 2026-08-06):**

| Tipo | `sedes_2026` | `bb_2027_previsto` | total |
|---|---|---|---|
| raiz | — | — | 1 |
| capa | 1 | 1 | 2 |
| escopo | 4 | 3 | 7 |
| seção (nível 3, não colapsada) | | | 24 |
| documento (nível 4) | | | 37 |
| matéria | 12 | 10 | 22 |
| assunto | 101 | 47 | 148 |
| pacote NotebookLM | 101 | 47 | 148 |
| **páginas HTML** | **242** | **146** | **389** |
| anexos (PDF/txt) | | | 87 (58 em `materiais/arquivos`, 29 em edital/histórico/sinergia) |
| mídias copiadas | | | 22 (17 m4a, 2 mp4, 2 png, 1 md) |
| manifestos | 1 | 1 | 2 |

Seções presentes por escopo (real): comum → `edital, materiais, historico, sinergia`; cargo →
`cronograma, materiais (herdada), discursiva` [+ `titulos` num cargo].

Estático **por concurso**: tudo sob `/{c}/`. **Global**: `/index.html` (remontado a cada build a
partir dos manifestos) e `/assets/`. O `deploy.sh` reconstrói todos os concursos antes de enviar
(#58), então na prática o build inteiro é regenerado a cada publicação.

---

## 6. USUÁRIOS E ACESSO

- **Autenticação: não existe.** `nginx.conf` não tem `auth_basic`, `allow/deny` nem TLS
  (`listen 80` apenas, `:40`). `SKILL.md` princípio 3: "sem publicação externa, sem autenticação";
  "Fora de escopo desta versão: Backend, login". Nada no JS pede credencial.
- **Quem acessa**: qualquer cliente que alcance `{host}:8099` na LAN. Nome `concursos.casa` é
  só o `server_name` esperado (`nginx.conf:41`, com `_` catch-all) e o padrão de `CONCURSOS_HOST`
  (`deploy.sh:70`); a resolução é responsabilidade externa — `deploy/README.md:51-56` sugere
  registro A em DNS local (roteador, Pi-hole, AdGuard, Unbound) ou `/etc/hosts`. No `deploy.env`
  local o host é um **IP**, não o nome. ⚠️ Se existe registro DNS `concursos.casa` de fato, e em
  que resolvedor, não é verificável no repositório.
- **Dimensionamento declarado**: "~3 usuários simultâneos" (`docker-compose.yml:33`,
  `nginx.conf:11`, `deploy/README.md:83`). ⚠️ Se são 3 pessoas reais ou folga de projeto, o
  repo não diz.
- **De quem é o conteúdo**: de **um vault** (o do dono do repo; `CLAUDE.md` global). Os dois
  concursos publicados vêm da mesma pasta `30_AREAS/CARREIRA/CONCURSOS/` desse vault
  (`.concurso.json[].origem`). Não há mecanismo para conteúdo de mais de uma pessoa: o site não
  tem noção de usuário, e o índice raiz só agrupa por órgão. ⚠️ Se outras pessoas da casa
  estudam pelo site (leitores), não é verificável.
- **Concursos publicados hoje**: **2** (`SEDES_2026` — banca Instituto Quadrix, prova
  2026-09-06; `BB_2027_PREVISTO` — banca Cesgranrio, sem data). 22 matérias, 148 assuntos.
- **O que há de sensível no site** (fatos, sem juízo):
  - `/{c}/.concurso.json` contém `origem` = **path absoluto do vault na máquina do dono**
    (inclui `/home/<usuário>/…`); nginx **serve dotfiles** (não há `location ~ /\.`), então o
    caminho é lido por qualquer cliente da LAN. Confirmado: `grep -rl '/home/' out/site` → só os
    dois manifestos (o 3º hit é uma URL externa `…/home/…` num documento).
  - Documentos do vault publicados na íntegra: edital (resumo, análise da banca, cronograma
    oficial), cronograma pessoal de estudo (`02-CRONOGRAMA`), discursiva, títulos, histórico,
    sinergia, materiais. `99-Status.md` **não** é publicado. O `.meta.json` não é copiado — só
    a allowlist entra na capa.
  - 86 PDFs copiados: leis (domínio público), editais/provas anteriores e provas de sinergia
    (baixados de portais públicos pela prep) e o edital original.
  - Mídias geradas no NotebookLM (podcasts, vídeos) e resumos próprios (Modelo 2: sem texto
    integral de livro; `CLAUDE.md`).
  - Nada de senha/token: `deploy.env` está no `.gitignore` e não é copiado para `out/`.
  - Tudo trafega em **HTTP sem TLS** dentro da LAN.

---

## 7. DEPLOY

- **Arquivos**: §2 (compose e nginx colados). `deploy/.gitignore` ignora `deploy.env`.
- **`deploy.sh` — o que faz, na ordem** (roda na **máquina do vault**, `deploy.sh:4`):
  1. Lê `deploy.env` linha a linha sem `source` (`:43-64`); precedência ambiente > env > padrões
     (`:70-74`). Aceita `BEELINK_*` como fallback (`:66-72`) — o servidor já se chamou `beelink.casa`
     (`deploy/README.md:44-45`). ⚠️ Modelo/OS do servidor não constam no repo.
  2. `--setup` (`:100-168`): checa porta livre via `ss`/`netstat` remoto, `mkdir -p {DIR}/site`,
     `scp` compose + nginx.conf, escreve `index.html` placeholder, escreve `{DIR}/.env` com
     `CONCURSOS_PORTA`, `docker compose up -d`, `docker compose ps`.
  3. Build (`:195-296`): descobre todos os `*/.concurso.json` em `out/site` (python inline),
     resolve `origem` (ou deduz pasta irmã, ecoando), roda `site_builder.py --concurso-dir … --out
     out/site` para **cada** concurso (alvo primeiro); órfãos (origem sumiu) são avisados e
     republicados como estão. `--so-build` para aqui.
  4. Guarda (`:336-390`): lista pastas de concurso no build e no servidor (`ssh find`); se o servidor
     tem algo que o build não tem, **aborta** salvo `--permitir-remocao`.
  5. `rsync -az --delete --chmod=D755,F644 --human-readable --info=stats1 out/site/ user@host:{DIR}/site/`
     (`:346, :397`); `--dry-run` acrescenta `--dry-run --itemize-changes`.
  6. Se o container não está `running`, `docker compose up -d` (`:407-412`).
- **Para onde / usuário**: `{CONCURSOS_USER}@{CONCURSOS_HOST}:{CONCURSOS_DIR}/site/`; padrões
  `concursos.casa`, `$USER`, `/opt/concursos`. Valores reais no `deploy.env` local (host = IP,
  dir ≠ padrão). Precisa de SSH por chave já configurada ⚠️ (o script não autentica nada).
- **Porta**: host `${CONCURSOS_PORTA:-8099}` → container 80 (`compose:26`).
- **Recursos**: 0,5 CPU / 128 MB limite; 0,05 / 32 MB reserva.
- **Onde roda**: container no servidor doméstico; build e rsync na máquina do vault. Não há
  build no servidor nem Dockerfile — a imagem é `nginx:alpine` pura.
- **CI** (`.github/workflows/tests.yml`, gatilho `push main` + `pull_request`, Python 3.11,
  `ubuntu-latest`): `test-all.sh` (todas as suítes + `test_install.sh` + `test_deploy.sh`);
  `bash -n` e `shellcheck` nos shells; higiene (`__pycache__`, nomes estranhos); `yaml.safe_load`
  do compose; arquivo > 2 MB barrado; versão em 3 lugares; skill citada na doc; índice de
  convenções; nome de pasta de histórico; "Versão atual" de uma linha; links/âncoras relativos;
  mermaid do README = `.mmd`. **O CI não faz deploy** nem gera o site real.
- **Ao republicar**: rsync **in-place** no diretório servido (bind mount `:ro`), sem diretório
  de staging, sem `--delay-updates`, sem swap de symlink, sem restart. Consequências factuais:
  **sem downtime** (nginx segue servindo) e **não atômico** — durante a transferência coexistem
  arquivos novos e velhos; `--delete` remove versões antigas de `assets/site.css?v=<hash>` que
  uma página ainda em cache (`expires 1h` para não-HTML; HTML é `no-cache`) pode referenciar.
  O build local também não é atômico: `rmtree` da pasta do concurso antes de regenerar
  (`site_builder.py:2251-2253`), e `out/site` é declarado "espelho do que está publicado, não
  cache" (`deploy.sh:381-384`).
- **Estado do deploy hoje**: nota de sessão 2026-08-16 diz que o build no ar é de **06/08**
  (mesma data dos manifestos em `out/site`), anterior às ondas D+E, e que faltava rodar
  `--setup` para levar nginx.conf/compose novos. ⚠️ Não verificado nesta sessão (sem acesso ao servidor).

---

## 8. TESTES

- **`skills/concurso-publica/scripts/tests/test_smoke.py`** — 3.547 linhas, **184 testes**, roda
  standalone (`python3 test_smoke.py`; pytest opcional). Rodado nesta sessão: **184/184 passaram**.
  Usa `fixture_concurso.py` (274 linhas), que monta um concurso sintético no layout canônico
  (`test_fixture_espelha_as_pastas_numeradas_do_vault`, `:64`) — a regra do repo é que o fixture
  espelhe a saída real da skill anterior (`CLAUDE.md`, "Fixture tem de espelhar…").
- **O que cobre da web** (por família, com o teste-âncora):
  - Coletor: progresso (`:91`, `:158`), cards (`:97`), mídias por presença (`:135`, `:2745`),
    flashcards nome divergente (`:148`), `notebooklm_url` (`:168`), concurso vazio (`:183`),
    layouts atual/antigo/legado (`:2991-3016`, `:3135`, `:3394`), nível pela pasta (`:3382`),
    fontes por id (`:1137`), placeholder (`:3189`, `:3227`), seções numeradas (`:1034`), herança
    do comum (`:854-900`), cruzamento mapa↔aprofundamento (`:1351`, `:1377`, `:2194-2258`),
    cobertura (`:1834-1890`, `:2077-2121`), tarefas (`:1931-2048`), mapa (`:1694-1807`),
    aferições (`:2806-2882`), pack NotebookLM (`:2396-2501`), cópia do `aprofundamento_id` (`:3416`).
  - `md2html`: 24 testes (`:205-419`) — headings/ids/sumário, listas aninhadas, tarefas, negrito/
    itálico, wikilinks (âncora, pipe, tabela), autolink, escape de HTML.
  - **Gerador (builder)**: gera páginas e assets (`:511`), não escreve no vault (`:458`), manifesto
    (`:493`), embute mídia presente e omite ausente (`:527`), links internos resolvem e nenhuma
    página órfã (`:612`, `:621`), auditor de links/âncoras (`:631`), rotas relativas (`:652`),
    3 classes de alvo (`:699`), rebuild limpa layout antigo (`:796`), anexo copiado uma vez (`:2646`),
    asset versionado (`:2258`), exemplo do modelo constrói (`:1614`), modelo antigo aceito (`:1670`),
    índice raiz acumula/agrupa (`:2911`, `:3048`), abas ARIA (`:3327`), trilha (`:3240`).
  - **Quiz**: `test_builder_quiz_com_cards_embutidos` (`:540`), `test_parsear_flashcards_…` (`:431`),
    `test_quiz_sobrevive_a_cartao_que_contem_fecha_script` (`:3271`),
    `test_teclado_do_quiz_nao_sequestra_os_botoes` (`:3313`). Os testes de JS são **asserts sobre o
    texto** de `site.js`/HTML gerado (ex.: `:1686`, `:3299`), **não execução em navegador** — não há
    headless browser, jsdom nem Node no repo.
  - CSS: cores só via variáveis (`:2936`, `:2953`), barras com cores de tema (`:2310`), wikilink morto (`:2704`).
- **`scripts/tests/test_deploy.sh`** — 361 linhas, **26 testes**, `ssh/scp/rsync/docker` substituídos
  por stubs que gravam o argv (`:29-40`); cobre `--setup`, plano de builds, órfãos, `--so-este`,
  guarda de remoção, `--dry-run`, `--chmod`, precedência de config. **26/26 passaram** nesta sessão.
- **`scripts/test-all.sh`** roda toda `scripts/tests/test_*.py` de cada skill + os `.sh`; é o passo
  principal do CI. Suíte total do repo: 675 asserts (nota de sessão 2026-08-16).
- **Não existe**: teste de integração contra o vault real; teste de renderização visual; teste de
  performance/peso; teste do nginx rodando (o `test_deploy.sh` não sobe container — os defeitos de
  `cap_drop` e `add_header` só apareceram "com o container de pé", nota de sessão 2026-08-16).

---

## 9. TAMANHO E HISTÓRICO

**Linhas** (sem testes; `wc -l`):

| Área | Código | Testes |
|---|---|---|
| **web** — `concurso-publica` (py 5.017 + js 316 + css 811) | **6.144** | 3.821 |
| **web** — `deploy/` (sh 424 + nginx 104 + compose 97) | **625** | 361 (`test_deploy.sh`) |
| `concurso-prep` | 4.967 | 2.184 |
| `concurso-aprofunda` | 4.237 | 2.266 |
| `concurso-notebooklm` | 1.377 | 848 |
| `concurso-afere` | 1.410 | 681 |
| `scripts/` (install, test-all) | 302 | 156 (`test_install.sh`) |

Web = 6.769 de 19.062 linhas de código (**36 %**); a `concurso-publica` é a maior skill do repo.
Dentro dela: `site_builder.py` 2.374 (39 %), `site_collector.py` 1.769 (29 %), `md2html.py` 437,
`aprofundamento_id.py` 437 (cópia), `site.css` 811, `site.js` 316.

**Git** (em `main`, `4e5b754`):
- **129 commits**, 30 merges, de 2026-07-29 a 2026-08-12 (15 dias de histórico; o primeiro commit
  `550db2a` já traz as skills). Branch local/remota: `main` + 3 `feat/*` já mergeadas (pendente
  apagar, nota de sessão 2026-08-16).
- Commits (sem merge) que tocam `skills/concurso-publica` ou `deploy/`: **51** — **23 só web**,
  **28 mistos** (também tocam `out2` [200 arquivos, ver abaixo], `concurso-aprofunda` 83 arquivos,
  `concurso-prep` 55, `CLAUDE.md` 14, `scripts` 11, `docs` 10).
- Por área: `concurso-publica` 45 commits, `deploy` 11, `aprofunda` 29, `prep` 25, `notebooklm` 8, `afere` 7.
- `git log --follow -- skills/concurso-publica/scripts/site_builder.py`: 22 commits, desde 2026-07-29,
  **sem renomeação** (o path é o mesmo desde o primeiro commit). O histórico da pasta
  `skills/concurso-publica/` é **separável por path** (`git log -- skills/concurso-publica` funciona
  limpo), mas 28 dos 51 commits são mistos — um `git filter-repo --path skills/concurso-publica
  --path deploy` produziria histórico coerente da web, com esses commits reduzidos ao que toca a web. ⚠️ Não executado.
- **`.git` = 101 MB** (`count-objects`: 1.747 objetos soltos, pack 0 bytes). Causa registrada em
  `tests.yml:53-56`: um build foi para `out2/` (fora do `.gitignore` da época) e entrou com mídia;
  removido no commit seguinte, segue no histórico. `.gitignore` hoje: `out*/`. Decisão de
  reescrever (force-push) **adiada** — tarefa no vault (nota de sessão 2026-08-16).
- Versão da skill web: **0.25.0** (2026-08-12); subiu de 0.23.0 → 0.25.0 na última sessão.
  CHANGELOG em Keep-a-Changelog.

---

## 10. CONTEXTO PARA ARQUITETURA (fatos, sem decidir)

### 10.1 O gerador consegue emitir HOJE um bundle só de dados (JSON + mídias) sem HTML?

- **JSON: sim, parcialmente.** `site_collector.py --concurso-dir … --out site-model.json` emite o
  modelo completo sem tocar no builder (`main`, `:1742-1765`). Limites factuais desse JSON:
  - traz **paths absolutos da máquina do vault** (`dir`, `caminho`, `resumo_md`, `mapa.caminho`,
    `pack_notebooklm.caminho`) e **não traz o conteúdo** dos `.md` — o corpo do assunto, dos
    documentos, dos mapas (exceto `blocos[].markdown` do mapa, que é cru) e o texto dos flashcards
    são lidos pelo **builder** no momento de renderizar (`site_builder.py:606`, `:668`, `:1906`).
  - as mídias e anexos aparecem só como **nome/caminho/bytes**; a cópia é do builder.
- **Mídias sem HTML: não há comando.** A cópia acontece dentro de `bloco_aprofundamento` (closure
  `copiar`, `:614-617`) e `copiar_anexos` (`:2092-2106`), ambos chamados pelo laço de renderização
  em `construir` (`:2266-2312`). Não existe flag "só copiar".

### 10.2 O que é DADO e o que é APRESENTAÇÃO no código

| Camada | Onde | Natureza |
|---|---|---|
| **Dado puro** | `site_collector.py` inteiro (1.769 linhas): descoberta de pastas, frontmatter, progresso, cobertura, mídias, pack, mapa em `blocos[]` | sem HTML; única saída é dict/JSON |
| **Dado que o builder ainda extrai** | `parsear_flashcards` (`site_builder.py:467-499`) → `[{f,v}]`; leitura dos `.md` de assunto/documento/report (`:606`, `:684-689`, `:1906`); `md2html.sumario()` | funções puras que devolvem estruturas; vivem no builder por acidente de organização |
| **Decisão de rotas (dado)** | `montar_rotas` (`:2109-2228`): tabela `plano[]` de {rota, tipo, objetos} + índice `Rotas` nome→rota | não emite HTML; é o "roteamento" |
| **Apresentação** | `md2html.converter()` (MD→HTML); todas as `pagina_*`, `bloco_*`, `card_*`, `selos_*`, `medidor`, `botao_aba`, `bloco_quiz` (`site_builder.py:260-2016`, ≈1.750 linhas); `site.css`; `site.js` | f-strings HTML, classes CSS, ARIA |
| **Regras de negócio embutidas na apresentação** | `agrupar_por_topico` (limiar 60 %, `:1487`), `TOPICOS_PARA_RECOLHER` (`:1085`), `bloco_sumario` (≥4, `:1889`), `medidor` (zero vs ausente vs indefinida, `:302-344`), `linhas_do_escopo/materia` (`:347-389`), `pagina_capa` (raiz vs por cargo, `:1958-1972`), `pagina_raiz` (agrupar por órgão, tag por nome, `:2027-2065`), `selos_aprofundamento` (`:935-993`), `assuntos_do_topico` (casamento exato, `:1040-1061`) | lógica misturada com o HTML que ela produz |
| **Efeitos colaterais** | `construir` (`:2231-2343`): `rmtree`, cópia de assets, escrita de páginas, manifesto, índice raiz | I/O |

### 10.3 O que exige estado por usuário

- **Hoje: nenhum estado por usuário no site.** Progresso = checkboxes no vault (lidos no build);
  respostas do quiz = não guardadas; favoritos = não existem; posição na leitura = não guardada.
- Único estado no cliente: `localStorage["concursos:tema"]` (preferência visual).
- O que **existe como dado** e hoje só é exibido: `progresso{feitos,total}` em 5 níveis (aprofundamento,
  assunto, matéria, escopo, documento, tópico do mapa, subtópico com `feito`); `checklist[].feito` do
  pack NotebookLM; `status` do assunto (`nao-iniciado|revisar|concluido`); flashcards com
  `cards.json`/`.csv` (Anki) ao lado.

### 10.4 Dependências em runtime

- **Vault**: não (§1.3). **Rede**: não — sem CDN, sem fonte externa, sem API; funciona por `file://`.
  **Além de arquivos estáticos**: nada; o nginx só faz `try_files` + redirect + headers.
- Únicos links externos: `notebooklm_url` (botão, `target=_blank`) e URLs que estejam dentro do
  conteúdo dos `.md` (autolink do `md2html`).

### 10.5 Peso das mídias

- 1,0 GB no build, 943 MB são áudio/vídeo (19 arquivos). Maior arquivo 68,1 MB; 10 > 50 MB; 0 > 100 MB.
- Servidos hoje como arquivo estático com `sendfile`, `Accept-Ranges` (seek), `expires 1h`,
  sem gzip, `preload="none"`. Nome de arquivo único por aprofundamento (`media/{ident}/{nome}`).
- Crescimento: cada podcast do NotebookLM tem 40–70 MB; há **148 assuntos** e **17 podcasts**
  (11 %); 177 pacotes prontos. ⚠️ Projeção não feita — depende de quantos pacotes serão executados.

### 10.6 O que precisaria mudar nas SKILLS se a saída fosse consumida por uma SPA em outro repo

Fatos sobre acoplamento (sem propor):

- **Zero acoplamento de código** das 4 skills com o HTML: nenhuma importa o builder (§1.4).
- **Contratos que uma SPA precisaria conhecer e hoje estão só na publica**:
  1. `SECOES` (pasta→seção→registro), `DOCS_NAO_PUBLICAVEIS`, `PLACEHOLDER_RE`, `IGNORAR_EXT`
     (`site_collector.py:964-989`) — a definição do que é publicável.
  2. `CATALOGO_MIDIAS` (`:298-307`) — a `concurso-notebooklm` nomeia mídias segundo ele.
  3. `aprofundamento_id.py` — fonte na aprofunda, cópia na publica.
  4. Parser de mapa (`H3_MAPA`, `blocos_do_topico`, `:1130-1240`) e de pack (`:575-728`).
  5. Parser de flashcards (`site_builder.py:467`) e contagem (`site_collector.py:282`).
  6. `md2html.py` — as convenções de wikilink/âncora/block-id e o resolvedor `(alvo, âncora)→href`
     via `Rotas` (`:85-170`). Wikilinks nos `.md` do vault usam duas convenções (caminho absoluto
     do vault no SEDES, nome nu no BB — docstring `Rotas.chave`, `:120-127`).
- **O que hoje só existe como HTML gerado** (não está no `site-model.json`): corpo renderizado
  dos assuntos/documentos/reports; cards do quiz; sumários; rotas/URLs; medidores; agrupamentos;
  ordem final de exibição; cobertura "explicada" (`bloco_cobertura`, `:1528`).
- **O que já está fora da web e não muda**: `.meta.json`, mapas, `.md` de assunto (frontmatter em
  `docs/CONTRATO-DE-DADOS.md`), `_fonte-notebooklm.md`, flashcards, mídias, aferições, `99-Status.md`.
- **Path absoluto**: o modelo carrega paths da máquina do vault; um consumidor em outra máquina
  não os resolve.

---

## 11. ZONA CINZENTA — "só leitura" vs "com backend" (opções, sem decidir)

| Item | Situação hoje | Se ficar só leitura | Se tiver backend |
|---|---|---|---|
| **Progresso (checkboxes)** | dado vive no vault; site exibe no build; 0,1–0,2 % marcados; a pessoa marca no Obsidian | continua lido no build; marcar no site é impossível; qualquer estudo fora do Obsidian não registra nada | site poderia gravar — mas o vault é "única fonte de verdade" (`SKILL.md` princípio 4, `CONVENCOES.md`); haveria dois lugares de escrita e um caminho site→vault que hoje **não existe** (nem API do Obsidian no servidor: o MCP Local REST API roda na máquina do dono, `~/.claude/CLAUDE.md`) |
| **Quiz** | prática sem correção nem histórico; SR do Obsidian sem nenhuma revisão registrada (0 `<!--SR:` em 177 baralhos) | quiz igual ao de hoje; histórico só no Obsidian/Anki | histórico por usuário; o SR do plugin ancora no **texto da frente** (`CLAUDE.md`), então um histórico paralelo não conversa com o do Obsidian sem espelhar essa chave |
| **Multiusuário** | conteúdo de um vault; ~3 leitores simultâneos de projeto; sem identidade | login só separa quem vê; conteúdo continua sendo um vault | identidade permite progresso/quiz por pessoa; mas há **um** conteúdo — separar "conteúdo de quem" exigiria mais de um vault ou pasta por pessoa, que a prep não produz hoje |
| **Tema/preferências** | `localStorage` | idem | por conta |
| **Mídia (1 GB, arquivos até 68 MB)** | estático via nginx com range requests | idem, atrás do proxy da suite | idem; um backend não precisa intermediar bytes, mas a autorização de URL de mídia (se atrás de login) passa a ser dele |
| **Coleta de dados (JSON)** | coletor emite JSON com paths absolutos e sem corpo dos `.md` | um bundle JSON+MD+mídia serviria como "API estática" | um backend leria o vault (precisa estar na máquina do vault ou receber sync) |
| **Republicação** | rsync in-place, não atômico, sem downtime | igual | um backend com banco tem estado a migrar a cada republicação |
| **NotebookLM** | link externo por assunto | igual | igual (sem API pública) |
| **Publicação incremental** | `.concurso.json` + rebuild de tudo | igual | um backend poderia indexar sem rebuild, mas quem lê o vault continua sendo a máquina do dono |

---

## 12. PERGUNTAS EM ABERTO (só o dono sabe)

1. **Quem mais usa o site hoje?** O "3 usuários simultâneos" é folga de projeto ou há outras pessoas
   da casa lendo? Se há, elas estudam concursos **diferentes** (outro vault/pasta) ou os mesmos?
2. **O progresso deve sair do vault?** Hoje 8 de 3.820 checkboxes estão marcados no vault inteiro e a
   tarefa "0,15 %" está aberta. A pessoa marca no Obsidian de fato, ou a marcação simplesmente não
   acontece em lugar nenhum? Isso decide se "gravar no site" resolve um problema real.
3. **Quiz: prática ou revisão?** O SR do Obsidian nunca foi usado (0 marcações). O quiz do site basta
   como prática, ou o histórico de acertos é o que falta?
4. **A SPA vai rodar no mesmo servidor doméstico** (bind mount, 0,5 CPU / 128 MB) ou em outro
   lugar? Isso muda o que pode ler o vault.
5. **O vault continua na máquina pessoal** (Insync/GDrive) — o servidor nunca terá acesso a ele?
   Todo caminho "backend lê o vault" depende dessa resposta.
6. **Login para quê:** esconder da LAN, ou identificar pessoa para estado por usuário? São
   requisitos diferentes.
7. **O path absoluto do vault publicado em `.concurso.json` incomoda?** É lido por qualquer cliente
   da LAN hoje.
8. **DNS `concursos.casa` existe** em algum resolvedor da casa, ou todo mundo usa o IP (como o
   `deploy.env`)? A suite vai ter domínio próprio?
9. **O `site-model.json` deve virar o contrato da SPA** ou a SPA consome os `.md` direto? Hoje o
   modelo não tem o corpo dos textos nem os cards.
10. **Design system compartilhado**: o `site.css` (811 linhas, variáveis de tema, paleta "papel/tinta/
    marca-texto") é descartado ou algo dele (tokens, componente de barra, bolha do cartão-resposta) é
    requisito?
11. **Quantos pacotes NotebookLM serão executados** (17 de 177 hoje)? Define o teto de mídia
    (≈50 MB por podcast).
12. **A cópia do `aprofundamento_id.py`** e o `CATALOGO_MIDIAS` passam a viver onde, se a publica
    some do repo? Quem for ler o vault precisa deles.
13. **Os 101 MB no `.git`** e as 3 branches mergeadas: decisão pendente antes de extrair a web para
    outro repositório?
14. **A skill `concurso-publica` continua existindo** (gerando o site atual) durante a transição, ou
    o site atual é desligado quando a SPA subir? Afeta se o `deploy/` permanece.

---

## Resumo dos ⚠️ (inferido, não confirmado no código)

- Registro DNS `concursos.casa` e resolvedor usado.
- Se os "3 usuários" são pessoas reais e se leitores externos existem.
- Modelo/OS do servidor (só se sabe que já se chamou "beelink").
- Estado do deploy no servidor (build de 06/08 no ar; `--setup` pendente) — não verificado.
- SSH por chave configurado (o script assume).
- `site-model-exemplo.json` defasado em 8 campos — verificado por `grep`, mas o **impacto** em quem
  consome `--modelo` externo não foi medido.
- Projeção de crescimento de mídia.
- Viabilidade de `git filter-repo` para separar o histórico da web — não executado.
