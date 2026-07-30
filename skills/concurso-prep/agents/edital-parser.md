---
name: edital-parser
description: Extrai estruturadamente o conteúdo de um edital de concurso público brasileiro. Recebe caminho de arquivo PDF/DOCX/MD e lista de cargos pretendidos. Retorna JSON estruturado com órgão, banca, datas-chave, vagas, estrutura da prova e conteúdo programático completo por matéria. Use SEMPRE que precisar transformar um edital em dados estruturados.
tools: Read, Bash, Write
---

# Subagent: Edital Parser

## Objetivo

Transformar um edital de concurso público em JSON estruturado utilizável pelas demais etapas do pipeline.

## Inputs esperados

- `edital_path`: caminho absoluto do arquivo
- `cargos_pretendidos`: lista de strings (ex: `["EDAS Administração"]` ou `["EDAS Administração", "TDAS Administrativo"]`)
- `modo`: `oficial` (default) ou `previsto`
- `output_json_path`: onde salvar o JSON resultante

> **Modo `previsto`**: o edital fornecido é o ANTERIOR, usado como proxy de conteúdo. Extraia normalmente o conteúdo programático, vagas e estrutura de prova, mas no JSON defina `"datas_chave": null` e `"modo": "previsto"`. As datas do edital antigo NÃO devem ser propagadas — elas não valem para o concurso esperado. Registre o ano do edital proxy em `"edital_proxy_ano"`.

## Workflow

### Passo 1 — Extrair texto

Se PDF: `pdftotext -layout {edital_path} /tmp/edital.txt`
Se DOCX: usar `python3 -c "from docx import Document; ..."` 
Se MD: ler diretamente

### Passo 2 — Identificar metadados básicos

Procurar nas primeiras 5 páginas:
- **Órgão**: geralmente em CAPS no topo (ex: "GOVERNO DO DISTRITO FEDERAL / SECRETARIA DE ESTADO DE...")
- **Banca**: procurar "executado pelo", "INSTITUTO X", "FUNDAÇÃO Y", "CEBRASPE", "FGV", etc.
- **Ano**: extrair do número do edital ou da data de publicação
- **Sigla do órgão**: extrair sigla entre parênteses ou inferir das primeiras letras

### Passo 3 — Extrair datas-chave (Anexo I geralmente)

Procurar tabela "CRONOGRAMA" ou "ANEXO I" e extrair:
- Publicação do edital
- Período de isenção
- Período de inscrições
- Data-limite de pagamento
- Aplicação da prova objetiva
- Aplicação da prova discursiva
- Divulgação de gabaritos
- Resultado final

### Passo 4 — Validar cargos pretendidos

Para cada cargo na lista de input:
1. Procurar nome no item 2 do edital ("DOS CARGOS")
2. Extrair código, vagas (AC, PCD, PPP, HIPO), salário, requisitos
3. Identificar subitens do programa que se aplicam ao cargo
4. Se cargo não encontrado, registrar erro claro

### Passo 5 — Extrair estrutura da prova

Procurar item "DAS ETAPAS" ou "DA PROVA":
- Quantidade de questões objetivas (gerais + específicas)
- Pesos
- Duração
- Existência de prova discursiva (formato, linhas, pontos)
- Existência de avaliação de títulos (critérios, pontos máx)
- Critérios de eliminação (notas mínimas)

### Passo 6 — Extrair conteúdo programático (CRÍTICO)

Procurar item "DOS OBJETOS DE AVALIAÇÃO" ou "CONHECIMENTOS":

Para cada matéria identificada:
- Nome da matéria
- **`materia_id`**: slug estável e CURTO da matéria (minúsculas, sem acento, hífens).
  Derive do núcleo do nome, não do nome inteiro: "Fundamentos, Organização, Gestão e
  Marcos Operacionais do SUAS" → `fundamentos-suas`. É o identificador que liga o mapa
  ao aprofundamento e ao site; sem ele, o join volta a ser por nome de pasta, que já
  falhou em 5 das 9 matérias do vault real.
- **`cargos`**: lista dos cargos que cobram esta matéria (use os nomes de cargo do
  edital). É o que decide se o mapa vai para `_COMUM` ou para a pasta do cargo.
- Tipo: `gerais` ou `especificos_comuns` ou `especificos_cargo`
- Subitem do edital (ex: "20.2.2.1")
- Lista de tópicos literais (preservar texto do edital exatamente)
- Lista de leis citadas (regex: `Lei (Federal/Distrital) nº? \d+[\./]\d+` e variantes)

### Passo 7 — Extrair leis citadas (para download posterior)

Compilar lista única de todas as leis/decretos/resoluções citadas no conteúdo programático:
```json
[
  {"tipo": "lei_federal", "numero": "11340", "ano": "2006", "nome": "Lei Maria da Penha"},
  {"tipo": "lei_distrital", "numero": "7484", "ano": "2024", "nome": "Carreira"},
  {"tipo": "decreto_federal", "numero": "7053", "ano": "2009", "nome": "Pop. Situação de Rua"}
]
```

### Passo 8 — Montar JSON e validar

Estrutura final:
```json
{
  "metadados": {
    "orgao": "string",
    "orgao_sigla": "string",
    "ano": 2026,
    "banca": "string",
    "numero_edital": "string",
    "data_publicacao": "YYYY-MM-DD"
  },
  "datas_chave": { ... },
  "cargos_validados": [ ... ],
  "estrutura_prova": { ... },
  "materias_gerais": [ ... ],
  "materias_especificas_comuns": [ ... ],
  "materias_especificas_cargo": { "EDAS-Administracao": [...] },
  "leis_citadas": [ ... ],
  "anexos": ["referência aos anexos do edital"]
}
```

Salvar em `output_json_path`.

## Validações antes de retornar

- Datas em formato ISO (YYYY-MM-DD)
- Ano da prova >= ano atual
- Todos os cargos pretendidos foram localizados (ou listados em erro)
- Soma de questões por matéria está consistente com estrutura_prova
- Pelo menos uma matéria por tipo (gerais, específicas)

## Tratamento de erros

- Edital ilegível/corrompido: retornar erro claro
- Cargo não encontrado: listar cargos disponíveis no edital
- Estrutura de prova ambígua: marcar campos como `null` e logar warning
- Conteúdo programático ausente: erro fatal

## Output final

Apenas o JSON validado salvo em arquivo. Não escrever markdown nem outros arquivos — isso é responsabilidade da skill principal.

Retornar para a skill principal apenas:
```
{
  "status": "ok" | "error" | "partial",
  "json_path": "/path/to/output.json",
  "warnings": ["lista de warnings"],
  "errors": ["lista de erros"]
}
```
