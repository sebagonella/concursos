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

- **Na Quadrix, tipo não é prova**: os cadernos TIPO A, B e C trazem as **mesmas 60 questões** com os blocos em rodízio — no SEDES/DF 2026, Conhecimentos Gerais é 1–20 no A, 41–60 no B e 21–40 no C, com enunciado e letra idênticos. (E os blocos se repetem entre cargos, mas só dentro da carreira: Conhecimentos Gerais e Específicos Comuns têm uma versão para os 3 cargos TDAS e outra para os 12 EDAS; a Especialidade é própria de cada um dos 15. Medido no gabarito, que agrupa os blocos por resposta.) Na CESGRANRIO, A/B/C são provas **diferentes**, e foi por esse modelo que a skill nasceu: aferir dois tipos Quadrix contaria cada questão duas vezes e dobraria o `provas_aferidas_n` sem uma questão nova sequer. Por isso a Quadrix afere **um caderno por execução**, e o tipo — que nenhuma página imprime — é deduzido pela ordem dos blocos e conferido contra o gabarito, porque a seção do tipo errado devolve 60 respostas plausíveis e erradas.

- **Anulada sai do denominador e entra na amostra**: a banca a retirou, e ela não mede nada — mas foi aferida, e precisa ser contada em algum lugar, ou a soma das contagens deixa de fechar com `questoes_aferidas`. A Quadrix marca com `X` ("Item 37: anulado.", CRESS-MG 2024); a regex da CESGRANRIO só aceitava `[A-E]`, a questão sumia e o fallback estourava traceback. O veredicto `⊘` vem preenchido do gabarito — não é julgamento —, e a linha **Anuladas** só aparece quando há anulada.
