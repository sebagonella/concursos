# Arquitetura

## Visão geral

O projeto é uma coleção de skills do Claude Code que produzem material de estudo dentro de um vault Obsidian. Nenhuma delas é um serviço rodando: são **instruções + scripts** que o Claude Code executa sob demanda.

Três etapas encadeadas, cada uma consumindo a saída da anterior, mais uma camada
opcional sobre a segunda:

1. **`concurso-prep`** — o edital vira a estrutura de estudo no vault.
2. **`concurso-aprofunda`** — o livro de referência vira assunto aprofundado, com flashcards e o pacote do NotebookLM.
3. **`concurso-publica`** — o vault vira site estático, servido por Docker na rede doméstica.
4. **`concurso-notebooklm`** — camada **opcional** que executa os pacotes do NotebookLM. Ver "NotebookLM manual, automação como camada opcional".
5. **`concurso-afere`** — mede o material contra a **prova real**. É a única etapa que olha para trás: com o caderno e o gabarito oficial, apura quantas questões o conteúdo escrito responde, compara os níveis `padrao` e `detalhado` e aponta o que corrigir. O script prepara o determinístico (versão do caderno, faixa de questões, gabarito, casamento de matéria) e **o agente julga** — nota que script inventa é nota que não vale.

## O fluxo completo, do edital ao site no ar

