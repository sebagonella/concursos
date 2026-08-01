---
data: {{DATA_GERACAO}}
data_atualizacao: {{DATA_GERACAO}}
tipo: cronograma
status: execucao
title: "Cronograma Relativo - {CARGO_NOME}"
concurso: "{ORGAO} (previsto)"
status: PREVISTO
modo: previsto
edital_proxy_ano: {ANO_PROXY}
tags: [concurso/{ORGAO_SLUG}/previsto, cargo/{CARGO_SLUG}]
---

> ⚠️ **CONTEÚDO PROVISÓRIO** — baseado no edital anterior ({ANO_PROXY}). Não há datas oficiais. Sujeito a alteração quando o edital oficial for publicado. Ao sair o edital, rode `--reconciliar` para converter este cronograma em datas reais.

# 📅 Cronograma Relativo — {CARGO_NOME}

Sem data de prova definida. Avance no seu próprio ritmo, seguindo a ordem de prioridade. Meta de estudo: **{HORAS_DIA}h/dia**.

## Como usar este cronograma

- As "Semanas" são **unidades relativas de progresso**, não datas de calendário.
- Avance para a próxima semana quando concluir os checkboxes da atual.
- Quando o edital oficial sair, a reconciliação ancora tudo em datas reais e ajusta o ritmo.

---

## Bloco 1 — Fundação (matérias-base de maior peso)

{BLOCO_1_MATERIAS}

## Bloco 2 — Aprofundamento (específicas do cargo + densas)

{BLOCO_2_MATERIAS}

## Bloco 3 — Consolidação (revisão + questões + simulados)

{BLOCO_3_MATERIAS}

---

## Distribuição relativa por semana

{TABELA_SEMANAS_RELATIVAS}

---

## Metas (independentes de data)

- Questões por dia: **{META_QUESTOES_DIA}+**
- Simulados livres: **{META_SIMULADOS}** (sem cronometragem fixa de data; usar como diagnóstico)
- Revisões espaçadas: D+1, D+3, D+7, D+15, D+30 a partir do estudo de cada tópico

## Quando o edital sair

1. Baixe o edital oficial para `99_INBOX/OUTROS/`
2. Rode: `concurso-prep --reconciliar --edital "99_INBOX/OUTROS/{edital-oficial}.pdf" --cargo "{CARGO_NOME}" --modo oficial`
3. A skill preserva todo o seu progresso (V1-PREVISTO) e gera a V2-OFICIAL com datas + relatório de diferenças.
