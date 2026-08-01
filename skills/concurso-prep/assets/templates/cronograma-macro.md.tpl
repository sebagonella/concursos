---
data: {{DATA_GERACAO}}
data_atualizacao: {{DATA_GERACAO}}
tipo: cronograma
status: execucao
tags:
  - concurso/{{ORGAO_SLUG}}/{{ANO}}
  - cronograma
  - cargo/{{CARGO_SLUG}}
data_geracao: {{DATA_GERACAO}}
data_prova: {{DATA_PROVA}}
horas_dia: {{HORAS_DIA}}
---

# 🗓️ Cronograma de Estudos - {{ORGAO}} {{ANO}}
## Cargo: {{CARGO_COMPLETO}}

> **Data da prova**: {{DATA_PROVA}}  
> **Dias restantes**: {{DIAS_RESTANTES}}  
> **Horas/dia disponíveis**: {{HORAS_DIA}}  
> **Total estimado de horas de estudo**: {{HORAS_TOTAIS}}

---

## 📊 Visão Geral das Fases

{{TABELA_FASES}}

---

## 🎯 Distribuição de Peso por Matéria

{{TABELA_DISTRIBUICAO_MATERIAS}}

---

## 🟦 Fases Detalhadas

{{BLOCOS_FASES}}

---

## 📌 Marcos Importantes do Cronograma

{{LISTA_MARCOS}}

---

## 📈 Metas Quantitativas Globais

| Métrica | Meta |
|---|---|
| Questões totais resolvidas | {{META_QUESTOES_TOTAL}} |
| Questões/dia (após semana 3) | {{META_QUESTOES_DIA}} |
| Simulados completos | {{META_SIMULADOS}} |
| Treinos de discursiva | {{META_DISCURSIVA}} |
| Flashcards Anki ativos | {{META_FLASHCARDS}} |
| Leituras de leis críticas | {{META_LEITURAS_LEIS}} |

---

## 🔁 Sistema de Revisões Espaçadas

Para cada matéria estudada, revisar nos intervalos:
- **D+1** (dia seguinte)
- **D+3**
- **D+7**
- **D+15**
- **D+30**
- **D+60**

Recomendação: usar **Anki** para automatizar.

---

## 🚦 Próximos passos imediatos

{{LISTA_ACOES_IMEDIATAS}}

---

## 🔗 Links

- [[cronograma-semanal|Cronograma Semanal Detalhado]]
- [[rotina-diaria|Rotina Diária]]
- [[metas-quantitativas|Metas Quantitativas]]
- [[../01-Edital/cronograma-oficial|Cronograma Oficial do Edital]]
- [[../03-Mapas-Materias/00-INDICE|Mapas por Matéria]]

---

*Gerado automaticamente em {{DATA_GERACAO}}*