O diagrama é renderizado no [README](../README.md#o-fluxo-do-edital-ao-site-no-ar)
— fica onde quem chega ao repositório o vê primeiro. A fonte é
[`fluxo-concurso.mmd`](fluxo-concurso.mmd).

Duas coisas no diagrama merecem nota, porque não são escolha estética. A **espinha é
linear** — uma aresta entre etapas consecutivas — e o vault aparece em **três
estados** em vez de uma caixa única com setas entrando e saindo de todo lado: com
fan-out (`a --> b & c`) e cross-links pontilhados, o layout automático do Mermaid
embaralha a ordem de leitura e a Etapa 3 acaba desenhada acima da Etapa 2. Já os
links `~~~` dentro da Etapa 1 são **invisíveis, só de posicionamento**: os quatro
subagents rodam em paralelo, mas sem nenhuma aresta o Mermaid empilha todos no
mesmo rank e a caixa sai alta e vazia.

## Padrão comum às skills

Cada skill segue a mesma anatomia:

- **`SKILL.md`** — o orquestrador. Frontmatter (`name`, `version`, `description` com triggers de ativação) + o fluxo em etapas numeradas que o Claude executa.
- **`scripts/`** — utilitários Python determinísticos (parsing, matching, geração de arquivos, validação). Tudo que *não* depende de julgamento fica aqui, para ser testável.
- **`assets/templates/`** — templates `.md.tpl` com placeholders `{MAIUSCULO}`.
- **`agents/`** (opcional) — subagents especializados, quando o trabalho se beneficia de paralelismo (a `concurso-prep` usa 5).
- **`scripts/tests/test_smoke.py`** — suíte que roda standalone, sem pytest.

### Divisão de trabalho: script vs. agente

Princípio central: **o script monta o arcabouço; o agente preenche o julgamento.**

O `build_subject_md.py`, por exemplo, cria o arquivo do assunto com a localização no livro e as seções vazias marcadas com placeholders. Quem escreve o resumo, escolhe as citações e identifica as pegadinhas é o Claude, na etapa 5 do fluxo. Isso mantém os scripts testáveis e o conteúdo de qualidade.

## Decisões de projeto

### Uma skill por ciclo de vida, não uma só

Cada skill tem responsabilidade e ciclo de vida próprios: `concurso-prep` roda uma vez por edital (e de novo em retificações); `concurso-aprofunda` roda por matéria/livro, quantas vezes for preciso; `concurso-publica` roda a cada vez que se quer republicar o site; `concurso-notebooklm` roda sob demanda, quando se quer gerar a mídia. Separá-las evita uma skill monolítica e permite evoluir cada uma sem risco para as outras — e, no caso da quarta, isola uma dependência frágil das três que não a têm.

### O site é derivado, o vault é a fonte

A `concurso-publica` nunca escreve no vault: lê e gera `out/site/`. O progresso exibido vem dos checkboxes dos `.md` — o site é **só leitura**. Isso elimina o problema de duas fontes de verdade divergindo. Regenerar o site é sempre seguro e idempotente.

### Vários aprofundamentos por assunto

Um assunto pode ser aprofundado com fontes diferentes e em dois níveis. A identidade é `{nivel}--{fonte1}[+{fonte2}]` e cada aprofundamento vive na própria pasta, direto sob a pasta do assunto:

```
assuntos/emprego-do-acento-indicativo-de-crase/
├── padrao--pestana/
│   └── emprego-do-acento-indicativo-de-crase--padrao--pestana--SEDES_2026.md
└── detalhado--pestana/
```

O identificador carrega **só o que diferencia**: nível (profundidade), fonte (origem) e — no nome do arquivo — concurso (contexto). Um contador de fontes e um índice posicional existiram numa versão anterior e foram removidos: ambos eram deriváveis do resto, e nome de arquivo que não desempata é custo permanente sem retorno. Já o concurso foi acrescentado por um motivo empírico: 18 arquivos colidiam entre `SEDES_2026` e `BB_2027_PREVISTO`, que usam o mesmo livro para os mesmos assuntos.

A ordem dos componentes é deliberada: **nível primeiro** faz os aprofundamentos do mesmo assunto ordenarem juntos por profundidade na listagem do sistema de arquivos, que é como o usuário navega no Obsidian.

O slug da fonte é o sobrenome de um autor (livro) ou o identificador da norma (`lei-8742`, `res-cmn-4893`). Essa dualidade não é acidente: cerca de 40% do material do vault vem de legislação, que não tem autor — um padrão só com "sobrenome" não cobriria o caso real. Quando a derivação automática não consegue deduzir (obra com dois autores, arquivo sem autor no nome), o script **avisa e exige slug explícito** em vez de gravar um path ruim; é o mesmo princípio de "nunca fingir precisão" aplicado a nomes.

Os nomes de arquivo repetem o identificador porque o Obsidian resolve wikilinks por nome de arquivo, e dois `crase.md` seriam ambíguos. Os formatos anteriores (`aprofundamentos/{id}/` e arquivo direto na pasta do assunto) continuam sendo lidos: quem não migrar não pode ficar sem site.

A convenção é implementada uma única vez, em `skills/concurso-aprofunda/scripts/aprofundamento_id.py`. Como as skills são instaladas de forma independente, a `concurso-publica` não pode importá-la — tem uma **cópia sincronizada**, com teste de smoke nas duas pontas que falha se divergirem. Cópia com detector de drift foi preferida a um pacote compartilhado porque o instalador copia skills isoladas para `~/.claude/skills/`, sem resolução de dependências.

#### Acrescentar uma fonte é renomear — e por que isso não é acidente

Como o id **é** o conjunto de fontes e o id **é** o path, não existe "adicionar fonte sem mexer no nome": `padrao--pestana` vira `padrao--pestana+rosenthal`. A alternativa seria omitir a fonte do nome quando há só uma — e foi exatamente isso que se recusou, porque então *toda* segunda fonte forçaria uma renomeação, em vez de só as ampliações deliberadas.

A renomeação é feita por `ampliar_aprofundamento.py`, em dois modos que diferem apenas em mover ou copiar: **ampliar** (o id antigo deixa de existir; o texto vira a semente da mescla) e **derivar** (os dois convivem). Modelar as duas operações como um script só, e não dois, veio de constatar que o trabalho mecânico é idêntico — o que muda é `shutil.move` × `shutil.copy2` e o que **não** viaja na cópia.

A cópia deliberadamente **não** leva `notebooklm_url`, o sidecar de estado nem a mídia. O motivo é o inverso do que faz a herança existir no modo ampliar: duas pastas apontando para o mesmo notebook fariam a `concurso-notebooklm` subir a nota da variante para dentro do notebook do original — porque `garantir_fontes()` sobe fonte **pelo nome e só adiciona, nunca remove**. Essa mesma característica é a razão de o ampliar emitir pendência nomeada em vez de tentar consertar sozinho: remover fonte do notebook exigiria importar a dependência frágil (`notebooklm-py`), que por decisão de projeto mora só na skill irmã.

A ordem das fontes é **significativa e nunca canonicalizada**. Ordenar alfabeticamente parece limpeza, mas renomearia material que ninguém pediu para mexer — quatro pastas do vault já estão fora de ordem alfabética. A ordem codifica cronologia de composição: a fonte 1 é aquela de onde o texto foi escrito, as seguintes completam. Daí acrescentar **no fim** ser o padrão, e conjunto igual em outra ordem ser pendência em vez de escolha silenciosa.

#### Localização por fonte: chaves numeradas, não separador

Um aprofundamento combinado precisa de um ponteiro de página **por fonte**. A fonte 1 fica em `localizacao_livro` e as demais em `localizacao_2`, `localizacao_3`. Três decisões aqui:

- **Numeradas, e não uma chave só com separador**, porque os ponteiros reais do vault já contêm `;` dentro deles (`"pp. 5 a 7 (arts. 1º a 4º); art. 7º VI na p. 1"`) — um separador seria ambíguo por construção.
- **A fonte 1 não virou `localizacao_1`**, para a retrocompatibilidade ser passiva: 122 arquivos de fonte única continuam documentos válidos sem tocar em nada, e nenhum dos quatro consumidores precisou mudar para continuar correto.
- **Nada é obrigado a ser parseável.** Dos 122 valores, só 61 casam o molde `— págs. N–M`; o resto é prosa (`"slides 12 a 21"`). É texto humano com atribuição de fonte — quem quiser página tenta extrair e **degrada**, nunca exige o formato.

O `book_index.py` continua indexando **um livro por execução**: N fontes já são N execuções, e juntá-las num arquivo só criaria um quarto formato e um lugar novo onde "de qual livro é esta página" se perde. Por isso `--mapa` é repetível, pareado por posição com `--fontes` — e por isso, no modo em lote do ampliador, `--mapa` é o único caminho correto: o ponteiro é por assunto, e um `--localizacao` único gravaria a página certa de um assunto e errada de todos os outros.

### A arquitetura de informação do site

O site espelha a organização do vault: `{concurso}/{comum|cargo}/`, com as seções
numeradas e `materias/{materia}/{assunto}/`. O espelho é deliberado — é a estrutura
que o usuário já navega no Obsidian, e inventar outra obrigaria a manter duas
taxonomias na cabeça.

**Hub e trilha, não árvore.** Não há sidebar com árvore de pastas. Cada nível é uma
página que explica o que há embaixo, e a trilha no topo diz onde se está.
Reproduzir o explorador do Obsidian no navegador não acrescentaria nada: quem abre o
site vem consumir, não gerenciar.

**Dois registros visuais.** As pastas numeradas do vault existem para ordenar no
explorador de arquivos — `05-HISTORICO` vem antes de `06-SINERGIA` porque alguém
escolheu os números. Espelhar essa numeração como *peso visual* faria "Sinergia"
competir com "Crase". Por isso o que se **estuda** ganha card com progresso, e o que
se **consulta** vira lista tipográfica, num registro mais quieto.

**Uma matéria, duas visões.** O mapa de matéria e o aprofundamento cobrem o mesmo
recorte por ângulos diferentes: o mapa é o plano do edital (tópicos e checklists), o
aprofundamento é o conteúdo (resumo, páginas do livro, flashcards). Ficam na mesma
página, em abas. Separá-los em duas seções obrigaria a saber em qual procurar.

**O tópico se abre por camadas, e a divisão não é estética.** Cada tópico do mapa
carrega cinco subseções — o literal do edital, os subtópicos derivados, o material
recomendado, as pegadinhas da banca e a meta — mais o que o autor do mapa tiver
escrito além disso. Publicá-las todas inline resolveria o problema errado: a maior
matéria do vault tem 24 tópicos, e cinco blocos densos em cada um viram um documento
em que nada se acha. Ficam sempre à vista o **literal do edital**, que é a autoridade
da página e ocupa uma linha, e o **checklist de subtópicos**, que é a superfície de
varredura; o resto vai para um `<details>` cujo resumo **conta o que há dentro**
(`⚠️ 7 pegadinhas · 📚 3 materiais`) — dobra muda obrigaria a abrir 24 tópicos para
descobrir onde está o que interessa. `<details>` nativo, e não acordeão em
JavaScript, porque abre sem JS, imprime e é o que faz o Ctrl+F do Chrome saltar para
dentro do tópico; o botão *Expandir tudo* existe porque o Firefox não faz isso na
busca da página.

**Nada escrito no tópico se perde em silêncio.** O parser reconhece cinco rótulos de
H3, mas o vault escreve mais: `Leis-chave`, `Conceitos-chave / fórmulas`,
`Referência legal` e blocos mnemônicos 🧠 somam 50 blocos dentro de tópicos
numerados. Antes eles não casavam nenhum padrão e eram descartados sem aviso —
justamente o conteúdo mais trabalhoso de escrever. Rótulo desconhecido passa a ser
publicado com o texto do vault **e avisado na geração**: publicar sem avisar
esconderia que o template e o vault divergiram; avisar sem publicar era o bug.

**Cada bloco é uma lista, não um dicionário.** Guardar as subseções num dict
chave→markdown era lossy por construção: um tópico com `### Subtópicos derivados —
TEORIA` e `— LEI 8.662/1993` tinha o primeiro sobrescrito pelo segundo. Eram 57
subtópicos em 5 tópicos, e o sintoma estava na página: uma lista com 1 item sob um
rodapé dizendo `0/22 itens do plano`. Vale como regra geral — **a lista exibida e o
contador têm de contar a mesma coisa**, e há teste que trava esse invariante em
todos os tópicos.

**O link fino tópico→assunto não é derivável, e por isso não é inventado.** Dos 203
tópicos dos 24 mapas do vault, cerca de 18% casam com o slug de um assunto. As
causas são legítimas: um tópico do edital pode explodir em vários assuntos (no SEDES,
"Domínio da estrutura morfossintática" cobre 7); nas matérias aprofundadas por
legislação o assunto **é** uma norma, então a relação é N:M e há tópico atendido por
assunto de *outra* matéria; e assuntos reaproveitados de outro concurso mantêm o slug
do edital de origem. O perigo não é a ausência de link — é o **falso negativo**: um
tópico sem link lido como "não tem aprofundamento" quando ele existe com outro nome
esconderia trabalho já feito. Aplica-se aqui a mesma regra de nunca fingir precisão
que rege a localização no livro: sem casamento exato, a página não afirma nada. Quem
quiser o link fino preenche um `mapa-aliases.json` opcional.

**O pacote NotebookLM é página por assunto, não por pacote.** Hoje são 158 pacotes no
vault para 121 assuntos: entre `padrao--X` e `detalhado--X` do mesmo assunto, só o
prompt de áudio difere — o resto é nome de arquivo. Uma página por pacote daria ~95% de
conteúdo repetido, então as versões viram abas. E é a única página do site cuja razão
de existir é uma **ação**: são 158 roteiros prontos e um punhado de mídias geradas, ou
seja, o gargalo nunca foi ter o roteiro, é executá-lo. Daí o botão de copiar em cada
prompt — e, depois, a `concurso-notebooklm`, que ataca o mesmo gargalo por baixo.

**Índices do vault são derivados, não republicados.** `00-INDICE.md` e `99-Status.md`
existem para navegar no Obsidian; na web, a navegação do site **é** o índice, e o
progresso do status vira a barra do hub do escopo. Republicá-los criaria uma segunda
lista que envelhece — mas eles continuam sendo *lidos*, porque é deles que saem a
ordenação das matérias e os selos de questões e prioridade (só 1 dos 24 mapas traz
`estimativa_questoes` no frontmatter).

**Rotas antes de renderizar.** O build tem dois passos: primeiro decide onde cada
página vai morar e indexa os nomes de arquivo do vault, depois renderiza. A ordem é
imposta pelo resolvedor de wikilinks — para virar `href`, `[[crase]]` precisa da URL
de uma página que talvez ainda não tenha sido gerada. Com um passo só, o resolvedor
não conseguia ver além dos assuntos irmãos da mesma matéria, e todo wikilink que
atravessasse matéria ou apontasse para documento morria por construção. O índice tem
três classes de alvo, porque nem todo alvo é página: página, artefato embutido
(flashcards, que viram âncora do quiz) e arquivo copiado (mídia, anexo).

Cuidado que vale registrar: o índice de nomes resolve por *basename*, e nomes repetem
entre escopos (`lingua-portuguesa` existe no comum e em cada cargo do BB;
`cronograma-macro.md` existe em três cargos do SEDES). Ele serve para **wikilink**,
onde a ambiguidade é inerente ao formato. Link de **navegação** é sempre calculado da
rota da própria página — usar o índice fazia o hub do cargo apontar para a matéria do
comum e deixava a própria órfã.

### Deploy por sincronização de arquivos

O container Docker serve o site por **bind mount**, não por cópia para dentro da imagem. Atualizar é `rsync`: sem rebuild, sem restart, sem downtime. Servir estático é I/O, não CPU — por isso 0.5 CPU e 128 MB bastam com folga para uso doméstico.

O container responde **direto** em `concursos.casa:8099`, servindo na raiz — sem proxy reverso na frente. A configuração anterior (subpath `/concursos` atrás do proxy de outro host) foi abandonada por acrescentar uma peça sem benefício num ambiente de rede doméstica. O caminho antigo continua redirecionando, com `rewrite`, para preservar deep links.

Duas diretivas do nginx merecem registro porque não são óbvias: `absolute_redirect off` e `port_in_redirect off`. O container escuta na 80 e é publicado na 8099; sem elas o nginx monta o cabeçalho `Location` dos redirects com a porta **interna**, e todo link antigo cai numa porta que não existe do lado de fora.

Como o gerador sempre emitiu **links relativos**, mudar de subpath para raiz não exigiu nenhuma alteração no `site_builder.py` — o mesmo site funciona nos dois modos.

### Versões lado a lado, nunca sobrescrita

Quando um edital previsto vira oficial, ou um oficial é retificado, a estrutura antiga é **arquivada**, não substituída: `V1-PREVISTO` → `V2-OFICIAL` → `V3-RETIFICADO`. O motivo é preservar o trabalho do estudante — se o diff errar, nada se perdeu. A migração de progresso é feita por arquivo de matéria, com aviso do que mudou.

### Modelo 2 (direitos autorais)

Três modelos foram considerados para o material extraído do livro:

1. ponteiros + resumo original;
2. **ponteiros + resumo original + trechos curtos citados** ← adotado;
3. extração integral do texto.

O modelo 3 foi descartado: reproduz a obra. O modelo 2 entrega o que ajuda de fato a estudar (onde ler, o que é essencial, o que a banca cobra) sem copiar o livro.

### NotebookLM manual, automação como camada opcional

Não existe API pública de consumidor do NotebookLM. A via da comunidade (`notebooklm-py`) usa endpoints internos não-documentados do Google e pode quebrar sem aviso. Por isso a `concurso-aprofunda` **gera o pacote de embarque** (fontes a subir, prompts prontos por gerável, roteiro de cliques) e o usuário executa — manualmente, sempre que quiser.

A automação **entrou**, na `concurso-notebooklm`, e entrou exatamente na forma prevista: skill **separada**, para a dependência não contaminar as outras três — nenhuma delas tem dependência Python obrigatória, e a `concurso-publica` não tem nenhuma; e camada **sobre** o modo manual, nunca em substituição. Sem a biblioteca instalada, a skill degrada e o pacote continua completo — a suíte dela passa sem a dependência, porque o `install.sh` roda os testes logo depois de copiar.

A divisão interna existe pelo mesmo motivo da fragilidade: **a lógica não toca a rede**. `pacote.py` (ler/escrever o pacote) e `plano.py` (o que gerar, com que nome) são stdlib puro e testáveis sem conexão; a fronteira de rede é fina e injetável. Quando o Google mudar algo por baixo, quebra num arquivo só.

Duas restrições descobertas ao ler a biblioteca, e que moldaram o escopo: ela **não aceita prompt customizado para mapa mental** (o `PROMPT_MINDMAP` do pacote não seria enviado) e **baixa o mapa em JSON**, formato que o catálogo de mídias da `concurso-publica` não reconhece — o arquivo ficaria invisível no site. Por isso o mapa mental ficou **fora** da automação, e pedi-lo é recusado **com a razão**, não ignorado. Pelo mesmo princípio, a extensão do arquivo baixado sai dos **bytes**, não da declaração: o site casa prefixo *e* extensão, então nome errado não vira outro tipo de mídia — vira invisível, que é o pior desfecho por ser silencioso.

### Localização no livro: TOC primeiro, densidade como rede

O `book_index.py` tenta casar os assuntos com o **sumário** do livro (preciso quando existe). Sem sumário utilizável, cai para **densidade de termos** por página. Ambos retornam um score, e baixa confiança vira pendência explícita — a skill nunca inventa uma página.

## Fluxo de dados entre as skills

A `concurso-prep` grava `.meta.json` na raiz da pasta do concurso com o conteúdo programático integral. A `concurso-aprofunda` lê os assuntos mapeados a partir daí (ou dos mapas de matéria) para saber o que procurar no livro. O `reuse_finder.py` varre o vault inteiro procurando `(livro, assunto)` já aprofundados em **outros** concursos, para reaproveitar em vez de refazer.

## Dependências e degradação

Todas as dependências Python são opcionais e o comportamento degrada com aviso, nunca com falha total:

| Ausente | Efeito |
|---|---|
| `reportlab` / `weasyprint` | leis saem só em `.md` (sem PDF) |
| `pyyaml` | apenas `.meta.yml` legado indisponível; `.meta.json` é o padrão |
| `python-docx` | editais `.docx` não são processados (PDF e MD seguem) |
| `tesseract` | PDFs escaneados viram pendência em vez de serem lidos |
| `notebooklm-py` | a `concurso-notebooklm` degrada: a camada de contrato (ler o pacote, planejar, nomear) continua, só a execução some. O pacote manual segue completo, e a suíte dela passa sem a biblioteca — o `install.sh` roda os testes logo depois de copiar |
| `pdftotext` | bloqueia leitura de PDF (é o único praticamente obrigatório) |

A `notebooklm-py` é caso à parte por ser a única **não-oficial**: roda sobre endpoints
internos do Google e quebra sem aviso, o que é justamente o motivo de viver numa skill
só. O `requirements.txt` dela pina a faixa `0.7.x`, verificada em campo; a 0.3.x grava
a credencial em outro caminho e ter as duas instaladas produz um `Auth not found` que
parece erro de login.
