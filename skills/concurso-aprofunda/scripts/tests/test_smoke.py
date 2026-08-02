#!/usr/bin/env python3
"""
test_smoke.py - Smoke tests da skill concurso-aprofunda (Subsistemas A + B + flashcards).

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


def test_pack_emite_notebooklm_url_para_o_site_ler():
    """A `concurso-publica` só mostra o botão "Abrir no NotebookLM" se
    `notebooklm_url:` estiver preenchida no pack. O template nunca emitia a chave, o
    que deixava o botão inalcançável em 100% dos casos — não havia como o usuário
    preencher um campo que não existia."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "assuntos" / "crase"
        base.mkdir(parents=True)
        (base / "crase.md").write_text(
            '---\ntitle: "Crase"\nmateria: "Português"\n---\nResumo real.\n',
            encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "notebooklm_pack.py"),
                        "--assuntos-dir", str(Path(d) / "assuntos"),
                        "--concurso", "SEDES_2026", "--materia", "Português"],
                       capture_output=True, text=True)
        pack = (base / "_fonte-notebooklm.md").read_text(encoding="utf-8")
        assert 'notebooklm_url: ""' in pack
        assert "notebooklm_status: nao-criado" in pack


def test_regerar_pack_nao_apaga_o_link_digitado_a_mao():
    """Regressão do risco que acompanha a chave nova: `notebooklm_pack.py` reescreve
    o pack sempre que o conteúdo muda, e acrescentar a chave ao template faz TODO
    pack existente contar como mudado. Sem herdar o valor, a URL que o usuário
    digitou iria para o `.bak.md` e o botão desapareceria do site sem erro — a única
    informação do pacote que não é regerável."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "assuntos" / "crase"
        base.mkdir(parents=True)
        (base / "crase.md").write_text(
            '---\ntitle: "Crase"\nmateria: "Português"\n---\nResumo real.\n',
            encoding="utf-8")
        args = [sys.executable, str(ROOT / "notebooklm_pack.py"),
                "--assuntos-dir", str(Path(d) / "assuntos"),
                "--concurso", "SEDES_2026", "--materia", "Português"]
        subprocess.run(args, capture_output=True, text=True)

        # o usuário cria o notebook e cola o link, e marca o status
        pack_f = base / "_fonte-notebooklm.md"
        txt = pack_f.read_text(encoding="utf-8")
        txt = txt.replace('notebooklm_url: ""',
                          'notebooklm_url: "https://notebooklm.google.com/notebook/abc"')
        txt = txt.replace("notebooklm_status: nao-criado", "notebooklm_status: criado")
        pack_f.write_text(txt, encoding="utf-8")

        # o resumo muda e o pacote é regerado
        (base / "crase.md").write_text(
            '---\ntitle: "Crase"\nmateria: "Português"\n---\nOutro resumo, revisado.\n',
            encoding="utf-8")
        subprocess.run(args, capture_output=True, text=True)

        novo = pack_f.read_text(encoding="utf-8")
        assert "https://notebooklm.google.com/notebook/abc" in novo
        assert "notebooklm_status: criado" in novo


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



def test_fix_notebooklm_enxerga_o_layout_de_aprofundamentos():
    """Regressão: o migrador não achava um único pacote do vault — e saía com 0.

    O inventário reimplementava a regra de layout procurando `{assunto}/{assunto}.md`,
    o formato plano legado. Como todos os 158 pacotes do vault vivem em
    `{assunto}/{nivel}--{fonte}/`, ele imprimia "Nenhum assunto encontrado" e
    encerrava **com sucesso**: migração que não migra e não reclama. O teste antigo
    passava porque o fixture usava o layout que o gerador não emite mais.
    """
    with tempfile.TemporaryDirectory() as d:
        pasta = Path(d) / "assuntos" / "crase" / "padrao--pestana"
        pasta.mkdir(parents=True)
        (pasta / "crase--padrao--pestana--X_2026.md").write_text(
            '---\ntitle: "Crase"\naprofundamento: "padrao--pestana"\nnivel: padrao\n'
            'fontes: "Pestana"\nstatus: concluido\n---\nResumo real.\n', encoding="utf-8")
        (pasta / "_fonte-notebooklm.md").write_text(
            "# antigo\npodcast-crase.mp3\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "fix_notebooklm_packs.py"),
                            "--assuntos-dir", str(Path(d) / "assuntos"),
                            "--concurso", "X_2026", "--materia", "P"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "Aprofundamentos encontrados: 1" in r.stdout, r.stdout
        novo = (pasta / "_fonte-notebooklm.md").read_text(encoding="utf-8")
        assert "podcast-crase--padrao--pestana--X_2026.m4a" in novo, novo[:400]
        assert (pasta / "_fonte-notebooklm.bak.md").exists(), "backup do gerador"


def test_fix_notebooklm_falha_alto_quando_nao_acha_nada():
    """Sair 0 sem escrever nada escondeu o bug do layout por versões. Pasta sem
    aprofundamento é erro, não sucesso silencioso."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "assuntos").mkdir()
        r = subprocess.run([sys.executable, str(ROOT / "fix_notebooklm_packs.py"),
                            "--assuntos-dir", str(Path(d) / "assuntos"),
                            "--concurso", "X_2026", "--materia", "P"],
                           capture_output=True, text=True)
        assert r.returncode == 1, (r.returncode, r.stdout)


