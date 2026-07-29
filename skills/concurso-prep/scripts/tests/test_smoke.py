#!/usr/bin/env python3
"""
test_smoke.py - Testes de fumaça (smoke tests) dos scripts da skill concurso-prep.

Roda com pytest OU standalone (sem pytest instalado):
    pytest scripts/tests/            # se pytest disponível
    python scripts/tests/test_smoke.py   # fallback standalone

Cobre os pontos que já quebraram no passado (item 18 da revisão):
- slugify: acentos, separadores, modo órgão
- diff_editais: mantido/removido/novo/alterado + contenção de tokens + estrutural
- validate_output: estrutura UPPERCASE, .meta.json, soma de questões, wikilink irmão
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # .../scripts
sys.path.insert(0, str(ROOT))

import slugify  # noqa: E402
import diff_editais as de  # noqa: E402


# --------------------------------------------------------------------------- #
# slugify
# --------------------------------------------------------------------------- #
def test_slugify_cargo_acentos():
    assert slugify.slugify_cargo("EDAS Administração") == "EDAS-ADMINISTRACAO"


def test_slugify_cargo_separadores():
    assert slugify.slugify_cargo("Técnico Judiciário - Área") == "TECNICO-JUDICIARIO-AREA"


def test_slugify_orgao():
    assert slugify.slugify_orgao("Sedes/DF", 2026) == "SEDES_2026"


# --------------------------------------------------------------------------- #
# diff_editais
# --------------------------------------------------------------------------- #
def test_diff_mantido_novo_removido():
    v1 = {"M": ["alpha topico", "beta topico"]}
    v2 = {"M": ["alpha topico", "gamma topico"]}
    r = de.diff(v1, v2)
    assert r["resumo"]["n_mantidos"] == 1
    assert r["resumo"]["n_removidos"] == 1
    assert r["resumo"]["n_novos"] == 1


def test_diff_contencao_tokens_vira_alterado():
    # tema expandido deve ser 'alterado', não removido+novo
    v1 = {"M": ["analise swot e bsc"]}
    v2 = {"M": ["analise swot bsc e mapa estrategico"]}
    r = de.diff(v1, v2)
    assert r["resumo"]["n_alterados"] == 1
    assert r["resumo"]["n_removidos"] == 0


def test_diff_estrutural():
    m1 = {"vagas_ac": 3, "salario": "R$ 3.599,70",
          "estrutura_prova": {"objetiva": {"total_questoes": 100}, "discursiva": None}}
    m2 = {"vagas_ac": 23, "salario": "R$ 6.071,09",
          "estrutura_prova": {"objetiva": {"total_questoes": 120}, "discursiva": {"tipo": "x"}}}
    mud = de.diff_estrutural(m1, m2)
    campos = {m["campo"] for m in mud}
    assert "Vagas (AC imediatas)" in campos
    assert "Tem discursiva?" in campos
    assert "Total de questões" in campos


# --------------------------------------------------------------------------- #
# validate_output (via subprocess, testa o CLI de ponta a ponta)
# --------------------------------------------------------------------------- #
def _montar_vault(base: Path, total_q=100, est1=40, est2=60):
    b = base / "SEDES_2026"
    for sub in ["_COMUM/01-EDITAL", "_COMUM/04-MATERIAIS",
                "_COMUM/05-HISTORICO-CONCURSO", "_COMUM/06-SINERGIA",
                "EDAS/02-CRONOGRAMA", "EDAS/03-MAPAS-MATERIAS"]:
        (b / sub).mkdir(parents=True, exist_ok=True)
    (b / ".meta.json").write_text(json.dumps({
        "orgao": "SEDES", "ano": 2026, "modo": "oficial",
        "datas_chave": {"prova_data": "2099-09-06"},
        "estrutura_prova": {"objetiva": {"total_questoes": total_q}},
    }), encoding="utf-8")
    (b / "00-INDICE.md").write_text("# Indice\n[[00-INDICE]]\n", encoding="utf-8")
    (b / "EDAS/03-MAPAS-MATERIAS/01.md").write_text(f"# A\n**Estimativa**: {est1} questoes\n", encoding="utf-8")
    (b / "EDAS/03-MAPAS-MATERIAS/02.md").write_text(f"# B\nEstimativa: {est2} questoes\n", encoding="utf-8")
    (b / "EDAS/02-CRONOGRAMA/cronograma-oficial.md").write_text("# crono\n", encoding="utf-8")
    return b


def _run_validate(path: Path):
    return subprocess.run(
        [sys.executable, str(ROOT / "validate_output.py"), str(path), "--json"],
        capture_output=True, text=True)


def test_validate_estrutura_ok():
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault(Path(d))
        r = _run_validate(b)
        out = json.loads(r.stdout)
        assert out["total_problemas"] == 0, out


def test_validate_soma_divergente():
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault(Path(d), total_q=100, est1=40, est2=30)  # soma 70 != 100
        r = _run_validate(b)
        out = json.loads(r.stdout)
        assert any("DIVERGENTE" in i for i in out["resultados"]["soma_questoes"])


# --------------------------------------------------------------------------- #
# runner standalone (sem pytest)
# --------------------------------------------------------------------------- #
# ---------------- validate_output: regressões ---------------- #
import validate_output as vo  # noqa: E402


def test_wikilink_regex_aceita_pipe_escapado_em_tabela():
    """Em tabela markdown o pipe do wikilink vem escapado (\\|); sem tratar isso,
    todo link em tabela virava LINK QUEBRADO — 74 falsos positivos num concurso real."""
    assert vo.WIKILINK_RE.search(r"[[pasta/arquivo\|rotulo]]").group(1) == "pasta/arquivo"
    assert vo.WIKILINK_RE.search("[[arquivo|rotulo]]").group(1) == "arquivo"
    assert vo.WIKILINK_RE.search("[[arquivo#secao]]").group(1) == "arquivo"
    assert vo.WIKILINK_RE.search("[[arquivo]]").group(1) == "arquivo"


def test_estimativa_nao_captura_meta_de_estudo():
    """O regex antigo casava as metas do checklist ('- [ ] 20 questoes de treino')
    e somava milhares, acusando divergencia em todo concurso."""
    assert vo.ESTIMATIVA_RE.search("**Estimativa**: 5 questoes")
    assert vo.ESTIMATIVA_RE.search("Estimativa: ~8 questoes")
    assert not vo.ESTIMATIVA_RE.search("## Meta\n- [ ] 20 questoes de treino")
    assert not vo.ESTIMATIVA_RE.search("- [ ] resolver 15 questoes")


def test_prova_data_aceita_date_do_yaml():
    """O .meta.yml legado e lido pelo YAML, que devolve datetime.date; o strptime
    so aceita str e quebrava o validador inteiro com TypeError."""
    from datetime import date, timedelta
    futuro = date.today() + timedelta(days=30)
    assert vo.check_cronograma_oficial(Path("."), {"datas_chave": {"prova_data": futuro}}) == []
    assert vo.check_cronograma_oficial(
        Path("."), {"datas_chave": {"prova_data": futuro.isoformat()}}) == []


def test_soma_questoes_por_cargo_em_concurso_multicargo():
    """Materias comuns valem para todos os cargos; somar todos juntos acusava
    divergencia em qualquer concurso multi-cargo."""
    with tempfile.TemporaryDirectory() as d:
        raiz = Path(d)
        for cargo, n in (("_COMUM", 40), ("CARGO-A", 30), ("CARGO-B", 30)):
            sub = raiz / cargo / "03-MAPAS-MATERIAS"
            sub.mkdir(parents=True)
            (sub / "m.md").write_text(f"**Estimativa**: {n} questoes\n", encoding="utf-8")
        # cada cargo soma 40 (comum) + 30 (proprio) = 70
        assert vo.check_soma_questoes(raiz, {"estrutura_prova": {"objetiva": {"total_questoes": 70}}}, 5.0) == []
        assert len(vo.check_soma_questoes(raiz, {"estrutura_prova": {"objetiva": {"total_questoes": 100}}}, 5.0)) == 2



def test_diff_aceita_pasta_do_concurso():
    """Passar a PASTA do concurso é o uso natural (é o que a skill tem em mãos);
    antes estourava IsADirectoryError e só aceitava o arquivo de metadata."""
    with tempfile.TemporaryDirectory() as d:
        for v, tops in (("v1", ["1 A", "2 B"]), ("v2", ["1 A", "2 B", "3 C"])):
            pasta = Path(d) / v
            pasta.mkdir()
            (pasta / ".meta.json").write_text(json.dumps(
                {"materias": [{"nome": "M", "topicos": tops}]}), encoding="utf-8")
        v1 = de.carregar_topicos(Path(d) / "v1")
        v2 = de.carregar_topicos(Path(d) / "v2")
        assert v1 == {"M": ["1 A", "2 B"]}
        assert len(v2["M"]) == 3



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
