# Revisão Profunda do Ecossistema: Skills, Agents, Scripts, Documentação e Novos Recursos

**Data:** 2026-10-04  
**Projeto:** `14_concursos` (Repositório) & `20_PROJETOS/PROFISSIONAL/14_concursos` (Vault Obsidian)  
**Autor:** Antigravity / Sebastião Gonella  
**Escopo:** Revisão completa e detalhada de todo o ecossistema (skills `concurso-prep`, `concurso-aprofunda`, `concurso-notebooklm`, `concurso-afere`; subagents; scripts utilitários; documentações e contratos), identificação de gaps e oportunidades de evolução, e proposição de novos recursos de alto impacto pedagógico para aprovação em concursos públicos. *(Skill `concurso-publica` excluída do escopo a pedido).*

---

## Sumário Executivo

O projeto `14_concursos` destaca-se por um nível invulgar de maturidade arquitetural e rigor empírico: convenções invioláveis documentadas a partir de incidentes reais, isolamento rigoroso de direitos autorais (Modelo 2), idempotência estrita para proteção do progresso do candidato, e testes standalone sem dependências pesadas.

Contudo, uma análise aprofundada sob a ótica da **eficiência e qualidade da preparação de alto rendimento para concursos públicos** revela que o ecossistema atual:
1. **É forte na fase de absorção teórica e mapeamento inicial**, mas possui **gaps críticos nas fases ativas de resolução de questões, simulados calibrados, fixação de distratores e prova discursiva**;
2. **Apresenta gargalos de acoplamento de engine** (projetado quase exclusivamente para o runtime do Claude Code e caminhos em `~/.claude/`, gerando atritos de execução no Antigravity CLI e modelos Gemini);
3. **Deixa o ciclo de aferição em aberto**, gerando diagnósticos ricos de provas reais que dependem de intervenção manual demorada para correção do material;
4. **Possui fragilidades na ingestão e atualização jurídica** (parsing de legislação no Planalto sem descarte/marcação de dispositivos revogados e ausência de radar de jurisprudência/súmulas);
5. **Depende de sumários limpos para indexação de livros**, falhando em documentos escaneados ou obras sem sumário estruturado devido ao fallback frágil por densidade de termos simples.

Abaixo apresenta-se o levantamento detalhado por subsistema, seguido pelo catálogo de novos recursos de ponta propostos para implementação.

---

## 1. Auditoria e Revisão por Componente

### 1.1 Skill `concurso-prep`

#### Diagnóstico Atual
Orquestra o bootstrap de um concurso em 10 etapas a partir do edital oficial ou anterior (modo previsto), gerando metadados (`.meta.json`), mapas de matéria com subtópicos e prioridades, catálogo canônico de materiais, histórico e sinergias.

#### Gaps e Limitações Identificados
1. **Extração de Texto do Edital (`extract_edital.py`):**
   - **Ausência de OCR Fallback:** O script depende exclusivamente de `pdftotext` (poppler). Quando o edital ou uma retificação é publicado como imagem escaneada em Diário Oficial (DODF, DOU, DOE), o comando sai com código 0 mas gera uma string vazia ou fragmentada. Embora a tabela de dependências da documentação mencione `tesseract`, o script `extract_edital.py` não possui chamada ao tesseract.
   - **Intercalação em Tabelas de Múltiplas Colunas:** Editais brasileiros (especialmente Cebraspe e FGV) organizam quadros de vagas, cotas (AC, PCD, PN/PPP, HIPO), requisitos e tabelas de matérias/pesos em tabelas densas de 4 a 8 colunas. O modo `-layout` do `pdftotext` frequentemente mistura o texto das colunas, induzindo o `edital-parser` a erros na contagem de questões e requisitos de cargos.
2. **Download de Documentos Oficiais (`fetch_pdf.py` e `fetch_lei.py`):**
   - **User-Agent de Bot Rejeitado por WAFs:** O `fetch_pdf.py` utiliza `USER_AGENT = "Mozilla/5.0 (compatible; ConcursoPrepBot/1.0; +https://example.com/bot)"`. Diversos portais de concursos (ex.: Cebraspe, FGV Conhecimento, PCI Concursos) e diários oficiais possuem regras de WAF/Cloudflare que bloqueiam requisições contendo `bot` ou `example.com` com erro 403 Forbidden.
   - **Perda de Dispositivos Revogados no Planalto (`fetch_lei.py`):** O Planalto serve leis em HTML mantendo os artigos revogados com tags `<strike>` ou `<s>`. O `_TextExtractor` do `fetch_lei.py` descarta essas tags e processa o texto interno como texto normal. Isso faz com que redações antigas e já revogadas apareçam no Markdown gerado sem indicação visual clara de revogação, gerando risco severo de o candidato memorizar norma desatualizada.