def test_fix_notebooklm_sem_leis_dir_nao_apaga_as_leis_da_lista_de_fontes():
    """44 dos 158 packs do vault listam leis como fonte a subir. Regenerar sem
    `--leis-dir` as apaga em silêncio — e o pack é onde o usuário lê o que subir."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        leis = d / "leis"
        leis.mkdir()
        (leis / "lei-8742-1993-loas.pdf").write_bytes(b"%PDF-1.4\n")
        pasta = d / "assuntos" / "bpc" / "padrao--lei-8742"
        pasta.mkdir(parents=True)
        (pasta / "bpc--padrao--lei-8742--X_2026.md").write_text(
            '---\ntitle: "BPC"\naprofundamento: "padrao--lei-8742"\nnivel: padrao\n'
            'fontes: "Lei 8.742/1993"\nstatus: concluido\n---\n'
            "O art. 20 da Lei 8742 define o BPC.\n", encoding="utf-8")
        cmd = [sys.executable, str(ROOT / "fix_notebooklm_packs.py"),
               "--assuntos-dir", str(d / "assuntos"), "--concurso", "X_2026",
               "--materia", "P", "--leis-dir", str(leis)]
        assert subprocess.run(cmd, capture_output=True, text=True).returncode == 0
        com = (pasta / "_fonte-notebooklm.md").read_text(encoding="utf-8")
        assert "lei-8742-1993-loas.pdf" in com, "a lei tem de entrar na lista de fontes"


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
        # este é o único fixture antigo que exercita o caminho que vazava: era o
        # nível `detalhado` que injetava `fontes:` dentro do prompt
        assert ".pdf" not in det and "Fonte X" not in det, det


def _blocos_de_prompt(pack: str) -> list[str]:
    """Todo bloco cercado do pacote — é o que o usuário cola no NotebookLM."""
    return re.findall(r"^```\s*\n(.*?)^```", pack, re.MULTILINE | re.DOTALL)


# padrões que denunciam um prompt mandando consultar a OBRA em vez da nota do vault
PROIBIDO_NO_PROMPT = (
    re.compile(r"\.pdf\b", re.I),
    re.compile(r"\bp[áa]gs?\.", re.I),
    re.compile(r"\bp[áa]ginas?\b", re.I),
    re.compile(r"\bcap[íi]tulos?\b", re.I),
    re.compile(r"\btrecho do livro\b", re.I),
    re.compile(r"Baseie-se nas fontes", re.I),   # a formulação que injetava `fontes:`
    re.compile(r"localizacao_livro", re.I),
)
# palavras comuns demais para acusar vazamento da fonte
GENERICOS = {"lei", "livro", "material", "proprio", "próprio", "para", "concursos",
             "gramatica", "gramática", "manual", "plano", "edicao", "edição"}


def _termos(s: str) -> set:
    return set(re.findall(r"[\wÀ-ÿ]{2,}", (s or "").lower()))


def test_prompt_nunca_manda_consultar_o_livro():
    """Guarda sistêmica: subir o livro é OPCIONAL, então prompt que o nomeia manda
    o modelo usar uma fonte que pode não estar no notebook.

    Regressão real: o áudio nível `detalhado` injetava
    `Baseie-se nas fontes: A-Gramatica-para-Concursos-Fernando-Pestana.pdf.` — um
    PDF marcado como *(Referência)* opcional na própria seção de fontes do pacote.

    Este teste vale para os prompts que ainda serão escritos: varre TODOS os blocos
    cercados de TODAS as combinações e falha se algum nomear obra, PDF ou página.
    """
    casos = [
        # (ident no padrão {nivel}--{fonte}, nivel, fontes, localizacao_livro)
        ("padrao--pestana", "padrao", "A Gramática para Concursos (Pestana)",
         "A-Gramatica-para-Concursos-Fernando-Pestana.pdf — págs. 192–682"),
        ("detalhado--pestana", "detalhado", "A-Gramatica-para-Concursos-Fernando-Pestana.pdf",
         "A-Gramatica-para-Concursos-Fernando-Pestana.pdf — págs. 192–682"),
        ("padrao--lei-8742", "padrao", "Lei nº 8.742/1993", "lei-8742-1993-loas.pdf — art. 20"),
        ("padrao--proprio", "padrao", "material próprio", ""),
    ]
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "assuntos" / "crase"
        for ident, nivel, fontes, loc in casos:
            p = base / ident
            p.mkdir(parents=True)
            extra = f'localizacao_livro: "{loc}"\n' if loc else ""
            (p / f"crase--{ident}.md").write_text(
                f'---\ntitle: "Crase"\naprofundamento: "{ident}"\nnivel: {nivel}\n'
                f'fontes: "{fontes}"\n{extra}status: concluido\n---\nConteúdo real.\n',
                encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "notebooklm_pack.py"),
                            "--assuntos-dir", str(Path(d) / "assuntos"),
                            "--concurso", "X_2026", "--materia", "P"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout)["gerados"] == len(casos)

        for ident, _, fontes, loc in casos:
            pack = (base / ident / "_fonte-notebooklm.md").read_text(encoding="utf-8")
            blocos = _blocos_de_prompt(pack)
            assert len(blocos) == 4, (ident, len(blocos))

            nota = f"crase--{ident}.md"
            clausula = f'Baseie-se na nota "{nota}" deste notebook.'
            # termos que SÓ o frontmatter de fonte conhece. O que o título do
            # assunto já diz é legítimo — num assunto "Lei 8.742/1993" citar a lei
            # no prompt é o próprio tema, não vazamento da obra.
            so_da_fonte = {t for t in _termos(f"{fontes} {loc}")
                           if len(t) > 3 and t not in _termos("Crase")
                           and t not in GENERICOS}

            for bloco in blocos:
                # TODO prompt ancora na nota, que é sempre o item 1 das fontes
                assert nota in bloco, (ident, bloco)
                # tirar a cláusula ANTES de varrer: o nome da nota carrega o slug
                # da fonte (`--pestana--`), e a varredura acusaria a própria frase
                # que este teste exige.
                corpo = bloco.replace(clausula, "")
                for padrao in PROIBIDO_NO_PROMPT:
                    assert not padrao.search(corpo), (ident, padrao.pattern, corpo)
                vazou = sorted(so_da_fonte & _termos(corpo))
                assert not vazou, (ident, "termo que só `fontes:` conhece", vazou)


def test_prompt_cabe_no_campo_do_estudio():
    """O campo "Customize" do Estúdio trunca. Prompt que estoura perde o fim —
    e o fim é onde ficam as instruções de conteúdo."""
    with tempfile.TemporaryDirectory() as d:
        # pior caso realista: nome de assunto e de aprofundamento longos
        ident = "detalhado--samu-sp+cruz-vermelha"
        p = Path(d) / "assuntos" / "nocoes-de-rcp-e-cadeia-de-sobrevivencia" / ident
        p.mkdir(parents=True)
        (p / f"nocoes-de-rcp-e-cadeia-de-sobrevivencia--{ident}--SEDES_2026.md").write_text(
            '---\ntitle: "Noções de RCP (reanimação cardiopulmonar) e cadeia de '
            'sobrevivência"\naprofundamento: "' + ident + '"\nnivel: detalhado\n'
            'fontes: "Manual do SAMU-192, CICV"\nstatus: concluido\n---\nReal.\n',
            encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "notebooklm_pack.py"),
                        "--assuntos-dir", str(Path(d) / "assuntos"),
                        "--concurso", "SEDES_2026", "--materia", "M"],
                       capture_output=True, text=True)
        # medido no pior caso real do vault: 490 chars. O teto dá folga sem virar
        # teste que nunca morde.
        for bloco in _blocos_de_prompt((p / "_fonte-notebooklm.md").read_text(encoding="utf-8")):
            assert len(bloco.strip()) <= 550, (len(bloco.strip()), bloco[:120])


def test_clausula_de_fonte_nomeia_a_nota_e_nada_mais():
    import notebooklm_pack as nlp
    assert nlp.clausula_fonte("crase--padrao--pestana--SEDES_2026.md") == (
        'Baseie-se na nota "crase--padrao--pestana--SEDES_2026.md" deste notebook.')


def _pack_de_um_assunto(d: Path, extra_fm: str = "") -> Path:
    """Gera um pacote de verdade e devolve o caminho dele."""
    p = d / "assuntos" / "crase" / "padrao--pestana"
    p.mkdir(parents=True, exist_ok=True)
    (p / "crase--padrao--pestana--X_2026.md").write_text(
        '---\ntitle: "Crase"\naprofundamento: "padrao--pestana"\nnivel: padrao\n'
        'fontes: "Pestana"\nstatus: concluido\n---\nReal.\n', encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "notebooklm_pack.py"),
                    "--assuntos-dir", str(d / "assuntos"),
                    "--concurso", "X_2026", "--materia", "M"],
                   capture_output=True, text=True)
    return p / "_fonte-notebooklm.md"


def test_regerar_preserva_todo_o_bloco_notebooklm():
    """Regressão: regerar o pacote apagava tudo que a automação escreveu.

    `herdar_campos()` herdava exatamente DUAS chaves. Qualquer campo novo — o id do
    notebook, a data, o que a integração precisa para não recriar o notebook — ia
    para o `.bak.md` na regeração seguinte, em silêncio. É o mesmo defeito que a
    função foi criada para evitar com o `notebooklm_url`, repetido. A herança agora
    é por PREFIXO: campo novo sobrevive sem ninguém lembrar de vir aqui.
    """
    with tempfile.TemporaryDirectory() as d:
        pack = _pack_de_um_assunto(Path(d))
        # a automação escreve o que só ela sabe
        txt = pack.read_text(encoding="utf-8")
        txt = txt.replace('notebooklm_url: ""',
                          'notebooklm_url: "https://notebooklm.google.com/notebook/abc"\n'
                          'notebooklm_id: "abc-123"\n'
                          'notebooklm_gerado_em: "2026-07-31"')
        txt = txt.replace("notebooklm_status: nao-criado", "notebooklm_status: completo")
        pack.write_text(txt, encoding="utf-8")

        # o gerador roda de novo — como rodou nos 158 pacotes do vault
        _pack_de_um_assunto(Path(d))

        novo = pack.read_text(encoding="utf-8")
        assert 'notebooklm_url: "https://notebooklm.google.com/notebook/abc"' in novo, "a URL"
        assert "notebooklm_status: completo" in novo, "o status"
        assert 'notebooklm_id: "abc-123"' in novo, "o id do notebook"
        assert 'notebooklm_gerado_em: "2026-07-31"' in novo, "a data"


def test_frontmatter_do_pack_novo_nao_tem_linha_vazia():
    """O bloco de campos herdados fica vazio no caso comum; o placeholder não pode
    deixar uma linha solta no meio do YAML."""
    with tempfile.TemporaryDirectory() as d:
        fm = _pack_de_um_assunto(Path(d)).read_text(encoding="utf-8").split("---")[1]
        assert not any(l == "" for l in fm.strip("\n").split("\n")), repr(fm)


def test_campo_notebooklm_vazio_nao_e_herdado_como_lixo():
    """Chave presente mas vazia não pode virar `notebooklm_id: ""` para sempre."""
    with tempfile.TemporaryDirectory() as d:
        pack = _pack_de_um_assunto(Path(d))
        pack.write_text(pack.read_text(encoding="utf-8").replace(
            'notebooklm_url: ""', 'notebooklm_url: ""\nnotebooklm_id: ""'), encoding="utf-8")
        _pack_de_um_assunto(Path(d))
        assert "notebooklm_id" not in pack.read_text(encoding="utf-8")


def test_pack_declara_nome_do_notebook_e_arquivos_no_frontmatter():
    """O nome do notebook e os nomes dos arquivos a salvar são CONTRATO, não prosa.

    A `concurso-publica` os extraía por regex do texto corrido e falhava: o roteiro
    do mapa mental e o do report chegavam vazios ao site, e o nome do notebook não
    chegava nunca. Declarados no frontmatter, a leitura é determinística — e é o que
    a automação vai consumir.
    """
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "assuntos" / "crase" / "padrao--pestana"
        p.mkdir(parents=True)
        (p / "crase--padrao--pestana--X_2026.md").write_text(
            '---\ntitle: "Crase"\naprofundamento: "padrao--pestana"\nnivel: padrao\n'
            'fontes: "Pestana"\nstatus: concluido\n---\nReal.\n', encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "notebooklm_pack.py"),
                        "--assuntos-dir", str(Path(d) / "assuntos"),
                        "--concurso", "X_2026", "--materia", "M"],
                       capture_output=True, text=True)
        pack = (p / "_fonte-notebooklm.md").read_text(encoding="utf-8")
        base = "crase--padrao--pestana--X_2026"
        assert 'nome_notebook: "X_2026 — Crase — padrao--pestana"' in pack, "nome do notebook"
        assert f'arquivo_podcast: "podcast-{base}.m4a"' in pack, "arquivo do podcast"
        assert f'arquivo_mapa_mental: "mapa-mental-{base}.png"' in pack, "arquivo do mapa mental"
        assert f'arquivo_video: "video-{base}.mp4"' in pack, "arquivo do vídeo"
        assert f'arquivo_report: "report-{base}.md"' in pack, "arquivo do report"


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
    # token reservado: escolha declarada, não derivação que deu errado
    assert not aid.slug_suspeito(aid.FONTE_PROPRIA)


# ---------------- aprofundamento sem fonte externa ---------------- #
def test_id_aprofundamento_proprio_nos_dois_niveis():
    """Material escrito do conhecimento do Claude, sem livro nem norma."""
    assert aid.id_aprofundamento([], "padrao", proprio=True) == "padrao--proprio"
    assert aid.id_aprofundamento(None, "detalhado", proprio=True) == "detalhado--proprio"
    info = aid.parse_id("padrao--proprio")
    assert info["nivel"] == "padrao" and info["fontes"] == ["proprio"]
    assert aid.eh_pasta_aprofundamento("detalhado--proprio")
    assert aid.eh_proprio("padrao--proprio")
    assert not aid.eh_proprio("padrao--pestana")


def test_lista_de_fontes_vazia_nao_e_o_mesmo_que_sem_fonte():
    """A distinção é o ponto: lista vazia significa que a DERIVAÇÃO falhou, e o
    fallback `fonte` existe para isso ficar visível (`slug_suspeito` o acusa).
    Sem essa separação, um material deliberadamente sem fonte se disfarçaria de
    erro de configuração — e o inverso também."""
    assert aid.id_aprofundamento([], "padrao") == "padrao--fonte"
    assert aid.slug_suspeito("fonte")
    assert aid.id_aprofundamento([], "padrao", proprio=True) == "padrao--proprio"


def test_rotulo_do_proprio_descreve_o_artefato():
    """No path o token é `proprio`; na tela vira o que a coisa é."""
    assert aid.rotulo("padrao--proprio") == "Padrão — material próprio"
    assert aid.rotulo("detalhado--proprio") == "Detalhado — material próprio"
    assert aid.rotulo("padrao--pestana") == "Padrão — pestana"


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


def _rodar_build(d, extra):
    return subprocess.run(
        [sys.executable, str(ROOT / "build_subject_md.py"),
         "--out-dir", str(d / "assuntos"), "--concurso", "TESTE_2026"] + extra,
        capture_output=True, text=True)


def test_build_subject_md_proprio_dispensa_livro():
    """Aprofundamento sem fonte externa, nos dois níveis, a partir de uma lista
    de assuntos — sem `mapa-localizacao.json`, que só o livro produz."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        lista = d / "assuntos.txt"
        lista.write_text("Crase\n", encoding="utf-8")
        for nivel in ("padrao", "detalhado"):
            out = _rodar_build(d, ["--assuntos", str(lista), "--proprio",
                                   "--nivel", nivel, "--materia", "Português"])
            assert out.returncode == 0, out.stderr
            alvo = (d / "assuntos" / "crase" / f"{nivel}--proprio"
                    / f"crase--{nivel}--proprio--TESTE_2026.md")
            assert alvo.exists(), list((d / "assuntos").rglob("*"))
            txt = alvo.read_text(encoding="utf-8")
            # sem livro não há página nem citação — e o material NÃO pode se
            # disfarçar de localização que falhou
            assert "localizacao_livro" not in txt
            assert "Trechos-âncora" not in txt
            assert "Ler as páginas" not in txt
            assert "não localizado" not in txt
            assert "Onde conferir" in txt
            assert 'fontes: "material próprio"' in txt


