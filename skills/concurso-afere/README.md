# concurso-afere

Mede o material aprofundado do vault contra a **prova real**: quantas questões o
conteúdo escrito responde, onde falha e o que corrigir.

Versão atual: **0.6.0** — afere prova da **Quadrix**: gabarito em grade, tipos A/B/C como as mesmas questões em rodízio, divisão por área com o vínculo questão → matéria julgado pelo agente, e questão anulada fora do denominador. O histórico completo está no [CHANGELOG.md](CHANGELOG.md).

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

### Prova da Quadrix

A Quadrix divide a prova por **área** ("Conhecimentos Gerais, 1 a 20"), não por matéria, e
aplica cadernos TIPO A/B/C que são **as mesmas questões em rodízio de blocos**. Por isso o
fluxo tem duas etapas, com um mapa questão → matéria no meio, preenchido pelo agente:

```bash
V=~/vault/30_AREAS/CARREIRA/CONCURSOS/SEDES_2026
C=$V/_COMUM/05-HISTORICO-CONCURSO/provas-anteriores

# 1. o par é confiável? (cargo pelo rodapé, tipo pela ordem dos blocos)
python3 $S/prova_id.py $C/prova-sedes-2026-tdas-agente-social-tipo-a.pdf \
        $C/gabarito-preliminar-sedes-2026.pdf

# 2. áreas da prova e matérias candidatas do vault
python3 $S/build_afericao.py --concurso-dir $V --prova <caderno> --gabarito <gabarito>

# 3. esqueleto do mapa de UMA área (um caderno por execução)
python3 $S/build_afericao.py --concurso-dir $V --prova <caderno> --gabarito <gabarito> \
  --area "Conhecimentos Gerais" --mapa-out /tmp/mapa-cg.json --bloco-out /tmp/cg.txt

# 4. o AGENTE lê /tmp/cg.txt e preenche a matéria de cada questão no mapa

# 5. uma aferição por matéria, cada uma com as suas questões
python3 $S/build_afericao.py --concurso-dir $V --mapa /tmp/mapa-cg.json

# 6. quando sair o gabarito definitivo: o que rejulgar
python3 $S/comparar_gabaritos.py --antes <preliminar> --depois <definitivo> \
  --afericao $V/_COMUM/03-APROFUNDAMENTO/lingua-portuguesa/00-AFERICAO-*.md
```

## Vereditos

| | Peso | Significa |
|---|---:|---|
| ✅ RESPONDE | 1,0 | o material tem o conceito decisivo |
| ⚠️ PARCIAL | 0,5 | dá para chegar, sem o caso pronto |
| ❌ NÃO RESPONDE | 0,2 | o assunto existe e não cobre — falha de **profundidade** |
| ⬜ SEM MATERIAL | — | o tópico nunca foi aprofundado — falha de **cobertura** |
| ⊘ ANULADA | — | a banca retirou a questão; vem preenchido do gabarito e sai do denominador |

## Testes

```bash
python3 scripts/tests/test_smoke.py     # 52 testes, sem pytest
```

Documentação do fluxo completo: [`SKILL.md`](SKILL.md) · histórico: [`CHANGELOG.md`](CHANGELOG.md)