3. **Ausência de Agente e Pipeline para Prova Discursiva:**
   - Na Etapa 9 do `SKILL.md`, a preparação para a prova discursiva resume-se à geração de um arquivo de texto estático `guia-discursiva.md`. Não há agente especializado em formular propostas de redação no padrão da banca, nem fornecimento de espelhos de correção analíticos (critérios macroestruturais e microestruturais).
4. **Acoplamento dos 5 Subagents ao Claude Code:**
   - Os subagents (`edital-parser.md`, `materia-mapper.md`, `material-collector.md`, `historico-researcher.md`, `sinergia-finder.md`) usam formato de cabeçalho YAML exclusivo do Claude Code (`tools: Read, WebSearch, Write`) e dependem da Task tool. No Antigravity, precisam ser invocados via `invoke_subagent` com ferramentas explícitas ou mapeados em formato agnóstico.

---

### 1.2 Skill `concurso-aprofunda`

#### Diagnóstico Atual
Consome os mapas de matéria e livros de referência densos no vault, localizando assuntos por página, gerando o arcabouço `.md` nos níveis `padrao` e `detalhado` (Modelo 2 de direitos autorais), cartões de repetição espaçada e pacotes NotebookLM.

#### Gaps e Limitações Identificados
1. **Localização em Livros sem Sumário (`book_index.py`):**
   - **Frigidez da Densidade de Termos:** O método de fallback por densidade de termos conta a ocorrência de tokens literais não-vazios por página. Em conceitos doutrinários abstratos (ex.: "Princípio da Autotutela Administrativa", "Interesse Público Primário vs Secundário", "Teoria da Culpa Administrativa"), os termos dispersam-se ou aparecem com sinônimos. Quando o livro não possui TOC estruturado ou os termos são genéricos, a densidade cobre mais de 80% do documento (sendo descartada pela regra `FRACAO_INUTIL`) ou zera, resultando em falsos negativos.
2. **Subaproveitamento da Repetição Espaçada:**
   - O `flashcards_gen.py` gera arquivos para o plugin Spaced Repetition do Obsidian e CSVs para o Anki. Contudo, auditorias no vault mostraram que dos 177 baralhos criados, praticamente nenhum histórico de revisão foi consolidado no Obsidian. O candidato estuda em múltiplos dispositivos e na rotina diária não abre o Obsidian desktop para revisar decks estáticos sem algoritmo moderno integrado.
3. **Desbalanceamento Teoria vs. Jurisprudência:**
   - O template atual prioriza fortemente a citação doutrinária ("Livro: Autor — cap. X"). Em matérias como Direito Constitucional, Administrativo, Tributário e Previdenciário, as bancas contemporâneas (Cebraspe, FGV) cobram maciçamente **súmulas vinculantes, súmulas ordinárias do STF/STJ, Teses de Repercussão Geral e informativos de jurisprudência**. Hoje, o arcabouço trata jurisprudência apenas como uma subseção opcional de "Relacionados", sem checagem de teses obrigatórias.
4. **Limitação da Seção `QUESTOES_COMENTADAS`:**
   - No nível `detalhado`, o agente formula apenas 2 a 3 questões exemplificativas. Não há detalhamento sistemático dos distratores nem metrificação do padrão de pegadinhas da banca específica.

---

### 1.3 Skill `concurso-notebooklm`

#### Diagnóstico Atual
Executa os pacotes `_fonte-notebooklm.md` via wrapper síncrono da CLI `notebooklm-py`, criando notebooks, realizando upload de notas e disparando a geração de podcasts de áudio, vídeos e relatórios sob demanda.