def _vault_com_mapa(d: Path) -> Path:
    base = d / "SEDES_2026"
    (base / "_COMUM" / "03-MAPAS-COMUNS").mkdir(parents=True)
    (base / "_COMUM" / "03-MAPAS-COMUNS" / "01-portugues.md").write_text(
        '---\nmateria_id: lingua-portuguesa\n---\n'
        '# 📚 Mapa de Estudo — Língua Portuguesa\n\n'
        '## 1. Crase 🔴\n\n### Subtópicos derivados\n\n'
        '- [ ] Regra geral: quando há artigo\n- [ ] Casos proibidos\n\n'
        '#### Detalhe\n\n- [ ] Antes de masculino\n\n'
        '### Material recomendado\n\n- Livro: X.\n\n'
        '## 2. Pontuação\n\n### Subtópicos derivados — TEORIA\n\n- [ ] Vírgula\n\n'
        '### Subtópicos derivados — PRÁTICA\n\n- [ ] Ponto e vírgula\n\n'
        '## 3. Sem subtópicos\n\n### Material recomendado\n\n- Livro: Y.\n',
        encoding="utf-8")
    return base


def _rodar_topico(base, *extra):
    return subprocess.run(
        [sys.executable, str(ROOT / "assuntos_do_topico.py"),
         "--concurso-dir", str(base), "--materia-id", "lingua-portuguesa"] + list(extra),
        capture_output=True, text=True)


