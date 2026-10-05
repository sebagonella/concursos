# Revisão crítica: skills, agents, scripts e documentação — ponderações sobre o levantamento do Gemini

**Data:** 2026-10-04
**Autor:** Claude Code (Opus 5.5), para revisão do dono do repositório
**Escopo:** `concurso-prep` (skill + 5 subagents), `concurso-aprofunda`, `concurso-notebooklm`,
`concurso-afere`, scripts de raiz e documentação. **`concurso-publica` fora do escopo**, citada
só onde uma proposta a afeta.
**Documento avaliado:** `docs/REVISAO-ECOSSISTEMA-SKILLS-AGENTS-SCRIPTS-E-RECURSOS.md`
(Antigravity/Gemini, mesma data), e a nota-espelho no vault.
**Status:** proposta — nada aqui foi implementado. Segue a regra do repositório: plano e
lista de gaps passam pelo dono antes de qualquer código.

---

## 0. Em uma página

1. **O Gemini acerta três fatos de código** — `fetch_lei.py` achata dispositivo revogado,
   `fetch_pdf.py` se anuncia como bot, `extract_edital.py` não tem OCR — **e acerta o
   sintoma central**: o material não é usado (177 baralhos, zero revisões).
2. **Mas erra o centro de gravidade.** Propõe sobretudo *recursos novos* (radar de
   súmulas, simulado no padrão Cebraspe, embeddings, Mermaid/Canvas). Os números do vault
   dizem que o gargalo não é falta de recurso: é que **nada do que já existe fecha o laço
   com o candidato**, e que **o ativo mais valioso já coletado — 12 provas reais, 11 com
   gabarito — não alimenta nada**.
