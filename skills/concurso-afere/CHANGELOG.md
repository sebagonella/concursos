# Changelog — concurso-afere

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

## [0.1.0] - 2026-08-04

### Adicionado

- **Primeira versão.** Afere o material aprofundado do vault contra a prova real, com
  gabarito oficial. `--materia` aceita uma ou mais matérias; `--cargo` traz todas as
  aprofundadas do cargo, incluindo as do `_COMUM` — é como o candidato estuda.
- **Quatro vereditos**, e `SEM MATERIAL` **fora do denominador**: o tópico que nunca foi
  aprofundado é falha de *cobertura*, não de *profundidade*, e as ações corretivas são
  diferentes. Medido: Conhecimentos Bancários tem 15 assuntos para 24 tópicos do mapa —
  misturar as duas coisas puniria a qualidade do texto por uma lacuna de planejamento.
- **`prova_id.py` compara versão do caderno E cargo.** Cruzar a prova do Agente Comercial
  com o gabarito do Agente de Tecnologia devolve 10 respostas plausíveis e completamente
  erradas: os dois têm "GABARITO 4" e o de Tecnologia nem declara A/B/C.
- **A faixa de questões vem da tabela da capa** ("Língua Portuguesa … 1 a 10"), não de
  contagem no corpo — o texto de apoio numera parágrafos, e `\n3\n` casava com o
  parágrafo 3 em vez da questão 3.
- **Matérias descobertas pelo filesystem.** O `.meta.json` do SEDES tem
  `materias_por_cargo`; o do BB **não tem**.
- **`validar_afericao.py`** recusa veredicto em branco, amostra não declarada, superlativo
  com uma prova só e o mesmo número escrito de dois jeitos (39,4 × 39,45 — a comparação é
  em `Decimal`, porque em float a diferença dá 0.050000000000004 e escapa).

### Notas

- **Não recorta questão a questão.** Tentei: em PDF de duas colunas o texto de uma questão
  não é contíguo — na Prova A as questões 3 e 6 aparecem lado a lado. Entrega-se o bloco
  da matéria, com aviso quando alguma marca de questão não aparece nele.
- Os 20 testes que reproduzem bug foram conferidos contra o código ingênuo.
