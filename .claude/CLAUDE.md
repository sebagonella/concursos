# 14_concursos — Contexto para Claude Code

## Vault Obsidian
- **Vault:** /home/sebagonella/work/cloud/1_insync-gdrive-sebastiao.gonella/02_SYNC-ALIVE/01_COFRES/02_NOTEBOOKS/02_OBSIDIAN/0_sebagonella2
- **Nota do projeto:** 20_PROJETOS/PROFISSIONAL/14_concursos/_PROJETO.md
- **Sessoes:** 20_PROJETOS/PROFISSIONAL/14_concursos/SESSOES/
- **Decisoes:** 20_PROJETOS/PROFISSIONAL/14_concursos/DECISOES/
- **Pesquisas:** 20_PROJETOS/PROFISSIONAL/14_concursos/PESQUISAS/
- **Tarefas:** 20_PROJETOS/PROFISSIONAL/14_concursos/TAREFAS/

## Ao iniciar (/session-start)
1. Leia _PROJETO.md via MCP
2. Leia a sessao mais recente em SESSOES/
3. Confirme o objetivo da sessao

## Ao finalizar (/session-end slug)
1. Crie nota de sessao em SESSOES/
2. Atualize daily note automaticamente

## Stack tecnica
- Repositorio: /home/sebagonella/work/local/02_SOLUTIONS/14_concursos
- Python 3 (skills e scripts, quase so stdlib), Bash (install/test/deploy),
  Docker + nginx:alpine (servir o site), Markdown/Obsidian como saida.
- Dependencias externas sao **opcionais** (reportlab, OCR) — degradacao graciosa.

## Comandos

```bash
bash scripts/install.sh                       # instala/atualiza TODAS as skills (global, ~/.claude/)
bash scripts/install.sh --only <skill>        # instala so uma
bash scripts/install.sh --local               # instala no .claude/ do diretorio atual
bash scripts/install.sh --uninstall           # desinstala
bash scripts/test-all.sh                      # roda os testes de todas as skills

./deploy/deploy.sh --setup                          # 1a vez no servidor domestico
./deploy/deploy.sh --concurso-dir <.../SEDES_2026>  # atualizacoes
./deploy/deploy.sh --concurso-dir <...> --dry-run   # conferir antes
./deploy/deploy.sh --concurso-dir <...> --so-este   # nao reconstruir os outros
```

> Apos instalar/atualizar, **reinicie a sessao do Claude Code** — as skills sao
> carregadas no inicio da sessao e a versao anterior pode ficar em cache.

## Regras do projeto

Regras vindas de bugs reais — quebra-las volta a quebrar coisas:

- **Slugs em UPPERCASE** para pastas de concurso e cargo (`SEDES_2026`,
  `EDAS-ADMINISTRACAO`, `_COMUM`). O validador checa isso.
- **Metadata em `.meta.json`** (nao YAML), com o conteudo programatico integral
  (`materias[].topicos` — o motor de diff depende) e o `edital_hash` (SHA-256).
- **Nunca sobrescrever versao anterior** numa reconciliacao: `V1-PREVISTO` →
  `V2-OFICIAL` → `V3-RETIFICADO`, lado a lado, preservando o progresso.
- **Direitos autorais (Modelo 2)**: a Etapa 2 nao extrai texto integral de livros
  protegidos — so localizacao (paginas) e trechos curtos citados. Resumo sempre
  original, escrito do zero. Nao relaxar.
- **Flashcards do Obsidian**: no formato multi-linha o `??` fica **sozinho na
  propria linha**; colado na resposta o plugin Spaced Repetition nao le o cartao.
- **Nunca fingir precisao**: localizacao com baixa confianca ou nao encontrada
  vira pendencia explicita para conferencia humana. Nao inventar pagina.
- **O site e derivado, o vault e a fonte**: `concurso-publica` nunca escreve no
  vault; o progresso exibido e so leitura.
- **O site espelha COMUM/cargo** (`{concurso}/{comum|cargo}/`). `00-INDICE.md` e
  `99-Status.md` sao derivados, nao republicados — mas continuam sendo lidos (deles
  saem a ordenacao das materias, os selos de questoes/prioridade e, do status, os
  checkboxes que entram na barra de tarefas do escopo).
- **Progresso e barra, em todo lugar.** A bolha do cartao-resposta nao mede mais
  progresso — sobrevive como selo de nivel e marcador das listas de tarefa. Duas
  tentativas falharam antes: `min(total, max_bolhas)` fazia 8 bolhas valerem 303
  tarefas, e depois barra na materia com bolha no assunto punha o mesmo numero com
  duas aparencias em telas vizinhas. Escopo e materia usam **duas barras lisas,
  sempre na mesma ordem**: tarefas de estudo (verde `--confere`) em cima, topicos do
  edital (azul `--tinta`) embaixo; o assunto usa so a de tarefas.
- **Tarefas de estudo = assuntos (uniao dos aprofundamentos) + itens do plano do mapa
  + documentos de secao + `99-Status.md`** (`progresso_tarefas`). Cada exclusao aqui ja
  escondeu trabalho: so os assuntos deixava os cargos sem barra tendo 21/17/8 tarefas em
  documentos; so o aprofundamento principal sumia com 181 checkboxes em 29 assuntos. Os
  **mapas sairam na 0.17.0 e voltaram na 0.18.0** — o argumento de que 1.998 itens nunca
  marcados afogariam as ~200 reais estava errado, e a exclusao deixava **12 das 22
  materias sem barra nenhuma**.
- **O mapa conta para quem guarda o arquivo**: materia com `mapa_em` (mapa emprestado
  pelo cruzamento) nao soma os itens do plano — somar dos dois lados contaria 237 em
  dobro so no comum do SEDES. As demais parcelas nao se sobrepoem por construcao: o
  status fica fora das pastas de `SECOES` e a secao herdada do `_COMUM` e ponteiro com
  `documentos: []`.
