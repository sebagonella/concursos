#!/usr/bin/env python3
"""
test_smoke.py - Smoke tests da skill concurso-publica (Subsistema A: coletor).

Roda com pytest ou standalone:
    python scripts/tests/test_smoke.py
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import site_collector as sc  # noqa: E402


# --------------------------------------------------------------------------- #
# indireção: a forma do modelo e a do caminho de saída vão mudar
# --------------------------------------------------------------------------- #
# Mais da metade da suíte fala da forma do modelo (`m["cargos"][0]…`) ou do caminho
# gerado (`out/<concurso>/<materia>/<assunto>/`). Ancorar isso em 30 lugares faz de
# qualquer mudança de estrutura um patch de 30 arquivos-teste. Todo acesso passa
# por estes três helpers, para a migração acontecer AQUI.
def _escopos(m: dict) -> list:
    """Os escopos do modelo — `escopos[]` quando existir, senão `cargos[]`."""
    return m.get("escopos") or m["cargos"]


def _materias(m: dict) -> list:
    """Todas as matérias do modelo, de todos os escopos, achatadas."""
    return [mat for e in _escopos(m) for mat in e["materias"]]


def _dir_materia(out: Path, concurso: str, materia: str = "portugues",
                 escopo: str = "cargo-x") -> Path:
    """Pasta da matéria no site gerado. O nível de escopo entra aqui quando o
    layout mudar; os testes não precisam saber."""
    return out / concurso / escopo / "materias" / materia


def _dir_assunto(out: Path, concurso: str, assunto: str,
                 materia: str = "portugues", escopo: str = "cargo-x") -> Path:
    return _dir_materia(out, concurso, materia, escopo) / assunto


def _mat_vault(base: Path, materia: str = "portugues",
               escopo: str = "CARGO-X") -> Path:
    """Pasta da matéria no VAULT, como a `concurso-aprofunda` a cria.

    Era `{CARGO}/03-MAPAS-MATERIAS/{materia}/` — caminho que a skill nunca emite, e
    que por isso mesmo mantinha o bug do `_GERAL` invisível. Agora espelha o real:
    `{ESCOPO}/03-APROFUNDAMENTO/{materia}/`.
    """
    return base / escopo / "03-APROFUNDAMENTO" / materia


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def _montar_concurso(base: Path, com_midias=True, com_url_nb=False):
    """Monta um concurso mínimo: 1 cargo, 1 matéria, 2 assuntos."""
    base.mkdir(parents=True, exist_ok=True)
    mat = _mat_vault(base)
    (base / ".meta.json").write_text(json.dumps(
        {"orgao": "TESTE", "ano": 2026, "banca": "Banca X"}), encoding="utf-8")

    # assunto completo: crase
    crase = mat / "assuntos" / "crase"
    crase.mkdir(parents=True)
    (crase / "crase.md").write_text(
        '---\ntitle: "Crase"\nstatus: concluido\n'
        'localizacao_livro: "Livro.pdf — págs. 10–20"\n---\n'
        "Resumo.\n- [x] Ler\n- [ ] Revisar\n- [ ] Questões\n", encoding="utf-8")
    (crase / "flashcards-crase.md").write_text(
        "---\ntipo: flashcards\n---\n#flashcards\n\nP1\n??\nR1\n\nP2\n??\nR2\n",
        encoding="utf-8")
    (crase / "flashcards-crase.csv").write_text("P1;R1;t\nP2;R2;t\n", encoding="utf-8")
    url = 'notebooklm_url: "https://notebooklm.google.com/notebook/x"\n' if com_url_nb else ""
    (crase / "_fonte-notebooklm.md").write_text(
        f"---\ntipo: fonte-notebooklm\n{url}---\npack\n", encoding="utf-8")
    if com_midias:
        (crase / "podcast-crase.m4a").write_bytes(b"AAA")
        (crase / "mapa-mental-crase.png").write_bytes(b"PNG")

    # assunto sem mídias e com flashcard de nome divergente: regencia
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
    # mapa de matéria: template rígido, com as variantes de rótulo que o vault usa
    escrever("CARGO-X/03-MAPAS-MATERIAS/01-portugues.md",
             '---\ntipo: mapa-materia\nmateria: "Português"\n---\n'
             '# Mapa de Estudo — Português\n\n'
             '## 1. Emprego do acento indicativo de crase 🔴\n\n'
             '### Tópicos do edital (literais)\n\n> Crase.\n\n'
             '### Subtópicos derivados\n\n- [ ] Regra geral\n- [ ] Casos proibidos\n\n'
             '### ⚠️ Pegadinhas da banca neste tópico\n\n- Antes de verbo.\n\n'
             '### Meta\n\n- [ ] 30 questões resolvidas\n\n'
             '## 2. Reconhecimento de tipos textuais\n\n'
             '### Subtópicos derivados — TEORIA\n\n- [ ] Narração\n\n'
             '### Meta\n\n- [ ] 10 questões resolvidas\n\n'
             '## ✍️ Meu resumo\n\n**Conceitos-chave:**\n-\n\n'
             '## ✅ Checklist Final\n\n- [ ] Revisar crase\n- [ ] Simulado\n')


# --------------------------------------------------------------------------- #
# unidades
# --------------------------------------------------------------------------- #
def test_fixture_espelha_as_pastas_numeradas_do_vault():
    """O fixture tem de ter a mesma forma que a `concurso-prep` gera.

    Fixture que inventa uma realidade que o gerador não produz é teste que se
    autoconfirma — foi assim que o bug do `_GERAL` ficou verde por meses (os
    assuntos estavam sob `03-MAPAS-MATERIAS`, caminho que a `concurso-aprofunda`
    nunca emite). Este teste existe para ninguém enxugar o fixture de novo.
    """
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        for rel in ("00-INDICE.md",
                    "_COMUM/01-EDITAL/edital-resumo.md",
                    "_COMUM/01-EDITAL/analise-banca.md",
                    "_COMUM/01-EDITAL/edital-original.pdf",
                    "_COMUM/04-MATERIAIS/livros-recomendados.md",
                    "_COMUM/04-MATERIAIS/leis-baixadas/lei-1234-1990.pdf",
                    "_COMUM/05-HISTORICO-CONCURSO/concursos-anteriores.md",
                    "_COMUM/06-SINERGIA/concursos-similares.md",
                    "CARGO-X/02-CRONOGRAMA/cronograma-macro.md",
                    "CARGO-X/03-MAPAS-MATERIAS/00-INDICE.md",
                    "CARGO-X/03-MAPAS-MATERIAS/01-portugues.md",
                    "CARGO-X/07-DISCURSIVA/guia-discursiva.md",
                    "CARGO-X/08-TITULOS.md",
                    "CARGO-X/99-Status.md"):
            assert (base / rel).exists(), rel


def test_contar_progresso():
    corpo = "- [x] a\n- [ ] b\n- [X] c\ntexto\n"
    p = sc.contar_progresso(corpo)
    assert p == {"total": 3, "feitos": 2}


def test_contar_cards_multiline_e_singleline():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "fc.md"
        f.write_text("P1\n??\nR1\n\nP2\n??\nR2\n", encoding="utf-8")
        assert sc.contar_cards(f) == 2
        f.write_text("---\nx: y\n---\nP1::R1\nP2::R2\nP3::R3\n", encoding="utf-8")
        assert sc.contar_cards(f) == 3


# --------------------------------------------------------------------------- #
# integração (CLI)
# --------------------------------------------------------------------------- #
def _rodar(base: Path) -> dict:
    r = subprocess.run(
        [sys.executable, str(ROOT / "site_collector.py"),
         "--concurso-dir", str(base), "--json"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_coleta_estrutura_completa():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        m = _rodar(base)
        assert m["concurso"] == "TESTE_2026"
        assert m["meta"]["banca"] == "Banca X"
        r = m["resumo"]
        # dois escopos: o cargo (que tem a matéria) e o _COMUM (que só tem seções).
        # Antes o _COMUM não era nem descoberto, porque a varredura partia de
        # `rglob("assuntos")` e ele não tem aprofundamento.
        assert (r["n_escopos"], r["n_cargos"]) == (2, 1)
        assert (r["n_materias"], r["n_assuntos"]) == (1, 2)
        assert r["n_documentos"] > 0 and r["n_anexos"] > 0
        assert [e["nome"] for e in _escopos(m)] == ["_COMUM", "CARGO-X"]
        assert [e["tipo"] for e in _escopos(m)] == ["comum", "cargo"]


def test_midias_por_presenca():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026", com_midias=True)
        m = _rodar(base)
        assuntos = {a["slug"]: a for a in _materias(m)[0]["assuntos"]}
        crase = assuntos["crase"]
        assert crase["midias"]["podcast"] == "podcast-crase.m4a"
        assert crase["midias"]["mapa_mental"] == "mapa-mental-crase.png"
        assert crase["midias"]["video"] is None      # ausente = None, sem quebrar
        reg = assuntos["regencia-verbal-e-nominal"]
        assert all(v is None for v in reg["midias"].values())


def test_flashcards_nome_divergente_tolerado():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        m = _rodar(base)
        assuntos = {a["slug"]: a for a in _materias(m)[0]["assuntos"]}
        reg = assuntos["regencia-verbal-e-nominal"]
        assert reg["flashcards"]["obsidian"] == "flashcards-regencia.md"
        assert reg["flashcards"]["n_cards"] == 1


def test_progresso_lido_do_vault():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        m = _rodar(base)
        crase = next(a for a in _materias(m)[0]["assuntos"]
                     if a["slug"] == "crase")
        assert crase["progresso"] == {"total": 3, "feitos": 1}
        assert crase["paginas_livro"] == "10–20"


def test_notebooklm_url_so_se_preenchida():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "A_2026", com_url_nb=False)
        m = _rodar(base)
        crase = next(a for a in _materias(m)[0]["assuntos"]
                     if a["slug"] == "crase")
        assert crase["notebooklm_url"] is None
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "B_2026", com_url_nb=True)
        m = _rodar(base)
        crase = next(a for a in _materias(m)[0]["assuntos"]
                     if a["slug"] == "crase")
        assert crase["notebooklm_url"].startswith("https://notebooklm.google.com/")


def test_concurso_vazio_avisa_sem_quebrar():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "VAZIO_2026"
        base.mkdir()
        r = subprocess.run(
            [sys.executable, str(ROOT / "site_collector.py"),
             "--concurso-dir", str(base), "--json"],
            capture_output=True, text=True)
        assert r.returncode == 0
        assert "nenhum assunto" in r.stderr.lower()
        m = json.loads(r.stdout)
        assert m["resumo"]["n_assuntos"] == 0



# --------------------------------------------------------------------------- #
# md2html (Subsistema B)
# --------------------------------------------------------------------------- #
import md2html  # noqa: E402
import site_builder as sb  # noqa: E402


def test_md2html_blocos_basicos():
    h = md2html.converter("# T\n\nUm **forte** e *leve*.\n\n- a\n- b\n")
    assert '<h1 id="t">T</h1>' in h      # heading agora carrega âncora
    assert "<strong>forte</strong>" in h and "<em>leve</em>" in h
    assert h.count("<li>") == 2


def test_md2html_imagem_nao_vira_link_com_bang_solto():
    """Regressão: `![alt](src)` casava a regex de LINK e saía como `!<a href=…>`,
    deixando toda imagem markdown quebrada."""
    h = md2html.converter("![Mapa da prova](mapa.png)\n")
    assert '<img src="mapa.png"' in h
    assert 'alt="Mapa da prova"' in h
    assert "!<a" not in h and "<a href=\"mapa.png\"" not in h


def test_md2html_embed_wikilink_nao_deixa_bang():
    """Regressão: `![[arquivo.png]]` resolvia o wikilink e sobrava o "!" na frente."""
    h = md2html.converter("![[podcast-crase.m4a]]\n")
    assert "!<span" not in h and "!<a" not in h
    assert "wikilink-morto" in h


def test_md2html_heading_recebe_id_e_sumario_bate():
    """O id do heading e a entrada do sumário vêm da MESMA fonte — se divergirem,
    `[[nota#seção]]` aponta para id inexistente."""
    md = "# Título\n\n## Regras gerais\n\ntexto\n\n### Casos especiais\n"
    h = md2html.converter(md)
    assert '<h2 id="regras-gerais">' in h
    assert '<h3 id="casos-especiais">' in h
    s = md2html.sumario(md)
    assert [x["id"] for x in s] == ["regras-gerais", "casos-especiais"]
    assert [x["nivel"] for x in s] == [2, 3]
    for x in s:                       # todo id do sumário existe no corpo
        assert f'id="{x["id"]}"' in h


def test_md2html_headings_repetidos_nao_colidem():
    h = md2html.converter("## Meta\n\na\n\n## Meta\n")
    assert '<h2 id="meta">' in h and '<h2 id="meta-2">' in h


def test_md2html_heading_dentro_de_codigo_nao_conta():
    """`#` em bloco cercado é comentário, não heading — se contasse, os ids do
    corpo e do sumário sairiam desalinhados."""
    md = "## Real\n\n```\n# comentario\n```\n\n## Outra\n"
    assert [x["id"] for x in md2html.sumario(md)] == ["real", "outra"]
    assert '<h2 id="outra">' in md2html.converter(md)


def test_md2html_wikilink_com_ancora_e_pipe_escapado():
    """Duas formas que o vault usa e o conversor ignorava: âncora de seção e o
    pipe escapado que a tabela markdown obriga (`\\|`), usado nos índices do BB."""
    def r(alvo):
        return f"../{alvo}/index.html"
    h = md2html.converter("[[crase#regras gerais|Regras]]\n", wikilink_resolver=r)
    assert '<a href="../crase/index.html#regras-gerais">Regras</a>' in h

    h2 = md2html.converter("| [[lei-8078\\|CDC]] |\n|---|\n| x |\n",
                           wikilink_resolver=r)
    assert '<a href="../lei-8078/index.html">CDC</a>' in h2
    assert "wikilink-morto" not in h2          # o alvo NÃO leva a barra no fim


def test_md2html_wikilink_sem_rotulo_mostra_so_o_nome():
    """Os wikilinks do SEDES usam caminho absoluto do vault. Sem rótulo, o caminho
    inteiro virava o texto visível da página — ruído, e vazando `_COMUM`."""
    h = md2html.converter("[[_COMUM/03-APROFUNDAMENTO/lingua-portuguesa/crase]]\n")
    assert ">crase<" in h
    assert "_COMUM" not in h


def test_md2html_checkbox_vira_tarefa_com_estado():
    h = md2html.converter("- [x] feito\n- [ ] aberto\n")
    assert "tarefa feito" in h and "tarefa aberto" in h


def test_md2html_escapa_html_perigoso():
    h = md2html.converter("<script>alert(1)</script> texto")
    assert "<script>" not in h
    assert "&lt;script&gt;" in h


def test_md2html_tabela_e_blockquote():
    h = md2html.converter("| a | b |\n|---|---|\n| 1 | 2 |\n\n> nota\n")
    assert "<table>" in h and "<th>a</th>" in h and "<td>1</td>" in h
    assert "<blockquote>" in h


def test_md2html_wikilink_resolvido_e_morto():
    h = md2html.converter("[[crase]] e [[inexistente]]",
                          wikilink_resolver=lambda a: "../crase/" if a == "crase" else None)
    assert '<a href="../crase/">crase</a>' in h
    assert "wikilink-morto" in h


def test_nome_legivel():
    assert sb.nome_legivel("SEDES_2026") == "SEDES 2026"
    assert "(previsto)" in sb.nome_legivel("BB_2027_PREVISTO")


def test_parsear_flashcards_multiline_e_singleline():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "fc.md"
        f.write_text("---\nx: y\n---\n#flashcards\n\nP1\n??\nR1\n\nP2\n??\nR2\n",
                     encoding="utf-8")
        cards = sb.parsear_flashcards(f)
        assert len(cards) == 2 and cards[0] == {"f": "P1", "v": "R1"}
        f.write_text("---\n---\nA::B\nC::D\n", encoding="utf-8")
        assert len(sb.parsear_flashcards(f)) == 2


# --------------------------------------------------------------------------- #
# site_builder (integração)
# --------------------------------------------------------------------------- #
def _construir(base: Path, out: Path):
    r = subprocess.run(
        [sys.executable, str(ROOT / "site_builder.py"),
         "--concurso-dir", str(base), "--out", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_builder_gera_paginas_e_assets():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        out = Path(d) / "site"
        r = _construir(base, out)
        # o contador tem de bater com o que foi realmente escrito. Ancorar um
        # inteiro aqui era dívida: qualquer página nova exigia editar o número, e o
        # número não dizia se o arquivo existia.
        assert r["paginas"] == len(list(out.rglob("index.html")))
        assert (out / "index.html").exists()            # índice raiz (concursos)
        assert (out / "teste_2026" / "index.html").exists()  # capa do concurso
        assert (out / "assets" / "site.css").exists()
        assert (out / "assets" / "site.js").exists()
        assert (_dir_assunto(out, "teste_2026", "crase") / "index.html").exists()


def test_builder_embute_midia_presente_e_omite_ausente():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026", com_midias=True)
        out = Path(d) / "site"
        _construir(base, out)
        crase = (_dir_assunto(out, "teste_2026", "crase") / "index.html").read_text(encoding="utf-8")
        assert "<audio controls" in crase          # tem podcast
        assert "media/unico/podcast-crase.m4a" in crase
        assert "<video" not in crase               # não tem vídeo -> seção ausente
        assert (_dir_assunto(out, "teste_2026", "crase")
                / "media" / "unico" / "podcast-crase.m4a").exists()


def test_builder_quiz_com_cards_embutidos():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        out = Path(d) / "site"
        _construir(base, out)
        crase = (_dir_assunto(out, "teste_2026", "crase") / "index.html").read_text(encoding="utf-8")
        assert 'class="cartao quiz"' in crase
        m = re.search(r'<script type="application/json">(.*?)</script>', crase, re.DOTALL)
        assert m and len(json.loads(m.group(1))) == 2


def test_builder_notebooklm_so_com_url():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "SEM_2026", com_url_nb=False)
        out = Path(d) / "s1"
        _construir(base, out)
        assert "Abrir no NotebookLM" not in (
            _dir_assunto(out, "sem_2026", "crase") / "index.html"
        ).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "COM_2026", com_url_nb=True)
        out = Path(d) / "s2"
        _construir(base, out)
        assert "Abrir no NotebookLM" in (
            _dir_assunto(out, "com_2026", "crase") / "index.html"
        ).read_text(encoding="utf-8")


def _auditar_links(out: Path) -> tuple[list, list]:
    """Resolve todo href/src do site contra o disco. Devolve (quebrados, órfãos).

    A versão anterior usava `([^"#?]+)`, o que fazia a regex **não casar nada**
    quando a URL tinha `#` ou `?` — ou seja, link com âncora passava sem ser
    verificado. Como o md2html agora gera âncoras de heading, uma classe inteira de
    link ficaria fora de cobertura exatamente quando passou a existir.

    Também exige `index.html` em link de diretório (senão o nginx devolve 403 ou
    listagem) e acusa página gerada que ninguém aponta — com a navegação crescendo,
    esquecer de linkar uma seção é plausível e invisível de outra forma.
    """
    quebrados: list[str] = []
    apontadas: set[Path] = set()
    paginas = {p.resolve() for p in out.rglob("index.html")}

    for f in sorted(out.rglob("*.html")):
        h = f.read_text(encoding="utf-8")
        for attr in ("href", "src"):
            for bruto in re.findall(rf'{attr}="([^"]+)"', h):
                if bruto.startswith(("http", "mailto:", "#", "data:")):
                    continue
                caminho, _, frag = bruto.partition("#")
                caminho = caminho.split("?")[0]
                if not caminho:
                    continue
                alvo = (f.parent / caminho).resolve()
                if alvo.is_dir():                 # link de diretório precisa de index
                    alvo = alvo / "index.html"
                if not alvo.exists():
                    quebrados.append(f"{f.relative_to(out)} -> {bruto}")
                    continue
                if alvo in paginas:
                    apontadas.add(alvo)
                if frag:                          # a âncora tem de existir no destino
                    if f'id="{frag}"' not in alvo.read_text(encoding="utf-8"):
                        quebrados.append(
                            f"{f.relative_to(out)} -> {bruto} (âncora inexistente)")

    raiz = (out / "index.html").resolve()
    orfas = sorted(str(p.relative_to(out)) for p in paginas - apontadas - {raiz})
    return quebrados, orfas


def test_builder_links_internos_resolvem():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        out = Path(d) / "site"
        _construir(base, out)
        quebrados, _orfas = _auditar_links(out)
        assert not quebrados, quebrados


def test_builder_nao_gera_pagina_orfa():
    """Página gerada e não linkada de lugar nenhum é trabalho invisível."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        out = Path(d) / "site"
        _construir(base, out)
        _quebrados, orfas = _auditar_links(out)
        assert not orfas, orfas


