# Exemplo de Teste - Sedes/DF 2026

Este diretório contém um caso de teste para validar a skill concurso-prep usando o edital real da Sedes/DF 2026 (Instituto Quadrix).

## Cenário

- **Edital**: PDF do edital nº 1 de 13/05/2026
- **Cargo**: EDAS Administração (Cargo 400)
- **Tempo até a prova**: ~107 dias (cronograma de 3 fases)

## Como rodar o teste

### Pré-requisitos
1. Skill instalada (veja `../../README.md`)
2. Vault Obsidian configurado em algum lugar
3. Edital baixado em `99_INBOX/OUTROS/` do vault

### Execução

No Claude Code, dentro do vault:

```
Use a skill concurso-prep:
- edital: "99_INBOX/OUTROS/edital-sedes-2026.pdf"
- cargo: "EDAS Administração"
- horas-dia: 4
```

### Resultado esperado

Pasta gerada: `30_AREAS/CARREIRA/CONCURSOS/SEDES_2026/`

Com aproximadamente:
- 30+ arquivos `.md`
- 10+ PDFs baixados (leis federais + DF)
- Estrutura de pastas conforme `SKILL.md` documenta

### Validação manual sugerida

Após geração, verificar:

1. **00-INDICE.md** existe e tem links para todas as seções
2. **edital-resumo.md** tem datas-chave corretas:
   - Prova: 06/09/2026
   - Inscrições: 09/06 a 13/07/2026
3. **Cronograma macro** divide em 3 fases (Fundação/Aprofundamento/Reta Final)
4. **Mapa de Língua Portuguesa** lista os 6 tópicos do subitem 20.2.2.1
5. **Mapa de Lei Maria da Penha** menciona o mínimo de 3 questões garantidas
6. **Análise da banca** identifica padrão Quadrix (lei seca, múltipla escolha 5 opções)
7. **Histórico do órgão** identifica IBRAE 2018 e Fundação Universa 2008
8. **Sinergias** lista pelo menos 3 concursos Quadrix recentes
9. **Discursiva** está populada (Sedes EDAS tem prova discursiva)
10. **Logs** em `.logs/` mostram execução bem-sucedida

## Caso de falha conhecido para teste

Para testar tratamento de erro, tente:
```
Skill concurso-prep com cargo "ESPECIALISTA INEXISTENTE"
```

Esperado: skill identifica que o cargo não existe no edital e pede confirmação.

## Métricas esperadas

| Métrica | Esperado |
|---|---|
| Tempo total | 15-30 min |
| PDFs baixados (sucesso) | ≥ 80% |
| Validação final | 0 erros críticos |
| Pendências geradas | < 5 |
