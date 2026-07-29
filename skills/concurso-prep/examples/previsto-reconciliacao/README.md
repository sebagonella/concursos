# Exemplo — Fluxo Previsto + Reconciliação

Demonstra o ciclo completo de um concurso esperado mas ainda sem edital.

## Cenário

Concurso do TJDFT esperado para ~2026, edital ainda não publicado. Existe o edital de 2015 (mesma carreira) como proxy.

## Fase 1 — Iniciar estudo no modo previsto

Edital anterior em `99_INBOX/OUTROS/edital-tjdft-2015.pdf`.

```
Use a skill concurso-prep:
- modo: previsto
- edital: "99_INBOX/OUTROS/edital-tjdft-2015.pdf"
- cargo: "Analista Judiciário - Área Administrativa"
- horas-dia: 3
```

### Resultado esperado

Pasta: `30_AREAS/CARREIRA/CONCURSOS/TJDFT_2026_PREVISTO/`

- Todos os arquivos com banner `⚠️ CONTEÚDO PROVISÓRIO`
- `_COMUM/01-EDITAL/edital-proxy.pdf` (o de 2015)
- `ANALISTA-JUDICIARIO-AREA-ADMINISTRATIVA/02-CRONOGRAMA/cronograma-relativo.md` (Semana 1, 2... sem datas)
- Mapas de matéria normais, mas marcados como provisórios
- Histórico e sinergias funcionando

### Validação

- [ ] Pasta termina em `_PREVISTO`
- [ ] Nenhuma data-calendário no cronograma
- [ ] Banner provisório em todos os `.md`
- [ ] `.meta.json` tem `modo: previsto` e `edital_proxy_ano: 2015`

## Fase 2 — O edital oficial sai (meses depois)

Edital oficial publicado em `99_INBOX/OUTROS/edital-tjdft-2026.pdf`.

```
Use a skill concurso-prep:
- reconciliar: true
- edital: "99_INBOX/OUTROS/edital-tjdft-2026.pdf"
- cargo: "Analista Judiciário - Área Administrativa"
- modo: oficial
```

### Resultado esperado

1. `TJDFT_2026_PREVISTO` renomeada para `TJDFT_2026_V1-PREVISTO` (intacta)
2. Nova `TJDFT_2026_V2-OFICIAL` gerada com datas reais
3. `TJDFT_2026_V2-OFICIAL/00-DIFF-PREVISTO-VS-OFICIAL.md` com:
   - 🟢 mantidos (progresso migrado)
   - 🔴 removidos
   - 🆕 novos
   - 🔀 alterados
   - 📅 datas reais
4. Índice raiz lista V1 (arquivada) e V2 (ativa)

### Validação

- [ ] V1 preservada sem alterações (progresso intacto)
- [ ] V2 tem cronograma com datas reais
- [ ] Diff lista corretamente as 4 categorias
- [ ] Tópicos idênticos tiveram "Meu resumo" copiado para a V2
- [ ] Tópicos alterados estão marcados "⚠️ REVISAR"

## Teste isolado do diff (sem rodar a skill inteira)

```bash
python3 scripts/diff_editais.py \
  --v1 TJDFT_2026_V1-PREVISTO/.meta.json \
  --v2 TJDFT_2026_V2-OFICIAL/.meta.json
```

Saída esperada: contagem de mantidos/removidos/novos/alterados + listas.