def test_auditor_de_links_pega_ancora_e_diretorio_sem_index():
    """Contra-prova do auditor: ele tem de reprovar o que antes passava calado."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "site"
        (out / "vazio").mkdir(parents=True)
        (out / "index.html").write_text(
            '<a href="vazio/">dir sem index</a>'
            '<a href="alvo/index.html#nao-existe">âncora morta</a>',
            encoding="utf-8")
        (out / "alvo").mkdir()
        (out / "alvo" / "index.html").write_text(
            '<h2 id="existe">x</h2>', encoding="utf-8")
        quebrados, _ = _auditar_links(out)
        assert any("vazio/" in q for q in quebrados)
        assert any("âncora inexistente" in q for q in quebrados)



# --------------------------------------------------------------------------- #
# prioridade, banca, multi-concurso, mídias e tema
# --------------------------------------------------------------------------- #
def test_prefixo_e_relativo_calculados_da_rota():
    """Substitui os prefixos literais (`"../"`, `"../../"`, `"../../../"`) que
    estavam espalhados pelos templates. Prefixo errado é a regressão mais comum
    desta skill, e cada nível de pasta novo exigia acertar todos na mão."""
    assert sb.prefixo_de("index.html") == ""
    assert sb.prefixo_de("conc/index.html") == "../"
    assert sb.prefixo_de("conc/mat/assunto/index.html") == "../../../"

    # irmão na mesma matéria
    assert sb.relativo("c/m/crase/index.html", "c/m/regencia/index.html") \
        == "../crase/index.html"
    # subir até a raiz do site (assets)
    assert sb.relativo("assets/site.css", "c/m/a/index.html") \
        == "../../../assets/site.css"
    # capa a partir da matéria, e índice raiz a partir da capa
    assert sb.relativo("c/index.html", "c/m/index.html") == "../index.html"
    assert sb.relativo("index.html", "c/index.html") == "../index.html"
    # âncora preservada
    assert sb.relativo("c/m/a/index.html#flashcards", "c/m/b/index.html") \
        == "../a/index.html#flashcards"


def test_rotas_casa_as_convencoes_de_wikilink_do_vault():
    """Os wikilinks do SEDES usam caminho absoluto do vault e os do BB, nome nu.
    Reduzir ao basename sem extensão faz as duas caírem na mesma chave."""
    r = sb.Rotas()
    r.registrar("c/m/crase/index.html", "crase", "crase--padrao--pestana--SEDES_2026")
    for alvo in ("crase",
                 "crase.md",
                 "CRASE",
                 "_COMUM/03-APROFUNDAMENTO/lingua-portuguesa/assuntos/crase",
                 "crase--padrao--pestana--SEDES_2026.md"):
        assert r.rota_de(alvo) == "c/m/crase/index.html", alvo
    assert r.rota_de("nao-existe") is None


def test_resolvedor_global_atravessa_materia():
    """O resolvedor anterior era uma closure sobre os assuntos da MESMA matéria, e
    todo wikilink que atravessava matéria ou apontava para documento morria."""
    r = sb.Rotas()
    r.registrar("c/portugues/crase/index.html", "crase")
    r.registrar("c/suas/loas/index.html", "loas")
    resolver = r.resolvedor("c/portugues/crase/index.html")
    assert resolver("loas") == "../../suas/loas/index.html"
    assert resolver("inexistente") is None


def test_rotas_tem_tres_classes_de_alvo():
    """Nem todo alvo de wikilink é página: flashcards são artefato embutido (viram
    âncora) e mídia é arquivo copiado. Sem essa distinção os wikilinks de mídia dos
    pacotes NotebookLM viram parede de link morto."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026", com_midias=True)
        m = sc.coletar_concurso(base)
        rotas, plano = sb.montar_rotas(m, "teste_2026")

        raiz_a = "teste_2026/cargo-x/materias/portugues/crase"
        # página
        assert rotas.rota_de("crase") == f"{raiz_a}/index.html"
        # artefato embutido -> âncora na página que o hospeda
        assert rotas.rota_de("flashcards-crase") == f"{raiz_a}/index.html#flashcards"
        # arquivo copiado -> caminho da mídia dentro do site
        assert rotas.rota_de("podcast-crase.m4a") \
            == f"{raiz_a}/media/unico/podcast-crase.m4a"
        # anexo de seção -> caminho do arquivo dentro do site
        assert rotas.rota_de("lei-1234-1990.pdf") \
            == "teste_2026/comum/materiais/arquivos/leis-baixadas/lei-1234-1990.pdf"
        # o plano cobre capa, os dois escopos, suas seções, documentos e assuntos
        tipos = [p["tipo"] for p in plano]
        assert tipos[0] == "capa"
        assert tipos.count("escopo") == 2
        assert tipos.count("assunto") == 2
        assert "secao" in tipos and "documento" in tipos