#### Gaps e Limitações Identificados
1. **Fragilidade Inerente de Biblioteca Não-Oficial:**
   - Como documentado em `ARQUITETURA.md`, `notebooklm-py` baseia-se em endpoints privados do Google com RPC IDs fixos. Atualizações do Google quebram a CLI repentinamente, exigindo isolamento permanente.
2. **Incapacidade de Gerar Mapas Mentais Customizados:**
   - A CLI do NotebookLM não suporta o envio do `PROMPT_MINDMAP` e faz download de mapas mentais em JSON bruto não renderizável. Como consequência, a geração de mapas mentais visuais foi totalmente desativada nesta automação. O candidato fica sem artefatos visuais no material de estudo a menos que os faça manualmente.
3. **Ausência de Múltiplas Contas / Rotação de Quotas:**
   - A automação usa uma única credencial de sessão (`~/.notebooklm/`). Em concursos de grande porte (ex.: 66 assuntos em `conhecimentos-bancarios`), a quota diária de áudio é atingida rapidamente (exit code 4). Não há suporte a fila inteligente com retentativa calendarizada ou rotação de credenciais.

---

### 1.4 Skill `concurso-afere`

#### Diagnóstico Atual
Compara o material aprofundado no vault com cadernos de prova reais e gabaritos oficiais definitivos, computando o grau de acerto do material por questão, matéria e nível (`padrao` vs `detalhado`).

#### Gaps e Limitações Identificados
1. **Ciclo Aberto de Aferição (Falta de Remediação Automática):**
   - A skill gera um diagnóstico impecável em `00-AFERICAO-*.md`, registrando questões `❌ NÃO RESPONDE` e `⚠️ PARCIAL`. No entanto, **o fluxo para por aí**. A aplicação das correções depende de o candidato reler a nota, localizar o assunto no vault, rodar manualmente `concurso-aprofunda --modo ampliar` e redigir o trecho que faltava.
2. **Extração de Questões em Layouts Complexos (`extrair_questoes.py`):**
   - Provas em PDF com duas colunas, textos motivadores compartilhados para múltiplas questões (ex.: "As questões 1 a 5 referem-se ao texto abaixo") ou tabelas de contabilidade/exatas têm trechos cortados ou misturados. O script entrega o bloco de texto bruto para o agente, que por vezes sofre alucinações de contexto ao correlacionar a alternativa ao comando da questão.
3. **Ausência de Metadados de Dificuldade e Distrator:**
   - A aferição julga se o material responde ou não à questão. Não registra a categoria da questão (decoreba de lei, doutrina pura, jurisprudência recente, interpretação lógica) nem a anatomia da pegadinha, perdendo insumos valiosos para o "Caderno de Erros".

---

### 1.5 Scripts Globais e Infraestrutura

1. **`scripts/install.sh`:**
   - Focado 100% no ecossistema Claude Code (`~/.claude/skills/` e `~/.claude/agents/`).
   - Não possui suporte ao Antigravity CLI (não gera ou atualiza `~/.gemini/config/skills.json` nem converte os subagents para definições compatíveis).
2. **`scripts/test-all.sh`:**
   - Executa com sucesso as 9 suítes standalone, mas limita-se a testes sintáticos e smoke tests locais. Não possui linter que valide a integridade referencial dos wikilinks do vault nem validação cruzada de schemas JSON com os `.meta.json` reais do cofre.

---

### 1.6 Documentação

1. **Rigor Histórico vs. Documentação Operacional:**
   - O `CLAUDE.md` da raiz e `ARQUITETURA.md` contêm relatos históricos detalhados de incidentes e bugs de versões passadas. Embora essenciais para evitar regressões, eles diluem a localização rápida de instruções operacionais para o agente.
2. **Descompasso de Contratos:**
   - Em `docs/CONTRATO-DE-DADOS.md`, a tabela de dados está bem estruturada, mas faltava menção aos novos fluxos planejados de exportação de bundle e de remediação.
3. **Ausência de Guia de Estudo de Alto Rendimento:**
   - Toda a documentação é voltada para a *construção* do material, sem diretrizes sobre *como o candidato deve estudar* de forma ativa (ciclo de estudos, revisão espaçada, técnica de fechamento de tópicos e cadernos de erros).

---

## 2. Levantamento de Recursos de Alto Impacto para o Candidato

