# Changelog — concurso-publica

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

## [0.22.1] - 2026-08-06

### Corrigido
- **`fontes_notebook: []` declarado sumia da ficha.** O bloco só aparecia com a
  lista não-vazia, então "conferido, não há lei a subir" e "ninguém conferiu"
  renderizavam idênticos — nada. Ausente, vazio e desconhecido são três coisas,
  a mesma regra que já vale para as barras de progresso: campo **ausente** segue
  sem bloco (não se sabe), campo **declarado vazio** passa a dizer *"Só a nota
  deste assunto · conferido · nenhuma lei a subir"*. Um assunto de livro sobe
  legitimamente só a nota; um cuja lista falhou também — sem dizer qual é qual,
  os dois ficam iguais na tela, e foi essa indistinção que gerou o relato "os
  notebooks só receberam uma fonte".

## [0.22.0] - 2026-08-05

### Corrigido

- **O selo conta as fontes pelo id, não pelo texto livre.** `fontes_externas` quebrava o campo
  `fontes:` por vírgula e unia as strings entre os níveis do assunto. Como a mesma obra aparece
  grafada como título num nível (`A Gramática para Concursos (Pestana)`) e como nome de arquivo
  no outro (`A-Gramatica-…-Pestana.pdf`), a união dava **3** onde as fontes são **2** — em
  **15 dos 29** assuntos multi-nível do vault. O `fontes_id`, derivado do id por `parse_id`,
  já existia no modelo e **não era usado na contagem**.
- **Material próprio em layout legado deixou de contar como fonte externa.** O filtro testava a
  PASTA (`fontes_id != [FONTE_PROPRIA]`) para decidir sobre o TEXTO: quando `parse_id` falha,
  `fontes_id` sai `[]`, a comparação dá verdadeiro e o "material próprio" era somado — o site
  afirmando que existe fonte onde o arquivo declara que não há. Agora o filtro é por slug.
- **Campo morto `rotulo` removido do modelo.** Era gravado no collector e o builder **nunca o
  lia** — recalculava com `rotulo_aprof`, em formato diferente ("Detalhado — pestana" ×
  "Pestana · Detalhado"). Duas regras para o mesmo dado, uma delas sem leitor.

### Adicionado

- **As duas listas de fonte, separadas e qualificadas.** A ficha do aprofundamento passa a
  dizer *Fontes do aprofundamento* (o que sustenta o texto escrito) e, quando houver,
  *Fontes do notebook* (o que sobe para gerar a mídia), com a contagem e se foram **declaradas**
  ou **sugeridas**. Elas divergem por natureza — um assunto de norma tem 1 fonte e manda 6 ao
  notebook; um de livro tem 2 e manda 1 —, e escrever "fontes" duas vezes sem qualificador na
  mesma tela é o que gerou a dúvida que originou esta série.
- `fontes_notebook` e `fontes_notebook_declarado` no modelo, lidos do frontmatter. Ausente ≠
  `[]`: vazio é decisão ("só a nota"), ausência é "ninguém declarou".

### Notas

- **Fixture corrigida:** `_add_aprof` criava ids **invertidos** (`pestana--padrao` em vez de
  `padrao--pestana`), que não parseiam. Enquanto a contagem vinha do texto isso não aparecia;
  com ela vindo do id, os testes passariam a medir 0 fontes e quebrariam **pelo motivo errado**.
  Fixture divergente é teste que se autoconfirma — o mesmo defeito que já custou dois bugs
  invisíveis nesta skill.
- `nome_legivel` de `aprofundamento_id` é importada **com alias** (`nome_da_fonte`): o
  `site_builder` tem uma `nome_legivel` própria, que traduz slug de **concurso**
  (`SEDES_2026` → `SEDES 2026`). Nomes iguais para coisas diferentes se pagam meses depois.

## [0.21.1] - 2026-08-05

### Alterado

- Cópia de `aprofundamento_id.py` **sincronizada** com a `concurso-aprofunda` 0.10.0
  (`separar_fontes`, `nome_legivel`, `fontes_legiveis`, `conferir_fontes`). O módulo é fonte de
  verdade lá e cópia byte-idêntica aqui, travada por `test_copia_do_aprofundamento_id_nao_divergiu`
  — mudar só o original quebraria o CI **na suíte desta skill**, porque o `test-all.sh` roda as
  nove do mesmo checkout.
- **Sem mudança de comportamento do site**: a contagem de fontes continua saindo do texto livre
  nesta versão. Passa a sair do id na 0.22.0.

## [0.21.0] - 2026-08-05

### Corrigido

- **A matéria publica TODAS as suas aferições**, não só a primeira em ordem alfabética. Uma
  matéria pode ser medida mais de uma vez — contra outra prova, ou contra a **mesma** depois
  de corrigido o material — e `achar_doc_afericao` devolvia um único nome. Com dois arquivos,
  `00-AFERICAO-…-POS-CORRECAO.md` viria antes de `00-AFERICAO-….md` (o `-` ordena antes do
  `.`) e **esconderia a original em silêncio**: o mesmo defeito que a 0.20.0 veio consertar,
  reaparecendo em outra forma.
- A ordem é **`data:` e depois `rodada:`**, ambas decrescentes — a última medição primeiro, as
  anteriores como histórico logo abaixo.
- **O `rodada:` existe porque o desempate pelo nome não funciona**, e reaferir logo após
  corrigir o material é justamente o caso em que as duas caem no mesmo dia. Medido no vault:
  com `data` igual, `00-AFERICAO-VENDAS-E-NEGOCIACAO.md` ordenava **depois** de
  `00-AFERICAO-VENDAS-E-NEGOCIACAO-2-POS-CORRECAO.md`, porque no ponto de divergência o `.`
  (46) é maior que o `-` (45) — e a rodada 2 caía para baixo da rodada 1. Ordem que depende de
  tabela ASCII é coincidência, não ordem.
- Nada é obrigatório: sem `data:` e sem `rodada:`, cai no nome e a aferição **nunca some** —
  no pior caso fica no fim.
- Todas continuam em `<details>` fechado, e nenhuma vaza para a lista de "documentos de apoio"
  — o filtro passou a excluir o conjunto inteiro, não só um nome.

## [0.20.0] - 2026-08-05

### Adicionado

- **A aferição contra prova real agora é publicada na página da matéria**, com conteúdo e
  **recolhida**. A skill `concurso-afere` grava `00-AFERICAO-*.md` ao lado do material que
  mediu, mas `DOCS_APOIO_CONHECIDOS` casava apenas `00-COBERTURA|00-GUIA|00-INDICE|COMO-USAR`
  — o arquivo era ignorado **em silêncio**, e as **duas** aferições do vault não apareciam em
  lugar nenhum do site.
