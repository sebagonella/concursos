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

Ficam num lugar só: [`CLAUDE.md`](../CLAUDE.md) da raiz, que o Claude Code carrega
junto com este arquivo. As transversais estão lá na íntegra; as de uma skill só, no
`CONVENCOES.md` dela, indexadas em [Por skill](../CLAUDE.md#por-skill).

**Este arquivo deixou de resumi-las de propósito.** Ele era um resumo, e resumo
deriva: quando a `concurso-afere` nasceu, as cinco convenções dela entraram no raiz
e **nenhuma** aqui — o commit que criou a skill tocou `README.md`, `CLAUDE.md` e
`ARQUITETURA.md` e não este. Um resumo que perde uma skill inteira faz o leitor
concluir que a skill não tem regras. Hoje o CI barra isso (o guarda "toda skill
citada" inclui este arquivo), mas o conserto de raiz foi parar de duplicar: aqui
mora só o que é próprio deste diretório — paths do vault, ciclo de sessão, stack e
comandos.

Ao evoluir uma skill: **plano antes de implementar** (o dono do repo aprova planos e
listas de gaps antes de qualquer código), teste que reproduz cada bug corrigido e
**falha contra o código antigo**, SemVer nos três lugares que o CI confere, e higiene
de pacote antes de fechar versão. Detalhe em
[Ao evoluir uma skill](../CLAUDE.md#ao-evoluir-uma-skill).
