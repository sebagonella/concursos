---
name: concurso-afere
version: 0.1.1
description: >
  Use quando o usuário tiver a PROVA REAL de um concurso (PDF do caderno + gabarito
  oficial) e quiser medir o material já aprofundado no vault contra ela — descobrindo
  quantas questões o conteúdo escrito responde, onde ele falha e o que corrigir. Afere
  UMA OU MAIS matérias específicas (`--materia`) ou TODAS as matérias aprofundadas de um
  cargo (`--cargo`), comparando os níveis `padrao` e `detalhado` quando os dois existem.
  Produz nota por nível, nota por prova, distribuição das questões por assunto e ações
  corretivas, salvos no vault junto do material medido. Triggers - "aferir o material
  contra a prova", "quantas questões o vault responde", "medir o aprofundamento com a
  prova real", "nota do material contra o gabarito", "analisar prova vs conteúdo",
  "comparar padrão e detalhado com a prova".
---

# concurso-afere

Quinta etapa do fluxo, e a única que olha para trás: mede se `concurso-prep`,
`concurso-aprofunda` e o que foi escrito à mão realmente respondem à prova.

## Pré-condições

1. Uma pasta de concurso com material aprofundado (`03-APROFUNDAMENTO/{materia}/assuntos/`).
2. **Prova + gabarito oficial** em PDF. A versão do caderno importa: ver abaixo.

## A divisão de trabalho (o ponto central)

| Script faz | Agente faz |
|---|---|
| identificar prova, caderno e cargo · extrair a faixa oficial de questões · ler o gabarito da versão certa · casar matéria da prova ↔ matéria do vault · medir divergência entre níveis · montar o arcabouço · validar aritmética e coerência | **mapear questão → assunto** · **declarar o conceito decisivo** · **dar o veredicto por nível** · escrever as ações |

O arcabouço sai com `···` onde o julgamento é necessário, e `validar_afericao.py`
**recusa** documento que ainda tenha o marcador. A skill nunca inventa nota — é o mesmo
desenho de `build_subject_md.py`, que monta o esqueleto e deixa o resumo para o agente.

## Parâmetros

| Parâmetro | Obrigatório | Default | Descrição |
|---|---|---|---|
| `concurso-dir` | sim | — | Pasta do concurso no vault |
| `prova` | sim | — | PDF do caderno. **Repetível**: uma vez por versão (A, B, C) |
| `gabarito` | não | irmão | Um por prova, na mesma ordem. Sem isso, procura `{prova}-gabarito.pdf` ao lado |
| **`materia`** | não¹ | — | **Uma ou mais** matérias. Aceita o nome da capa ou o `materia_id` |
| **`cargo`** | não¹ | — | **Todas** as matérias aprofundadas do cargo — as dele **mais** as do `_COMUM` |
| `bloco-out` | não | — | Grava o texto das questões, para o agente ler |
| `dry-run` | não | false | Mostra o que faria, sem escrever no vault |

¹ `materia` e `cargo` são mutuamente exclusivos. Sem nenhum dos dois, a skill **lista as
matérias aferíveis e sai** — nunca assume "todas" por omissão.

## Fluxo

