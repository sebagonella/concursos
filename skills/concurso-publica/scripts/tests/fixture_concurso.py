#!/usr/bin/env python3
"""
fixture_concurso.py - O concurso de teste, na forma que o vault realmente tem.

Mora fora do `test_smoke.py` porque tem DOIS consumidores: a suíte da skill e a
suíte do `deploy.sh` (`scripts/tests/test_deploy.sh`, na raiz do repo), que
precisa de um concurso construível sem inventar o seu próprio.

Fixture divergente é teste que se autoconfirma — foi assim que o bug do `_GERAL`
ficou verde por meses (assuntos sob `03-MAPAS-MATERIAS`, caminho que a
`concurso-aprofunda` nunca emite) e assim que a chave `notebooklm_url`, que o
template nunca escrevia, passou a ser esperada pelo parser. Um segundo fixture
para o deploy seria a terceira vez. Por isso: um só, aqui.
"""
import json
from pathlib import Path

# Identidade do aprofundamento principal do fixture. Exportadas porque a suíte
# monta nomes de arquivo a partir delas — o nome-base é `{assunto}--{id}--{CONCURSO}`
# e repetir a string em 20 testes é como o fixture antigo saiu do lugar sem ninguém
# notar.
CONCURSO_FIX = "TESTE_2026"
APROF_CRASE = "padrao--pestana"
NOME_BASE_CRASE = f"crase--{APROF_CRASE}--{CONCURSO_FIX}"


def _mat_vault(base: Path, materia: str = "portugues",
               escopo: str = "CARGO-X") -> Path:
    """Pasta da matéria no VAULT, como a `concurso-aprofunda` a cria.

    Era `{CARGO}/03-MAPAS-MATERIAS/{materia}/` — caminho que a skill nunca emite, e
    que por isso mesmo mantinha o bug do `_GERAL` invisível. Agora espelha o real:
    `{ESCOPO}/03-APROFUNDAMENTO/{materia}/`.
    """
    return base / escopo / "03-APROFUNDAMENTO" / materia


def _template_pack() -> str | None:
    """O `.tpl` real da `concurso-aprofunda`, quando as duas skills convivem.

    Devolve None se a irmã não estiver ao lado (skill instalada sozinha) — mesmo
    precedente de `test_copia_do_aprofundamento_id_nao_divergiu`.
    """
    # parents: [0]=tests [1]=scripts [2]=concurso-publica [3]=skills [4]=repo.
    # Mesmos candidatos de `test_copia_do_aprofundamento_id_nao_divergiu`.
    aqui = Path(__file__).resolve()
    rel = Path("assets") / "templates" / "fonte-notebooklm.md.tpl"
    for cand in (aqui.parents[3] / "concurso-aprofunda" / rel,
                 aqui.parents[4] / "skills" / "concurso-aprofunda" / rel):
        if cand.exists():
            return cand.read_text(encoding="utf-8")
    return None


