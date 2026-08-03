# Changelog

Todas as mudanças notáveis da skill `concurso-prep` são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [1.10.0] - 2026-08-03

### Corrigido
- **O consumidor da bibliografia rodava ANTES do produtor.** A Etapa 5 (mapas) vinha
  antes da Etapa 6 (materiais), e o `materia-mapper` recebia a instrução de
  "reaproveitar `04-MATERIAIS/livros-recomendados.md`" — arquivo que ainda não tinha
  sido escrito. Ele então redigitava a obra de memória. As duas etapas trocaram de
  lugar: materiais é a 5, mapas é a 6, e o catálogo vai **inline** para o mapper.
- **O catálogo era gravado sempre em `_COMUM`, por caminho escrito à mão.** Agora
  vale a mesma regra de `cargos_ids[]` dos mapas: matéria de um cargo só tem catálogo
  no cargo. Media-se, no vault, 5 dos 7 escopos sem catálogo nenhum — e o do BB
  intitulado "Agente de Tecnologia", sem seção para as 3 matérias exclusivas do
  Agente Comercial (99 itens de material sem bibliografia correspondente).
- **O `material-collector` não tinha passo de pesquisa.** Tinha `WebSearch` no
  frontmatter e uma instrução de "identificar 1-3 livros consagrados" — sem query,
  sem fonte, sem critério. Passa a exigir no mínimo 2 buscas por matéria e
  confirmação de autor/editora/edição/ISBN em fonte primária (site da editora, Open
  Library/Google Books, biblioteca), com **piso de autor**: sem ele a entrada vai
  marcada como pendência dizendo o que se procurou. Era impossível distinguir "não
  encontrei" de "não procurei".
- **O retorno do collector eram só contagens.** `"livros_listados": 28` não permitia
  a nenhuma etapa posterior citar ou conferir a bibliografia — a raiz mecânica da
  divergência. Agora devolve `catalogos[].entradas[]` inteiras.
- Três contratos conflitantes sobre a mesma coisa: ISBN exigido em 3 lugares com 3
  redações; o `SKILL.md` afirmando que o `materia-mapper` não lê arquivo quando o
  frontmatter já dizia o contrário desde a 1.6.0; e `edital-resumo.md.tpl` com
  `04-Materiais` em CamelCase, wikilink que não resolve em filesystem case-sensitive.

### Adicionado
- **`scripts/material_id.py`** — fonte de verdade da identidade de um material: a
  âncora do catálogo (`^mat-pestana-gramatica`, block id do Obsidian), o conjunto
  canônico de prefixos e o casamento **exato ou nada** entre item de mapa e entrada.
  65 testes, todos com linhas literais do vault.
- **`assets/templates/livros-recomendados.md.tpl`** — o catálogo nunca teve template;
  nascia da prosa dentro do agent, sem contrato de formato versionado.
- **`check_material` no `validate_output.py`** — escopo com mapa tem catálogo, `Livro:`
  de mapa resolve para âncora existente, entrada sem autor está marcada como
  pendência, e prefixo fora do conjunto vira aviso (nunca erro: descartar item
  apagaria conteúdo escrito à mão). Rodado contra o vault, acusa exatamente os 7
  problemas que a auditoria mediu.

### Notas
- A auditoria de 03/08/2026 nos dois concursos: 473 itens de material nos mapas contra
  62 nos catálogos; interseção de 15,6% (BB) e 5,9% (SEDES); Pestana com 4 grafias e 3
  editoras contraditórias; 25 livros sem autor; 31 prefixos distintos; 2 dos 473 itens
  linkando para algo baixado.
- Testes: 62 -> 62 + **65** (`test_material_id.py`). O `test-all.sh` passou a rodar
  toda `test_*.py` da skill, não só `test_smoke.py`.

## [1.9.0] - 2026-08-01

### Adicionado
- **`scripts/migrar_meta.py`** — completa o `.meta.json` dos concursos já gerados, sem
  reexecutar a skill. A alternativa seria rodar tudo de novo, e ela é pior: o ganho é
  ~90% metadado, mas a reexecução **regeneraria a prosa dos mapas** (11 do SEDES e 3 do
  BB têm resumo escrito) e custaria até 20 subagents. O que falta é dado, e dado se
  corrige cirurgicamente.

  Cada campo vem de uma fonte que já existe no próprio meta:

  | campo | de onde |
  |---|---|
  | `cargos_validados[]` | `cargos_multi` (SEDES) / `cargos_gerados` (BB) |
  | `estrutura_prova_por_cargo` | `cargos_multi[].titulos`/`.discursiva` |
  | `edital_hash` | recalculado do texto, por `edital_hash.py` |
  | `materias[].cargos_ids` | `materias_por_cargo` / `cargos_gerados[].especificos` |
  | matérias ausentes | anexo do edital, **conferido** contra os mapas |

  Medido nos dois concursos: SEDES ganha 3 `cargos_validados`, o
  `estrutura_prova_por_cargo` que corrige o `titulos: false` mentiroso, o hash certo e
  `cargos_ids` em 5/5; o BB ganha as **3 matérias do AGENTE-COMERCIAL** que não existiam
  no meta — sem elas, reconciliar aquele cargo o perderia inteiro — e `cargos_ids` em 10/10.

