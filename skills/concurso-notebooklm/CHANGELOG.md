# Changelog — concurso-notebooklm

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

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
