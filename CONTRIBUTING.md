# Como contribuir

Este repositório é uma coleção de **skills do Claude Code**. Boa parte do trabalho é
feito *pelo* Claude, com revisão humana — e as regras abaixo existem porque o
histórico mostrou onde as coisas quebram.

O contexto operacional para o agente está em [`CLAUDE.md`](CLAUDE.md), que o Claude
Code carrega automaticamente. Este arquivo é o resumo para humanos; o GitHub o
oferece ao abrir uma PR, que é justamente o momento em que ele importa.

## O ciclo

1. **Plano antes de implementar.** O dono do repo revisa planos e listas de gaps
   antes de qualquer código. Apresente o plano e espere aprovação — vale para
   correção de bug também, quando ela muda comportamento.
2. **Branch a partir de `main`, sempre.** Mesmo quando a mudança toca o arquivo de
   uma PR ainda aberta. Já houve um caso em que duas PRs empilhadas foram mergeadas
   com **79 segundos** de diferença: o retarget automático do GitHub não pega essa
   janela, e o commit ficou em duas branches remotas e **fora da `main`**, que
   permaneceu numa versão anterior à do site já publicado.
3. **Um teste que reproduz o bug** — e que **falha contra o código antigo**. Confira
   isso de verdade (`git stash` no arquivo corrigido e rode a suíte). Teste que passa
   nos dois lados é decoração, e o repositório já teve defeitos verdes por anos
   porque o fixture inventava o que o gerador não produz.
4. **SemVer em três lugares**, que o CI compara entre si: frontmatter do `SKILL.md`,
   linha `Versão atual:` do `README.md` da skill e topo do `CHANGELOG.md`. Esquecer
   o README é o erro comum, porque ele não parece metadado.
5. **Higiene antes de fechar**: sem `__pycache__`, sem órfãos, sem nomes estranhos.

## Rodar os testes

```bash
bash scripts/test-all.sh              # tudo: 5 suítes Python + 2 de shell
python3 skills/<skill>/scripts/tests/test_smoke.py    # uma só, standalone
```

As suítes rodam **sem pytest** de propósito: o `install.sh` as executa logo depois de
copiar a skill, e depender de dependência externa quebraria a instalação de quem só
quer o modo manual.

## O que o CI confere

Além de rodar as suítes, o [`tests.yml`](.github/workflows/tests.yml) barra:

| Guarda | O que pega |
|---|---|
| Consistência de versões | os três lugares divergindo, ou `version:` ausente |
| Toda skill citada | skill nova que não entrou no README / CLAUDE / ARQUITETURA |
| Índice de convenções | regra num `CONVENCOES.md` que o índice do `CLAUDE.md` não lista |
| Links relativos | link ou **âncora** apontando para o que não existe |
| Diagrama sincronizado | o bloco ```mermaid do README divergindo do `.mmd` |
| Nome de pasta do vault | a pasta de histórico escrita sem o sufixo `-CONCURSO`, que é o nome real |
| `Versão atual` | a linha virando um segundo changelog (máx. 400 chars) |
| Sintaxe shell | `bash -n` em `scripts/*.sh`, `scripts/tests/*.sh` e `deploy/deploy.sh` |
| Higiene | `__pycache__` commitado, nome de arquivo com `{` ou `}` |
| Docker | `docker-compose.yml` que não parseia |

Um colaborador que edite o README e quebre o mermaid não tem como adivinhar por que
o CI reprovou — por isso a tabela está aqui.

## Convenções que não se negociam

As transversais estão em [`CLAUDE.md`](CLAUDE.md#valem-em-todo-o-repositório); as de
cada skill, no `CONVENCOES.md` dela, indexadas em
[Por skill](CLAUDE.md#por-skill). Todas vieram de bugs reais e trazem o número
medido que as originou — **o número é o que impede a regressão**, então não o remova
ao editar.

As duas que mais custaram, se você só for ler duas:

- **Preservar trabalho do usuário.** Nenhuma re-execução apaga resumo, flashcard ou
  progresso. O padrão é único: pula o existente, reporta no JSON (não só no stderr),
  e `--forcar` faz `.md.bak`. Uma auditoria achou quatro violações em quatro skills
  *depois* de a regra existir — ela não pega por analogia.
- **Nunca fingir precisão.** Localização de baixa confiança vira pendência
  explícita. Página inventada é pior que página ausente, porque a ausente avisa.

## Estrutura

O contrato de dados entre as skills — quem escreve cada campo e quem o lê — está em
[`docs/CONTRATO-DE-DADOS.md`](docs/CONTRATO-DE-DADOS.md). As decisões de projeto e o
porquê delas, em [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md).

Skill nova entra em `skills/<nome>/` com o mesmo formato (`SKILL.md` com frontmatter,
`scripts/` com testes, `assets/templates/`, `examples/`). O `install.sh` descobre
skills sozinho — não precisa editá-lo.