### Corrigido (defeitos do próprio migrador, achados no dry-run contra o vault real)
- **Rodapé de página entrando no meio do tópico.** O número da página vem em linha
  própria antes do form feed e, ao juntar as linhas, virava conteúdo: o item 1 de
  Conhecimentos de Informática saía como `ambiente Linux (SUSE 34 SLES 15 SP2)`.
- **A seção não terminava no anexo seguinte**: o último tópico de Vendas e Negociação
  engolia `ANEXO IV - CRONOGRAMA`, porque o cabeçalho do anexo usa travessão e não
  dois-pontos.
- **`_COMUM` não quer dizer "todos os cargos"**, e sim "mais de um" — a Etapa 5 manda
  gravar ali a matéria que vale para 2 de 3. Tratar como "todos" dava falso alarme no
  `fundamentos-suas` do SEDES, que é só do TDAS.
- **Conferência ausente virava silêncio**: matéria extraída do edital sem mapa para
  cruzar passava sem aviso. Agora é pendência — é a mesma armadilha do check que
  "passava" por não encontrar nada.
- `--json` era poluído pelo aviso de dry-run e não era JSON válido.

### Corrigido (dois defeitos que só apareceram ao APLICAR no vault)
- **As matérias novas saíam sem `materia_id`** — logo, sem o campo que as liga ao
  aprofundamento e ao site. O id não é derivado do nome (isso seria re-derivar
  identidade, o que o ADR proíbe): sai do `materia_id` que o mapa correspondente já
  declara. Sem mapa de onde tirá-lo, é pendência.
- **`tipo: 'especificos'`** é vocabulário legado e não existe no schema. Passa a ser
  normalizado pelo escopo: `especificos_comuns` quando vale para mais de um cargo,
  `especificos_cargo` quando é de um só.

### Notas
- 9 testes novos; 62 na suíte da skill.
- A conferência das matérias extraídas **rodou de verdade** nos três casos do BB:
  14/14, 4/4 e 17/17 tópicos entre edital e mapa.
- Fora do escopo deste script, e ainda pendentes no BB: os dois `00-INDICE.md` que a
  Etapa 10.1 gera. São conteúdo, não metadado.

## [1.8.1] - 2026-08-01

Higiene: os itens pequenos que o diagnóstico levantou e que, somados, eram o que fazia
duas execuções da skill produzirem estruturas diferentes.

### Corrigido
- **O `SKILL.md` se contradizia sobre o cronograma.** A Etapa 4.5 mandava gravar o
  `cronograma-oficial.md` em `{CARGO}/02-CRONOGRAMA/`; a árvore de "Estrutura gerada"
  o punha em `_COMUM/01-EDITAL/`, e é o que o vault faz. Resolvido a favor da árvore,
  com o motivo escrito: o cronograma oficial é **do concurso** (inscrição, prova,
  resultado) e igual para todos os cargos — repeti-lo por cargo seria duplicar. O que é
  por cargo é o `cronograma-macro.md`.
- **O nome do arquivo da discursiva não era fixo**: a Etapa 9.6 só dizia a pasta, então
  o SEDES gerou `guia-discursiva.md` e o BB `discursiva.md`. Fixado em
  `guia-discursiva.md`. (Arquivos já existentes não são renomeados — renomear quebra
  wikilink e progresso.)
- **O log de validação ignorava o item 15**: `validate_output.py` gravava sempre na raiz
  de `.logs/`, e o vault real acumulou **43 `validacao-*.json` soltos**, sem como saber
  de qual concurso era cada um. Passa a gravar em `.logs/{CONCURSO}/`.

### Modificado
- **`cronograma-semanal.md.tpl` deixou de ser órfão.** Estava listado nos templates e
  nunca foi produzido em nenhuma das duas execuções reais. Em vez de apagá-lo — são 55
  linhas úteis, com uma matéria foco por semana e checkboxes, e o modo previsto já fala
  em "Semana 1, Semana 2…" — ganhou uso declarado como **Etapa 4.6 opcional**, gerada
  quando o usuário pedir esse nível de detalhe. Sem mudança na saída padrão.

