---
data: {DATA}
tipo: analise
status: revisar
materia: "{MATERIA_NOME}"
materia_id: {MATERIA_ID}
concurso: {CONCURSO}
banca: "{BANCA}"
provas_aferidas: "{PROVAS_AFERIDAS}"
gabarito_fonte: "{GABARITO_FONTE}"
questoes_aferidas: {N_QUESTOES}
provas_aferidas_n: {N_PROVAS}
tags: [area/carreira, concurso/aprofundamento, analise/afericao]
---

# 🎯 Aferição do material contra prova real — {MATERIA_NOME}

> Mede o aprofundamento de {MATERIA_NOME} do vault contra **{N_QUESTOES} questões** de
> {N_PROVAS} prova(s), com **gabarito oficial**. Uma nota por nível aprofundado.

## ⚠️ O que esta medição vale — e o que ela NÃO vale
{RESSALVA_TAUTOLOGIA}
- **Amostra: {N_QUESTOES} questões em {N_PROVAS} prova(s).** Diferença menor que 1 ponto
  entre níveis está dentro do ruído — não decida nada com base em empate técnico.
- **O julgamento "responde / não responde" é do agente**, feito lendo o material contra
  cada questão. O gabarito é oficial; a atribuição de suficiência não é auditada por
  terceiro.
- A conferência de **versão do caderno e cargo** foi feita arquivo a arquivo: usar a
  tabela do caderno errado troca quase todas as respostas.

## 📊 Resultado

{TABELA_RESULTADO}

**Critério declarado:** RESPONDE = 1,0 · PARCIAL = 0,5 · NÃO RESPONDE = 0,2 (esperança do
chute em 5 alternativas). **SEM MATERIAL sai do denominador** — o tópico nunca foi
aprofundado, e isso é falha de **cobertura**, não de **profundidade**: as ações corretivas
são diferentes (escrever o assunto × aprofundar o assunto).

{NOTAS_POR_PROVA}

## 📋 Questão a questão

{TABELA_QUESTOES}

✅ responde · ⚠️ responde em parte · ❌ não responde · ⬜ sem material no vault

## 📈 Distribuição por assunto

{TABELA_DISTRIBUICAO}

## 🔻 Divergência entre níveis

{DIVERGENCIA_NIVEIS}

## ✅ Ações recomendadas

{ACOES}

## 🔗 Fontes

{FONTES}

## 📝 Para estudar depois

- [ ] Resolver as {N_QUESTOES} questões sem consultar e comparar com os gabaritos acima
{TAREFAS_EXTRA}