def test_assuntos_do_topico_extrai_so_o_topico_pedido():
    with tempfile.TemporaryDirectory() as d:
        base = _vault_com_mapa(Path(d))
        out = _rodar_topico(base, "--topico", "1")
        assert out.returncode == 0, out.stderr
        r = json.loads(out.stdout)
        assert r["topico_id"] == "crase"
        assert r["topico"] == "1. Crase"          # emoji de prioridade some
        assert r["materia"] == "Língua Portuguesa"   # do H1, não do nome do arquivo
        # "Regra geral: quando há artigo" -> o assunto é o tema antes dos dois-pontos
        assert r["assuntos"] == ["Regra geral", "Casos proibidos", "Antes de masculino"]
        assert "Vírgula" not in r["assuntos"]     # não vaza do tópico 2


def test_assuntos_do_topico_soma_blocos_com_sufixo():
    with tempfile.TemporaryDirectory() as d:
        base = _vault_com_mapa(Path(d))
        r = json.loads(_rodar_topico(base, "--topico", "2").stdout)
        assert r["assuntos"] == ["Vírgula", "Ponto e vírgula"]


def test_assuntos_do_topico_aceita_numero_slug_e_trecho():
    with tempfile.TemporaryDirectory() as d:
        base = _vault_com_mapa(Path(d))
        for alvo in ("1", "crase", "Crase"):
            assert json.loads(_rodar_topico(base, "--topico", alvo).stdout)["topico_id"] \
                == "crase", alvo


def test_assuntos_do_topico_falha_alto_quando_nao_existe():
    """Devolver lista vazia faria a etapa seguinte gerar nada e parecer que o
    tópico simplesmente não tem assunto."""
    with tempfile.TemporaryDirectory() as d:
        base = _vault_com_mapa(Path(d))
        out = _rodar_topico(base, "--topico", "99")
        assert out.returncode == 2
        assert "não encontrado" in out.stderr
        assert "1. Crase" in out.stderr          # lista o que existe


