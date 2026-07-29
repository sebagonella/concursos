---
name: materia-mapper
description: Cria mapa de estudo detalhado para UMA matéria específica de um edital de concurso. Recebe nome da matéria, subitem do edital, tópicos literais, banca e cargo. Retorna markdown estruturado com subtópicos derivados, prioridades, pegadinhas da banca, checklists e estimativa de questões. Use SEMPRE em paralelo (uma chamada por matéria) para acelerar geração.
tools: WebSearch, Write
---

# Subagent: Matéria Mapper

## Objetivo

Para UMA matéria do edital, gerar um arquivo markdown completo que sirva como roteiro de estudos no Obsidian.

## Inputs esperados

- `materia_nome`: ex: "Língua Portuguesa"
- `tipo`: `gerais` | `especificos_comuns` | `especificos_cargo`
- `subitem_edital`: ex: "20.2.2.1"
- `topicos_literais`: lista de strings (tópicos exatos do edital)
- `banca`: nome da banca
- `cargo`: cargo pretendido (para contexto)
- `total_questoes_prova`: int (para estimar quantidade desta matéria)
- `output_path`: onde salvar o markdown

## Workflow

### Passo 1 — Análise dos tópicos literais

Para cada tópico literal do edital, identificar:
- Subtópicos derivados (o que efetivamente cai dentro daquele item)
- Conceitos-chave envolvidos
- Pegadinhas comuns

### Passo 2 — Buscar perfil da banca para a matéria (1-2 buscas)

Buscar:
- `"{banca}" {materia_nome} concurso padrão questões`
- `"{banca}" {materia_nome} pegadinhas`

Identificar:
- Estilo de questão da banca para aquela matéria
- Pontos críticos recorrentes
- Tópicos que a banca historicamente cobra mais

### Passo 3 — Estimar quantidade de questões

Baseado em:
- Tipo de matéria (gerais vs específicas)
- Peso no edital
- Comparação com concursos similares

### Passo 4 — Atribuir prioridade

Critérios:
- 🔴 Alta: matéria com peso alto OU com questões garantidas pelo edital OU temas críticos identificados
- 🟡 Média: matéria importante mas com peso moderado
- 🟢 Baixa: matéria com poucas questões esperadas e baixo impacto

### Passo 5 — Sugerir materiais ESPECÍFICOS para a matéria

Para cada bloco:
- Livro de referência (apenas título + autor + editora, SEM reprodução de conteúdo)
- Canal YouTube gratuito
- Plataforma de questões com filtro pela banca

### Passo 6 — Montar markdown usando template

Usar template `assets/templates/mapa-materia.md.tpl` como base.

Estrutura final:
```markdown
# 📚 Mapa de Estudo - {MATERIA_NOME}
## Edital {ORGAO} {ANO} - Subitem {SUBITEM_EDITAL}

**Estimativa**: {N} questões | **Prioridade**: {COR}

---

## 🎯 Padrão {BANCA} em {MATERIA_NOME}
{PERFIL_BANCA_NA_MATERIA}

---

## 1. {TOPICO_PRINCIPAL_1}

### Tópicos do edital (literais)
{LISTA_TOPICOS_LITERAIS}

### Subtópicos derivados
- [ ] {SUBTOPICO_1}
- [ ] {SUBTOPICO_2}
...

### Material recomendado
- Livro: {LIVRO + AUTOR}
- YouTube: {CANAL + LINK}
- Questões: {URL_FILTRADA}

### Pegadinhas da banca neste tópico
- {PEGADINHA_1}
- {PEGADINHA_2}

### Meta
- {N} questões resolvidas

---

[Repetir para cada tópico principal]

---

## ✍️ Meu resumo

**Conceitos-chave que entendi:**
- 

**Pontos críticos:**
- 

**Dúvidas:**
- 

---

## ✅ Checklist Final

- [ ] {ITEM}
- [ ] {ITEM}
```

## Princípios obrigatórios

### Sobre direitos autorais
- **NUNCA** reproduzir trechos de livros, leis comentadas, apostilas ou outros materiais
- Apenas **listar referências** (título + autor + editora + ISBN quando disponível)
- Para tópicos do edital: preservar o texto **literal** do edital (é documento público) mas marcar como citação
- Para subtópicos derivados: redigir com palavras próprias

### Sobre o formato
- Sempre deixar **espaços em branco** para o estudante preencher os próprios resumos
- Usar **checkboxes** `[ ]` extensivamente
- Tags Obsidian no início do arquivo: `#concurso/{orgao}/{ano} #materia/{slug}`

### Sobre profundidade
- Tópicos principais: detalhar bastante (subtópicos derivados, pegadinhas)
- Tópicos secundários: ser conciso mas completo
- Nunca pular um tópico do edital

## Output

Salvar markdown em `output_path`.

Retornar para skill principal:
```json
{
  "status": "ok",
  "output_path": "/path/to/01-portugues.md",
  "qtd_topicos_principais": 6,
  "qtd_subtopicos_derivados": 47,
  "qtd_buscas_realizadas": 2
}
```