Para transformar o repositório de um "gerador de anotações" em um **sistema integrado de alta performance para aprovação**, foram pesquisadas as melhores práticas das metodologias contemporâneas de estudo para concursos de alto nível (magistratura, fiscal, carreiras bancárias, tribunais e serviços sociais):

### Recurso 1: Radar de Legislação & Jurisprudência Atualizada (`concurso-juris`)
- **Problema:** Em média, 60% das questões jurídicas cobram letra da lei e 30% cobram entendimento jurisprudencial sumulado ou recente. Além disso, bancas têm predileção absoluta por **leis alteradas nos últimos 24 meses**. No ecossistema atual, a lei baixada fica estática no vault e não há mecanismo de mapeamento de súmulas.
- **Solução / Especificação:**
  - Script e base de consulta para conferir a vacatio legis e vigência de normas baixadas.
  - No `fetch_lei.py`: implementar o tratamento explícito de `<strike>`, `<del>` e `<s>`, convertendo dispositivos revogados para `~~texto~~` com banner indicativo de revogação.
  - Catálogo de Súmulas Vinculantes do STF e Súmulas do STJ vinculadas por tag temática ao `materia_id`.
  - Módulo que destaca artigos de alta incidência em prova ("artigos-chave"), alertando o estudante para memorização literal.

### Recurso 2: Sistema Completo de Preparação para Provas Discursivas (`concurso-discursiva`)
- **Problema:** As etapas discursivas (estudo de caso, dissertação técnica, parecer ou redação) costumam definir a ordem de classificação final e eliminação em concursos públicos. O repositório atual apenas gera um `guia-discursiva.md` estático.
- **Solução / Especificação:**
  - **Gerador de Temas Inéditos com Textos Motivadores:** Módulo que gera cadernos de treino prático compostos por tema, situação-problema hipotética e 3 quesitos avaliativos no estilo da banca (ex.: Cebraspe).
  - **Espelho Oficial de Correção Analítico:** Geração da grade de correção com distribuição de pontuação macroestrutural (apresentação, legibilidade, coesão, tópicos de conteúdo) e microestrutural (morfossintaxe, pontuação, vocabulário).
  - **Corretor Automático de Rascunhos de Redação:** Agente que recebe o rascunho do candidato (digitado ou transcrito de OCR de folha pautada manuscrita), aplica a fórmula matemática exata de penalidade da banca (ex.: fórmula Cebraspe $NF = NC - 2 \times (ER / TL)$), atribui a nota justificada quesito por quesito e fornece sugestões de reescrita em padrão nota máxima.

### Recurso 3: Motor de Simulados Balanceados & Gestão de Tempo (`concurso-simulado`)
- **Problema:** O cronograma do concurso define a meta de realizar 6 simulados completos, mas não existe nenhuma automação que monte, formate ou audite esses simulados.
- **Solução / Especificação:**
  - **Montador de Simulados por Matriz de Pesos:** Script que seleciona questões das provas anteriores baixadas (`05-HISTORICO-CONCURSO` e `06-SINERGIA`) ou formula questões inéditas, respeitando rigorosamente o número de questões por disciplina previsto no edital.
  - **Folha de Respostas e Temporizador:** Geração de caderno de questões, gabarito lacrado e folha de respostas para simulação realista com controle de ritmo de minutos por questão.
  - **Cálculo de Nota Líquida da Banca:** Apuração automática aplicando a regra do edital (ex.: sistema Cespe Certo/Errado em que 1 erro anula 1 acerto; regras de nota mínima por bloco da FGV).

### Recurso 4: Caderno de Erros Ativo com Metacognição (`caderno-erros`)
- **Problema:** Candidatos que não catalogam seus erros cometem os mesmos deslizes na prova. Hoje o sistema registra o erro apenas na aferição de prova real.
- **Solução / Especificação:**
  - Estrutura de notas `CADERNO-DE-ERROS.md` dentro de cada matéria no vault.
  - Taxonomia padronizada de falhas:
    - `[TEORIA]` — Lacuna de conteúdo (não sabia o conceito).
    - `[PEGADINHA]` — Sabia o conceito, mas caiu no distrator da banca.
    - `[LEITURA]` — Má interpretação do comando da questão (ex.: "marque a INCORRETA").
    - `[DECOREBA]` — Esquecimento de prazos, idades, quóruns ou fórmulas.
  - Geração automática de flashcard de reforço focado na desconstrução da pegadinha.