### Notas
- 1 teste novo; 53 na suíte da skill.
- Fica **pendente e é do usuário**: `SEDES_2026/.meta.yml.arquivado`, resíduo da migração
  para `.meta.json`. É arquivo no vault, e a skill não escreve no vault sem confirmação.

## [1.8.0] - 2026-08-01

### Adicionado
- **Etapa 9b — avaliação de títulos, por cargo.** O artefato `08-TITULOS.md` já era
  publicado pelo site (o `site_collector` reconhece `08-TITULOS` e trata arquivo solto,
  não só pasta) e já existia no vault, feito à mão. O que faltava era o **produtor**:
  nenhuma etapa da skill gerava. A etapa extrai do edital o quadro de atribuição de
  pontos (alínea, título, pontuação, máximo), o teto total, as regras de entrega e monta
  o checklist de documentos, separando titulação acadêmica de experiência profissional —
  que costuma ser a alínea de maior peso e a que exige mais tempo de coleta.
- **A condição é POR CARGO**, lida de `estrutura_prova_por_cargo[{CARGO}].titulos.presente`
  com queda para o campo agregado. Títulos raramente valem para todos: no SEDES o edital
  os dá **exclusivamente ao EDAS**.
- `assets/templates/titulos.md.tpl`, modelado no artefato real do vault.
- **`check_titulos` no validador, nos dois sentidos** — cargo elegível sem
  `08-TITULOS.md`, e arquivo existindo em cargo que o meta diz não ter títulos. Cada
  lado denuncia um erro diferente. Rodado contra o SEDES real, o segundo caso dispara na
  hora: o ASSISTENTE-SOCIAL tem o arquivo e o `.meta.json` grava um único
  `titulos.presente: false` com a ressalva em prosa — o campo afirma o falso para um dos
  três cargos, e é campo que alimenta o diff estrutural da retificação.

### Notas
- 4 testes novos; 52 na suíte da skill.
- A etapa não inventa pontuação: o quadro é dado do edital, e alínea que não ficar clara
  vira pendência para conferência humana.

## [1.7.0] - 2026-08-01

Segunda metade da revisão comportamental: reconciliação, coleta e o subagent que não
conseguia ler o próprio template. O fluxo de reconciliação **nunca tinha rodado** — não
existe nenhum `V2`/`V3` no vault — então ele foi executado ponta a ponta em sandbox,
sobre cópia do SEDES e do BB, nos dois casos (A: previsto → oficial; B: oficial →
retificado). Um defeito novo apareceu só por causa disso, e está abaixo.

### Corrigido
- **A reconciliação multi-cargo era cega.** `diff_editais.py` lia apenas `materias[]` e
  não conhecia `materias_por_cargo`. Medido no SEDES real: removendo 3 tópicos da matéria
  específica do ASSISTENTE-SOCIAL, o diff reportava **0 removidos** — num concurso de 3
  cargos, mudança em 2 deles passava em silêncio. Agora roda **por cargo** (item 8), lê
  `materias[].cargos_ids` e `materias_por_cargo`, aceita `--cargo`, e avisa quando um
  cargo é criado ou extinto entre as versões.
- **O diff estrutural não via vagas nem salário** — os campos que, junto com as datas,
  são o que retificação mexe (B.4). Ele procurava `vagas_ac`/`salario` na raiz, e o
  `.meta.json` do SEDES guarda em `cargo.vagas_imediatas`/`cargo.remuneracao`. Achado ao
  rodar o CASO B: mudar as vagas de 133 para 150 não produzia mudança nenhuma. Passa a
  procurar nos dois lugares e a comparar **por cargo**, porque uma retificação pode mexer
  nas vagas de um só.
- **O cabeçalho do relatório era fixo** em "Previsto (V1) vs Oficial (V2)", inclusive
  numa retificação — o B.5 manda ajustar.
- **`edital_hash` era regra sem executor.** O `SKILL.md` define, desde a 1.3.0, o SHA-256
  do **texto extraído**; sem script, cada execução escolheu: o SEDES gravou o hash dos
  **bytes do PDF**, o BB gravou o do texto (mais um `edital_pdf_sha256` que o SKILL não
  definia). No SEDES, portanto, o R.0.2 nunca reconhecia "edital idêntico", e um mesmo
  edital re-salvo viraria `V3-RETIFICADO` espúrio. Novo `scripts/edital_hash.py`, com
  canonicalização definida (CRLF, espaço no fim de linha, linhas em branco no fim) — sem
  ela o hash muda com detalhe irrelevante. Diagnostica o caso do SEDES por nome e recusa
  hashear PDF-imagem, porque texto vazio colide entre editais diferentes.