def test_wikilink_de_flashcards_aponta_para_a_ancora_do_quiz():
    """Antes, TODO wikilink morto do site real apontava para flashcards."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        alvo = _mat_vault(base) / "assuntos" / "crase"
        md = alvo / "crase.md"
        md.write_text(md.read_text(encoding="utf-8")
                      + "\nVer [[flashcards-crase]].\n", encoding="utf-8")
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_assunto(out, "teste_2026", "crase") / "index.html").read_text(
            encoding="utf-8")
        assert 'href="index.html#flashcards"' in h
        assert 'id="flashcards"' in h
        quebrados, _ = _auditar_links(out)
        assert not quebrados, quebrados


def test_escopo_vem_do_primeiro_componente_do_caminho():
    """Regressão do bug do `_GERAL`. A versão anterior procurava o segmento
    `03-MAPAS` no caminho e devolvia o componente anterior — mas o aprofundamento
    vive em `03-APROFUNDAMENTO`, então a condição nunca casava com o vault real e
    TODA matéria caía em `_GERAL`, deixando a capa sem agrupamento nenhum.

    O teste antigo não pegava porque a fixture montava os assuntos sob
    `03-MAPAS-MATERIAS`, um layout que a concurso-aprofunda não produz.
    """
    base = Path("/v/SEDES_2026")
    casos = {
        "_COMUM/03-APROFUNDAMENTO/lingua-portuguesa": "_COMUM",
        "AGENTE-COMERCIAL/03-APROFUNDAMENTO/vendas-e-negociacao": "AGENTE-COMERCIAL",
        "CARGO-X/03-MAPAS-MATERIAS/portugues": "CARGO-X",
        "portugues": "_GERAL",           # layout achatado: matéria na raiz
    }
    for rel, esperado in casos.items():
        assert sc.cargo_de(base / rel, base) == esperado, rel
    assert sc.cargo_de(Path("/outro/lugar"), base) == "_GERAL"


def test_midia_do_assunto_e_uniao_dos_aprofundamentos():
    """Regressão: `midias` era herdada do aprofundamento PRINCIPAL, e como a
    ordenação põe `detalhado` primeiro, um assunto cuja mídia estava no `padrao`
    aparecia sem mídia. No vault real era o caso do único assunto com podcast,
    vídeo e mapa mental — o site anunciava "0 com áudio" na matéria inteira.
    """
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026", com_midias=False)
        alvo = _mat_vault(base) / "assuntos" / "crase"
        # detalhado (que ordena primeiro) SEM mídia; padrao COM mídia
        for nome, tem_midia in (("detalhado--pestana", False), ("padrao--pestana", True)):
            p = alvo / nome
            p.mkdir(parents=True)
            (p / f"crase--{nome}.md").write_text(
                f'---\ntitle: "Crase"\nfontes: "Pestana"\n---\nx\n', encoding="utf-8")
            if tem_midia:
                (p / f"podcast-crase--{nome}.m4a").write_bytes(b"A")

        a = sc.coletar_assunto(alvo)
        assert a["aprofundamentos"][0]["nivel"] == "detalhado"      # principal
        assert a["aprofundamentos"][0]["midias"]["podcast"] is None
        assert a["midias"]["podcast"], "presença deve ser a UNIÃO, não a do principal"

        m = sc.coletar_materia(alvo.parent.parent)
        assert m["n_com_podcast"] == 1


def test_rebuild_nao_deixa_pasta_do_layout_antigo():
    """Regressão: `construir()` só fazia mkdir, então pasta de layout anterior
    sobrevivia em out/ — e o `rsync --delete` do deploy NÃO a remove, porque ela
    existe na origem. A limpeza tem de ser escopada ao concurso: apagar o destino
    inteiro mataria os concursos irmãos e o assets/ compartilhado."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "site"
        aaa = _montar_concurso(Path(d) / "AAA_2026")
        _construir(aaa, out)
        _construir(_montar_concurso(Path(d) / "BBB_2027"), out)

        orfa = out / "aaa_2026" / "layout-antigo"
        orfa.mkdir(parents=True)
        (orfa / "index.html").write_text("velho", encoding="utf-8")

        _construir(aaa, out)           # rebuild do MESMO concurso
        assert not orfa.exists(), "pasta órfã sobreviveu ao rebuild"
        # o irmão e os assets compartilhados NÃO podem ter sido levados
        assert (out / "bbb_2027" / "index.html").exists()
        assert (out / "assets" / "site.css").exists()
        assert (out / "index.html").exists()


