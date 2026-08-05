# concurso-afere

Mede o material aprofundado do vault contra a **prova real**: quantas questões o
conteúdo escrito responde, onde falha e o que corrigir.

Versão atual: **0.1.1** (afere uma ou mais matérias (`--materia`) ou todas as matérias
aprofundadas de um cargo (`--cargo`), com nota por nível `padrao` e `detalhado`, nota por
prova e distribuição das questões por assunto; o script prepara o determinístico e **o
agente julga**, com quatro vereditos em que `SEM MATERIAL` fica fora do denominador —
falha de cobertura e falha de profundidade têm ações diferentes. Nesta versão, o check de
formatação dupla passou a exigir **relação de arredondamento** em vez de proximidade
absoluta: duas notas vizinhas de mesma precisão não são o mesmo número escrito duas vezes).

## Por que existe

Aferir à mão as três versões da prova do BB 2022/001 produziu cinco erros de manuseio —
nenhum de análise: varredura pegando o arquivo errado, quase cruzar prova com gabarito de
outro cargo, arredondamento inconsistente, texto residual contradizendo o documento e
diagnóstico feito na rota errada do site. Cada um virou uma guarda testada aqui.

## Uso

```bash
S=~/.claude/skills/concurso-afere/scripts
V=~/vault/30_AREAS/CARREIRA/CONCURSOS/BB_2027_PREVISTO
P=$V/_COMUM/05-HISTORICO-CONCURSO/provas-anteriores/prova-bb-2023-agente-comercial

# 1. o par prova/gabarito é confiável?
python3 $S/prova_id.py $P-a.pdf $P-a-gabarito.pdf

# 2. o que dá para aferir?
python3 $S/casar_materias.py --prova $P-a.pdf --concurso-dir $V --cargo AGENTE-COMERCIAL

# 3. arcabouço de uma matéria, com as três versões
python3 $S/build_afericao.py --concurso-dir $V \
  --prova $P-a.pdf --prova $P-b.pdf --prova $P-c.pdf \
  --materia "Língua Portuguesa" --bloco-out /tmp/questoes.txt

# 4. o AGENTE lê /tmp/questoes.txt e preenche os campos `···`

# 5. validar
python3 $S/validar_afericao.py --concurso-dir $V
```

## Vereditos

| | Peso | Significa |
|---|---:|---|
| ✅ RESPONDE | 1,0 | o material tem o conceito decisivo |
| ⚠️ PARCIAL | 0,5 | dá para chegar, sem o caso pronto |
| ❌ NÃO RESPONDE | 0,2 | o assunto existe e não cobre — falha de **profundidade** |
| ⬜ SEM MATERIAL | — | o tópico nunca foi aprofundado — falha de **cobertura** |

## Testes

```bash
python3 scripts/tests/test_smoke.py     # 20 testes, sem pytest
```

Documentação do fluxo completo: [`SKILL.md`](SKILL.md) · histórico: [`CHANGELOG.md`](CHANGELOG.md)