def test_assuntos_do_topico_ignora_marcadores_do_obsidian_tasks():
    """Regressão: marcar o subtópico como concluído no Obsidian renomeava o assunto.

    O plugin Tasks acrescenta `✅ 2026-07-30` ao fim da linha. Como o corte nos
    dois-pontos só limpava itens do formato "Tema: explicação", num item SEM `:`
    a data ia parar dentro do nome — o slug virava
    `criacao-de-brasilia-...-plano-de-metas-2026-07-30` e deixava de casar com a
    pasta já existente no vault, fazendo o assunto parecer não aprofundado.
    """
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "SEDES_2026"
        (base / "_COMUM" / "03-MAPAS-COMUNS").mkdir(parents=True)
        (base / "_COMUM" / "03-MAPAS-COMUNS" / "01-df.md").write_text(
            '---\nmateria_id: conhecimentos-df\n---\n'
            '# 📚 Mapa de Estudo — Conhecimentos do DF\n\n'
            '## 1. Conhecimentos do DF\n\n### Subtópicos derivados\n\n'
            # concluído: o caso real, item SEM dois-pontos
            '- [x] Criação de Brasília, plano de metas ✅ 2026-07-30\n'
            # agendado + vencimento, ainda em aberto
            '- [ ] Geografia do DF ➕ 2026-07-01 📅 2026-08-15\n'
            # prioridade do Tasks, sem data
            '- [ ] Realidade étnica ⏫\n'
            # item COM dois-pontos: já sobrevivia, tem de continuar sobrevivendo
            '- [x] Política e organização: acumula competências ✅ 2026-07-30\n'
            # emoji que NÃO é do Tasks pertence ao nome e não pode ser cortado
            '- [ ] Mnemônicos 🧠 do bloco\n',
            encoding="utf-8")
        out = subprocess.run(
            [sys.executable, str(ROOT / "assuntos_do_topico.py"),
             "--concurso-dir", str(base), "--materia-id", "conhecimentos-df",
             "--topico", "1"], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        assuntos = json.loads(out.stdout)["assuntos"]
        assert assuntos == ["Criação de Brasília, plano de metas",
                            "Geografia do DF",
                            "Realidade étnica",
                            "Política e organização",
                            "Mnemônicos 🧠 do bloco"], assuntos
        # o que o bug produzia não pode reaparecer em nenhum deles
        assert not any("2026-" in a for a in assuntos), assuntos


def test_assuntos_do_topico_avisa_quando_topico_nao_tem_subtopicos():
    with tempfile.TemporaryDirectory() as d:
        base = _vault_com_mapa(Path(d))
        out = _rodar_topico(base, "--topico", "3")
        assert out.returncode == 0
        assert json.loads(out.stdout)["assuntos"] == []
        assert "nada a aprofundar" in out.stderr


def test_build_subject_md_nao_destroi_resumo_ja_escrito():
    """Regressão do defeito mais caro possível: o `.md` é onde mora o resumo
    escrito à mão, e o script gravava por cima SEM PERGUNTAR. Rodar a matéria de
    novo trocava o texto pronto por arcabouço com os {PLACEHOLDER} de volta — e o
    modo seletivo (um tópico por vez) é justamente reexecutar a mesma matéria."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        lista = d / "assuntos.txt"
        lista.write_text("Crase\n", encoding="utf-8")
        args = ["--assuntos", str(lista), "--proprio", "--materia", "Português"]
        assert _rodar_build(d, args).returncode == 0
        alvo = (d / "assuntos" / "crase" / "padrao--proprio"
                / "crase--padrao--proprio--TESTE_2026.md")
        alvo.write_text(alvo.read_text(encoding="utf-8").replace(
            "{RESUMO}", "Resumo que levou horas para escrever."), encoding="utf-8")

        out = _rodar_build(d, args)                    # segunda execução
        assert out.returncode == 0, out.stderr
        txt = alvo.read_text(encoding="utf-8")
        assert "Resumo que levou horas para escrever." in txt
        assert "{RESUMO}" not in txt
        rel = json.loads(out.stdout)
        assert rel["gerados"] == 0 and rel["ja_existiam"], rel

        out = _rodar_build(d, args + ["--forcar"])     # regenerar de propósito
        assert out.returncode == 0, out.stderr
        assert "{RESUMO}" in alvo.read_text(encoding="utf-8")
        assert alvo.with_suffix(".md.bak").exists()
        assert "Resumo que levou horas" in \
            alvo.with_suffix(".md.bak").read_text(encoding="utf-8")


def test_build_subject_md_aceita_assuntos_em_json():
    """`book_index.py` consome `{"materia","assuntos":[...]}`; o build lia TXT.
    Formatos diferentes para a mesma lista obrigavam a converter à mão entre uma
    etapa e a seguinte."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        spec = d / "assuntos.json"
        spec.write_text(json.dumps({"materia": "Português", "assuntos": ["Crase"]},
                                   ensure_ascii=False), encoding="utf-8")
        out = _rodar_build(d, ["--assuntos", str(spec), "--proprio"])
        assert out.returncode == 0, out.stderr
        txt = (d / "assuntos" / "crase" / "padrao--proprio"
               / "crase--padrao--proprio--TESTE_2026.md").read_text(encoding="utf-8")
        assert 'materia: "Português"' in txt


def test_build_subject_md_exige_mapa_ou_assuntos():
    with tempfile.TemporaryDirectory() as d:
        out = _rodar_build(Path(d), ["--proprio"])
        assert out.returncode != 0
        assert "--mapa" in out.stderr and "--assuntos" in out.stderr


def test_build_subject_md_grava_o_vinculo_com_o_topico():
    """O elo assunto->tópico do edital: a skill lê o mapa para saber quais
    assuntos existem, então ela SABE de que tópico cada um veio — só não
    registrava. Sem isso o site não tem como agrupar por tópico."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        lista = d / "assuntos.txt"
        lista.write_text("Crase\n", encoding="utf-8")
        out = _rodar_build(d, ["--assuntos", str(lista), "--proprio",
                               "--materia", "Português",
                               "--materia-id", "lingua-portuguesa",
                               "--topico-id", "estrutura-morfossintatica",
                               "--topico", "5. Estrutura morfossintática"])
        assert out.returncode == 0, out.stderr
        txt = (d / "assuntos" / "crase" / "padrao--proprio"
               / "crase--padrao--proprio--TESTE_2026.md").read_text(encoding="utf-8")
        assert "materia_id: lingua-portuguesa" in txt
        assert "topico_id: [estrutura-morfossintatica]" in txt
        assert 'topico: ["5. Estrutura morfossintática"]' in txt


def test_build_subject_md_sem_topico_emite_lista_vazia_e_avisa():
    """`[]` é "ainda não vinculado"; `[""]` seria lixo que o leitor teria de
    aprender a ignorar. E a ausência do vínculo tem de ser dita, não suposta."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        lista = d / "assuntos.txt"
        lista.write_text("Crase\n", encoding="utf-8")
        out = _rodar_build(d, ["--assuntos", str(lista), "--proprio",
                               "--materia", "Português"])
        txt = (d / "assuntos" / "crase" / "padrao--proprio"
               / "crase--padrao--proprio--TESTE_2026.md").read_text(encoding="utf-8")
        assert "topico_id: []" in txt and "topico: []" in txt
        assert 'tags: [concurso/aprofundamento, portugues, crase' in txt   # sem item vazio
        assert any("topico-id" in a for a in json.loads(out.stdout)["avisos"])


def _vault_falso_com_vinculos(d: Path, topico_id="criancas"):
    ap = d / "assuntos" / "eca" / "padrao--lei-8069"
    ap.mkdir(parents=True)
    md = ap / "eca--padrao--lei-8069--X.md"
    md.write_text('---\ntitle: "ECA"\nmateria: "Direitos"\nstatus: revisar\n---\n'
                  "Resumo do usuário.\n- [x] feito\n- [ ] aberto\n", encoding="utf-8")
    v = d / "v.json"
    v.write_text(json.dumps({"concurso": "X", "materias": [{
        "materia_id": "direitos-violacoes-vulnerabilidades",
        "pasta_aprofundamento": "direitos-violacoes",
        "mapas_candidatos": [{"slug": "direitos-violacoes-vulnerabilidades",
                              "topicos": [{"id": "criancas", "numero": 1,
                                           "titulo": "Crianças e adolescentes"}]}],
        "assuntos": [{"slug": "eca", "arquivos": [str(md)],
                      "topico_id": [topico_id] if topico_id else []}],
    }]}, ensure_ascii=False), encoding="utf-8")
    return md, v


def _rodar_aplicar(v, *extra):
    return subprocess.run(
        [sys.executable, str(ROOT / "aplicar_vinculos.py"), "--vinculos", str(v)]
        + list(extra), capture_output=True, text=True)


def test_aplicar_vinculos_dry_run_nao_escreve():
    with tempfile.TemporaryDirectory() as d:
        md, v = _vault_falso_com_vinculos(Path(d))
        antes = md.read_text(encoding="utf-8")
        out = _rodar_aplicar(v)
        assert out.returncode == 0, out.stderr
        assert md.read_text(encoding="utf-8") == antes
        assert not md.with_suffix(".bak.md").exists()


def test_aplicar_vinculos_grava_e_preserva_o_trabalho_do_usuario():
    """Dentro desses arquivos mora o resumo escrito à mão e o progresso (os
    checkboxes). O script só acrescenta metadado — corpo passa intacto, e há
    backup porque reescrever arquivo do usuário sem rede é como se perde coisa."""
    with tempfile.TemporaryDirectory() as d:
        md, v = _vault_falso_com_vinculos(Path(d))
        out = _rodar_aplicar(v, "--aplicar")
        assert out.returncode == 0, out.stderr
        txt = md.read_text(encoding="utf-8")
        assert "materia_id: direitos-violacoes-vulnerabilidades" in txt
        assert "topico_id: [criancas]" in txt
        assert 'topico: ["1. Crianças e adolescentes"]' in txt
        assert "Resumo do usuário." in txt
        assert "- [x] feito" in txt and "- [ ] aberto" in txt
        # `.md.bak`, e não `.bak.md`: o collector do site varre `*.md` e escolhe
        # o principal por ordem alfabética — `x.bak.md` vinha ANTES de `x.md` e
        # era servido no lugar do arquivo real, sem o vínculo recém-gravado
        assert md.with_suffix(".md.bak").exists()
        assert not md.with_suffix(".bak.md").exists()
        assert len(list(md.parent.glob("*.md"))) == 1


def test_aplicar_vinculos_recusa_topico_inexistente():
    """Gravar um id que o mapa não tem faria o site agrupar por um tópico que
    não existe — e ninguém veria, porque o assunto simplesmente sumiria da
    lista. Vira pendência ruidosa, com exit code."""
    with tempfile.TemporaryDirectory() as d:
        md, v = _vault_falso_com_vinculos(Path(d), topico_id="topico-inventado")
        out = _rodar_aplicar(v, "--aplicar")
        assert out.returncode == 2
        assert "inexistente" in out.stderr
        assert "materia_id" not in md.read_text(encoding="utf-8")


def test_aplicar_vinculos_aceita_assunto_sem_topico():
    """`[]` é estado legítimo — "ainda não vinculado" — e o site tem um balde
    visível para ele. Não é erro e não pode virar exceção."""
    with tempfile.TemporaryDirectory() as d:
        md, v = _vault_falso_com_vinculos(Path(d), topico_id=None)
        out = _rodar_aplicar(v, "--aplicar")
        assert out.returncode == 0, out.stderr
        assert "topico_id: []" in md.read_text(encoding="utf-8")
        assert "SEM tópico" in out.stdout


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


# ------------------- renomear_aprof (máquina compartilhada) ------------------- #
def test_migrador_usa_a_mesma_reescrita_de_link_do_modulo():
    """A regra de layout mora num lugar só.

    Copiar a reescrita de wikilink para o outro consumidor reproduziria o modo de
    falha do fix_notebooklm_packs.py: uma cópia que deriva do original e um dia
    acha zero, calada. Identidade de objeto, não igualdade de comportamento —
    para o teste falhar já na cópia, antes de a cópia divergir.
    """
    import migrar_aprofundamentos as migr
    import renomear_aprof as ren
    assert migr.reescrever_referencias is ren.reescrever_referencias
    assert migr.mapa_de_links is ren.mapa_de_links
    assert migr.planejar_movimentos is ren.planejar_movimentos
    assert migr.atualizar_frontmatter is ren.atualizar_frontmatter
    assert migr.PREFIXOS_RENOMEAR is ren.PREFIXOS_RENOMEAR

    import notebooklm_pack as nlp
    assert nlp.frontmatter_sem_linha_vazia is ren.frontmatter_sem_linha_vazia


def test_mapa_de_links_cobre_path_e_stem_nos_tres_finais():
    """O índice referencia por path a partir de 'assuntos/'; o Obsidian, por stem.
    E o pipe aparece cru, escapado (tabela) e ausente (link sem alias)."""
    import renomear_aprof as ren
    de = Path("/v/CONCURSOS/X/m/assuntos/crase/padrao--a/crase--padrao--a--X.md")
    mapa = ren.mapa_de_links([(de, "crase--padrao--a+b--X.md")], "padrao--a+b")

    rel_antigo = "assuntos/crase/padrao--a/crase--padrao--a--X"
    rel_novo = "assuntos/crase/padrao--a+b/crase--padrao--a+b--X"
    for fim in ("|", "\\|", "]]"):
        assert mapa[rel_antigo + fim] == rel_novo + fim, f"path com final {fim!r}"
        assert mapa["[[crase--padrao--a--X" + fim] == "[[crase--padrao--a+b--X" + fim


def test_sidecar_do_notebooklm_viaja_com_o_aprofundamento():
    """`_notebooklm-estado.json` guarda o notebook_id: perdê-lo obriga a recriar o
    notebook do zero. No layout legado-plano ele caía no `continue` de 'arquivo
    alheio' e ficava para trás."""
    import renomear_aprof as ren
    with tempfile.TemporaryDirectory() as d:
        origem = Path(d) / "assuntos" / "crase"
        origem.mkdir(parents=True)
        md = origem / "crase.md"
        md.write_text("---\ntitle: x\n---\n", encoding="utf-8")
        (origem / "_notebooklm-estado.json").write_text("{}", encoding="utf-8")
        (origem / "anotacao-solta.md").write_text("minha", encoding="utf-8")

        movs = dict(ren.planejar_movimentos(origem, md, "crase--padrao--a--X",
                                            formato="legado-plano"))
        nomes = {p.name: novo for p, novo in movs.items()}
        assert nomes.get("_notebooklm-estado.json") == "_notebooklm-estado.json"
        assert "anotacao-solta.md" not in nomes, "arquivo alheio não pode viajar"


def test_gerar_para_pasta_nao_toca_nos_irmaos():
    """Regenerar o pack de UMA pasta não pode espalhar .bak.md pelas outras — foi
    para isso que gerar_para_pasta() saiu de dentro do main()."""
    import notebooklm_pack as nlp
    tpl = (ROOT.parent / "assets/templates/fonte-notebooklm.md.tpl").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as d:
        assunto = Path(d) / "assuntos" / "crase"
        fm = ('---\ntitle: "Crase"\nmateria: "Português"\nconcurso: "X_2026"\n'
              'nivel: padrao\naprofundamento: "{ident}"\n---\n\nResumo real.\n')
        for ident in ("padrao--a", "padrao--b"):
            p = assunto / ident
            p.mkdir(parents=True)
            (p / f"crase--{ident}--X_2026.md").write_text(fm.format(ident=ident),
                                                          encoding="utf-8")

        alvo = assunto / "padrao--a"
        r = nlp.gerar_para_pasta(alvo, assunto, concurso="X_2026", tpl=tpl)
        assert r["estado"] == "gerado", r
        assert (alvo / "_fonte-notebooklm.md").exists()
        assert not (assunto / "padrao--b" / "_fonte-notebooklm.md").exists(), \
            "gerou o pacote do irmão"


# --------------------- ampliar_aprofundamento (fontes novas) --------------------- #
def _vault_aprof(d: Path, *, fontes="Livro A (Alfa)", nivel="padrao",
                 concurso="X_2026", com_midia=False, com_url=False) -> Path:
    """Um aprofundamento montado pelos GERADORES REAIS, dentro de .../CONCURSOS/.

    Fixture montada à mão inventa o que o gerador não produz — o antipadrão que já
    deixou dois defeitos verdes por anos neste repo.
    """
    raiz = d / "CONCURSOS" / concurso / "_COMUM" / "03-APROFUNDAMENTO" / "portugues"
    out = raiz / "assuntos"
    mapa = d / "m.json"
    mapa.write_text(json.dumps({
        "livro": "L.pdf", "materia": "Português",
        "localizacoes": {"Crase": {"paginas": [1, 9], "confianca": "alta", "metodo": "toc"}},
    }), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "build_subject_md.py"),
                        "--mapa", str(mapa), "--out-dir", str(out), "--fontes", fontes,
                        "--nivel", nivel, "--concurso", concurso,
                        "--materia", "Português"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    aprof = next(p for p in (out / "crase").iterdir() if p.is_dir())
    md = next(aprof.glob("crase--*.md"))

    # o arcabouço vem com placeholders; o pacote pula quem não foi preenchido
    txt = md.read_text(encoding="utf-8")
    txt = re.sub(r"\{[A-Z_]{3,}\}", "conteúdo real escrito à mão", txt)
    md.write_text(txt, encoding="utf-8")

    cards = aprof / "cards.json"
    cards.write_text(json.dumps({
        "assunto": "Crase", "materia": "Português",
        "cards": [{"front": "O que é crase?", "back": "Fusão de duas vogais idênticas."}],
    }), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "flashcards_gen.py"),
                        "--cards", str(cards), "--out-dir", str(aprof),
                        "--aprofundamento", aprof.name, "--concurso", concurso],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    subprocess.run([sys.executable, str(ROOT / "notebooklm_pack.py"),
                    "--assuntos-dir", str(out), "--concurso", concurso,
                    "--materia", "Português"], capture_output=True, text=True)

    if com_midia:
        (aprof / f"podcast-{md.stem}.m4a").write_bytes(b"audio")
    if com_url:
        pack = aprof / "_fonte-notebooklm.md"
        p = pack.read_text(encoding="utf-8")
        p = p.replace('notebooklm_url: ""',
                      'notebooklm_url: "https://notebook.google.com/notebook/abc-123"')
        p = p.replace("notebooklm_status: nao-criado",
                      'notebooklm_status: criado\nnotebooklm_id: "abc-123"')
        pack.write_text(p, encoding="utf-8")
        # regera para o pacote passar a declarar a mídia que acabou de existir
        subprocess.run([sys.executable, str(ROOT / "notebooklm_pack.py"),
                        "--assuntos-dir", str(out), "--concurso", concurso,
                        "--materia", "Português"], capture_output=True, text=True)
    return aprof