- **Publicar só o nome não resolveria.** Os "outros documentos de apoio" viram uma lista de
  nomes de arquivo (`<li>00-AFERICAO-….md</li>`), e a aferição é a análise que mede a matéria:
  nota por nível, distribuição das questões por assunto, lacunas nomeadas e ações corretivas —
  **267 linhas** em Vendas e Negociação. Ela é para ser lida, não citada.
- Vai em `<details>` **fechado**, pelo mesmo motivo da bússola: é ainda maior que ela, e
  documento longo no topo de uma aba esconde o que a aba existe para mostrar. Título no
  `<summary>`, `@media print` reabre.

### Alterado

- **A regra do documento recolhido virou um lugar só** (`_doc_recolhido`), com `bussola_recolhida`
  e `afericao_recolhida` sobre ela. Era regra de layout prestes a ser copiada — e regra de layout
  copiada é a que diverge depois. O CSS seguiu o mesmo caminho: os seletores da bússola passaram
  a valer para as duas, sem hex fixo novo.

## [0.19.0] - 2026-08-03

### Corrigido
- **A bússola da banca escondia a lista de assuntos, e a aba Estudo parecia vazia.**
  O documento "Como a banca cobra esta matéria" é o primeiro bloco da visão Estudo e
  era renderizado inteiro, aberto. Medido na matéria `direitos-violacoes-vulnerabilidades`
  do SEDES: a bússola ocupava **2.770px** e o primeiro grupo de assuntos começava em
  **3.131px** — **2,3 telas** de rolagem numa janela de 1.321px. O relato do dono foi
  literal: *"Mulheres e violência de gênero nem existe dentro de Estudo, apenas em Plano"*.
  Existia; estava três telas abaixo de uma parede de texto.

  O incentivo estava invertido: **quanto melhor a bússola, mais ela escondia** o que a
  aba existe para mostrar. No vault, as duas matérias com bússola escrita tinham 5.976 e
  7.424 caracteres antes do primeiro assunto; as sem bússola, 64 e 101.

  Agora a bússola sai num `<details>` **fechado**, com o título no `<summary>` e uma
  dica ("perfil da banca nesta matéria"). Ela continua sendo o primeiro bloco — a
  `concurso-aprofunda` a quer antes da lista, para orientar o estudo —, mas os assuntos
  voltam para a primeira tela. `<details>` nativo: funciona sem JS, o Ctrl+F do Chrome
  abre o bloco, e no `@media print` o corpo volta a aparecer inteiro (papel não tem
  clique). Coberto por `test_bussola_da_banca_abre_recolhida`, que falha contra o
  código anterior.

## [0.18.0] - 2026-08-03

### Corrigido
- **HTML novo era servido com CSS velho, e o defeito era invisível.** O nginx manda
  `expires 1h` e a URL do asset não tinha versão, então o navegador buscava as páginas
  novas e reaproveitava a folha antiga: os rótulos das barras saíam no tipo do corpo, o
  `flex` sumia e rótulo e número colavam, e a barra de cobertura saía **verde** — a cor
  que ela tinha na versão anterior. A página renderizava; só renderizava errado. Agora
  o link carrega um resumo do conteúdo (`site.css?v=<hash>`).
- **12 das 22 matérias apareciam sem a barra de tarefas.** Os checkboxes do mapa do
  edital estavam excluídos por decisão da 0.17.0 — 1.998 itens, nenhum marcado, "que
  afogariam as ~200 do aprofundamento". O argumento não se sustentou: "Ler as páginas"
  e "Resolver 30 questões" são a mesma espécie de trabalho, e a exclusão escondia mais
  do que protegia. **Os itens do plano voltaram para a barra de tarefas**, na matéria e
  no escopo. Efeito: 22 de 22 matérias passam a ter as duas barras.
- **O progresso do assunto contava só o aprofundamento principal**, perdendo **181
  checkboxes** em 29 assuntos — dois de português apareciam zerados tendo 8 e 7 tarefas
  na versão detalhada. Agora é a união de todos os aprofundamentos.
- **Matéria com aprofundamento no `_COMUM` ficava só com a aba Plano.** `tem_estudo`
  olhava apenas `materia["assuntos"]`, vazia quando o mapa é do cargo e o material é do
  comum. Três matérias do SEDES estavam assim, com a cobertura já afirmando 40%, 60% e
  25%. A aba Estudo passa a existir e mostra os assuntos da irmã, linkando para lá.
- **Matéria criada só a partir de mapa nascia com o progresso zerado à mão**, apagando
  de 35 a 176 itens que ela de fato tem.

### Alterado
- **A bolha do cartão-resposta deixou de medir progresso.** Ela sobrevive como selo de
  nível e como marcador das listas de tarefa; o card e a página do assunto passam a
  usar a barra, como o resto do site. Tinha ficado o mesmo número com duas aparências
  em telas vizinhas.

### Notas de projeto
- O mapa conta para **quem guarda o arquivo**: matéria com `mapa_em` (mapa emprestado
  pelo cruzamento) não soma os itens do plano — somar dos dois lados contaria 237 em
  dobro só no `_COMUM` do SEDES.
- Os assuntos da irmã entram em `assuntos_herdados`, chave à parte que a agregação de
  progresso ignora. Copiá-los para `assuntos` faria os mesmos checkboxes contarem nos
  dois escopos.

## [0.17.0] - 2026-08-03

### Adicionado
- **Duas barras lisas de progresso** no card de escopo (capa), no hub do escopo e no
  card de matéria: **tarefas de estudo** em cima, **tópicos do edital** embaixo, sempre
  nessa ordem. Pilha cujo significado por linha muda de card para card é ilegível — e a
  incomparabilidade entre as caixas foi exatamente a queixa que originou a mudança.
- `escopos[].progresso_tarefas` — tudo o que há para marcar no escopo: assuntos +
  documentos de seção + `99-Status.md`. `progresso_documentos` e `progresso_status`
  eram coletados e **jogados fora**: nenhum consumidor no builder. Efeito no vault: os
  três cargos do SEDES e o AGENTE-DE-TECNOLOGIA do BB deixam de aparecer **sem
  indicador nenhum** tendo 21, 17, 8 e 37 tarefas em documentos.
- `escopos[].cobertura` — o agregado dos tópicos das matérias, para a barra do escopo
  ser a soma exata das barras das matérias.
- `materias[].progresso` — a matéria não tinha agregado nenhum, só os assuntos
  individualmente, então o card não tinha o que mostrar.

### Alterado
- **A barra de cobertura passou de verde para azul.** Quem conhece o site vai notar.
  A regra agora é uma só e vale em todo lugar: **verde `--confere` = o que EU fiz**
  (o visto de concluído, como a tarefa marcada da lista já era) e **azul `--tinta` =
  o material que existe** (a caneta que o escreveu). Antes a tarefa marcada era verde
  na lista e azul na bolha, e a cobertura — que é material — era verde.
