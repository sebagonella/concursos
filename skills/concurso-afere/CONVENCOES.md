# Convenções invioláveis — `concurso-afere`

Regras que vieram de **bugs reais** neste repositório. Cada uma traz o número que a
originou, e é o número que impede a regressão: sem ele a regra vira opinião, e
opinião se "melhora" de volta ao defeito.

Moram aqui, e não no `CLAUDE.md` da raiz, porque só valem para esta skill — e o
raiz é carregado em todo turno de toda sessão, inclusive nas que não a tocam. O
índice de todas está em [`CLAUDE.md`](../../CLAUDE.md#por-skill).

> Se uma destas regras conflitar com o código, **o código venceu** e a regra virou
> defeito de documentação. Corrija os dois na mesma PR.

---

- **Aferir prova é casar VERSÃO e CARGO, ou falhar alto**: gabarito errado não dá erro — dá resposta plausível. A prova do Agente Comercial cruzada com o gabarito do Agente de Tecnologia devolve 10 respostas completamente erradas, porque os dois têm "GABARITO 4" e o de Tecnologia nem declara A/B/C. E a tabela do caderno 1 diverge da do 4 em **9 das 10** questões de Português: a versão do exemplar decide o gabarito inteiro.

- **Na aferição, `SEM MATERIAL` nunca vira nota baixa**: tópico que jamais foi aprofundado é falha de **cobertura**; assunto escrito que não cobre a questão é falha de **profundidade**. As ações são diferentes — escrever × aprofundar —, então o primeiro sai do denominador da nota. Conhecimentos Bancários tem 15 assuntos para 24 tópicos do mapa; misturar as duas coisas puniria o texto por uma lacuna de planejamento.

- **A conclusão não excede a amostra**: com **1** prova a aferição de Português concluiu "empate técnico" (9,0 × 9,2); com **3**, inverteu (9,67 × 8,77) e as 4 falhas do `detalhado` mostraram-se todas do mesmo tipo. O `provas_aferidas_n` vai no frontmatter e o validador barra superlativo sem ele.

- **Cobertura de tópico é tautológica quando o vault veio do mesmo edital da prova** — os assuntos saíram do programa que ela cobra, e 100% de aderência é aritmética, não validação. A ressalva é escrita **antes** dos números, pela própria skill, para não depender de alguém lembrar.

- **O `detalhado` não é superconjunto do `padrao`**: medido nos 9 assuntos de Português do BB, **22%** dos conceitos que o padrão declara cobrir não aparecem no detalhado (pior caso 44%, em compreensão de textos). Custou 4 das 30 questões aferidas, todas de coesão referencial. Enquanto os dois níveis forem gerados independentemente, isso se repete.

