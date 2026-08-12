# Convenções invioláveis — `concurso-publica`

Regras que vieram de **bugs reais** neste repositório. Cada uma traz o número que a
originou, e é o número que impede a regressão: sem ele a regra vira opinião, e
opinião se "melhora" de volta ao defeito.

Moram aqui, e não no `CLAUDE.md` da raiz, porque só valem para esta skill — e o
raiz é carregado em todo turno de toda sessão, inclusive nas que não a tocam. O
índice de todas está em [`CLAUDE.md`](../../CLAUDE.md#por-skill).

> Se uma destas regras conflitar com o código, **o código venceu** e a regra virou
> defeito de documentação. Corrija os dois na mesma PR.

---

- **O site é derivado, o vault é a fonte**: a `concurso-publica` nunca escreve no vault. O progresso exibido no site vem dos checkboxes dos `.md` e é **só leitura** — não criar um segundo lugar onde o progresso vive.

- **O site espelha COMUM/cargo**: a estrutura de saída é `{concurso}/{comum|cargo}/`, como as pastas do vault. `00-INDICE.md` e `99-Status.md` são **derivados, não republicados** — a navegação do site é o índice, e os checkboxes do status entram na barra de tarefas do escopo. Mas eles continuam sendo *lidos*: é de lá que saem a ordenação das matérias e os selos de questões/prioridade.

- **Progresso é barra, em todo lugar.** A bolha do cartão-resposta deixou de medir progresso: ela sobrevive como selo de nível (meia = padrão, cheia = detalhado) e como marcador das listas de tarefa. Duas tentativas anteriores falharam pelo mesmo motivo — `min(total, max_bolhas)` fazia 8 bolhas valerem 303 tarefas, e depois barra na matéria com bolha no assunto punha o **mesmo número com duas aparências em telas vizinhas**. Escopo e matéria usam **duas barras lisas empilhadas, sempre na mesma ordem**: tarefas de estudo (verde `--confere`, o visto de concluído) em cima, tópicos do edital (azul `--tinta`, a caneta que escreveu o material) embaixo; o assunto usa uma só, a de tarefas. Trocar a ordem ou a cor num lugar só torna as caixas incomparáveis, que é exatamente o defeito.

- **Tarefas de estudo é tudo o que há para marcar** — assuntos (a **união** dos aprofundamentos, não só o principal) + os **itens do plano do mapa** + documentos de seção + `99-Status.md`, somados em `progresso_tarefas`. Cada exclusão aqui já escondeu trabalho: contando só os assuntos, os cargos apareciam sem barra tendo 21, 17 e 8 tarefas em documentos; contando só o aprofundamento principal, sumiam 181 checkboxes em 29 assuntos. **Os mapas ficaram de fora na 0.17.0 e voltaram na 0.18.0** — o argumento de que 1.998 itens nunca marcados afogariam as ~200 reais estava errado, porque "Ler as páginas" e "Resolver 30 questões" são a mesma espécie de trabalho, e a exclusão deixava **12 das 22 matérias sem barra nenhuma**. Denominador grande e verdadeiro ganha de pequeno e mudo.

- **O mapa conta para quem guarda o arquivo.** `cruzar_materias_comuns` anexa o mapa do cargo à matéria irmã do `_COMUM`, então a matéria com `mapa_em` **não** soma os itens do plano: somar dos dois lados contaria 237 em dobro só no comum do SEDES. É a mesma regra da tarefa herdada, e o resto das parcelas não se sobrepõe por construção — o `99-Status` fica fora das pastas de `SECOES`, e a seção herdada do `_COMUM` é ponteiro com `documentos: []`.

- **Matéria com aprofundamento tem aba Estudo, mesmo que o material more no comum.** `tem_estudo` olhava só `materia["assuntos"]`, e a matéria do cargo tem a lista vazia quando o mapa é dele e o material é do `_COMUM` — três matérias do SEDES ficavam só com o Plano enquanto a cobertura já afirmava 40%, 60% e 25%. Os assuntos da irmã entram em `assuntos_herdados`, **chave à parte que a agregação de progresso ignora**: copiá-los para `assuntos` faria os mesmos checkboxes contarem nos dois escopos. Matéria só-com-mapa e **sem** irmã segue sem Estudo, que é o caso legítimo de 9 matérias.

- **Documento longo no topo de uma aba esconde o que a aba existe para mostrar**: a bússola `COMO-A-BANCA-COBRA` é o primeiro bloco da visão Estudo e era publicada inteira e aberta. Medido: **2.770px** de bússola empurravam o primeiro grupo de assuntos para **3.131px** — **2,3 telas** numa janela de 1.321px —, e o relato foi "o tópico **nem existe** dentro de Estudo". Existia. O incentivo ficava invertido: **quanto melhor o documento, mais ele escondia a lista** (as duas matérias com bússola tinham 5.976 e 7.424 chars antes do primeiro assunto; as sem bússola, 64 e 101). Documento de apoio no topo de uma aba vai em `<details>` **fechado**, com título no `<summary>` — nativo, sem JS, e `@media print` reabre. E a lição de verificação: **"o HTML contém o elemento" não é "a pessoa vê o elemento"** — depois de publicar, meça **posição**, não só presença.

- **Asset publicado leva a versão do conteúdo na URL** (`site.css?v=<hash>`). O nginx manda `expires 1h`, então sem isso o navegador serve **HTML novo com CSS velho** — e o defeito é invisível, porque a página renderiza, só renderiza errado: foi assim que os rótulos das barras saíram no tipo do corpo e a cobertura saiu verde depois de já ser azul no servidor.

- **Barra ausente, vazia e desconhecida são três coisas**: some só quando o medido não existe (cobertura sem mapa nenhum); vem vazia com o trilho à vista quando existe e está em zero (`0/48`, nunca `0/0`); vem **hachurada e escrita** quando existe e não se pode saber (`vinculo_ausente`). Matéria sem vínculo **nunca** entra no denominador agregado — é o falso zero já proibido no link tópico↔assunto, agora em escala de escopo, onde uma matéria arrastaria a barra de um cargo inteiro.

- **Tarefa pertence a quem guarda o arquivo; cobertura pertence a quem tem o edital.** A barra de tarefas de uma matéria conta só os assuntos **próprios** — matéria "aprofundada no comum" não repete os checkboxes do `_COMUM` no cargo, senão o mesmo trabalho conta duas vezes e nenhum total fecha. A cobertura é o oposto: o tópico é do edital **do cargo**, então a matéria emprestada entra sim no denominador dele.

- **Nunca inferir o link mapa↔assunto por slug**: dos 203 tópicos dos 24 mapas do vault, ~18% casam. Um tópico do edital pode cobrir vários assuntos, aprofundamento por legislação é N:M, e assunto reaproveitado de outro concurso mantém o slug do edital de origem. Sem casamento exato, a página **não afirma nada** — o falso negativo ("sem aprofundamento" quando existe com outro nome) esconde trabalho feito. O link fino vem de `mapa-aliases.json`, opcional.

- **Nada escrito no tópico do mapa se perde em silêncio**: rótulo de H3 fora do template é **publicado** (com o texto do vault) **e avisado** na geração — publicar sem avisar esconde que template e vault divergiram, avisar sem publicar foi o bug que sumiu com 50 blocos (`Leis-chave`, mnemônicos 🧠). Rótulo repetido no mesmo tópico **acumula**, nunca sobrescreve: guardar as subseções num dict chave→markdown perdia 57 subtópicos em 5 tópicos. E **a lista exibida tem de contar o mesmo que o contador do rodapé** — foi a contradição (1 item listado sob `0/22 itens do plano`) que denunciou o defeito, e há teste que trava o invariante.

- **Cobertura é contagem; qualidade não se inventa**: a % de tópicos com aprofundamento sai do `topico_id` gravado, e as lacunas aparecem **por nome**. Nota sintética de qualidade foi descartada por medição — no vault os sinais que a comporiam estão saturados (placeholders em 0 arquivos, `status` `revisar` em todos, `confianca baixa` em 0 de 92), então a nota seria constante disfarçada de métrica. Mostra-se o que **existe** (cards, âncoras, nível). E matéria com assuntos sem vínculo tem cobertura **desconhecida**, nunca zero.

- **Selo de mídia no card só para o que existe**: mostrar os 8 tipos com os ausentes em cinza são 88 ícones numa matéria de 11 assuntos. A grade completa fica na página do assunto, onde "falta gerar" é acionável.

- **Índice de nomes é para wikilink; navegação é calculada**: o índice resolve por basename e nomes repetem entre escopos (`lingua-portuguesa` no comum e em cada cargo). Link de navegação sai sempre da rota da própria página — usar o índice fazia o hub do cargo apontar para a matéria do comum e deixava a própria órfã.

- **Cores só via variáveis de tema**: nada de hex fixo para cor de texto no CSS, senão o tema escuro quebra (já aconteceu com `strong`). Toda variável precisa existir nos dois temas — há teste que barra isso.