- **A bolha do cartão-resposta ficou onde cada bolha é uma tarefa**: o nível do
  assunto (3 a 5 checkboxes). `min(total, max_bolhas)` fazia 8 bolhas valerem 303
  tarefas — uma bolha ≈ 38 — e o comprimento da barra variar por card. `gabarito()`
  agora **delega ao medidor** acima do limite, e não existe mais reescala em lugar
  nenhum: uma bolha, uma tarefa, sem arredondamento.
- **`_GERAL` deixou de zerar o progresso à mão** — concurso em layout achatado
  mostrava barra vazia tendo trabalho real.
- `examples/site-model-exemplo.json` passou a ser **gerado do fixture da suíte**, não
  escrito à mão. Estava defasado em silêncio: faltavam `materia_id`, `cobertura`,
  `sinais`, `progresso_documentos` e `progresso_status`.

### Corrigido
- **Documentação que mentia.** `SKILL.md`, `site_collector.py` e `site_builder.py`
  afirmavam que "o progresso do `99-Status` vira a barra do hub do escopo". Não virava:
  a barra lia só os assuntos. Agora vira de fato — como uma das três parcelas.

### Notas de projeto
- Os checkboxes dos **mapas continuam fora** da barra de tarefas: os 24 mapas do vault
  somam 2.220, nenhum marcado, e afogariam as ~200 que alguém pretende marcar.
- Matéria com `vinculo_ausente` **nunca** entra no denominador agregado — seria o falso
  zero já proibido no link tópico↔assunto, agora em escala de escopo, onde uma matéria
  arrastaria a barra de um cargo inteiro. Sai da conta e é declarada por escrito, com
  o trilho hachurado.
- Tarefa é de quem guarda o arquivo: a barra da matéria conta só os assuntos
  **próprios**, senão "aprofundado no comum" contaria os mesmos checkboxes no cargo e
  no `_COMUM`. Cobertura é o oposto — o tópico é do edital do cargo, então a matéria
  emprestada entra sim no denominador dele.

## [0.16.0] - 2026-08-03

### Corrigido
- **Wikilink com âncora resolvia pelo BASENAME.** Há um `livros-recomendados.md` por
  escopo — sete no concurso real — e `Rotas.chave` reduz tudo ao último segmento, então
  `[[…/livros-recomendados#^mat-x]]` caía sempre na primeira página homônima
  registrada. Foram **160 links** apontando para âncora que não existe naquela página.
  A âncora é única dentro do concurso (35 no SEDES, 93 no BB, zero repetidas entre
  escopos) e por isso vence o nome. O `md2html` passa a entregar a âncora ao resolvedor.
- **O block id do Obsidian saía como texto visível** e o wikilink resolvia para um id
  inexistente — o link levava à página certa e não pulava a lugar nenhum. Vira âncora
  HTML invisível, como no modo leitura do Obsidian.
- **Backups eram publicados como anexo.** Os scripts que reescrevem material deixam
  `.md.bak` ao lado do arquivo, e a varredura recursiva os tratava como anexo: viravam
  arquivo para baixar. Pior, o "anexo" impedia a seção de colapsar num documento só, e
  o catálogo ficava um clique adiante.
- **Cargo com catálogo próprio perdia o link para o do comum**: com um documento só, a
  seção colapsa numa página de documento, e `pagina_documento` não renderizava o bloco
  de herança.

### Notas
- Site dos dois concursos: 264 links para o catálogo resolvendo, 0 quebrados, e 64
  links diretos para PDF de lei nas páginas de matéria.
- Testes: 145 -> 147.

## [0.15.0] - 2026-08-03

### Corrigido
- **A página de Materiais não existia no cargo, e sumia em silêncio.** A coleta é
  estritamente por escopo, e três filtros em cascata descartavam a seção inexistente
  sem avisar: `coletar_escopo` só anexa seção com conteúdo, `montar_rotas` não cria
  rota do que não existe e `pagina_escopo` pula grupo vazio. Medido no vault: **5 dos
  7 escopos** sem `04-MATERIAIS`, ou seja, quem estuda por um cargo não tinha nenhum
  caminho de navegação até a bibliografia. Agora o cargo herda a seção do `_COMUM`
  **por referência** — o conteúdo continua num lugar só, e o cargo ganha o ponteiro.
  Copiar os anexos para cada cargo é o defeito que já fez o site pular de 78 para 685
  PDFs; há teste que barra a duplicação.
- **A frase que mandava o leitor a "Materiais, no menu do concurso" era texto morto**
  — o esqueleto da página tem só marca, trilha e botão de tema, e a página apontada
  não existia no cargo. Virou link calculado da rota da própria página (nunca
  procurado no índice de nomes: `materiais` existe em vários escopos, e o índice
  devolveria sempre o primeiro registrado).

### Adicionado
- `Rotas.marcar()`/`tem_pagina()` — registro das páginas efetivamente emitidas, para a
  navegação poder perguntar "esta página existe?" sem passar pelo índice de nomes.
- Testes do que não tinha nenhum: o bloco "Material por tópico", a classificação
  `tipo_do_material` (incluindo o fallback deliberado para rótulo desconhecido), a
  herança do cargo e a não-duplicação de anexos. Eram 4 comportamentos com CSS e sem
  asserção.

### Notas
- O dublê `_RotasFalsas` da suíte ganhou `tem_pagina`: dublê que não acompanha a
  interface real esconde o que o código passou a exigir — e foi assim que a suíte
  acusou a mudança, corretamente.
- Rodado contra os dois concursos: 7 páginas de Materiais (eram 2), 5 links herdados
  e 21 links de bibliografia resolvendo, 0 ocorrências da frase morta, 78 PDFs (sem
  duplicação).
- Testes: 137 -> 142.

## [0.14.0] - 2026-08-03

### Adicionado
- **O manifesto de cada concurso guarda a pasta de origem no vault** (`origem` em
  `out/site/{slug}/.concurso.json`). É a peça que faltava para o `deploy.sh`
  reconstruir tudo que está no build antes de enviar: o envio é `rsync --delete` do
  diretório inteiro, mas o `--concurso-dir` nomeia um concurso só, e sem saber de onde
  os demais vieram não havia como atualizá-los. Foi assim que o `BB_2027_PREVISTO` foi
  republicado com um build de véspera enquanto se publicava o `SEDES_2026` — sem erro
  nenhum na saída.

### Alterado
- Os helpers de fixture da suíte saíram do `test_smoke.py` para
  `scripts/tests/fixture_concurso.py`. Ganharam um segundo consumidor — a suíte do
  `deploy.sh`, na raiz do repo — e um fixture por consumidor é como dois defeitos já
  ficaram verdes por meses neste repositório.

