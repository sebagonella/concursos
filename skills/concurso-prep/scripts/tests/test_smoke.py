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


def _montar_vault_com_materias(base: Path, com_mapa=True, materia_id=True):
    """Vault mínimo em que o `.meta.json` DECLARA as matérias — é o cruzamento
    que faltava: o validador nunca lia `materias[]`."""
    b = _montar_vault(base)
    meta = json.loads((b / ".meta.json").read_text(encoding="utf-8"))
    meta["materias"] = [{"nome": "Língua Portuguesa", "topicos": ["a"]}]
    meta["materias_por_cargo"] = {
        "EDAS": [{"nome": "Serviço Social", "topicos": ["b"]}]}
    (b / ".meta.json").write_text(json.dumps(meta), encoding="utf-8")
    fm_id = "materia_id: lingua-portuguesa\n" if materia_id else ""
    (b / "EDAS/03-MAPAS-MATERIAS/01-lingua-portuguesa.md").write_text(
        f"---\n{fm_id}---\n# Mapa\n**Estimativa**: 40 questoes\n", encoding="utf-8")
    if com_mapa:
        fm2 = "materia_id: servico-social\n" if materia_id else ""
        (b / "EDAS/03-MAPAS-MATERIAS/06-servico-social.md").write_text(
            f"---\n{fm2}---\n# Mapa\n**Estimativa**: 60 questoes\n", encoding="utf-8")
    return b


def test_validate_acusa_materia_sem_mapa():
    """O check que não existia. `check_soma_questoes` era estruturalmente cego a
    isto: soma os mapas que EXISTEM e aborta com INFO quando não acha nenhum, de
    modo que zero mapas gerados passava como OK."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault_com_materias(Path(d), com_mapa=False)
        out = json.loads(_run_validate(b).stdout)
        cob = out["resultados"]["cobertura_mapas"]
        assert any(i.startswith("FALTA") and "Serviço Social" in i for i in cob), cob
        assert out["total_problemas"] > 0


def test_validate_ok_quando_toda_materia_tem_mapa():
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault_com_materias(Path(d))
        cob = json.loads(_run_validate(b).stdout)["resultados"]["cobertura_mapas"]
        assert not [i for i in cob if not i.startswith("INFO")], cob


def test_validate_le_materias_por_cargo_tambem():
    """Nenhum dos dois lugares é completo sozinho: no SEDES `materias[]` só traz
    as de um cargo; no BB não há `materias_por_cargo` e faltam 3 matérias."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault_com_materias(Path(d))
        meta = json.loads((b / ".meta.json").read_text(encoding="utf-8"))
        assert len(vo.materias_do_meta(meta)) == 2   # 1 de cada lugar