def test_rotulo_do_escopo_nao_expoe_convencao_de_pasta():
    assert sb.nome_escopo("_COMUM") == "Comum a todos os cargos"
    assert sb.nome_escopo("_GERAL") == ""          # escopo implícito: sem rótulo
    assert sb.nome_escopo("AGENTE-COMERCIAL") == "AGENTE-COMERCIAL"


def test_capa_agrupa_por_escopo():
    """O agrupamento por COMUM/cargo dentro do concurso — item 1 do pedido, que
    nunca funcionou porque `cargo_de()` caía sempre em `_GERAL`.

    A capa lista os GALHOS (um card por escopo). A grade de matérias, que ficava
    aqui, desceu para o hub do escopo: na capa o que se faz é escolher o cargo.
    """
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        # matéria aprofundada sob _COMUM, como no vault real
        outra = base / "_COMUM" / "03-APROFUNDAMENTO" / "suas" / "assuntos" / "loas"
        outra.mkdir(parents=True)
        (outra / "loas.md").write_text('---\ntitle: "LOAS"\n---\nx\n', encoding="utf-8")

        out = Path(d) / "site"
        _construir(base, out)
        h = (out / "teste_2026" / "index.html").read_text(encoding="utf-8")
        assert "CARGO-X" in h and "Comum a todos os cargos" in h
        assert '<span class="tag">comum</span>' in h
        assert "_COMUM" not in h, "convenção de pasta não deve vazar para a página"
        # os dois hubs de escopo existem e a capa aponta para eles
        assert (out / "teste_2026" / "comum" / "index.html").exists()
        assert (out / "teste_2026" / "cargo-x" / "index.html").exists()
        assert 'href="comum/index.html"' in h and 'href="cargo-x/index.html"' in h
        quebrados, orfas = _auditar_links(out)
        assert not quebrados, quebrados
        assert not orfas, orfas


