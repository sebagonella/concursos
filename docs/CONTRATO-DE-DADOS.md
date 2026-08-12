# Contrato de dados entre as skills

As cinco skills não se chamam. Elas se comunicam **pelo vault**: uma escreve
arquivos, a seguinte os lê. Esse acoplamento é de propósito — o usuário edita o
material entre as etapas, e um formato intermediário em memória o deixaria de fora.

O preço é que os nomes de campo viram contrato público sem parecer contrato. Este
documento existe porque, até ele, as chaves só existiam nos `.md.tpl`: quem
precisasse consertar vínculo de material legado tinha de ler o gerador para
descobrir que `topico_id` é **lista**, e o `ARQUITETURA.md` chegou a afirmar que a
Etapa 2 lia o `.meta.json` — que nenhum dos seus 17 scripts abre.

> Quando este documento e o código divergirem, **o código vence** e este documento
> está com defeito. Os `.md.tpl` de `skills/*/assets/templates/` são a fonte.

---

## O mapa geral

```
concurso-prep ──> .meta.json          ──> concurso-prep (diff), afere, publica
              └─> mapas de matéria    ──> concurso-aprofunda, publica
                  materiais/leis      ──> aprofunda (fontes), publica

concurso-aprofunda ──> .md do assunto ──> publica, afere
                   ├─> flashcards      ──> publica (quiz)
                   └─> _fonte-notebooklm.md ──> notebooklm (executa), publica (página)

concurso-notebooklm ──> mídias + notebooklm_url ──> publica

concurso-afere ──> 00-AFERICAO-*.md ──> publica
```

Uma leitura que **não** existe, e é o engano comum: a `concurso-aprofunda` não abre
o `.meta.json`. O que ela lê são os mapas.

---

## 1. `.meta.json` — a metadata do concurso

Fica na raiz da pasta do concurso. **JSON, não YAML** — decisão travada, porque o
motor de diff precisa do conteúdo programático integral e YAML aninhado a essa
profundidade é frágil de editar à mão.

| Campo | Tipo | Quem escreve | Quem lê |
|---|---|---|---|
| `orgao`, `orgao_sigla`, `ano`, `banca` | string / int | prep | publica (`meta`), afere (banca) |
| `modo` | `oficial` \| `previsto` | prep | afere (ressalva de tautologia), publica |
| `edital_hash` | string SHA-256 | prep | prep (detecta edital alterado) |
| `materias[].nome` / `.materia_id` / `.tipo` | string | prep | prep (diff), publica |
| `materias[].topicos[]` | lista de string | prep | prep (**motor de diff**) |
| `materias[].cargos_ids[]` | lista, `^[A-Z0-9-]+$` | prep | prep, publica |
| `estrutura_prova.objetiva.total_questoes` | int | prep | prep (diff), publica |
| `estrutura_prova.discursiva` | `{"presente": bool, "tipo"?: str}` | prep | prep (diff) |
| `estrutura_prova.titulos` | `{"presente": bool}` | prep | prep (diff) |
| `estrutura_prova_por_cargo` | `{SIGLA: {discursiva, titulos}}` | prep | prep (diff **por cargo**) |
| `cargos_validados[]` | lista de objeto | prep | publica (vagas/salário multi-cargo) |
| `datas_chave.prova_data` | `YYYY-MM-DD` | prep | prep (diff), publica |

**`cargos_ids`, não `cargos`.** Rotear pelo nome do cargo cria pastas como
`EDAS Serviço Social/`. O schema (`skills/concurso-prep/assets/schema-edital.json`)
exige o formato UPPERCASE.

**`discursiva` é objeto, não booleano.** `{"presente": false}` é *truthy* em Python:
avaliar o dict em vez do campo fez o diff estrutural devolver zero mudanças quando a
retificação ligava ou desligava a discursiva.

---

## 2. Mapa de matéria — o que a Etapa 2 realmente lê

Um `.md` por matéria, em `{ESCOPO}/03-MAPAS-MATERIAS/` ou, quando a matéria vale
para mais de um cargo, em `_COMUM/03-MAPAS-COMUNS/`.

### Frontmatter

| Campo | Tipo | Observação |
|---|---|---|
| `tipo` | `mapa-materia` | |
| `materia` | string | rótulo de leitura ("Língua Portuguesa") |
| `materia_id` | slug | **identidade declarada**, nunca re-derivada do nome |
| `cargos` | lista | quem cobra esta matéria |
| `subitem_edital` | string | o item do edital de onde ela saiu |
| `prioridade` | `alta` \| `media` \| `base` | selo no site |
| `questoes_estimadas` | int | selo no site — a chave é esta, não `estimativa_questoes` |

### Corpo

Um `## ` por tópico do edital; dentro dele, H3 do template (`Tópicos do edital
(literais)`, `Subtópicos derivados`, `Material recomendado`, `Pegadinhas da banca`,
`Meta`). H3 fora do template é **publicado assim mesmo e avisado** na geração — e
rótulo repetido no mesmo tópico **acumula**, nunca sobrescreve.

---

## 3. `.md` do assunto aprofundado

O path é o contrato tanto quanto o frontmatter:

```
{ESCOPO}/03-APROFUNDAMENTO/{materia}/assuntos/{assunto}/
└── {nivel}--{fonte1}[+{fonte2}]/
    ├── {assunto}--{nivel}--{fonte1}[+…]--{CONCURSO}.md
    ├── flashcards-{mesmo-nome-base}.md / .csv
    ├── cards.json
    └── _fonte-notebooklm.md
```

