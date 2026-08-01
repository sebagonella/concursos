---
name: concurso-prep
version: 1.8.1
description: Use quando o usuário fornecer um edital de concurso público (PDF/DOCX/MD) e pedir para montar a estrutura de estudos completa, OU quando pedir para começar a estudar para um concurso ainda SEM edital/data (concurso previsto/esperado — usa o edital anterior como proxy), OU quando o edital oficial sair/for retificado e for preciso reconciliar/atualizar o que já foi gerado. Triggers comuns - "preparar concurso", "analisar edital", "montar cronograma de concurso", "estudar para concurso da {órgão}", "concurso previsto sem edital", "começar antes do edital", "edital saiu, atualizar", "edital foi retificado", "reconciliar edital". Gera no vault Obsidian estrutura completa - cronograma adaptativo (ou relativo sem datas no modo previsto), mapas por matéria, materiais de referência (leis baixadas em Markdown E PDF), histórico do órgão, provas anteriores e concursos com sinergia. Suporta multi-cargo (pasta única com subpastas por cargo), modo previsto (--modo previsto) e reconciliação/retificação (--reconciliar).
---

# Skill: Preparação Automática para Concursos Públicos

Esta skill orquestra a geração de uma estrutura de estudos completa para um concurso, replicando o fluxo de análise manual que produz cronograma + mapas de matéria + materiais + histórico + sinergias no vault Obsidian.

## Parâmetros aceitos

| Parâmetro | Obrigatório | Default | Descrição |
|---|---|---|---|
| `--edital` | sim | — | Caminho do PDF/DOCX/MD do edital (relativo ao vault ou absoluto). No modo `previsto`, é o edital ANTERIOR usado como proxy |
| `--cargo` | sim | — | Cargo pretendido. Multi-cargo: separar por vírgula. Ex: `"EDAS:Administração,TDAS:Administrativo"` |
| `--modo` | não | `oficial` | `oficial` (edital vigente, com datas) ou `previsto` (concurso esperado, edital ainda não publicado — usa edital anterior como proxy, sem datas) |
| `--reconciliar` | não | false | Aciona o fluxo de reconciliação/atualização. Cobre DOIS casos: (a) **previsto → oficial** (o edital saiu): gera `V2-OFICIAL` lado a lado com `V1-PREVISTO`; (b) **oficial → oficial retificado** (o edital mudou): gera `V3-RETIFICADO` a partir da versão oficial vigente. A skill detecta o caso automaticamente pelo estado da pasta existente. Exige `--edital` apontando para o edital novo/retificado |
| `--ano-esperado` | não | ano corrente + 1 | (modo previsto) Ano estimado do concurso previsto, usado no nome da pasta `{ORGAO}_{ANO}_PREVISTO`. Ex: `--ano-esperado 2027` |
| `--formatos-lei` | não | `md,pdf` | Formatos em que as leis baixadas são salvas: `md`, `pdf` ou ambos. Padrão gera os dois (Markdown para o vault + PDF fiel) |
| `--vault-root` | não | auto-detect | Raiz do vault Obsidian |
| `--horas-dia` | não | 4 | Horas disponíveis de estudo por dia |
| `--force-overwrite` | não | false | Substituir pasta destino se já existir |
| `--no-download` | não | false | Pular downloads (modo offline) |

## Pré-condições

Antes de executar:

1. Verificar existência do arquivo de edital
2. Confirmar que o vault tem estrutura `30_AREAS/CARREIRA/CONCURSOS/` (criar se ausente)
3. Confirmar ferramentas disponíveis: WebSearch, WebFetch, Bash, Read, Write, Task

## Convenção de nomeação de pastas (OBRIGATÓRIA)

**Todas as pastas geradas devem estar em UPPERCASE.** Os nomes de cargo são convertidos para slug (sem acento, sem espaço) e então para maiúsculas.

Regras de slugificação de cargo:
1. Remover acentos (Administração → Administracao)
2. Substituir espaços e separadores por hífen (EDAS Administração → EDAS-Administracao)
3. Converter tudo para UPPERCASE → `EDAS-ADMINISTRACAO`

Exemplos:
- `"EDAS Administração"` → pasta `EDAS-ADMINISTRACAO`
- `"TDAS Administrativo"` → pasta `TDAS-ADMINISTRATIVO`
- `"Técnico Judiciário - Área Administrativa"` → pasta `TECNICO-JUDICIARIO-AREA-ADMINISTRATIVA`

Pasta do concurso: `{ORGAO_SIGLA}_{ANO}` também em UPPERCASE → ex: `SEDES_2026`.

Pastas fixas (`_COMUM`, `01-EDITAL`, `02-CRONOGRAMA`, etc.) também em UPPERCASE.

> **Importante**: o nome "bonito" do cargo (com acento e espaços) vai apenas no **título interno** dos arquivos `.md` (no `# Cabeçalho` e no frontmatter), nunca no nome de pasta ou arquivo.

Helper disponível: `scripts/slugify.py "EDAS Administração"` retorna `EDAS-ADMINISTRACAO`.