def test_secoes_numeradas_viram_paginas_com_anexos():
    """Item 2 do pedido: todo o conteúdo abaixo do concurso, não só o
    aprofundamento. Os `.md` viram documento; o resto vira anexo copiado, porque o
    nginx só serve `/srv/site` — sem a cópia, o link da lei só funcionaria na
    máquina do vault."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        out = Path(d) / "site"
        _construir(base, out)

        comum = out / "teste_2026" / "comum"
        # documento de seção
        assert (comum / "edital" / "edital-resumo" / "index.html").exists()
        assert (comum / "edital" / "index.html").exists()
        assert (comum / "materiais" / "index.html").exists()
        assert (comum / "historico" / "index.html").exists()
        assert (comum / "sinergia" / "index.html").exists()
        # seções do cargo
        cargo = out / "teste_2026" / "cargo-x"
        for slug in ("cronograma", "discursiva", "titulos"):
            assert (cargo / slug / "index.html").exists(), slug
        # anexos copiados, preservando a subpasta do vault
        assert (comum / "materiais" / "arquivos" / "leis-baixadas"
                / "lei-1234-1990.pdf").exists()
        assert (comum / "edital" / "arquivos" / "edital-original.pdf").exists()

        # 00-INDICE e 99-Status são LIDOS, não republicados
        todo_html = "\n".join(p.read_text(encoding="utf-8")
                              for p in out.rglob("index.html"))
        assert "00-INDICE" not in todo_html
        assert not list(out.rglob("*99-status*"))

        quebrados, orfas = _auditar_links(out)
        assert not quebrados, quebrados
        assert not orfas, orfas


def test_mapa_de_materia_vira_aba_plano():
    """Item 4 do pedido. Uma matéria, duas visões: Plano (o mapa do edital) e Estudo
    (os assuntos aprofundados)."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_materia(out, "teste_2026") / "index.html").read_text(encoding="utf-8")

        assert 'data-visao-alvo="plano"' in h and 'data-visao-alvo="estudo"' in h
        assert 'data-visao="plano"' in h and 'data-visao="estudo"' in h
        # os dois tópicos do mapa do fixture, com seus subtópicos
        assert h.count('class="topico"') == 2
        assert "Emprego do acento indicativo de crase" in h
        assert "Regra geral" in h and "Casos proibidos" in h
        # rótulos com variante (⚠️ Pegadinhas, Subtópicos derivados — TEORIA) foram lidos
        assert "Narração" in h
        # emoji de prioridade sai do título e vira selo
        assert "🔴" not in h
        quebrados, orfas = _auditar_links(out)
        assert not quebrados, quebrados
        assert not orfas, orfas


def test_mapa_descarta_meu_resumo_e_conta_progresso_separado():
    """`✍️ Meu resumo` está vazio em 16 dos 24 mapas do vault e nos outros 8 é
    exercício de preenchimento — na web rende cabeçalho seguido de nada.

    E o progresso do mapa é contado à parte: os 24 mapas somam 2.220 checkboxes
    nenhum marcado, e misturá-los com os ~200 do aprofundamento apagaria a única
    barra que hoje significa algo."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_materia(out, "teste_2026") / "index.html").read_text(encoding="utf-8")
        assert "Meu resumo" not in h
        assert "Conceitos-chave" not in h
        assert "itens do plano" in h        # progresso do mapa, rotulado como tal

        m = sc.coletar_concurso(base)
        mat = _materias(m)[0]
        # o progresso do assunto (3 itens, 1 feito) não foi contaminado pelo mapa
        assert mat["assuntos"][0]["progresso"] == {"total": 3, "feitos": 1}
        assert mat["mapa"]["progresso"]["total"] >= 3


def test_topico_do_mapa_linka_so_com_casamento_exato():
    """Derivar o link tópico→assunto por slugificação daria link errado na maioria:
    dos 203 tópicos dos 24 mapas do vault, só ~18% casam. E o falso negativo é pior
    que a ausência — tópico sem link lido como "não tem aprofundamento" quando existe
    com outro nome esconde trabalho já feito. Sem casamento, a página não afirma nada.
    """
    materia = {"assuntos": [{"slug": "crase"}, {"slug": "regencia"}],
               "aliases_mapa": {}}
    # casa exato
    assert sb.assuntos_do_topico({"titulo": "Crase", "slug": "crase"}, materia) \
        == ["crase"]
    # não casa: nenhum palpite
    assert sb.assuntos_do_topico(
        {"titulo": "Domínio da estrutura morfossintática", "slug": "dominio-da-estrutura"},
        materia) == []
    # alias opcional resolve o 1:N que o slug não alcança
    materia_alias = dict(materia, aliases_mapa={
        "dominio da estrutura morfossintatica": ["crase", "regencia"]})
    assert sb.assuntos_do_topico(
        {"titulo": "Domínio da estrutura morfossintática", "slug": "x"},
        materia_alias) == ["crase", "regencia"]
    # alias apontando para assunto inexistente não inventa link
    materia_ruim = dict(materia, aliases_mapa={"crase": ["nao-existe"]})
    assert sb.assuntos_do_topico({"titulo": "Crase", "slug": "crase"},
                                 materia_ruim) == []


def test_pagina_sem_topico_nao_afirma_falta_de_aprofundamento():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_materia(out, "teste_2026") / "index.html").read_text(encoding="utf-8")
        for frase in ("sem aprofundamento", "não aprofundado", "nao aprofundado"):
            assert frase.lower() not in h.lower(), frase


def test_materia_so_com_mapa_nao_e_descartada():
    """`coletar_materia()` devolvia None sem `assuntos/`, então matéria que só tem
    plano de estudo era descartada em silêncio — sumia o plano inteiro do cargo."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        # mapa de matéria sem nenhum aprofundamento correspondente
        (base / "CARGO-X" / "03-MAPAS-MATERIAS" / "02-matematica.md").write_text(
            '---\ntipo: mapa-materia\nmateria: "Matemática"\n---\n'
            '# Mapa — Matemática\n\n## 1. Porcentagens\n\n'
            '### Subtópicos derivados\n\n- [ ] Regra de três\n', encoding="utf-8")
        out = Path(d) / "site"
        _construir(base, out)
        assert (_dir_materia(out, "teste_2026", "matematica") / "index.html").exists()
        h = (_dir_materia(out, "teste_2026", "matematica")
             / "index.html").read_text(encoding="utf-8")
        assert "Porcentagens" in h
        # sem aprofundamento, não há por que oferecer a aba
        assert 'data-visao-alvo="estudo"' not in h
        quebrados, orfas = _auditar_links(out)
        assert not quebrados and not orfas


def test_materia_homonima_em_escopos_diferentes_nao_colide():
    """Regressão: a navegação usava o índice de NOMES, que resolve por basename e o
    primeiro registro vence — com `portugues` no cargo e no comum, o hub do cargo
    apontava para a matéria do comum e a própria ficava órfã. Link de navegação é
    sempre explícito; o índice é só para wikilink."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        outra = base / "_COMUM" / "03-APROFUNDAMENTO" / "portugues" / "assuntos" / "crase"
        outra.mkdir(parents=True)
        (outra / "crase.md").write_text('---\ntitle: "Crase (comum)"\n---\nx\n',
                                        encoding="utf-8")
        out = Path(d) / "site"
        _construir(base, out)
        assert (_dir_materia(out, "teste_2026", "portugues", "comum")
                / "index.html").exists()
        assert (_dir_materia(out, "teste_2026", "portugues", "cargo-x")
                / "index.html").exists()
        hub = (out / "teste_2026" / "cargo-x" / "index.html").read_text(encoding="utf-8")
        assert 'href="materias/portugues/index.html"' in hub
        quebrados, orfas = _auditar_links(out)
        assert not quebrados, quebrados
        assert not orfas, orfas


def test_pacote_notebooklm_vira_pagina_com_prompts():
    """Item 3 do pedido. O vault tem 92 pacotes prontos e um único assunto com mídia
    de verdade: o gargalo não é ter o roteiro, é executá-lo — daí a página existir
    para dar o prompt a um toque."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        pack = _mat_vault(base) / "assuntos" / "crase" / "_fonte-notebooklm.md"
        pack.write_text(
            "---\ntipo: fonte-notebooklm\nnotebooklm_status: nao-criado\n---\n"
            "# Pacote\n\n## 1. Fontes para subir no notebook\n\n"
            "1. **`crase.md`** — o resumo curado.\n\n"
            "## 2. 🎧 Podcast (Audio Overview)\n\n"
            "- Studio → **Audio Overview** → **Customize**.\n"
            "- Formato: Deep Dive\n\n```\nFoque em Crase para concurso.\n```\n\n"
            "## 3. 🧠 Mapa Mental (Mind Map)\n\n```\nConstrua o mapa mental.\n```\n\n"
            "## 7. 💬 Perguntas úteis no chat\n\n- O que mais cai?\n\n"
            "## ✅ Checklist\n\n- [ ] Criar notebook\n- [x] Subir fontes\n",
            encoding="utf-8")
        out = Path(d) / "site"
        _construir(base, out)

        p = _dir_assunto(out, "teste_2026", "crase") / "notebooklm" / "index.html"
        assert p.exists()
        h = p.read_text(encoding="utf-8")
        assert h.count('class="cartao prompt"') == 2      # podcast e mapa mental
        assert h.count("data-copiar") == 2
        assert "Foque em Crase para concurso." in h
        assert "Studio → Audio Overview → Customize." in h   # roteiro de cliques
        assert "O que mais cai?" in h
        assert 'class="tarefa feito"' in h and 'class="tarefa aberto"' in h
        # sem URL salva, orienta em vez de oferecer botão morto
        assert "Abrir no NotebookLM" not in h
        assert "notebooklm_url" in h
        # a página do assunto oferece o caminho para cá
        ha = (_dir_assunto(out, "teste_2026", "crase")
              / "index.html").read_text(encoding="utf-8")
        assert "Pacote NotebookLM" in ha

        quebrados, orfas = _auditar_links(out)
        assert not quebrados, quebrados
        assert not orfas, orfas


