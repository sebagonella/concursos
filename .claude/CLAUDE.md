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
  saem a ordenacao das materias e os selos de questoes/prioridade).
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
- **Deploy e sincronizacao**: bind mount + rsync, sem rebuild nem restart. Nao
  introduzir passos de build no deploy. **Defeito conhecido:** o `deploy.sh` constroi
  so o concurso de `--concurso-dir` mas envia o `out/site/` inteiro com `--delete`, e
  esse diretorio acumula — concurso construido numa sessao anterior e republicado com
  o conteudo daquela data, **sem aviso**. Rode o deploy uma vez por concurso presente
  em `out/site/`, ou apague o diretorio antes. Ver `deploy/README.md`.
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
corrigido, SemVer no frontmatter do `SKILL.md` + entrada no `CHANGELOG.md`, e
higiene de pacote (sem `__pycache__`, sem orfaos) antes de fechar versao.

> Regras completas, estrutura de pastas e contexto de dominio: `CLAUDE.md` da
> raiz do repositorio — esta secao e um resumo, aquele arquivo e a fonte.