### Notas
- Campo aditivo: manifesto antigo continua válido, e o `deploy.sh` deduz a origem pela
  pasta irmã quando ele não a tem, ecoando o palpite.
- Testes: 136 -> 137 (mais 22 na suíte nova do deploy).

## [0.13.0] - 2026-08-02

### Adicionado
- **A ficha do aprofundamento mostra onde cada fonte foi localizada.** Num
  aprofundamento combinado só aparecia o ponteiro da fonte 1, o que faria o leitor
  procurar no livro errado as outras. O modelo ganha `localizacoes: [{fonte, texto}]`,
  lido de `localizacao_livro` + `localizacao_2..N` que a `concurso-aprofunda` grava.
- O texto do ponteiro vai **inteiro**, não só as páginas extraídas: 61 dos 122 valores
  do vault são prosa livre ("slides 12 a 21") que a regex de página não casa.
  `paginas_livro` continua existindo para quem já o consome.

### Notas
- Com fonte única nada muda — continua "No livro — págs. X", travado por teste.
- Cópia de `aprofundamento_id.py` sincronizada (ganhou as funções de localização).
- Testes: 134 -> 136.

## [0.12.0] - 2026-08-01

### Corrigido
- **"Vagas (AC)" e "Salário" nunca renderizavam na ficha do concurso.** O
  `site_builder` procurava os dois na RAIZ do `.meta.json`, e num concurso multi-cargo
  eles vivem em `cargos_validados[]` — o SEDES tem 3 cargos com vagas e salários
  diferentes, e não existe número de raiz que os represente sem inventar um agregado.
  A ficha passa a mostrar **por cargo** quando a raiz não tem o valor, e continua
  mostrando o agregado quando tem (concurso de cargo único).
- **A allowlist do modelo não deixava o dado chegar.** O `site_collector` filtra o
  `.meta.json` para um conjunto explícito de campos — o que é bom, o modelo é contrato
  público — mas `cargos_validados` não estava nele. Produtor e consumidor discordando de
  novo, e o sintoma era um campo que simplesmente não aparecia.
- Salário numérico saía cru (`4762.97`). Vira `R$ 4.762,97`.

### Notas
- 3 testes novos; 134 na suíte.
- O fixture dos dois testes de ficha é montado pelo **coletor real**, não à mão: montar
  o modelo campo a campo é inventar o que o gerador produz, e foi assim que dois
  defeitos ficaram verdes por anos neste repo.

## [0.11.3] - 2026-07-31

### Corrigido
- **O `SKILL.md` acumulava changelog dentro do orquestrador.** Eram quatro blocos
  "Novidades da 0.3.0 / 0.4.0 / 0.5.0 / 0.7.0" — e pararam aí, com a skill em 0.11.2,
  sete versões depois. O que era decisão de projeto (como o aprofundamento é lido, por
  que o selo só mostra mídia existente, a cópia sincronizada do `aprofundamento_id.py`)
  virou descrição do estado atual, sem moldura de versão; o resto é papel do
  `CHANGELOG.md`. É a mesma lição que a `concurso-aprofunda` já tinha registrado no
  seu README ao remover o roadmap que contradizia o changelog.
- **Tabela "Estado de implementação" removida.** Os três primeiros subsistemas estavam
  ✅ havia muito tempo e o quarto, a busca client-side, era uma promessa de "próxima
  entrega" feita na 0.3.0 e não cumprida em onze versões. As referências órfãs aos
  rótulos `(A)`, `(B/C)` e "contrato entre A e B" passaram a nomear os scripts.

## [0.11.2] - 2026-07-31

### Corrigido
Quatro defeitos de renderização do `md2html.py`, todos medidos no vault antes e
depois. No HTML gerado dos dois concursos: **1.406 asteriscos crus → 0**, wikilink
não resolvido **→ 0**, e **3.969 sublistas aninhadas** em 338 páginas onde antes a
hierarquia era achatada.

- **Lista aninhada chegava ACHATADA ao site.** O conversor guardava *uma* lista
  aberta, então o subitem virava irmão do pai e a hierarquia — que é a informação —
  sumia. Eram 408 linhas em 51 arquivos. Agora há uma pilha por nível de indentação,
  e a sublista abre **dentro** do `<li>` do pai: `<ul>` como filho direto de `<ul>` é
  HTML inválido, e fechar o `<li>` antes era o jeito errado de fazer parecer certo.
- **Item de lista perdia a linha de continuação.** Linha indentada sem marcador virava
  parágrafo solto fora da lista — 838 linhas em 38 arquivos. Pior: quando o negrito
  atravessava a quebra, as duas metades caíam em conversões inline diferentes e os
  asteriscos chegavam crus à página. A continuação passa a ser juntada ao item
  **antes** da conversão inline. Linha indentada que *tem* marcador continua sendo
  sublista, não continuação.
- **`**​*negrito* contendo itálico**` não convertia.** A classe negada `[^*]+` parava
  no primeiro `*` interno e a linha inteira chegava ao site com os asteriscos crus —
  139 linhas em 20 arquivos. Passa a aceitar `*` dentro, com `***x***` tratado antes
  (senão o passo preguiçoso casaria `**` + `*x` + `**` e deixaria um `*` solto). A
  forma inversa, `*Fui eu **que fiz***`, já funcionava e tem teste para continuar
  funcionando.
- **Wikilink com pipe CRU quebrava a tabela.** O `|` do link era lido como separador:
  duas colunas viravam quatro e o link aparecia em texto puro. O escapado (`\|`) já
  era tratado; o cru, que o vault também escreve, não era. Agora o miolo de `[[…]]` é
  mascarado antes de dividir a linha, o que cobre as duas formas.

> Nota de método: o negrito usa `[\s\S]+?`, não `.+?`. O texto que chega ao conversor
> inline é um bloco inteiro com as linhas ainda separadas por `\n`, e o vault quebra
> linha no meio de negrito o tempo todo — `.` fecharia o casamento na quebra. Foi
> exatamente o que aconteceu na primeira tentativa desta correção, e a medição no
> site gerado (1.406 asteriscos) é que denunciou.

### Adicionado
- Sete testes de regressão, um por defeito e um por invariante: hierarquia preservada,
  ausência de `<ul>` inválido, estado das tarefas por nível, continuação que não engole
  a sublista, negrito atravessando quebra de linha, e as duas formas de pipe em tabela.

## [0.11.1] - 2026-07-31