def test_pacote_notebooklm_e_por_assunto_com_abas():
    """Uma página por ASSUNTO, não por pacote: entre `padrao--X` e `detalhado--X` só
    o prompt de áudio difere, e 92 páginas com ~95% de repetição não se justificam."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        alvo = _mat_vault(base) / "assuntos" / "crase"
        for nome in ("padrao--pestana", "detalhado--pestana"):
            p = alvo / nome
            p.mkdir(parents=True)
            (p / f"crase--{nome}.md").write_text(
                '---\ntitle: "Crase"\nfontes: "Pestana"\n---\nx\n', encoding="utf-8")
            (p / "_fonte-notebooklm.md").write_text(
                "---\ntipo: fonte-notebooklm\n---\n# P\n\n"
                "## 2. 🎧 Podcast\n\n```\nprompt " + nome + "\n```\n",
                encoding="utf-8")
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_assunto(out, "teste_2026", "crase") / "notebooklm"
             / "index.html").read_text(encoding="utf-8")
        # três abas: os dois aprofundamentos novos + o legado (arquivo solto na pasta
        # do assunto), que a skill continua lendo de propósito
        assert h.count('data-alvo="') == 3
        assert 'data-alvo="original"' in h
        assert "prompt padrao--pestana" in h and "prompt detalhado--pestana" in h
        # uma página só para o assunto, não uma por pacote
        assert len(list((_dir_assunto(out, "teste_2026", "crase")
                         / "notebooklm").glob("**/index.html"))) == 1


def test_card_mostra_so_midia_presente_e_pagina_mostra_todas():
    """Numa matéria de 11 assuntos, os 8 tipos com os ausentes em cinza são 88 ícones
    que afogam o título. No card só entra o que existe; a grade completa fica na
    página do assunto, onde "falta gerar" é acionável — é de lá que se chega ao
    prompt do NotebookLM."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026", com_midias=True)
        out = Path(d) / "site"
        _construir(base, out)
        materia = (_dir_materia(out, "teste_2026") / "index.html").read_text(encoding="utf-8")
        assunto = (_dir_assunto(out, "teste_2026", "crase")
                   / "index.html").read_text(encoding="utf-8")
        assert "selo ausente" not in materia
        assert 'class="selo"' in materia            # o que existe continua sinalizado
        assert "selo ausente" in assunto            # na página, o que falta é visível


def test_card_nao_repete_a_mesma_informacao_em_tres_selos():
    """O card antigo trazia "1 fonte", "Padrão + Detalhado" e "2 versões" — com uma
    única fonte, "2 versões" é exatamente "Padrão + Detalhado" dito de novo. Fonte
    única passa a ser texto de contexto (dado), ao lado das páginas; selo fica só
    para estado."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        alvo = _mat_vault(base) / "assuntos" / "regencia-verbal-e-nominal"
        for nome in ("padrao--pestana", "detalhado--pestana"):
            p = alvo / nome
            p.mkdir(parents=True)
            (p / f"regencia--{nome}.md").write_text(
                '---\ntitle: "Regência"\nfontes: "Pestana"\n'
                'localizacao_livro: "Pestana.pdf — págs. 978–1017"\n---\nx\n',
                encoding="utf-8")
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_materia(out, "teste_2026") / "index.html").read_text(encoding="utf-8")

        assert "Padrão + Detalhado" in h            # o nível continua sinalizado
        assert "1 fonte" not in h                   # fonte única não é selo
        assert "versões" not in h                   # com 1 fonte, repetiria o nível
        assert "págs. 978–1017 · Pestana" in h      # virou linha de contexto

        # com DUAS fontes, os selos voltam: aí a contagem informa algo novo
        outro = alvo / "padrao--abreu"
        outro.mkdir(parents=True)
        (outro / "regencia--padrao--abreu.md").write_text(
            '---\ntitle: "Regência"\nfontes: "Abreu"\n---\nx\n', encoding="utf-8")
        _construir(base, out)
        h2 = (_dir_materia(out, "teste_2026") / "index.html").read_text(encoding="utf-8")
        assert "2 fontes" in h2 and "versões" in h2


def test_anexo_e_copiado_uma_vez_por_secao_nao_por_documento():
    """Regressão: `copiar_anexos` rodava também na página de cada documento, e como a
    rota do documento é um nível mais fundo, cada documento recebia uma cópia inteira
    dos anexos da seção. No vault real dava 685 PDFs em vez de 78, e o site pulava de
    260 MB para 534."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        out = Path(d) / "site"
        _construir(base, out)
        copias = list(out.rglob("lei-1234-1990.pdf"))
        assert len(copias) == 1, [str(p.relative_to(out)) for p in copias]
        assert copias[0].parent.name == "leis-baixadas"      # subpasta preservada
        # e o PDF do edital, cuja seção tem 2 documentos, também só uma vez
        assert len(list(out.rglob("edital-original.pdf"))) == 1
        quebrados, _ = _auditar_links(out)
        assert not quebrados, quebrados