def _ampliar(aprof: Path, *extra, fonte="Livro B (Beta)"):
    return subprocess.run(
        [sys.executable, str(ROOT / "ampliar_aprofundamento.py"),
         "--aprof-dir", str(aprof), "--fonte", fonte, *extra],
        capture_output=True, text=True)


def test_ampliar_renomeia_pasta_e_todos_os_nomes_base():
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        assunto = aprof.parent
        r = _ampliar(aprof, "--aplicar")
        novo = assunto / "padrao--alfa+beta"
        assert novo.is_dir(), r.stdout
        assert not aprof.exists(), "o id antigo tem de deixar de existir no modo ampliar"
        nomes = sorted(p.name for p in novo.iterdir())
        assert "crase--padrao--alfa+beta--X_2026.md" in nomes, nomes
        assert "flashcards-crase--padrao--alfa+beta--X_2026.md" in nomes, nomes
        assert "flashcards-crase--padrao--alfa+beta--X_2026.csv" in nomes, nomes
        assert not any("alfa--" in n and "+beta" not in n for n in nomes), nomes


def test_ampliar_renomeia_midia_para_o_pacote_continuar_achando():
    """Se a mídia não viaja com o nome novo, `plano.ja_existe()` devolve False e a
    automação regera podcast/vídeo que já existem — queima de quota."""
    sys.path.insert(0, str(ROOT.parents[1] / "concurso-notebooklm" / "scripts"))
    import pacote as pac_mod
    import plano as plano_mod
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d), com_midia=True, com_url=True)
        _ampliar(aprof, "--aplicar")
        novo = aprof.parent / "padrao--alfa+beta"
        pac = pac_mod.ler(novo / "_fonte-notebooklm.md")
        assert pac.arquivo_de("podcast") == "podcast-crase--padrao--alfa+beta--X_2026.m4a"
        assert plano_mod.ja_existe(pac, "podcast"), "a mídia renomeada tem de ser achada"