def _pack_como_a_aprofunda_gera(slug: str, concurso: str = "TESTE_2026",
                                assunto: str = "Crase") -> str:
    """Corpo do pacote no formato REAL, renderizado do template da skill irmã.

    Antes o fixture escrevia a palavra `pack` como corpo, e o teste ad-hoc inventava
    `- Studio → …` **como bullet** — no template real essa linha é parágrafo. O
    fixture criou a realidade que o parser exigia, o teste ficou verde, e o vault
    produziu `roteiro: []` em mapa mental e report. É o mesmo modo de falha do bug
    do `_GERAL`, e é por isso que o corpo agora vem do template de verdade.
    """
    tpl = _template_pack()
    if tpl is None:                       # sem a irmã, um mínimo honesto
        return (f"# Pacote\n\n## 1. Fontes para subir no notebook\n\n"
                f'Crie um notebook novo chamado **"{concurso} — {assunto}"** e adicione:\n\n'
                f"1. **`{slug}.md`** — o resumo curado.\n\n"
                f"## 2. 🎧 Podcast (Audio Overview)\n\n"
                f"Studio → **Audio Overview** → clique em **Customize**.\n"
                f"- **Formato:** Deep Dive\n\n```\nP\n```\n\n"
                f"Salve nesta pasta como **`podcast-{slug}.m4a`**.\n")
    corpo = tpl.split("---\n", 2)[-1]     # sem o frontmatter, que o chamador monta
    for chave, valor in (("{CONCURSO}", concurso), ("{ASSUNTO}", assunto),
                         ("{SLUG_ASSUNTO}", slug), ("{MATERIA}", "Português"),
                         ("{TAG_ASSUNTO}", slug),
                         ("{LISTA_FONTES}", f"1. **`{slug}.md`** — o resumo curado."),
                         ("{PROMPT_AUDIO}", f"Foque em {assunto} para concurso."),
                         ("{PROMPT_MINDMAP}", "Construa o mapa mental."),
                         ("{PROMPT_VIDEO}", "Faca um video-aula."),
                         ("{PROMPT_REPORT}", "Gere um guia de estudos."),
                         ("{PERGUNTAS_CHAT}", "- O que mais cai?")):
        corpo = corpo.replace(chave, valor)
    return corpo


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def _montar_concurso(base: Path, com_midias=True, com_url_nb=False, meta=None):
    """Monta um concurso mínimo: 1 cargo, 1 matéria, 2 assuntos.

    `meta` sobrescreve o `.meta.json`. Existe para o `site-model-exemplo.json`
    poder ser regerado daqui com um metadado realista, continuando a ser saída
    de verdade do coletor — exemplo escrito à mão é exemplo que diverge.
    """
    base.mkdir(parents=True, exist_ok=True)
    mat = _mat_vault(base)
    (base / ".meta.json").write_text(json.dumps(
        meta or {"orgao": "TESTE", "ano": 2026, "banca": "Banca X"}),
        encoding="utf-8")

    # ------------------------------------------------------------------ #
    # assunto completo: crase — no layout CANÔNICO
    #
    # Era `assuntos/crase/crase.md`, um `.md` solto na pasta do assunto. Esse é o
    # layout LEGADO, e medindo o vault real ele não existe mais: 0 arquivos assim
    # contra 178 no canônico. Como a maioria dos ~100 testes de página parte daqui,
    # a suíte inteira exercitava `legado: True`, `fontes_id: []`, `n_fontes_id:
    # None` e id `"unico"` — o caminho que a `concurso-aprofunda` NÃO emite. É a
    # terceira encarnação do mesmo defeito (`_GERAL`, `notebooklm_url`), agora na
    # dimensão do layout: fixture divergente é teste que se autoconfirma.
    #
    # O nome-base repete o identificador porque o Obsidian resolve wikilink por
    # NOME de arquivo — e todo artefato do aprofundamento (o `.md`, os flashcards,
    # as mídias) carrega o mesmo nome-base, como no vault.
    # ------------------------------------------------------------------ #
    NOME_BASE = f"crase--{APROF_CRASE}--{CONCURSO_FIX}"
    crase = mat / "assuntos" / "crase" / APROF_CRASE
    crase.mkdir(parents=True)
    (crase / f"{NOME_BASE}.md").write_text(
        # frontmatter na ordem e com as chaves do `assunto.md.tpl` real
        f'---\ntitle: "Crase"\nmateria: "Português"\nmateria_id: portugues\n'
        f'topico_id: [emprego-do-acento-indicativo-de-crase]\n'
        f'topico: ["1. Emprego do acento indicativo de crase"]\n'
        f'concurso: "{CONCURSO_FIX}"\ntipo: assunto-aprofundado\n'
        f'localizacao_livro: "Livro.pdf — págs. 10–20"\n'
        f'confianca_localizacao: alta\nprioridade: alta\n'
        f'aprofundamento: "{APROF_CRASE}"\nnivel: padrao\nfontes: "Pestana"\n'
        f'tags: [concurso/aprofundamento, portugues, crase]\nstatus: concluido\n'
        f'fontes_notebook: []\n---\n'
        "Resumo.\n- [x] Ler\n- [ ] Revisar\n- [ ] Questões\n", encoding="utf-8")
    (crase / f"flashcards-{NOME_BASE}.md").write_text(
        "---\ntipo: flashcards\n---\n#flashcards\n\nP1\n??\nR1\n\nP2\n??\nR2\n",
        encoding="utf-8")
    (crase / f"flashcards-{NOME_BASE}.csv").write_text("P1;R1;t\nP2;R2;t\n",
                                                       encoding="utf-8")
    url = 'notebooklm_url: "https://notebooklm.google.com/notebook/x"\n' if com_url_nb else ""
    (crase / "_fonte-notebooklm.md").write_text(
        f"---\ntipo: fonte-notebooklm\n{url}---\n"
        + _pack_como_a_aprofunda_gera(NOME_BASE), encoding="utf-8")
    if com_midias:
        (crase / f"podcast-{NOME_BASE}.m4a").write_bytes(b"AAA")
        (crase / f"mapa-mental-{NOME_BASE}.png").write_bytes(b"PNG")

    # ------------------------------------------------------------------ #
    # assunto no layout LEGADO, de propósito: `regencia-verbal-e-nominal`
    #
    # O vault não tem mais nenhum, mas o coletor ainda aceita (`_arquivo_principal`
    # trata `{pasta}.md`), e caminho aceito sem teste é caminho que apodrece. Fica
    # UM — o secundário —, para o canônico ser o que a suíte exercita por padrão.
    # Traz também o flashcard de nome mais curto que o slug, que é outro caso real.
    # ------------------------------------------------------------------ #
    reg = mat / "assuntos" / "regencia-verbal-e-nominal"
    reg.mkdir(parents=True)
    (reg / "regencia-verbal-e-nominal.md").write_text(
        '---\ntitle: "Regência"\nstatus: concluido\n---\nResumo.\n', encoding="utf-8")
    (reg / "flashcards-regencia.md").write_text(  # nome mais curto que o slug
        "---\n---\n#flashcards\nP::R\n", encoding="utf-8")

    _montar_secoes(base)
    return base