- **`fetch_lei.py` gravava casca e reportava sucesso.** Com o Planalto sem responder, ele
  avisava "texto extraido muito curto", **gravava o `.md` só com cabeçalho (384 chars),
  imprimia `OK md:` e saía com `rc=0`** — o arquivo entrava no vault com cara de lei
  baixada. Agora abaixo de `MIN_CHARS_LEI` (800) **nada é gravado** e o exit é 5.
- **O `materia-mapper` não tinha `Read`** (`tools: WebSearch, Write`) e o Passo 6 da spec
  dele mandava usar `assets/templates/mapa-materia.md.tpl` — um arquivo que ele não
  conseguia abrir. O template estava morto para o único agent que deveria consumi-lo, e o
  frontmatter era improvisado a cada execução: três execuções seguidas produziram três
  formatos diferentes (`questoes_estimadas: 8-10`, `questoes_estimadas: 4`,
  `estimativa_questoes: "4-6"`), nenhum igual ao template, nenhum com `cargos:`. Ganhou
  `Read`, mais a instrução explícita de que os tópicos literais vêm inline e de que ir à
  web buscá-los não é alternativa.
- **Os templates não traziam o frontmatter que o vault exige.** Só o `mapa-materia` tinha
  `tipo:`; nenhum tinha `status:`/`data:`. Os campos existiam nos arquivos do vault
  porque foram inventados na hora — daí o mesmo artefato ter saído `tipo: mapa-materia`
  num concurso e `tipo: documentacao` no outro. Os 12 templates passam a trazer `data`,
  `data_atualizacao`, `tipo` e `status`, com valores do vocabulário canônico do vault.
- **`tipo: reconciliacao` não existe no vocabulário do vault** (divergência pré-existente
  no `diff-reconciliacao.md.tpl`). Sem consumidor e sem nenhuma nota usando; passou a
  `documentacao`.

### Notas
- 9 testes novos; 48 na suíte da skill.
- O que a reconciliação ponta a ponta mostrou e **não** é código: no `.meta.json` do
  SEDES, todo o conteúdo específico de um cargo é **um único "tópico"** de milhares de
  caracteres. O diff funciona, mas a granularidade dele é a do meta — remover "um tópico"
  ali apaga o programa inteiro do cargo. É consequência da granularidade grosseira do run
  de 15/07, e a decisão de identidade declarada abre o caminho para corrigir sem quebrar
  vínculo.

## [1.6.0] - 2026-08-01

Revisão comportamental da skill: em vez de reler a documentação, rodou-se a 1.5.0 em
sandbox contra o edital do SEDES que o vault já tinha processado em 15/07. O que os
dois resultados não batendo revelou está abaixo.

### Adicionado
- **`assets/schema-edital.json` — contrato único da Etapa 2.** Até aqui o `SKILL.md`
  documentava uma `materias[]` plana e o `agents/edital-parser.md` documentava três
  chaves (`materias_gerais`, `materias_especificas_comuns`, `materias_especificas_cargo`).
  Dois documentos do mesmo repo, contratos incompatíveis, e a conversão de um para o
  outro ficava com o modelo, sem regra escrita: é a raiz de o `.meta.json` do SEDES e o
  do BB terem saído com schemas diferentes entre si e do documentado — e de o BB ter
  ficado sem o conteúdo programático de um cargo inteiro. Os dois documentos agora
  **referenciam** o schema em vez de descrever cada um o seu.
- **`scripts/materia_id.py` — fonte de verdade da identidade de matéria.** Resolve o
  `materia_id` **reusando o que já está declarado no `.meta.json`** em vez de
  re-derivar; id novo é proposta e sai com código 2, exigindo confirmação. Contra os 20
  títulos reais do SEDES: 6 resolvidos (2 deles por similaridade — o parser de hoje
  escreveu "Conhecimentos do **Distrito Federal**…" onde o de 15/07 tinha "do **DF**…",
  e o id sobreviveu com os 58 assuntos que pendem dele), 14 pedindo confirmação.
  Decisão em `identidade-da-materia-declarada-e-persistida`.
- **`scripts/validate_parsed.py`** — valida a saída da Etapa 2 contra o schema e **para
  o fluxo**. Era o executor que faltava: regra sem executor é regra que cada execução
  interpreta do seu jeito. Contra as saídas reais acusa 15 violações na do parser e 11
  no `.meta.json` do BB. Checador em stdlib, com uma inversão deliberada: **toda
  palavra-chave usada no schema tem de estar implementada, senão o script falha alto** —
  checador parcial silencioso é a doença que esta versão conserta.
- Checagens de coerência que o JSON Schema não expressa: cargo validado sem nenhuma
  matéria, `cargos_ids` apontando para cargo inexistente, `materia_id` repetido, modo
  oficial sem `prova_data`.

