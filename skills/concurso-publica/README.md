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

Versão atual: **0.19.0** (a **bússola da banca abre recolhida** na aba Estudo — aberta, ela ocupava 2.770px e empurrava o primeiro grupo de assuntos para 3.131px, 2,3 telas abaixo, e a aba parecia não ter a matéria; o incentivo ficava invertido, porque quanto melhor o documento mais ele escondia a lista. O título continua à vista no `<summary>` e um clique traz o texto inteiro). Na 0.18.0: (o asset publicado leva a versão do conteúdo na URL — o nginx cacheia 1h e o navegador servia **HTML novo com CSS velho**, um defeito invisível porque a página renderiza, só renderiza errado; os **itens do plano do mapa voltam para a barra de tarefas**, o que faz 22 de 22 matérias terem as duas barras onde 12 não tinham nenhuma; o progresso do assunto passa a somar todos os aprofundamentos, recuperando 181 checkboxes; matéria com aprofundamento no comum ganha a aba **Estudo** que lhe faltava; e a bolha do cartão-resposta deixa de medir progresso, que agora é barra em todo lugar). Na 0.17.0: (duas barras lisas de progresso no escopo e na matéria — tarefas de estudo em verde, tópicos do edital em azul, sempre nessa ordem; a barra de tarefas passa a contar tudo o que há para marcar (assuntos + documentos + `99-Status`), o que faz quatro dos sete escopos do vault deixarem de aparecer sem indicador nenhum; **a barra de cobertura mudou de verde para azul**, porque verde passou a significar "o que eu fiz" e azul "o material que existe"; e a bolha do cartão-resposta ficou onde cada bolha é uma tarefa — 8 bolhas não valem mais 303). Na 0.16.0: (o wikilink com âncora resolve pela ÂNCORA e não pelo nome do arquivo — há um `livros-recomendados.md` por escopo, e o basename mandava 160 links para a página homônima errada; o block id do Obsidian vira âncora HTML de verdade; e backups `.md.bak` deixam de ser publicados como anexo). Na 0.15.0: (a página de Materiais passa a existir em cada cargo, herdando por referência a bibliografia do comum, e a página de matéria ganha link até ela — antes a seção sumia em silêncio no galho do cargo e a frase apontava para um menu inexistente). Na 0.14.0: (o manifesto de cada concurso guarda a pasta de origem no vault,
que é o que permite ao `deploy.sh` reconstruir todo o build antes de enviar — sem isso,
concurso construído numa sessão anterior era republicado com o conteúdo daquela data).
Na 0.13.0: a ficha do aprofundamento mostra onde **cada** fonte foi
localizada, e o ponteiro vai inteiro — metade dos valores do vault é prosa livre que a
regex de página não casa. Na 0.12.0: correção de documentação, com o `SKILL.md`
acumulando "novidades da versão X" que pararam na 0.7.0. Na 0.11.2:
quatro defeitos de renderização — lista aninhada deixa de achatar, item de lista não
perde a linha de continuação, negrito contendo itálico converte, e o pipe cru de
wikilink não quebra mais a tabela.