```
1. Conferir o par prova/gabarito         scripts/prova_id.py
   - versão (A/B/C), caderno (1-4) e CARGO, lidos do CONTEÚDO, não do nome
   - divergência => exit 2. Não é preciosismo: cruzar a prova do Agente Comercial
     com o gabarito do Agente de Tecnologia devolve 10 respostas plausíveis e
     completamente erradas, sem erro nenhum na saída.

2. Descobrir matérias e faixas           scripts/extrair_questoes.py · casar_materias.py
   - a faixa ("1 a 10") vem da TABELA DA CAPA — é fato publicado pela banca
   - as matérias do vault vêm do FILESYSTEM (o .meta.json do BB não tem
     materias_por_cargo; depender dele quebraria em metade dos concursos)
   - sem casamento confiável, PERGUNTA. Nunca infere vínculo por slug.

3. Ler o gabarito da versão certa        scripts/gabarito.py
   - a tabela do caderno 1 e a do 4 divergem em 9 das 10 questões de Português

4. Medir divergência entre níveis        scripts/divergencia_niveis.py
   - só quando os dois níveis existem; caso contrário, declara que não há comparação

5. Montar o arcabouço                    scripts/build_afericao.py
   - --bloco-out grava as questões para o agente ler

6. JULGAR  [tarefa do AGENTE]
   Para cada questão: o assunto que ela cobra, o CONCEITO DECISIVO (o que separa a
   alternativa certa das erradas) e o veredicto por nível:

     ✅ RESPONDE (1,0) · ⚠️ PARCIAL (0,5) · ❌ NÃO RESPONDE (0,2) · ⬜ SEM MATERIAL

   ⬜ SEM MATERIAL sai do denominador: o tópico nunca foi aprofundado, e isso é falha
   de COBERTURA, não de PROFUNDIDADE. As ações são diferentes — escrever o assunto x
   aprofundar o assunto. Misturar as duas puniria a qualidade do texto por uma lacuna
   de planejamento.

7. Validar                               scripts/validar_afericao.py
   - veredicto em branco, nota sem amostra declarada, mesmo número com duas
     formatações, superlativo com uma prova só => falha
```

## Saída no vault

- **Por matéria**: `{concurso}/{escopo}/03-APROFUNDAMENTO/{materia}/00-AFERICAO-*.md` —
  fica onde a correção acontece, e o site a publica como documento da matéria.
- **Hub**: `{concurso}/_COMUM/05-HISTORICO-CONCURSO/00-AFERICOES.md` — responde "que
  provas já usei e o que cada uma mostrou", sem duplicar conteúdo.
- **PDFs**: `05-HISTORICO-CONCURSO/provas-anteriores/`, com a versão no nome
  (`...-a.pdf`, `...-a-gabarito.pdf`).

## Princípios

- **Versão do caderno e cargo casam, ou falha alto.** Gabarito errado não dá erro — dá
  resposta plausível, que é pior.
- **Cobertura é tautológica quando o vault veio do mesmo edital da prova.** A skill
  detecta `modo: previsto` e escreve a ressalva **antes** dos números, sozinha.
- **A conclusão não excede a amostra.** Com 1 prova a primeira aferição concluiu
  "empate técnico" (9,0 × 9,2); com 3, inverteu (9,67 × 8,77). O N vai no frontmatter e
  o validador barra superlativo sem ele.
- **O veredicto é do agente.** Script que julga é script que inventa nota.
- **Recorte cirúrgico por questão é precisão fingida.** Em PDF de duas colunas o texto
  de uma questão não é contíguo — entrega-se o bloco da matéria e o agente lê.
- **Varrer e não achar nada falha alto.**

## Scripts

- `prova_id.py` — versão, caderno e cargo pelo conteúdo; `conferir_par()` nomeia a divergência
- `extrair_questoes.py` — faixas pela tabela da capa; bloco da matéria com aviso quando falta questão
- `gabarito.py` — respostas do caderno e da seção certos; erro nomeia os cadernos disponíveis
- `casar_materias.py` — matéria da prova ↔ matéria do vault; `escopos_do_cargo()` traz `_COMUM` + cargo
- `divergencia_niveis.py` — % dos conceitos do `padrao` ausentes no `detalhado`
- `build_afericao.py` — arcabouço (não julga)
- `validar_afericao.py` — recusa aferição incompleta ou incoerente
- `tests/test_smoke.py` — 20 testes, standalone

**Reúso** (não reimplementar): `arquivo_principal()` da `concurso-aprofunda` —
`glob("*.md")[0]` pega o `_fonte-notebooklm.md`, porque `_` ordena antes das letras.
