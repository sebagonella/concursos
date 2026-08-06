# Changelog — concurso-notebooklm

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

## [0.3.0] - 2026-08-06

### Corrigido

- **`Relatorio.codigo_saida` era CÓDIGO MORTO.** A propriedade existia e **nenhum chamador a
  usava**: `nlm_run.py` remontava `2 if falhou else 0` à mão e a quota noutro ponto,
  `nlm_coleta.py` idem. A regra do código de saída vivia num lugar que ninguém lia — então
  acrescentar `fontes_faltando` só a ela não teria mudado nada. Os dois `main()` passam a
  consultar o relatório, tomando o **pior** código entre os pacotes processados.
- **Fonte declarada que falta em disco passa a sair 2.** Notebook montado sem a lei que o
  próprio pacote declara não é sucesso: a "pendência nomeada" ia só para o stdout, e quem
  automatiza olha o **exit code**, que dizia que estava tudo bem. A quota mantém precedência
  (4), porque é o único caso em que "rode amanhã" é a instrução certa.
- O aviso das fontes faltantes sai junto do **bloco final** do `nlm_run`, não no meio: mensagem
  no meio de saída longa não se lê.

### Adicionado

- **`notebooklm_fontes_subidas` e `notebooklm_fontes_faltando` gravados no pacote.** Antes o
  relatório morria no stdout da execução e não havia como saber, depois, com que fontes um
  podcast foi gerado — a não ser abrindo o notebook. O prefixo `notebooklm_` é deliberado:
  `herdar_campos` herda por prefixo, então os campos sobrevivem a toda regeração futura do
  pacote sem código novo. Fontes que já estavam no notebook entram na conta, porque também
  sustentam a mídia gerada.

## [0.2.1] - 2026-07-31

### Corrigido
- **O `requirements.txt` instalava a versão que a 0.2.0 tinha acabado de diagnosticar
  como culpada.** O pin era `>=0.3.4,<0.4`, mas todo o ciclo foi verificado contra a
  **0.7.3**, e a 0.3.4 é justamente a faixa que grava a credencial em outro caminho —
  a causa do `Auth not found` registrado abaixo. Quem seguisse o `README` e rodasse
  `pip install -r` recebia o bug pronto. A faixa passa a ser `>=0.7.3,<0.8`, com o
  motivo no próprio arquivo para ninguém baixar de volta sem saber o que quebra.

## [0.2.0] - 2026-07-31

A **camada de rede**. A skill passa a criar o notebook, subir as fontes, disparar as
gerações e coletar os arquivos — verificado ponta a ponta contra o NotebookLM real.

### Adicionado
- `scripts/porta.py` — a fronteira. **A fronteira é a CLI, não a API Python**: a
  biblioteca expõe as duas, mas a API é `async` e mora em módulos com underscore que o
  próprio projeto declara instáveis; a CLI é a superfície pública, devolve JSON e foi
  a que se verificou em campo. Por subprocess, a skill fica **síncrona** como o resto
  do repositório, e a degradação vira trivial: sem o executável, não há o que importar.
  O vocabulário de estado é **nosso**, não o da biblioteca — é o que faz a fronteira
  sobreviver ao Google renomear coisas. A `PortaFalsa` vive no mesmo módulo do
  Protocol, e há teste comparando as assinaturas: dublê e interface não podem divergir
  sem alguém ver.
- `scripts/executor.py` — junta plano e porta. **Não recria notebook que já existe**
  (reexecutar sobre 66 assuntos criaria 66 duplicados e queimaria a quota) e **não
  ressobe fonte que já está lá**. A quota é tratada **por tipo**: esgotar áudio não
  impede report, cujo teto é muito mais folgado.
- `scripts/nlm_run.py` e `scripts/nlm_coleta.py` — os dois comandos. O `run` **não
  espera**: são minutos por item, e 66 itens seriam horas com um processo segurando a
  sessão. Ele grava os `task_id` e diz o comando da coleta; a coleta roda quantas
  vezes quiser.
- **Código de saída 4 para quota**, separado do 2. É o único caso em que "rode de novo
  amanhã" é a instrução certa, e o relatório diz que o teto **não** é informado pelo
  servidor — o que se sabe é que ele recusou.
- 19 testes novos, todos com o dublê e sem rede.

### Corrigido
- **`Auth not found` logo depois de um login bem-sucedido.** Com duas instalações da
  biblioteca (uma no `~/.local`, outra na venv do projeto), o `PATH` escolhe a errada —
  e as versões guardam a credencial em caminhos **diferentes**: a 0.3.x em
  `$NOTEBOOKLM_HOME/storage_state.json`, a 0.7.x em `profiles/<nome>/`. Os comandos
  passam a preferir o `notebooklm` da venv do projeto, e caminho explícito continua
  sendo respeitado. Foi encontrado rodando de verdade, não em teste.

### Onde cada dado mora
- **Durável e humano → frontmatter do pacote**: `notebooklm_id`, `notebooklm_url`,
  `notebooklm_status`, `notebooklm_gerado_em`. O usuário os lê no Obsidian e o site os
  publica.
- **Volátil e de máquina → sidecar `_notebooklm-estado.json`**: os `task_id` em voo.
  Não vão para o frontmatter porque são ruído num documento curado; porque mudam a
  cada execução, e cada mudança dispararia o backup `.bak.md` do gerador; e porque um
  `task_id` velho é indistinguível de um vivo — a consulta devolve "pendente" para
  tarefa desconhecida, daí também o teto de idade de 6 h na coleta.