### Recurso 5: Mapas Mentais Nativos em Mermaid e Obsidian Canvas
- **Problema:** O NotebookLM não aceita prompts customizados para mapas mentais e os exporta em JSON incompatível. O candidato fica sem sínteses visuais.
- **Solução / Especificação:**
  - Criação de gerador nativo de diagramas em **Mermaid** (`mindmap` ou `graph TD`) inseridos diretamente no corpo dos resumos aprofundados (`assunto.md`).
  - Geração opcional de arquivos **Obsidian Canvas** (`.canvas`) conectando os assuntos de uma mesma matéria, permitindo ao estudante visualizar a árvore conceitual do edital navegando com zoom no Obsidian.

### Recurso 6: Busca Semântica e Indexação Multimodal de Livros (`book_index.py` v2)
- **Problema:** Livros escaneados ou sem sumário detalhado falham no matching determinístico atual.
- **Solução / Especificação:**
  - Adicionar suporte a embeddings locais leves (via modelo em Python como `all-MiniLM-L6-v2` ou chamada de API) para mapear o conteúdo de cada capítulo contra os títulos de tópicos do edital.
  - Eliminar o risco de "páginas que cobrem 80% do livro" através de segmentação por janelas semânticas (chunks) com score de relevância ponderada.

### Recurso 7: Fechamento Automatizado do Ciclo de Aferição (`remediar_afericao.py`)
- **Problema:** As notas de aferição expõem os pontos fracos do material, mas exigem trabalho manual para correção.
- **Solução / Especificação:**
  - Script que lê as tabelas de `00-AFERICAO-*.md`.
  - Para cada questão `❌` ou `⚠️`, localiza o arquivo do assunto no vault, injeta um bloco de alerta (`> 🎯 Correção Pós-Aferição [Prova X]: ...`) e atualiza o deck de flashcards acrescentando novos cartões com o conceito decisivo da questão.

---

## 3. Matriz de Priorização e Roteiro de Implementação

| Recurso / Melhoria | Complexidade | Impacto no Candidato | Fase Recomendada |
|---|:---:|:---:|:---:|
| **1. Compatibilidade Dual-Engine & `install.sh --gemini`** | Baixa | Alto (viabilidade operacional) | **Fase 1** (Imediata) |
| **2. Fechamento de Aferição (`remediar_afericao.py`)** | Média | Altíssimo (ciclo fechado de qualidade) | **Fase 1** (Imediata) |
| **3. Correção de Tags Revogadas no `fetch_lei.py` e User-Agent** | Baixa | Alto (segurança jurídica) | **Fase 1** (Imediata) |
| **4. Skill / Agente de Prova Discursiva (`concurso-discursiva`)** | Média-Alta | Altíssimo (diferencial de aprovação) | **Fase 2** (Curto Prazo) |
| **5. Caderno de Erros Ativo com Taxonomia de Falhas** | Média | Altíssimo (metacognição do candidato) | **Fase 2** (Curto Prazo) |
| **6. Geração de Simulados e Matriz de Pesos (`concurso-simulado`)** | Média | Alto (treino realista) | **Fase 2** (Curto Prazo) |
| **7. Mapas Mentais Nativos em Mermaid nos Resumos** | Baixa-Média | Alto (aprendizado visual e revisão rápida) | **Fase 3** (Médio Prazo) |
| **8. Busca Semântica em Livros (`book_index.py` v2)** | Média-Alta | Médio-Alto (robustez de indexação) | **Fase 3** (Médio Prazo) |
| **9. Radar de Súmulas e Atualizações Legislativas Recentes** | Média | Alto (questões de ponta) | **Fase 3** (Médio Prazo) |

---

## 4. Conclusão

O repositório `14_concursos` possui alicerces sólidos de engenharia de software e respeito à integridade do conhecimento do usuário. Com a incorporação das melhorias apontadas nesta revisão — com destaque para o **fechamento do ciclo de aferição**, a **preparação ativa para provas discursivas**, o **caderno de erros estruturado** e a **geração de simulados calibrados** —, o sistema atinge o estado de arte pedagógico, proporcionando ao candidato uma esteira completa que vai do edital cru até a nota máxima na lista de aprovados.