> **A fonte do nome é `cargos_validados[].sigla`, da Etapa 2 — não o texto digitado em
> `--cargo`.** Slugificar o parâmetro faz o nome da pasta depender de como a pessoa
> escreveu: `"TDAS Agente Social"` vira `TDAS-AGENTE-SOCIAL`, enquanto o mesmo cargo no
> vault é `AGENTE-SOCIAL`. O `--cargo` serve para **localizar** o cargo no edital; quem
> nomeia a pasta é a sigla que o parser devolveu.

## Modos de operação (OFICIAL vs PREVISTO)

A skill opera em dois modos, controlados por `--modo`.

### Modo `oficial` (default)

Edital vigente, com cronograma e datas reais. Fluxo completo das 10 etapas com cronograma ancorado na data da prova. É o comportamento original.

### Modo `previsto`

Para concursos **esperados mas ainda sem edital publicado** (banca contratada, expectativa forte, autorização publicada). O usuário fornece o **edital anterior** do mesmo concurso como proxy de conteúdo.

Diferenças em relação ao modo oficial:

1. **Sem datas**: ignora qualquer cronograma/datas do edital proxy. Não há data de prova, inscrição, etc.
2. **Cronograma relativo**: gera o cronograma em "Semana 1, Semana 2, ..." sem datas-calendário, organizado por ordem de prioridade de matérias e ritmo de horas/dia. O aluno avança no próprio passo.
3. **Marcação PROVISÓRIO**: todo arquivo gerado recebe, no frontmatter e no topo, um aviso `status: PREVISTO` e banner `> ⚠️ CONTEÚDO PROVISÓRIO — baseado no edital anterior ({ANO_PROXY}). Sujeito a alteração quando o edital oficial for publicado.`
4. **Pasta com sufixo de versão**: a pasta do concurso recebe sufixo `_PREVISTO` → ex: `SEDES_2027_PREVISTO`. Isso evita colisão e deixa claro o status.
5. **Etapas de datas adaptadas**: a Etapa 4 (cronograma) usa o template relativo; o `cronograma-oficial.md` é substituído por `cronograma-relativo.md` com aviso de ausência de datas.
6. **Histórico e sinergias**: continuam funcionando normalmente (até mais úteis, pois é tudo que se tem). O edital proxy entra automaticamente como "edital de referência" no histórico.
7. **`.meta.json`**: registra `modo: previsto`, `edital_proxy_ano: {ANO}`, `data_geracao`, e os hashes do conteúdo programático para permitir o diff futuro.

### Reconciliação (`--reconciliar`): quando o edital oficial sai

Quando o edital oficial é publicado, o usuário roda novamente com `--reconciliar --edital "caminho/edital-oficial.pdf" --modo oficial`. Decisão de design: **versão lado a lado**.

Comportamento:

1. **Preserva a versão prevista intacta**: a pasta `{ORGAO}_{ANO}_PREVISTO` é renomeada para `{ORGAO}_{ANO}_V1-PREVISTO` (nada dentro dela é alterado — progresso, anotações e flashcards do aluno ficam preservados).
2. **Gera a versão oficial nova**: cria `{ORGAO}_{ANO}_V2-OFICIAL` executando o fluxo completo no modo oficial (com datas reais).
3. **Produz relatório de diff**: gera `{ORGAO}_{ANO}_V2-OFICIAL/00-DIFF-PREVISTO-VS-OFICIAL.md` comparando o conteúdo programático das duas versões:
   - 🟢 **Matérias/tópicos mantidos** (estudar continua valendo — com link para o mapa V1 correspondente, para reaproveitar progresso)
   - 🔴 **Matérias/tópicos removidos** (parar de estudar)
   - 🆕 **Matérias/tópicos novos** (começar a estudar)
   - 🔀 **Matérias/tópicos alterados** (revisar — ex: lei trocada, peso mudado)
   - 📅 **Datas reais agora disponíveis** (cronograma convertido de relativo para ancorado na prova)
4. **Migração de progresso assistida**: no diff, para cada tópico mantido, inclui instrução de como copiar a seção "Meu resumo" do mapa V1 para o V2 (a skill faz isso automaticamente quando o tópico é idêntico; sinaliza para revisão manual quando o tópico mudou).
5. **Atualiza índice raiz**: o `00-INDICE.md` no nível `CONCURSOS/` passa a listar as duas versões, marcando V1 como "arquivada (prevista)" e V2 como "ativa (oficial)".

O diff é calculado comparando os hashes e o texto do conteúdo programático armazenados em `.meta.json` de cada versão. O script `scripts/diff_editais.py` faz essa comparação e alimenta o template `diff-reconciliacao.md.tpl`.

### Re-execução no modo previsto (edital proxy atualizado, mas ainda sem oficial)

Se o usuário rodar de novo em modo previsto (ex: trocou o edital proxy por um mais recente, ou ajustou cargo), aplica-se a idempotência normal (preserva `99-Status.md` e arquivos editados manualmente), sem criar versão nova — continua sendo V1-PREVISTO.

## Fluxo de execução (10 etapas)

### Etapa 1 — Bootstrap e validação

