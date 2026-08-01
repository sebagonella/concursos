---
title: "Diff: Previsto vs Oficial - {ORGAO} {ANO}"
tipo: documentacao
gerado_em: {DATA_RECONCILIACAO}
versao_anterior: V1-PREVISTO
versao_atual: V2-OFICIAL
tags: [concurso/{ORGAO_SLUG}/reconciliacao]
---

# 🔀 Relatório de Reconciliação — {ORGAO} {ANO}

Comparação entre a versão **prevista** (baseada no edital {ANO_PROXY}) e o **edital oficial** agora publicado.

- **Versão prevista (arquivada)**: [[{ORGAO_SLUG}_{ANO}_V1-PREVISTO/00-INDICE|V1-PREVISTO]]
- **Versão oficial (ativa)**: [[{ORGAO_SLUG}_{ANO}_V2-OFICIAL/00-INDICE|V2-OFICIAL]]

## Resumo das mudanças

| Categoria | Quantidade |
|---|---|
| 🟢 Mantidos (estudar continua valendo) | {N_MANTIDOS} |
| 🔴 Removidos (parar de estudar) | {N_REMOVIDOS} |
| 🆕 Novos (começar a estudar) | {N_NOVOS} |
| 🔀 Alterados (revisar) | {N_ALTERADOS} |

**Progresso migrado automaticamente**: {N_MIGRADOS} tópicos. **Revisão manual necessária**: {N_REVISAR} tópicos.

---

## 🟢 Mantidos — seu progresso foi preservado

Estes tópicos continuam no edital oficial. Resumos e checkboxes da V1 foram copiados para a V2.

{LISTA_MANTIDOS}

## 🔴 Removidos — não caem mais

Estes tópicos saíram do edital oficial. **Pare de estudá-los.** (Permanecem na V1 apenas como histórico.)

{LISTA_REMOVIDOS}

## 🆕 Novos — começar a estudar

Estes tópicos são novidade no edital oficial. Não havia equivalente na versão prevista.

{LISTA_NOVOS}

## 🔀 Alterados — revisar com atenção

Mudaram de alguma forma (lei trocada, redação diferente, peso/quantidade alterados). O progresso foi copiado mas marcado para revisão.

{LISTA_ALTERADOS}

---

## 📅 Datas agora disponíveis

O cronograma relativo foi convertido em cronograma com datas reais.

| Evento | Data |
|---|---|
| Publicação do edital | {DATA_PUBLICACAO} |
| Inscrições | {DATA_INSCRICOES} |
| **Prova** | **{DATA_PROVA}** |
| Resultado final | {DATA_RESULTADO} |

**Dias até a prova**: {DIAS_RESTANTES} → cronograma recalibrado para o perfil **{PERFIL_CRONOGRAMA}**.

Veja o novo cronograma em [[{ORGAO_SLUG}_{ANO}_V2-OFICIAL/{CARGO_SLUG}/02-CRONOGRAMA/cronograma-macro|Cronograma Oficial]].

---

## ✅ Próximos passos

- [ ] Revisar os tópicos marcados em 🔀 Alterados
- [ ] Iniciar os tópicos em 🆕 Novos
- [ ] Remover da rotina os tópicos em 🔴 Removidos
- [ ] Conferir o novo cronograma com datas e ajustar ritmo de estudo
- [ ] Refazer simulados considerando a nova distribuição de matérias