### Corrigido
- **`check_soma_questoes` passava por vacuidade — e o SEDES era o caso.** O regex só
  casava inteiro único, mas a estimativa honesta é uma **faixa** (o edital não distribui
  questões por matéria), e era assim que os 9 mapas do SEDES escreviam: `~14 a 16
  questões`. Nenhum casava, o check abortava com `INFO` e reportava OK. O concurso onde
  a soma "passava" era o único onde ela nunca tinha sido calculada. Agora o regex aceita
  faixa, a soma compara o total com um **intervalo**, e mapa sem estimativa é
  **problema**, não `INFO`. Com isso o SEDES revela uma divergência real que estava
  invisível: os mapas do ASSISTENTE-SOCIAL estimam 76-90 questões numa prova de 60.
- **`check_wikilinks` não conhecia a raiz do vault**: os 19 "links quebrados" do SEDES
  apontavam para três PDFs que **existem** em `40_RECURSOS/LIVROS/`, fora da pasta do
  concurso. O concurso fechava em exit 1 por problema nenhum — e validador que dá alarme
  falso deixa de ser lido. Ganhou `--vault-root`, com auto-detecção via `.obsidian/`.
  SEDES caiu de 19 problemas para 1 (o real, acima).
- **Mapa órfão deixou de ser `INFO`**: mapa que não corresponde a nenhuma matéria do
  `.meta.json` é conteúdo programático perdido. Foi assim que as três matérias do
  AGENTE-COMERCIAL do BB ficaram fora do meta, avisadas só por uma linha que não contava
  como problema. O BB passa de 2 problemas para 7, todos legítimos.