```
1.1 Verificar existência do edital no caminho fornecido
1.2 Detectar formato (PDF/DOCX/MD); converter para texto se necessário
1.3 Detectar vault root (procurar .obsidian/ subindo na árvore se não fornecido)
1.4 Criar diretório de logs: {vault}/30_AREAS/CARREIRA/CONCURSOS/.logs/
1.5 Iniciar log de execução chamando scripts/log_helper.py com timestamp e parâmetros
1.6 Determinar MODO:
    - Se --reconciliar: ir para o fluxo de RECONCILIAÇÃO (ver seção dedicada)
    - Se --modo previsto: sufixo de pasta = "_PREVISTO"; ignorar datas; usar cronograma relativo
    - Se --modo oficial (default): fluxo completo com datas
1.7 Definir nome da pasta do concurso:
    - oficial:  {ORGAO_SIGLA}_{ANO}
    - previsto: {ORGAO_SIGLA}_{ANO_ESPERADO}_PREVISTO
      (ANO_ESPERADO = ano corrente+1 se não informado; pode vir do nome do arquivo ou perguntado)
```

### Etapa 2 — Parse do edital (subagent `edital-parser`)

Delegar para o subagent `edital-parser` via Task tool, passando:
- caminho do edital extraído
- lista de cargos pretendidos
- **o `.meta.json` do concurso, se já existir** (é de lá que saem os `materia_id`
  já declarados — ver 2.2)

**O contrato de saída é `assets/schema-edital.json`, e só ele.** Não descreva aqui um
formato paralelo: até a 1.5.0, este arquivo documentava uma `materias[]` plana e o
`agents/edital-parser.md` documentava três chaves (`materias_gerais`,
`materias_especificas_comuns`, `materias_especificas_cargo`). Dois documentos, dois
contratos, e a conversão de um para o outro ficava com o modelo — foi assim que o
`.meta.json` do SEDES e o do BB saíram com schemas diferentes entre si e do
documentado, e que o BB ficou sem o conteúdo programático de um cargo inteiro.

```
2.1 Rodar o edital-parser. Ele grava o JSON no caminho combinado.
2.2 Resolver a identidade das matérias:
      python3 scripts/materia_id.py --parsed <saida.json> --meta <pasta-do-concurso>
    - id `declarado`/`similar`: REUSAR, sempre. É o vínculo com o aprofundamento.
    - id `novo`: é PROPOSTA. Confirmar com o usuário antes de gravar (o script
      sai com código 2 justamente para não deixar passar batido).
    - matéria marcada como `candidato a divisão`: perguntar ao usuário se ela é
      uma matéria ou várias. Quem decide granularidade é gente, não heurística.
2.3 Validar o contrato ANTES de seguir:
      python3 scripts/validate_parsed.py <saida.json>
    Saída fora do schema PARA o fluxo. Nenhuma etapa seguinte roda com contrato
    quebrado — todas assumem este formato.
```

> **Por que a confirmação humana existe.** A granularidade da matéria é juízo, não
> dado: duas execuções desta skill sobre o MESMO edital do SEDES produziram 5-6
> matérias em 15/07 e 20 em 01/08. Como o `materia_id` liga mapa, aprofundamento e
> site, re-derivá-lo deixaria 20 mapas órfãos dos 90 assuntos já aprofundados. A
> decisão está no ADR `identidade-da-materia-declarada-e-persistida`: a estabilidade
> não vem de uma regra de derivação melhor, vem de **não re-derivar**.

### Etapa 3 — Análise da banca (WebSearch direto, sem subagent)

```
3.1 Buscar "perfil da banca {BANCA}" + "estilo de prova {BANCA}" + "pegadinhas {BANCA}"
3.2 Identificar características recorrentes (tipo de questão, padrão de cobrança)
3.3 Salvar em {OUTPUT_DIR}/_COMUM/01-EDITAL/analise-banca.md usando template
```

### Etapa 4 — Cronograma macro

**Branch por modo:**

**Modo `oficial`** (com datas):
```
4.1 Calcular dias entre hoje e data_prova
4.2 Aplicar lógica adaptativa (ver tabela abaixo)
4.3 Distribuir matérias por fase, ponderando por peso
4.4 Para multi-cargo: gerar cronograma por cargo, marcando matérias compartilhadas
4.5 Salvar o cronograma DO CARGO em {OUTPUT_DIR}/{CARGO_SLUG_UPPER}/02-CRONOGRAMA/
    usando cronograma-macro.md.tpl.
    O cronograma-oficial.md (datas do concurso: inscricao, prova, resultado) vai em
    {OUTPUT_DIR}/_COMUM/01-EDITAL/, com cronograma-oficial.md.tpl — ele e do
    CONCURSO e igual para todos os cargos, entao nao se repete por cargo.
4.6 (opcional) Detalhe semanal: cronograma-semanal.md.tpl gera
    {CARGO_SLUG_UPPER}/02-CRONOGRAMA/cronograma-semanal.md, com uma materia foco por
    semana mais as de manutencao. Gerar quando o usuario pedir esse nivel de detalhe;
    o macro sozinho ja e um cronograma completo.
```