3. **Há erros factuais e de método** no levantamento: "só 2-3 questões comentadas" (o real
   tem 6; o "2-3" vem do prompt de *vídeo*); `extrair_questoes.py` "não trata duas
   colunas" (trata, de propósito); `FRACAO_INUTIL` "descarta" (rebaixa para pendência);
   "66 assuntos em conhecimentos bancários" (são 15); estatísticas sem fonte ("60% letra
   de lei, 30% jurisprudência"); propostas desenhadas para o **Cebraspe** quando os dois
   concursos reais são **Quadrix** e **Cesgranrio**.
4. **Duas propostas colidem com decisões já tomadas.** O `install.sh --gemini` escreveria
   num arquivo que o `bootstrap-home.sh` do toolkit **regrava inteiro**; e o
   `CADERNO-DE-ERROS.md` no vault contraria a direção decidida em 29/09 e mantida pela
   ADR-007 da suíte (03/10): dado individual de estudo mora no app (perfil A), não no vault. A `remediar_afericao.py` "que injeta correções" viola
   "o agente julga" e reintroduz a **circularidade** que o próprio vault já documentou.
5. **O que o levantamento não viu é mais grave do que o que viu:**
   - a `concurso-afere` **só lê prova Cesgranrio/BB** — o SEDES, cuja prova real foi em
     **06/09/2026**, não pode ser aferido;
   - o gerador de flashcards usa **`??`, que neste vault é o separador _reverso_**: os
     2.836 cartões viram ~5,7 mil revisões, metade delas inúteis;
   - **nada confere o conteúdo escrito pelo agente** (citação existe na página? é curta?
     o `detalhado` cobre o `padrao`? — medido: 22% dos conceitos do padrão faltam no
     detalhado);
   - **promessas do `SKILL.md` sem executor** (idempotência por hash, migração V1→V2
     "automática", "cronograma termina antes da prova", `config.yml` que nenhum script lê);
   - os subagents chamam `scripts/…` por **caminho relativo** — causa provável de os
     downloads reais terem sido feitos via `curl`, à margem dos scripts.
6. **Proposta de rumo** (seção 5): **Fase 0** parar de ensinar errado (leis revogadas,
   cartões reversos, bugs que queimam quota) → **Fase 1** usar o que já foi coletado
   (afere multi-banca, aferir o SEDES, banco de questões reais vinculado a assunto,
   incidência por tópico) → **Fase 2** medir o candidato, na suíte, como a ADR-007 decidiu →
   **Fase 3** recursos novos com recorte (discursiva parametrizada pela banca, vigência de
   lei, recursos contra gabarito, revisão cruzada entre modelos).

---

## 1. Método e limites

- **Leitura direta** de README, ARQUITETURA, CONTRATO-DE-DADOS, CONTRIBUTING, SETUP-VAULT,
  `CLAUDE.md`, `install.sh`, `test-all.sh`, CI, os `SKILL.md`, os `CONVENCOES.md` e o plano
  da suíte (`docs/PLANO-BACKEND-SUITE-E-ESTUDO-INDIVIDUALIZADO.md`) com a ADR de 2026-09-29 e a
  **ADR-007 da nella-suite (2026-10-03)**, que a substituiu: mantém a direção (backend próprio e
  estudo individual, em perfil A), revisa o desenho e põe o pipeline do vault — este repositório —
  na "trilha C", com só o contrato do bundle entrando na especificação da suíte.
- **Quatro auditorias paralelas, só leitura**, uma por frente (prep+agents; aprofunda;
  afere+notebooklm; dados reais do vault), cada achado com `arquivo:linha`. Os achados que
  sustentam conclusões fortes foram **reconferidos à mão** (marcados abaixo com ✔).
- **Dados reais** dos dois concursos do vault (`SEDES_2026`, `BB_2027_PREVISTO`) medidos com
  `find`/`grep`/`wc`, sem escrever nada.
- **Não verificado:** HTML vivo do Planalto (sem acesso à rede nesta revisão), base do Anki,
  logs de acesso do site, se as citações do vault existem de fato nas páginas dos livros,
  comportamento de WAF de bancas, e o desempenho real do candidato na prova do SEDES.

---

## 2. O retrato: gerar × usar

| | SEDES_2026 | BB_2027_PREVISTO |
|---|---|---|
| Modo / banca | oficial · **Instituto Quadrix** · prova em **06/09/2026 (já ocorreu)** | previsto · **Fundação Cesgranrio** |
| Mapas de matéria (tópicos H2) | 9 (91) | 10 (161) |
| Aprofundamentos (padrão / detalhado) | 121 (109 / 12, detalhado só em LP) | 56 (47 / 9, detalhado só em LP) |
| Matérias aprofundadas | 7 no comum + 1 de cargo; 2 cargos sem nada próprio | **3 de 10** |
| Flashcards: baralhos / cartões / revisões | 121 / 1.704 / **0** | 56 / 1.132 / **0** |
| Checkboxes marcados nos mapas | **0 / 715** | **0 / 1.046** |
| Aferições contra prova real | **0** | 4 (LP e Vendas, 2 rodadas cada) |
| Pacotes NotebookLM executados | 7 / 121 | 9 / 56 |
| Provas reais no vault (com gabarito) | 4 (3) | 8 (8) |
| Provas usadas para alguma coisa | **0** | 3 (só para aferir) |

Os números somados contam a história: **~341 mil palavras escritas, 2.836 cartões, 177
roteiros de NotebookLM — e nenhum sinal de uso pelo candidato**: 0 revisões espaçadas,
0 de 1.761 checkboxes, 0 treinos de discursiva registrados (o guia do SEDES calendarizou 8,
entre 04 e 29/08), 0 simulados, 0 erros catalogados. O único ciclo de qualidade que rodou foi
**material × prova**, só no BB, conduzido pelo agente. A prova do concurso com data real
passou sem aferição e sem registro de resultado.

E a cobertura **não segue o peso da prova**: no BB, Tecnologia da Informação vale 35 de 70
questões do Agente de Tecnologia e tem **zero** assuntos aprofundados — enquanto Vendas foi
aferida duas vezes. As três provas de sinergia baixadas para o BB são, justamente, de TI.

> **Consequência para a revisão:** todo recurso proposto deve ser julgado por uma pergunta —
> *isto faz o candidato praticar, ou mede o que ele sabe?* Gerar mais material com a mesma
> taxa de uso zero não muda a nota de ninguém.

---

## 3. Avaliação do levantamento do Gemini

### 3.1 Onde ele acerta

| Afirmação | Evidência |
|---|---|
| `fetch_lei.py` achata dispositivo revogado | ✔ O `_TextExtractor` não trata `<strike>`/`<s>`/`<del>` (`fetch_lei.py:71-95`). No vault, a LGPD tem o **Art. 55-A seis vezes**, com redações contraditórias (`lei-13709-2018-lgpd.md:1341,1619,1649,1656,1661,1670`), e incisos duplicados aparecem na Lei 9.613 (14) e na 12.846. **O Gemini subestimou**: não é risco, é material errado já em uso. |
| `fetch_pdf.py` com User-Agent de bot | ✔ `ConcursoPrepBot/1.0; +https://example.com/bot` (`fetch_pdf.py:22`); o `fetch_lei.py:38` também. (Mas ver 3.2 — trocar o UA não resolve os bloqueios reais.) |
| `extract_edital.py` sem OCR | ✔ Só `pdftotext` (`extract_edital.py:20`); PDF-imagem sai com `OK: 0 chars` e código 0. A documentação promete que "sem OCR o PDF escaneado vira pendência" — na `concurso-prep`, nada cumpre. |
| Flashcards sem uso | ✔ 177 baralhos, 0 marcadores `<!--SR:` no vault inteiro (o plugin está com `dataStore: NOTES`). |
| Ciclo da aferição depende de trabalho manual | Correto como descrição; a solução proposta é que está errada (3.2). |
| Mapa mental fora da automação | Correto e já documentado na ARQUITETURA, com a razão. |
| Discursiva sem correção nem espelho | Correto em parte: o guia existe e é razoável (13 seções, critérios, banco de temas, régua), mas não há treino, correção nem espelho. |

### 3.2 Onde ele erra ou exagera

| Afirmação do Gemini | Veredito | Por quê |
|---|---|---|
| "No `detalhado`, apenas 2 a 3 questões" | **Incorreto** | O "2-3 exemplos" é do **prompt de vídeo** (`notebooklm_pack.py:252`). O `SKILL.md:338-339` exige comentar cada alternativa; o detalhado de crase do BB tem **6** questões, duas reais citadas com página. O gap verdadeiro é outro: **88% dos aprofundamentos são `padrao`, cujo template não tem seção de questões**, e as do detalhado são majoritariamente inventadas "estilo banca". |
| `extrair_questoes.py` falha com duas colunas e texto-base compartilhado | **Incorreto** | O corpo é lido **sem** `-layout` de propósito (`extrair_questoes.py:4-8,129`), e o recorte por questão foi recusado como precisão fingida: o agente recebe o bloco da matéria inteiro, com o texto-base. Os limites reais são outros (3.3, A1-A5). |
| `FRACAO_INUTIL` "descarta" a localização | **Incorreto** | Rebaixa para `baixa` e vira pendência (`book_index.py:47-66`) — é a proteção, não a falha. |
| `book_index` precisa de busca semântica | **Premissa falsa** | ✔ Nenhum dos 9 `mapa-localizacao*.json` do vault usa `toc` ou `densidade`, os únicos métodos que o script emite. Todos foram localizados pelo agente lendo o livro (`ancora-capitulo`, `mapeamento por artigo`, `leitura verificada`). Embeddings consertariam uma peça que o fluxo real já contorna. |
| "Desbalanceamento teoria × jurisprudência" | **Exagerado para o uso real** | Os templates de fato não têm seção de súmula. Mas as matérias aprofundadas são SUAS, legislação do DF, Português, Conhecimentos Bancários e Vendas; só 3-7 dos 177 arquivos citam STF/STJ. O gap real é **letra da lei e vigência**, não súmula. |
| "66 assuntos em conhecimentos-bancarios" estourando quota | **Incorreto** | São 15. O "66" é exemplo do `SKILL.md:47` da notebooklm. |
| Rotação de contas para a quota do NotebookLM | **Não recomendado** | A quota já é `exit 4` retomável por tipo (`executor.py:59-69`). Rotacionar contas para contornar quota tende a violar os termos do Google e multiplica a exposição — cada credencial dá acesso à conta inteira. |
| UA de bot causa os 403 | **Diagnóstico errado** | Os bloqueios registrados no vault (bb.com.br) foram de bot-gate em JavaScript, em downloads feitos **via `curl`** — nenhum agente chama `fetch_pdf.py` (3.3, F). Trocar a string não resolveria. |
| Tabelas multi-coluna quebram com `-layout` | **Parcial / invertido** | `-layout` costuma ser o *melhor* modo para tabela; o risco é texto corrido em colunas de Diário Oficial. Pior, e não visto: no DOCX, `extract_docx` lê só `doc.paragraphs` (`extract_edital.py:44`) e **descarta todas as tabelas** — vagas, provas e pesos. |
| Subagents "acoplados ao Claude Code" | **Parcial** | O frontmatter `tools:` é do Claude Code, sim. O defeito concreto, que quebra **até no Claude Code**, é o caminho relativo (`material-collector.md:142`, `edital-parser.md:146`) — ver 3.3, F. |
| `install.sh --gemini` registrando em `~/.gemini/config/skills.json` | **Conflita com o ambiente** | ✔ Esse arquivo é **gerado** pelo `bootstrap-home.sh` do toolkit do vault, que o compara com uma string esperada e o **regrava inteiro** (`bootstrap-home.sh:94-102`). Uma entrada escrita pelo `install.sh` sumiria na próxima execução do bootstrap — e a ADR-007 da suíte fixou a mesma regra para o `agy-bootstrap` ("sem reescrever o `skills.json` do toolkit"). O ambiente já tem o padrão certo: `.agents/skills.json` **relativo** no workspace e `.agents/agents/<nome>/agent.md` com frontmatter do Antigravity e corpo espelhado, conferido por diff (é como o vault faz com o `privacy-reviewer`). |
| Mermaid/Canvas como substituto do mapa mental | **Baixo valor agora** | O site roda offline, sem CDN, e **não renderiza Mermaid** (nenhuma ocorrência na `concurso-publica`); o app da suíte precisaria de renderizador. O vault já tem 11 mapas feitos à mão. |
| "60% das questões jurídicas cobram letra da lei e 30% jurisprudência"; "predileção absoluta por leis alteradas nos últimos 24 meses" | **Sem fonte** | Números sem origem num repositório cuja regra é "o número medido impede a regressão". Não devem guiar priorização. |

### 3.3 Problemas de método

- **Genérico em vez de situado.** O simulado proposto aplica "1 erro anula 1 acerto" e a
  correção da discursiva usa a fórmula do Cebraspe. O SEDES é **Quadrix**, com redação de
  20-30 linhas e critérios **CAC 7 · OT 1,5 · DLP 1,5** já gravados no `.meta.json`; o BB é
  **Cesgranrio**, múltipla escolha de 5 alternativas, sem penalidade. Nenhuma das duas
  regras se aplica aos concursos reais.
- **Contradiz a decisão anterior do próprio ciclo.** A ADR de 2026-09-29 decidiu que
  progresso, revisão espaçada e anotações são **individuais por usuário e não tocam o
  vault** (escrever de volta no Obsidian foi descartado explicitamente), e a ADR-007, que a
  substituiu, manteve isso: o perfil A existe justamente porque "estudo individual exige gravar
  dado por pessoa". O `CADERNO-DE-ERROS.md` por matéria no vault e a "folha de respostas" violam
  essa decisão.
- **Remediação que injeta texto.** "Script que injeta `> 🎯 Correção Pós-Aferição` e
  acrescenta cartões com o conceito decisivo da questão" (a) põe script redigindo conteúdo —
  contra "o agente julga" (`concurso-afere/SKILL.md:110`); (b) escreve no `.md` curado sem o
  padrão pula/reporta/`--forcar`+`.bak`; (c) **ensina para a prova**: o vault já registrou que,
  depois de usadas para escrever, as provas A/B/C "medem memória, não profundidade", e reservou
  a de 2021. A versão do plano de 29/09 (marcar `status: revisar` + tag + pacote para o
  `--modo ampliar`) é melhor, mas também tem um problema: o `status:` do assunto já é usado
  para estado **editorial** (175 de 177 estão `revisar`), não de estudo — usá-lo para lacuna de
  aferição sobrecarrega o mesmo campo com um terceiro sentido.
- **Retórica acima da medida** ("estado de arte pedagógico", "nota máxima na lista de
  aprovados"). O repositório tem uma cultura deliberada de afirmar só o que mediu; um
  levantamento que a ignora é mais difícil de usar como base de decisão.

### 3.4 Os sete recursos propostos, um a um

| # | Recurso (Gemini) | Vale? | Ajuste necessário | Onde mora |
|---|---|---|---|---|
| 1 | Radar de legislação e jurisprudência | **Parte sim** | Começar pelo barato e urgente: revogação correta no `fetch_lei` + **vigência** (rebaixar, comparar hash, avisar "lei mudou"). Súmulas só quando houver concurso jurídico no vault. | vault (prep) |
| 2 | Discursiva (temas, espelho, correção) | **Sim, com recorte** | Parametrizar por **gênero e critérios do edital** (já no `.meta.json`), não por fórmula de banca fixa. A correção pelo agente é *feedback*, nunca "nota oficial". Os textos do candidato e o histórico são dado individual → suíte. | conteúdo no vault; treino na suíte |
| 3 | Simulados calibrados | **Sim, depois do banco de questões** | Sem questões reais vinculadas e sem pesos/eliminação no schema, o simulado não tem matéria-prima nem regra de nota. A montagem (matriz do edital) é determinística → script; a resolução e a nota do candidato → suíte. | spec no vault; execução na suíte |
| 4 | Caderno de erros com metacognição | **Sim — é o recurso certo** | Na **suíte**, não no vault (ADR-007, perfil A). A causa do erro (`TEORIA`/`PEGADINHA`/`LEITURA`/`DECOREBA`) é **declarada pela pessoa**, com ajuda do agente, nunca inferida por script. | suíte |
| 5 | Mapas mentais Mermaid/Canvas | **Adiar** | Não renderiza no site nem na suíte sem trabalho extra; há mapas manuais. | — |
| 6 | Busca semântica no `book_index` | **Não** | O fluxo real não usa a saída do `book_index` (3.2). Melhorias baratas sem dependência pesada estão em 5, item 1.6. | — |
| 7 | `remediar_afericao.py` | **Sim, reformulado** | Não injeta nada: a aferição passa a ter uma **tabela estruturada de ações** (assunto como wikilink, nível, o que falta, questões), e um script **determinístico** lista pendências e confere se o assunto mudou depois da aferição. Quem escreve continua sendo o agente, pelo `--modo ampliar`. | vault (afere + aprofunda) |

---

## 4. O que o levantamento não viu

### 4.1 A medição: `concurso-afere` presa a uma banca

- ✔ **Só funciona com prova Cesgranrio/BB.** Cargos reconhecidos são os do BB
  (`prova_id.py:57-61`); o caderno é identificado por "GABARITO [1-4]"; o gabarito tem de estar
  no formato `N - X` (`gabarito.py:60`). Rodado contra a prova Quadrix do CRESS-RS que está no
  vault do SEDES, `prova_id.py` sai com `exit 2`. O gabarito Quadrix é uma **grade** (linha de
  números, linha de letras). **O concurso com prova real já aplicada é exatamente o que não pode
  ser aferido.**
- **Anulada não existe.** A Quadrix marca com `X`; a regex só aceita `[A-E]`; a questão some,
  e no fallback o erro estoura sem `try` (`build_afericao.py:108`).
- **Prova com 100+ questões não é lida** (`\d{1,2}` em `gabarito.py:60`, `extrair_questoes.py:192`,
  `prova_id.py:97`).
- ✔ **Peso do chute fixo em 0,2** (`validar_afericao.py:53`), que supõe 5 alternativas. Em
  Certo/Errado com penalidade o valor esperado é 0; sem penalidade, 0,5. A nota fica
  incomparável entre bancas.
- **Preliminar × definitivo** não se distinguem (`gabarito_fonte` é texto fixo).
- **O validador não confere a tabela por questão** contra as contagens do Resultado, nem que o
  "Assunto cobrado" exista (é texto livre, não wikilink).
- **Matéria descartada em silêncio** no modo `--cargo` abaixo do limiar de Jaccard 0,62
  (`casar_materias.py:29`, `build_afericao.py:251,265`) — o oposto do "sem casamento, pergunta"
  do próprio `SKILL.md:65`.
- **A prova "gasta" não virou convenção.** A lição mais cara do vault — reaferir contra as mesmas
  provas usadas para escrever é circular — mora só em prosa, na nota da rodada 2. Pela regra do
  repo, lição vira número, convenção e teste.

### 4.2 Ativos ociosos: as provas reais

- **12 provas reais e 11 gabaritos** em `05-HISTORICO-CONCURSO/` e `06-SINERGIA/`. Nenhum mapa,
  nenhum assunto e nenhum script da `concurso-aprofunda` as referencia (grep: 0). Só 3 foram usadas
  — para aferir, não para estudar.
- **599 itens de "pegadinha da banca" nos 19 mapas, 0 citando questão ou prova.** Saem de 1-2
  buscas genéricas (`materia-mapper.md:43-52`). É o "nunca fingir precisão" aplicado ao conteúdo:
  pegadinha sem lastro é opinião com cara de dado.
- **Consumidor antes do produtor, de novo.** Os mapas são a Etapa 6; histórico e sinergia, as 7 e 8.
  O mapper estima questões "por comparação com concursos similares" (`materia-mapper.md:59`) antes
  de as provas similares terem sido baixadas — o mesmo defeito que a 1.x corrigiu para os materiais
  (`concurso-prep/SKILL.md:260-268`), agora com as provas.
- **Incidência por tópico não existe.** A prioridade dos tópicos não tem base estatística.

### 4.3 Integridade do conteúdo: ninguém confere o que o agente escreve

- `validar_assuntos.py` cobra uma seção e contagens do frontmatter. **Ninguém confere** se a
  citação existe na página citada, se é "curta" (o Modelo 2 não tem número: `SKILL.md:326-327`),
  ou se o tamanho bate com o nível. O `SKILL.md` também não diz **como** ler as páginas.
- ✔ **O `detalhado` não é superconjunto do `padrao`**: 22% dos conceitos que o padrão declara não
  aparecem no detalhado (pior caso 44%); custou 4 de 30 questões aferidas
  ([`concurso-afere/CONVENCOES.md`](../skills/concurso-afere/CONVENCOES.md)). A convenção registra
  o defeito mas não há mecanismo que o impeça.
- **Páginas em dois sistemas de numeração**: o sumário devolve a impressa, a densidade devolve o
  índice do PDF (`book_index.py:193,247` × `:266`), sem detecção de deslocamento. O vault teve de
  anotar à mão "números referem-se à página do PDF".
- **Revisão humana nunca aconteceu**: 175 de 177 aprofundamentos estão `status: revisar`, nenhum
  `concluido`. Numa amostra, uma questão comentada afirma "duas estão erradas" e em seguida
  admite que uma delas é "discutível"; e um assunto do BB fala em "peculiaridade da Quadrix"
  (resíduo do SEDES). Pequenos, mas mostram que o texto não passa por segunda leitura.
- **O investimento foi para a infraestrutura de nomes.** O CHANGELOG da aprofunda tem ~55 itens,
  quase todos sobre identidade, renomeação e pacotes; nenhum sobre correção do conteúdo.

### 4.4 Legislação

- Além do revogado achatado (3.1): o bug do `_SKIP` (`meta`/`link`) que esvaziou ou truncou o MD de
  5 normas foi registrado em 15/07 como "contornado" e **continua no código** (`fetch_lei.py:71`).
- O SEDES tem **38 leis em PDF e 0 em `.md`**, contra a convenção MD+PDF.
- **Sem vigência**: só `baixado_em` (`fetch_lei.py:125`). E o `material-collector.md:210` manda
  "preferir versão simples" em vez da compilada — o que pode levar ao texto **original**,
  desatualizado. (O CDC baixado da URL `compilado` saiu sem duplicatas — indício, não verificado.)
- O `reuse_finder.py` não confere versão da norma: um resumo de lei alterada entre dois concursos
  seria reaproveitado sem aviso.
- **Zero testes** em `fetch_lei`, `fetch_pdf` e `extract_edital`. Um fixture HTML com `<strike>`
  teria pegado o caso da LGPD.

### 4.5 Flashcards

- ✔ **`??` é o separador reverso** neste vault (`multilineReversedCardSeparator = '??'`;
  o comum é `?`). O docstring do gerador sabe (`flashcards_gen.py:66-67`: "Gera cartão reverso"),
  a [`CONVENCOES.md`](../skills/concurso-aprofunda/CONVENCOES.md) descreve `??` só como "o formato
  multi-linha". Efeito: cada cartão vira dois, e o reverso de "prazo → 30 dias" ou de uma resposta
  de parágrafo é um cartão sem valor. **Janela de correção é agora**: com zero histórico de revisão,
  trocar não custa nada — e o `export_bundle` da suíte vai precisar saber quantos cartões existem.
- Sem **cloze**, o formato útil para lei seca; CSV do Anki sem diretivas de cabeçalho.

### 4.6 Promessas do `SKILL.md` sem executor (`concurso-prep`)

| Promessa | Realidade |
|---|---|
| Idempotência comparando hashes por arquivo (`SKILL.md:565-567`) | Nenhum script grava hash por arquivo; o único é o `edital_hash`. |
| Migração V1→V2 "a skill faz isso automaticamente" (`SKILL.md:98`; `config.yml:44`) | Não há script. |
| `validate_output` checa "cronograma termina antes da prova" (`SKILL.md:404`) | Só checa se `prova_data` é válida e futura (`validate_output.py:584-602`). |
| Limiares de fase, metas, whitelist de fontes (`config.yml`) | **Nenhum script lê o `config.yml`** ✔. `log_helper download-suspeito` existe e ninguém o chama. |
| `check_pdfs` valida os PDFs | Só o cabeçalho `%PDF-`: a prova escaneada do SEDES (11 páginas de imagem, 264 caracteres) passa. |

A aritmética do cronograma (dias, fases, percentuais) também fica com o modelo — a mesma classe de
defeito "duas execuções, dois formatos" que o CHANGELOG da prep registra várias vezes. Cerca de 1,9
mil das ~5 mil linhas de `scripts/` são migração pontual; o caminho principal não tem script.

### 4.7 Subagents e contratos divergentes

- ✔ **Caminhos relativos** (`python scripts/fetch_lei.py` em `material-collector.md:142`): os agents
  são copiados para `.claude/agents/` sem reescrita (`install.sh`) e rodam com o vault como CWD.
  Coerente com os downloads do vault terem sido feitos via `curl`.
- ✔ O `edital-parser` roda `pdftotext -layout` direto (`edital-parser.md:26`), **sem passar pelo
  `extract_edital.py`** — um OCR posto no script não seria usado.
- Formato inline do mapa no `materia-mapper.md:112-172` diverge do `mapa-materia.md.tpl`;
  prioridade "🟢 Baixa" no agent × `base` no contrato.
- Entradas da Etapa 8: o `SKILL.md` passa banca e matérias; o `sinergia-finder` espera pesos, cargo
  e `output_dir`. O `historico-researcher` aceita sites de cursinho; a sinergia os proíbe.
- Descrições velhas no `schema-edital.json` (mapper "sem ferramenta de leitura"; "Etapa 5 roteia").

### 4.8 O schema não guarda o que decide a nota

O `schema-edital.json:53-76` só exige `total_questoes`, `discursiva.presente` e `titulos.presente`.
Pesos por bloco, nota mínima/eliminação e critérios da discursiva existem no `.meta.json` do SEDES
**como extras**, sem garantia de que uma nova execução os grave, e fora do diff estrutural. No BB,
`estrutura_prova_por_cargo` é `null`: o meta descreve um cargo só. **Sem isso não há simulado com
nota líquida, nem relatório de cobertura por peso.**

### 4.9 NotebookLM

- **Retomar queima quota.** A mensagem de quota manda repetir o comando; o `planejar()` só olha o
  disco e ignora o sidecar (`plano.py:105-149`); o `executar()` substitui a tarefa do mesmo tipo
  (`executor.py:168-171`). A mídia em geração é pedida de novo e a anterior fica órfã. Sem teste.
- Cria **notebook duplicado** para pacote com zero tarefas (`nlm_run.py:128-131`).
- "Desiste após 6 h" é medido em **dias** × 24 (`executor.py:198`).
- Sem filtro por prioridade: 161 de 177 pacotes nunca rodaram e não há dado de que os 17 podcasts
  foram ouvidos. Escalar a geração é aposta.
- Falta guarda que recuse `NOTEBOOKLM_HOME` dentro do vault (sincroniza com o Drive).

### 4.10 Bugs pontuais

- `validar_assuntos.py --corrigir` **duplica** a seção "Para estudar depois" em assunto que só tinha
  incoerência de `fontes:` (`:176-186`), e sai 0; a ajuda diz `.bak.md`, o código grava `.md.bak`.
- EPUB: arquivos ordenados alfabeticamente, não pela ordem de leitura que a docstring promete
  (`book_index.py:126` × `:151-152`). OCR só dispara com menos de 200 caracteres no livro inteiro.
- Templates da prep com links para arquivos que nenhuma etapa gera (`rotina-diaria`,
  `metas-quantitativas`), caminhos relativos errados e chave `status:` duplicada
  (`cronograma-relativo.md.tpl:5,8`) — escondidos porque o validador resolve wikilink só pelo nome.

### 4.11 Documentação

- **Numeração das etapas inconsistente**: "três etapas" seguidas de cinco itens (`CLAUDE.md`,
  ARQUITETURA); a notebooklm é "3+" na tabela e "Etapa 4" nos pré-requisitos; a afere é "Etapa 5".
- **SETUP-VAULT manda instalar global** (`bash scripts/install.sh`, caminhos `~/.claude/skills/…`),
  contra a forma de instalar adotada aqui (`--local`).
- As convenções da `concurso-notebooklm` (`SKILL.md:125-141`) não estão no índice "Por skill".
- `concurso-afere/SKILL.md` omite `--escopo`, `--out` e `--forcar`; o README dela tem um parágrafo
  órfão; `CONVENCOES.md:35` da aprofunda cita linhas do `book_index` que mudaram.
- **A documentação não reflete a ADR-007** (que substituiu a de 29/09): README e ARQUITETURA ainda
  apresentam o site estático como destino final, sem dizer que ele segue no ar só até o cutover
  para o app da suíte. E o plano da suíte e o levantamento do Gemini estão
  **fora do git** (não rastreados).
- O Gemini sugere um "guia de estudo de alto rendimento". Concordo com a lacuna, mas o lugar é a
  suíte (onde o estudo acontece), não mais um documento no repo das skills.

---

## 5. Evoluções propostas

Princípios: **usar o que já existe antes de criar**; respeitar as convenções (o agente julga,
preservar trabalho, nunca fingir precisão, número medido); **conteúdo canônico no vault, dado
individual na suíte** (ADR-007, que substituiu a de 29/09).

### Fase 0 — Parar de ensinar errado (custo baixo, dias)

| # | Item | Por quê | Pronto quando |
|---|---|---|---|
| 0.1 | `fetch_lei`: revogado vira `~~…~~` ou bloco "redação anterior", última redação destacada, preferir URL compilada; corrigir o `_SKIP`; **rebaixar as leis do vault** | 6× Art. 55-A na LGPD; o candidato pode decorar texto revogado | fixture HTML com `<strike>` falha no código atual e passa no novo; LGPD sem duplicata |
| 0.2 | Flashcards com `?` por padrão, reverso só por cartão; migrar os 177 baralhos | ~2.836 revisões inúteis; zero histórico = migração grátis | contagem de cartões do plugin = contagem gerada |
| 0.3 | Bugs: `--corrigir` duplicando; quota re-pedida (G-N1); notebook duplicado; "6 h" em dias; anulada estourando traceback | quota e conteúdo queimados por instrução da própria skill | um teste por bug, falhando contra o código antigo |
| 0.4 | Agents com caminho absoluto (o `install.sh` reescreve `scripts/` ou o orquestrador passa `SKILL_DIR`); `edital-parser` passa a chamar `extract_edital.py` | os scripts de download e extração estão sendo contornados | download de lei no fluxo real passa pelo `fetch_lei.py` |
| 0.5 | Detectar PDF-imagem cedo (caracteres por página) em `extract_edital` e `check_pdfs`; ler tabelas do DOCX | prova escaneada passa como válida; quadro de vagas do DOCX some | validador acusa a prova de 2019 do SEDES |

### Fase 1 — Usar o que já foi coletado (custo médio, semanas)

| # | Item | Por quê |
|---|---|---|
| 1.1 | **Afere multi-banca**: perfil por banca (formato do gabarito, anuladas como `⊘` fora do denominador, 3 dígitos, peso de chute vindo do `.meta.json`); fixtures = `pdftotext` real dos 3 pares Quadrix do vault | destrava o SEDES; hoje só a Cesgranrio passa |
| 1.2 | **Aferir o SEDES contra a prova de 06/09** (caderno + gabarito definitivo, se já publicado) | é a única prova real do concurso ativo; mede 121 aprofundamentos que nunca foram medidos |
| 1.3 | **Banco de questões reais**: extrair as questões das provas (reaproveitando `extrair_questoes.py`), o **agente** casa questão → tópico/assunto, um script grava um arquivo **derivado e regenerável** (`questoes-reais.md`) ao lado do assunto, com prova, ano, versão, número e gabarito. Nunca injetado no resumo. Cada prova ganha `uso: medicao \| treino \| reservada`, e a reservada fica fora | transforma 9 provas nunca usadas em prática; preserva provas para medir |
| 1.4 | **Incidência por tópico** a partir do banco; histórico e sinergia **antes** dos mapas; pegadinha passa a citar a questão ou a ser marcada `inferida` | 599 pegadinhas sem lastro; prioridade sem base |
| 1.5 | **Integridade do conteúdo**: `conferir_citacoes.py` (citação existe no `pdftotext` da página ±1, tamanho máximo, palavras por nível); `trecho_livro.py --paginas` para o agente ler antes de escrever; vocabulário de `metodo:` no contrato | Modelo 2 e "nunca fingir precisão" sem verificação |
| 1.6 | **Detalhado ⊇ padrão**: a lista de conceitos do padrão entra como checklist de entrada do detalhado, e um script acusa conceito ausente | 22% de perda medida, 4 questões |
| 1.7 | **`book_index` barato**: bookmarks do PDF, sumário além das 15 primeiras páginas, deslocamento página impressa × PDF declarado na saída, ordem de leitura do EPUB | conserta o que é usado, sem dependência pesada |
| 1.8 | **Schema com o que decide a nota**: pesos por bloco, eliminação, critérios da discursiva, estrutura **por cargo**; entram no diff estrutural | pré-requisito de simulado e de cobertura por peso |
| 1.9 | **Relatório de cobertura por peso**: questões da prova por matéria × assuntos aprofundados | TI = 50% do Agente de Tecnologia com 0 assuntos |
| 1.10 | **Ações da aferição estruturadas** (tabela com wikilink, nível, falta, questões) + script de pendências que confere se o assunto mudou depois da data; convenção da prova gasta com campo `provas_usadas_para_escrever` e confirmação explícita ao reaferir | fecha o ciclo sem injetar e sem circularidade |

### Fase 2 — Medir o candidato (com a suíte, como a ADR-007 decidiu)

O vault produz o **conteúdo canônico**; a suíte guarda o **dado individual**:

- **Vault → bundle:** banco de questões com metadados (banca, ano, versão, assunto, gabarito,
  anulada, uso), **especificação de simulado** gerada da matriz do edital (determinística),
  cartões com **id estável atribuído no vault** — a ADR-007 recusou o id por hash da frente do
  plano de 29/09, porque ele zera o histórico de revisão quando a frente é corrigida. A migração
  da Fase 0.2 (`??` → `?`) é o momento natural de atribuir esses ids, e vem **antes** do bundle,
  para a suíte não importar cartões reversos.
- **Suíte:** respostas por usuário; nota líquida pela regra do edital (determinística, legítima para
  código); **caderno de erros** com causa declarada pela pessoa; FSRS sobre os cartões; o estado
  "lacuna de aferição" separado do estado de estudo.
- **Laço de volta:** o que a suíte medir (taxa de erro por assunto, causas) volta ao vault como
  **pendência** para o agente ampliar — relatório, nunca escrita automática no `.md`.

### Fase 3 — Recursos novos, com recorte

| # | Recurso | Recorte |
|---|---|---|
| 3.1 | **Discursiva parametrizada** | Régua, estrutura e espelho derivados do gênero e dos critérios do edital (redação Quadrix CAC/OT/DLP; redação Cesgranrio; estudo de caso), banco de temas com texto motivador. Correção pelo agente = feedback marcado como tal. Textos e histórico → suíte. |
| 3.2 | **Vigência de lei** ("radar" barato) | Rebaixar periodicamente, comparar hash, avisar "lei mudou desde o download" nos assuntos que a usam; `reuse_finder` alerta quando a norma mudou. Súmulas só com concurso jurídico. |
| 3.3 | **Recursos contra gabarito preliminar** (novo) | Na janela de 2-3 dias após o preliminar, usar a infraestrutura da afere + a seção "Divergências entre autores" para apontar questões contestáveis, com fundamento citado (livro e página). Alto valor, janela curta, reaproveita quase tudo. |
| 3.4 | **Revisão cruzada entre modelos** (novo) | Usar o dual-engine para **qualidade**, não só instalação: o outro modelo revisa o assunto escrito (fatos, citações, banca errada, questão ambígua) e produz **relatório de pendências** — nunca edita. Ataca 4.3 diretamente. |
| 3.5 | **NotebookLM por valor** | `--prioridade alta` e/ou "assuntos com lacuna na aferição", variante curta para revisão, prompts com banca e formato da prova. Nada de rotação de contas. |
| 3.6 | **Dual-engine operacional** | Seguir o padrão já usado no vault — `.agents/skills.json` relativo no workspace, `.agents/agents/<nome>/agent.md` gerado a partir de `skills/concurso-prep/agents/*.md` com o frontmatter do Antigravity, guarda de CI que compara os corpos — e alinhar ao que a ADR-007 definiu para a suíte: `CLAUDE.md` como fonte, `AGENTS.md` de ponte para o `agy` (que não lê `CLAUDE.md` nem `.claude/`), guarda de segredos nas duas engines. Não tocar `~/.gemini/config/skills.json`. |

**Descartar ou adiar:** embeddings no `book_index`; rotação de contas do NotebookLM; Mermaid/Canvas;
radar de súmulas; qualquer regra de nota específica do Cebraspe enquanto não houver concurso
Cebraspe no vault.

---

## 6. Roteiros comparados

| Item | Gemini | Esta revisão | Motivo da diferença |
|---|---|---|---|
| `install.sh --gemini` | Fase 1 | Fase 3, em outro formato | é operacional, não muda a nota; e o formato proposto é sobrescrito pelo bootstrap |
| `remediar_afericao.py` | Fase 1 (injeta) | Fase 1 (pendências estruturadas) | injetar viola convenções e reintroduz circularidade |
| `fetch_lei` + UA | Fase 1 | Fase 0 (`fetch_lei`); UA irrelevante | lei revogada é material errado em uso |
| Afere multi-banca + aferir SEDES | — | **Fase 1** | o concurso ativo não pode ser medido |
| Banco de questões reais + incidência | — | **Fase 1** | 9 provas nunca usadas; 599 pegadinhas sem lastro |
| Flashcards `??` | — | **Fase 0** | dobra a carga; migração grátis agora |
| Conferência de citações / detalhado ⊇ padrão | — | **Fase 1** | ninguém confere o conteúdo |
| Discursiva | Fase 2 | Fase 3, parametrizada | depende do schema com critérios (1.8) |
| Caderno de erros | Fase 2 (no vault) | Fase 2 (na suíte) | ADR-007 (perfil A) |
| Simulados | Fase 2 | Fase 2, depois de 1.3 e 1.8 | sem questões e sem regra de nota não há simulado |
| Mermaid/Canvas | Fase 3 | adiar | não renderiza; baixo valor |
| Busca semântica | Fase 3 | descartar | o fluxo real não usa o `book_index` |
| Radar de súmulas | Fase 3 | só vigência de lei | concursos atuais não são jurídicos |

---

## 7. Decisões do dono

Tomadas em 2026-10-04, depois da leitura desta revisão:

| # | Questão | Decisão | Efeito no roteiro |
|---|---|---|---|
| 1 | Aferir o SEDES agora? | **Sim** — o gabarito definitivo já saiu | 1.1 (afere multi-banca, começando pelo perfil Quadrix) e 1.2 (aferir a prova de 06/09) vão para o topo da Fase 1 |
| 2 | Onde mora o banco de questões? | **Conteúdo canônico no vault** (derivado, regenerável); **respostas e erros na suíte** | confirma a Fase 2 como desenhada; o `export_bundle` passa a levar as questões e a especificação de simulado |
| 3 | Migrar os flashcards para `?` agora? | **Sim** | 0.2 confirmado, e antes do `export_bundle`, para a suíte não importar cartões reversos |
| 4 | Prioridade do BB | **Agente Comercial** | 1.9 (cobertura por peso) roda para o Agente Comercial. **Pré-requisito:** o `.meta.json` do BB descreve só a prova do Agente de Tecnologia (`estrutura_prova_por_cargo: null`), então o 1.8 (estrutura por cargo) vem antes. A TI do Agente de Tecnologia fica registrada como lacuna conhecida, sem prioridade |
| 5 | Versionar o plano da suíte, o levantamento do Gemini e esta revisão? | **Sim** | os três entram no git juntos |

Ainda aberta:

6. **Atualizar README/ARQUITETURA** para a ADR-007 agora, ou quando o `export_bundle` existir?

---

## Fontes

- Levantamento avaliado: `docs/REVISAO-ECOSSISTEMA-SKILLS-AGENTS-SCRIPTS-E-RECURSOS.md`.
- Plano e decisão anteriores: `docs/PLANO-BACKEND-SUITE-E-ESTUDO-INDIVIDUALIZADO.md` e a ADR de
  2026-09-29 no vault do projeto, ambos **superados** pela ADR-007 da nella-suite (2026-10-03).
- Código e documentação do repositório na `main` em `5042029`, mais os arquivos não rastreados acima.
- Dados do vault: `30_AREAS/CARREIRA/CONCURSOS/{SEDES_2026,BB_2027_PREVISTO}` (só leitura).
- Ambiente dual-engine: `bootstrap-home.sh` e `sync-vault.sh` do toolkit do vault; `.agents/` do vault.
