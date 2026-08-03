---
name: concurso-publica
version: 0.16.0
description: Use quando o usuário quiser transformar a estrutura de um concurso já gerada no vault (pelas skills concurso-prep e concurso-aprofunda) em um site estático navegável para uso local/rede doméstica. Publica TODO o conteúdo abaixo da pasta do concurso, espelhando a organização do vault (COMUM e um galho por cargo) - edital e análise da banca, cronograma, mapas de matéria, materiais e leis baixadas, histórico, sinergia, discursiva, títulos e o aprofundamento. Cada matéria tem duas visões (Plano, do mapa do edital, e Estudo, dos assuntos aprofundados); no Plano, cada tópico leva o literal do edital, os subtópicos derivados, o material recomendado, as pegadinhas da banca, a meta de questões e as seções que o mapa tiver além dessas. Cada assunto tem o podcast tocando, o vídeo rodando, mapa mental e report embutidos, flashcards como quiz e uma página com os prompts do pacote NotebookLM prontos para copiar. Triggers - "publicar o concurso como site", "gerar páginas web do concurso", "site do vault", "ver o material no navegador", "montar o site de estudo", "levar os mapas de matéria para a web", "ver as pegadinhas da banca no site", "publicar o pacote do NotebookLM".
---

# concurso-publica

Terceira etapa do fluxo: **vault → site estático**. Consome a saída das etapas 1 e 2 e gera páginas navegáveis com as mídias embutidas.

## Princípios (decisões aprovadas pelo dono do projeto)

1. **Gerador próprio** (Python + templates), sem dependência de Node/Quartz.
2. **Por concurso**: `--concurso-dir` aponta para uma pasta de concurso; nada de vault inteiro.
3. **Local/rede doméstica** nesta versão — sem publicação externa, sem autenticação.
4. **Site só leitura**: o progresso é lido do vault (checkboxes dos `.md`) na geração e exibido; o site nunca edita nada. O vault é a única fonte de verdade; o site é derivado regenerável.
5. **NotebookLM interativo por link**: o botão "Abrir no NotebookLM" aparece só se `notebooklm_url:` estiver preenchida no frontmatter do `_fonte-notebooklm.md` do assunto. Sem iframe do Google (bloqueado por política deles).

Mídia ausente = seção ausente na página, sem quebrar (degradação graciosa).

## Estrutura de saída

```
out/site/
├── index.html                            todos os concursos, por órgão
├── assets/                               css e js compartilhados
└── {concurso}/
    ├── index.html                        capa: ficha da prova + um card por escopo
    ├── .concurso.json                    manifesto (alimenta o índice raiz)
    ├── comum/
    │   ├── index.html                    hub do escopo
    │   ├── edital/{doc}/                 resumo · análise da banca · cronograma oficial
    │   ├── materiais/{doc}/              livros · canais · plataformas · leis
    │   ├── materiais/arquivos/…          anexos copiados (PDF das leis)
    │   ├── historico/, sinergia/
    │   └── materias/{materia}/
    │       ├── index.html                abas Plano | Estudo
    │       └── {assunto}/
    │           ├── index.html            aprofundamento (abas por fonte/nível)
    │           └── notebooklm/index.html  pacote: fontes + prompts com copiar
    └── {cargo}/                          idem, mais cronograma/, discursiva/, titulos/
```

O caminho espelha a organização do vault (`_COMUM` e um galho por cargo). Seção com
um documento só e sem anexo **é** o documento — índice de um item é página inútil.

**Uma matéria, duas visões.** O mapa de matéria (`03-MAPAS-*`) e o aprofundamento
(`03-APROFUNDAMENTO`) cobrem o mesmo recorte por ângulos diferentes: o mapa é o plano
do edital, o aprofundamento é o conteúdo. Ficam na mesma página, em abas — separá-los
obrigaria a saber em qual procurar.

**O link tópico→assunto só sai com casamento exato.** Dos 203 tópicos dos 24 mapas do
vault, cerca de 18% casam por slug: um tópico pode explodir em 7 assuntos, nas
matérias de "lei como fonte" o assunto **é** uma norma (relação N:M), e assuntos
reaproveitados de outro concurso seguem o slug do outro edital. Sem casamento, a
página **não afirma nada** — o falso negativo, um tópico lido como "não tem
aprofundamento" quando ele existe com outro nome, esconderia trabalho já feito. Quem
quiser o link fino preenche `mapa-aliases.json` na pasta da matéria (opcional):