**Modo `previsto`** (sem datas — cronograma relativo):
```
4.1 NÃO calcular datas. Ignorar qualquer data do edital proxy.
4.2 Definir nº de semanas com base no volume de conteúdo e em --horas-dia
    (ex: matérias densas como SUAS/AFO recebem mais semanas)
4.3 Distribuir matérias por ORDEM DE PRIORIDADE em "Semana 1, Semana 2, ..."
    sem datas-calendário. O aluno avança no próprio ritmo.
4.4 Para multi-cargo: idem, relativo, por cargo
4.5 Salvar em {OUTPUT_DIR}/{CARGO_SLUG_UPPER}/02-CRONOGRAMA/ usando
    cronograma-relativo.md.tpl. NÃO gerar cronograma-oficial.md.
4.6 Inserir banner PROVISÓRIO no topo de cada arquivo do cronograma.
```

**Lógica adaptativa de fases (apenas modo oficial):**

| Dias restantes | Fases | Distribuição |
|---|---|---|
| > 180 | Fundação → Aprofundamento → Reta Final → Preparação Final | 35/35/20/10% |
| 90-180 | Fundação → Aprofundamento → Reta Final | 40/40/20% |
| 30-90 | Revisão Acelerada → Simulados Intensivos | 60/40% |
| < 30 | Modo Emergência (revisão+simulados intercalados) | 100% |

**Fases no modo previsto** (sem datas, por blocos relativos):

| Bloco relativo | Foco |
|---|---|
| Bloco 1 (Fundação) | Matérias-base de maior peso e maior incidência histórica |
| Bloco 2 (Aprofundamento) | Específicas do cargo + matérias densas |
| Bloco 3 (Consolidação) | Revisão + questões + simulados livres |

> No modo previsto, o aluno é orientado a **avançar continuamente** e, quando o edital sair, rodar `--reconciliar` para ganhar datas e ajustar o ritmo.

### Etapa 5 — Mapas por matéria (subagents `materia-mapper` em paralelo)

Para cada matéria do edital, despachar um subagent `materia-mapper` em paralelo via múltiplas chamadas Task na mesma resposta. Input para cada um, **tudo inline no prompt**:
- nome da matéria
- **`materia_id`** (slug estável da matéria — é o que liga o mapa ao aprofundamento)
- subitem do edital
- tópicos literais do edital
- banca (para perfil de cobrança)
- cargo (para contexto)

> **Inline, literalmente.** O `materia-mapper` tem `tools: WebSearch, Write` — ele
> **não lê arquivo**. Passar um caminho não funciona, e o modo de falha observado é
> ele ir à web reconstruir os tópicos do edital a partir de blog de cursinho. Os
> tópicos literais vão no texto do prompt, sempre.

**Onde gravar — a regra do escopo.** Uma matéria pertence a **`cargos_ids[]`** (quais
cargos a cobram, da Etapa 2):

| `cargos_ids[]` | Destino |
|---|---|
| mais de um cargo | `{OUTPUT_DIR}/_COMUM/03-MAPAS-COMUNS/{NN}-{materia-slug}.md` |
| um cargo só | `{OUTPUT_DIR}/{CARGO_SLUG_UPPER}/03-MAPAS-MATERIAS/{NN}-{materia-slug}.md` |

> **`cargos_ids`, não `cargos`.** São dois campos: `cargos` traz o nome legível
> ("EDAS Serviço Social") e `cargos_ids` traz o slug (`EDAS-SERVICO-SOCIAL`). Rotear
> pelo primeiro cria pasta com espaço e acento — `EDAS Serviço Social/03-MAPAS-MATERIAS/` —
> contra a convenção UPPERCASE que o próprio validador checa.