- **Barra ausente, vazia e desconhecida sao tres coisas**: some so quando o medido nao
  existe; vem vazia com o trilho a vista quando esta em zero (`0/48`, nunca `0/0`); vem
  hachurada e escrita quando e `vinculo_ausente`. Materia sem vinculo nunca entra no
  denominador agregado — falso zero em escala de escopo esconde o trabalho de uma
  materia inteira.
- **Tarefa e de quem guarda o arquivo; cobertura e de quem tem o edital**: a barra de
  tarefas da materia conta so os assuntos proprios (senao "aprofundado no comum" conta
  duas vezes), mas a materia emprestada entra sim na cobertura do cargo. E ela **tem aba
  Estudo**: os assuntos da irma entram em `assuntos_herdados`, chave a parte que a
  agregacao ignora — antes `tem_estudo` olhava so `assuntos` e tres materias do SEDES
  ficavam so com o Plano tendo 40%, 60% e 25% de cobertura.
- **Asset publicado leva a versao do conteudo na URL** (`site.css?v=<hash>`): o nginx
  manda `expires 1h`, entao sem isso o navegador serve **HTML novo com CSS velho** — e o
  defeito e invisivel, porque a pagina renderiza, so renderiza errado.
- **Nada escrito no topico do mapa se perde em silencio**: H3 fora do template e
  publicado com o texto do vault **e avisado** na geracao; rotulo repetido no mesmo
  topico acumula, nunca sobrescreve; e a lista exibida conta o mesmo que o contador
  do rodape (ha teste que trava o invariante).
- **Cobertura e contagem, nunca nota inventada**: a % de topicos aprofundados sai do
  `topico_id` gravado e as lacunas aparecem por nome; nota sintetica de qualidade foi
  descartada porque os sinais estao saturados no vault. Materia com assuntos sem vinculo
  tem cobertura DESCONHECIDA, nunca zero.
- **Arcabouco nao sobrescreve conteudo**: `build_subject_md.py` pula `.md` existente;
  regerar exige `--forcar`, com backup.
- **Nunca inferir o link mapa↔assunto por slug**: so ~18% dos topicos casam. Sem
  casamento exato a pagina nao afirma nada; o link fino vem de `mapa-aliases.json`.
- **Fixture tem de espelhar a saida real da skill anterior** — fixture que inventa o
  que o gerador nao produz e teste que se autoconfirma (foi assim com o bug do
  `_GERAL` e com a chave `notebooklm_url`).
- **Cores so via variaveis de tema** no CSS (nada de hex fixo para cor de texto);
  toda variavel precisa existir nos dois temas — ha teste que barra isso.
- **Deploy e sincronizacao, e por isso reconstroi o build inteiro**: bind mount + rsync,
  sem rebuild de imagem nem restart — isso nao muda. Mas o `--concurso-dir` nomeia UM
  concurso enquanto o envio e `rsync --delete` do `out/site/` inteiro, que acumula;
  construir so o pedido republicava os demais com o conteudo da sessao em que foram
  gerados, **sem aviso**. Hoje o deploy reconstroi **todos** os concursos do build antes
  de enviar, achando a origem no campo `origem` do `.concurso.json`; manifesto antigo sem
  o campo cai na pasta irma, **com o palpite ecoado**. Origem sumida = republicado como
  esta e **avisado duas vezes** (comeco e fim), nunca escolha silenciosa entre publicar
  velho e despublicar bom. `--so-este` pula os outros, avisando. E **nao** apague o
  `out/site/`: um build com um concurso so **remove os outros do servidor** — o diretorio
  e espelho do publicado, nao cache. Ver `scripts/tests/test_deploy.sh` e `deploy/README.md`.
- **Acrescentar fonte a um aprofundamento e renomear**: o id *e* o conjunto de fontes e
  o id *e* o path, entao `padrao--pestana` vira `padrao--pestana+rosenthal`. Quem faz e
  `ampliar_aprofundamento.py` (modos `ampliar`/`derivar`), que move primeiro e regenera
  o pacote depois — invertido, o `notebooklm_url` some em silencio. A ordem das fontes
  nunca e canonicalizada; fonte nova entra no fim.
- **Localizacao e por fonte, em chaves numeradas**: fonte 1 em `localizacao_livro`, as
  demais em `localizacao_2`, `localizacao_3`. Chave unica com `;` nao serve — os
  ponteiros reais contem `;` dentro deles. E metade dos valores do vault e prosa livre:
  quem quiser pagina tenta extrair e **degrada**, nunca exige o formato.
- **No modo em lote, o ponteiro vem do `--mapa`, nunca do `--localizacao`**: o mapa
  resolve a pagina POR ASSUNTO; um `--localizacao` unico gravaria a pagina certa de um
  assunto e errada de todos os outros.
- **Preservar trabalho do usuario**: re-execucoes nao apagam resumos, flashcards
  ou progresso; scripts que sobrescrevem artefatos fazem backup.

Ao evoluir uma skill: **plano antes de implementar** (o dono do repo aprova
planos e listas de gaps antes de qualquer codigo), teste que reproduz cada bug
corrigido, SemVer nos **tres** lugares que o CI confere (`SKILL.md`, `Versao atual:` do
`README.md` da skill e topo do `CHANGELOG.md`), e
higiene de pacote (sem `__pycache__`, sem orfaos) antes de fechar versao.

> Regras completas, estrutura de pastas e contexto de dominio: `CLAUDE.md` da
> raiz do repositorio — esta secao e um resumo, aquele arquivo e a fonte.