def test_ampliar_mantem_o_md_principal_como_fonte_do_pacote():
    sys.path.insert(0, str(ROOT.parents[1] / "concurso-notebooklm" / "scripts"))
    import pacote as pac_mod
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        _ampliar(aprof, "--aplicar")
        novo = aprof.parent / "padrao--alfa+beta"
        pac = pac_mod.ler(novo / "_fonte-notebooklm.md")
        _, faltando = pac_mod.resolver_fontes(pac, None)
        assert faltando == [], f"o notebook seria criado sem a fonte principal: {faltando}"


def test_ampliar_preserva_url_e_id_do_notebook():
    """A única informação do pacote que não dá para regerar."""
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d), com_url=True)
        _ampliar(aprof, "--aplicar")
        pack = (aprof.parent / "padrao--alfa+beta" / "_fonte-notebooklm.md").read_text(
            encoding="utf-8")
        assert "abc-123" in pack, pack[:400]
        assert "padrao--alfa+beta" in pack, "o nome do notebook tem de acompanhar"


def test_ampliar_avisa_da_nota_obsoleta_dentro_do_notebook():
    """`garantir_fontes()` só ADICIONA fonte: o notebook fica com a nota antiga e a
    nova, e o modelo passa a gerar mídia sobre material contraditório."""
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d), com_url=True)
        antiga = next(aprof.glob("crase--*.md")).name
        r = _ampliar(aprof, "--aplicar")
        rel = json.loads(r.stdout)
        pend = " ".join(p for i in rel["itens"] for p in i.get("pendencias", []))
        assert antiga in pend and "ADICIONA" in pend, pend
        pack = (aprof.parent / "padrao--alfa+beta" / "_fonte-notebooklm.md").read_text(
            encoding="utf-8")
        assert f'notebooklm_fonte_obsoleta: "{antiga}"' in pack, pack[:600]


def test_ampliar_reescreve_wikilink_no_indice_da_materia():
    """O índice vive FORA de assuntos/ e aponta pelo path completo."""
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        md = next(aprof.glob("crase--*.md"))
        rel = f"assuntos/crase/{aprof.name}/{md.stem}"
        indice = aprof.parents[2] / "00-INDICE-PORTUGUES.md"
        indice.write_text(f"- [[{rel}|Crase]]\n- [[{md.stem}]]\n", encoding="utf-8")
        _ampliar(aprof, "--aplicar")
        txt = indice.read_text(encoding="utf-8")
        assert "padrao--alfa+beta" in txt, txt
        assert "padrao--alfa/" not in txt and "--padrao--alfa--" not in txt, txt


def test_ampliar_recusa_destino_existente():
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        (aprof.parent / "padrao--alfa+beta").mkdir()
        r = _ampliar(aprof, "--aplicar")
        assert r.returncode == 2, r.stdout
        assert json.loads(r.stdout)["resumo"].get("CONFLITO") == 1
        assert aprof.exists(), "não pode ter mexido na origem"