### Alterado
- **O assunto abre na aba do nível `padrao`**, não mais no `detalhado`. Entra-se num assunto para revisar; o tratamento exaustivo fica a um clique. O desempate dentro do mesmo nível continua alfabético pelo id do aprofundamento — o que decide os 8 assuntos do vault com dois `padrao`. Muda também o que o card mostra, porque o primeiro aprofundamento **representa** o assunto: descrição, bolha de progresso, contagem de flashcards e URL do NotebookLM passam a vir do `padrao`. Efeito colateral bem-vindo: o único assunto do vault com mídia gerada guarda os 7 arquivos em `padrao--pestana`, que era justamente a aba fechada.

### Corrigido
- **O aprofundamento do layout plano legado podia sequestrar a aba.** Ele não tem identidade de fonte e recebe o id `original`, que vem antes de `padrao--*` no alfabeto — abriria nele em vez do aprofundamento de verdade. Passa a ordenar depois dos identificados do mesmo nível. Não há nenhum no vault hoje; é rede para o caso.

### Adicionado
- Dois testes que afirmam no **HTML** qual aba abre (`aba ativa` + `data-alvo` casando com o painel) e que o desempate entre dois `padrao` é alfabético. Antes a garantia era indireta, via `aprofundamentos[0]`, e o site podia divergir sem ninguém ver.

## [0.11.0] - 2026-07-31

### Corrigido
- **A página do pacote NotebookLM não dizia com que nome criar o notebook nem com que nome salvar cada arquivo** — as duas informações sem as quais o roteiro não se executa sem abrir o Obsidian. O nome do notebook nunca chegava (só a lista numerada da seção 1 era lida, e o nome está na frase que a introduz), e o nome do arquivo vivia numa linha que o parser de roteiro descartava.
- **`_roteiro_do_bloco()` exigia bullet e descartava as instruções que mais importam.** No template real, `Studio → …`, `Generate → …` e `Salve … como …` são **parágrafo**, não item de lista. Resultado: o roteiro do **mapa mental** e o do **report**, cujas instruções são todas parágrafo, saíam **vazios** — está congelado assim no `examples/site-model-exemplo.json`. A regra agora é aberta: toda linha de instrução entra, e o que é estrutura (blockquote, título, lista de fontes) sai. Lista fechada falha em silêncio; regra aberta falha à vista.
- **O fixture inventava a realidade que o parser exigia.** Ele escrevia `- Studio → …` **como bullet**, o que no template real não é bullet, e o corpo do pacote era a palavra `pack`. O teste ficava verde enquanto o vault produzia roteiro vazio — o mesmo modo de falha do bug do `_GERAL`. Agora o fixture **renderiza o `.tpl` real** da skill irmã, e `test_o_que_o_coletor_espera_do_pack_existe_no_template_real` quebra se o template mudar de forma.
- **O botão de copiar não alcançaria nada fora de um cartão de prompt** (`closest(".prompt")`): existiria e não faria nada, sem erro visível. Passou a aceitar `.copiavel`/`.texto-copiavel`, com teste que trava os seletores.

### Adicionado
- `pack_notebooklm.nome_notebook` e `prompts[].arquivo_saida` no modelo — os identificadores que a automação vai consumir. Lidos do frontmatter do pacote (contrato) com a prosa como **fallback**, para os pacotes do vault que ainda não foram regerados.
- A página mostra o nome do notebook **por aprofundamento** (dois aprofundamentos = dois notebooks, com nomes diferentes; no cabeçalho da página apareceria o nome errado nas outras abas) e o nome do arquivo em cada cartão de gerável.
- `examples/site-model-exemplo.json` atualizado — trazia `roteiro: []` congelado — e o teste do exemplo agora afirma roteiro não vazio e arquivo de saída em todos os geráveis.

## [0.10.0] - 2026-07-30

### Adicionado
- **Cobertura do edital, por matéria**: barra e fração `15/24 tópicos (62%)`, com as **lacunas nomeadas** num `<details>` — quais tópicos ainda não têm aprofundamento. A mesma fração aparece no card da matéria, no hub do escopo. É **contagem** do `topico_id` gravado na Etapa 2, nunca estimativa. No vault real: 60 de 151 tópicos = 40%.
- **O que existe em cada assunto**, no card: nº de cards e ausência de trechos-âncora. Contagem e presença, nunca julgamento.
- **Material por tópico**, consolidado na aba Plano: os 458 itens que já estavam nos mapas, na ordem do edital, com marcador por tipo (livro, vídeo, questões, norma). **Derivado**, não redigitado — antes só dava para vê-los abrindo um `<details>` por tópico.

### Decidido — sem nota de qualidade
Uma nota sintética foi descartada por medição, não por gosto: no vault real os sinais que a comporiam estão **saturados** — placeholders não preenchidos em 0 arquivos, `status` `revisar` em todos, `confianca_localizacao: baixa` em 0 de 92. A nota seria uma constante disfarçada de métrica, que é o oposto da regra de nunca fingir precisão. Mede-se cobertura (contável) e mostra-se o que existe (verificável).

### Corrigido
- **Falso zero de cobertura.** Matéria com assuntos e **nenhum** `topico_id` gravado tinha cobertura desconhecida, não zero — reportar 0% diria "nada foi aprofundado" sobre uma matéria inteiramente aprofundada. Agora esse caso não afirma nada, e há teste que trava.
- A cobertura é calculada **depois** do cruzamento entre escopos: rodar antes dava 0% em `direitos-violacoes` e `servico-social`, cujo mapa está no cargo e os assuntos no `_COMUM`.

## [0.9.0] - 2026-07-30

### Adicionado
- **Aba Plano em toda matéria que tenha mapa em qualquer escopo**, com a origem dita quando o plano vem do escopo vizinho ("Plano do edital de …, esta matéria é compartilhada").
- **Visão Estudo com dois eixos**: por **tópico do edital** (na ordem do plano) e por prioridade. Assunto ainda sem vínculo vai para um balde visível — escondê-lo faria a matéria parecer menor do que é.
- **Aprofundamento sem fonte externa aparece como o que é**: a aba do assunto diz "Material próprio · Detalhado" (a cascata genérica faria title-case e sairia "Proprio"), a ficha mostra `Fonte: material próprio` sem a linha "No livro", e a seção `Onde conferir` toma o lugar dos trechos-âncora. Verificado de ponta a ponta, com as duas versões do mesmo assunto lado a lado.
- **"material próprio" não conta como fonte.** Ele ocupa o campo `fontes:` porque o template precisa preencher algo, mas é a declaração de que NÃO há fonte externa — contá-lo fazia o card anunciar "2 fontes" num assunto com uma norma e um texto escrito do zero.
- `materia_id` e `topico_id` lidos do frontmatter: o join entre mapa e aprofundamento passa a ser por id, e não por nome de pasta.

