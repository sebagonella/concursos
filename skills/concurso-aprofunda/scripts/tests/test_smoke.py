#!/usr/bin/env python3
"""
test_smoke.py - Smoke tests da skill concurso-aprofunda (Subsistemas A + B + flashcards).

Roda com pytest ou standalone:
    python scripts/tests/test_smoke.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import textmatch as tm  # noqa: E402


# ------------------------- textmatch ------------------------- #
def test_normalizar_remove_acento():
    assert tm.normalizar("Concordância Verbal") == "concordancia verbal"


def test_score_match_alto_para_titulo_igual():
    assert tm.score_match("Crase", "Crase") >= 0.99


def test_score_match_parcial():
    s = tm.score_match("Regência verbal", "Regência Verbal e Nominal")
    assert 0.6 <= s <= 1.0


def test_densidade_detecta_pagina_relevante():
    termos = tm.tokens_significativos("concordância verbal sujeito")
    pagina_rel = "O verbo concorda com o sujeito. Concordância verbal é regra."
    pagina_irr = "A crase é a fusão de duas vogais idênticas."
    assert tm.densidade_termos(pagina_rel, termos) > tm.densidade_termos(pagina_irr, termos)


# ------------------------- book_index ------------------------- #
def _make_book(path: Path):
    """Cria um TXT com form-feeds simulando páginas + sumário."""
    paginas = [
        "SUMARIO\nConcordancia Verbal ........ 3\nCrase ........ 5\n",   # p1
        "Prefacio do livro.",                                            # p2
        "Concordancia Verbal\nO verbo concorda com o sujeito em numero.", # p3
        "Casos especiais de concordancia verbal.",                       # p4
        "Crase\nCrase e a fusao da preposicao a com artigo.",            # p5
        "Casos de crase facultativa.",                                   # p6
    ]
    path.write_text("\f".join(paginas), encoding="utf-8")


def test_book_index_localiza_por_toc():
    with tempfile.TemporaryDirectory() as d:
        livro = Path(d) / "livro.txt"
        _make_book(livro)
        assuntos = Path(d) / "a.json"
        assuntos.write_text(json.dumps({
            "materia": "Português", "assuntos": ["Concordância verbal", "Crase"]
        }), encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(ROOT / "book_index.py"),
             "--livro", str(livro), "--assuntos", str(assuntos), "--json"],
            capture_output=True, text=True)
        out = json.loads(r.stdout)
        cv = out["localizacoes"]["Concordância verbal"]
        assert cv["metodo"] == "toc"
        assert cv["paginas"][0] == 3


def test_book_index_nao_encontrado_vira_pendencia():
    with tempfile.TemporaryDirectory() as d:
        livro = Path(d) / "livro.txt"
        _make_book(livro)
        assuntos = Path(d) / "a.json"
        assuntos.write_text(json.dumps({
            "materia": "Português", "assuntos": ["Tópico Inexistente XYZ"]
        }), encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(ROOT / "book_index.py"),
             "--livro", str(livro), "--assuntos", str(assuntos), "--json"],
            capture_output=True, text=True)
        out = json.loads(r.stdout)
        assert out["localizacoes"]["Tópico Inexistente XYZ"]["confianca"] == "nao_encontrado"
        assert any("NÃO LOCALIZADO" in p for p in out["pendencias"])


# ------------------------- build_subject_md ------------------------- #
def test_build_subject_gera_md_com_ponteiro():
    with tempfile.TemporaryDirectory() as d:
        mapa = Path(d) / "mapa.json"
        mapa.write_text(json.dumps({
            "livro": "livro.pdf", "materia": "Português",
            "localizacoes": {"Crase": {"paginas": [5, 6], "confianca": "alta", "metodo": "toc"}},
        }), encoding="utf-8")
        out = Path(d) / "assuntos"
        r = subprocess.run(
            [sys.executable, str(ROOT / "build_subject_md.py"),
             "--mapa", str(mapa), "--out-dir", str(out), "--concurso", "X_2026",
             "--legado-plano"],
            capture_output=True, text=True)
        assert r.returncode == 0
        md = (out / "crase" / "crase.md").read_text(encoding="utf-8")
        assert "páginas **5–6**" in md
        assert "{RESUMO}" in md  # placeholder para o agente preencher


# ------------------------- flashcards_gen ------------------------- #
def test_flashcards_descarta_invalidos_e_duplicados():
    with tempfile.TemporaryDirectory() as d:
        cards = Path(d) / "c.json"
        cards.write_text(json.dumps({
            "assunto": "Crase", "materia": "Português",
            "cards": [
                {"front": "O que é crase?", "back": "Fusão de a+a.", "tag": "def"},
                {"front": "", "back": "vazio", "tag": ""},
                {"front": "O que é crase?", "back": "duplicado", "tag": ""},
            ],
        }), encoding="utf-8")
        out = Path(d) / "cr"
        r = subprocess.run(
            [sys.executable, str(ROOT / "flashcards_gen.py"),
             "--cards", str(cards), "--out-dir", str(out)],
            capture_output=True, text=True)
        res = json.loads(r.stdout)
        assert res["cards_validos"] == 1
        assert res["cards_descartados"] == 2
        md = (out / "flashcards-crase.md").read_text(encoding="utf-8")
        assert "\n??\n" in md  # ?? em linha própria (formato multiline correto)
        assert (out / "flashcards-crase.md").exists()
        assert (out / "flashcards-crase.csv").exists()


def test_build_subject_usa_paginas_relevantes_quando_embutido():
    """Assunto de confiança média com paginas_relevantes deve usar as específicas."""
    with tempfile.TemporaryDirectory() as d:
        mapa = Path(d) / "mapa.json"
        mapa.write_text(json.dumps({
            "livro": "l.pdf", "materia": "P",
            "localizacoes": {"Gêneros": {"paginas": [100, 200], "confianca": "media",
                                          "metodo": "toc", "paginas_relevantes": [110, 130]}},
        }), encoding="utf-8")
        out = Path(d) / "a"
        subprocess.run([sys.executable, str(ROOT / "build_subject_md.py"),
                        "--mapa", str(mapa), "--out-dir", str(out), "--legado-plano"],
                       capture_output=True, text=True)
        md = (out / "generos" / "generos.md").read_text(encoding="utf-8")
        assert "110" in md and "130" in md  # usou as relevantes


def test_book_coverage_detecta_gaps():
    with tempfile.TemporaryDirectory() as d:
        mapa = Path(d) / "mapa.json"
        mapa.write_text(json.dumps({
            "livro": "l.pdf", "materia": "P", "total_paginas": 1000,
            "localizacoes": {
                "A": {"paginas": [100, 200], "confianca": "alta"},
                "B": {"paginas": [800, 900], "confianca": "alta"},
            },
        }), encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "book_coverage.py"),
                            "--mapa", str(mapa), "--min-gap", "30"],
                           capture_output=True, text=True)
        # gap pré-textual (1-99), gap 201-799, e final 901-1000
        assert "201" in r.stdout and "799" in r.stdout


def test_reuse_finder_acha_aproveitavel_e_ignora_arcabouco():
    with tempfile.TemporaryDirectory() as d:
        conc = Path(d) / "CONCURSOS"
        # SEDES tem crase preenchida (aproveitável) e pontuacao só arcabouço
        base = conc / "SEDES_2026" / "C" / "03-MAPAS-MATERIAS" / "port" / "assuntos"
        (base / "crase").mkdir(parents=True)
        (base / "crase" / "crase.md").write_text(
            '---\ntitle: "Crase"\nlocalizacao_livro: "Pestana.pdf — págs. 1018–1045"\n'
            'status: concluido\n---\nConteúdo real preenchido sobre crase.\n', encoding="utf-8")
        (base / "pontuacao").mkdir(parents=True)
        (base / "pontuacao" / "pontuacao.md").write_text(
            '---\ntitle: "Pontuação"\nlocalizacao_livro: "Pestana.pdf — págs. 890–929"\n'
            'status: nao-iniciado\n---\n{RESUMO_COMPLETO}\n', encoding="utf-8")
        assuntos = Path(d) / "a.json"
        assuntos.write_text(json.dumps({"assuntos": ["Crase", "Pontuação", "Regência"]}),
                            encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "reuse_finder.py"),
                            "--vault-concursos", str(conc), "--livro", "Pestana.pdf",
                            "--assuntos", str(assuntos), "--concurso-atual", "TJDFT_2027"],
                           capture_output=True, text=True)
        out = json.loads(r.stdout)
        assert "Crase" in out["reaproveitaveis"]          # preenchida -> aproveita
        assert "Pontuação" in out["sem_fonte"]            # arcabouço -> não aproveita
        assert "Regência" in out["sem_fonte"]             # inexistente -> não aproveita


def test_notebooklm_pack_gera_pacote_por_assunto():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "assuntos" / "crase"
        base.mkdir(parents=True)
        (base / "crase.md").write_text(
            '---\ntitle: "Crase"\nmateria: "Português"\n'
            'localizacao_livro: "Pestana.pdf — págs. 1018–1045"\nstatus: concluido\n---\n'
            'Resumo real da crase, sem placeholders.\n', encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "notebooklm_pack.py"),
                            "--assuntos-dir", str(Path(d) / "assuntos"),
                            "--concurso", "SEDES_2026", "--materia", "Português"],
                           capture_output=True, text=True)
        out = json.loads(r.stdout)
        assert out["gerados"] == 1
        pack = (base / "_fonte-notebooklm.md").read_text(encoding="utf-8")
        assert "SEDES_2026 — Crase" in pack       # nome do notebook
        assert "Audio Overview" in pack            # roteiro do podcast
        assert "Foque em Crase" in pack
        assert "podcast-crase.m4a" in pack   # extensao correta
        assert "[[mapa-mental-crase.png]]" in pack  # nota de links
        assert "Construa o mapa mental" in pack  # prompt de mindmap fino            # prompt específico


def test_notebooklm_pack_pula_arcabouco():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "assuntos" / "vazio"
        base.mkdir(parents=True)
        (base / "vazio.md").write_text(
            '---\ntitle: "Vazio"\nstatus: nao-iniciado\n---\n{RESUMO_COMPLETO}\n',
            encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "notebooklm_pack.py"),
                            "--assuntos-dir", str(Path(d) / "assuntos")],
                           capture_output=True, text=True)
        out = json.loads(r.stdout)
        assert out["gerados"] == 0
        assert any("vazio" in x for x in out["pulados_sem_preenchimento"])


def test_fix_notebooklm_preserva_e_atualiza():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "assuntos" / "crase"
        base.mkdir(parents=True)
        # resumo com "progresso" do usuário
        (base / "crase.md").write_text(
            '---\ntitle: "Crase"\nmateria: "Português"\nstatus: concluido\n---\n'
            'Resumo real.\n<!-- MEU PROGRESSO -->\n', encoding="utf-8")
        # pack antigo com .mp3 e link preenchido
        (base / "_fonte-notebooklm.md").write_text(
            "# antigo\npodcast-crase.mp3\n[[podcast-crase.mp3]]\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "fix_notebooklm_packs.py"),
                            "--assuntos-dir", str(Path(d) / "assuntos"),
                            "--concurso", "BB_2027_PREVISTO", "--materia", "Português"],
                           capture_output=True, text=True)
        assert r.returncode == 0
        # backup criado, progresso preservado, pack novo com .m4a
        assert (base / "_fonte-notebooklm.bak.md").exists()
        assert "MEU PROGRESSO" in (base / "crase.md").read_text(encoding="utf-8")
        novo = (base / "_fonte-notebooklm.md").read_text(encoding="utf-8")
        assert "podcast-crase.m4a" in novo
        assert "BB_2027_PREVISTO" in novo



def test_niveis_geram_templates_diferentes():
    """padrao e detalhado devem produzir estruturas de seções distintas."""
    with tempfile.TemporaryDirectory() as d:
        mapa = Path(d) / "m.json"
        mapa.write_text(json.dumps({
            "livro": "L.pdf", "materia": "P",
            "localizacoes": {"Crase": {"paginas": [1, 9], "confianca": "alta", "metodo": "toc"}},
        }), encoding="utf-8")
        out = Path(d) / "assuntos"
        for nivel, fonte in (("padrao", "Livro A (Alfa)"), ("detalhado", "Livro B (Beta)")):
            r = subprocess.run([sys.executable, str(ROOT / "build_subject_md.py"),
                                "--mapa", str(mapa), "--out-dir", str(out),
                                "--fontes", fonte, "--nivel", nivel],
                               capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
        base = out / "crase"
        assert (base / "padrao--alfa").is_dir()
        assert (base / "detalhado--beta").is_dir()
        det = next((base / "detalhado--beta").glob("crase*.md")).read_text(encoding="utf-8")
        pad = next((base / "padrao--alfa").glob("crase*.md")).read_text(encoding="utf-8")
        # só o detalhado tem as seções aprofundadas
        for secao in ("Exemplos resolvidos", "Questões comentadas", "Divergências"):
            assert secao in det, secao
            assert secao not in pad, secao
        assert "nivel: detalhado" in det and "nivel: padrao" in pad


def test_varias_fontes_numa_execucao_geram_um_aprofundamento():
    with tempfile.TemporaryDirectory() as d:
        mapa = Path(d) / "m.json"
        mapa.write_text(json.dumps({
            "livro": "L.pdf", "materia": "P",
            "localizacoes": {"Crase": {"paginas": [1, 9], "confianca": "alta", "metodo": "toc"}},
        }), encoding="utf-8")
        out = Path(d) / "assuntos"
        r = subprocess.run([sys.executable, str(ROOT / "build_subject_md.py"),
                            "--mapa", str(mapa), "--out-dir", str(out),
                            "--fontes", "Livro A (Alfa),Livro B (Beta)", "--nivel", "detalhado"],
                           capture_output=True, text=True)
        rel = json.loads(r.stdout)
        assert rel["aprofundamento"] == "detalhado--alfa+beta"
        assert len(rel["fontes"]) == 2
        assert (out / "crase" / "detalhado--alfa+beta").is_dir()


def test_notebooklm_pack_gera_um_por_aprofundamento():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "assuntos" / "crase" / "aprofundamentos"
        for ident, nivel in (("alfa--padrao", "padrao"), ("beta--detalhado", "detalhado")):
            p = base / ident
            p.mkdir(parents=True)
            (p / f"crase--{ident}.md").write_text(
                f'---\ntitle: "Crase"\naprofundamento: "{ident}"\nnivel: {nivel}\n'
                f'fontes: "Fonte X"\nstatus: concluido\n---\nConteúdo real.\n',
                encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "notebooklm_pack.py"),
                            "--assuntos-dir", str(Path(d) / "assuntos"),
                            "--concurso", "X_2026", "--materia", "P"],
                           capture_output=True, text=True)
        out = json.loads(r.stdout)
        assert out["gerados"] == 2, out
        # o prompt do detalhado é diferente do padrão
        det = (base / "beta--detalhado" / "_fonte-notebooklm.md").read_text(encoding="utf-8")
        pad = (base / "alfa--padrao" / "_fonte-notebooklm.md").read_text(encoding="utf-8")
        assert "APROFUNDADO" in det and "APROFUNDADO" not in pad


# ---------------- convenção de aprofundamento (aprofundamento_id) ---------------- #
import aprofundamento_id as aid  # noqa: E402


def test_id_aprofundamento_uma_fonte():
    assert aid.id_aprofundamento(["A Gramática para Concursos (Pestana)"],
                                 "padrao") == "padrao--pestana"


def test_id_aprofundamento_varias_fontes_numera_na_ordem():
    got = aid.id_aprofundamento(["Lei nº 12.846/2013", "Decreto nº 11.129/2022"], "padrao")
    assert got == "padrao--lei-12846+dec-11129"


def test_id_aprofundamento_rejeita_nivel_invalido():
    try:
        aid.id_aprofundamento(["x"], "profundo")
    except ValueError:
        return
    raise AssertionError("nível inválido deveria levantar ValueError")


def test_slug_fonte_livro_usa_autor():
    assert aid.slug_fonte("A-Gramatica-para-Concursos-Fernando-Pestana.pdf") == "pestana"


def test_slug_fonte_ignora_ano_e_edicao():
    # o último token do nome é '2012'; ano/edição nunca identificam a fonte
    assert aid.slug_fonte("Administracao-de-Marketing-Kotler-e-Keller-14ed-2012.pdf") == "keller"


def test_slug_fonte_normas():
    assert aid.slug_fonte("Lei nº 8.742/1993") == "lei-8742"
    assert aid.slug_fonte("Lei Complementar nº 105/2001") == "lc-105"
    assert aid.slug_fonte("Lei Distrital 6.938/2021") == "leidf-6938"
    assert aid.slug_fonte("Decreto nº 7.053/2009") == "dec-7053"
    assert aid.slug_fonte("Resolução CMN nº 4.893/2021") == "res-cmn-4893"
    assert aid.slug_fonte("Res. Conjunta CNAS/CONANDA nº 1/2009") == "res-conj-cnas-conanda-1"


def test_slug_fonte_norma_dentro_de_parenteses():
    assert aid.slug_fonte("PRSAC do BB (Resolução CMN nº 4.945/2021)") == "res-cmn-4945"


def test_override_de_slug_vence_a_derivacao():
    got = aid.id_aprofundamento(["qualquer coisa"], "detalhado", fontes_slug=["kotler"])
    assert got == "detalhado--kotler"


def test_parse_id_ida_e_volta():
    ident = aid.id_aprofundamento(["Lei nº 7.716/1989", "STF ADO 26"], "detalhado")
    info = aid.parse_id(ident)
    assert info["nivel"] == "detalhado"
    assert info["n_fontes"] == 2
    assert info["fontes"] == ["lei-7716", "stf-ado-26"]


def test_parse_id_recusa_pasta_que_nao_e_aprofundamento():
    for nome in ("aprofundamentos", "cards.json", "crase", "pestana--padrao"):
        assert aid.parse_id(nome) is None
        assert not aid.eh_pasta_aprofundamento(nome)


def test_nome_base_espelha_a_pasta():
    ident = "padrao--pestana"
    assert aid.nome_base("crase", ident) == "crase--padrao--pestana"
    assert (aid.nome_base("crase", ident, "SEDES_2026")
            == "crase--padrao--pestana--SEDES_2026")


def test_slug_suspeito_pega_ano_e_vazio():
    assert aid.slug_suspeito("2012")
    assert aid.slug_suspeito("")
    assert aid.slug_suspeito("fonte")
    assert not aid.slug_suspeito("pestana")


# ---------------- flashcards: nome de arquivo casa com o wikilink ---------------- #
def test_flashcards_usam_nome_base_do_aprofundamento():
    """Regressão: flashcards_gen gerava 'flashcards-{assunto}.md' enquanto o
    build_subject_md apontava o wikilink para 'flashcards-{assunto}--{id}'.
    Resultado: link quebrado e dois arquivos homônimos no vault."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        cards = d / "cards.json"
        cards.write_text(json.dumps({
            "assunto": "Crase", "materia": "Português",
            "cards": [{"front": "P?", "back": "R.", "tag": "conceito"}],
        }), encoding="utf-8")
        out = subprocess.run(
            [sys.executable, str(ROOT / "flashcards_gen.py"), "--cards", str(cards),
             "--out-dir", str(d / "ap"), "--aprofundamento", "detalhado--pestana",
             "--concurso", "SEDES_2026"],
            capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        gerados = {Path(p).name for p in json.loads(out.stdout)["gerados"]}
        assert "flashcards-crase--detalhado--pestana--SEDES_2026.md" in gerados
        assert "flashcards-crase--detalhado--pestana--SEDES_2026.csv" in gerados


def test_flashcards_sem_aprofundamento_mantem_nome_legado():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        cards = d / "cards.json"
        cards.write_text(json.dumps({
            "assunto": "Crase", "cards": [{"front": "P?", "back": "R.", "tag": "t"}],
        }), encoding="utf-8")
        out = subprocess.run(
            [sys.executable, str(ROOT / "flashcards_gen.py"), "--cards", str(cards),
             "--out-dir", str(d / "ap")], capture_output=True, text=True)
        gerados = {Path(p).name for p in json.loads(out.stdout)["gerados"]}
        assert "flashcards-crase.md" in gerados


def test_build_subject_md_gera_pasta_no_padrao_atual():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        mapa = d / "mapa.json"
        mapa.write_text(json.dumps({
            "materia": "Português", "livro": "L.pdf",
            "localizacoes": {"Crase": {"paginas": [10, 20], "confianca": "alta",
                                       "metodo": "toc"}},
        }), encoding="utf-8")
        out = subprocess.run(
            [sys.executable, str(ROOT / "build_subject_md.py"), "--mapa", str(mapa),
             "--out-dir", str(d / "assuntos"), "--nivel", "detalhado",
             "--concurso", "SEDES_2026",
             "--fontes", "A Gramática (Pestana)"], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        alvo = (d / "assuntos" / "crase" / "detalhado--pestana"
                / "crase--detalhado--pestana--SEDES_2026.md")
        assert alvo.exists(), f"não gerou no padrão atual: {list((d/'assuntos').rglob('*'))}"
        # não deve mais existir o nível intermediário 'aprofundamentos/'
        assert not (d / "assuntos" / "crase" / "aprofundamentos").exists()


def test_build_subject_md_avisa_quando_slug_da_fonte_e_ruim():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        mapa = d / "mapa.json"
        mapa.write_text(json.dumps({
            "materia": "M", "livro": "2012.pdf",
            "localizacoes": {"X": {"paginas": [1, 2], "confianca": "alta"}},
        }), encoding="utf-8")
        out = subprocess.run(
            [sys.executable, str(ROOT / "build_subject_md.py"), "--mapa", str(mapa),
             "--out-dir", str(d / "a"), "--fontes", "2012.pdf"],
            capture_output=True, text=True)
        assert json.loads(out.stdout)["avisos"], "deveria avisar sobre slug suspeito"


def test_parse_id_ainda_le_o_formato_anterior():
    """Vault não migrado não pode ficar ilegível para o site."""
    info = aid.parse_id("detalhado--2f--f1-lei-7716--f2-stf-ado-26")
    assert info["nivel"] == "detalhado"
    assert info["fontes"] == ["lei-7716", "stf-ado-26"]
    assert info["formato"] == "0.3"


def test_nome_base_com_concurso_e_unico_entre_concursos():
    """O Obsidian resolve wikilink por nome: dois concursos com o mesmo livro
    e o mesmo assunto não podem gerar arquivos homônimos."""
    ident = aid.id_aprofundamento(["A Gramática (Pestana)"], "padrao")
    a = aid.nome_base("crase", ident, "SEDES_2026")
    b = aid.nome_base("crase", ident, "BB_2027_PREVISTO")
    assert a != b


def test_id_nao_carrega_informacao_redundante():
    """Contador de fontes e índice posicional não diferenciam nada — não entram."""
    ident = aid.id_aprofundamento(["Lei nº 1/2020", "Lei nº 2/2020"], "padrao")
    assert "2f" not in ident and "f1-" not in ident and "f2-" not in ident


def test_migrador_recusa_pasta_com_dois_md_principais():
    """Regressão: pasta com arcabouço órfão + conteúdo preenchido fazia o migrador
    escolher o primeiro em ordem alfabética, trocando conteúdo por arcabouço."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        pasta = d / "CONCURSOS" / "X_2026" / "m" / "assuntos" / "crase" / "padrao--1f--f1-pestana"
        pasta.mkdir(parents=True)
        fm = ('---\ntitle: "Crase"\nconcurso: "X_2026"\n'
              'localizacao_livro: "L.pdf — págs. 1–9"\nstatus: revisar\n---\n')
        (pasta / "crase--padrao--1f--f1-pestana.md").write_text(fm + "conteudo real\n",
                                                               encoding="utf-8")
        (pasta / "crase--padrao--pestana--X_2026.md").write_text(fm + "{DESENVOLVIMENTO}\n",
                                                                 encoding="utf-8")
        out = subprocess.run(
            [sys.executable, str(ROOT / "migrar_aprofundamentos.py"),
             "--raiz", str(d / "CONCURSOS"), "--dry-run"],
            capture_output=True, text=True)
        rel = json.loads(out.stdout)
        assert rel["resumo"].get("PENDENCIA"), "deveria recusar a pasta ambígua"
        motivos = " ".join(m for i in rel["itens"] for m in i.get("motivos", []))
        assert "mais de um .md principal" in motivos, motivos


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