A regra vive em `skills/concurso-aprofunda/scripts/aprofundamento_id.py`, que é
fonte de verdade com cópia sincronizada em `concurso-publica` — travada por teste
nas duas skills.

| Campo | Tipo | Quem lê | Observação |
|---|---|---|---|
| `title` | string | publica | |
| `materia`, `materia_id` | string / slug | publica, afere | |
| **`topico_id`** | **lista** `[slug, …]` | publica (cobertura) | ver abaixo |
| `topico` | lista de string | publica | o literal do edital |
| `concurso` | string | publica | |
| `tipo` | `assunto-aprofundado` | publica | |
| `localizacao_livro` | string livre | publica | ponteiro da **fonte 1** |
| `localizacao_2`, `localizacao_3`… | string livre | publica | uma por fonte adicional |
| `confianca_localizacao` | `alta` \| `media` \| `baixa` | publica | `baixa` vira pendência |
| `prioridade` | `alta` \| `media` \| `base` | publica | agrupa os cards |
| `aprofundamento` | string | publica | o id (`padrao--pestana`) |
| `nivel` | `padrao` \| `detalhado` | publica, afere | |
| `fontes` | string | publica | texto legível; o id manda |
| `fontes_notebook` | lista | notebooklm, publica | `[]` declarado ≠ ausente |
| `status` | `nao-iniciado` \| `revisar` \| `concluido` | publica | |
| `notebooklm_url`, `notebooklm_*` | string | publica | escritos pela Etapa 4 |

### `topico_id` é lista

`build_subject_md.py` grava `[{valor}]` e o `site_collector` itera
(`for t in a.get("topico_id") or []`). Escrever uma string crua faz a cobertura não
casar nada — **silenciosamente**, que é o modo de falha que o projeto proíbe.

Quem grava `topico_id`/`materia_id` em material legado é o par
`propor_vinculos.py` → `aplicar_vinculos.py`, da `concurso-aprofunda`.

### Localização é por fonte, em chaves numeradas

`localizacao_livro` é a fonte 1; as demais vão em `localizacao_2`, `localizacao_3`.
Chave única com `;` não serve — os ponteiros reais contêm `;` dentro deles. E **nada
é obrigado a ser parseável**: metade dos valores do vault é prosa livre. Quem quiser
página tenta extrair e **degrada**, nunca exige o formato.

---

## 4. `_fonte-notebooklm.md` — contrato da automação

O que a `concurso-notebooklm` consome vive no **frontmatter**, nunca no texto
corrido: extrair nome de arquivo por regex de prosa foi o que fez o roteiro do mapa
mental e o do report chegarem vazios ao site.

| Campo | Quem escreve | Quem lê |
|---|---|---|
| `nome_notebook` | aprofunda | notebooklm (cria o notebook), publica (exibe) |
| `arquivo_podcast` / `_mapa_mental` / `_video` / `_report` | aprofunda | notebooklm (nomeia o download), publica (detecta a mídia) |
| `notebooklm_id`, `notebooklm_url`, `notebooklm_status` | notebooklm | publica (botão do notebook) |
| `notebooklm_fontes_subidas` / `_faltando` | notebooklm | publica (ficha) |

O estado volátil (os `task_id` em voo) fica no sidecar
`_notebooklm-estado.json`, fora do frontmatter — ele muda a cada execução e cada
mudança dispararia o backup do gerador.

---

## 5. Modelo do site (`site-model.json`)

Saída do `site_collector.py`, entrada do `site_builder.py`. É contrato público
(`--modelo` está documentado no `SKILL.md`), e o exemplo vivo está em
`skills/concurso-publica/examples/site-model-exemplo.json` — **gerado pelo coletor**,
nunca escrito à mão.

Chaves de topo: `concurso`, `dir`, `meta`, `escopos[]`, `cargos[]` (alias de
compatibilidade), `descartados_placeholder[]`, `resumo`.

Dentro de cada escopo, as que mais confundem:

- **`progresso`** × **`progresso_tarefas`** — o primeiro é só o das matérias; o
  segundo soma matérias + documentos de seção + `99-Status.md`, e é o que a barra do
  escopo mostra.
- **`assuntos`** × **`assuntos_herdados`** — a segunda é chave à parte que a
  agregação de progresso **ignora**, senão os mesmos checkboxes contariam nos dois
  escopos.
- **`cobertura.vinculo_ausente`** — matéria com assuntos sem `topico_id`. Não é
  zero: é *desconhecido*, e ela fica fora do denominador agregado.
- **`mapa_em`** — a matéria usa o mapa de outro escopo, e por isso **não** soma os
  itens do plano (quem soma é quem guarda o arquivo).

---

## Aferição (`00-AFERICAO-*.md`)

Escrita pela `concurso-afere`, publicada pela `concurso-publica`. Uma matéria tem
legitimamente **várias** — a segunda rodada usa `--out` com nome próprio
(`…-2-POS-CORRECAO.md`).

`provas_aferidas_n` no frontmatter é obrigatório: o validador barra superlativo sem
ele, porque com uma prova só a conclusão não se sustenta (com 1 prova a aferição de
Português concluiu "empate técnico"; com 3, inverteu).
