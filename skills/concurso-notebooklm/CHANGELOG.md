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

### Decidido
- **Mapa mental fora da automação, por ora.** Duas razões técnicas: a biblioteca não
  aceita prompt customizado para ele — o `PROMPT_MINDMAP` do pacote não seria
  enviado — e o download vem em **JSON**, que o `CATALOGO_MIDIAS` da
  `concurso-publica` não reconhece: o arquivo ficaria invisível no site. Pedir
  `mapa-mental` é **recusado com a razão**, não ignorado.
- **Default `podcast:deep-dive`**, com `nada` e `tudo` como tokens especiais.
- **O prompt enviado é o do pacote, byte a byte.** Reescrevê-lo aqui criaria duas
  versões do mesmo texto — a que o usuário copia no site e a que a automação manda.