### Corrigido
- **`mapa_em` era dado morto**: gravado e nunca lido, então a matéria do comum aparecia sem aba Plano mesmo com o plano existindo no cargo — exatamente o caso de "Direitos e Violações (EDAS)". Agora o mapa é **anexado**, não só apontado. No vault real isso já leva o BB de 2 matérias sem plano para zero.
- **Casar por nome de pasta falhava em 5 das 9 matérias aprofundadas** — a mesma matéria é `direitos-violacoes` no aprofundamento e `direitos-violacoes-vulnerabilidades` no mapa, com três grafias do nome. `materia_id` resolve.
- **Dois seletores de aba na mesma página brigavam**: o JS alternava `.visao` no documento inteiro, então um segundo eixo dentro da Estudo desligaria a visão inteira. A troca de eixo é escopada ao contêiner.
- Mesma matéria mapeada em mais de um cargo passa a registrar os mapas extras, em vez de escolher um em silêncio.

## [0.8.0] - 2026-07-30

### Adicionado
- **Todas as subseções do tópico vão para a web.** O mapa de matéria escreve, por tópico, o literal do edital, os subtópicos derivados, o material recomendado, as pegadinhas da banca e a meta de questões. O coletor já lia as cinco desde a 0.7.0 — o `bloco_plano` usava só os subtópicos e **descartava o resto na renderização**. Agora tudo passa por `md2html`, então tabela do mnemônico vira tabela, negrito da lei aparece e wikilink do material vira link.
- **Divulgação progressiva por tópico**, com `<details>` nativo: o literal do edital e o checklist ficam à vista (o primeiro é a autoridade, o segundo é por onde se passa o olho); material, pegadinhas, meta e complementos ficam a um clique. Nativo porque abre sem JavaScript, imprime e é o que faz o Ctrl+F do Chrome saltar para dentro do tópico. Matéria com até 8 tópicos nasce aberta; acima disso, recolhida com botão **Expandir tudo** — o Firefox não expande na busca da página, e quem imprime quer o plano inteiro (o JS abre tudo no `beforeprint` e restaura depois).
- **O resumo da dobra conta o que há dentro** (`⚠️ 7 pegadinhas · 📚 3 materiais`). Dobra muda obrigaria a abrir 24 tópicos para achar o que interessa.
- **H3 fora do template deixa de ser descartado em silêncio.** `Leis-chave`, `Conceitos-chave / fórmulas`, `Referência legal` e os blocos mnemônicos 🧠 somam 50 blocos dentro de tópicos numerados do vault — o conteúdo que dá mais trabalho para escrever, e o que sumia. Entram como `extra`, com o rótulo do vault, e a geração **avisa no stderr** quais rótulos saíram do template.
- **URL nua vira link** no `md2html`. `- Questões: https://…` é o formato do "Material recomendado", e sem isso a linha chegava como texto morto justamente na seção cuja razão de existir é levar ao material.
- `md2html.converter(..., prefixo_id=)`, para converter trechos soltos da mesma página sem colidir `id`.

### Corrigido
- **Subtópicos sobrescritos: 57 itens em 5 tópicos não chegavam à página.** `secoes[chave] = texto` fazia o último bloco vencer, então um tópico com `### Subtópicos derivados — TEORIA` e `— LEI 8.662/1993` perdia o primeiro inteiro. Dava para ver: o tópico 2 de `servico-social` listava **1** subtópico enquanto o rodapé dizia **`0/22 itens do plano`** — a página se contradizia sozinha. Agora são 21, em 4 grupos rotulados.
- **O sufixo temático do bloco some do rótulo, não do dado**: `— LEI 8.662/1993 (DECORAR ARTIGOS)` vira o título do grupo no checklist. Sem ele, quatro listas distintas viravam uma só, sem dizer de quê.
- **Estado do checkbox preservado.** `- [x]` era descartado: item estudado ficava idêntico a não começado, enquanto o contador do rodapé dizia o contrário.
- **`#### ` dentro de um bloco de subtópicos não some.** O vault usa H4 para subdividir (`#### Proteção Social Básica (PSB) — ofertada no CRAS`); como a lista só recolhia bullets, o H4 sumia junto com a informação de a que parte cada item pertence.
- **Bolha só no que é marcável.** Bullet simples dentro de um bloco de subtópicos ganhava a bolha do cartão-resposta e parecia checkbox em aberto — a lista mostrava mais itens do que o contador conta. Pego contra o vault real, não pelo fixture: 2 tópicos misturam bullet e checkbox no mesmo bloco. Há teste que trava o invariante "bolhas == denominador do rodapé" em todos os tópicos.
- **Ordem dos itens dentro do bloco.** Varrer checkbox e bullet em dois passes juntava todos os checkbox antes de todos os bullets, embaralhando bloco misto.
- **O selo de prioridade do tópico tinha classe sem estilo.** `bloco_plano` emitia `.selo-aprof.nivel-alta|media|base` e o CSS só define `nivel-padrao|detalhado|ambos` — o selo saía sem estilo nenhum, e ainda emprestava a semântica de "profundidade do aprofundamento" para "prioridade do tópico". Agora é `.selo-prio.prio-*`, com as cores que já existiam em `.grupo-prioridade`.

### Modificado
- `mapa.topicos[].secoes` (dict chave→markdown) vira **`blocos[]`** (lista ordenada com `chave`, `rotulo`, `sufixo`, `markdown`, `itens`), e `subtopicos` deixa de ser `list[str]` para ser `list[{texto, feito, grupo}]`. `--modelo site-model.json` é contrato público: o builder continua aceitando o formato da 0.7.x, com teste.
- **`examples/site-model-exemplo.json` passa a representar o mapa** — trazia `"mapa": null`, ou seja, o contrato justamente da parte que mudou não estava representado. E passa a ser **exercitado por teste**: nada o construía, então podia divergir do código em silêncio, que é o defeito de fixture que este repositório já pagou duas vezes.
- Página de matéria de 24 tópicos: 25,6 kB → 69,8 kB. HTML do site inteiro: 4,6 MB → 5,1 MB, sem arquivo novo e sem requisição nova.

## [0.7.0] - 2026-07-30

### Modificado (deploy)
- **A porta publicada passa de 8088 para 8099** — a 8088 já estava em uso no host, e o `docker compose up` falhava com "address already in use".
- **`CONCURSOS_PORTA` passa a valer de fato.** O mapeamento do `docker-compose.yml` estava fixo em `"8088:80"` e a variável só alimentava as URLs impressas: trocar de porta exigia editar os dois lugares, e quem mexesse só na variável via o script anunciar um endereço diferente do que o container realmente publicava. Agora o compose usa `${CONCURSOS_PORTA:-8099}` e o `--setup` escreve um `.env` ao lado dele, que o compose lê sozinho. A porta interna do nginx segue 80.
- **`--setup` confere a porta antes de subir o container**, e diz qual processo a está ocupando. Antes o erro vinha do Docker, sem apontar o culpado nem o que fazer — e descobrir isso depois custava outra ida ao servidor.
- **`--setup` deixa uma página explicando que falta publicar.** Entre o setup e o primeiro deploy, `site/` está vazio: sem `index.html` e com autoindex desligado, o nginx devolve um **403 Forbidden** cru, que não diz o que fazer e parece container quebrado quando o container está perfeito (`/healthz` responde `ok` nos dois casos). O `rsync --delete` do deploy remove a página sozinho. Reproduzido com container real: vazio → 403, placeholder → 200, deploy → site.

