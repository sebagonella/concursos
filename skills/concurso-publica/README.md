# concurso-publica

Etapa 3: transforma a estrutura de um concurso no vault em **site estático**
navegável. Publica todo o conteúdo abaixo da pasta do concurso — edital, análise da
banca, cronograma, mapas de matéria, materiais e leis, histórico, sinergia,
discursiva, títulos e o aprofundamento — com mídias embutidas (podcast, mapa mental,
vídeo, report), quiz de flashcards e os pacotes do NotebookLM. Uso local/rede
doméstica; site só leitura (o vault é a fonte de verdade).

```bash
# coletar o modelo do site a partir de um concurso
python scripts/site_collector.py --concurso-dir <.../CONCURSOS/SEDES_2026> --out site-model.json
```

```bash
# gerar o site completo
python scripts/site_builder.py --concurso-dir <.../CONCURSOS/SEDES_2026> --out out/site
python -m http.server -d out/site 8000     # conferir localmente
```

A saída espelha o vault: `{concurso}/{comum|cargo}/`, com as seções numeradas e
`materias/{materia}/{assunto}/`. Cada matéria tem duas visões — **Plano** (o mapa do
edital) e **Estudo** (os assuntos aprofundados). No Plano, cada tópico traz o literal
do edital e o checklist derivado à vista, e a um clique o material recomendado, as
pegadinhas da banca, a meta de questões e o que mais o mapa tiver escrito.

Versão atual: **0.10.0** (cobertura do edital em % por matéria, com as lacunas
nomeadas; o que existe em cada assunto; e todo o material recomendado consolidado
por tópico).
