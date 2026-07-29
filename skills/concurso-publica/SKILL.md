---
name: concurso-publica
version: 0.6.0
description: Use quando o usuário quiser transformar a estrutura de um concurso já gerada no vault (pelas skills concurso-prep e concurso-aprofunda) em um site estático navegável para uso local/rede doméstica — com uma página por assunto onde o podcast (m4a) toca, o vídeo roda, o mapa mental e o report aparecem embutidos, e os flashcards viram quiz interativo. Triggers - "publicar o concurso como site", "gerar páginas web do concurso", "site do vault", "ver o material no navegador", "montar o site de estudo".
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

## Estado de implementação

| Subsistema | Status |
|---|---|
| A — `site_collector.py` (vault → site-model.json) | ✅ implementado |
| B — `site_builder.py` + `md2html.py` + assets (modelo → HTML) | ✅ implementado |
| C — Quiz de flashcards embutido | ✅ implementado (no builder) |
| D — Busca client-side | 🔜 próxima entrega |

**Novidades da 0.3.0:** tema claro/escuro, índice raiz com todos os concursos
(deploy incremental via manifesto `.concurso.json`), assuntos agrupados por
prioridade (alta/média/base), seção "Como a banca cobra" antes dos assuntos,
download de todas as mídias e suporte aos 8 tipos do Estúdio do NotebookLM
(áudio, vídeo, slides, mapa mental, infográfico, relatório, teste, tabela).

**Novidades da 0.4.0:** concursos agrupados por **órgão** no índice raiz;
suporte a **vários aprofundamentos por assunto** (fontes e níveis diferentes),
com seletor em abas na página do assunto — as mídias de cada aprofundamento ficam
em `media/<id>/`, sem colidir.

**Novidades da 0.5.0:** leitura do padrão de pastas atual da `concurso-aprofunda`
(0.3.0):

```
assuntos/{slug-assunto}/{nivel}--{fonte1}[+{fonte2}]/
```

O nível e as fontes passam a ser derivados do **nome da pasta**, que é mais
confiável que o frontmatter (material antigo pode não ter `nivel:`). Os layouts
anteriores (`aprofundamentos/{id}/` e o legado plano) continuam sendo lidos — o
site não pode quebrar por material que o usuário ainda não migrou.

> A convenção vive em `scripts/aprofundamento_id.py`, **cópia sincronizada** da
> fonte em `concurso-aprofunda`. Não edite aqui: edite lá e copie por cima. Há
> teste de smoke que falha se as duas divergirem.

Nos cards de assunto, um selo sinaliza **quantas fontes** e **quais níveis**
existem (Padrão / Detalhado / ambos), reaproveitando a bolha do cartão-resposta:
meia bolha = padrão, bolha cheia = detalhado.

42/42 testes passando.

## Fluxo

```
1. Coletar o modelo
   scripts/site_collector.py --concurso-dir <.../CONCURSOS/SEDES_2026> --out site-model.json
   - Varre cargos/matérias/assuntos; detecta mídias por presença de arquivo
     (podcast-*.m4a, video-*.mp4, mapa-mental-*.png, report-*.md)
   - Conta flashcards (multiline e singleline; tolera nome divergente do slug)
   - Lê progresso dos checkboxes e páginas do livro do frontmatter
   - Lê notebooklm_url do pack, se preenchida

2. Gerar as páginas
   - capa do concurso (dados do .meta.json: banca, prova, vagas)
   - índice por matéria com badges de mídia (🎧🧠🎬📄🃏)
   - página por assunto: resumo renderizado + players embutidos + quiz

3. Empacotar
   - out/site/{CONCURSO}/ com assets locais (sem CDN; funciona offline)
   - abrir via index.html ou servir na rede local (python -m http.server)
```

## O modelo coletado (contrato entre A e B)

`site-model.json`: concurso → meta → cargos[] → materias[] → assuntos[], onde cada
assunto traz `titulo`, `status`, `paginas_livro`, `midias{podcast,video,mapa_mental,report}`,
`flashcards{obsidian,anki,n_cards}`, `notebooklm_url`, `progresso{total,feitos}`.
Ver docstring do `site_collector.py` para o formato completo.

## Scripts

- `site_collector.py` — **(A)** varre o concurso e monta o modelo do site
- `site_builder.py` — **(B/C)** gera as páginas HTML com mídias embutidas e quiz
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

Em `deploy/`: ambiente Docker para servir o site em `concursos.casa:8088`.

- `docker-compose.yml` — nginx:alpine com bind mount do site; publica a porta **8088**;
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
