---
tipo: material
escopo: "{{ESCOPO}}"
concurso: "{{ORGAO}} {{ANO}}"
data_atualizacao: {{DATA}}
tags:
  - concurso/{{ORGAO_SLUG}}/{{ANO}}
  - material/catalogo
---

# 📚 Catálogo de Material — {{ESCOPO_LEGIVEL}}

> **Este é o catálogo canônico do escopo.** Cada obra é descrita **uma vez**, aqui.
> Os tópicos dos mapas de matéria **apontam** para estas entradas em vez de
> redigitar título e autor — foi a redigitação que produziu, no vault, quatro
> grafias e três editoras contraditórias para o mesmo livro.
>
> Só referências bibliográficas: **não há reprodução de conteúdo**. Adquira pelos
> canais oficiais (editoras, livrarias) ou consulte em biblioteca.

## Como citar uma entrada daqui

O `^mat-...` no fim de cada entrada é um **block id do Obsidian**. No mapa:

```markdown
### Material recomendado
- Livro: [[livros-recomendados#^mat-pestana-gramatica|Pestana — A Gramática]] — cap. 4
```

O rótulo depois do `|` é para leitura e pode ser reescrito à vontade; o vínculo é a
âncora. A regra do id vive em `scripts/material_id.py` — não a reimplemente.

---

{{ENTRADAS_POR_MATERIA}}

<!--
Cada entrada segue esta forma. Campo sem valor é OMITIDO — linha em branco
parece dado perdido por descuido, e o que falta de verdade vai em `⚠️ Pendência`.

## {{NOME_DA_MATERIA}}

### {{TITULO_DA_OBRA}}

- **Autor:** {{AUTOR}}
- **Editora:** {{EDITORA}} · {{EDICAO}}
- **ISBN:** {{ISBN}}
- **Cobre:** {{MATERIA_ID}}
- **Onde obter:** {{ONDE_OBTER}}

^{{ANCORA}}

Sem autor identificado, a entrada NÃO some e NÃO é maquiada:

### {{TITULO_DA_OBRA}}

- **Cobre:** {{MATERIA_ID}}
- **⚠️ Pendência:** autoria não identificada — {{O_QUE_FOI_PROCURADO}}

^{{ANCORA}}
-->

---

## Pendências

Obras que a pesquisa não conseguiu identificar por completo estão em
[[pendencias-material]], com o que foi procurado em cada caso. Lacuna registrada é
trabalho pendente; lacuna silenciosa vira dado errado — a diferença entre "procurei
e não achei" e "não procurei" precisa estar escrita.
