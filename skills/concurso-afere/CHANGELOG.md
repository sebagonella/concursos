# Changelog — concurso-afere

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · [SemVer](https://semver.org/lang/pt-BR/).

## [0.6.0] - 2026-10-04

### Adicionado
- **Prova da Quadrix.** A skill só lia a CESGRANRIO: cargos do BB fixos em
  `prova_id.py`, caderno identificado por "GABARITO [1-4]", gabarito no formato
  `N - X`. Rodada contra a prova Quadrix do CRESS-RS que já estava no vault do SEDES,
  saía com `exit 2` — e o SEDES, cuja prova real foi em 06/09/2026, não podia ser
  aferido. Novo `quadrix.py`:
  - gabarito em **grade** (linha de números, linha de letras), uma seção por cargo e
    tipo, `X` como anulada e PRELIMINAR/DEFINITIVO lidos do cabeçalho;
  - **tabela de divisão por área** — com uma coluna por tipo (SEDES), uma tabela por
    cargo (CRESS-MG) ou, quando ela é por nível e nada diz o nível do cargo
    (CRESS-RS), recusa nomeada em vez de faixa inventada;
  - **cargo pelo rodapé** do caderno, casado com as seções do gabarito; empate é erro;
  - **tipo pela ordem dos blocos**, já que nenhuma página imprime "TIPO A".
- **Mapa questão → matéria, em duas etapas** (`mapa_questoes.py`). A prova Quadrix
  divide por ÁREA: "Conhecimentos Gerais, 1 a 20" mistura Português, legislação do DF
  e primeiros socorros. A matéria de cada questão é julgamento do agente; o
  `build_afericao.py --area` grava o esqueleto e o `--mapa` gera uma aferição por
  matéria, recusando questão esquecida, matéria inexistente e gabarito editado no mapa.
- **`comparar_gabaritos.py`**: do preliminar ao definitivo, lista só as questões
  alteradas ou anuladas de cada aferição, para rejulgar. Não reescreve julgamento.
- Frontmatter da aferição Quadrix: `cargo_prova`, `tipo_caderno`, `area_prova`,
  `questoes_anuladas`; `gabarito_fonte` passa a dizer `preliminar` ou `definitivo`, e o
  documento sobre o preliminar ganha a ressalva.

### Corrigido
- **Números de questão com três dígitos** (`\d{1,2}` → `\d{1,3}` em `gabarito.py`,
  `prova_id.py` e `extrair_questoes.py`): "100 - B" era lido como "00 - B".
- **Anulada fora do denominador e dentro da amostra** no validador: a soma das
  contagens ignorava a linha e acusava a amostra de não fechar.
- `SKILL.md` documenta `--escopo`, `--out` e `--forcar`, que existiam sem menção; o
  README perdeu um parágrafo órfão que sobrara de edição.

### Testes
- 17 novos (52 no total), com fixtures da **saída real do `pdftotext`**: os três
  gabaritos Quadrix inteiros e o recorte estrutural de dois cadernos do SEDES (sem o
  texto das questões). Contra a 0.5.0, o de três dígitos falha com `GabaritoErro`, o
  da anulada acusa "não somam a amostra", e o de banca — lida antes só nas duas
  primeiras páginas — classificava como CESGRANRIO o gabarito do SEDES, que só assina
  "INSTITUTO QUADRIX" na oitava.

## [0.5.0] - 2026-08-12

### Corrigido
- **Empate no casamento de matéria era resolvido em silêncio.**
  `if s > melhor_score` ficava com o primeiro da iteração e nem contava que houvesse
  outro igual. O caso é real e está nomeado no `CLAUDE.md`: matéria homônima no
  `_COMUM` e no cargo — no SEDES, `servico-social` existe nos dois — dá score
  IDÊNTICO, e uma das duas era medida sem que nada dissesse qual. O `SKILL.md`
  promete "sem casamento confiável, PERGUNTA". Agora o empate é registrado em
  `Casamento.empatados` e o build **recusa**, nomeando os candidatos.
- **`--escopo` (novo)** é a saída para esse empate: sem ela, a recusa seria um beco
  sem saída no caso real do SEDES. Combinada com `--cargo`, vale a interseção, e
  pedir escopo fora do cargo é erro nomeado.
- **O `except GabaritoErro` engolia a mensagem que existe para ser lida.** O
  fallback para a tabela inteira é legítimo — há gabarito sem cabeçalho de seção —,
  mas descartava o "recorte de seção errado ou tabela em formato novo". E o que se
  perde não é cosmético: sem o recorte, a faixa numérica passa a ser a única defesa
  contra pegar a resposta de outra matéria. Agora vira aviso, que já sai no stderr e
  acompanha os dados.

### Testes
- Três para o empate (registro, recusa nomeada e `--escopo` desfazendo) e dois para
  o fallback. Contra a 0.4.0, o de empate nem chega a falhar por asserção:
  `AttributeError: 'Casamento' object has no attribute 'empatados'` — o empate era
  invisível por construção.

## [0.4.0] - 2026-08-12

### Corrigido
- **A coluna Q renumerava as questões de 1 a N.** `for i, q in enumerate(...)`
  descartava `q` e imprimia `i + 1`: numa faixa 21–25 a tabela saía `Q1…Q5` enquanto
  o `--bloco-out` que o agente lê traz os números reais. O cruzamento
  questão↔veredicto era feito contra rótulos que não existem na prova — invisível só
  em Língua Portuguesa, que começa em 1.
- **O pareamento entre provas era posicional, não por número de questão.**
  `sorted(d["gabarito"])[i]` indexava CADA prova pela posição da primeira:
  `IndexError` quando as contagens diferiam e, pior, casamento **silencioso** de
  gabaritos de questões distintas quando as faixas diferiam. O número da questão é a
  chave comum entre as versões — é ele que pareia, e questão ausente numa prova vira
  `?` em vez de puxar a resposta da seguinte.

### Testes
- `test_tabela_usa_o_numero_real_da_questao` (falha contra a 0.3.0 devolvendo
  `['1','2','3','4','5']` onde a prova tem 21–25) e
  `test_provas_com_faixas_diferentes_nao_estouram_nem_pareiam_errado` (falha com
  `IndexError`).

## [0.3.0] - 2026-08-06

### Corrigido
- **`build_afericao.py` sobrescrevia a aferição já julgada.** O destino tem nome fixo
  (`00-AFERICAO-{MATERIA_ID}.md`) e o `write_text` era incondicional, então reexecutar
  a mesma matéria trocava **o julgamento do agente** — veredicto por questão, conceito
  decisivo, ações corretivas — pelo arcabouço com `···` de volta. É exatamente o
  trabalho que a skill declara não saber fazer sozinha ("o script prepara o
  determinístico e **o agente julga**"), e o único que nenhuma reexecução recupera.
  Agora aferição existente é **pulada**, com o motivo no stderr e `pulado: true` no
  relatório JSON; `--forcar` regenera, com backup `.md.bak`. Para uma segunda rodada,
  o caminho continua sendo `--out` com nome próprio (`...-2-POS-CORRECAO.md`), que é o
  que a `concurso-publica` já espera encontrar — uma matéria tem legitimamente várias.
- **O `--bloco-out` saiu de dentro do bloco de escrita da aferição.** Ele é derivado da
  PROVA, não do julgamento: é o determinístico que o agente lê para julgar. Preso ao
  mesmo `if`, quem reencontrasse uma aferição pronta e quisesse refazê-la noutro
  arquivo ficaria sem o insumo.

### Testes
- Primeira cobertura do `build_afericao.py`, que era o único script da skill sem teste
  nenhum — e o único que **escreve no vault**.
  `test_build_afericao_nao_sobrescreve_julgamento` falha contra a 0.2.0 com "segunda
  execução NÃO apaga o julgamento"; `test_build_afericao_forcar_faz_backup` cobre a
  saída explícita.

## [0.2.0] - 2026-08-05

### Adicionado

- **O validador confere a aritmética da nota** — o check 2 que o docstring anunciava e que
  **nunca existiu no código**. Ele recalcula a nota a partir das contagens declaradas, pelo
  critério da própria skill (RESPONDE 1,0 · PARCIAL 0,5 · NÃO RESPONDE 0,2), e compara com a
  nota escrita **por nível**; e confere que `respondidas + parciais + não respondidas + sem
  material` fecha com `questoes_aferidas` do frontmatter. Sem ele, a aritmética da primeira
  aferição de Vendas e Negociação (13,0+13,2+13,2 = 39,4 e 39,4/45 = 8,76) foi conferida à mão.
- **`SEM MATERIAL` fica fora do denominador**, como manda o critério: 10 respondidas e 5 sem
  material dá **10,0**, não 6,7. Incluí-lo puniria o texto por uma lacuna de planejamento — e
  há teste travando isso.
- A mensagem **mostra a conta**: `35·1,0 + 8·0,5 + 2·0,2 = 39,4 sobre 45 dá 8,76, mas o
  documento diz 9,20`. Erro de aritmética sem a conta ao lado obriga a refazê-la para saber
  quem está errado.

### Notas

- **O check se cala onde não há contagem**, em vez de falhar alto. Onde não há números não há
  aritmética a conferir, e o documento incompleto já é pego pelo marcador `···` do check 1.
  Isso mantém o validador utilizável nas variações reais de formato — a tabela de Vendas e
  Negociação tem **uma** coluna de nível e uma linha `Sem material`; a de Língua Portuguesa
  tem **duas** colunas e nenhuma.
- Verificado contra os dois documentos reais do vault (passam) e contra cópias adulteradas na
  nota e numa contagem (pegos, com a conta na mensagem). 22 → 26 testes.

## [0.1.1] - 2026-08-05

### Corrigido

- **O check de formatação dupla passou a exigir relação de arredondamento, não
  proximidade.** O critério anterior (`|a − b| <= 0,05`) confundia duas coisas
  diferentes: *o mesmo número escrito de dois jeitos* — o defeito — e *dois números
  legitimamente vizinhos*. Numa matéria estável as notas por prova caem naturalmente a
  menos de 0,05 umas das outras, e a primeira aferição de **Vendas e Negociação** foi
  recusada inteira por trazer **8,76** (consolidado) e **8,80** (provas B e C), que são
  valores distintos, calculados em separado e ambos corretos. Agora só há defeito quando
  as **precisões diferem** e o menos preciso é um arredondamento válido do mais preciso.
  O par que originou a regra (**39,4 × 39,45**) continua sendo pego, e a mensagem passou
  a nomear qual número parece o arredondamento de qual.
- A comparação é por **desigualdade**, não por `round()`: 39,45 arredonda para 39,4
  (HALF_EVEN) ou 39,5 (HALF_UP), e os **dois** são o defeito — fixar um modo deixaria o
  outro passar. Segue em `Decimal` pelo motivo de sempre (em float, 39,45 − 39,4 dá
  0.050000000000004 e escaparia do limiar por epsilon).
- **O docstring do script dizia "39,4 numa tabela e 39,5 noutra"**, mas o incidente real
  — registrado neste changelog em 0.1.0 — foi **39,4 × 39,45**. A imprecisão importa:
  39,4 × 39,5 têm a *mesma* precisão e nunca foram pegos por regra nenhuma, nem pela
  antiga. Corrigido.

### Notas

- **Fica de fora, por construção:** dois valores de mesma precisão, por mais próximos que
  estejam (39,4 × 39,5). Não há como pegá-los sem recusar 13,0 × 13,2, que é legítimo e
  aparece na aferição de Vendas. Preferiu-se deixar passar o caso hipotético a recusar o
  caso real.
- O `validar_afericao.py` tem no docstring um check 2 ("notas por prova somam ao
  consolidado") que **não existe no código**. Não entra nesta correção: é gap separado e
  mais substantivo — implementado, teria conferido sozinho a aritmética de Vendas.

## [0.1.0] - 2026-08-04

### Adicionado

- **Primeira versão.** Afere o material aprofundado do vault contra a prova real, com
  gabarito oficial. `--materia` aceita uma ou mais matérias; `--cargo` traz todas as
  aprofundadas do cargo, incluindo as do `_COMUM` — é como o candidato estuda.
- **Quatro vereditos**, e `SEM MATERIAL` **fora do denominador**: o tópico que nunca foi
  aprofundado é falha de *cobertura*, não de *profundidade*, e as ações corretivas são
  diferentes. Medido: Conhecimentos Bancários tem 15 assuntos para 24 tópicos do mapa —
  misturar as duas coisas puniria a qualidade do texto por uma lacuna de planejamento.
- **`prova_id.py` compara versão do caderno E cargo.** Cruzar a prova do Agente Comercial
  com o gabarito do Agente de Tecnologia devolve 10 respostas plausíveis e completamente
  erradas: os dois têm "GABARITO 4" e o de Tecnologia nem declara A/B/C.
- **A faixa de questões vem da tabela da capa** ("Língua Portuguesa … 1 a 10"), não de
  contagem no corpo — o texto de apoio numera parágrafos, e `\n3\n` casava com o
  parágrafo 3 em vez da questão 3.
- **Matérias descobertas pelo filesystem.** O `.meta.json` do SEDES tem
  `materias_por_cargo`; o do BB **não tem**.
- **`validar_afericao.py`** recusa veredicto em branco, amostra não declarada, superlativo
  com uma prova só e o mesmo número escrito de dois jeitos (39,4 × 39,45 — a comparação é
  em `Decimal`, porque em float a diferença dá 0.050000000000004 e escapa).

### Notas

- **Não recorta questão a questão.** Tentei: em PDF de duas colunas o texto de uma questão
  não é contíguo — na Prova A as questões 3 e 6 aparecem lado a lado. Entrega-se o bloco
  da matéria, com aviso quando alguma marca de questão não aparece nele.
- Os 20 testes que reproduzem bug foram conferidos contra o código ingênuo.
