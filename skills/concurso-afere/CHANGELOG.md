# Changelog — concurso-afere

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

## [0.2.0] - 2026-08-05

### Adicionado

- **O validador confere a aritmética da nota** — o check 2 que o docstring anunciava e que
  **nunca existiu no código**. Ele recalcula a nota a partir das contagens declaradas, pelo
  critério da própria skill (RESPONDE 1,0 · PARCIAL 0,5 · NÃO RESPONDE 0,2), e compara com a
  nota escrita **por nível**; e confere que `respondidas + parciais + não respondidas + sem
  material` fecha com `questoes_aferidas` do frontmatter. Sem ele, a aritmética da primeira
  aferição de Vendas e Negociação (13,0+13,2+13,2 = 39,4 e 39,4/45 = 8,76) foi conferida à mão.
- **`SEM MATERIAL` fica fora do denominador**, como manda o critério: 10 respondidas e 5 sem
  material dá **10,0**, não 6,7. Incluí-lo puniria o texto por uma lacuna de planejamento — e
  há teste travando isso.
- A mensagem **mostra a conta**: `35·1,0 + 8·0,5 + 2·0,2 = 39,4 sobre 45 dá 8,76, mas o
  documento diz 9,20`. Erro de aritmética sem a conta ao lado obriga a refazê-la para saber
  quem está errado.

### Notas

- **O check se cala onde não há contagem**, em vez de falhar alto. Onde não há números não há
  aritmética a conferir, e o documento incompleto já é pego pelo marcador `···` do check 1.
  Isso mantém o validador utilizável nas variações reais de formato — a tabela de Vendas e
  Negociação tem **uma** coluna de nível e uma linha `Sem material`; a de Língua Portuguesa
  tem **duas** colunas e nenhuma.
- Verificado contra os dois documentos reais do vault (passam) e contra cópias adulteradas na
  nota e numa contagem (pegos, com a conta na mensagem). 22 → 26 testes.

## [0.1.1] - 2026-08-05

### Corrigido

- **O check de formatação dupla passou a exigir relação de arredondamento, não
  proximidade.** O critério anterior (`|a − b| <= 0,05`) confundia duas coisas
  diferentes: *o mesmo número escrito de dois jeitos* — o defeito — e *dois números
  legitimamente vizinhos*. Numa matéria estável as notas por prova caem naturalmente a
  menos de 0,05 umas das outras, e a primeira aferição de **Vendas e Negociação** foi
  recusada inteira por trazer **8,76** (consolidado) e **8,80** (provas B e C), que são
  valores distintos, calculados em separado e ambos corretos. Agora só há defeito quando
  as **precisões diferem** e o menos preciso é um arredondamento válido do mais preciso.
  O par que originou a regra (**39,4 × 39,45**) continua sendo pego, e a mensagem passou
  a nomear qual número parece o arredondamento de qual.
- A comparação é por **desigualdade**, não por `round()`: 39,45 arredonda para 39,4
  (HALF_EVEN) ou 39,5 (HALF_UP), e os **dois** são o defeito — fixar um modo deixaria o
  outro passar. Segue em `Decimal` pelo motivo de sempre (em float, 39,45 − 39,4 dá
  0.050000000000004 e escaparia do limiar por epsilon).
- **O docstring do script dizia "39,4 numa tabela e 39,5 noutra"**, mas o incidente real
  — registrado neste changelog em 0.1.0 — foi **39,4 × 39,45**. A imprecisão importa:
  39,4 × 39,5 têm a *mesma* precisão e nunca foram pegos por regra nenhuma, nem pela
  antiga. Corrigido.

### Notas

- **Fica de fora, por construção:** dois valores de mesma precisão, por mais próximos que
  estejam (39,4 × 39,5). Não há como pegá-los sem recusar 13,0 × 13,2, que é legítimo e
  aparece na aferição de Vendas. Preferiu-se deixar passar o caso hipotético a recusar o
  caso real.
- O `validar_afericao.py` tem no docstring um check 2 ("notas por prova somam ao
  consolidado") que **não existe no código**. Não entra nesta correção: é gap separado e
  mais substantivo — implementado, teria conferido sozinho a aritmética de Vendas.

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