def test_validate_sugere_candidato_por_palavra_nao_por_prefixo():
    """`fundamentos-suas` é o mapa certo de "Fundamentos, Organização, Gestão e
    Marcos Operacionais do SUAS" — compartilham só "suas". E prefixo casava
    lixo: sugeria `conhecimentos-df-…` para "Conhecimentos Específicos"."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_vault_com_materias(Path(d), materia_id=False)
        meta = json.loads((b / ".meta.json").read_text(encoding="utf-8"))
        meta["materias"] = [
            {"nome": "Fundamentos, Organização, Gestão e Marcos Operacionais do SUAS"},
            {"nome": "Conhecimentos Específicos — Agente Social"},
        ]
        meta.pop("materias_por_cargo")
        (b / ".meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (b / "EDAS/03-MAPAS-MATERIAS/04-fundamentos-suas.md").write_text(
            "---\n---\n# M\n", encoding="utf-8")
        cob = vo.check_cobertura_mapas(b, meta)
        suas = [i for i in cob if "SUAS" in i]
        assert suas and suas[0].startswith("AVISO"), suas
        assert "fundamentos-suas" in suas[0]
        agente = [i for i in cob if "Agente Social" in i]
        assert agente and agente[0].startswith("FALTA"), agente


def _montar_concurso_com_duplicatas(base: Path, iguais=True):
    """Dois cargos com o MESMO mapa — o defeito que a 1.4.0 corrige na origem."""
    b = base / "BB_2027"
    corpo = "---\nmateria: \"Português\"\n---\n# Mapa\n\n## 1. Crase\n\n- [ ] regra\n"
    for cargo in ("AGENTE-COMERCIAL", "AGENTE-DE-TECNOLOGIA"):
        d = b / cargo / "03-MAPAS-MATERIAS"
        d.mkdir(parents=True)
        txt = corpo if iguais else corpo + f"\n<!-- {cargo} -->\n" * 40
        (d / "01-lingua-portuguesa.md").write_text(txt, encoding="utf-8")
    # só um cargo cobra esta: não pode ser tocada
    (b / "AGENTE-COMERCIAL/03-MAPAS-MATERIAS/08-vendas.md").write_text(
        corpo, encoding="utf-8")
    (b / "_COMUM").mkdir(parents=True, exist_ok=True)
    (b / "00-INDICE.md").write_text(
        "- [[AGENTE-COMERCIAL/03-MAPAS-MATERIAS/01-lingua-portuguesa|Português]]\n",
        encoding="utf-8")
    return b


def _rodar_consolidar(b, *extra):
    return subprocess.run(
        [sys.executable, str(ROOT / "consolidar_mapas_comuns.py"),
         "--concurso-dir", str(b)] + list(extra), capture_output=True, text=True)


def test_consolidar_dry_run_nao_move():
    with tempfile.TemporaryDirectory() as d:
        b = _montar_concurso_com_duplicatas(Path(d))
        out = _rodar_consolidar(b)
        assert out.returncode == 0, out.stderr
        assert (b / "AGENTE-COMERCIAL/03-MAPAS-MATERIAS/01-lingua-portuguesa.md").exists()
        assert not (b / "_COMUM/03-MAPAS-COMUNS").exists()


def test_consolidar_junta_duplicata_e_conserta_o_wikilink():
    """Mover sem reescrever o wikilink deixa o vault cheio de link quebrado —
    os índices apontam para o mapa pelo caminho completo."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_concurso_com_duplicatas(Path(d))
        out = _rodar_consolidar(b, "--aplicar")
        assert out.returncode == 0, out.stderr
        assert (b / "_COMUM/03-MAPAS-COMUNS/01-lingua-portuguesa.md").exists()
        for cargo in ("AGENTE-COMERCIAL", "AGENTE-DE-TECNOLOGIA"):
            assert not (b / cargo / "03-MAPAS-MATERIAS/01-lingua-portuguesa.md").exists()
        # matéria de um cargo só fica onde está
        assert (b / "AGENTE-COMERCIAL/03-MAPAS-MATERIAS/08-vendas.md").exists()
        idx = (b / "00-INDICE.md").read_text(encoding="utf-8")
        assert "_COMUM/03-MAPAS-COMUNS/01-lingua-portuguesa" in idx
        assert "AGENTE-COMERCIAL/03-MAPAS-MATERIAS/01-lingua" not in idx


def test_consolidar_recusa_quando_os_gemeos_divergem():
    """Conteúdos diferentes podem ser matérias diferentes com o mesmo nome de
    arquivo. Escolher um no palpite apagaria trabalho — vira pendência."""
    with tempfile.TemporaryDirectory() as d:
        b = _montar_concurso_com_duplicatas(Path(d), iguais=False)
        out = _rodar_consolidar(b, "--aplicar")
        assert out.returncode == 2
        assert "divergem" in out.stderr
        assert (b / "AGENTE-COMERCIAL/03-MAPAS-MATERIAS/01-lingua-portuguesa.md").exists()
        assert (b / "AGENTE-DE-TECNOLOGIA/03-MAPAS-MATERIAS/01-lingua-portuguesa.md").exists()


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