def test_ampliar_avisa_permutacao_das_mesmas_fontes():
    """`a+b` e `b+a` seriam dois caminhos para o mesmo conjunto."""
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        (aprof.parent / "padrao--beta+alfa").mkdir()
        r = _ampliar(aprof, "--aplicar")
        assert r.returncode == 2
        motivos = " ".join(m for i in json.loads(r.stdout)["itens"]
                           for m in i.get("motivos", []))
        assert "outra ordem" in motivos, motivos
        r2 = _ampliar(aprof, "--aplicar", "--permitir-permutacao")
        assert (aprof.parent / "padrao--alfa+beta").is_dir(), r2.stdout


def test_ampliar_dry_run_e_o_padrao():
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        antes = sorted(p.name for p in aprof.iterdir())
        r = _ampliar(aprof)
        assert "DRY-RUN" in r.stdout
        assert sorted(p.name for p in aprof.iterdir()) == antes
        assert not (aprof.parent / "padrao--alfa+beta").exists()


def test_ampliar_falha_alto_quando_nao_acha_nada():
    """Sair 0 sem achar nada foi o que escondeu a migração que não rodou."""
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        r = subprocess.run(
            [sys.executable, str(ROOT / "ampliar_aprofundamento.py"),
             "--assuntos-dir", str(aprof.parents[1]),
             "--aprofundamento", "padrao--nao-existe", "--fonte", "X"],
            capture_output=True, text=True)
        assert r.returncode == 1, r.stdout


def test_ampliar_preserva_o_corpo_do_md():
    """Ampliar mexe na identidade, não no texto: o resumo é do usuário."""
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        md = next(aprof.glob("crase--*.md"))
        corpo_antes = md.read_text(encoding="utf-8").split("\n---\n", 1)[1]
        _ampliar(aprof, "--aplicar")
        novo = next((aprof.parent / "padrao--alfa+beta").glob("crase--*.md"))
        corpo = novo.read_text(encoding="utf-8").split("\n---\n", 1)[1]
        # só o wikilink dos flashcards muda, porque o par dele foi renomeado
        assert corpo.replace("alfa+beta", "alfa") == corpo_antes


def test_ampliar_registra_a_localizacao_da_fonte_nova():
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        _ampliar(aprof, "--aplicar", "--localizacao", "Beta — pp. 210 a 240")
        txt = next((aprof.parent / "padrao--alfa+beta").glob("crase--*.md")).read_text(
            encoding="utf-8")
        assert 'localizacao_2: "Beta — pp. 210 a 240"' in txt, txt[:500]
        assert "localizacao_livro:" in txt, "a fonte 1 continua onde estava"


def test_fonte_sem_localizacao_vira_pendencia_e_nao_pagina_inventada():
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        r = _ampliar(aprof, "--aplicar")
        pend = " ".join(p for i in json.loads(r.stdout)["itens"]
                        for p in i.get("pendencias", []))
        assert "sem --localizacao" in pend, pend
        txt = next((aprof.parent / "padrao--alfa+beta").glob("crase--*.md")).read_text(
            encoding="utf-8")
        assert "localizacao_2:" not in txt, "não pode inventar ponteiro"


def test_ampliar_rebaixa_status_para_revisar():
    """Declarar-se concluído antes da mescla é afirmação falsa que o site publica."""
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        md = next(aprof.glob("crase--*.md"))
        md.write_text(md.read_text(encoding="utf-8").replace(
            "status: nao-iniciado", "status: concluido"), encoding="utf-8")
        _ampliar(aprof, "--aplicar")
        txt = next((aprof.parent / "padrao--alfa+beta").glob("crase--*.md")).read_text(
            encoding="utf-8")
        assert 'status: "revisar"' in txt, txt[:400]


def test_derivar_mantem_o_antigo_intacto_e_nao_leva_a_url():
    """O par assimétrico: duas pastas apontando para o mesmo notebook fariam
    `garantir_fontes` subir a nota da variante para dentro do notebook do original."""
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d), com_midia=True, com_url=True)
        md = next(aprof.glob("crase--*.md"))
        rel = f"assuntos/crase/{aprof.name}/{md.stem}"
        indice = aprof.parents[2] / "00-INDICE-PORTUGUES.md"
        indice.write_text(f"- [[{rel}|Crase]]\n", encoding="utf-8")

        _ampliar(aprof, "--modo", "derivar", "--aplicar")
        novo = aprof.parent / "padrao--alfa+beta"
        assert aprof.is_dir() and novo.is_dir(), "os dois têm de conviver"
        assert "abc-123" in (aprof / "_fonte-notebooklm.md").read_text(encoding="utf-8")
        assert "abc-123" not in (novo / "_fonte-notebooklm.md").read_text(encoding="utf-8")
        assert not (novo / "_notebooklm-estado.json").exists()
        assert not list(novo.glob("podcast-*")), "mídia não é copiada por padrão"
        # o wikilink de fora ainda resolve para o original: não se mexe nele
        assert rel in indice.read_text(encoding="utf-8")
        assert 'derivado_de: "padrao--alfa"' in next(novo.glob("crase--*.md")).read_text(
            encoding="utf-8")


def test_ampliar_em_lote_pega_todos_os_assuntos_com_aquele_id():
    """O caso real é a matéria inteira recebendo a mesma segunda fonte."""
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        assuntos = aprof.parents[1]
        outro = assuntos / "regencia" / "padrao--alfa"
        outro.mkdir(parents=True)
        (outro / "regencia--padrao--alfa--X_2026.md").write_text(
            '---\ntitle: "Regência"\nconcurso: "X_2026"\nnivel: padrao\n'
            'aprofundamento: "padrao--alfa"\nfontes: "Livro A (Alfa)"\n---\nTexto.\n',
            encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(ROOT / "ampliar_aprofundamento.py"),
             "--assuntos-dir", str(assuntos), "--aprofundamento", "padrao--alfa",
             "--fonte", "Livro B (Beta)", "--aplicar"], capture_output=True, text=True)
        assert json.loads(r.stdout)["resumo"].get("AMPLIAR") == 2, r.stdout
        assert (assuntos / "crase" / "padrao--alfa+beta").is_dir()
        assert (assuntos / "regencia" / "padrao--alfa+beta").is_dir()


def test_slug_da_fonte_e_sempre_ecoado():
    """slug_suspeito() não acusa slug plausível-e-errado (um PDF com nome corrompido
    deriva `indleycintra`): a defesa é o usuário ver o slug antes de aplicar."""
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        r = _ampliar(aprof)
        assert "'beta'" in " ".join(json.loads(r.stdout)["slugs_derivados"]), r.stdout


def test_ampliar_recusa_fonte_que_ja_esta_no_aprofundamento():
    with tempfile.TemporaryDirectory() as d:
        aprof = _vault_aprof(Path(d))
        r = _ampliar(aprof, "--aplicar", fonte="Livro A (Alfa)")
        assert r.returncode == 2
        assert "já estão neste aprofundamento" in r.stdout


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
