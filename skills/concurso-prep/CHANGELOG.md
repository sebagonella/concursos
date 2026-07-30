# Changelog

Todas as mudanças notáveis da skill `concurso-prep` são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

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