- **A Etapa 5 roteava pelo campo errado**: `cargos[]` traz o nome legível ("EDAS Serviço
  Social") e `cargos_ids[]` traz o slug. Seguida à risca, a regra criava a pasta
  `EDAS Serviço Social/03-MAPAS-MATERIAS/`, com espaço e acento, contra a convenção
  UPPERCASE que o próprio validador checa.
- **`check_structure` não exigia o que a Etapa 10.1 promete**: `00-INDICE.md` por pasta
  (o SEDES gerava, o BB não, e nada acusava) nem `_COMUM/03-MAPAS-COMUNS` em concurso
  multi-cargo.
- **`estrutura_prova` não era por cargo**, e o meta afirmava o falso: o edital do SEDES
  dá títulos exclusivamente ao EDAS, e o `.meta.json` grava `titulos.presente: false`
  com uma observação em prosa — errado para um dos três cargos, num campo que alimenta o
  diff estrutural da retificação. Documentado `estrutura_prova_por_cargo`.
- **O nome da pasta do cargo vinha do texto digitado em `--cargo`**, então dependia de
  como a pessoa escrevia (`"TDAS Agente Social"` → `TDAS-AGENTE-SOCIAL`, enquanto o vault
  usa `AGENTE-SOCIAL`). Passa a vir de `cargos_validados[].sigla`.
- **A Etapa 5 mandava passar os tópicos ao `materia-mapper` sem dizer que tem de ser
  inline.** O agent declara `tools: WebSearch, Write` — ele **não lê arquivo**, e o modo
  de falha observado é ir à web reconstruir os tópicos do edital a partir de blog de
  cursinho.
- **Fixture que inventava o que o gerador não produz**: o fixture base criava dois mapas
  sem matéria correspondente — coisa que a skill nunca gera — e era isso que fazia o
  teste de cobertura conviver com mapa órfão sem reclamar.

### Notas
- 12 testes novos, um por defeito, com a saída real do run de 01/08 como fixture.
- O `materia-mapper` continua sem `Read` e o `fetch_lei.py` continua gravando `.md` de
  casca com `rc=0`; o `diff_editais.py` continua cego a `materias_por_cargo`. Ficaram
  para a 1.7.0.

## [1.5.0] - 2026-07-30

### Modificado
- **Levantamento de material com piso, e por tópico.** O `material-collector` pedia "1-3 livros" e nada para o resto; passa a exigir, por matéria, livro com autor/editora, fonte gratuita, plataforma com filtro da banca e — em matéria de legislação — a **norma oficial**, além de registrar o que **não** achou. O `materia-mapper` pedia uma tripla fixa Livro/YouTube/Questões por tópico; passa a pedir o material **daquele tópico**, reaproveitando a bibliografia da matéria em vez de reinventá-la, com a norma como fonte primária quando o tópico for jurídico.

## [1.4.0] - 2026-07-30

### Corrigido
- **Matéria comum a vários cargos era mapeada uma vez POR CARGO.** A Etapa 5 tinha destino único (`{CARGO}/03-MAPAS-MATERIAS/`), então num concurso multi-cargo a mesma matéria virava N arquivos quase idênticos — no BB, 5 matérias × 2 cargos = 10 onde deviam existir 5 — e editar um exigia lembrar do gêmeo. Pior: o `_COMUM/03-MAPAS-COMUNS/` que o README, o `SETUP-VAULT.md` e o `site_collector.py` leem **nunca era escrito pela skill**. O consumidor lia o que o produtor não produzia, e o sintoma visível era matéria aprofundada aparecendo no site sem aba Plano. Agora a Etapa 5 roteia por `cargos[]`: mais de um cargo vai para `_COMUM`, um cargo só fica no cargo.
- **O validador não checava se toda matéria tem mapa** — nunca lia `materias[]`. E `check_soma_questoes` era estruturalmente cego ao buraco: soma os mapas que existem e aborta com `INFO` quando não acha nenhum, de modo que **zero mapas gerados passava como OK**. Novo check `cobertura_mapas`, que lê `materias[]` **e** `materias_por_cargo` (nenhum dos dois é completo sozinho: no SEDES o primeiro só traz um cargo; no BB o segundo não existe e faltam 3 matérias).

### Adicionado
- **`materia_id`** no contrato do `edital-parser` e no frontmatter do mapa: slug estável e curto, derivado do núcleo do nome ("Fundamentos, Organização, Gestão e Marcos Operacionais do SUAS" → `fundamentos-suas`). É o identificador que liga mapa, aprofundamento e site — sem ele o join volta a ser por nome de pasta, que falhava em 5 das 9 matérias do vault real.
- **`cargos[]`** por matéria, que é o que decide o escopo do mapa. O vocabulário existia (`tipo: especificos_comuns`) e não era consumido por nada.
- `scripts/aplicar_materia_id.py` e `scripts/aplicar_materia_id_meta.py`: gravam o `materia_id` no frontmatter dos mapas e nas matérias do `.meta.json`. São as outras duas pernas do vínculo — com o id só no assunto, mapa e aprofundamento continuam sem se encontrar, e o validador segue derivando o id do nome completo do edital, que nunca casa com o slug curto do arquivo. Dry-run por padrão; ambiguidade vira pendência em vez de escolha no palpite.
- `scripts/consolidar_mapas_comuns.py`: junta em `_COMUM/03-MAPAS-COMUNS/` os mapas já duplicados, reescrevendo os wikilinks (os índices apontam pelo caminho completo). Dry-run por padrão; gêmeos que divergem viram pendência em vez de escolha no palpite.

## [1.3.1] - 2026-07-29

### Adicionado
- `diff_editais.py` aceita a **pasta do concurso** além do arquivo de metadata. Passar a pasta é o uso natural — é o que a skill tem em mãos — e antes estourava `IsADirectoryError`.

### Corrigido
Quatro defeitos no `validate_output.py`, todos encontrados ao rodá-lo contra os concursos reais do vault — onde acusava **220 e 317 "problemas"** que não existiam:

- **Crash com `.meta.yml`**: o YAML converte `prova_data` para `datetime.date`, e o `strptime` só aceita `str` — o validador morria com `TypeError` antes de terminar. Agora aceita `date`, `datetime` e `str`.
- **Soma de questões contava metas de estudo**: o regex casava `Meta\n- [ ] 20 questões de treino` do checklist, somando **3769** questões numa prova de 70. Agora só o campo `Estimativa` conta.
- **Soma não considerava multi-cargo**: as matérias de `_COMUM` valem para todos os cargos, mas os mapas de todos eram somados juntos — qualquer concurso multi-cargo acusava divergência. Agora soma **por cargo** (`_COMUM` + específicas) e reporta o cargo no diagnóstico.
- **Wikilinks davam falso positivo**: (a) só arquivos `.md` eram indexados, então todo link para mídia (`.m4a`, `.png`, `.pdf`) aparecia como quebrado; (b) o regex não tratava o pipe **escapado** (`\|`) usado em tabelas, e o alvo capturado saía com a barra — 74 falsos positivos num concurso. Backups `.bak.md` também deixaram de ser varridos, e mídia ainda não baixada do NotebookLM passou a ser tratada como pendência esperada, não defeito.

Com as correções, `SEDES_2026` fecha em **0 problemas** e `BB_2027_PREVISTO` em **2** — estes reais: os mapas estimam 80 e 90 questões para provas de 70.

Cada correção tem teste de regressão.

## [1.3.0] - 2026-07-15

### Adicionado
- **Leis em Markdown E PDF** (`scripts/fetch_lei.py`): baixa a lei da fonte oficial (HTML) e gera os dois formatos — `.md` (com frontmatter Obsidian, capítulos/artigos realçados, link para a fonte) e `.pdf` (via weasyprint, com fallback para reportlab a partir do texto). Resolve o problema de o Planalto/SINJ-DF servirem HTML e não PDF. Parâmetro `--formatos-lei md,pdf` e `defaults.formatos_lei` no config.
- **Suporte a RETIFICAÇÃO de edital** (item 4): `--reconciliar` agora cobre dois casos, detectados automaticamente pelo estado da pasta — (A) previsto → oficial e (B) oficial → oficial retificado (gera `V3-RETIFICADO`, incrementando Vn em retificações sucessivas). Nenhuma versão anterior é sobrescrita.
- **Detecção automática de edital alterado** (item 21): `edital_hash` (SHA-256 do texto do edital) gravado no `.meta.json` permite reconhecer, numa reconciliação, se o edital fornecido é idêntico ou uma versão diferente/retificada.
- **Diff estrutural** (item 16): o `diff_editais.py` passa a comparar também vagas, salário, nº de questões, presença de discursiva e datas — não só o conteúdo programático.
- **Parâmetro `--ano-esperado`** (item 6) para controlar o ano da pasta no modo previsto.
- **Whitelist de domínios** (item 12) para provas/editais em `fontes_provas_editais` (com política `alertar`/`bloquear`), além de `--whitelist` no `fetch_lei.py`.
- **Suíte de smoke tests** (item 18) em `scripts/tests/test_smoke.py` (roda com pytest ou standalone; cobre slugify, diff e validate).
- **`requirements.txt`** (item 19) com dependências opcionais documentadas.
- **`.meta.json` de exemplo** (item 20) em `examples/previsto-reconciliacao/meta-exemplo/`.
- Comando `download-suspeito` e flag `--concurso` no `log_helper.py`.

### Modificado
- **Validador reescrito** (`validate_output.py`): corrigido para a convenção **UPPERCASE** (`_COMUM/01-EDITAL`), que quebrava 100% das validações (item 1); passou a checar soma de questões vs. total da prova, banner PROVISÓRIO no modo previsto e cronograma vs. data da prova (item 2); resolve wikilinks entre **pastas-irmãs** de versões (item 13).
- **Metadata em `.meta.json`** em vez de `.meta.yml` (item 11) — elimina a dependência de PyYAML no caminho principal (fallback legado mantido). O `.meta.json` passa a gravar o **conteúdo programático integral** (item 7), exigido pelo diff.
- **Matching do diff** aprimorado com contenção de tokens: temas expandidos (ex.: "SWOT e BSC" → "SWOT, BSC e mapa estratégico") são classificados como *alterados* em vez de removido+novo.
- **Reconciliação multi-cargo** (item 8) especificada: diff e migração de progresso por cargo; `_COMUM/` reconciliado uma vez.
- **Regra de migração de progresso** (item 17) definida por arquivo de matéria.
- **Logs por concurso** (item 15): `.logs/{ORGAO}_{ANO}/` em vez de `.logs/` global.
- **`install.sh`** passa a copiar `CHANGELOG.md` e `requirements.txt` (item 14) e alerta se `reportlab` faltar.
- **`description` da skill** ampliada com triggers de modo previsto e reconciliação/retificação (item 3).
- **Busca da pasta na reconciliação** por prefixo `{ORGAO}_*` + `.meta.json` (item 5), tolerando ano previsto ≠ ano oficial.
- Tratamento de `YAMLError` no `diff_editais.py` (item 10).

### Nota de proveniência
Esta versão consolida, sobre a base **1.1.0**, tanto os 13 ajustes planejados para a 1.2.0 (P0+P1+P2 baratos) quanto os 8 itens restantes (item 9 e P3). A 1.2.0 chegou a ser construída antes, mas seu pacote se perdeu num reset de ambiente; os ajustes foram reaplicados a partir do histórico de revisão e reunidos diretamente na 1.3.0.

## [1.2.0] - 2026-06-30 (consolidada na 1.3.0)

### Adicionado / Modificado
- P0 (1-3): validador UPPERCASE, checks de soma/banner/cronograma, description com triggers de previsto.
- P1 (4-8): retificação de edital, busca de pasta por prefixo, `--ano-esperado`, `.meta` com conteúdo integral, multi-cargo na reconciliação.
- P2 baratos (10, 11, 13, 14, 15): exceção YAML, `.meta.json`, wikilink entre pastas-irmãs, install copiando CHANGELOG, logs por concurso.

> Pacote não distribuído isoladamente; conteúdo incorporado à 1.3.0.

## [1.1.0] - 2026-06-05

### Adicionado
- **Modo `previsto`** (`--modo previsto`): permite iniciar a preparação para concursos esperados mas ainda sem edital publicado, usando o edital anterior como proxy de conteúdo.
  - Cronograma **relativo** (Semana 1, 2... sem datas), no template `cronograma-relativo.md.tpl`.
  - Pasta com sufixo `_PREVISTO` (ex: `TJDFT_2026_PREVISTO`).
  - Banner `⚠️ CONTEÚDO PROVISÓRIO` em todos os arquivos gerados.
  - `edital-proxy.pdf` em vez de `edital-original.pdf` no `_COMUM/01-EDITAL/`.
- **Reconciliação** (`--reconciliar`): quando o edital oficial é publicado, gera versão lado a lado preservando a prevista.
  - Renomeia a versão prevista para `_V1-PREVISTO` (intacta, progresso preservado).
  - Gera `_V2-OFICIAL` com datas reais.
  - Produz `00-DIFF-PREVISTO-VS-OFICIAL.md` com categorias 🟢 mantidos / 🔴 removidos / 🆕 novos / 🔀 alterados / 📅 datas.
  - Migração assistida de progresso (copia "Meu resumo" e checkboxes de tópicos idênticos para a V2).
- `scripts/diff_editais.py`: compara conteúdo programático de duas versões com matching por similaridade (limiar configurável, default 0.72).
- `assets/templates/diff-reconciliacao.md.tpl`: relatório de diff da reconciliação.
- `assets/templates/cronograma-relativo.md.tpl`: cronograma sem datas para o modo previsto.
- `examples/previsto-reconciliacao/`: caso de teste do ciclo previsto → reconciliação.
- Seções `previsto` e `reconciliacao` no `assets/config.yml`.
- Parâmetros `--modo` e `--reconciliar` documentados no SKILL.md e README.md.

### Modificado
- **Etapa 1 (Bootstrap)**: agora determina o modo de operação e define o sufixo de pasta conforme `oficial`/`previsto`/reconciliação.
- **Etapa 4 (Cronograma)**: ramifica entre cronograma com datas (oficial) e cronograma relativo por blocos (previsto).
- **Etapa 10 (Validação)**: passou a aceitar cronograma relativo e a checar presença do banner provisório no modo previsto.
- `agents/edital-parser.md`: recebe `modo`; no modo previsto, não propaga datas do edital antigo e registra `edital_proxy_ano`.
- README.md: nova seção "Modos de operação" e estrutura de projeto atualizada.
- SKILL.md: nova seção "Modos de operação", fluxo de reconciliação dedicado e variações de nome de pasta por estado.

### Notas
- A escolha de **versão lado a lado** (em vez de merge destrutivo) garante que nenhum progresso se perca caso o matching por similaridade do diff erre. A V1 fica como referência consultável.
- A qualidade do diff depende de o `edital-parser` extrair o conteúdo programático com granularidade consistente entre as duas versões. Editais antigos com formatação muito diferente podem gerar falsos "alterados" — ajustável via `limiar_similaridade` no config.

## [1.0.0] - 2026-05-29

### Adicionado
- Versão inicial da skill `concurso-prep`.
- Orquestrador `SKILL.md` com fluxo de 10 etapas:
  1. Bootstrap e validação
  2. Parse do edital (subagent `edital-parser`)
  3. Análise da banca (WebSearch)
  4. Cronograma macro adaptativo
  5. Mapas por matéria (subagents `materia-mapper` em paralelo)
  6. Coleta de materiais (subagent `material-collector`)
  7. Histórico do órgão (subagent `historico-researcher`)
  8. Sinergias (subagent `sinergia-finder`)
  9. Discursiva (condicional)
  10. Índices, validação e finalização
- 5 subagents especializados em `agents/`.
- 11 templates Markdown em `assets/templates/`.
- 4 scripts utilitários: `extract_edital.py`, `fetch_pdf.py`, `validate_output.py`, `log_helper.py`.
- `scripts/slugify.py`: nomes de pasta em UPPERCASE (slug sem acento).
- Suporte multi-cargo (pasta única com `_COMUM` + subpastas por cargo).
- Cronograma adaptativo por dias restantes (4 perfis: >180, 90-180, 30-90, <30 dias).
- Política de download: baixa leis (Planalto/SINJ-DF) e provas anteriores; nunca baixa livros (copyright).
- Idempotência com preservação de arquivos editados manualmente (hashes em `.meta.yml`).
- Logs simples (tempo, falhas, pendências, downloads falhos).
- Validação automática pós-geração (placeholders, wikilinks, aritmética de questões, datas, PDFs).
- `install.sh` (instalação global/local/uninstall).
- `examples/sedes-2026-mock/`: caso de teste do modo oficial.

[1.1.0]: #110---2026-06-05
[1.0.0]: #100---2026-05-29