### Adicionado
- **Escopos COMUM/cargo dentro do concurso.** A estrutura de saída espelha o vault: `{concurso}/{comum|cargo}/`. A capa lista os galhos, um card por escopo; a grade de matérias desceu para o hub do escopo, porque na capa o que se faz é escolher o cargo.
- **Todo o conteúdo abaixo do concurso**, por tabela declarativa `SECOES`: edital, cronograma, materiais (com as leis), histórico, sinergia, discursiva e títulos. Os `.md` viram documento; o resto vira **anexo copiado** — o nginx serve só `/srv/site`, então sem a cópia o link da lei funcionaria apenas na máquina do vault. Anexo mostra o tamanho antes do clique: há PDF de quase 10 MB.
- **Mapas de matéria na aba Plano.** Cada matéria é uma página com duas visões — Plano (o mapa do edital, com tópicos e subtópicos) e Estudo (os assuntos aprofundados). São ângulos do mesmo recorte; separá-los obrigaria a saber em qual procurar. Reusa o seletor em abas que já existia.
- **Pacote NotebookLM como página**, uma por assunto, com abas por aprofundamento e **botão de copiar** em cada prompt. É a única página do site cuja razão de existir é uma ação: o vault tem 92 pacotes prontos e um único assunto com mídia real — o gargalo não é ter o roteiro, é executá-lo.
- **Resolvedor global de wikilinks**, com três classes de alvo: página, artefato embutido (flashcards → âncora do quiz) e arquivo copiado (mídia, anexo). Contra o vault real, wikilinks mortos caíram de 96 para 22, e os 22 restantes apontam para mapas de outro cargo.
- Sumário lateral em documento com mais de 3 seções, reusando `.colunas`/`.lateral`. Há documento de 2.400 linhas; rolar 600 sem índice é o que faz voltar para o Obsidian.
- `mapa-aliases.json` **opcional** na pasta da matéria, para o link fino tópico→assunto que o slug não alcança. Ausente = sem links extras, nenhum palpite.

### Corrigido
- **O agrupamento por cargo nunca funcionou.** `cargo_de()` procurava o segmento `03-MAPAS` no caminho, mas o aprofundamento vive em `03-APROFUNDAMENTO`: a condição nunca casava e TODA matéria caía em `_GERAL`, deixando a capa sem agrupamento. A capa do BB passou de zero `<h2>` para os dois escopos. O teste existia e ficava verde porque o fixture montava os assuntos sob `03-MAPAS-MATERIAS`, caminho que a `concurso-aprofunda` não produz — fixture que inventa uma realidade que o gerador não gera é teste que se autoconfirma. Regressão em `test_escopo_vem_do_primeiro_componente_do_caminho`.
- **A varredura precisava inverter, não só ser renomeada.** `achar_materias()` partia de `rglob("assuntos")`, então a árvore era descoberta a partir da existência de aprofundamento — um escopo que só tem `01-EDITAL` (o `_COMUM` de qualquer concurso antes da Etapa 2) nunca era descoberto. `achar_escopos()` acha os galhos primeiro.
- **A mídia do assunto vinha do aprofundamento errado.** `midias` era herdada do principal, e a ordenação põe `detalhado` primeiro; o único assunto do vault com podcast, vídeo e mapa mental guarda os três em `padrao--pestana`, então o site anunciava "0 com áudio" numa matéria que os tinha. Presença passa a ser a união dos aprofundamentos. Regressão em `test_midia_do_assunto_e_uniao_dos_aprofundamentos`.
- **Matéria que só tem mapa deixa de ser descartada** — `coletar_materia()` devolvia None sem `assuntos/`, e no BB isso sumia com 7 das 8 matérias de cada cargo.
- **`md2html`, quatro lacunas:** `![alt](src)` casava a regex de link e saía como `!<a href=…>` (toda imagem quebrada); headings não tinham `id`, logo não havia âncora nem sumário; `[[alvo#seção]]` e o pipe escapado `\|` que a tabela markdown obriga — usado nos índices do BB — não eram reconhecidos, e o divisor de células partia o wikilink em duas.
- **`.wikilink-morto`** era emitido desde a primeira versão e nunca teve regra no CSS. Wikilink sem rótulo passa a exibir só o último segmento: os do SEDES usam caminho absoluto do vault, e o caminho inteiro como texto visível vazava `_COMUM` para 9 páginas.
- **Rebuild deixava lixo.** `construir()` só fazia mkdir, então pasta de layout anterior sobrevivia em `out/` e o `rsync --delete` não a removia, porque existe na origem. Limpeza escopada ao concurso, preservando irmãos e o `assets/`.
- **Navegação interna resolvia pelo índice de nomes**, que casa por basename com o primeiro registro vencendo — com `lingua-portuguesa` no comum e no cargo, o hub do cargo apontava para a matéria do comum e a própria ficava órfã. Link de navegação passa a ser explícito (`rota_irma`, `rota_anexo`); o índice fica só para wikilink. Foi o auditor de links que pegou.
- `iniciarSeletorAprof` tratava só o **primeiro** `.seletor-aprof` da página, o que impediria as abas de visão de coexistirem com as de aprofundamento.