def _montar_secoes(base: Path):
    """As pastas numeradas que a concurso-prep gera e o site ainda não publica.

    Junto com `_mat_vault()`, é o que faz o fixture ter a MESMA forma que o vault:
    foi exatamente um fixture divergente (assuntos sob `03-MAPAS-MATERIAS`, caminho
    que a concurso-aprofunda nunca emite) que manteve o bug do `_GERAL` verde.
    """
    def escrever(rel: str, texto: str):
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto, encoding="utf-8")

    escrever("00-INDICE.md",
             '---\ntipo: moc\n---\n# TESTE 2026\n\n'
             '- [[_COMUM/01-EDITAL/edital-resumo|Resumo do edital]]\n')

    escrever("_COMUM/01-EDITAL/edital-resumo.md",
             '---\ntipo: documentacao\n---\n# Resumo do edital\n\n'
             '## Estrutura da prova\n\n| Bloco | Questões |\n|---|---|\n| Geral | 20 |\n\n'
             '## Leis citadas\n\nVer [[_COMUM/04-MATERIAIS/livros-recomendados]].\n')
    escrever("_COMUM/01-EDITAL/analise-banca.md",
             '---\ntipo: documentacao\n---\n# Análise da banca\n\n'
             '## Pegadinhas comuns\n\n- Literalidade da lei.\n')
    (base / "_COMUM" / "01-EDITAL" / "edital-original.pdf").write_bytes(b"%PDF-1.4 x")

    escrever("_COMUM/04-MATERIAIS/livros-recomendados.md",
             '---\ntipo: material\n---\n# Livros\n\n## Português\n\n- Um livro.\n')
    escrever("_COMUM/04-MATERIAIS/leis-baixadas/00-INDICE.md",
             '---\ntipo: moc\n---\n# Leis\n\n- [[lei-1234-1990|Lei 1.234/1990]]\n')
    (base / "_COMUM" / "04-MATERIAIS" / "leis-baixadas"
     / "lei-1234-1990.pdf").write_bytes(b"%PDF-1.4 lei")

    escrever("_COMUM/05-HISTORICO-CONCURSO/concursos-anteriores.md",
             '---\ntipo: historico\n---\n# Edições anteriores\n\n## Análise\n\nTexto.\n')
    (base / "_COMUM" / "05-HISTORICO-CONCURSO" / "provas-anteriores").mkdir(parents=True)
    (base / "_COMUM" / "05-HISTORICO-CONCURSO" / "provas-anteriores"
     / "prova-2019.pdf").write_bytes(b"%PDF-1.4 prova")

    escrever("_COMUM/06-SINERGIA/concursos-similares.md",
             '---\ntipo: sinergia\n---\n# Sinergia\n\n## Critério aplicado\n\nTexto.\n')

    escrever("CARGO-X/02-CRONOGRAMA/cronograma-macro.md",
             '---\ntipo: cronograma\n---\n# Cronograma\n\n## Fases\n\n- [ ] Fase 1\n')
    escrever("CARGO-X/07-DISCURSIVA/guia-discursiva.md",
             '---\ntipo: documentacao\n---\n# Discursiva\n\n## Critérios\n\n- Coesão.\n')
    escrever("CARGO-X/08-TITULOS.md",
             '---\ntipo: documentacao\n---\n# Títulos\n\n- [ ] Diploma\n')
    escrever("CARGO-X/99-Status.md",
             '---\ntipo: status\n---\n# Status\n\n## Marcos\n\n- [x] Inscrição\n- [ ] Prova\n')

    # índice de matérias, com a linha de onde saem ordenação e selos
    escrever("CARGO-X/03-MAPAS-MATERIAS/00-INDICE.md",
             '---\ntipo: moc\n---\n# Mapas\n\n'
             '- [[01-portugues|01 · Português]] — ~10–12 q · 🟡 média\n')
    # Mapa de matéria. O template é rígido, mas o vault real varia dentro dele, e o
    # fixture precisa espelhar ESSA variação — não a forma idealizada. Daqui vêm:
    # as três formas do rótulo de pegadinhas (com e sem emoji, com e sem o nome da
    # banca), blocos REPETIDOS de subtópicos com sufixo temático, um H3 fora do
    # template (`Leis-chave`, `🧠 …` com tabela), checkbox já marcado, URL nua e
    # wikilink no material, e o mesmo H4 em dois tópicos (que colidiria de id).
    escrever("CARGO-X/03-MAPAS-MATERIAS/01-portugues.md",
             '---\ntipo: mapa-materia\nmateria: "Português"\n---\n'
             '# Mapa de Estudo — Português\n\n'
             '## 1. Emprego do acento indicativo de crase 🔴\n\n'
             '### Tópicos do edital (literais)\n\n> Crase.\n\n'
             '### Leis-chave\n\n- Acordo Ortográfico de 1990.\n\n'
             '#### Fontes\n\n- Manual da banca.\n\n'
             '### Subtópicos derivados — TEORIA\n\n'
             '- [x] Regra geral\n- [ ] Casos proibidos\n\n'
             '#### Detalhe do bloco\n\n- [ ] Antes de masculino\n\n'
             '### Subtópicos derivados — LEI 8.662/1993 (DECORAR ARTIGOS)\n\n'
             '- [ ] Artigo 4º\n'
             '- Observação sem checkbox\n\n'
             '### Material recomendado\n\n'
             '- Livro: *Gramática* — Pestana (Método).\n'
             '- Questões: https://qconcursos.com/crase\n'
             '- Lei: [[lei-1234-1990.pdf]]\n\n'
             '### ⚠️ Pegadinhas da banca neste tópico\n\n'
             '- Antes de verbo.\n- Antes de pronome.\n\n'
             '### Meta\n\n- [ ] 30 questões resolvidas\n\n'
             '---\n\n'
             '## 2. Reconhecimento de tipos textuais\n\n'
             '### Tópicos do edital (literais)\n\n> Tipos textuais.\n\n'
             '### Subtópicos derivados — TEORIA\n\n- [ ] Narração\n\n'
             '#### Detalhe do bloco\n\n- [ ] Dissertação\n\n'
             '### Pegadinhas da Quadrix neste tópico\n\n- Trocar tipo por gênero.\n\n'
             '### 🧠 Quem faz o quê — tabela de ouro\n\n'
             '| Tipo | Marca |\n|---|---|\n| Narração | Tempo |\n\n'
             '#### Fontes\n\n- Caderno de questões.\n\n'
             '### Meta\n\n- [ ] 10 questões resolvidas\n\n'
             '## ✍️ Meu resumo\n\nRASCUNHO-NAO-PUBLICAR\n-\n\n'
             '## ✅ Checklist Final\n\n- [ ] Revisar crase\n- [ ] Simulado\n')


def dir_aprof_crase(base: Path, materia: str = "portugues",
                    escopo: str = "CARGO-X") -> Path:
    """A pasta do aprofundamento principal — onde moram o `.md`, os flashcards, as
    mídias e o pacote.

    Existe porque `assuntos/crase` deixou de ser a pasta que guarda arquivos: no
    layout canônico ela só contém pastas de aprofundamento. Teste que escreve mídia
    ou lê o pacote quer ESTA pasta, e apontar para a de cima faz o arquivo ser
    ignorado em silêncio — que é o modo de falha mais caro desta suíte.
    """
    return _mat_vault(base, materia, escopo) / "assuntos" / "crase" / APROF_CRASE


# Nomes públicos, para quem importa de fora da suíte da skill.
montar_concurso = _montar_concurso