def test_00_indice_nao_sequestra_wikilink_para_a_capa():
    """Regressão: registrar o nome genérico `00-INDICE` para a capa fazia TODO
    `[[00-INDICE]]` do vault cair no concurso — e o vault tem esse nome em meia dúzia
    de lugares. Wikilink resolvido para o lugar errado é pior que morto: o morto
    avisa, o errado não."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        doc = base / "_COMUM" / "01-EDITAL" / "edital-resumo.md"
        doc.write_text(doc.read_text(encoding="utf-8")
                       + "\nVer o [[00-INDICE]] das leis.\n", encoding="utf-8")
        out = Path(d) / "site"
        _construir(base, out)
        h = (out / "teste_2026" / "comum" / "edital" / "edital-resumo"
             / "index.html").read_text(encoding="utf-8")
        assert "wikilink-morto" in h, "alvo ambíguo deve ficar morto, não ser adivinhado"
        assert '<a href="../../../index.html">00-INDICE</a>' not in h


def test_documento_longo_ganha_sumario_lateral():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        longo = base / "_COMUM" / "01-EDITAL" / "cronograma-oficial.md"
        longo.write_text("---\ntipo: documentacao\n---\n# Cronograma oficial\n\n"
                         + "".join(f"## Etapa {i}\n\ntexto\n\n" for i in range(1, 6)),
                         encoding="utf-8")
        out = Path(d) / "site"
        _construir(base, out)
        h = (out / "teste_2026" / "comum" / "edital" / "cronograma-oficial"
             / "index.html").read_text(encoding="utf-8")
        assert 'class="cartao sumario"' in h
        assert 'href="#etapa-1"' in h and 'id="etapa-1"' in h
        quebrados, _ = _auditar_links(out)
        assert not quebrados, quebrados

        # documento curto não ganha sumário — 2 seções não justificam índice
        h2 = (out / "teste_2026" / "comum" / "edital" / "analise-banca"
              / "index.html").read_text(encoding="utf-8")
        assert 'class="cartao sumario"' not in h2


def test_css_estiliza_wikilink_morto():
    """O md2html emite `.wikilink-morto` desde a primeira versão; sem regra no CSS
    o alvo não publicado ficava indistinguível de texto comum."""
    css = (ROOT.parent / "assets" / "site.css").read_text(encoding="utf-8")
    assert ".wikilink-morto" in css
    bloco = css[css.index(".wikilink-morto"):]
    bloco = bloco[:bloco.index("}")]
    assert "var(--" in bloco and not re.search(r":\s*#[0-9a-fA-F]{3,6}", bloco)


def test_normalizar_prioridade_aceita_prefixo():
    assert sc.normalizar_prioridade("Prioridade alta") == "alta"
    assert sc.normalizar_prioridade("Média") == "media"
    assert sc.normalizar_prioridade("Base/leitura") == "base"
    assert sc.normalizar_prioridade("qualquer") is None


def test_prioridade_derivada_do_guia():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        mat = _mat_vault(base)
        (mat / "00-GUIA-NOTEBOOKLM.md").write_text(
            "## Ordem sugerida\n\nPrioridade alta (os que derrubam): Crase.\n"
            "Média: Regência.\n", encoding="utf-8")
        m = _rodar(base)
        assuntos = {a["slug"]: a for a in _materias(m)[0]["assuntos"]}
        assert assuntos["crase"]["prioridade"] == "alta"
        assert assuntos["regencia-verbal-e-nominal"]["prioridade"] == "media"


def test_prioridade_do_frontmatter_tem_precedencia():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        crase = _mat_vault(base) / "assuntos" / "crase"
        (crase / "crase.md").write_text(
            '---\ntitle: "Crase"\nprioridade: base\nstatus: concluido\n---\ntexto\n',
            encoding="utf-8")
        m = _rodar(base)
        a = next(x for x in _materias(m)[0]["assuntos"] if x["slug"] == "crase")
        assert a["prioridade"] == "base"


def test_detecta_todas_as_midias_do_notebooklm():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        crase = _mat_vault(base) / "assuntos" / "crase"
        for nome in ("video-crase.mp4", "slides-crase.pdf", "infografico-crase.png",
                     "report-crase.md", "teste-crase.md", "tabela-crase.csv"):
            (crase / nome).write_bytes(b"x")
        m = _rodar(base)
        a = next(x for x in _materias(m)[0]["assuntos"] if x["slug"] == "crase")
        for chave in ("podcast", "video", "slides", "mapa_mental",
                      "infografico", "report", "teste", "tabela"):
            assert a["midias"][chave], f"não detectou {chave}"


def test_doc_da_banca_detectado_e_renderizado_antes_dos_assuntos():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        mat = _mat_vault(base)
        (mat / "COMO-A-BANCA-COBRA-PORTUGUES.md").write_text(
            "# Como a Banca X cobra\n\nTexto sobre o estilo da banca.\n", encoding="utf-8")
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_materia(out, "teste_2026") / "index.html").read_text(encoding="utf-8")
        i_banca = h.find("Como a Banca X cobra")
        i_grupo = h.find('class="grupo-prioridade"')
        assert i_banca > 0
        assert i_grupo == -1 or i_banca < i_grupo


def test_indice_raiz_acumula_concursos():
    """Deploy incremental: publicar o 2º concurso não some com o 1º do índice."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "site"
        b1 = _montar_concurso(Path(d) / "AAA_2026")
        _construir(b1, out)
        b2 = _montar_concurso(Path(d) / "BBB_2027")
        r = _construir(b2, out)
        assert r["concursos_no_indice"] == 2
        raiz = (out / "index.html").read_text(encoding="utf-8")
        assert "aaa_2026/index.html" in raiz and "bbb_2027/index.html" in raiz


def test_downloads_e_tema_presentes():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026", com_midias=True)
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_assunto(out, "teste_2026", "crase") / "index.html").read_text(encoding="utf-8")
        assert 'class="baixar"' in h and 'download="podcast-crase.m4a"' in h
        assert "tema-troca" in h           # botão de tema
        assert "data-tema" in h            # script anti-flash



def test_css_sem_cor_fixa_em_texto_fora_das_variaveis():
    """Regressão: cores de TEXTO fixas (hex) fora dos blocos :root quebram o tema
    escuro — foi o que aconteceu com `strong { color: #101425 }`."""
    css = (ROOT.parent / "assets" / "site.css").read_text(encoding="utf-8")
    # remover os blocos de variáveis (lá o hex é legítimo)
    sem_root = re.sub(r":root(\[data-tema=\"escuro\"\])?\s*\{.*?\n\}", "", css, flags=re.DOTALL)
    # procurar `color: #xxx` (não background-color) fora deles
    ofensores = []
    for m in re.finditer(r"(?<!-)\bcolor:\s*(#[0-9A-Fa-f]{3,8})", sem_root):
        trecho = sem_root[max(0, m.start() - 90):m.start()]
        # #fff sobre superfícies fixas escuras (pre, lightbox) é aceitável
        if any(t in trecho for t in ("pre ", "pre{", ".lightbox", ".topo", ".tema-troca")):
            continue
        ofensores.append(m.group(1))
    assert not ofensores, f"cor de texto fixa fora das variáveis de tema: {ofensores}"


def test_variaveis_de_tema_definidas_nos_dois_temas():
    css = (ROOT.parent / "assets" / "site.css").read_text(encoding="utf-8")
    claro = re.search(r":root\s*\{(.*?)\n\}", css, re.DOTALL).group(1)
    escuro = re.search(r':root\[data-tema="escuro"\]\s*\{(.*?)\n\}', css, re.DOTALL).group(1)
    for var in ("--forte", "--sobre-tinta", "--superficie", "--papel", "--grafite"):
        assert var in claro, f"{var} ausente no tema claro"
        assert var in escuro, f"{var} ausente no tema escuro"



# --------------------------------------------------------------------------- #
# múltiplos aprofundamentos por assunto e agrupamento por órgão
# --------------------------------------------------------------------------- #
def _add_aprof(base: Path, assunto: str, ident: str, nivel: str, fontes: str):
    d = (_mat_vault(base) / "assuntos"
         / assunto / "aprofundamentos" / ident)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{assunto}--{ident}.md").write_text(
        f'---\ntitle: "{assunto.title()}"\naprofundamento: "{ident}"\n'
        f'nivel: {nivel}\nfontes: "{fontes}"\nstatus: concluido\n---\nTexto.\n',
        encoding="utf-8")
    return d


def test_varios_aprofundamentos_por_assunto():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        _add_aprof(base, "crase", "pestana--padrao", "padrao", "Pestana")
        _add_aprof(base, "crase", "damasceno--detalhado", "detalhado", "Damasceno")
        m = _rodar(base)
        a = next(x for x in _materias(m)[0]["assuntos"] if x["slug"] == "crase")
        # 2 novos + o legado que já existia na fixture
        assert a["n_aprofundamentos"] == 3
        assert set(a["niveis"]) == {"padrao", "detalhado"}
        # detalhado vem primeiro (é o principal)
        assert a["aprofundamentos"][0]["nivel"] == "detalhado"


def test_legado_continua_funcionando_sozinho():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        m = _rodar(base)
        a = next(x for x in _materias(m)[0]["assuntos"] if x["slug"] == "crase")
        assert a["n_aprofundamentos"] == 1
        assert a["aprofundamentos"][0]["aprofundamento"] == "unico"


def test_site_gera_seletor_quando_ha_varios():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        _add_aprof(base, "crase", "pestana--padrao", "padrao", "Pestana")
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_assunto(out, "teste_2026", "crase") / "index.html").read_text(encoding="utf-8")
        assert "seletor-aprof" in h
        assert 'data-alvo="pestana--padrao"' in h
        assert h.count('class="aprof') >= 2      # blocos de conteúdo separados
        # assunto com um só aprofundamento não ganha seletor
        h2 = (_dir_assunto(out, "teste_2026", "regencia-verbal-e-nominal") / "index.html").read_text(encoding="utf-8")
        assert "seletor-aprof" not in h2