## [0.1.0] - 2026-07-31

Primeira versão: **camada de contrato**. Lê o pacote, decide o que gerar, nomeia a
saída e grava os metadados de volta no vault. **Ainda não fala com o NotebookLM** —
a fronteira de rede é a próxima etapa, e foi separada de propósito: a lógica de
negócio é stdlib puro e testável sem conexão, então quando o Google mudar algo por
baixo da biblioteca, quebra num arquivo só.

### Adicionado
- `scripts/pacote.py` — único módulo que toca o `_fonte-notebooklm.md`. Lê o
  frontmatter (nome do notebook, `arquivo_*` de cada gerável, `notebooklm_*`), um
  prompt por gerável e a lista de fontes; resolve cada fonte num arquivo real do
  disco; e grava campos de volta de forma **atômica**, preservando o resto byte a
  byte. Pacote sem frontmatter **falha alto**: seguir em frente criaria um notebook
  sem saber para qual assunto.
- `scripts/plano.py` — decide o que gerar, pulando o que já tem arquivo na pasta
  (mesma regra de presença que o site usa, para não haver um segundo lugar guardando
  "isto já foi gerado"). Valida `--midias` à mão, no padrão do `--formatos` do
  `fetch_lei.py`, nomeando as opções válidas em vez de falhar seco. Deriva a URL do
  notebook do id, sem rede. E adivinha o container pelos **bytes**, porque a
  biblioteca grava no caminho que recebe: nome com extensão errada não vira outro
  tipo de mídia, vira **invisível** para o site — pior, por ser silencioso.
- 26 testes, verdes **sem** a `notebooklm-py` instalada. Os pacotes usados como
  fixture são gerados pelo `notebooklm_pack.py` de verdade, e há guarda cruzada que
  falha se a `concurso-publica` mudar as extensões aceitas para podcast.

### Verificado em campo (2026-07-31)

Primeira execução real contra o NotebookLM, com a `notebooklm-py` **0.7.3** e conta
dedicada. O que se confirmou:

- **`notebooklm login` não funciona nesta versão.** Ela espera a página no host antigo
  (`page.wait_for_url` em `cli/services/playwright_login.py`), e desde o rebrand
  "Gemini Notebook" o Google leva a sessão para `notebook.google.com`. A espera de 5
  minutos estoura sempre. `NOTEBOOKLM_BASE_URL` **não** contorna: o host novo não está
  na lista branca de `_env.py`. Contorno documentado no README — `--browser-cookies`,
  que nem usa Playwright — e `scripts/salvar_sessao.py` para recuperar um login que
  já aconteceu no perfil persistente.
- **Só a detecção quebra.** Com a credencial salva, `auth check`, `list`, `create`,
  `source add`, `generate audio` e `share` respondem normalmente. O `auth check`
  mostra `OSID` nos **dois** hosts.
- **O título da fonte é o nome do arquivo.** `source add` não recebe título, e isso é
  sorte boa: os prompts do pacote ancoram na nota **pelo nome do arquivo**, então a
  âncora resolve sozinha. Regra que decorre disso: **nunca renomear no upload**.
- **A URL de compartilhamento é a que `plano.url_do_notebook()` deriva**, byte a byte
  — confirmado contra o `share_url` devolvido pelo Google. Derivar não custa rede;
  `share public` é a chamada que muda acesso, e é outra coisa.
- **O idioma é `pt_BR`, com underscore.** O default da biblioteca é `en` — esquecer
  produziria podcasts em inglês e queimaria a quota do dia.
- **O container do áudio é `.m4a`, e a incógnita está resolvida.** O download chega
  como ISO-BMFF de brand `dash` (`ftypdash`), **AAC estéreo, ~257 kbps**, fMP4
  auto-contido — `moov` no início, seguido de `sidx`/`moof`/`mdat`. Toca no `<audio>`
  do site, e `.m4a` é extensão correta para ele. Ou seja: o nome que o pacote já
  declarava estava certo, e a checagem por bytes confirma em vez de presumir.
- **Ciclo completo verificado num assunto real** (`especificos-cargo ·
  populacao-situacao-rua · padrao--dec-7053`): notebook criado, 5 fontes subidas,
  podcast de **17 min** gerado com o prompt do pacote, link de compartilhamento
  ativo, metadados gravados no vault e **o site publicando o player sem nenhum passo
  manual** — inclusive o botão "Abrir no NotebookLM", que veio do `notebooklm_url`
  que a automação escreveu.

### Decidido
- **Mapa mental fora da automação, por ora.** Duas razões técnicas: a biblioteca não
  aceita prompt customizado para ele — o `PROMPT_MINDMAP` do pacote não seria
  enviado — e o download vem em **JSON**, que o `CATALOGO_MIDIAS` da
  `concurso-publica` não reconhece: o arquivo ficaria invisível no site. Pedir
  `mapa-mental` é **recusado com a razão**, não ignorado.
- **Default `podcast:deep-dive`**, com `nada` e `tudo` como tokens especiais.
- **O prompt enviado é o do pacote, byte a byte.** Reescrevê-lo aqui criaria duas
  versões do mesmo texto — a que o usuário copia no site e a que a automação manda.