### Modificado
- **`construir()` virou dois passos:** `montar_rotas()` decide onde cada página mora, e só depois vem a renderização. É pré-requisito do resolvedor global — para virar `href`, um wikilink precisa da URL de páginas ainda não geradas.
- **Prefixo sai da rota**, não da contagem manual: `pagina()` recebe a rota da própria página e as trilhas usam `relativo()`. Os literais `"../"`, `"../../"` e `"../../../"` espalhados pelos templates faziam cada nível de pasta novo custar um acerto à mão em cada template.
- **Card de assunto redesenhado:** selo só para mídia que EXISTE (a grade dos 8 tipos com ausentes fica na página do assunto, onde "falta gerar" é acionável); fim da redundância entre "1 fonte", "Padrão + Detalhado" e "2 versões" — com uma fonte, a contagem repetia o nível.
- **O progresso do mapa é contado separado do aprofundamento.** Os 24 mapas do vault somam 2.220 checkboxes, nenhum marcado; misturá-los com os ~200 do aprofundamento apagaria a única barra que significa algo.
- **`✍️ Meu resumo` não é publicado** — vazio em 16 dos 24 mapas e, nos outros 8, exercício de preenchimento com tabela de células vazias. Faz sentido no Obsidian, onde se escreve; nenhum na web.
- Seção com um documento só e sem anexo **é** o documento: índice que lista um item é página inútil e gerava caminho redundante (`titulos/titulos/`).
- **O link tópico→assunto só sai com casamento exato.** Dos 203 tópicos dos 24 mapas, ~18% casam por slug: um tópico do SEDES explode em 7 assuntos, nas matérias de "lei como fonte" o assunto É uma norma (N:M), e 9 assuntos de Português foram reaproveitados do BB. Sem casamento a página **não afirma nada** — o falso negativo (tópico lido como "sem aprofundamento" quando existe com outro nome) esconderia trabalho feito.
- `.grupo` extraído dos três cabeçalhos duplicados (órgão, escopo, prioridade) — menos CSS do que antes. Nenhuma variável de cor nova.
- Removidos o parâmetro morto `origem_dir` de `pagina_assunto` e o atalho `status` do assunto.
- **`prioridades_do_guia()` mantida, com pendência registrada.** Ela procura arquivos `00-GUIA-*` que **não existem em nenhum dos dois concursos** (a prioridade real vem do frontmatter, em 20 arquivos), mas há teste que a exercita de propósito — apagar a função exigiria apagar o teste. O certo é reapontá-la para o mapa de matéria, que é onde a "ordem sugerida" de fato vive; fica para uma próxima versão.
- `cargos[]` segue no modelo como **alias** de `escopos[]`, porque `--modelo site-model.json` é contrato público documentado.

### Testes
- 73 (eram 42), com regressão para cada defeito acima.
- **Auditor de links reforçado.** A regex usava `([^"#?]+)`, o que fazia **não casar nada** quando a URL tinha `#` — link com âncora passava sem verificação, e uma classe inteira de link ficaria fora de cobertura justamente quando as âncoras passaram a existir. Agora confere que o `id` existe no destino, exige `index.html` em link de diretório e acusa página órfã, com contra-prova própria.
- Fixture reescrito para espelhar o vault: `{ESCOPO}/03-APROFUNDAMENTO/{materia}/` e as pastas numeradas, com teste barrando que alguém o enxugue.
- A forma do modelo e o caminho de saída passam por helpers (`_escopos`, `_materias`, `_dir_materia`, `_dir_assunto`), para mudança de estrutura não virar patch de 30 asserções.

## [0.6.0] - 2026-07-29

### Modificado (deploy)
- **O site passa a responder em `concursos.casa:8088`, na raiz** — não mais em `beelink.casa/concursos`. O `nginx.conf` serve `/`, o compose publica a porta 8088 e o `deploy.sh` usa o novo host. Não é mais preciso proxy reverso na frente.
- O caminho antigo `/concursos/<algo>` **redireciona para `/<algo>`** (rewrite, não return fixo), preservando deep links já salvos.
- `absolute_redirect off` + `port_in_redirect off`: sem isso o nginx montava o `Location` com a porta **interna** (`localhost/` em vez de `concursos.casa:8088/`) e todo redirect caía na porta errada. Verificado com container real.
- Variáveis do `deploy.sh` renomeadas de `BEELINK_*` para `CONCURSOS_*` (as antigas seguem aceitas como fallback), e a porta virou `CONCURSOS_PORTA`.
- Removida a redeclaração de `m4a` no bloco `types` — o `mime.types` do nginx já a cobre, e a duplicata gerava warning na inicialização.

> O gerador **não** precisou mudar: o site sempre usou links relativos, então funciona igual na raiz ou em subpath.

### Modificado
- Acompanha o identificador enxugado da `concurso-aprofunda` 0.4.0 (`{nivel}--{fonte}`, sem contador nem índice posicional; concurso no nome do arquivo). Os formatos anteriores continuam sendo lidos.

## [0.5.0] - 2026-07-29

### Adicionado
- Leitura do **novo padrão de pastas de aprofundamento** (`{assunto}/{nivel}--{N}f--f1-{fonte}/`), definido na `concurso-aprofunda` 0.3.0. Os layouts anteriores (`aprofundamentos/{id}/` e o legado plano) continuam sendo lidos — o site nunca deve quebrar por material que o usuário não migrou.
- `scripts/aprofundamento_id.py` — cópia sincronizada da convenção; teste de smoke falha se divergir da fonte em `concurso-aprofunda`.
- O coletor passa a derivar nível e fontes **do nome da pasta**, que é mais confiável que o frontmatter (material antigo pode não ter `nivel:`). Novos campos por aprofundamento: `rotulo`, `n_fontes_id`, `fontes_id`.

## [0.4.2] - 2026-07-28

### Corrigido
- Parser de frontmatter lia comentários inline do YAML junto com o valor, fazendo o nível `padrao` ser tratado como distinto e suprimindo o selo "Padrão + Detalhado".

## [0.4.1] - 2026-07-28

### Adicionado
- Selos nos cards de assunto indicando **quantas fontes** e **quais níveis** (Padrão / Detalhado / ambos), usando a bolha do cartão-resposta: meia = padrão, cheia = detalhado.

## [0.4.0] - 2026-07-28

### Adicionado
- Concursos agrupados por **órgão** no índice raiz.
- Suporte a **vários aprofundamentos por assunto**, com seletor em abas; mídias de cada aprofundamento isoladas em `media/<id>/`.

### Modificado
- Lê tanto a estrutura nova (`aprofundamentos/`) quanto o formato legado.

## [0.3.0] - 2026-07-28

### Adicionado
- **Tema claro/escuro** com preferência do sistema, memória da escolha e script anti-flash.
- **Índice raiz multi-concurso** com manifesto `.concurso.json` por concurso (deploy incremental não remove os demais).
- Assuntos agrupados por **prioridade** (alta/média/base).
- Seção **"Como a banca cobra"** antes da lista de assuntos.
- **Download** de todas as mídias e suporte aos 8 tipos do Estúdio do NotebookLM (áudio, vídeo, slides, mapa mental, infográfico, relatório, teste, tabela de dados).

### Corrigido
- Cores de texto fixas em hex quebravam o tema escuro (`strong` ficava quase invisível). Todas migradas para variáveis de tema, com teste de regressão.

## [0.2.0] - 2026-07-28

### Adicionado
- Subsistema B (`site_builder.py`) + `md2html.py`: geração das páginas (capa, matéria, assunto) com mídias embutidas.
- Quiz de flashcards interativo na página do assunto.

### Corrigido
- Prefixos relativos dos assets tinham um nível a mais — CSS e JS não carregavam nas páginas internas.

## [0.1.0] - 2026-07-28

### Adicionado
- Subsistema A (`site_collector.py`): varre a pasta do concurso e monta o `site-model.json`.