def test_midias_de_aprofundamentos_nao_colidem():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        d1 = _add_aprof(base, "crase", "aaa--padrao", "padrao", "A")
        d2 = _add_aprof(base, "crase", "bbb--detalhado", "detalhado", "B")
        (d1 / "podcast-crase--aaa--padrao.m4a").write_bytes(b"1")
        (d2 / "podcast-crase--bbb--detalhado.m4a").write_bytes(b"2")
        out = Path(d) / "site"
        _construir(base, out)
        media = (_dir_assunto(out, "teste_2026", "crase") / "media")
        assert (media / "aaa--padrao").is_dir()
        assert (media / "bbb--detalhado").is_dir()


def test_indice_raiz_agrupa_por_orgao():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "site"
        for nome, orgao in (("SEDES_2026", "SEDES"), ("SEDES_2028", "SEDES"),
                            ("BB_2027", "BB")):
            base = _montar_concurso(Path(d) / nome)
            # o órgão vem do .meta.json (tem precedência sobre o nome da pasta)
            (base / ".meta.json").write_text(
                json.dumps({"orgao": orgao, "ano": 2026, "banca": "X"}), encoding="utf-8")
            _construir(base, out)
        raiz = (out / "index.html").read_text(encoding="utf-8")
        assert "grupo-orgao" in raiz
        assert "<h2>SEDES</h2>" in raiz and "<h2>BB</h2>" in raiz
        # SEDES tem 2 concursos no mesmo grupo
        assert "2 concursos" in raiz



def test_selos_de_aprofundamento_sinalizam_fontes_e_niveis():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        _add_aprof(base, "crase", "pestana--padrao", "padrao", "Pestana")
        _add_aprof(base, "crase", "damasceno--detalhado", "detalhado", "Damasceno")
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_assunto(out, "teste_2026", "crase") / "index.html").read_text(encoding="utf-8")
        assert "selos-aprof" in h
        assert "2 fontes" in h                      # duas fontes distintas
        assert "Padrão + Detalhado" in h            # ambos os níveis
        assert "nivel-ambos" in h
        # a bolha (assinatura visual) é usada para indicar profundidade
        assert 'class="bolha meia"' in h and 'class="bolha cheia"' in h

        # assunto com um só nível mostra só ele
        h2 = (_dir_assunto(out, "teste_2026", "regencia-verbal-e-nominal") / "index.html").read_text(encoding="utf-8")
        assert "Padrão + Detalhado" not in h2



def test_frontmatter_ignora_comentario_inline_do_yaml():
    """Regressão: 'nivel: padrao   # padrao | detalhado' era lido com o comentário
    junto, quebrando a comparação de níveis e os selos."""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "a.md"
        f.write_text('---\nnivel: padrao   # padrao | detalhado\n'
                     'prioridade: alta  # alta | media | base\n'
                     'url: "https://x.com/a#frag"\n---\ncorpo\n', encoding="utf-8")
        fm = sc.ler_frontmatter(f)
        assert fm["nivel"] == "padrao"
        assert fm["prioridade"] == "alta"
        assert fm["url"] == "https://x.com/a#frag"   # '#' em valor citado é preservado


def test_niveis_distintos_geram_selo_combinado():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        _add_aprof(base, "crase", "aaa--padrao", "padrao", "Fonte A")
        _add_aprof(base, "crase", "bbb--detalhado", "detalhado", "Fonte B")
        out = Path(d) / "site"
        _construir(base, out)
        h = (_dir_assunto(out, "teste_2026", "crase") / "index.html").read_text(encoding="utf-8")
        assert "Padrão + Detalhado" in h
        assert "2 fontes" in h


# --------------------------------------------------------------------------- #
# padrão de pastas atual: {assunto}/{nivel}--{N}f--f1-{fonte}/
# --------------------------------------------------------------------------- #
def _assunto_do_modelo(m, slug):
    return next(x for x in _materias(m)[0]["assuntos"] if x["slug"] == slug)


def _add_aprof_atual(base: Path, assunto: str, ident: str, fontes: str = ""):
    """Cria um aprofundamento no padrão ATUAL (sem o nível 'aprofundamentos/')."""
    d = (_mat_vault(base) / "assuntos"
         / assunto / ident)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{assunto}--{ident}.md").write_text(
        f'---\ntitle: "{assunto.title()}"\nstatus: concluido\n'
        f'fontes: "{fontes}"\n---\nTexto.\n', encoding="utf-8")
    return d


def test_coleta_no_padrao_de_pastas_atual():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        _add_aprof_atual(base, "crase", "detalhado--1f--f1-pestana")
        _add_aprof_atual(base, "crase", "padrao--1f--f1-pestana")
        a = _assunto_do_modelo(_rodar(base), "crase")
        assert a["n_aprofundamentos"] == 3, a["n_aprofundamentos"]   # 2 novos + legado da fixture
        # detalhado vem primeiro (ordenação por nível)
        assert a["aprofundamentos"][0]["nivel"] == "detalhado"
        assert a["aprofundamentos"][1]["nivel"] == "padrao"


def test_nivel_vem_da_pasta_mesmo_sem_frontmatter():
    """A pasta é a fonte da identidade: material antigo pode não ter 'nivel:'."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        _add_aprof_atual(base, "crase", "detalhado--2f--f1-pestana--f2-abreu")
        a = _assunto_do_modelo(_rodar(base), "crase")
        ap = a["aprofundamentos"][0]
        assert ap["nivel"] == "detalhado"
        assert ap["n_fontes_id"] == 2
        assert ap["fontes_id"] == ["pestana", "abreu"]


def test_layouts_antigo_e_atual_convivem():
    """Quem não migrou o vault não pode ficar sem site."""
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        _add_aprof_atual(base, "crase", "detalhado--1f--f1-pestana")
        _add_aprof(base, "crase", "abreu--padrao", "padrao", "Abreu")   # layout 0.2.x
        a = _assunto_do_modelo(_rodar(base), "crase")
        assert a["n_aprofundamentos"] == 3   # atual + 0.2.x + legado da fixture


def test_pasta_que_nao_e_aprofundamento_e_ignorada():
    with tempfile.TemporaryDirectory() as d:
        base = _montar_concurso(Path(d) / "TESTE_2026")
        _add_aprof_atual(base, "crase", "padrao--1f--f1-pestana")
        lixo = (_mat_vault(base) / "assuntos"
                / "crase" / "anotacoes-soltas")
        lixo.mkdir(parents=True, exist_ok=True)
        (lixo / "rascunho.md").write_text("---\ntitle: x\n---\nnada\n", encoding="utf-8")
        a = _assunto_do_modelo(_rodar(base), "crase")
        assert a["n_aprofundamentos"] == 2   # o aprofundamento + o legado; a pasta solta é ignorada


def test_copia_do_aprofundamento_id_nao_divergiu():
    """A convenção é compartilhada por cópia entre as duas skills; se divergir,
    o site passa a ler uma estrutura diferente da que a outra skill escreve."""
    aqui = Path(__file__).resolve().parents[1] / "aprofundamento_id.py"
    # parents: [0]=tests [1]=scripts [2]=concurso-publica [3]=skills [4]=repo.
    # Instalada isoladamente (~/.claude/skills/), o irmão fica em [3]; no repo,
    # em [3] também ("skills/"). Procura nos dois e só pula se realmente não houver.
    aqui_ = Path(__file__).resolve()
    candidatos = [aqui_.parents[3] / "concurso-aprofunda" / "scripts" / "aprofundamento_id.py",
                  aqui_.parents[4] / "skills" / "concurso-aprofunda" / "scripts" / "aprofundamento_id.py"]
    fonte = next((c for c in candidatos if c.exists()), None)
    if fonte is None:
        return                      # skill instalada sem a irmã: nada a comparar
    def corpo(p):
        txt = p.read_text(encoding="utf-8")
        i = txt.find("NIVEIS = ")
        return txt[i:]
    assert corpo(aqui) == corpo(fonte), (
        "aprofundamento_id.py divergiu entre concurso-aprofunda e concurso-publica; "
        "edite o original e copie por cima")


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    falhas = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            falhas += 1
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            falhas += 1
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - falhas}/{len(fns)} testes passaram.")
    return falhas


if __name__ == "__main__":
    sys.exit(1 if _run_standalone() else 0)
