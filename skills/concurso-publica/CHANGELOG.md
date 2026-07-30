# Changelog — concurso-publica

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

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