```json
{ "Domínio da estrutura morfossintática do período": ["crase", "regencia-verbal-e-nominal"] }
```

`00-INDICE.md` e `99-Status.md` são **derivados, não republicados**: a navegação do
site é o índice, e o progresso do status vira a barra do hub do escopo. Republicá-los
criaria uma segunda lista que envelhece.

**Como o aprofundamento é lido.** O padrão de pastas da `concurso-aprofunda` é

```
assuntos/{slug-assunto}/{nivel}--{fonte1}[+{fonte2}]/
```

e o nível e as fontes saem do **nome da pasta**, que é mais confiável que o
frontmatter (material antigo pode não ter `nivel:`). Os layouts anteriores
(`aprofundamentos/{id}/` e o legado plano) continuam sendo lidos — o site não pode
quebrar por material que o usuário ainda não migrou. Vários aprofundamentos do mesmo
assunto viram abas na página, e a mídia de cada um fica em `media/<id>/`, sem colidir.

> A convenção vive em `scripts/aprofundamento_id.py`, **cópia sincronizada** da
> fonte em `concurso-aprofunda`. Não edite aqui: edite lá e copie por cima. Há
> teste de smoke que falha se as duas divergirem.

Nos cards de assunto, um selo sinaliza **quantas fontes** e **quais níveis**
existem (Padrão / Detalhado / ambos), reaproveitando a bolha do cartão-resposta:
meia bolha = padrão, bolha cheia = detalhado. A aba que abre é a do nível `padrao`.

**Selo só para mídia que existe.** No card, os tipos ausentes não aparecem: numa
matéria de 11 assuntos, mostrar os 8 tipos em cinza são 88 ícones que afogam o
título. A grade completa, com os ausentes, fica na página do assunto — onde "falta
gerar" é acionável, porque é de lá que se chega ao prompt do NotebookLM.

O site suporta os **8 tipos do Estúdio** do NotebookLM (áudio, vídeo, slides, mapa
mental, infográfico, relatório, teste, tabela), detectados por presença de arquivo;
tem tema claro/escuro, índice raiz com os concursos agrupados por órgão (deploy
incremental via manifesto `.concurso.json`), assuntos agrupados por prioridade, a
seção "Como a banca cobra" antes da lista, sumário lateral em documento longo e
download de todas as mídias.

Suíte de smoke completa (`bash scripts/test-all.sh`), com uma regressão por defeito já corrigido.

> O histórico de versões vive no [`CHANGELOG.md`](CHANGELOG.md). Este arquivo descreve
> o estado atual: uma lista de "novidades da versão X" aqui vira changelog duplicado e
> já ficou sete versões para trás uma vez.

## Fluxo

```
1. Coletar o modelo
   scripts/site_collector.py --concurso-dir <.../CONCURSOS/SEDES_2026> --out site-model.json
   - Acha os ESCOPOS primeiro (_COMUM + cargos), depois o que há dentro de cada
   - Seções numeradas por tabela SECOES: documentos (.md) e anexos (o resto)
   - Matérias: aprofundamento (assuntos/) unido ao mapa de matéria, pelo slug
   - Detecta mídia por presença de arquivo; presença é a UNIÃO dos aprofundamentos
   - Lê progresso dos checkboxes (mapa contado à parte do aprofundamento)
   - Extrai o pacote NotebookLM: fontes, os 4 prompts, perguntas e checklist

2. Gerar as páginas — em dois passos
   - montar_rotas(): decide onde cada página mora e indexa os nomes do vault.
     Vem antes de renderizar porque o resolvedor de wikilinks precisa da URL de
     páginas que ainda não existem
   - renderizar: capa → hub de escopo → seção → documento → matéria (Plano|Estudo)
     → assunto → pacote NotebookLM

3. Empacotar
   - out/site/{CONCURSO}/ com assets locais (sem CDN; funciona offline)
   - abrir via index.html ou servir na rede local (python -m http.server)
```