Quando a matéria vale para mais de um cargo mas **não para todos**, gravar em `_COMUM` do
mesmo jeito e declarar a aplicabilidade no `00-INDICE.md` da pasta (ex.: "⚠️ Só TDAS —
Agente e Cuidador Social").

> Esta regra existe porque a ausência dela custou caro. A skill escrevia **sempre** por
> cargo, então num concurso multi-cargo a mesma matéria comum era mapeada N vezes — no BB
> viraram 5 matérias × 2 cargos = 10 arquivos quase idênticos — e o `_COMUM/03-MAPAS-COMUNS/`
> que o README, o `SETUP-VAULT.md` e o `site_collector.py` leem **nunca era escrito**. O
> consumidor lia o que o produtor não produzia, e o efeito visível era matéria aprofundada
> aparecendo no site sem aba Plano.

**Importante**: rodar todos os mapeamentos em paralelo na mesma mensagem (uma chamada Task por matéria). Para 8 matérias = 8 chamadas Task simultâneas.

**Ao terminar, conferir a cobertura**: toda matéria do edital tem de ter mapa. O
`validate_output.py` checa isso na Etapa 10, mas um subagent que falhou (2 retries e
segue) é mais barato de reprocessar agora do que depois.

### Etapa 6 — Coleta de materiais (subagent `material-collector`)

Delegar `material-collector` com:
- lista completa de matérias e tópicos
- lista de leis citadas no edital (extraída pelo edital-parser)

O subagent vai:
1. Para cada matéria, listar livros de referência (sem download, só nome+autor+ISBN)
2. Listar canais YouTube gratuitos (URLs)
3. Listar plataformas de questões (URLs filtradas pela banca quando possível)
4. **Baixar PDFs das leis** citadas no edital:
   - Federais: `planalto.gov.br/ccivil_03/_ato{ANO}/LEI/L{NUMERO}.htm`
   - DF: `sinj.df.gov.br`
   - Resoluções: portais oficiais (MDS, CNAS, CFP, etc.)
5. Salvar em `{OUTPUT_DIR}/_COMUM/04-MATERIAIS/`

### Etapa 7 — Histórico do órgão (subagent `historico-researcher`)

Delegar com:
- nome do órgão e siglas históricas (ex: Sedes ⇒ Sedes/Sedest/Sedestmidh)
- cargo pretendido (para verificar se houve vaga em edições anteriores)

O subagent vai:
1. Pesquisar concursos do órgão nos últimos 15 anos
2. Identificar bancas anteriores
3. Verificar histórico de vagas para o cargo
4. **Baixar PDFs de editais anteriores** quando disponíveis publicamente
5. Identificar URLs de provas anteriores (mas só baixar se for prova com o cargo específico)
6. Salvar em `{OUTPUT_DIR}/_COMUM/05-HISTORICO-CONCURSO/`

### Etapa 8 — Sinergias (subagent `sinergia-finder`)

Delegar com:
- banca atual
- lista de matérias do edital

O subagent vai:
1. Buscar concursos recentes (últimos 5 anos) da mesma banca
2. Filtrar por aqueles com pelo menos 3 matérias em comum
3. **Baixar até 3 provas anteriores** (com gabarito) priorizando:
   - mesma banca + mesma matéria-chave do cargo (ex: AFO, SUAS)
   - concursos do mesmo estado/região
4. Salvar em `{OUTPUT_DIR}/_COMUM/06-SINERGIA/`

### Etapa 9 — Discursiva (condicional)

Se `estrutura_prova.discursiva.presente == true`:

```
9.1 Identificar formato (estudo de caso / dissertação / redação)
9.2 Extrair critérios de avaliação do edital
9.3 Gerar lista de temas prováveis baseada em matérias específicas + atualidades do órgão
9.4 Sugerir estrutura padrão de resposta
9.5 Calendarizar treinos (mínimo 6-8 ao longo do cronograma)
9.6 Salvar em {OUTPUT_DIR}/{CARGO_SLUG_UPPER}/07-DISCURSIVA/guia-discursiva.md
    (nome fixo: o SEDES gerou `guia-discursiva.md` e o BB `discursiva.md`, porque a
    etapa so dizia a pasta)
```

### Etapa 9b — Avaliação de títulos (condicional, POR CARGO)

Títulos raramente valem para todos os cargos: no SEDES, o edital os dá
**exclusivamente ao EDAS**, e o TDAS não tem. Por isso a condição é por cargo, lida de
`estrutura_prova_por_cargo[{CARGO}].titulos.presente`, com queda para
`estrutura_prova.titulos.presente` quando não houver divergência entre cargos.

Se verdadeiro, para cada cargo elegível:

```
9b.1 Extrair do edital o QUADRO DE ATRIBUIÇÃO DE PONTOS: alínea, título aceito,
     pontuação por item e máximo por alínea (é uma tabela do edital — copiar os
     valores, nunca estimá-los)
9b.2 Registrar o total máximo e a regra de teto ("ainda que a soma exceda")
9b.3 Extrair as regras de entrega: onde enviar, prazo, formato, o que desclassifica
     um documento (ilegível, alínea errada)
9b.4 Montar checklist acionável de documentos a reunir, separando titulação
     acadêmica de experiência profissional — a alínea de experiência costuma ser a
     de maior peso e a que exige mais tempo de coleta
9b.5 Salvar em {OUTPUT_DIR}/{CARGO_SLUG_UPPER}/08-TITULOS.md usando titulos.md.tpl
```

> **Por que isto existe.** O artefato já era publicado pelo site (o `site_collector`
> reconhece `08-TITULOS` e trata arquivo solto, não só pasta) e já existia no vault —
> feito à mão. Só o **produtor** faltava: nenhuma etapa gerava. A Etapa 10 passa a
> checar os dois lados: cargo com títulos e sem arquivo, e arquivo sem títulos no meta.

> **Não inventar pontuação.** O quadro de pontos é dado do edital. Alínea que não
> ficar clara vira pendência para conferência humana, como manda a regra geral.

### Etapa 10 — Índices, validação e finalização

```
10.1 Gerar 00-INDICE.md de cada pasta com links wikilink para todos os arquivos
10.2 Gerar 99-Status.md com checklist global de progresso
10.3 Rodar scripts/validate_output.py para checar:
     - Todos os {placeholders} preenchidos
     - Links wikilink resolvem
     - Soma de questões bate com total da prova
     - (modo oficial) Cronograma termina antes da prova
     - (modo previsto) Cronograma é relativo e banner PROVISÓRIO presente
     - Cargo com títulos tem 08-TITULOS.md (e não há 08-TITULOS.md em cargo que o
       meta diz não ter títulos — os dois lados denunciam erros diferentes)
     - PDFs baixados são válidos
10.4 Gravar .meta.json (formato JSON nativo — item 11) contendo, no mínimo:
     - orgao, orgao_sigla, ano, banca, modo, data_geracao
     - datas_chave (prova_data etc.; null no modo previsto)
     - estrutura_prova COMPLETA (objetiva.total_questoes, discursiva, titulos,
       vagas_ac, vagas_total, salario) — necessária para o DIFF ESTRUTURAL (item 16).
       `vagas_ac` e `salario` ficam na RAIZ: é de lá que o site os lê.
     - estrutura_prova_por_cargo quando a estrutura DIFERIR entre cargos. No SEDES,
       títulos valem exclusivamente para o EDAS; gravar um único
       `titulos.presente: false` com uma observação em prosa afirma o falso para um
       dos três cargos — num campo que alimenta o diff estrutural da retificação
     - materias[] com o CONTEÚDO PROGRAMÁTICO INTEGRAL: cada matéria com
       nome, subitem_edital e a lista `topicos` completa (item 7 — o diff exige
       materias[].topicos íntegros; gravar só hashes quebra a reconciliação)
     - edital_hash: SHA-256 do texto extraído do edital (item 21 — permite detectar
       automaticamente, numa reconciliação futura, se o edital fornecido é o mesmo
       ou uma versão diferente/retificada)
     - por-cargo (multi-cargo): repetir estrutura_prova/materias por cargo quando divergirem
10.5 Finalizar log com sumário (tempo total, arquivos gerados, downloads ok/falhos)
10.6 Apresentar ao usuário sumário com:
     - Estrutura criada
     - Quantidade de arquivos gerados
     - Pendências (se houver)
     - Próximos passos sugeridos
```

## Fluxo de RECONCILIAÇÃO (`--reconciliar`)

Acionado com `--reconciliar --edital "<edital novo>.pdf"`. Cobre **dois casos**, detectados automaticamente pelo estado da pasta existente do concurso. Não roda as 10 etapas isoladamente — executa este fluxo dedicado e, dentro dele, gera a nova versão oficial.

### R.0 — Detecção de caso (item 4)

```
R.0.1 Descobrir a pasta-alvo do concurso (item 5: buscar por PREFIXO, não por ano fixo):
      - Derivar {ORGAO} do edital novo. Listar em CONCURSOS/ todas as pastas que
        casem com "{ORGAO}_*" (qualquer ano/sufixo).
      - Para cada candidata, ler .meta.json e casar por orgao (+ cargo, se multi-cargo).
      - Preferir, nesta ordem: *_V2-OFICIAL > *_OFICIAL (sem sufixo) > *_PREVISTO.
R.0.2 Calcular o hash com `python3 scripts/edital_hash.py <edital> --comparar <pasta-alvo>`.
      NAO calcule o hash de outro jeito: o script e a fonte de verdade e define a
      canonicalizacao do texto (CRLF, espaco no fim de linha, linhas em branco no
      fim). Quando o calculo ficava a cargo do modelo, o SEDES gravou o hash dos
      BYTES do PDF e o BB gravou o do TEXTO — duas convencoes, e no SEDES o
      "edital identico" nunca era reconhecido.
      - Se IGUAL: avisar "o edital fornecido é idêntico ao já processado; nada a reconciliar"
        e encerrar (a menos que --force-overwrite).
      - Se DIFERENTE: seguir.
R.0.3 Determinar o caso:
      - CASO A (previsto → oficial): pasta-alvo é *_PREVISTO.
      - CASO B (oficial → retificado): pasta-alvo já é oficial (*_OFICIAL ou *_V2-OFICIAL).
```

### CASO A — previsto → oficial

```
A.1 Renomear {ORGAO}_{ANO}_PREVISTO -> {ORGAO}_{ANO}_V1-PREVISTO
    (NÃO alterar o conteúdo interno — preserva progresso, resumos, flashcards do aluno)
A.2 Ler o .meta.json da V1 (conteúdo programático antigo)
A.3 Executar as 10 etapas no modo oficial -> {ORGAO}_{ANO}_V2-OFICIAL (com datas reais)
A.4 diff (V1 vs V2); gerar 00-DIFF-PREVISTO-VS-OFICIAL.md (diff-reconciliacao.md.tpl)
A.5 Migração de progresso assistida (regra do item 17, ver abaixo)
A.6 Índice: V1-PREVISTO = "📦 arquivada"; V2-OFICIAL = "✅ ativa"
A.7 Gravar no .meta.json da V2: reconciliado_de: V1-PREVISTO, data_reconciliacao,
    edital_hash (novo), contagem de mudanças
```

### CASO B — oficial → oficial RETIFICADO (item 4)

```
B.1 Determinar o próximo selo de versão da pasta oficial vigente:
    - Se a vigente é *_OFICIAL (sem número) ou *_V2-OFICIAL -> nova = *_V3-RETIFICADO
    - Se já houver retificações, incrementar: V3 -> V4 -> ... (ler maior Vn existente)
    NUNCA sobrescrever a oficial vigente; ela é arquivada como referência.
B.2 Ler o .meta.json da versão oficial vigente (conteúdo programático + estrutura)
B.3 Executar as 10 etapas no modo oficial sobre o edital RETIFICADO -> {ORGAO}_{ANO}_V{n}-RETIFICADO
B.4 diff (vigente vs retificada) com scripts/diff_editais.py, que roda POR CARGO
    (aceita --cargo para restringir a um):
    - inclui o DIFF ESTRUTURAL (item 16): vagas, salário, nº de questões, pesos,
      presença de discursiva, datas — retificações costumam mexer nesses campos
B.5 Gerar {…}_V{n}-RETIFICADO/00-DIFF-RETIFICACAO.md (mesmo template de diff,
    cabeçalho ajustado para "vigente vs retificado")
B.6 Migração de progresso assistida (item 17): copiar o ARQUIVO de mapa inteiro
    dos tópicos mantidos/alterados, marcando no topo os tópicos que mudaram/saíram
B.7 Índice: versão anterior = "📦 arquivada (pré-retificação)"; retificada = "✅ ativa"
B.8 Gravar no .meta.json da retificada: retificado_de: V{n-1}, data_reconciliacao,
    edital_hash (novo), contagem de mudanças (incl. estruturais)
```

### Regra de migração de progresso (item 17)

A granularidade é por **arquivo de matéria** (o "Meu resumo" e os checkboxes vivem no arquivo da matéria, não por tópico isolado):

- Matéria **integralmente mantida**: copiar o arquivo de mapa inteiro da versão anterior para a nova, sem alteração.
- Matéria **parcialmente alterada**: copiar o arquivo inteiro e inserir, no topo, um bloco `> ⚠️ REVISAR` listando os tópicos que mudaram (🔀) ou saíram (🔴) e os novos (🆕) a estudar.
- Matéria **nova**: criar do zero (sem migração).

### Multi-cargo na reconciliação (item 8)

Quando o concurso tem mais de um cargo (`_COMUM/` + subpastas por cargo), a reconciliação roda **por cargo**: o diff de conteúdo programático e a migração de progresso são executados uma vez para cada subpasta de cargo. O `_COMUM/` (edital, materiais, histórico, sinergia) é reconciliado uma única vez e compartilhado. O relatório de diff é gerado por cargo (`{CARGO}/00-DIFF-*.md`) mais um resumo consolidado na raiz.

Ao final (ambos os casos), apresentar sumário: tópicos mantidos/removidos/novos/alterados, mudanças estruturais, quanto de progresso migrou e o que exige revisão manual.

## Estrutura gerada (referência)

```
{vault}/30_AREAS/CARREIRA/CONCURSOS/{ORGAO_SIGLA}_{ANO}/
├── 00-INDICE.md
├── .meta.json                        # metadata para re-execuções
├── _COMUM/                          # materiais compartilhados (multi-cargo)
│   ├── 01-EDITAL/
│   │   ├── edital-original.pdf
│   │   ├── edital-resumo.md
│   │   ├── cronograma-oficial.md
│   │   └── analise-banca.md
│   ├── 04-MATERIAIS/
│   │   ├── livros-recomendados.md
│   │   ├── canais-youtube.md
│   │   ├── plataformas-questoes.md
│   │   └── leis-baixadas/
│   │       ├── 00-INDICE.md
│   │       ├── *.md              # cada lei em Markdown (linkável no vault)
│   │       └── *.pdf             # e em PDF (arquivo fiel)
│   ├── 05-HISTORICO-CONCURSO/
│   │   ├── concursos-anteriores.md
│   │   ├── editais-anteriores/*.pdf
│   │   └── provas-anteriores/*.pdf
│   └── 06-SINERGIA/
│       ├── concursos-similares.md
│       └── provas-baixadas/*.pdf
├── {CARGO-SLUG-UPPER-1}/            # ex: EDAS-ADMINISTRACAO
│   ├── 02-CRONOGRAMA/
│   ├── 03-MAPAS-MATERIAS/
│   ├── 07-DISCURSIVA/               # se aplicável
│   ├── 08-TITULOS.md                # se o cargo tiver avaliação de títulos
│   └── 99-Status.md
└── {CARGO-SLUG-UPPER-2}/            # se multi-cargo, ex: TDAS-ADMINISTRATIVO
    └── ...
```

**Variações do nome da pasta do concurso conforme o estado:**

| Estado | Nome da pasta | Quando |
|---|---|---|
| Oficial direto | `SEDES_2026` | `--modo oficial` (default), edital já publicado |
| Previsto | `SEDES_2027_PREVISTO` | `--modo previsto`, sem edital ainda |
| Pós-reconciliação (arquivada) | `SEDES_2027_V1-PREVISTO` | a versão prevista após o oficial sair |
| Pós-reconciliação (ativa) | `SEDES_2027_V2-OFICIAL` | nova versão com datas reais + diff |

No modo previsto, dentro da pasta:
- `_COMUM/01-EDITAL/` contém `edital-proxy.pdf` (o anterior) em vez de `edital-original.pdf`
- `02-CRONOGRAMA/` contém `cronograma-relativo.md` (não `cronograma-oficial.md`)
- Todos os `.md` têm banner `> ⚠️ CONTEÚDO PROVISÓRIO`
- A V2-OFICIAL inclui adicionalmente `00-DIFF-PREVISTO-VS-OFICIAL.md`

## Idempotência (re-execução)

Se a pasta destino já existe:

1. Ler `.meta.json` com hashes da geração anterior
2. Comparar com estado atual dos arquivos
3. Se algum arquivo foi modificado pelo usuário (hash diferente), **preservar** e listar em pendências
4. Sem `--force-overwrite`, perguntar: substituir tudo / atualizar mantendo mudanças / abortar

## Tratamento de erros

- **Edital sem dados claros**: pedir confirmação ao usuário (modo interativo)
- **Lei não encontrada**: registrar em `.logs/{ORGAO}_{ANO}/pendencias.md` e seguir
- **Banca desconhecida**: usar perfil genérico + alertar usuário
- **Subagent timeout**: 2 retries, depois falha graciosa preservando o que já foi feito
- **Download falho**: registrar em `.logs/downloads-falhos.md` com URL para tentativa manual

## Logs

Localização base: `{vault}/30_AREAS/CARREIRA/CONCURSOS/.logs/`

Item 15 — **logs por concurso**: quando `defaults.logs_por_concurso: true` (padrão), os arquivos de pendências/downloads ficam em subpasta por concurso, evitando misturar execuções de concursos diferentes:

```
.logs/
├── execucao-{TIMESTAMP}.log          # log geral da execução (com carimbo do concurso)
├── {ORGAO}_{ANO}/
│   ├── downloads-falhos.md           # URLs que falharam, para retry manual
│   ├── downloads-suspeitos.md        # baixados de fora da whitelist (item 12)
│   └── pendencias.md                 # coisas que precisam de ação humana
└── {OUTRO_ORGAO}_{ANO}/ ...
```

Os subcomandos de `scripts/log_helper.py` aceitam `--concurso {ORGAO}_{ANO}` para escrever na subpasta correta.

## Templates usados

Todos em `assets/templates/`:
- `edital-resumo.md.tpl`
- `cronograma-oficial.md.tpl`
- `cronograma-relativo.md.tpl` — **(modo previsto)** cronograma sem datas
- `cronograma-macro.md.tpl`
- `cronograma-semanal.md.tpl` — **(opcional, Etapa 4.6)** detalhe semana a semana
- `analise-banca.md.tpl`
- `mapa-materia.md.tpl`
- `historico-concurso.md.tpl`
- `concursos-similares.md.tpl`
- `discursiva.md.tpl`
- `titulos.md.tpl` — **(Etapa 9b)** avaliação de títulos, por cargo elegível
- `diff-reconciliacao.md.tpl` — **(reconciliação)** relatório previsto vs oficial
- `indice-pasta.md.tpl`
- `status.md.tpl`

## Scripts utilitários

Em `scripts/`:
- `extract_edital.py` — extrai texto do PDF via pdftotext
- `materia_id.py` — **FONTE DE VERDADE da identidade de matéria**: resolve o
  `materia_id` reusando o que já está declarado no `.meta.json`, em vez de re-derivar.
  Não reimplemente a convenção em outro script
- `validate_parsed.py` — valida a saída da Etapa 2 contra `assets/schema-edital.json`;
  roda ANTES da Etapa 3 e para o fluxo se o contrato estiver quebrado
- `fetch_lei.py` — **baixa lei de fonte oficial e gera MD + PDF** (item 9)
- `fetch_pdf.py` — download robusto com retry e validação de header `%PDF` (para fontes que já servem PDF nativo)
- `slugify.py` — converte cargo/órgão em slug UPPERCASE para nome de pasta
- `diff_editais.py` — **(reconciliação)** compara conteúdo programático + estrutura da
  prova entre versões, **por cargo**. Lê `materias[].cargos_ids` e `materias_por_cargo`
- `edital_hash.py` — **fonte de verdade do `edital_hash`**: SHA-256 do texto
  canonicalizado, mais o `edital_pdf_sha256` dos bytes. Não calcule o hash em outro lugar
- `validate_output.py` — validação pós-geração
- `log_helper.py` — utilitário de logging (com subpasta por concurso)
- `tests/test_smoke.py` — suíte de smoke tests (pytest ou standalone)

## Comportamento padrão

- Sempre rodar em **modo completo** (não há modo draft)
- Sempre tentar **baixar** leis (em MD+PDF) e provas (a menos de `--no-download`)
- Sempre preservar arquivos modificados pelo usuário em re-execuções
- Sempre gerar log simples (tempo + falhas)
- Sempre validar output antes de finalizar

## Idioma

Todo o conteúdo gerado em **Português brasileiro**.

## Sumário final apresentado ao usuário

Ao terminar, mostrar:
```
✅ Estrutura gerada em: {caminho}
📊 Arquivos criados: {N}
📥 PDFs baixados: {ok}/{total}
⏱️ Tempo total: {duração}
⚠️ Pendências: {qtd} (ver .logs/pendencias.md)

Próximos passos sugeridos:
1. Abrir {OUTPUT_DIR}/00-INDICE.md no Obsidian
2. Revisar o cronograma em 02-CRONOGRAMA/
3. Conferir pendências em .logs/pendencias.md
4. Começar pelo assunto de prioridade alta identificado em 03-MAPAS-MATERIAS/
```