## O modelo coletado (o contrato entre coletor e builder)

`site-model.json`: concurso → meta → **escopos[]** → { `tipo` (comum/cargo),
`nome`, `slug`, `secoes[]`, `materias[]`, `progresso` }.

- **`secoes[]`** — `ordinal`, `rotulo`, `slug`, `registro` (estudo/consulta),
  `documentos[]` (título, slug, resumo, progresso) e `anexos[]` (arquivo, bytes,
  subpasta).
- **`materias[]`** — o de sempre (`assuntos[]` com `midias`, `flashcards`,
  `progresso`, `aprofundamentos[]`) mais `mapa` (tópicos do edital) e, quando as
  duas metades vivem em escopos diferentes, `aprofundamento_em` / `mapa_em`.
- **`mapa.topicos[]`** — `numero`, `titulo`, `slug`, `prioridade`, `progresso`,
  `subtopicos[]` (`texto`, `feito`, `grupo`) e **`blocos[]`**: todos os H3 do
  tópico na ordem do documento, cada um com `chave` (`topicos_edital`,
  `subtopicos`, `material`, `pegadinhas`, `meta` ou `extra`), o `rotulo` literal do
  vault, o `sufixo` temático, o `markdown` cru e os `itens`. `mapa.rotulos_extras`
  lista os rótulos fora do template, que a geração avisa no stderr.
  `blocos[]` substituiu o dict `secoes` da 0.7.x — que perdia bloco repetido — mas
  o builder ainda lê o formato antigo.
- Cada aprofundamento traz `pack_notebooklm` com os prompts extraídos.

`cargos[]` continua presente como **alias** de `escopos[]`: `--modelo
site-model.json` é contrato público e um `site-model.json` salvo antes não deve
quebrar. Ver docstring do `site_collector.py` para o formato completo.

## Scripts

- `site_collector.py` — varre o concurso e monta o modelo do site
- `site_builder.py` — gera as páginas HTML com mídias embutidas e o quiz de flashcards
- `md2html.py` — conversor Markdown→HTML próprio (sem dependências; o site roda offline)
- `tests/test_smoke.py` — suíte standalone

### Gerar o site

```bash
python scripts/site_builder.py --concurso-dir <.../SEDES_2026> --out out/site
# abrir out/site/index.html, ou servir: python -m http.server -d out/site
```

Saída: capa do concurso → índice por matéria → página por assunto (resumo renderizado,
player de áudio, vídeo, mapa mental com lightbox, guia de estudos e quiz de flashcards).

### Direção visual

Paleta e elementos tirados do mundo da prova de concurso: papel, tinta de caneta
esferográfica azul (a que o edital exige), marca-texto e caneta vermelha de correção.
O elemento-assinatura é a **bolha do cartão-resposta**, usada como indicador de
progresso (lido do vault, só leitura). Tipografia por stack de sistema — sem webfonts,
porque o site precisa funcionar offline na rede doméstica.

## Deploy (servidor doméstico)

Em `deploy/`: ambiente Docker para servir o site em `concursos.casa:8099`.

- `docker-compose.yml` — nginx:alpine com bind mount do site; publica a porta **8099**;
  limites 0.5 CPU / 128 MB (dimensionado para ~3 usuários simultâneos; servir estático é I/O, não CPU)
- `nginx.conf` — serve o site na **raiz** (`/`), com healthcheck e logs enxutos.
  O caminho antigo `/concursos/<algo>` redireciona para `/<algo>`, preservando deep links
- `deploy.sh` — roda na máquina do vault: gera o site e sincroniza via rsync/SSH.
  Como o container usa bind mount, **não há rebuild nem restart** a cada atualização.
- `README.md` — instalação, snippet do proxy reverso, verificação e troubleshooting

```bash
./deploy.sh --setup                                    # 1ª vez
./deploy.sh --concurso-dir <.../SEDES_2026>            # atualizações
./deploy.sh --concurso-dir <...> --dry-run             # conferir antes
```

## Fora de escopo desta versão

Backend, login, sincronização site→vault, iframe do NotebookLM, PWA/offline-first.
